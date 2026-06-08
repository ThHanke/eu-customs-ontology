from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class NewClass(BaseModel):
    iri_local_name: str
    label_en: str
    label_de: str
    definition_en: str
    bfo_parent_iri: str
    class_type: Literal["material_entity", "process", "quality", "other"]


class NewProperty(BaseModel):
    iri_local_name: str
    label_en: str
    property_type: Literal["object", "data"]
    domain_iri: str
    range_iri: str
    is_functional: bool


class NodeRestriction(BaseModel):
    owl_class_iri: str
    restriction_type: Literal["someValuesFrom", "hasValue", "decimalRange", "complement"]
    property_iri: str
    value: str
    facet: str | None


class NodeAxiomSet(BaseModel):
    candidate_id: str = ""
    cn_code: str
    new_classes: list[NewClass]
    new_properties: list[NewProperty]
    restrictions: list[NodeRestriction]
    coverage_score: float
    coverage_explanation: str
    source_note_ids: list[str]
    source_text_hash: str
    tbox_hash: str
    status: Literal["proposed", "approved", "failed"] = "proposed"
    agent_model: str = ""
    generated_at: str = ""

    @model_validator(mode="before")
    @classmethod
    def _compute_candidate_id(cls, data: dict) -> dict:
        if isinstance(data, dict) and not data.get("candidate_id"):
            cn_code = data.get("cn_code") or ""
            source_text_hash = data.get("source_text_hash") or ""
            tbox_hash = data.get("tbox_hash") or ""
            if cn_code and source_text_hash and tbox_hash:
                content = f"{cn_code}{source_text_hash}{tbox_hash}"
                data["candidate_id"] = hashlib.sha256(content.encode()).hexdigest()
        return data

    @field_validator("coverage_score")
    @classmethod
    def _validate_coverage_score(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("coverage_score must be between 0.0 and 1.0")
        return v


# Anthropic tool definition for LLM-driven axiom proposal.
# The input_schema covers only LLM-provided fields (candidate_id, status,
# agent_model, generated_at are excluded — they are set by the pipeline).
PROPOSE_AXIOMS_TOOL_SCHEMA: dict = {
    "name": "propose_axioms",
    "description": (
        "Propose OWL axioms for a EU Customs Nomenclature (CN) node. "
        "Given the legal text for a CN code and the current TBox context, "
        "return structured OWL axioms that discriminate this node from its siblings. "
        "Follow BFO upper-ontology alignment: every new class must have a BFO or EUCN parent. "
        "Set coverage_score to reflect how well the proposed axioms cover all distinguishing "
        "criteria found in the legal text (1.0 = complete coverage)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "cn_code": {
                "type": "string",
                "description": "The CN commodity code this axiom set describes (e.g. '2204.21').",
            },
            "new_classes": {
                "type": "array",
                "description": "New OWL classes to introduce into the ontology.",
                "items": {
                    "type": "object",
                    "properties": {
                        "iri_local_name": {
                            "type": "string",
                            "description": "Local name for the new class IRI (will be placed under the EUCN namespace).",
                        },
                        "label_en": {"type": "string", "description": "English rdfs:label."},
                        "label_de": {"type": "string", "description": "German rdfs:label."},
                        "definition_en": {
                            "type": "string",
                            "description": "English IAO:0000115 definition.",
                        },
                        "bfo_parent_iri": {
                            "type": "string",
                            "description": (
                                "IRI of the BFO (http://purl.obolibrary.org/obo/) or EUCN "
                                "(https://w3id.org/eucn/) parent class."
                            ),
                        },
                        "class_type": {
                            "type": "string",
                            "enum": ["material_entity", "process", "quality", "other"],
                            "description": "BFO category for the new class.",
                        },
                    },
                    "required": [
                        "iri_local_name",
                        "label_en",
                        "label_de",
                        "definition_en",
                        "bfo_parent_iri",
                        "class_type",
                    ],
                },
            },
            "new_properties": {
                "type": "array",
                "description": "New OWL properties to introduce.",
                "items": {
                    "type": "object",
                    "properties": {
                        "iri_local_name": {
                            "type": "string",
                            "description": "Local name for the property IRI.",
                        },
                        "label_en": {"type": "string", "description": "English rdfs:label."},
                        "property_type": {
                            "type": "string",
                            "enum": ["object", "data"],
                            "description": "Whether this is an ObjectProperty or DatatypeProperty.",
                        },
                        "domain_iri": {"type": "string", "description": "IRI of the property domain."},
                        "range_iri": {"type": "string", "description": "IRI of the property range."},
                        "is_functional": {
                            "type": "boolean",
                            "description": "Whether to assert owl:FunctionalProperty.",
                        },
                    },
                    "required": [
                        "iri_local_name",
                        "label_en",
                        "property_type",
                        "domain_iri",
                        "range_iri",
                        "is_functional",
                    ],
                },
            },
            "restrictions": {
                "type": "array",
                "description": "OWL class restrictions (existential, hasValue, range, complement).",
                "items": {
                    "type": "object",
                    "properties": {
                        "owl_class_iri": {
                            "type": "string",
                            "description": "IRI of the class on which the restriction is placed.",
                        },
                        "restriction_type": {
                            "type": "string",
                            "enum": ["someValuesFrom", "hasValue", "decimalRange", "complement"],
                        },
                        "property_iri": {
                            "type": "string",
                            "description": "IRI of the property used in the restriction.",
                        },
                        "value": {
                            "type": "string",
                            "description": (
                                "Filler value: an IRI for someValuesFrom/hasValue/complement, "
                                "or a numeric literal for decimalRange."
                            ),
                        },
                        "facet": {
                            "type": ["string", "null"],
                            "description": (
                                "XSD facet IRI (e.g. xsd:minInclusive) for decimalRange; "
                                "null for other restriction types."
                            ),
                        },
                    },
                    "required": ["owl_class_iri", "restriction_type", "property_iri", "value", "facet"],
                },
            },
            "coverage_score": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": (
                    "Float in [0, 1] indicating how completely the proposed axioms capture "
                    "all distinguishing criteria from the legal text."
                ),
            },
            "coverage_explanation": {
                "type": "string",
                "description": "Human-readable explanation of coverage_score and any gaps.",
            },
            "source_note_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "IDs of the legal-text notes used as source for these axioms.",
            },
            "source_text_hash": {
                "type": "string",
                "description": "SHA-256 hex digest of the concatenated source note texts.",
            },
            "tbox_hash": {
                "type": "string",
                "description": "SHA-256 hex digest of the TBox serialisation used as context.",
            },
        },
        "required": [
            "cn_code",
            "new_classes",
            "new_properties",
            "restrictions",
            "coverage_score",
            "coverage_explanation",
            "source_note_ids",
            "source_text_hash",
            "tbox_hash",
        ],
    },
}
