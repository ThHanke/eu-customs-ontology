"""Unit tests for Chapter 22 curated equivalence axioms."""
import pytest
from rdflib import Graph, Literal
from rdflib.namespace import OWL, RDF, XSD

from src.ontology.bfo_stubs import add_bfo_stubs
from src.ontology.discriminating_props_beverages import add_discriminating_props_beverages
from src.ontology.equivalence_axioms_beverages import add_equivalence_axioms_beverages
from src.ontology.namespaces import EUCN
from src.ontology.product_classes_beverages import add_product_classes_beverages

PRODUCT_CLASSES_WITH_EQUIV = [
    EUCN.Water,
    EUCN.NonAlcoholicBeverage,
    EUCN.Beer,
    EUCN.Wine,
    EUCN.SparklingWine,
    EUCN.StillWine,
    EUCN.FlavouredWine,
    EUCN.FermentedBeverage,
    EUCN.EthylAlcohol,
    EUCN.Spirit,
    EUCN.Vinegar,
]


class TestEquivalenceAxiomsBeverages:
    def _graph(self) -> Graph:
        g = Graph()
        add_bfo_stubs(g)
        add_discriminating_props_beverages(g)
        add_product_classes_beverages(g)
        add_equivalence_axioms_beverages(g)
        return g

    def test_beer_equivalentclass_present(self):
        g = self._graph()
        equiv = list(g.objects(EUCN.Beer, OWL.equivalentClass))
        assert equiv, "eucn:Beer must have owl:equivalentClass"

    def test_all_product_classes_have_equiv(self):
        g = self._graph()
        for cls in PRODUCT_CLASSES_WITH_EQUIV:
            equiv = list(g.objects(cls, OWL.equivalentClass))
            assert equiv, f"{cls} missing owl:equivalentClass"

    def test_equiv_subjects_are_known_classes(self):
        g = self._graph()
        known = set(PRODUCT_CLASSES_WITH_EQUIV)
        for s, _, _ in g.triples((None, OWL.equivalentClass, None)):
            # subject must be a named (non-blank) URI
            if not isinstance(s, type(EUCN.Beer)):
                continue  # skip blank node subjects
            assert s in known, f"Unexpected equivalentClass subject: {s}"

    def test_no_literal_as_equivalentclass_object(self):
        from rdflib import Literal
        g = self._graph()
        # Objects of owl:equivalentClass must be class expressions (BNode or URIRef), never Literals
        for _, _, o in g.triples((None, OWL.equivalentClass, None)):
            assert not isinstance(o, Literal), f"Literal as equivalentClass object: {o}"

    def test_beer_intersection_has_restrictions(self):
        g = self._graph()
        inter = list(g.objects(EUCN.Beer, OWL.equivalentClass))
        assert inter
        inter_bnode = inter[0]
        restr_list = list(g.objects(inter_bnode, OWL.intersectionOf))
        assert restr_list, "Beer equivalentClass must have intersectionOf"

    def test_idempotent(self):
        g = Graph()
        add_bfo_stubs(g)
        add_discriminating_props_beverages(g)
        add_product_classes_beverages(g)
        add_equivalence_axioms_beverages(g)
        count1 = len(g)
        add_equivalence_axioms_beverages(g)
        count2 = len(g)
        assert count1 == count2


def _hasvalue_complements_in_intersection(g: Graph, cls_iri) -> list[tuple]:
    """Return (prop, val) pairs from NOT(prop=val) complements in cls_iri's intersection."""
    inter_bnode = list(g.objects(cls_iri, OWL.equivalentClass))[0]
    node = list(g.objects(inter_bnode, OWL.intersectionOf))[0]
    pairs = []
    while node != RDF.nil:
        first = list(g.objects(node, RDF.first))
        if first:
            member = first[0]
            for inner in g.objects(member, OWL.complementOf):
                if (inner, RDF.type, OWL.Restriction) in g:
                    for prop in g.objects(inner, OWL.onProperty):
                        for val in g.objects(inner, OWL.hasValue):
                            pairs.append((prop, val))
        rest = list(g.objects(node, RDF.rest))
        node = rest[0] if rest else RDF.nil
    return pairs


def _expected_neg_hasvalue_pairs(g: Graph, cls_iri) -> set[tuple]:
    """Collect (prop, val) from hasValue restrictions in disjoint siblings' equivalentClass."""
    pairs = set()
    for sibling in g.objects(cls_iri, OWL.disjointWith):
        for inter in g.objects(sibling, OWL.equivalentClass):
            lst = list(g.objects(inter, OWL.intersectionOf))
            if not lst:
                continue
            node = lst[0]
            while node != RDF.nil:
                first = list(g.objects(node, RDF.first))
                if first:
                    m = first[0]
                    if (m, RDF.type, OWL.Restriction) in g and (m, OWL.hasValue, None) in g:
                        for p in g.objects(m, OWL.onProperty):
                            for v in g.objects(m, OWL.hasValue):
                                pairs.add((p, v))
                rest = list(g.objects(node, RDF.rest))
                node = rest[0] if rest else RDF.nil
    return pairs


class TestEquivalenceComplementRestrictions:
    def _graph(self) -> Graph:
        g = Graph()
        add_bfo_stubs(g)
        add_discriminating_props_beverages(g)
        add_product_classes_beverages(g)
        add_equivalence_axioms_beverages(g)
        return g

    def test_spirit_neg_hasvalue_covers_all_disjoint_sibling_conditions(self):
        g = self._graph()
        expected = _expected_neg_hasvalue_pairs(g, EUCN.Spirit)
        actual = set(_hasvalue_complements_in_intersection(g, EUCN.Spirit))
        assert actual == expected, (
            f"Spirit NOT(P=v) mismatch: actual={actual}, expected={expected}"
        )

    def test_ethyl_neg_hasvalue_covers_all_disjoint_sibling_conditions(self):
        g = self._graph()
        expected = _expected_neg_hasvalue_pairs(g, EUCN.EthylAlcohol)
        actual = set(_hasvalue_complements_in_intersection(g, EUCN.EthylAlcohol))
        assert actual == expected, (
            f"EthylAlcohol NOT(P=v) mismatch: actual={actual}, expected={expected}"
        )

    def test_complement_bnode_is_owl_class(self):
        g = self._graph()
        outer_bnodes = list(g.subjects(OWL.complementOf, None))
        assert outer_bnodes, "Expected complement BNodes"
        for b in outer_bnodes:
            assert (b, RDF.type, OWL.Class) in g, f"Complement BNode {b} not typed owl:Class"
