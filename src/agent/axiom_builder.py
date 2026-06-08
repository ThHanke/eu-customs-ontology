from __future__ import annotations

from rdflib import Graph, Literal
from rdflib.namespace import XSD

from src.ontology.namespaces import EUCN
from src.ontology.owl_helpers import (
    _decimal_range_restr,
    _equiv,
    _has_value_restr,
    _some_values_class_restr,
)
from src.schema.axiom_candidate import AxiomCandidate

KNOWN_PROPERTIES = frozenset({
    "alcoholByVolumePercent",
    "maxContainerVolumeL",
    "producedBy",
    "isCarbonated",
    "isDenatured",
    "pressureBar",
})

FACET_MAP = {
    "minExclusive": XSD.minExclusive,
    "maxInclusive": XSD.maxInclusive,
    "minInclusive": XSD.minInclusive,
    "maxExclusive": XSD.maxExclusive,
}

BOOLEAN_PROPS = frozenset({"isCarbonated", "isDenatured"})


def build_equivalence_axioms_from_candidates(
    g: Graph,
    candidates: list[AxiomCandidate],
) -> None:
    """Build OWL equivalence axioms from active AxiomCandidates. Idempotent."""
    active = [c for c in candidates if c.status != "stale"]
    if not active:
        return

    groups: dict[str, list[AxiomCandidate]] = {}
    for c in active:
        if c.property_iri.startswith("eucn:"):
            suffix = c.property_iri.split("eucn:", 1)[1]
            if suffix not in KNOWN_PROPERTIES:
                raise ValueError(f"Unknown property IRI: {c.property_iri}")
        groups.setdefault(c.owl_class, []).append(c)

    for owl_class in sorted(groups):
        group = groups[owl_class]
        phase1 = []
        for c in group:
            if c.restriction_type == "complement":
                raise ValueError("complement restriction_type not supported yet")
            prop_suffix = c.property_iri.split("eucn:", 1)[1]
            key = f"cand:{c.candidate_id[:12]}"
            if c.restriction_type == "someValuesFrom":
                phase1.append(_some_values_class_restr(g, EUCN[prop_suffix], EUCN[c.value], key))
            elif c.restriction_type == "hasValue":
                if prop_suffix in BOOLEAN_PROPS:
                    lit = Literal(c.value == "true", datatype=XSD.boolean)
                else:
                    lit = Literal(c.value, datatype=XSD.string)
                phase1.append(_has_value_restr(g, EUCN[prop_suffix], lit, key))
            elif c.restriction_type == "decimalRange":
                facet_iri = FACET_MAP[c.facet]
                phase1.append(_decimal_range_restr(g, EUCN[prop_suffix], facet_iri, float(c.value), key))
        if phase1:
            _equiv(g, EUCN[owl_class], phase1, f"cand:{owl_class[:8].lower()}")
