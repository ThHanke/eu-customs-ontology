from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from src.agent.chapter_runner import ChapterRunner, ChapterRunResult
from src.agent.node_registry import NodeRegistry
from src.schema.legal_text import LegalSection
from src.schema.node_axiom_set import NodeAxiomSet, NewClass, NewProperty
from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

BFO_MATERIAL = "http://purl.obolibrary.org/obo/BFO_0000040"
EUCN_NS = "https://w3id.org/eucn/"

_FAKE_TBOX_HASH = "a" * 64
_FAKE_STATIC_CTX = "@prefix eucn: <https://w3id.org/eucn/> ."

_MINIMAL_TTL = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix eucn: <https://w3id.org/eucn/> .
<https://w3id.org/eucn> a owl:Ontology .
"""


def _make_section(cn_code: str, note_id: str, source_text: str, language: str = "en") -> LegalSection:
    return LegalSection(
        note_id=note_id,
        chapter=22,
        cn_code=cn_code,
        note_type="test_note",
        source_text=source_text,
        source_text_hash=hashlib.sha256(source_text.encode()).hexdigest(),
        ingestion_date="2026-01-01",
        language=language,
        source_url="https://example.com",
        fetched_at="2026-06-08",
    )


def _make_axiom_set(
    cn_code: str,
    status: str = "proposed",
    new_classes: list | None = None,
    new_properties: list | None = None,
    source_text_hash: str = "a" * 64,
    tbox_hash: str = "b" * 64,
) -> NodeAxiomSet:
    return NodeAxiomSet(
        cn_code=cn_code,
        new_classes=new_classes or [],
        new_properties=new_properties or [],
        restrictions=[],
        coverage_score=0.8,
        coverage_explanation="Test.",
        source_note_ids=["n1"],
        source_text_hash=source_text_hash,
        tbox_hash=tbox_hash,
        status=status,  # type: ignore[arg-type]
        agent_model="test-model",
        generated_at="2026-06-08T10:00:00Z",
    )


def _make_wizard_tree(chapter: int = 22) -> WizardTree:
    node = ClassificationNode(
        node_id="root",
        question_text="What chapter?",
        answer_options=[],
        is_terminal=False,
        cn_code=None,
        path_from_root=[],
    )
    return WizardTree(chapter=chapter, nodes={"root": node}, root_node_id="root")


def _write_notes_jsonl(data_root: Path, chapter: int, sections: list[LegalSection]) -> None:
    notes_dir = data_root / "legal_text" / f"ch{chapter:02d}"
    notes_dir.mkdir(parents=True, exist_ok=True)
    notes_path = notes_dir / "notes.jsonl"
    lines = [s.model_dump_json() for s in sections]
    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_base_tbox(data_root: Path, chapter: int) -> Path:
    tbox_dir = data_root / "agent_tbox" / f"ch{chapter:02d}"
    tbox_dir.mkdir(parents=True, exist_ok=True)
    p = tbox_dir / "base_tbox.ttl"
    p.write_text(_MINIMAL_TTL, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

_PATCH_STATIC_CTX = "src.agent.chapter_runner.context_builder.build_static_context"
_PATCH_TBOX_HASH = "src.agent.chapter_runner.context_builder.compute_tbox_hash"
_PATCH_NODE_CTX = "src.agent.chapter_runner.context_builder.build_node_context"
_PATCH_AGENT_CLS = "src.agent.chapter_runner.LLMAxiomAgent"


def _make_mock_agent(return_value: NodeAxiomSet) -> MagicMock:
    mock_instance = MagicMock()
    mock_instance.run.return_value = return_value
    return mock_instance


# ---------------------------------------------------------------------------
# Test: empty chapter (no legal text notes)
# ---------------------------------------------------------------------------


def test_empty_chapter_returns_zero_result(tmp_path: Path):
    """Chapter with no legal text notes returns ChapterRunResult(0,0,0,0)."""
    runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
    wizard_tree = _make_wizard_tree()
    _make_base_tbox(tmp_path, 22)

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=_FAKE_TBOX_HASH), \
         patch(_PATCH_AGENT_CLS) as MockAgent:

        result = runner.run(wizard_tree)

    assert result == ChapterRunResult(total=0, skipped=0, proposed=0, failed=0)
    MockAgent.assert_not_called()


# ---------------------------------------------------------------------------
# Test: happy path — two nodes, both stale, both proposed
# ---------------------------------------------------------------------------


def test_happy_path_two_stale_nodes_both_proposed(tmp_path: Path):
    """Two stale nodes → two agent calls, two upserts, both proposed."""
    sections = [
        _make_section("22", "note_22", "Chapter 22 text"),
        _make_section("2204", "note_2204", "Wine of fresh grapes"),
    ]
    _write_notes_jsonl(tmp_path, 22, sections)
    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    axiom_22 = _make_axiom_set("22", status="proposed")
    axiom_2204 = _make_axiom_set("2204", status="proposed")
    agent_side_effects = [axiom_22, axiom_2204]

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=_FAKE_TBOX_HASH), \
         patch(_PATCH_NODE_CTX, return_value={"notes_en": [], "notes_de": [], "hierarchy_path": [], "running_tbox": "", "existing_axioms": []}), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        mock_instance.run.side_effect = agent_side_effects
        MockAgentCls.return_value = mock_instance

        result = runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        result = runner.run(wizard_tree)

    assert result.total == 2
    assert result.skipped == 0
    assert result.proposed == 2
    assert result.failed == 0
    assert mock_instance.run.call_count == 2

    # Verify registry was populated
    registry = NodeRegistry(tmp_path / "axiom_candidates" / "ch22")
    assert registry._load_one("22") is not None
    assert registry._load_one("2204") is not None


# ---------------------------------------------------------------------------
# Test: cache hit — node with matching hashes → zero agent calls
# ---------------------------------------------------------------------------


def test_cache_hit_skips_agent_call(tmp_path: Path):
    """A node whose hashes match is skipped — no agent call."""
    # Write notes.jsonl with one section
    source_text = "Wine notes"
    sections = [_make_section("2204", "note_001", source_text)]
    _write_notes_jsonl(tmp_path, 22, sections)
    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    # Pre-populate registry with matching hashes
    combined = source_text  # single section, single text
    source_text_hash = hashlib.sha256(combined.encode()).hexdigest()
    tbox_hash = _FAKE_TBOX_HASH

    registry_dir = tmp_path / "axiom_candidates" / "ch22"
    registry = NodeRegistry(registry_dir)
    stored = _make_axiom_set("2204", status="proposed",
                             source_text_hash=source_text_hash,
                             tbox_hash=tbox_hash)
    registry.upsert(stored)

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=tbox_hash), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        result = runner.run(wizard_tree)

    assert result.total == 1
    assert result.skipped == 1
    assert result.proposed == 0
    assert result.failed == 0
    mock_instance.run.assert_not_called()


# ---------------------------------------------------------------------------
# Test: topological order — shorter codes processed before longer ones
# ---------------------------------------------------------------------------


def test_topological_order(tmp_path: Path):
    """Codes are processed in topological order: 2→4→6→8 digits."""
    sections = [
        _make_section("220410", "note_a", "Six-digit text"),
        _make_section("22041000", "note_b", "Eight-digit text"),
        _make_section("2204", "note_c", "Four-digit text"),
        _make_section("22", "note_d", "Two-digit text"),
    ]
    _write_notes_jsonl(tmp_path, 22, sections)
    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    processed_order: list[str] = []

    def _capture_agent_run(cn_code, **kwargs):
        processed_order.append(cn_code)
        return _make_axiom_set(cn_code, status="proposed")

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=_FAKE_TBOX_HASH), \
         patch(_PATCH_NODE_CTX, return_value={"notes_en": ["text"], "notes_de": [], "hierarchy_path": [], "running_tbox": "", "existing_axioms": []}), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        mock_instance.run.side_effect = _capture_agent_run
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        runner.run(wizard_tree)

    assert processed_order == ["22", "2204", "220410", "22041000"]


# ---------------------------------------------------------------------------
# Test: error path — agent returns failed for one node, run continues
# ---------------------------------------------------------------------------


def test_error_path_failed_node_continues(tmp_path: Path):
    """Agent returns 'failed' for one node; run continues, failure counted."""
    sections = [
        _make_section("22", "note_22", "Chapter 22"),
        _make_section("2204", "note_2204", "Wine"),
    ]
    _write_notes_jsonl(tmp_path, 22, sections)
    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    axiom_proposed = _make_axiom_set("22", status="proposed")
    axiom_failed = _make_axiom_set("2204", status="failed")

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=_FAKE_TBOX_HASH), \
         patch(_PATCH_NODE_CTX, return_value={"notes_en": ["text"], "notes_de": [], "hierarchy_path": [], "running_tbox": "", "existing_axioms": []}), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        mock_instance.run.side_effect = [axiom_proposed, axiom_failed]
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        result = runner.run(wizard_tree)

    assert result.total == 2
    assert result.proposed == 1
    assert result.failed == 1
    assert result.skipped == 0
    assert mock_instance.run.call_count == 2


# ---------------------------------------------------------------------------
# Test: running TBox grows after each proposed node
# ---------------------------------------------------------------------------


def test_running_tbox_grows_after_proposed_nodes(tmp_path: Path):
    """After each proposed node with new classes, the running TBox grows."""
    sections = [
        _make_section("22", "note_22", "Chapter 22"),
        _make_section("2204", "note_2204", "Wine"),
    ]
    _write_notes_jsonl(tmp_path, 22, sections)
    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    new_class_22 = NewClass(
        iri_local_name="ChapterClass",
        label_en="Chapter Class",
        label_de="Kapitel Klasse",
        definition_en="A test class.",
        bfo_parent_iri=BFO_MATERIAL,
        class_type="material_entity",
    )
    new_class_2204 = NewClass(
        iri_local_name="WineClass",
        label_en="Wine Class",
        label_de="Weinweinwein",
        definition_en="A wine class.",
        bfo_parent_iri=BFO_MATERIAL,
        class_type="material_entity",
    )

    axiom_22 = _make_axiom_set("22", status="proposed", new_classes=[new_class_22])
    axiom_2204 = _make_axiom_set("2204", status="proposed", new_classes=[new_class_2204])

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=_FAKE_TBOX_HASH), \
         patch(_PATCH_NODE_CTX, return_value={"notes_en": ["text"], "notes_de": [], "hierarchy_path": [], "running_tbox": "", "existing_axioms": []}), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        mock_instance.run.side_effect = [axiom_22, axiom_2204]
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        result = runner.run(wizard_tree)

    running_tbox_path = tmp_path / "agent_tbox" / "ch22" / "running.ttl"
    assert running_tbox_path.exists()
    content = running_tbox_path.read_text(encoding="utf-8")
    assert "ChapterClass" in content
    assert "WineClass" in content


# ---------------------------------------------------------------------------
# Test: running TBox reset at start of each chapter run
# ---------------------------------------------------------------------------


def test_running_tbox_reset_on_each_run(tmp_path: Path):
    """The running TBox is deleted at the start of each chapter run."""
    # Pre-create a running TBox with old content
    running_dir = tmp_path / "agent_tbox" / "ch22"
    running_dir.mkdir(parents=True, exist_ok=True)
    running_tbox_path = running_dir / "running.ttl"
    running_tbox_path.write_text("old content from previous run", encoding="utf-8")

    # No sections → no processing
    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=_FAKE_TBOX_HASH), \
         patch(_PATCH_AGENT_CLS):

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        runner.run(wizard_tree)

    # The file should have been deleted since no new axioms were proposed
    assert not running_tbox_path.exists()


# ---------------------------------------------------------------------------
# Test: force flag overrides cache
# ---------------------------------------------------------------------------


def test_force_flag_overrides_cache(tmp_path: Path):
    """With force=True, even cached nodes are re-processed."""
    source_text = "Wine notes"
    sections = [_make_section("2204", "note_001", source_text)]
    _write_notes_jsonl(tmp_path, 22, sections)
    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    # Pre-populate registry with matching hashes
    combined = source_text
    source_text_hash = hashlib.sha256(combined.encode()).hexdigest()
    tbox_hash = _FAKE_TBOX_HASH

    registry_dir = tmp_path / "axiom_candidates" / "ch22"
    registry = NodeRegistry(registry_dir)
    stored = _make_axiom_set("2204", status="proposed",
                             source_text_hash=source_text_hash,
                             tbox_hash=tbox_hash)
    registry.upsert(stored)

    axiom_result = _make_axiom_set("2204", status="proposed",
                                   source_text_hash=source_text_hash,
                                   tbox_hash=tbox_hash)

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=tbox_hash), \
         patch(_PATCH_NODE_CTX, return_value={"notes_en": ["text"], "notes_de": [], "hierarchy_path": [], "running_tbox": "", "existing_axioms": []}), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        mock_instance.run.return_value = axiom_result
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        result = runner.run(wizard_tree, force=True)

    assert result.total == 1
    assert result.skipped == 0
    assert result.proposed == 1
    mock_instance.run.assert_called_once()


# ---------------------------------------------------------------------------
# Test: base TBox built from scratch when no flat TTL exists
# ---------------------------------------------------------------------------


def test_base_tbox_built_from_scratch_when_not_found(tmp_path: Path):
    """When no flat TTL glob matches, a base_tbox.ttl is built from scratch."""
    # No ontology/ directory with flat TTL — add a section so processing is triggered
    sections = [_make_section("2204", "note_001", "Wine")]
    _write_notes_jsonl(tmp_path, 22, sections)
    wizard_tree = _make_wizard_tree()
    axiom_result = _make_axiom_set("2204", status="proposed")

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=_FAKE_TBOX_HASH), \
         patch("src.agent.chapter_runner.build_tbox") as mock_build_tbox, \
         patch(_PATCH_NODE_CTX, return_value={"notes_en": ["text"], "notes_de": [], "hierarchy_path": [], "running_tbox": "", "existing_axioms": []}), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        # build_tbox does nothing; Graph remains empty, serialize still produces valid TTL
        mock_build_tbox.return_value = None
        mock_instance = MagicMock()
        mock_instance.run.return_value = axiom_result
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        runner.run(wizard_tree)

    # The base_tbox.ttl should have been written
    base_tbox_path = tmp_path / "agent_tbox" / "ch22" / "base_tbox.ttl"
    assert base_tbox_path.exists()


# ---------------------------------------------------------------------------
# Test: base TBox found via glob when flat TTL exists
# ---------------------------------------------------------------------------


def test_base_tbox_from_flat_ttl_glob(tmp_path: Path):
    """When flat TTL exists, it is used as base_tbox_path."""
    sections = [_make_section("2204", "note_001", "Wine")]
    _write_notes_jsonl(tmp_path, 22, sections)

    # Create a flat TTL file
    ontology_dir = tmp_path / "ontology"
    ontology_dir.mkdir(parents=True, exist_ok=True)
    flat_ttl = ontology_dir / "eucn-ch22-2026-flat.ttl"
    flat_ttl.write_text(_MINIMAL_TTL, encoding="utf-8")

    wizard_tree = _make_wizard_tree()
    axiom_result = _make_axiom_set("2204", status="proposed")

    base_tbox_used: list[Path] = []

    def _capture_agent_run(cn_code, node_context, base_tbox_path, running_tbox_path, existing_axioms_ttl=""):
        base_tbox_used.append(base_tbox_path)
        return axiom_result

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=_FAKE_TBOX_HASH), \
         patch(_PATCH_NODE_CTX, return_value={"notes_en": ["text"], "notes_de": [], "hierarchy_path": [], "running_tbox": "", "existing_axioms": []}), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        mock_instance.run.side_effect = _capture_agent_run
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        runner.run(wizard_tree)

    assert len(base_tbox_used) == 1
    assert base_tbox_used[0] == flat_ttl


# ---------------------------------------------------------------------------
# Test: source_text_hash uses full text when full/ file exists
# ---------------------------------------------------------------------------


def test_source_text_hash_uses_full_text_file(tmp_path: Path):
    """When full/{note_id}.txt exists, it is used instead of source_text."""
    source_text = "Short note"
    full_text = "Long full legal text for note 001"
    sections = [_make_section("2204", "note_001", source_text)]
    _write_notes_jsonl(tmp_path, 22, sections)

    # Write full text file
    full_dir = tmp_path / "legal_text" / "ch22" / "full"
    full_dir.mkdir(parents=True, exist_ok=True)
    (full_dir / "note_001.txt").write_text(full_text, encoding="utf-8")

    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    expected_hash = hashlib.sha256(full_text.encode()).hexdigest()
    tbox_hash = _FAKE_TBOX_HASH

    # Pre-populate registry with the expected hash (cache hit scenario)
    registry_dir = tmp_path / "axiom_candidates" / "ch22"
    registry = NodeRegistry(registry_dir)
    stored = _make_axiom_set("2204", status="proposed",
                             source_text_hash=expected_hash,
                             tbox_hash=tbox_hash)
    registry.upsert(stored)

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=tbox_hash), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        result = runner.run(wizard_tree)

    # Should be a cache hit — no agent call
    assert result.skipped == 1
    mock_instance.run.assert_not_called()


# ---------------------------------------------------------------------------
# Test: ChapterRunResult is a dataclass with expected fields
# ---------------------------------------------------------------------------


def test_chapter_run_result_defaults():
    r = ChapterRunResult()
    assert r.total == 0
    assert r.skipped == 0
    assert r.proposed == 0
    assert r.failed == 0


def test_chapter_run_result_equality():
    a = ChapterRunResult(total=5, skipped=2, proposed=2, failed=1)
    b = ChapterRunResult(total=5, skipped=2, proposed=2, failed=1)
    assert a == b


# ---------------------------------------------------------------------------
# Test: multiple sections per cn_code
# ---------------------------------------------------------------------------


def test_multiple_sections_per_cn_code_hash(tmp_path: Path):
    """Multiple sections for a cn_code are sorted by note_id and joined."""
    # Sections in reverse note_id order to verify sorting
    sections = [
        _make_section("2204", "note_z", "Second note (z)"),
        _make_section("2204", "note_a", "First note (a)"),
    ]
    _write_notes_jsonl(tmp_path, 22, sections)
    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    # Hash should be SHA256 of "First note (a)\nSecond note (z)" (sorted by note_id)
    expected_hash = hashlib.sha256("First note (a)\nSecond note (z)".encode()).hexdigest()
    tbox_hash = _FAKE_TBOX_HASH

    # Pre-populate registry with the expected hash (cache hit)
    registry_dir = tmp_path / "axiom_candidates" / "ch22"
    registry = NodeRegistry(registry_dir)
    stored = _make_axiom_set("2204", status="proposed",
                             source_text_hash=expected_hash,
                             tbox_hash=tbox_hash)
    registry.upsert(stored)

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=tbox_hash), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        result = runner.run(wizard_tree)

    assert result.skipped == 1
    mock_instance.run.assert_not_called()


# ---------------------------------------------------------------------------
# Test: LLMAxiomAgent instantiated with correct model and static_context
# ---------------------------------------------------------------------------


def test_agent_instantiated_with_correct_params(tmp_path: Path):
    """ChapterRunner passes model and static_context to LLMAxiomAgent."""
    sections = [_make_section("2204", "note_001", "Wine")]
    _write_notes_jsonl(tmp_path, 22, sections)
    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    axiom_result = _make_axiom_set("2204", status="proposed")

    with patch(_PATCH_STATIC_CTX, return_value="MY_STATIC_CONTEXT"), \
         patch(_PATCH_TBOX_HASH, return_value=_FAKE_TBOX_HASH), \
         patch(_PATCH_NODE_CTX, return_value={"notes_en": ["text"], "notes_de": [], "hierarchy_path": [], "running_tbox": "", "existing_axioms": []}), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        mock_instance.run.return_value = axiom_result
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="my-special-model", data_root=tmp_path)
        runner.run(wizard_tree)

    MockAgentCls.assert_called_once_with(
        model="my-special-model",
        static_context="MY_STATIC_CONTEXT",
    )


# ---------------------------------------------------------------------------
# Test: running TBox not written for failed nodes
# ---------------------------------------------------------------------------


def test_running_tbox_not_written_for_failed_node(tmp_path: Path):
    """A failed node does not contribute classes/props to the running TBox."""
    new_class = NewClass(
        iri_local_name="ShouldNotAppear",
        label_en="Should Not Appear",
        label_de="Sollte nicht erscheinen",
        definition_en="This class should not be in running TBox.",
        bfo_parent_iri=BFO_MATERIAL,
        class_type="material_entity",
    )
    sections = [_make_section("2204", "note_001", "Wine")]
    _write_notes_jsonl(tmp_path, 22, sections)
    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    # Agent returns failed with new_classes (which should NOT be written)
    failed_set = NodeAxiomSet(
        cn_code="2204",
        new_classes=[new_class],
        new_properties=[],
        restrictions=[],
        coverage_score=0.0,
        coverage_explanation="failed",
        source_note_ids=[],
        source_text_hash="a" * 64,
        tbox_hash="b" * 64,
        status="failed",
        agent_model="test-model",
        generated_at="2026-06-08T10:00:00Z",
    )

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=_FAKE_TBOX_HASH), \
         patch(_PATCH_NODE_CTX, return_value={"notes_en": ["text"], "notes_de": [], "hierarchy_path": [], "running_tbox": "", "existing_axioms": []}), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        mock_instance.run.return_value = failed_set
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        runner.run(wizard_tree)

    running_tbox_path = tmp_path / "agent_tbox" / "ch22" / "running.ttl"
    assert not running_tbox_path.exists()


# ---------------------------------------------------------------------------
# Test: agent raises exception — chapter run continues, failure counted
# ---------------------------------------------------------------------------


def test_agent_exception_continues_and_counts_failure(tmp_path: Path):
    """When agent.run raises an exception, the loop continues and failed is incremented."""
    sections = [
        _make_section("22", "note_22", "Chapter 22"),
        _make_section("2204", "note_2204", "Wine"),
    ]
    _write_notes_jsonl(tmp_path, 22, sections)
    _make_base_tbox(tmp_path, 22)
    wizard_tree = _make_wizard_tree()

    axiom_proposed = _make_axiom_set("22", status="proposed")

    with patch(_PATCH_STATIC_CTX, return_value=_FAKE_STATIC_CTX), \
         patch(_PATCH_TBOX_HASH, return_value=_FAKE_TBOX_HASH), \
         patch(_PATCH_NODE_CTX, return_value={"notes_en": ["text"], "notes_de": [], "hierarchy_path": [], "running_tbox": "", "existing_axioms": []}), \
         patch(_PATCH_AGENT_CLS) as MockAgentCls:

        mock_instance = MagicMock()
        # First call succeeds; second call raises
        mock_instance.run.side_effect = [axiom_proposed, RuntimeError("API error")]
        MockAgentCls.return_value = mock_instance

        runner = ChapterRunner(chapter=22, model="test-model", data_root=tmp_path)
        result = runner.run(wizard_tree)

    assert result.total == 2
    assert result.proposed == 1
    assert result.failed == 1
    assert result.skipped == 0
    assert mock_instance.run.call_count == 2
