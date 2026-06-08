"""Unit tests for Chapter 22 curated equivalence axioms."""
import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF

from src.ontology.bfo_stubs import add_bfo_stubs
from src.ontology.discriminating_props import add_discriminating_props
from src.ontology.equivalence_axioms import add_ch22_equivalence_axioms
from src.ontology.namespaces import EUCN
from src.ontology.product_classes import add_product_classes_ch22

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


class TestEquivalenceAxioms:
    def _graph(self) -> Graph:
        g = Graph()
        add_bfo_stubs(g)
        add_discriminating_props(g)
        add_product_classes_ch22(g)
        add_ch22_equivalence_axioms(g)
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
        add_discriminating_props(g)
        add_product_classes_ch22(g)
        add_ch22_equivalence_axioms(g)
        count1 = len(g)
        add_ch22_equivalence_axioms(g)
        count2 = len(g)
        assert count1 == count2
