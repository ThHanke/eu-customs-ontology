from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agent.harmonizer import HarmonizationCorrection, harmonize
from src.reasoning.konclude import KoncludeConsistencyError

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_MINIMAL_TTL = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix eucn: <https://w3id.org/eucn/> .

<https://w3id.org/eucn> a owl:Ontology .
eucn:AlcoholicBeverage a owl:Class .
eucn:FermentedDrink a owl:Class .
"""

_IRI_A = "https://w3id.org/eucn/AlcoholicBeverage"
_IRI_B = "https://w3id.org/eucn/FermentedDrink"

_NEW_IRIS_TWO = [
    {
        "iri": _IRI_A,
        "label": "Alcoholic Beverage",
        "definition": "A beverage containing ethanol produced by fermentation.",
        "class_or_property": "class",
    },
    {
        "iri": _IRI_B,
        "label": "Fermented Drink",
        "definition": "A beverage containing ethanol produced by fermentation.",
        "class_or_property": "class",
    },
]


def _make_base_tbox(tmp_path: Path) -> Path:
    p = tmp_path / "base_tbox.ttl"
    p.write_text(_MINIMAL_TTL, encoding="utf-8")
    return p


def _make_tool_response(corrections: list[dict], tool_id: str = "t_001") -> MagicMock:
    """Build a mock Anthropic message response carrying propose_harmonization tool use."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = "propose_harmonization"
    block.id = tool_id
    block.input = {"corrections": corrections}

    response = MagicMock()
    response.content = [block]
    return response


# ---------------------------------------------------------------------------
# Happy path: two IRIs with identical definitions → one equivalentClass link
# ---------------------------------------------------------------------------


def test_happy_path_duplicate_class(tmp_path):
    """Two IRIs with identical definitions → one equivalentClass correction stored."""
    base_tbox = _make_base_tbox(tmp_path)
    out_path = tmp_path / "axiom_candidates" / "ch22" / "harmonization.jsonl"

    correction_payload = [
        {
            "primary_iri": _IRI_A,
            "duplicate_iri": _IRI_B,
            "equivalence_type": "class",
            "rationale": "Identical definitions — same concept.",
        }
    ]

    with patch("src.agent.harmonizer.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_tool_response(correction_payload)

        with patch("src.agent.harmonizer.check_consistency", return_value=True):
            result = harmonize(
                chapter=22,
                new_iris=_NEW_IRIS_TWO,
                base_tbox_path=base_tbox,
                model="claude-opus-4-8",
                out_path=out_path,
            )

    assert len(result) == 1
    assert isinstance(result[0], HarmonizationCorrection)
    assert result[0].primary_iri == _IRI_A
    assert result[0].duplicate_iri == _IRI_B
    assert result[0].equivalence_type == "class"
    assert result[0].rationale != ""

    # JSONL output written
    assert out_path.exists()
    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    stored = json.loads(lines[0])
    assert stored["primary_iri"] == _IRI_A
    assert stored["equivalence_type"] == "class"


# ---------------------------------------------------------------------------
# No duplicates: LLM returns empty list → zero corrections
# ---------------------------------------------------------------------------


def test_no_duplicates_returns_empty(tmp_path):
    """LLM returns empty corrections list → zero corrections, no output file."""
    base_tbox = _make_base_tbox(tmp_path)
    out_path = tmp_path / "harmonization.jsonl"

    with patch("src.agent.harmonizer.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_tool_response([])

        with patch("src.agent.harmonizer.check_consistency", return_value=True):
            result = harmonize(
                chapter=22,
                new_iris=_NEW_IRIS_TWO,
                base_tbox_path=base_tbox,
                model="claude-opus-4-8",
                out_path=out_path,
            )

    assert result == []
    assert not out_path.exists()


# ---------------------------------------------------------------------------
# Konclude failure: correction skipped, warning logged, run completes
# ---------------------------------------------------------------------------


def test_konclude_failure_skips_corrections(tmp_path, caplog):
    """Konclude inconsistency → empty result, warning logged, no raise."""
    import logging

    base_tbox = _make_base_tbox(tmp_path)

    correction_payload = [
        {
            "primary_iri": _IRI_A,
            "duplicate_iri": _IRI_B,
            "equivalence_type": "class",
            "rationale": "Same concept.",
        }
    ]

    with patch("src.agent.harmonizer.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_tool_response(correction_payload)

        with patch(
            "src.agent.harmonizer.check_consistency",
            side_effect=KoncludeConsistencyError("Inconsistent ontology detected."),
        ):
            with caplog.at_level(logging.WARNING, logger="src.agent.harmonizer"):
                result = harmonize(
                    chapter=22,
                    new_iris=_NEW_IRIS_TWO,
                    base_tbox_path=base_tbox,
                    model="claude-opus-4-8",
                )

    assert result == []
    assert any("Konclude" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Empty new_iris: skip LLM call entirely, return []
# ---------------------------------------------------------------------------


def test_empty_new_iris_skips_llm(tmp_path):
    """Empty new_iris → no LLM call, returns empty list immediately."""
    base_tbox = _make_base_tbox(tmp_path)

    with patch("src.agent.harmonizer.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value

        result = harmonize(
            chapter=22,
            new_iris=[],
            base_tbox_path=base_tbox,
            model="claude-opus-4-8",
        )

        mock_client.messages.create.assert_not_called()

    assert result == []


# ---------------------------------------------------------------------------
# No tool use block in response
# ---------------------------------------------------------------------------


def test_no_tool_use_block_returns_empty(tmp_path, caplog):
    """LLM response without tool_use block → warning logged, empty result."""
    import logging

    base_tbox = _make_base_tbox(tmp_path)

    text_block = MagicMock()
    text_block.type = "text"
    text_block.name = None
    mock_response = MagicMock()
    mock_response.content = [text_block]

    with patch("src.agent.harmonizer.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = mock_response

        with caplog.at_level(logging.WARNING, logger="src.agent.harmonizer"):
            result = harmonize(
                chapter=22,
                new_iris=_NEW_IRIS_TWO,
                base_tbox_path=base_tbox,
                model="claude-opus-4-8",
            )

    assert result == []
    assert any("no propose_harmonization" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# out_path=None: corrections returned but not saved
# ---------------------------------------------------------------------------


def test_out_path_none_does_not_save(tmp_path):
    """When out_path=None, corrections are returned but no file is written."""
    base_tbox = _make_base_tbox(tmp_path)

    correction_payload = [
        {
            "primary_iri": _IRI_A,
            "duplicate_iri": _IRI_B,
            "equivalence_type": "class",
            "rationale": "Same concept.",
        }
    ]

    with patch("src.agent.harmonizer.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_tool_response(correction_payload)

        with patch("src.agent.harmonizer.check_consistency", return_value=True):
            result = harmonize(
                chapter=22,
                new_iris=_NEW_IRIS_TWO,
                base_tbox_path=base_tbox,
                model="claude-opus-4-8",
                out_path=None,
            )

    assert len(result) == 1
    # No files written anywhere unexpected
    assert not any(tmp_path.glob("*.jsonl"))


# ---------------------------------------------------------------------------
# Property equivalence type
# ---------------------------------------------------------------------------


def test_property_equivalence_type(tmp_path):
    """equivalence_type='property' is handled correctly."""
    base_tbox = _make_base_tbox(tmp_path)

    iri_p1 = "https://w3id.org/eucn/hasAlcohol"
    iri_p2 = "https://w3id.org/eucn/alcoholContent"

    new_iris = [
        {"iri": iri_p1, "label": "has alcohol", "definition": "ABV fraction.", "class_or_property": "property"},
        {"iri": iri_p2, "label": "alcohol content", "definition": "ABV fraction.", "class_or_property": "property"},
    ]

    correction_payload = [
        {
            "primary_iri": iri_p1,
            "duplicate_iri": iri_p2,
            "equivalence_type": "property",
            "rationale": "Same measure expressed differently.",
        }
    ]

    with patch("src.agent.harmonizer.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_tool_response(correction_payload)

        with patch("src.agent.harmonizer.check_consistency", return_value=True):
            result = harmonize(
                chapter=22,
                new_iris=new_iris,
                base_tbox_path=base_tbox,
                model="claude-opus-4-8",
            )

    assert len(result) == 1
    assert result[0].equivalence_type == "property"


# ---------------------------------------------------------------------------
# Scratch temp file is always deleted (even on Konclude failure)
# ---------------------------------------------------------------------------


def test_scratch_file_deleted_on_konclude_failure(tmp_path):
    """Temp scratch TTL file is cleaned up even when Konclude raises."""
    base_tbox = _make_base_tbox(tmp_path)

    created_temps: list[Path] = []
    real_tempfile = __import__("tempfile")

    original_named_temp = real_tempfile.NamedTemporaryFile

    def _track_temp(**kwargs):
        ctx = original_named_temp(**kwargs)
        created_temps.append(Path(ctx.name))
        return ctx

    correction_payload = [
        {
            "primary_iri": _IRI_A,
            "duplicate_iri": _IRI_B,
            "equivalence_type": "class",
            "rationale": "Same.",
        }
    ]

    with patch("src.agent.harmonizer.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_tool_response(correction_payload)

        with patch("src.agent.harmonizer.tempfile.NamedTemporaryFile", side_effect=_track_temp):
            with patch(
                "src.agent.harmonizer.check_consistency",
                side_effect=KoncludeConsistencyError("bad"),
            ):
                result = harmonize(
                    chapter=22,
                    new_iris=_NEW_IRIS_TWO,
                    base_tbox_path=base_tbox,
                    model="claude-opus-4-8",
                )

    assert result == []
    # All temp files should have been cleaned up
    for p in created_temps:
        assert not p.exists(), f"Temp file not cleaned up: {p}"


# ---------------------------------------------------------------------------
# Konclude binary absent: FileNotFoundError → [] without raising
# ---------------------------------------------------------------------------


def test_konclude_not_found_returns_empty(tmp_path):
    """check_consistency raising FileNotFoundError → warning logged, empty list returned."""
    import logging

    base_tbox = _make_base_tbox(tmp_path)

    correction_payload = [
        {
            "primary_iri": _IRI_A,
            "duplicate_iri": _IRI_B,
            "equivalence_type": "class",
            "rationale": "Same concept.",
        }
    ]

    with patch("src.agent.harmonizer.anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = _make_tool_response(correction_payload)

        with patch(
            "src.agent.harmonizer.check_consistency",
            side_effect=FileNotFoundError("konclude: command not found"),
        ):
            # Must not raise — FileNotFoundError must be swallowed
            result = harmonize(
                chapter=22,
                new_iris=_NEW_IRIS_TWO,
                base_tbox_path=base_tbox,
                model="claude-opus-4-8",
            )

    assert result == []
