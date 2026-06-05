from __future__ import annotations

import uuid

from rdflib import URIRef

from src.ontology.namespaces import EUCN, PIPELINE_NS_UUID


def mint_iri(key: str) -> URIRef:
    """Deterministic IRI via UUID5 keyed on key string."""
    uid = uuid.uuid5(PIPELINE_NS_UUID, key)
    return EUCN[f"ind/{uid}"]


def cn_code_iri(code: str) -> URIRef:
    return mint_iri(f"cn:{code}")


def taric_measure_iri(sid: str) -> URIRef:
    return mint_iri(f"measure:{sid}")


def classification_node_iri(path: list[str]) -> URIRef:
    # Serialize path as pipe-joined string; empty path = root
    return mint_iri(f"node:{'|'.join(path)}")


def chapter_iri(chapter: int) -> URIRef:
    return mint_iri(f"chapter:{chapter:02d}")


def heading_iri(heading: str) -> URIRef:
    return mint_iri(f"heading:{heading}")
