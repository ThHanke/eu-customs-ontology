"""Unit tests for src/ontology/core.py — build_core_tbox."""
from __future__ import annotations

import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS, XSD

from src.ontology.core import CORE_IRI, build_core_tbox
from src.ontology.namespaces import BFO_OBJECT, BFO_PROCESS, EUCN, RO_HAS_OUTPUT


# ── Fixture ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def core_graph() -> Graph:
    return build_core_tbox(Graph())


# ── 1. Returns a Graph instance ───────────────────────────────────────────────

class TestReturnType:
    def test_returns_graph(self):
        g = build_core_tbox(Graph())
        assert isinstance(g, Graph)


# ── 2. Ontology header ────────────────────────────────────────────────────────

class TestOntologyHeader:
    def test_core_iri_is_owl_ontology(self, core_graph):
        assert (CORE_IRI, RDF.type, OWL.Ontology) in core_graph


# ── 3-5. eucn:producedBy ──────────────────────────────────────────────────────

class TestProducedBy:
    def test_is_object_property(self, core_graph):
        assert (EUCN.producedBy, RDF.type, OWL.ObjectProperty) in core_graph

    def test_is_functional_property(self, core_graph):
        assert (EUCN.producedBy, RDF.type, OWL.FunctionalProperty) in core_graph

    def test_inverse_of_ro_has_output(self, core_graph):
        assert (EUCN.producedBy, OWL.inverseOf, RO_HAS_OUTPUT) in core_graph

    def test_label_en(self, core_graph):
        from rdflib import Literal
        assert (EUCN.producedBy, RDFS.label, Literal("produced by", lang="en")) in core_graph

    def test_label_de(self, core_graph):
        from rdflib import Literal
        assert (EUCN.producedBy, RDFS.label, Literal("hergestellt durch", lang="de")) in core_graph


# ── 6-7. eucn:cnHeadingCode ───────────────────────────────────────────────────

class TestCnHeadingCode:
    def test_is_datatype_property(self, core_graph):
        assert (EUCN.cnHeadingCode, RDF.type, OWL.DatatypeProperty) in core_graph

    def test_range_is_xsd_string(self, core_graph):
        assert (EUCN.cnHeadingCode, RDFS.range, XSD.string) in core_graph

    def test_label_en(self, core_graph):
        from rdflib import Literal
        assert (EUCN.cnHeadingCode, RDFS.label, Literal("CN heading code", lang="en")) in core_graph

    def test_label_de(self, core_graph):
        from rdflib import Literal
        assert (EUCN.cnHeadingCode, RDFS.label, Literal("KN-Positionsnummer", lang="de")) in core_graph


# ── 8-9. BFO stubs ────────────────────────────────────────────────────────────

class TestBfoStubs:
    def test_bfo_object_is_declared(self, core_graph):
        assert (BFO_OBJECT, RDF.type, OWL.Class) in core_graph

    def test_bfo_process_is_declared(self, core_graph):
        assert (BFO_PROCESS, RDF.type, OWL.Class) in core_graph


# ── 10. Idempotency ───────────────────────────────────────────────────────────

class TestIdempotency:
    def test_calling_twice_same_triple_count(self):
        g = Graph()
        build_core_tbox(g)
        count1 = len(g)
        build_core_tbox(g)
        count2 = len(g)
        assert count1 == count2, f"Duplicate triples added: {count1} → {count2}"


# ── 11-12. Bilingual labels (already covered per-property above, extra check) ─

class TestBilingualLabels:
    def test_produced_by_has_en_and_de_labels(self, core_graph):
        labels = list(core_graph.objects(EUCN.producedBy, RDFS.label))
        langs = {getattr(lbl, "language", None) for lbl in labels}
        assert "en" in langs
        assert "de" in langs

    def test_cn_heading_code_has_en_and_de_labels(self, core_graph):
        labels = list(core_graph.objects(EUCN.cnHeadingCode, RDFS.label))
        langs = {getattr(lbl, "language", None) for lbl in labels}
        assert "en" in langs
        assert "de" in langs


# ── 13. Turtle roundtrip ──────────────────────────────────────────────────────

class TestTurtleRoundtrip:
    def test_serializes_and_parses_as_turtle(self, core_graph):
        ttl = core_graph.serialize(format="turtle")
        g2 = Graph()
        g2.parse(data=ttl, format="turtle")
        assert len(g2) > 0
        assert len(g2) == len(core_graph)


# ── 14. No chapter-specific classes ──────────────────────────────────────────

class TestNoChapterSpecificClasses:
    _CHAPTER_CLASSES = [
        EUCN.Beer,
        EUCN.Wine,
        EUCN.SparklingWine,
        EUCN.StillWine,
        EUCN.Spirits,
        EUCN.Ethanol,
    ]

    def test_no_beer_class(self, core_graph):
        assert (EUCN.Beer, RDF.type, OWL.Class) not in core_graph

    def test_no_wine_class(self, core_graph):
        assert (EUCN.Wine, RDF.type, OWL.Class) not in core_graph

    def test_no_chapter_specific_classes(self, core_graph):
        classes = set(core_graph.subjects(RDF.type, OWL.Class))
        for cls in self._CHAPTER_CLASSES:
            assert cls not in classes, f"Chapter-specific class {cls} found in core graph"
