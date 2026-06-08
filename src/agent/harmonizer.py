from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel
from rdflib import Graph, URIRef
from rdflib.namespace import OWL

from src.reasoning.konclude import KoncludeConsistencyError, check_consistency

logger = logging.getLogger(__name__)

PROPOSE_HARMONIZATION_TOOL = {
    "name": "propose_harmonization",
    "description": "Identify semantic duplicate IRIs and propose equivalentClass/equivalentProperty links",
    "input_schema": {
        "type": "object",
        "properties": {
            "corrections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "primary_iri": {"type": "string"},
                        "duplicate_iri": {"type": "string"},
                        "equivalence_type": {"type": "string", "enum": ["class", "property"]},
                        "rationale": {"type": "string"},
                    },
                    "required": ["primary_iri", "duplicate_iri", "equivalence_type", "rationale"],
                },
            }
        },
        "required": ["corrections"],
    },
}


class HarmonizationCorrection(BaseModel):
    primary_iri: str
    duplicate_iri: str
    equivalence_type: Literal["class", "property"]
    rationale: str


def _build_harmonization_prompt(chapter: int, new_iris: list[dict]) -> str:
    lines: list[str] = [
        f"Chapter {chapter} ontology harmonization.",
        "",
        "The following IRIs were coined during this chapter run. "
        "Identify any pairs that are semantically equivalent (same concept, different names). "
        "Propose owl:equivalentClass or owl:equivalentProperty links where appropriate.",
        "",
        "New IRIs:",
    ]
    for entry in new_iris:
        iri = entry.get("iri", "")
        label = entry.get("label", "")
        definition = entry.get("definition", "")
        kind = entry.get("class_or_property", "class")
        lines.append(f"  [{kind}] {iri}")
        if label:
            lines.append(f"    label: {label}")
        if definition:
            lines.append(f"    definition: {definition}")
    lines.append("")
    lines.append(
        "Call propose_harmonization with the list of corrections. "
        "If there are no duplicates, return an empty corrections list."
    )
    return "\n".join(lines)


def _build_scratch_graph(base_tbox_path: Path, corrections: list[dict]) -> Graph:
    """Parse base TBox and add equivalence triples for proposed corrections."""
    g = Graph()
    g.parse(str(base_tbox_path), format="turtle")
    for corr in corrections:
        p = URIRef(corr["primary_iri"])
        d = URIRef(corr["duplicate_iri"])
        if corr["equivalence_type"] == "class":
            g.add((p, OWL.equivalentClass, d))
            g.add((d, OWL.equivalentClass, p))
        else:
            g.add((p, OWL.equivalentProperty, d))
            g.add((d, OWL.equivalentProperty, p))
    return g


def harmonize(
    chapter: int,
    new_iris: list[dict],
    base_tbox_path: Path,
    model: str,
    *,
    out_path: Path | None = None,
) -> list[HarmonizationCorrection]:
    """Detect semantic duplicates among new_iris and produce equivalence links.

    Args:
        chapter: Chapter number (for prompt context and output path).
        new_iris: List of {iri, label, definition, class_or_property} dicts.
        base_tbox_path: Path to the assembled chapter TBox (Turtle).
        model: Anthropic model name.
        out_path: If given, write corrections as JSONL to this path.

    Returns:
        List of HarmonizationCorrection instances (empty if none found or on error).
    """
    if not new_iris:
        logger.debug("harmonize: no new IRIs for chapter %d, skipping LLM call", chapter)
        return []

    client = anthropic.Anthropic()
    user_message = _build_harmonization_prompt(chapter, new_iris)

    logger.debug("harmonize: calling LLM for chapter %d with %d IRIs", chapter, len(new_iris))
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": user_message}],
        tools=[PROPOSE_HARMONIZATION_TOOL],
        tool_choice={"type": "any"},
    )

    # Extract tool use block
    proposed_corrections: list[dict] = []
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "propose_harmonization":
            proposed_corrections = block.input.get("corrections", [])
            break
    else:
        logger.warning(
            "harmonize: no propose_harmonization tool call in LLM response for chapter %d", chapter
        )
        return []

    if not proposed_corrections:
        logger.info("harmonize: LLM proposed no equivalences for chapter %d", chapter)
        # Still run consistency check on the base TBox to confirm it is consistent
        scratch_path: Path | None = None
        try:
            g = _build_scratch_graph(base_tbox_path, [])
            with tempfile.NamedTemporaryFile(suffix=".ttl", delete=False, mode="w") as f:
                scratch_path = Path(f.name)
            g.serialize(destination=str(scratch_path), format="turtle")
            check_consistency(scratch_path)
        except (KoncludeConsistencyError, Exception) as exc:
            logger.warning(
                "harmonize: Konclude consistency check failed for chapter %d (no corrections): %s",
                chapter, exc,
            )
        finally:
            if scratch_path is not None:
                scratch_path.unlink(missing_ok=True)
        return []

    # Build and validate scratch graph with proposed corrections
    scratch_path = None
    try:
        g = _build_scratch_graph(base_tbox_path, proposed_corrections)
        with tempfile.NamedTemporaryFile(suffix=".ttl", delete=False, mode="w") as f:
            scratch_path = Path(f.name)
        g.serialize(destination=str(scratch_path), format="turtle")
        check_consistency(scratch_path)
    except (KoncludeConsistencyError, Exception) as exc:
        logger.warning(
            "harmonize: Konclude consistency check failed for chapter %d corrections — skipping: %s",
            chapter, exc,
        )
        return []
    finally:
        if scratch_path is not None:
            scratch_path.unlink(missing_ok=True)

    # Build typed correction objects
    corrections: list[HarmonizationCorrection] = []
    for corr in proposed_corrections:
        try:
            corrections.append(HarmonizationCorrection(**corr))
        except Exception as exc:
            logger.warning("harmonize: invalid correction entry skipped: %s — %s", corr, exc)

    if corrections and out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            for corr in corrections:
                fh.write(corr.model_dump_json() + "\n")
        logger.info("harmonize: wrote %d corrections to %s", len(corrections), out_path)

    return corrections
