import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from src.ontology.product_classes_beverages import add_product_classes_beverages
from src.ontology.bfo_stubs import add_bfo_stubs
from src.ontology.namespaces import BFO_OBJECT, EUCN
from src.ontology.tbox import build_tbox

HEADING_CLASSES = [
    EUCN.Water,
    EUCN.NonAlcoholicBeverage,
    EUCN.Beer,
    EUCN.Wine,
    EUCN.FlavouredWine,
    EUCN.FermentedBeverage,
    EUCN.EthylAlcohol,
    EUCN.Spirit,
    EUCN.Vinegar,
]

ALL_PRODUCT_CLASSES = HEADING_CLASSES + [
    EUCN.Beverage,
    EUCN.SparklingWine,
    EUCN.StillWine,
    EUCN.GrapeMust,
]


class TestProductClassesBeverages:
    def _graph(self) -> Graph:
        g = Graph()
        add_bfo_stubs(g)
        add_product_classes_beverages(g)
        return g

    def test_beer_is_owl_class(self):
        g = self._graph()
        assert (EUCN.Beer, RDF.type, OWL.Class) in g

    def test_subclass_chain_still_wine(self):
        g = self._graph()
        assert (EUCN.StillWine, RDFS.subClassOf, EUCN.Wine) in g
        assert (EUCN.Wine, RDFS.subClassOf, EUCN.Beverage) in g
        assert (EUCN.Beverage, RDFS.subClassOf, BFO_OBJECT) in g

    def test_beer_disjoint_with_wine(self):
        g = self._graph()
        assert (EUCN.Beer, OWL.disjointWith, EUCN.Wine) in g
        assert (EUCN.Wine, OWL.disjointWith, EUCN.Beer) in g

    def test_no_all_disjoint_classes(self):
        g = self._graph()
        assert (None, RDF.type, OWL.AllDisjointClasses) not in g

    def test_every_product_class_has_en_label(self):
        g = self._graph()
        for cls in ALL_PRODUCT_CLASSES:
            labels = [o for o in g.objects(cls, RDFS.label)
                      if hasattr(o, "language") and o.language == "en"]
            assert labels, f"{cls} missing rdfs:label@en"

    def test_every_product_class_has_de_label(self):
        g = self._graph()
        for cls in ALL_PRODUCT_CLASSES:
            labels = [o for o in g.objects(cls, RDFS.label)
                      if hasattr(o, "language") and o.language == "de"]
            assert labels, f"{cls} missing rdfs:label@de"

    def test_every_product_class_has_en_definition(self):
        g = self._graph()
        for cls in ALL_PRODUCT_CLASSES:
            defs = [o for o in g.objects(cls, SKOS.definition)
                    if hasattr(o, "language") and o.language == "en"]
            assert defs, f"{cls} missing skos:definition@en"

    def test_every_product_class_has_de_definition(self):
        g = self._graph()
        for cls in ALL_PRODUCT_CLASSES:
            defs = [o for o in g.objects(cls, SKOS.definition)
                    if hasattr(o, "language") and o.language == "de"]
            assert defs, f"{cls} missing skos:definition@de"

    def test_class_count_at_least_12(self):
        g = self._graph()
        classes = list(g.subjects(RDF.type, OWL.Class))
        assert len(classes) >= 12, f"Expected ≥12 OWL classes, got {len(classes)}"

    def test_all_heading_classes_disjoint(self):
        """All pairs of heading-level siblings must have owl:disjointWith."""
        import itertools
        g = self._graph()
        for a, b in itertools.combinations(HEADING_CLASSES, 2):
            assert (a, OWL.disjointWith, b) in g, f"Missing {a} disjointWith {b}"
            assert (b, OWL.disjointWith, a) in g, f"Missing {b} disjointWith {a}"

    def test_wine_subclasses_disjoint(self):
        g = self._graph()
        wine_subs = [EUCN.SparklingWine, EUCN.StillWine, EUCN.GrapeMust]
        import itertools
        for a, b in itertools.combinations(wine_subs, 2):
            assert (a, OWL.disjointWith, b) in g, f"Missing {a} disjointWith {b}"

    def test_idempotent(self):
        g = Graph()
        add_bfo_stubs(g)
        add_product_classes_beverages(g)
        count1 = len(g)
        add_product_classes_beverages(g)
        count2 = len(g)
        assert count1 == count2

    def test_tbox_has_product_classes(self):
        g = build_tbox(Graph())
        assert (EUCN.Beer, RDF.type, OWL.Class) in g
        assert (EUCN.Wine, RDF.type, OWL.Class) in g
