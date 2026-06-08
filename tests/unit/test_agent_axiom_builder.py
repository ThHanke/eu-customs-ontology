from __future__ import annotations

import pytest
from rdflib import Graph
from rdflib.namespace import OWL

from src.agent.axiom_builder import build_equivalence_axioms_from_candidates
from src.schema.axiom_candidate import AxiomCandidate


def _svf_cand(owl_class="Beer", value="MaltFermentation"):
    return AxiomCandidate(
        chapter=22,
        owl_class=owl_class,
        restriction_type="someValuesFrom",
        property_iri="eucn:producedBy",
        value=value,
        facet=None,
        source_note_id="n1",
        source_text="from malted barley",
        source_text_hash="abc123",
        source_ingestion_date="2023-10-06",
        status="proposed",
        confidence=0.90,
        extractor="rule-based",
        extracted_at="2026-06-08",
    )


def _dr_cand(owl_class="Beer", facet="minExclusive", value="0.5"):
    return AxiomCandidate(
        chapter=22,
        owl_class=owl_class,
        restriction_type="decimalRange",
        property_iri="eucn:alcoholByVolumePercent",
        value=value,
        facet=facet,
        source_note_id="n2",
        source_text="ABV exceeding 0.5%",
        source_text_hash="def456",
        source_ingestion_date="2023-10-06",
        status="approved",
        confidence=0.95,
        extractor="rule-based",
        extracted_at="2026-06-08",
    )


def test_decimal_range_candidate_produces_some_values_from():
    g = Graph()
    build_equivalence_axioms_from_candidates(g, [_dr_cand()])
    triples = list(g.triples((None, OWL.someValuesFrom, None)))
    assert len(triples) > 0


def test_some_values_from_candidate_produces_some_values_from():
    g = Graph()
    build_equivalence_axioms_from_candidates(g, [_svf_cand()])
    triples = list(g.triples((None, OWL.someValuesFrom, None)))
    assert len(triples) > 0


def test_idempotent_double_call():
    g = Graph()
    build_equivalence_axioms_from_candidates(g, [_svf_cand()])
    count_after_first = len(g)
    build_equivalence_axioms_from_candidates(g, [_svf_cand()])
    assert len(g) == count_after_first


def test_complement_candidate_raises():
    c = AxiomCandidate(
        chapter=22,
        owl_class="Beer",
        restriction_type="complement",
        property_iri="eucn:producedBy",
        value="SomeFermentation",
        facet=None,
        source_note_id="n3",
        source_text="not from grain",
        source_text_hash="ghi789",
        source_ingestion_date="2023-10-06",
        status="proposed",
        confidence=0.80,
        extractor="rule-based",
        extracted_at="2026-06-08",
    )
    g = Graph()
    with pytest.raises(ValueError, match="complement"):
        build_equivalence_axioms_from_candidates(g, [c])


def test_empty_list_produces_no_triples():
    g = Graph()
    build_equivalence_axioms_from_candidates(g, [])
    assert len(g) == 0


def test_stale_candidates_excluded():
    stale = AxiomCandidate(
        chapter=22,
        owl_class="Beer",
        restriction_type="someValuesFrom",
        property_iri="eucn:producedBy",
        value="MaltFermentation",
        facet=None,
        source_note_id="n1",
        source_text="from malted barley",
        source_text_hash="abc123",
        source_ingestion_date="2023-10-06",
        status="stale",
        confidence=0.90,
        extractor="rule-based",
        extracted_at="2026-06-08",
    )
    g = Graph()
    build_equivalence_axioms_from_candidates(g, [stale])
    assert len(g) == 0
