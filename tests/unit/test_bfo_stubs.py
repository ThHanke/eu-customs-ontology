import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS

from src.ontology.bfo_stubs import add_bfo_stubs
from src.ontology.namespaces import BFO, BFO_OBJECT
from src.ontology.tbox import build_tbox


class TestBFOStubs:
    def test_bfo_object_is_owl_class(self):
        g = Graph()
        add_bfo_stubs(g)
        assert (BFO_OBJECT, RDF.type, OWL.Class) in g

    def test_idempotent(self):
        g = Graph()
        add_bfo_stubs(g)
        count1 = len(g)
        add_bfo_stubs(g)
        count2 = len(g)
        assert count1 == count2

    def test_bfo_object_iri_prefix(self):
        iri = str(BFO_OBJECT)
        assert iri.startswith("http://purl.obolibrary.org/obo/BFO_")

    def test_en_label(self):
        g = Graph()
        add_bfo_stubs(g)
        labels = [o for o in g.objects(BFO_OBJECT, RDFS.label) if hasattr(o, "language") and o.language == "en"]
        assert labels

    def test_de_label(self):
        g = Graph()
        add_bfo_stubs(g)
        labels = [o for o in g.objects(BFO_OBJECT, RDFS.label) if hasattr(o, "language") and o.language == "de"]
        assert labels

    def test_is_defined_by(self):
        from src.ontology.bfo_stubs import BFO_ONTOLOGY_URI
        g = Graph()
        add_bfo_stubs(g)
        assert (BFO_OBJECT, RDFS.isDefinedBy, BFO_ONTOLOGY_URI) in g

    def test_tbox_contains_bfo_stub(self):
        g = build_tbox(Graph())
        assert (BFO_OBJECT, RDF.type, OWL.Class) in g
