"""Integration tests for Konclude CLI wrapper.

Requires rdf-reasoner-konclude to be present at KONCLUDE_CLI_PATH.
"""
import pytest
from pathlib import Path
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS

from src.reasoning.konclude import check_consistency, classify, KoncludeConsistencyError
from src.ontology.tbox import build_tbox

KONCLUDE_AVAILABLE = Path("/home/hanke/rdf-reasoner-konclude/dist/cli.js").exists()
skip_no_konclude = pytest.mark.skipif(not KONCLUDE_AVAILABLE, reason="Konclude CLI not found")


def _write_ttl(tmp_path: Path, g: Graph) -> Path:
    out = tmp_path / "test.ttl"
    out.write_text(g.serialize(format="turtle"))
    return out


@skip_no_konclude
class TestKonclude:
    def test_tbox_consistent(self, tmp_path):
        g = Graph()
        build_tbox(g)
        ttl = _write_ttl(tmp_path, g)
        assert check_consistency(ttl) is True

    def test_simple_abox_consistent(self, tmp_path):
        from rdflib import Literal, URIRef
        from rdflib.namespace import XSD
        from src.ontology.namespaces import CUSTOMS
        g = Graph()
        build_tbox(g)
        ind = CUSTOMS["ind/test001"]
        g.add((ind, RDF.type, CUSTOMS.CNCode))
        g.add((ind, CUSTOMS.codeString, Literal("22042100", datatype=XSD.string)))
        ttl = _write_ttl(tmp_path, g)
        assert check_consistency(ttl) is True

    def test_inconsistent_ontology_raises(self, tmp_path):
        from rdflib import URIRef
        from src.ontology.namespaces import CUSTOMS
        g = Graph()
        build_tbox(g)
        # Add two disjoint classes and type one individual as both
        ClsA = CUSTOMS["ClsA"]
        ClsB = CUSTOMS["ClsB"]
        g.add((ClsA, RDF.type, OWL.Class))
        g.add((ClsB, RDF.type, OWL.Class))
        g.add((ClsA, OWL.disjointWith, ClsB))
        ind = CUSTOMS["ind/broken"]
        g.add((ind, RDF.type, ClsA))
        g.add((ind, RDF.type, ClsB))
        ttl = _write_ttl(tmp_path, g)
        with pytest.raises(KoncludeConsistencyError):
            check_consistency(ttl)

    def test_missing_cli_raises(self, tmp_path):
        import src.reasoning.konclude as mod
        original = mod.KONCLUDE_CLI_PATH
        mod.KONCLUDE_CLI_PATH = "/nonexistent/cli.js"
        try:
            g = Graph()
            ttl = _write_ttl(tmp_path, g)
            with pytest.raises(FileNotFoundError):
                check_consistency(ttl)
        finally:
            mod.KONCLUDE_CLI_PATH = original
