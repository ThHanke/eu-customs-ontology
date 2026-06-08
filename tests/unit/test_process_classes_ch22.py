"""Unit tests for Ch22 BFO Process subclasses."""
import itertools

from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from src.ontology.bfo_stubs import add_bfo_stubs
from src.ontology.namespaces import BFO_PROCESS, EUCN
from src.ontology.process_classes_ch22 import add_process_classes_ch22
from src.ontology.tbox import build_tbox

PROCESS_CLASSES = [
    EUCN.MaltFermentation,
    EUCN.GrapeFermentation,
    EUCN.GrapeFlavouringProcess,
    EUCN.FruitFermentation,
    EUCN.GrainDistillation,
    EUCN.AceticFermentation,
    EUCN.SweetenedWaterProcess,
]


def _graph() -> Graph:
    g = Graph()
    add_bfo_stubs(g)
    add_process_classes_ch22(g)
    return g


class TestProcessClasses:
    def test_all_process_classes_are_owl_classes(self):
        g = _graph()
        for cls in PROCESS_CLASSES:
            assert (cls, RDF.type, OWL.Class) in g, f"{cls} missing rdf:type owl:Class"

    def test_all_process_classes_subclass_of_bfo_process(self):
        g = _graph()
        for cls in PROCESS_CLASSES:
            assert (cls, RDFS.subClassOf, BFO_PROCESS) in g, \
                f"{cls} missing rdfs:subClassOf BFO_PROCESS"

    def test_all_process_classes_have_en_label(self):
        g = _graph()
        for cls in PROCESS_CLASSES:
            labels = [o for o in g.objects(cls, RDFS.label)
                      if hasattr(o, "language") and o.language == "en"]
            assert labels, f"{cls} missing rdfs:label@en"

    def test_all_process_classes_have_de_label(self):
        g = _graph()
        for cls in PROCESS_CLASSES:
            labels = [o for o in g.objects(cls, RDFS.label)
                      if hasattr(o, "language") and o.language == "de"]
            assert labels, f"{cls} missing rdfs:label@de"

    def test_all_process_classes_have_en_definition(self):
        g = _graph()
        for cls in PROCESS_CLASSES:
            defs = [o for o in g.objects(cls, SKOS.definition)
                    if hasattr(o, "language") and o.language == "en"]
            assert defs, f"{cls} missing skos:definition@en"

    def test_all_process_classes_have_de_definition(self):
        g = _graph()
        for cls in PROCESS_CLASSES:
            defs = [o for o in g.objects(cls, SKOS.definition)
                    if hasattr(o, "language") and o.language == "de"]
            assert defs, f"{cls} missing skos:definition@de"


class TestDisjointWith:
    def test_all_21_pairs_have_disjointWith_forward(self):
        g = _graph()
        for a, b in itertools.combinations(PROCESS_CLASSES, 2):
            assert (a, OWL.disjointWith, b) in g, \
                f"Missing {a} owl:disjointWith {b}"

    def test_all_21_pairs_have_disjointWith_symmetric(self):
        g = _graph()
        for a, b in itertools.combinations(PROCESS_CLASSES, 2):
            assert (b, OWL.disjointWith, a) in g, \
                f"Missing symmetric {b} owl:disjointWith {a}"

    def test_no_singletons_in_graph(self):
        """Process singletons removed — classification uses class membership."""
        g = _graph()
        for ind_iri in [
            EUCN["malt-fermentation"], EUCN["grape-fermentation"],
            EUCN["grape-flavouring"], EUCN["fruit-fermentation"],
            EUCN["grain-distillation"], EUCN["acetic-fermentation"],
            EUCN["sweetened-water-process"],
        ]:
            assert (ind_iri, RDF.type, OWL.NamedIndividual) not in g, \
                f"Unexpected singleton {ind_iri} still in graph"


class TestIntegration:
    def test_tbox_has_all_7_process_classes(self):
        g = build_tbox(Graph())
        for cls in PROCESS_CLASSES:
            assert (cls, RDF.type, OWL.Class) in g, \
                f"build_tbox missing {cls}"


class TestIdempotency:
    def test_double_call_same_triple_count(self):
        g = Graph()
        add_bfo_stubs(g)
        add_process_classes_ch22(g)
        count1 = len(g)
        add_process_classes_ch22(g)
        count2 = len(g)
        assert count1 == count2, \
            f"Idempotency violated: {count1} triples after 1st call, {count2} after 2nd"
