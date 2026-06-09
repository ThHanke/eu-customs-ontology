import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF, SKOS

from src.ontology.tbox import build_tbox
from src.ontology.namespaces import EUCN


class TestBuildTBox:
    def _tbox(self) -> Graph:
        return build_tbox(Graph())

    def test_returns_graph(self):
        g = self._tbox()
        assert isinstance(g, Graph)

    def test_class_count(self):
        g = self._tbox()
        classes = list(g.subjects(RDF.type, OWL.Class))
        assert len(classes) >= 6, f"Expected ≥6 classes, got {len(classes)}: {classes}"

    def test_property_count(self):
        g = self._tbox()
        obj = list(g.subjects(RDF.type, OWL.ObjectProperty))
        data = list(g.subjects(RDF.type, OWL.DatatypeProperty))
        assert len(obj) + len(data) >= 10, f"Expected ≥10 properties, got {len(obj)+len(data)}"

    def test_every_class_has_en_definition(self):
        from rdflib import URIRef
        g = self._tbox()
        for cls in g.subjects(RDF.type, OWL.Class):
            if not isinstance(cls, URIRef):
                continue  # skip anonymous intersection/restriction BNodes
            en_defs = [o for o in g.objects(cls, SKOS.definition)
                       if hasattr(o, 'language') and o.language == "en"]
            assert en_defs, f"{cls} missing skos:definition@en"

    def test_every_class_has_de_definition(self):
        from rdflib import URIRef
        g = self._tbox()
        for cls in g.subjects(RDF.type, OWL.Class):
            if not isinstance(cls, URIRef):
                continue  # skip anonymous intersection/restriction BNodes
            de_defs = [o for o in g.objects(cls, SKOS.definition)
                       if hasattr(o, 'language') and o.language == "de"]
            assert de_defs, f"{cls} missing skos:definition@de"

    def test_every_property_has_en_definition(self):
        g = self._tbox()
        props = list(g.subjects(RDF.type, OWL.ObjectProperty)) + \
                list(g.subjects(RDF.type, OWL.DatatypeProperty))
        for p in props:
            en_defs = [o for o in g.objects(p, SKOS.definition)
                       if hasattr(o, 'language') and o.language == "en"]
            assert en_defs, f"{p} missing skos:definition@en"

    def test_turtle_roundtrip(self):
        g = self._tbox()
        ttl = g.serialize(format="turtle")
        g2 = Graph()
        g2.parse(data=ttl, format="turtle")
        assert len(g2) > 0

    def test_idempotent(self):
        g = Graph()
        build_tbox(g)
        size1 = len(g)
        build_tbox(g)
        size2 = len(g)
        assert size1 == size2, f"Duplicate triples added: {size1} → {size2}"

    def test_taric_code_subclass_of_cn_code(self):
        from rdflib.namespace import RDFS
        g = self._tbox()
        assert (EUCN.TARICCode, RDFS.subClassOf, EUCN.CNCode) in g
