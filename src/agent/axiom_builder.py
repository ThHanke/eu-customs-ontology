from __future__ import annotations

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from src.ontology.namespaces import EUCN
from src.ontology.owl_helpers import (
    _decimal_range_restr,
    _equiv,
    _has_value_restr,
    _some_values_class_restr,
)
from src.schema.axiom_candidate import AxiomCandidate
from src.schema.node_axiom_set import NodeAxiomSet, NodeRestriction

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


_EUCN_NS = "https://w3id.org/eucn/"
_IAO_DEFINITION = URIRef("http://purl.obolibrary.org/obo/IAO_0000115")


def _iri(s: str) -> URIRef:
    if s.startswith("http://") or s.startswith("https://"):
        return URIRef(s)
    return URIRef(f"{_EUCN_NS}{s}")


def _restr_bnode(g: Graph, restr: NodeRestriction, key: str) -> BNode | None:
    """Build a restriction BNode, add its triples to g, return the BNode.

    Returns None for complement restrictions (handled separately as disjointness).
    """
    prop_iri = _iri(restr.property_iri)

    if restr.restriction_type == "someValuesFrom":
        r = BNode(f"r_sv_{key}")
        g.add((r, RDF.type, OWL.Restriction))
        g.add((r, OWL.onProperty, prop_iri))
        g.add((r, OWL.someValuesFrom, _iri(restr.value)))
        return r

    if restr.restriction_type == "hasValue":
        r = BNode(f"r_hv_{key}")
        g.add((r, RDF.type, OWL.Restriction))
        g.add((r, OWL.onProperty, prop_iri))
        val = restr.value
        if ":" in val:
            filler: URIRef | Literal = URIRef(val)
        elif val.lower() in ("true", "false"):
            filler = Literal(val.lower() == "true", datatype=XSD.boolean)
        else:
            filler = Literal(val, datatype=XSD.string)
        g.add((r, OWL.hasValue, filler))
        return r

    if restr.restriction_type == "decimalRange":
        facet_iri = URIRef(restr.facet) if restr.facet else XSD.maxInclusive
        facet_b = BNode(f"facet_{key}")
        g.add((facet_b, facet_iri, Literal(str(float(restr.value)), datatype=XSD.decimal)))
        dtype = BNode(f"dtype_{key}")
        g.add((dtype, RDF.type, RDFS.Datatype))
        g.add((dtype, OWL.onDatatype, XSD.decimal))
        fl = BNode(f"fl_{key}")
        g.add((fl, RDF.first, facet_b))
        g.add((fl, RDF.rest, RDF.nil))
        g.add((dtype, OWL.withRestrictions, fl))
        r = BNode(f"r_dr_{key}")
        g.add((r, RDF.type, OWL.Restriction))
        g.add((r, OWL.onProperty, prop_iri))
        g.add((r, OWL.someValuesFrom, dtype))
        return r

    return None  # complement — caller handles separately


def build_graph_from_node_axiom_set(g: Graph, axiom_set: NodeAxiomSet) -> None:
    """Merge OWL triples from a NodeAxiomSet into *g*.

    New classes are expressed as *defined classes* (owl:equivalentClass with an
    intersection of their parent and all non-complement restrictions), enabling
    OWL reasoners to classify ABox individuals from their properties alone.

    Restrictions on existing (non-new) classes remain as rdfs:subClassOf
    (necessary conditions). Complement/disjointness axioms are always subClassOf.
    """
    # Index restrictions by the class they apply to
    restr_by_class: dict[str, list[tuple[int, NodeRestriction]]] = {}
    for i, restr in enumerate(axiom_set.restrictions):
        key = str(_iri(restr.owl_class_iri))
        restr_by_class.setdefault(key, []).append((i, restr))

    new_class_iris: set[str] = {str(_iri(nc.iri_local_name)) for nc in axiom_set.new_classes}

    # ── New classes: defined via owl:equivalentClass ──────────────────────────
    for nc in axiom_set.new_classes:
        cls_iri = _iri(nc.iri_local_name)
        g.add((cls_iri, RDF.type, OWL.Class))
        g.add((cls_iri, RDFS.label, Literal(nc.label_en, lang="en")))
        g.add((cls_iri, RDFS.label, Literal(nc.label_de, lang="de")))
        g.add((cls_iri, _IAO_DEFINITION, Literal(nc.definition_en, lang="en")))

        parent_iri = URIRef(nc.bfo_parent_iri)
        cls_restrs = restr_by_class.get(str(cls_iri), [])

        defining = [(i, r) for i, r in cls_restrs if r.restriction_type != "complement"]
        disjoint = [(i, r) for i, r in cls_restrs if r.restriction_type == "complement"]

        if defining:
            # equivalentClass (parent ⊓ r1 ⊓ r2 ⊓ …) — sufficient for classification
            parts: list = [parent_iri]
            for i, restr in defining:
                bnode = _restr_bnode(g, restr, f"{axiom_set.cn_code}:{i}")
                if bnode is not None:
                    parts.append(bnode)
            _equiv(g, cls_iri, parts, f"{axiom_set.cn_code}:{nc.iri_local_name[:12]}")
        else:
            g.add((cls_iri, RDFS.subClassOf, parent_iri))

        # Disjointness stays as subClassOf (not part of the definition)
        for i, restr in disjoint:
            compl = BNode(f"r_compl_{axiom_set.cn_code}:{i}")
            g.add((compl, RDF.type, OWL.Class))
            g.add((compl, OWL.complementOf, _iri(restr.value)))
            g.add((cls_iri, RDFS.subClassOf, compl))

    # ── New properties ────────────────────────────────────────────────────────
    for np_ in axiom_set.new_properties:
        prop_iri = _iri(np_.iri_local_name)
        prop_type = OWL.ObjectProperty if np_.property_type == "object" else OWL.DatatypeProperty
        g.add((prop_iri, RDF.type, prop_type))
        if np_.is_functional:
            g.add((prop_iri, RDF.type, OWL.FunctionalProperty))
        g.add((prop_iri, RDFS.label, Literal(np_.label_en, lang="en")))
        if np_.domain_iri:
            g.add((prop_iri, RDFS.domain, _iri(np_.domain_iri)))
        if np_.range_iri:
            g.add((prop_iri, RDFS.range, _iri(np_.range_iri)))

    # ── Restrictions on existing classes: subClassOf (necessary conditions) ──
    for i, restr in enumerate(axiom_set.restrictions):
        cls_iri = _iri(restr.owl_class_iri)
        if str(cls_iri) in new_class_iris:
            continue  # handled above via equivalentClass
        key = f"{axiom_set.cn_code}:{i}"
        if restr.restriction_type == "complement":
            compl = BNode(f"r_compl_{key}")
            g.add((compl, RDF.type, OWL.Class))
            g.add((compl, OWL.complementOf, _iri(restr.value)))
            g.add((cls_iri, RDFS.subClassOf, compl))
        else:
            r = _restr_bnode(g, restr, key)
            if r is not None:
                g.add((cls_iri, RDFS.subClassOf, r))


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
