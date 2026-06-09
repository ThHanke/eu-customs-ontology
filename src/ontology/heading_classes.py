from __future__ import annotations

import json
import re
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from src.ontology.namespaces import BFO_OBJECT, EUCN

_STOP = frozenset(
    "a an the in of from to for by or and with not than excl excluding other "
    "made containing holding less greater equal than vol l".split()
)
_NON_ALNUM = re.compile(r"[^a-zA-Z0-9 ]+")


def _to_local_name(label_en: str, code: str, max_words: int = 6) -> str:
    """Convert an EN label to a CamelCase IRI local name, suffixed with the CN code."""
    clean = _NON_ALNUM.sub(" ", label_en)
    words = [
        w.capitalize()
        for w in clean.split()
        if w.lower() not in _STOP and len(w) > 1
    ]
    return "".join(words[:max_words]) + code


def add_heading_classes(
    g: Graph,
    chapter: int,
    labels: dict[str, dict[str, str]],
    uncovered_cn_codes: set[str] | None = None,
    chapter_root_iri: URIRef | None = None,
) -> None:
    """Add heading-level and uncovered-terminal OWL classes to *g*.

    Parameters
    ----------
    g:
        Target graph; modified in place.
    chapter:
        Chapter number (used to derive the chapter-root parent IRI).
    labels:
        Mapping ``{cn_code: {"en": "...", "de": "..."}}`` from tariffnumber API.
    uncovered_cn_codes:
        8-digit terminal codes that have no CLASS API legal text.  When provided,
        these also get a simple named OWL class (subClassOf their 4d heading class).
    """
    heading_iris: dict[str, URIRef] = {}

    # 4-digit heading classes — structural parents
    for code, lang_labels in sorted(labels.items()):
        if len(code) != 4:
            continue
        label_en = lang_labels.get("en", "")
        label_de = lang_labels.get("de", "")
        if not label_en:
            continue
        local_name = _to_local_name(label_en, code)
        iri = EUCN[local_name]
        heading_iris[code] = iri
        g.add((iri, RDF.type, OWL.Class))
        g.add((iri, RDFS.subClassOf, chapter_root_iri or BFO_OBJECT))
        g.add((iri, RDFS.label, Literal(label_en, lang="en")))
        if label_de:
            g.add((iri, RDFS.label, Literal(label_de, lang="de")))
        g.add((iri, SKOS.definition, Literal(label_en, lang="en")))
        if label_de:
            g.add((iri, SKOS.definition, Literal(label_de, lang="de")))

    if not uncovered_cn_codes:
        return

    # 8-digit terminal classes without CLASS API coverage
    for code in sorted(uncovered_cn_codes):
        if len(code) != 8:
            continue
        lang_labels = labels.get(code, {})
        label_en = lang_labels.get("en", "")
        label_de = lang_labels.get("de", "")
        if not label_en:
            continue
        local_name = _to_local_name(label_en, code)
        iri = EUCN[local_name]
        g.add((iri, RDF.type, OWL.Class))
        parent = heading_iris.get(code[:4], BFO_OBJECT)
        g.add((iri, RDFS.subClassOf, parent))
        g.add((iri, RDFS.label, Literal(label_en, lang="en")))
        if label_de:
            g.add((iri, RDFS.label, Literal(label_de, lang="de")))
        g.add((iri, SKOS.definition, Literal(label_en, lang="en")))
        if label_de:
            g.add((iri, SKOS.definition, Literal(label_de, lang="de")))


def load_heading_labels(cache_path: Path) -> dict[str, dict[str, str]]:
    """Load heading labels from JSON cache, returning {} if missing."""
    if not cache_path.exists():
        return {}
    return json.loads(cache_path.read_text(encoding="utf-8"))
