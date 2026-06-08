from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path

from pydantic import BaseModel

from src.agent.chapter_runner import ChapterRunResult
from src.agent.node_registry import NodeRegistry

logger = logging.getLogger(__name__)


class ChapterCoverageReport(BaseModel):
    """Per-chapter coverage report aggregating node metrics."""

    chapter: int
    total_nodes: int
    nodes_with_notes: int
    nodes_proposed: int
    nodes_failed: int
    nodes_skipped: int
    mean_coverage_score: float
    low_coverage_nodes: list[dict]  # list of {"cn_code": str, "coverage_score": float, "explanation": str}
    generated_at: str


def build_report(
    chapter: int,
    node_registry: NodeRegistry,
    run_result: ChapterRunResult,
) -> ChapterCoverageReport:
    """Aggregate per-node coverage metrics into a chapter report.

    Args:
        chapter: Chapter number (e.g. 22).
        node_registry: Registry holding all axiom sets for the chapter.
        run_result: Result from chapter run (total, skipped, proposed, failed).

    Returns:
        ChapterCoverageReport with aggregated metrics.
    """
    # Collect all non-failed axiom sets
    coverage_scores: list[float] = []
    low_coverage_nodes: list[dict] = []

    for axiom_set in node_registry.iter_all():
        # Only include non-failed entries in mean
        if axiom_set.status != "failed":
            coverage_scores.append(axiom_set.coverage_score)

        # Collect low-coverage nodes (score < 0.5) from proposed sets
        if axiom_set.status == "proposed" and axiom_set.coverage_score < 0.5:
            low_coverage_nodes.append(
                {
                    "cn_code": axiom_set.cn_code,
                    "coverage_score": axiom_set.coverage_score,
                    "explanation": axiom_set.coverage_explanation,
                }
            )

    # Compute mean coverage score (0.0 if no scores available)
    mean_coverage_score = (
        sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0
    )

    # nodes_with_notes = total - skipped (nodes that were processed)
    nodes_with_notes = run_result.total - run_result.skipped

    return ChapterCoverageReport(
        chapter=chapter,
        total_nodes=run_result.total,
        nodes_with_notes=nodes_with_notes,
        nodes_proposed=run_result.proposed,
        nodes_failed=run_result.failed,
        nodes_skipped=run_result.skipped,
        mean_coverage_score=mean_coverage_score,
        low_coverage_nodes=low_coverage_nodes,
        generated_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )


def write_report(report: ChapterCoverageReport, out_path: Path) -> None:
    """Write report to disk atomically.

    Args:
        report: The report to write.
        out_path: Output path (will be written atomically via tmp file).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    os.rename(tmp, out_path)


def print_summary(report: ChapterCoverageReport) -> None:
    """Print human-readable summary to stdout.

    Args:
        report: The report to summarize.
    """
    low_count = len(report.low_coverage_nodes)
    print(
        f"[coverage] ch{report.chapter:02d}: {report.total_nodes} nodes, "
        f"mean {report.mean_coverage_score:.2f}, "
        f"{low_count} low-coverage (<0.5)"
    )
