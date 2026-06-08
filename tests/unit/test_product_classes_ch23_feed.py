import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from src.ontology.bfo_stubs import add_bfo_stubs
from src.ontology.namespaces import BFO_OBJECT, EUCN
from src.ontology.product_classes_ch23_feed import add_product_classes_ch23_feed

HEADING_CLASSES = [
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


class TestProductClassesCh23Feed:
    def _graph(self) -> Graph:
        g = Graph()
        add_bfo_stubs(g)
        add_product_classes_ch23_feed(g)
        return g

    def test_feedstuff_product_is_owl_class(self):
        g = self._graph()
        assert (EUCN.FeedstuffProduct, RDF.type, OWL.Class) in g

    def test_feedstuff_product_subclass_bfo_object(self):
        g = self._graph()
        assert (EUCN.FeedstuffProduct, RDFS.subClassOf, BFO_OBJECT) in g

    @pytest.mark.parametrize("cls", HEADING_CLASSES)
    def test_heading_class_is_owl_class(self, cls):
        g = self._graph()
        assert (cls, RDF.type, OWL.Class) in g

    @pytest.mark.parametrize("cls", HEADING_CLASSES)
    def test_heading_class_subclass_feedstuff_product(self, cls):
        g = self._graph()
        assert (cls, RDFS.subClassOf, EUCN.FeedstuffProduct) in g

    @pytest.mark.parametrize("cls", HEADING_CLASSES)
    def test_heading_class_has_en_label(self, cls):
        from rdflib import Literal
        g = self._graph()
        labels = {str(o) for s, p, o in g if s == cls and p == RDFS.label
                  and isinstance(o, Literal) and o.language == "en"}
        assert labels, f"{cls} missing @en label"

    @pytest.mark.parametrize("cls", HEADING_CLASSES)
    def test_heading_class_has_de_label(self, cls):
        from rdflib import Literal
        g = self._graph()
        labels = {str(o) for s, p, o in g if s == cls and p == RDFS.label
                  and isinstance(o, Literal) and o.language == "de"}
        assert labels, f"{cls} missing @de label"

    def test_animal_byproduct_meal_cn_heading_code_2301(self):
        from rdflib import Literal
        g = self._graph()
        bnode_vals = {str(o) for s, p, o in g
                      if p == OWL.hasValue and isinstance(o, Literal)
                      and str(o) == "2301"}
        assert bnode_vals

    def test_animal_feed_preparation_cn_heading_code_2309(self):
        from rdflib import Literal
        g = self._graph()
        bnode_vals = {str(o) for s, p, o in g
                      if p == OWL.hasValue and isinstance(o, Literal)
                      and str(o) == "2309"}
        assert bnode_vals

    def test_pairwise_disjoint_meal_vs_bran(self):
        g = self._graph()
        assert (EUCN.AnimalByProductMeal, OWL.disjointWith, EUCN.CerealMillingResidue) in g
        assert (EUCN.CerealMillingResidue, OWL.disjointWith, EUCN.AnimalByProductMeal) in g

    def test_idempotent(self):
        g = Graph()
        add_bfo_stubs(g)
        add_product_classes_ch23_feed(g)
        n1 = len(g)
        add_product_classes_ch23_feed(g)
        assert len(g) == n1
