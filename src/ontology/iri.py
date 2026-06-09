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


def measure_type_iri(code: str) -> URIRef:
    return mint_iri(f"mtype:{code}")


def geographic_area_iri(code: str) -> URIRef:
    return mint_iri(f"area:{code}")


def footnote_iri(code: str) -> URIRef:
    return mint_iri(f"footnote:{code}")


def certificate_iri(code: str) -> URIRef:
    return mint_iri(f"cert:{code}")


def regulation_iri(regulation_id: str) -> URIRef:
    return mint_iri(f"reg:{regulation_id}")


def duty_expression_iri(measure_sid: str) -> URIRef:
    return mint_iri(f"duty:{measure_sid}")


def measure_condition_iri(condition_sid: str) -> URIRef:
    return mint_iri(f"cond:{condition_sid}")


def additional_code_iri(code: str) -> URIRef:
    return mint_iri(f"addcode:{code}")
