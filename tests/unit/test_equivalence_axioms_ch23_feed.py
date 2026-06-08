import pytest
from rdflib import Graph
from rdflib.namespace import OWL

from src.ontology.bfo_stubs import add_bfo_stubs
from src.ontology.core import build_core_tbox
from src.ontology.equivalence_axioms_ch23_feed import add_equivalence_axioms_ch23_feed
from src.ontology.namespaces import EUCN
from src.ontology.process_classes_ch23_feed import add_process_classes_ch23_feed
from src.ontology.product_classes_ch23_feed import add_product_classes_ch23_feed

EQUIV_CLASSES = [
    EUCN.AnimalByProductMeal,
    EUCN.CerealMillingResidue,
    EUCN.StarchManufactureResidue,
    EUCN.SoybeanOilcake,
    EUCN.GroundnutOilcake,
    EUCN.VegetableOilcake,
    EUCN.WineLees,
    EUCN.PlantResidue,
    EUCN.AnimalFeedPreparation,
]


class TestEquivalenceAxiomsCh23Feed:
    def _graph(self) -> Graph:
        g = Graph()
        add_bfo_stubs(g)
        build_core_tbox(g)
        add_product_classes_ch23_feed(g)
        add_process_classes_ch23_feed(g)
        add_equivalence_axioms_ch23_feed(g)
        return g

    @pytest.mark.parametrize("cls", EQUIV_CLASSES)
    def test_has_equivalent_class_axiom(self, cls):
        g = self._graph()
        equiv_objects = [o for s, p, o in g
                         if s == cls and p == OWL.equivalentClass]
        assert equiv_objects, f"{cls} has no equivalentClass axiom"

    def test_nine_equivalence_axioms(self):
        g = self._graph()
        classes_with_equiv = {s for s, p, o in g if p == OWL.equivalentClass}
        ch23_classes = set(EQUIV_CLASSES)
        assert ch23_classes.issubset(classes_with_equiv)

    def test_soyabean_equiv_uses_soybean_extraction(self):
        from rdflib.namespace import OWL
        g = self._graph()
        some_values = {o for s, p, o in g if p == OWL.someValuesFrom}
        assert EUCN.SoybeanOilExtraction in some_values

    def test_wine_lees_equiv_uses_wine_lees_byproduction(self):
        g = self._graph()
        some_values = {o for s, p, o in g if p == OWL.someValuesFrom}
        assert EUCN.WineLeesByproduction in some_values

    def test_idempotent(self):
        g = Graph()
        add_bfo_stubs(g)
        build_core_tbox(g)
        add_product_classes_ch23_feed(g)
        add_process_classes_ch23_feed(g)
        add_equivalence_axioms_ch23_feed(g)
        n1 = len(g)
        add_equivalence_axioms_ch23_feed(g)
        assert len(g) == n1
