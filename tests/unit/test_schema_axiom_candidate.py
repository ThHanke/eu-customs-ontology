from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schema.axiom_candidate import AxiomCandidate


def test_candidate_id_deterministic():
    data = {
        "chapter": 22,
        "owl_class": "Beer",
        "restriction_type": "someValuesFrom",
        "property_iri": "eucn:producedBy",
        "value": "WineOrBeer",
        "facet": None,
        "source_note_id": "note_001",
        "source_text": "Beer is produced from barley",
        "source_text_hash": "abc123",
        "source_ingestion_date": "2026-06-08",
        "status": "proposed",
        "confidence": 0.95,
        "extractor": "rule-based",
        "extracted_at": "2026-06-08T10:00:00Z",
    }

    candidate1 = AxiomCandidate(**data)
    candidate2 = AxiomCandidate(**data)

    assert candidate1.candidate_id == candidate2.candidate_id


def test_candidate_id_different_value():
    data_base = {
        "chapter": 22,
        "owl_class": "Beer",
        "restriction_type": "someValuesFrom",
        "property_iri": "eucn:producedBy",
        "facet": None,
        "source_note_id": "note_001",
        "source_text": "Beer is produced from barley",
        "source_text_hash": "abc123",
        "source_ingestion_date": "2026-06-08",
        "status": "proposed",
        "confidence": 0.95,
        "extractor": "rule-based",
        "extracted_at": "2026-06-08T10:00:00Z",
    }

    data1 = {**data_base, "value": "WineOrBeer"}
    data2 = {**data_base, "value": "Whisky"}

    candidate1 = AxiomCandidate(**data1)
    candidate2 = AxiomCandidate(**data2)

    assert candidate1.candidate_id != candidate2.candidate_id


def test_restriction_type_rejects_unknown():
    data = {
        "chapter": 22,
        "owl_class": "Beer",
        "restriction_type": "fooBar",
        "property_iri": "eucn:producedBy",
        "value": "WineOrBeer",
        "facet": None,
        "source_note_id": "note_001",
        "source_text": "Beer is produced from barley",
        "source_text_hash": "abc123",
        "source_ingestion_date": "2026-06-08",
        "status": "proposed",
        "confidence": 0.95,
        "extractor": "rule-based",
        "extracted_at": "2026-06-08T10:00:00Z",
    }

    with pytest.raises(ValidationError):
        AxiomCandidate(**data)


def test_confidence_rejected_above_1():
    data = {
        "chapter": 22,
        "owl_class": "Beer",
        "restriction_type": "someValuesFrom",
        "property_iri": "eucn:producedBy",
        "value": "WineOrBeer",
        "facet": None,
        "source_note_id": "note_001",
        "source_text": "Beer is produced from barley",
        "source_text_hash": "abc123",
        "source_ingestion_date": "2026-06-08",
        "status": "proposed",
        "confidence": 1.5,
        "extractor": "rule-based",
        "extracted_at": "2026-06-08T10:00:00Z",
    }

    with pytest.raises(ValidationError):
        AxiomCandidate(**data)


def test_confidence_rejected_below_0():
    data = {
        "chapter": 22,
        "owl_class": "Beer",
        "restriction_type": "someValuesFrom",
        "property_iri": "eucn:producedBy",
        "value": "WineOrBeer",
        "facet": None,
        "source_note_id": "note_001",
        "source_text": "Beer is produced from barley",
        "source_text_hash": "abc123",
        "source_ingestion_date": "2026-06-08",
        "status": "proposed",
        "confidence": -0.1,
        "extractor": "rule-based",
        "extracted_at": "2026-06-08T10:00:00Z",
    }

    with pytest.raises(ValidationError):
        AxiomCandidate(**data)


def test_status_rejects_invalid():
    data = {
        "chapter": 22,
        "owl_class": "Beer",
        "restriction_type": "someValuesFrom",
        "property_iri": "eucn:producedBy",
        "value": "WineOrBeer",
        "facet": None,
        "source_note_id": "note_001",
        "source_text": "Beer is produced from barley",
        "source_text_hash": "abc123",
        "source_ingestion_date": "2026-06-08",
        "status": "invalid_status",
        "confidence": 0.95,
        "extractor": "rule-based",
        "extracted_at": "2026-06-08T10:00:00Z",
    }

    with pytest.raises(ValidationError):
        AxiomCandidate(**data)


def test_facet_none_uses_empty_string_in_id():
    data_with_none = {
        "chapter": 22,
        "owl_class": "Beer",
        "restriction_type": "decimalRange",
        "property_iri": "eucn:abv",
        "value": "5.5",
        "facet": None,
        "source_note_id": "note_001",
        "source_text": "ABV must be at least 5.5",
        "source_text_hash": "abc123",
        "source_ingestion_date": "2026-06-08",
        "status": "proposed",
        "confidence": 0.95,
        "extractor": "rule-based",
        "extracted_at": "2026-06-08T10:00:00Z",
    }

    data_with_empty = {
        "chapter": 22,
        "owl_class": "Beer",
        "restriction_type": "decimalRange",
        "property_iri": "eucn:abv",
        "value": "5.5",
        "facet": "",
        "source_note_id": "note_001",
        "source_text": "ABV must be at least 5.5",
        "source_text_hash": "abc123",
        "source_ingestion_date": "2026-06-08",
        "status": "proposed",
        "confidence": 0.95,
        "extractor": "rule-based",
        "extracted_at": "2026-06-08T10:00:00Z",
    }

    candidate_none = AxiomCandidate(**data_with_none)
    candidate_empty = AxiomCandidate(**data_with_empty)

    assert candidate_none.candidate_id == candidate_empty.candidate_id
