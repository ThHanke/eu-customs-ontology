"""Unit tests for Ch22 BFO Process subclasses and singleton individuals."""
import itertools

import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from src.ontology.bfo_stubs import add_bfo_stubs
from src.ontology.namespaces import BFO_PROCESS, EUCN
from src.ontology.process_classes_ch22 import add_process_classes_ch22
from src.ontology.tbox import build_tbox

# ── Fixture data ──────────────────────────────────────────────────────────────

PROCESS_CLASSES = [
    EUCN.MaltFermentation,
    EUCN.GrapeFermentation,
    EUCN.GrapeFlavouringProcess,
    EUCN.FruitFermentation,
    EUCN.GrainDistillation,
    EUCN.AceticFermentation,
    EUCN.SweetenedWaterProcess,
]

SINGLETONS = [
    EUCN["malt-fermentation"],
    EUCN["grape-fermentation"],
    EUCN["grape-flavouring"],
    EUCN["fruit-fermentation"],
    EUCN["grain-distillation"],
    EUCN["acetic-fermentation"],
    EUCN["sweetened-water-process"],
]

# Map from singleton IRI to its class IRI
SINGLETON_CLASS = {
    EUCN["malt-fermentation"]: EUCN.MaltFermentation,
    EUCN["grape-fermentation"]: EUCN.GrapeFermentation,
    EUCN["grape-flavouring"]: EUCN.GrapeFlavouringProcess,
    EUCN["fruit-fermentation"]: EUCN.FruitFermentation,
    EUCN["grain-distillation"]: EUCN.GrainDistillation,
    EUCN["acetic-fermentation"]: EUCN.AceticFermentation,
    EUCN["sweetened-water-process"]: EUCN.SweetenedWaterProcess,
}


def _graph() -> Graph:
    g = Graph()
    add_bfo_stubs(g)
    add_process_classes_ch22(g)
    return g


# ── Process class tests ───────────────────────────────────────────────────────

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


# ── Singleton individual tests ────────────────────────────────────────────────

class TestProcessSingletons:
    def test_all_singletons_are_named_individuals(self):
        g = _graph()
        for ind in SINGLETONS:
            assert (ind, RDF.type, OWL.NamedIndividual) in g, \
                f"{ind} missing rdf:type owl:NamedIndividual"

    def test_all_singletons_typed_as_their_class(self):
        g = _graph()
        for ind, cls in SINGLETON_CLASS.items():
            assert (ind, RDF.type, cls) in g, \
                f"{ind} missing rdf:type {cls}"

    def test_all_singletons_have_en_label(self):
        g = _graph()
        for ind in SINGLETONS:
            labels = [o for o in g.objects(ind, RDFS.label)
                      if hasattr(o, "language") and o.language == "en"]
            assert labels, f"{ind} missing rdfs:label@en"

    def test_all_singletons_have_de_label(self):
        g = _graph()
        for ind in SINGLETONS:
            labels = [o for o in g.objects(ind, RDFS.label)
                      if hasattr(o, "language") and o.language == "de"]
            assert labels, f"{ind} missing rdfs:label@de"


# ── Pairwise owl:differentFrom tests ─────────────────────────────────────────

class TestDifferentFrom:
    def test_all_21_pairs_have_differentFrom_forward(self):
        g = _graph()
        pairs = list(itertools.combinations(SINGLETONS, 2))
        assert len(pairs) == 21, f"Expected 21 pairs, got {len(pairs)}"
        for a, b in pairs:
            assert (a, OWL.differentFrom, b) in g, \
                f"Missing {a} owl:differentFrom {b}"

    def test_all_21_pairs_have_differentFrom_symmetric(self):
        g = _graph()
        for a, b in itertools.combinations(SINGLETONS, 2):
            assert (b, OWL.differentFrom, a) in g, \
                f"Missing symmetric {b} owl:differentFrom {a}"

    def test_differentFrom_count_is_42(self):
        """21 pairs × 2 directions = 42 differentFrom triples."""
        g = _graph()
        count = sum(
            1 for _ in g.triples((None, OWL.differentFrom, None))
        )
        assert count == 42, f"Expected 42 owl:differentFrom triples, got {count}"


# ── Pairwise owl:disjointWith tests (classes) ────────────────────────────────

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


# ── Integration tests ─────────────────────────────────────────────────────────

class TestIntegration:
    def test_tbox_has_all_7_process_classes(self):
        g = build_tbox(Graph())
        for cls in PROCESS_CLASSES:
            assert (cls, RDF.type, OWL.Class) in g, \
                f"build_tbox missing {cls}"

    def test_tbox_has_all_7_singletons(self):
        g = build_tbox(Graph())
        for ind in SINGLETONS:
            assert (ind, RDF.type, OWL.NamedIndividual) in g, \
                f"build_tbox missing singleton {ind}"

    def test_tbox_has_differentFrom_axioms(self):
        g = build_tbox(Graph())
        for a, b in itertools.combinations(SINGLETONS, 2):
            assert (a, OWL.differentFrom, b) in g, \
                f"build_tbox missing {a} owl:differentFrom {b}"


# ── Idempotency test ──────────────────────────────────────────────────────────

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
