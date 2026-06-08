import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from src.ontology.namespaces import BFO_PROCESS, EUCN
from src.ontology.process_classes_ch23_feed import add_process_classes_ch23_feed

PROCESS_CLASSES = [
    EUCN.AnimalMealRendering,
    EUCN.GrainMillingProcess,
    EUCN.StarchExtractionProcess,
    EUCN.SoybeanOilExtraction,
    EUCN.GroundnutOilExtraction,
    EUCN.OtherOilseedExtraction,
    EUCN.WineLeesByproduction,
    EUCN.PlantResidueCollection,
    EUCN.AnimalFeedMixing,
]


class TestProcessClassesCh23Feed:
    def _graph(self) -> Graph:
        g = Graph()
        add_process_classes_ch23_feed(g)
        return g

    @pytest.mark.parametrize("cls", PROCESS_CLASSES)
    def test_process_class_is_owl_class(self, cls):
        g = self._graph()
        assert (cls, RDF.type, OWL.Class) in g

    @pytest.mark.parametrize("cls", PROCESS_CLASSES)
    def test_process_class_subclass_bfo_process(self, cls):
        g = self._graph()
        assert (cls, RDFS.subClassOf, BFO_PROCESS) in g

    @pytest.mark.parametrize("cls", PROCESS_CLASSES)
    def test_process_class_has_bilingual_labels(self, cls):
        from rdflib import Literal
        g = self._graph()
        en = any(isinstance(o, Literal) and o.language == "en"
                 for s, p, o in g if s == cls and p == RDFS.label)
        de = any(isinstance(o, Literal) and o.language == "de"
                 for s, p, o in g if s == cls and p == RDFS.label)
        assert en and de, f"{cls} missing bilingual labels"

    def test_nine_process_classes(self):
        g = self._graph()
        classes = {s for s, p, o in g
                   if p == RDFS.subClassOf and o == BFO_PROCESS}
        assert len(classes) == 9

    def test_pairwise_disjoint_soya_vs_groundnut(self):
        g = self._graph()
        assert (EUCN.SoybeanOilExtraction, OWL.disjointWith, EUCN.GroundnutOilExtraction) in g
        assert (EUCN.GroundnutOilExtraction, OWL.disjointWith, EUCN.SoybeanOilExtraction) in g

    def test_pairwise_disjoint_count(self):
        g = self._graph()
        pairs = sum(1 for s, p, o in g if p == OWL.disjointWith)
        assert pairs == 9 * 8  # symmetric: 9 choose 2 = 36 pairs, each direction

    def test_idempotent(self):
        g = Graph()
        add_process_classes_ch23_feed(g)
        n1 = len(g)
        add_process_classes_ch23_feed(g)
        assert len(g) == n1
