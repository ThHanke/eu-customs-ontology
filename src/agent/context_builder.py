from __future__ import annotations

import hashlib
import logging
import re
from datetime import date

from rdflib import Graph

from src.ontology.tbox import build_tbox
from src.schema.legal_text import LegalSection
from src.schema.wizard import ClassificationNode

logger = logging.getLogger(__name__)

_TRIPLE_CAP = 500


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
    build_tbox(g, chapter=chapter, **kwargs)
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
    wizard_nodes: dict[str, list[ClassificationNode]],
    running_tbox_ttl: str,
) -> dict:
    """Return structured per-node context for the LLM prompt.

    Parameters
    ----------
    cn_code:
        The CN code for which the context is assembled.
    legal_sections:
        Legal text sections relevant to this node (filtered by caller).
    wizard_nodes:
        Mapping of cn_code -> list[ClassificationNode].  Used to look up
        ancestor nodes and collect question_text for the hierarchy path.
    running_tbox_ttl:
        Current TBox Turtle string (grows as the agent emits new axioms).
    """
    hierarchy_path = _compute_hierarchy_path(cn_code, wizard_nodes)

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
    wizard_nodes: dict[str, list[ClassificationNode]],
) -> list[dict]:
    """Return ordered list of ancestor dicts from shortest prefix to longest."""
    ancestors = []
    for candidate_code, nodes in wizard_nodes.items():
        if candidate_code != cn_code and cn_code.startswith(candidate_code):
            question_texts = [n.question_text for n in nodes] if nodes else []
            ancestors.append(
                {
                    "cn_code": candidate_code,
                    "question_texts": question_texts,
                }
            )
    ancestors.sort(key=lambda x: len(x["cn_code"]))
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
