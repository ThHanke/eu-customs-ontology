from rdflib import URIRef
from src.ontology.iri import (
    cn_code_iri,
    taric_measure_iri,
    classification_node_iri,
    mint_iri,
)


class TestIRIMinting:
    def test_cn_code_deterministic(self):
        assert cn_code_iri("22042100") == cn_code_iri("22042100")

    def test_cn_code_is_uriref(self):
        iri = cn_code_iri("22042100")
        assert isinstance(iri, URIRef)
        assert iri.startswith("https://eu-customs-ontology.example.org/ontology/")

    def test_different_codes_different_iris(self):
        assert cn_code_iri("22042100") != cn_code_iri("22042200")

    def test_taric_measure_deterministic(self):
        assert taric_measure_iri("123456") == taric_measure_iri("123456")

    def test_classification_node_deterministic(self):
        path = ["Q1:yes", "Q2:no"]
        assert classification_node_iri(path) == classification_node_iri(path)

    def test_classification_node_root(self):
        iri = classification_node_iri([])
        assert isinstance(iri, URIRef)

    def test_classification_node_different_paths(self):
        a = classification_node_iri(["A"])
        b = classification_node_iri(["B"])
        assert a != b

    def test_cn_vs_measure_differ(self):
        assert cn_code_iri("22042100") != taric_measure_iri("22042100")
