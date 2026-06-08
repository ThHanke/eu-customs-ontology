from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agent.chapter_runner import ChapterRunResult
from src.agent.coverage_reporter import (
    ChapterCoverageReport,
    build_report,
    print_summary,
    write_report,
)
from src.agent.node_registry import NodeRegistry
from src.schema.node_axiom_set import NodeAxiomSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BFO_MATERIAL = "http://purl.obolibrary.org/obo/BFO_0000040"
EUCN_NS = "https://w3id.org/eucn/"

_RESTRICTION = dict(
    owl_class_iri=f"{EUCN_NS}Wine",
    restriction_type="someValuesFrom",
    property_iri=f"{EUCN_NS}producedFrom",
    value=f"{EUCN_NS}Grape",
    facet=None,
)


def _make_axiom_set(
    cn_code: str = "2204",
    source_text_hash: str = "aabbccdd",
    tbox_hash: str = "11223344",
    status: str = "proposed",
    coverage_score: float = 0.8,
    coverage_explanation: str = "Test coverage.",
    generated_at: str = "2026-06-08T10:00:00Z",
) -> NodeAxiomSet:
    return NodeAxiomSet(
        cn_code=cn_code,
        new_classes=[],
        new_properties=[],
        restrictions=[_RESTRICTION],
        coverage_score=coverage_score,
        coverage_explanation=coverage_explanation,
        source_note_ids=["note_001"],
        source_text_hash=source_text_hash,
        tbox_hash=tbox_hash,
        status=status,  # type: ignore[arg-type]
        agent_model="test-model",
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# Happy path: 3 nodes with scores 0.9, 0.3, 0.7 → mean 0.63, one low-coverage
# ---------------------------------------------------------------------------


def test_build_report_happy_path(tmp_path: Path):
    """Test with 3 nodes (scores 0.9, 0.3, 0.7) → mean 0.63, one low-coverage."""
    registry = NodeRegistry(tmp_path)

    # Create 3 proposed nodes with different scores
    axiom_sets = [
        _make_axiom_set(cn_code="2204.1", coverage_score=0.9),
        _make_axiom_set(cn_code="2204.2", coverage_score=0.3, coverage_explanation="Partial coverage."),
        _make_axiom_set(cn_code="2204.3", coverage_score=0.7),
    ]

    for axiom_set in axiom_sets:
        registry.upsert(axiom_set)

    # Create run result: all 3 nodes processed
    run_result = ChapterRunResult(total=3, skipped=0, proposed=3, failed=0)

    # Build report
    report = build_report(chapter=22, node_registry=registry, run_result=run_result)

    # Verify aggregates
    assert report.chapter == 22
    assert report.total_nodes == 3
    assert report.nodes_with_notes == 3
    assert report.nodes_proposed == 3
    assert report.nodes_failed == 0
    assert report.nodes_skipped == 0
    assert abs(report.mean_coverage_score - 0.6333333333) < 0.001  # (0.9 + 0.3 + 0.7) / 3
    assert len(report.low_coverage_nodes) == 1
    assert report.low_coverage_nodes[0]["cn_code"] == "2204.2"
    assert report.low_coverage_nodes[0]["coverage_score"] == 0.3
    assert report.low_coverage_nodes[0]["explanation"] == "Partial coverage."


# ---------------------------------------------------------------------------
# Edge case: all nodes skipped (cache hits) → report reflects stored scores
# ---------------------------------------------------------------------------


def test_build_report_all_skipped(tmp_path: Path):
    """Test with all nodes skipped from cache → scores loaded from registry."""
    registry = NodeRegistry(tmp_path)

    # Store 3 proposed nodes with prior scores
    axiom_sets = [
        _make_axiom_set(cn_code="2204.1", coverage_score=0.8),
        _make_axiom_set(cn_code="2204.2", coverage_score=0.4, coverage_explanation="Low coverage."),
        _make_axiom_set(cn_code="2204.3", coverage_score=0.6),
    ]

    for axiom_set in axiom_sets:
        registry.upsert(axiom_set)

    # Run result: all 3 nodes skipped (cache hits)
    run_result = ChapterRunResult(total=3, skipped=3, proposed=0, failed=0)

    # Build report
    report = build_report(chapter=22, node_registry=registry, run_result=run_result)

    # Verify: still aggregates the stored scores
    assert report.total_nodes == 3
    assert report.nodes_with_notes == 0  # total - skipped = 3 - 3 = 0
    assert report.nodes_proposed == 0
    assert report.nodes_skipped == 3
    assert abs(report.mean_coverage_score - 0.6) < 0.001  # (0.8 + 0.4 + 0.6) / 3
    assert len(report.low_coverage_nodes) == 1
    assert report.low_coverage_nodes[0]["cn_code"] == "2204.2"


# ---------------------------------------------------------------------------
# Edge case: mix of proposed and failed nodes
# ---------------------------------------------------------------------------


def test_build_report_mix_proposed_failed(tmp_path: Path):
    """Test with mix of proposed and failed nodes → mean excludes failed."""
    registry = NodeRegistry(tmp_path)

    # 2 proposed, 1 failed
    axiom_sets = [
        _make_axiom_set(cn_code="2204.1", coverage_score=0.8, status="proposed"),
        _make_axiom_set(cn_code="2204.2", coverage_score=0.0, status="failed"),
        _make_axiom_set(cn_code="2204.3", coverage_score=0.6, status="proposed"),
    ]

    for axiom_set in axiom_sets:
        registry.upsert(axiom_set)

    run_result = ChapterRunResult(total=3, skipped=0, proposed=2, failed=1)

    # Build report
    report = build_report(chapter=22, node_registry=registry, run_result=run_result)

    # Mean should only include non-failed entries: (0.8 + 0.6) / 2 = 0.7
    assert report.nodes_failed == 1
    assert abs(report.mean_coverage_score - 0.7) < 0.001
    assert len(report.low_coverage_nodes) == 0  # Neither proposed has score < 0.5


# ---------------------------------------------------------------------------
# Edge case: empty registry → mean is 0.0
# ---------------------------------------------------------------------------


def test_build_report_empty_registry(tmp_path: Path):
    """Test with empty registry → mean is 0.0."""
    registry = NodeRegistry(tmp_path)

    run_result = ChapterRunResult(total=0, skipped=0, proposed=0, failed=0)

    report = build_report(chapter=22, node_registry=registry, run_result=run_result)

    assert report.total_nodes == 0
    assert report.mean_coverage_score == 0.0
    assert len(report.low_coverage_nodes) == 0


# ---------------------------------------------------------------------------
# Verification: write_report writes parseable JSON
# ---------------------------------------------------------------------------


def test_write_report_writes_valid_json(tmp_path: Path):
    """Test that write_report writes valid, parseable JSON."""
    registry = NodeRegistry(tmp_path / "registry")

    axiom_set = _make_axiom_set(cn_code="2204.1", coverage_score=0.5)
    registry.upsert(axiom_set)

    run_result = ChapterRunResult(total=1, skipped=0, proposed=1, failed=0)
    report = build_report(chapter=22, node_registry=registry, run_result=run_result)

    # Write to tmp_path / "report.json"
    out_path = tmp_path / "report.json"
    write_report(report, out_path)

    # Verify file exists
    assert out_path.exists()

    # Verify it's valid JSON and can be parsed
    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    assert parsed["chapter"] == 22
    assert parsed["total_nodes"] == 1
    assert parsed["nodes_proposed"] == 1


# ---------------------------------------------------------------------------
# Verification: write_report is atomic (uses tmp file)
# ---------------------------------------------------------------------------


def test_write_report_atomic_write(tmp_path: Path):
    """Test that write_report uses atomic tmp write."""
    registry = NodeRegistry(tmp_path / "registry")

    axiom_set = _make_axiom_set(cn_code="2204.1", coverage_score=0.8)
    registry.upsert(axiom_set)

    run_result = ChapterRunResult(total=1, skipped=0, proposed=1, failed=0)
    report = build_report(chapter=22, node_registry=registry, run_result=run_result)

    out_path = tmp_path / "report.json"
    write_report(report, out_path)

    # Verify final file exists and tmp does not
    assert out_path.exists()
    assert not out_path.with_suffix(".json.tmp").exists()


# ---------------------------------------------------------------------------
# Verification: write_report prints summary to stdout
# ---------------------------------------------------------------------------


def test_write_report_prints_summary(tmp_path: Path, capsys):
    """Test that write_report prints summary to stdout via print_summary."""
    registry = NodeRegistry(tmp_path / "registry")

    axiom_set = _make_axiom_set(cn_code="2204.1", coverage_score=0.8)
    registry.upsert(axiom_set)

    run_result = ChapterRunResult(total=1, skipped=0, proposed=1, failed=0)
    report = build_report(chapter=22, node_registry=registry, run_result=run_result)

    out_path = tmp_path / "report.json"
    write_report(report, out_path)

    # Capture stdout and verify summary was printed
    captured = capsys.readouterr()
    assert "[coverage] ch22:" in captured.out
    assert "1 nodes" in captured.out
    assert "mean 0.80" in captured.out


# ---------------------------------------------------------------------------
# Verification: ChapterCoverageReport has required fields
# ---------------------------------------------------------------------------


def test_chapter_coverage_report_schema(tmp_path: Path):
    """Test that ChapterCoverageReport has all required fields."""
    registry = NodeRegistry(tmp_path / "registry")

    axiom_set = _make_axiom_set(cn_code="2204.1", coverage_score=0.75)
    registry.upsert(axiom_set)

    run_result = ChapterRunResult(total=1, skipped=0, proposed=1, failed=0)
    report = build_report(chapter=22, node_registry=registry, run_result=run_result)

    # Verify all required fields are present
    assert hasattr(report, "chapter")
    assert hasattr(report, "total_nodes")
    assert hasattr(report, "nodes_with_notes")
    assert hasattr(report, "nodes_proposed")
    assert hasattr(report, "nodes_failed")
    assert hasattr(report, "nodes_skipped")
    assert hasattr(report, "mean_coverage_score")
    assert hasattr(report, "low_coverage_nodes")
    assert hasattr(report, "generated_at")

    # Verify types
    assert isinstance(report.chapter, int)
    assert isinstance(report.total_nodes, int)
    assert isinstance(report.nodes_with_notes, int)
    assert isinstance(report.nodes_proposed, int)
    assert isinstance(report.nodes_failed, int)
    assert isinstance(report.nodes_skipped, int)
    assert isinstance(report.mean_coverage_score, float)
    assert isinstance(report.low_coverage_nodes, list)
    assert isinstance(report.generated_at, str)
