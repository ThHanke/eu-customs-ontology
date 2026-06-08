from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schema.node_axiom_set import (
    NewClass,
    NewProperty,
    NodeAxiomSet,
    NodeRestriction,
    PROPOSE_AXIOMS_TOOL_SCHEMA,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BFO_MATERIAL = "http://purl.obolibrary.org/obo/BFO_0000040"
EUCN_NS = "https://w3id.org/eucn/"

_VALID_CLASS = dict(
    iri_local_name="FermentedGrapeProduct",
    label_en="Fermented Grape Product",
    label_de="Fermentiertes Traubenprodukt",
    definition_en="A material entity produced by fermentation of grape juice.",
    bfo_parent_iri=BFO_MATERIAL,
    class_type="material_entity",
)

_VALID_PROPERTY = dict(
    iri_local_name="hasAlcoholicStrength",
    label_en="has alcoholic strength",
    property_type="data",
    domain_iri=f"{EUCN_NS}FermentedGrapeProduct",
    range_iri="http://www.w3.org/2001/XMLSchema#decimal",
    is_functional=True,
)

_VALID_RESTRICTION = dict(
    owl_class_iri=f"{EUCN_NS}FermentedGrapeProduct",
    restriction_type="decimalRange",
    property_iri=f"{EUCN_NS}hasAlcoholicStrength",
    value="15.0",
    facet="http://www.w3.org/2001/XMLSchema#maxInclusive",
)


def _make_valid_axiom_set(**overrides) -> dict:
    base = dict(
        cn_code="2204.21",
        new_classes=[_VALID_CLASS],
        new_properties=[_VALID_PROPERTY],
        restrictions=[_VALID_RESTRICTION],
        coverage_score=0.9,
        coverage_explanation="Covers alcohol content and product type.",
        source_note_ids=["note_001", "note_002"],
        source_text_hash="deadbeef" * 8,
        tbox_hash="cafebabe" * 8,
        status="proposed",
        agent_model="claude-opus-4",
        generated_at="2026-06-08T12:00:00Z",
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Happy path: round-trip JSON serialisation
# ---------------------------------------------------------------------------


def test_round_trip_json():
    data = _make_valid_axiom_set()
    instance = NodeAxiomSet(**data)
    json_str = instance.model_dump_json()
    restored = NodeAxiomSet.model_validate_json(json_str)
    assert restored == instance


def test_round_trip_preserves_candidate_id():
    data = _make_valid_axiom_set()
    instance = NodeAxiomSet(**data)
    restored = NodeAxiomSet.model_validate_json(instance.model_dump_json())
    assert restored.candidate_id == instance.candidate_id


# ---------------------------------------------------------------------------
# candidate_id determinism
# ---------------------------------------------------------------------------


def test_candidate_id_deterministic():
    data = _make_valid_axiom_set()
    a = NodeAxiomSet(**data)
    b = NodeAxiomSet(**data)
    assert a.candidate_id == b.candidate_id
    assert len(a.candidate_id) == 64  # SHA-256 hex digest


def test_candidate_id_differs_for_different_inputs():
    a = NodeAxiomSet(**_make_valid_axiom_set(cn_code="2204.21"))
    b = NodeAxiomSet(**_make_valid_axiom_set(cn_code="2204.29"))
    assert a.candidate_id != b.candidate_id


def test_candidate_id_sha256_of_concatenation():
    import hashlib

    data = _make_valid_axiom_set()
    instance = NodeAxiomSet(**data)
    expected = hashlib.sha256(
        (data["cn_code"] + data["source_text_hash"] + data["tbox_hash"]).encode()
    ).hexdigest()
    assert instance.candidate_id == expected


# ---------------------------------------------------------------------------
# coverage_score validation
# ---------------------------------------------------------------------------


def test_coverage_score_above_1_raises():
    with pytest.raises(ValidationError):
        NodeAxiomSet(**_make_valid_axiom_set(coverage_score=1.1))


def test_coverage_score_below_0_raises():
    with pytest.raises(ValidationError):
        NodeAxiomSet(**_make_valid_axiom_set(coverage_score=-0.01))


def test_coverage_score_boundary_0_is_valid():
    n = NodeAxiomSet(**_make_valid_axiom_set(coverage_score=0.0))
    assert n.coverage_score == 0.0


def test_coverage_score_boundary_1_is_valid():
    n = NodeAxiomSet(**_make_valid_axiom_set(coverage_score=1.0))
    assert n.coverage_score == 1.0


# ---------------------------------------------------------------------------
# Empty collections are valid
# ---------------------------------------------------------------------------


def test_empty_new_classes_and_restrictions_valid():
    data = _make_valid_axiom_set(
        new_classes=[],
        restrictions=[],
        coverage_score=0.0,
        coverage_explanation="No axioms found.",
    )
    n = NodeAxiomSet(**data)
    assert n.new_classes == []
    assert n.restrictions == []


def test_empty_new_properties_valid():
    data = _make_valid_axiom_set(new_properties=[])
    n = NodeAxiomSet(**data)
    assert n.new_properties == []


# ---------------------------------------------------------------------------
# Literal field validation
# ---------------------------------------------------------------------------


def test_invalid_class_type_raises():
    bad_class = {**_VALID_CLASS, "class_type": "artifact"}
    with pytest.raises(ValidationError):
        NodeAxiomSet(**_make_valid_axiom_set(new_classes=[bad_class]))


def test_invalid_restriction_type_raises():
    bad_restriction = {**_VALID_RESTRICTION, "restriction_type": "allValuesFrom"}
    with pytest.raises(ValidationError):
        NodeAxiomSet(**_make_valid_axiom_set(restrictions=[bad_restriction]))


def test_invalid_property_type_raises():
    bad_prop = {**_VALID_PROPERTY, "property_type": "annotation"}
    with pytest.raises(ValidationError):
        NodeAxiomSet(**_make_valid_axiom_set(new_properties=[bad_prop]))


def test_invalid_status_raises():
    with pytest.raises(ValidationError):
        NodeAxiomSet(**_make_valid_axiom_set(status="rejected"))


# ---------------------------------------------------------------------------
# facet can be None
# ---------------------------------------------------------------------------


def test_restriction_facet_none_is_valid():
    restriction = {**_VALID_RESTRICTION, "restriction_type": "someValuesFrom", "facet": None}
    n = NodeAxiomSet(**_make_valid_axiom_set(restrictions=[restriction]))
    assert n.restrictions[0].facet is None


# ---------------------------------------------------------------------------
# PROPOSE_AXIOMS_TOOL_SCHEMA structure
# ---------------------------------------------------------------------------


def test_tool_schema_has_required_keys():
    assert "name" in PROPOSE_AXIOMS_TOOL_SCHEMA
    assert "description" in PROPOSE_AXIOMS_TOOL_SCHEMA
    assert "input_schema" in PROPOSE_AXIOMS_TOOL_SCHEMA


def test_tool_schema_name():
    assert PROPOSE_AXIOMS_TOOL_SCHEMA["name"] == "propose_axioms"


def test_tool_schema_input_schema_required_fields():
    required = set(PROPOSE_AXIOMS_TOOL_SCHEMA["input_schema"]["required"])
    expected = {
        "cn_code",
        "new_classes",
        "new_properties",
        "restrictions",
        "coverage_score",
        "coverage_explanation",
        "source_note_ids",
        "source_text_hash",
        "tbox_hash",
    }
    assert required == expected


def test_tool_schema_excludes_pipeline_fields():
    """candidate_id, status, agent_model, generated_at must NOT appear in required."""
    required = set(PROPOSE_AXIOMS_TOOL_SCHEMA["input_schema"]["required"])
    for field in ("candidate_id", "status", "agent_model", "generated_at"):
        assert field not in required, f"Pipeline field '{field}' should not be in LLM required list"


def test_tool_schema_coverage_score_has_bounds():
    props = PROPOSE_AXIOMS_TOOL_SCHEMA["input_schema"]["properties"]
    assert props["coverage_score"]["minimum"] == 0.0
    assert props["coverage_score"]["maximum"] == 1.0


def test_tool_schema_is_plain_dict():
    """Schema must be a plain dict so it can be passed directly to the Anthropic SDK."""
    assert isinstance(PROPOSE_AXIOMS_TOOL_SCHEMA, dict)
    assert isinstance(PROPOSE_AXIOMS_TOOL_SCHEMA["input_schema"], dict)
