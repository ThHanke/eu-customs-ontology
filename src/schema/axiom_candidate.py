from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class AxiomCandidate(BaseModel):
    candidate_id: str
    chapter: int
    owl_class: str
    restriction_type: Literal["someValuesFrom", "hasValue", "decimalRange", "complement"]
    property_iri: str
    value: str
    facet: str | None
    source_note_id: str
    source_text: str
    source_text_hash: str
    source_ingestion_date: str
    status: Literal["proposed", "approved", "stale"]
    confidence: float
    extractor: str
    extracted_at: str

    @model_validator(mode="before")
    @classmethod
    def _compute_candidate_id(cls, data: dict) -> dict:
        if isinstance(data, dict) and "candidate_id" not in data:
            chapter = data.get("chapter")
            owl_class = data.get("owl_class")
            restriction_type = data.get("restriction_type")
            property_iri = data.get("property_iri")
            value = data.get("value")
            facet = data.get("facet") or ""

            if all(x is not None for x in [chapter, owl_class, restriction_type, property_iri, value]):
                content = f"{chapter}:{owl_class}:{restriction_type}:{property_iri}:{value}:{facet}"
                data["candidate_id"] = hashlib.sha256(content.encode()).hexdigest()
        return data

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v
