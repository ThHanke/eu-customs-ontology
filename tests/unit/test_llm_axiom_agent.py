from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agent.llm_axiom_agent import LLMAxiomAgent
from src.reasoning.konclude import KoncludeConsistencyError
from src.schema.node_axiom_set import NodeAxiomSet

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_MINIMAL_TTL = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix eucn: <https://w3id.org/eucn/> .

<https://w3id.org/eucn> a owl:Ontology .
"""

_VALID_TOOL_INPUT = {
    "cn_code": "2204",
    "new_classes": [],
    "new_properties": [],
    "restrictions": [],
    "coverage_score": 0.8,
    "coverage_explanation": "Covered main criteria.",
    "source_note_ids": ["note1"],
    "source_text_hash": "a" * 64,
    "tbox_hash": "b" * 64,
}


def _make_mock_response(tool_input: dict, tool_id: str = "tool_123") -> MagicMock:
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.id = tool_id
    mock_tool_use.input = tool_input
    mock_response = MagicMock()
    mock_response.content = [mock_tool_use]
    return mock_response


def _make_base_tbox(tmp_path: Path) -> Path:
    p = tmp_path / "base_tbox.ttl"
    p.write_text(_MINIMAL_TTL, encoding="utf-8")
    return p


def _make_running_tbox(tmp_path: Path) -> Path:
    # Return a path that does NOT exist — agent should handle this gracefully
    return tmp_path / "running_tbox.ttl"


def _make_agent() -> LLMAxiomAgent:
    with patch("src.agent.llm_axiom_agent.anthropic.Anthropic"):
        agent = LLMAxiomAgent(model="claude-opus-4-8", static_context="@prefix eucn: <https://w3id.org/eucn/> .")
    return agent


# ---------------------------------------------------------------------------
# Test: happy path (first attempt consistent)
# ---------------------------------------------------------------------------


def test_happy_path_returns_proposed(tmp_path):
    """First attempt is consistent → status='proposed'."""
    base_tbox = _make_base_tbox(tmp_path)
    running_tbox = _make_running_tbox(tmp_path)

    with patch("src.agent.llm_axiom_agent.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_mock_response(_VALID_TOOL_INPUT)

        with patch("src.agent.llm_axiom_agent.check_consistency", return_value=True):
            agent = LLMAxiomAgent(model="claude-opus-4-8", static_context="@prefix eucn: <https://w3id.org/eucn/> .")
            result = agent.run(
                cn_code="2204",
                node_context={
                    "hierarchy_path": [{"cn_code": "22", "question_texts": ["Wine?"]}],
                    "notes_en": ["Wine of fresh grapes."],
                    "notes_de": ["Wein aus frischen Weintrauben."],
                    "running_tbox": "",
                    "existing_axioms": [],
                },
                base_tbox_path=base_tbox,
                running_tbox_path=running_tbox,
                existing_axioms_ttl="",
            )

    assert isinstance(result, NodeAxiomSet)
    assert result.status == "proposed"
    assert result.cn_code == "2204"
    assert result.coverage_score == 0.8
    assert mock_client.messages.create.call_count == 1


# ---------------------------------------------------------------------------
# Test: retry (first attempt inconsistent, second consistent)
# ---------------------------------------------------------------------------


def test_retry_second_attempt_consistent(tmp_path):
    """First attempt inconsistent, second consistent → proposed after 2 API calls."""
    base_tbox = _make_base_tbox(tmp_path)
    running_tbox = _make_running_tbox(tmp_path)

    with patch("src.agent.llm_axiom_agent.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_mock_response(_VALID_TOOL_INPUT)

        consistency_results = [
            KoncludeConsistencyError("Inconsistent.\nstderr: [INFO] ignored line\nActual error line"),
            True,
        ]
        call_count = [0]

        def _mock_check(path):
            idx = call_count[0]
            call_count[0] += 1
            r = consistency_results[idx]
            if isinstance(r, Exception):
                raise r
            return r

        with patch("src.agent.llm_axiom_agent.check_consistency", side_effect=_mock_check):
            agent = LLMAxiomAgent(model="claude-opus-4-8", static_context="ctx")
            result = agent.run(
                cn_code="2204",
                node_context={
                    "hierarchy_path": [],
                    "notes_en": ["Some wine note."],
                    "notes_de": [],
                    "running_tbox": "",
                    "existing_axioms": [],
                },
                base_tbox_path=base_tbox,
                running_tbox_path=running_tbox,
                existing_axioms_ttl="",
            )

    assert result.status == "proposed"
    assert mock_client.messages.create.call_count == 2


def test_retry_sends_tool_result_with_is_error(tmp_path):
    """On inconsistency, the second API call must include a tool_result with is_error=True."""
    base_tbox = _make_base_tbox(tmp_path)
    running_tbox = _make_running_tbox(tmp_path)

    captured_calls: list[dict] = []

    def _capture_create(**kwargs):
        captured_calls.append(kwargs)
        return _make_mock_response(_VALID_TOOL_INPUT)

    consistency_results = [
        KoncludeConsistencyError("Inconsistent.\nstderr: error detail"),
        True,
    ]
    call_count = [0]

    def _mock_check(path):
        idx = call_count[0]
        call_count[0] += 1
        r = consistency_results[idx]
        if isinstance(r, Exception):
            raise r
        return r

    with patch("src.agent.llm_axiom_agent.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.side_effect = _capture_create

        with patch("src.agent.llm_axiom_agent.check_consistency", side_effect=_mock_check):
            agent = LLMAxiomAgent(model="claude-opus-4-8", static_context="ctx")
            agent.run(
                cn_code="2204",
                node_context={
                    "hierarchy_path": [],
                    "notes_en": ["Wine note"],
                    "notes_de": [],
                    "running_tbox": "",
                    "existing_axioms": [],
                },
                base_tbox_path=base_tbox,
                running_tbox_path=running_tbox,
                existing_axioms_ttl="",
            )

    assert len(captured_calls) == 2
    second_messages = captured_calls[1]["messages"]
    # The last user message should contain tool_result with is_error=True
    last_user = second_messages[-1]
    assert last_user["role"] == "user"
    assert isinstance(last_user["content"], list)
    tool_result = last_user["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["is_error"] is True


# ---------------------------------------------------------------------------
# Test: max retries exhausted
# ---------------------------------------------------------------------------


def test_max_retries_returns_failed(tmp_path):
    """3 inconsistent attempts → status='failed', coverage_score=0."""
    base_tbox = _make_base_tbox(tmp_path)
    running_tbox = _make_running_tbox(tmp_path)

    with patch("src.agent.llm_axiom_agent.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_mock_response(_VALID_TOOL_INPUT)

        with patch(
            "src.agent.llm_axiom_agent.check_consistency",
            side_effect=KoncludeConsistencyError("Inconsistent.\nstderr: bad axiom"),
        ):
            agent = LLMAxiomAgent(model="claude-opus-4-8", static_context="ctx")
            result = agent.run(
                cn_code="2204",
                node_context={
                    "hierarchy_path": [],
                    "notes_en": ["Some note."],
                    "notes_de": [],
                    "running_tbox": "",
                    "existing_axioms": [],
                },
                base_tbox_path=base_tbox,
                running_tbox_path=running_tbox,
                existing_axioms_ttl="",
            )

    assert result.status == "failed"
    assert result.coverage_score == 0
    assert mock_client.messages.create.call_count == 3


# ---------------------------------------------------------------------------
# Test: empty notes → NodeAxiomSet with coverage_score=0, no API call
# ---------------------------------------------------------------------------


def test_empty_notes_no_api_call(tmp_path):
    """No notes → NodeAxiomSet with empty lists, coverage_score=0.0, no API call."""
    base_tbox = _make_base_tbox(tmp_path)
    running_tbox = _make_running_tbox(tmp_path)

    with patch("src.agent.llm_axiom_agent.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value

        agent = LLMAxiomAgent(model="claude-opus-4-8", static_context="ctx")
        result = agent.run(
            cn_code="2204",
            node_context={
                "hierarchy_path": [],
                "notes_en": [],
                "notes_de": [],
                "running_tbox": "",
                "existing_axioms": [],
            },
            base_tbox_path=base_tbox,
            running_tbox_path=running_tbox,
            existing_axioms_ttl="",
        )

    assert result.status == "proposed"
    assert result.coverage_score == 0.0
    assert result.coverage_explanation == "No legal text available"
    assert result.new_classes == []
    assert result.new_properties == []
    assert result.restrictions == []
    mock_client.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# Test: tool_use block is parsed correctly
# ---------------------------------------------------------------------------


def test_tool_use_block_parsed_correctly(tmp_path):
    """The propose_axioms tool use block input is correctly parsed into NodeAxiomSet fields."""
    base_tbox = _make_base_tbox(tmp_path)
    running_tbox = _make_running_tbox(tmp_path)

    tool_input = {
        "cn_code": "2204.21",
        "new_classes": [
            {
                "iri_local_name": "FermentedGrapeProduct",
                "label_en": "Fermented Grape Product",
                "label_de": "Fermentiertes Traubenprodukt",
                "definition_en": "A material entity from fermented grapes.",
                "bfo_parent_iri": "http://purl.obolibrary.org/obo/BFO_0000030",
                "class_type": "material_entity",
            }
        ],
        "new_properties": [
            {
                "iri_local_name": "hasAlcoholicStrength",
                "label_en": "has alcoholic strength",
                "property_type": "data",
                "domain_iri": "https://w3id.org/eucn/FermentedGrapeProduct",
                "range_iri": "http://www.w3.org/2001/XMLSchema#decimal",
                "is_functional": True,
            }
        ],
        "restrictions": [
            {
                "owl_class_iri": "https://w3id.org/eucn/FermentedGrapeProduct",
                "restriction_type": "decimalRange",
                "property_iri": "https://w3id.org/eucn/hasAlcoholicStrength",
                "value": "15.0",
                "facet": "http://www.w3.org/2001/XMLSchema#maxInclusive",
            }
        ],
        "coverage_score": 0.9,
        "coverage_explanation": "Covers alcohol content.",
        "source_note_ids": ["note1", "note2"],
        "source_text_hash": "c" * 64,
        "tbox_hash": "d" * 64,
    }

    with patch("src.agent.llm_axiom_agent.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_mock_response(tool_input)

        with patch("src.agent.llm_axiom_agent.check_consistency", return_value=True):
            agent = LLMAxiomAgent(model="claude-opus-4-8", static_context="ctx")
            result = agent.run(
                cn_code="2204.21",
                node_context={
                    "hierarchy_path": [],
                    "notes_en": ["Wine of fresh grapes."],
                    "notes_de": [],
                    "running_tbox": "",
                    "existing_axioms": [],
                },
                base_tbox_path=base_tbox,
                running_tbox_path=running_tbox,
                existing_axioms_ttl="",
            )

    assert result.cn_code == "2204.21"
    assert len(result.new_classes) == 1
    assert result.new_classes[0].iri_local_name == "FermentedGrapeProduct"
    assert result.new_classes[0].class_type == "material_entity"
    assert len(result.new_properties) == 1
    assert result.new_properties[0].iri_local_name == "hasAlcoholicStrength"
    assert result.new_properties[0].is_functional is True
    assert len(result.restrictions) == 1
    assert result.restrictions[0].restriction_type == "decimalRange"
    assert result.coverage_score == 0.9
    assert result.source_note_ids == ["note1", "note2"]
    assert result.agent_model == "claude-opus-4-8"
    assert result.generated_at != ""


# ---------------------------------------------------------------------------
# Test: INFO lines are stripped from Konclude feedback
# ---------------------------------------------------------------------------


def test_info_lines_stripped_from_feedback(tmp_path):
    """[INFO] lines from Konclude stderr are stripped before sending as tool result."""
    base_tbox = _make_base_tbox(tmp_path)
    running_tbox = _make_running_tbox(tmp_path)

    captured_calls: list[dict] = []

    def _capture_create(**kwargs):
        captured_calls.append(kwargs)
        return _make_mock_response(_VALID_TOOL_INPUT)

    konclude_error = KoncludeConsistencyError(
        "Ontology is inconsistent.\n"
        "stderr: [INFO] Loading ontology\n"
        "[INFO] Parsing done\n"
        "ERROR: Class clash detected\n"
        "[INFO] Cleanup\n"
    )

    consistency_results = [konclude_error, True]
    call_count = [0]

    def _mock_check(path):
        idx = call_count[0]
        call_count[0] += 1
        r = consistency_results[idx]
        if isinstance(r, Exception):
            raise r
        return r

    with patch("src.agent.llm_axiom_agent.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.side_effect = _capture_create

        with patch("src.agent.llm_axiom_agent.check_consistency", side_effect=_mock_check):
            agent = LLMAxiomAgent(model="claude-opus-4-8", static_context="ctx")
            agent.run(
                cn_code="2204",
                node_context={
                    "hierarchy_path": [],
                    "notes_en": ["Wine note"],
                    "notes_de": [],
                    "running_tbox": "",
                    "existing_axioms": [],
                },
                base_tbox_path=base_tbox,
                running_tbox_path=running_tbox,
                existing_axioms_ttl="",
            )

    second_messages = captured_calls[1]["messages"]
    last_user = second_messages[-1]
    feedback_content = last_user["content"][0]["content"]
    assert "[INFO]" not in feedback_content
    assert "ERROR: Class clash detected" in feedback_content


# ---------------------------------------------------------------------------
# Test: existing_axioms_ttl is included in scratch graph
# ---------------------------------------------------------------------------


def test_existing_axioms_ttl_included_in_scratch(tmp_path):
    """existing_axioms_ttl is parsed and included in the scratch consistency check."""
    base_tbox = _make_base_tbox(tmp_path)
    running_tbox = _make_running_tbox(tmp_path)

    existing_ttl = (
        "@prefix eucn: <https://w3id.org/eucn/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "eucn:ExistingClass a owl:Class .\n"
    )

    scratch_paths: list[Path] = []
    real_check = __import__("src.reasoning.konclude", fromlist=["check_consistency"]).check_consistency

    def _capture_scratch(path: Path) -> bool:
        scratch_paths.append(path)
        content = Path(path).read_text()
        # Verify existing_ttl content is present in scratch
        assert "ExistingClass" in content, f"ExistingClass not found in scratch TTL:\n{content}"
        return True

    with patch("src.agent.llm_axiom_agent.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_mock_response(_VALID_TOOL_INPUT)

        with patch("src.agent.llm_axiom_agent.check_consistency", side_effect=_capture_scratch):
            agent = LLMAxiomAgent(model="claude-opus-4-8", static_context="ctx")
            agent.run(
                cn_code="2204",
                node_context={
                    "hierarchy_path": [],
                    "notes_en": ["Wine note"],
                    "notes_de": [],
                    "running_tbox": "",
                    "existing_axioms": [],
                },
                base_tbox_path=base_tbox,
                running_tbox_path=running_tbox,
                existing_axioms_ttl=existing_ttl,
            )

    assert len(scratch_paths) == 1


# ---------------------------------------------------------------------------
# Test: system prompt uses template from file
# ---------------------------------------------------------------------------


def test_system_prompt_contains_static_context():
    """The system prompt passed to the API embeds the static_context."""
    captured: list[dict] = []

    def _capture(**kwargs):
        captured.append(kwargs)
        return _make_mock_response(_VALID_TOOL_INPUT)

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_path = Path(tmp_str)
        base_tbox = _make_base_tbox(tmp_path)
        running_tbox = _make_running_tbox(tmp_path)

        with patch("src.agent.llm_axiom_agent.anthropic.Anthropic") as MockClient:
            mock_client = MockClient.return_value
            mock_client.messages.create.side_effect = _capture

            with patch("src.agent.llm_axiom_agent.check_consistency", return_value=True):
                agent = LLMAxiomAgent(
                    model="claude-opus-4-8",
                    static_context="MY_UNIQUE_STATIC_CONTEXT_XYZ",
                )
                agent.run(
                    cn_code="2204",
                    node_context={
                        "hierarchy_path": [],
                        "notes_en": ["Wine note"],
                        "notes_de": [],
                        "running_tbox": "",
                        "existing_axioms": [],
                    },
                    base_tbox_path=base_tbox,
                    running_tbox_path=running_tbox,
                    existing_axioms_ttl="",
                )

    assert len(captured) == 1
    system_prompt = captured[0]["system"]
    assert "MY_UNIQUE_STATIC_CONTEXT_XYZ" in system_prompt
