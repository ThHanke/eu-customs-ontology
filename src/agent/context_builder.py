from __future__ import annotations

import hashlib
import logging
import re
from datetime import date
from pathlib import Path

from rdflib import Graph

from src.ontology.tbox import build_tbox
from src.schema.legal_text import LegalSection
from src.schema.wizard import ClassificationNode

logger = logging.getLogger(__name__)

_TRIPLE_CAP = 600

_DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"


def _load_heading_labels(chapter: int) -> dict:
    cache = _DATA_ROOT / "intermediate" / f"tariffnumber_ch{chapter:02d}.json"
    if not cache.exists():
        return {}
    from src.ontology.heading_classes import load_heading_labels
    return load_heading_labels(cache)


def build_static_context(chapter: int, extract_date: date | None = None) -> str:
    """Serialize BFO stubs + core TBox + chapter TBox into compact Turtle.

    Parameters
    ----------
    chapter:
        Chapter number to build the TBox for.
    extract_date:
        Date to pass to build_tbox for versionIRI/versionInfo embedding.
        When *None* build_tbox uses today's date.  Pass a fixed epoch date
        (e.g. ``date(2000, 1, 1)``) to obtain a stable, date-independent
        serialisation suitable for hashing.

    Logs a warning if the serialized graph exceeds _TRIPLE_CAP triples.
    """
    g = Graph()
    kwargs = {} if extract_date is None else {"extract_date": extract_date}
    heading_labels = _load_heading_labels(chapter)
    build_tbox(g, chapter=chapter, heading_labels=heading_labels or None, **kwargs)
    triple_count = len(g)
    if triple_count > _TRIPLE_CAP:
        logger.warning(
            "Static context for chapter %d has %d triples (cap %d)",
            chapter,
            triple_count,
            _TRIPLE_CAP,
        )
    else:
        logger.debug("Static context for chapter %d: %d triples", chapter, triple_count)
    return g.serialize(format="turtle")


def build_node_context(
    cn_code: str,
    legal_sections: list[LegalSection],
    running_tbox_ttl: str,
    all_wizard_nodes: dict[str, ClassificationNode] | None = None,
) -> dict:
    """Return structured per-node context for the LLM prompt.

    Parameters
    ----------
    cn_code:
        The CN code for which the context is assembled.
    legal_sections:
        Legal text sections relevant to this node (filtered by caller).
    running_tbox_ttl:
        Current TBox Turtle string (grows as the agent emits new axioms).
    all_wizard_nodes:
        Flat mapping of node_id (8-digit zero-padded) -> ClassificationNode
        covering all nodes in the wizard tree (including intermediate nodes).
        Used by _compute_hierarchy_path to resolve the ancestor chain.
    """
    hierarchy_path = _compute_hierarchy_path(cn_code, all_wizard_nodes or {})

    notes_en = [
        s.source_text
        for s in legal_sections
        if s.language == "en" and s.cn_code == cn_code
    ]
    notes_de = [
        s.source_text
        for s in legal_sections
        if s.language == "de" and s.cn_code == cn_code
    ]

    existing_axioms = _collect_existing_axioms(cn_code, running_tbox_ttl)

    return {
        "hierarchy_path": hierarchy_path,
        "notes_en": notes_en,
        "notes_de": notes_de,
        "running_tbox": running_tbox_ttl,
        "existing_axioms": existing_axioms,
    }


def compute_tbox_hash(chapter: int) -> str:
    """Return SHA-256 hex digest over the serialized TBox for *chapter*.

    Uses a fixed epoch date so the hash is stable across days.
    """
    ttl = build_static_context(chapter, extract_date=date(2000, 1, 1))
    return hashlib.sha256(ttl.encode()).hexdigest()


def _compute_hierarchy_path(
    cn_code: str,
    all_wizard_nodes: dict[str, ClassificationNode],
) -> list[dict]:
    """Return ordered ancestor dicts from chapter root down to direct parent.

    Parameters
    ----------
    cn_code:
        The CN code to resolve ancestors for.  Padded to 8 digits with
        trailing zeros before lookup (e.g. ``"2205"`` → ``"22050000"``).
    all_wizard_nodes:
        Flat mapping of node_id (8-digit zero-padded) -> ClassificationNode
        covering all nodes in the wizard tree.
    """
    if not all_wizard_nodes:
        return []
    node_id = cn_code.ljust(8, "0")
    node = all_wizard_nodes.get(node_id)
    if node is None:
        return []
    ancestors = []
    for ancestor_id in node.path_from_root:
        ancestor = all_wizard_nodes.get(ancestor_id)
        if ancestor is None:
            continue
        ancestors.append(
            {
                "cn_code": ancestor_id,
                "question_texts": [ancestor.question_text] if ancestor.question_text else [],
            }
        )
    return ancestors


def _collect_existing_axioms(cn_code: str, running_tbox_ttl: str) -> list[str]:
    """Extract lines from the running TBox that mention the cn_code fragment.

    For numeric cn_codes a digit-boundary regex is used so that e.g. "22"
    does not match "2204", "2022", or "Regulation22".
    """
    if not running_tbox_ttl:
        return []
    if cn_code.isdigit():
        pattern = re.compile(r'(?<!\d)' + re.escape(cn_code) + r'(?!\d)', re.IGNORECASE)
        return [line for line in running_tbox_ttl.splitlines() if pattern.search(line)]
    fragment = cn_code.lower()
    return [line for line in running_tbox_ttl.splitlines() if fragment in line.lower()]
