"""Integration: equivalence axioms pass Konclude consistency check."""
import pytest
from pathlib import Path
from rdflib import Graph, Literal
from rdflib.namespace import OWL, RDF, XSD

from src.ontology.bfo_stubs import add_bfo_stubs
from src.ontology.discriminating_props_beverages import add_discriminating_props_beverages
from src.ontology.equivalence_axioms_beverages import add_equivalence_axioms_beverages
from src.ontology.namespaces import EUCN
from src.ontology.product_classes_beverages import add_product_classes_beverages
from src.ontology.tbox import build_tbox
from src.reasoning.konclude import KoncludeConsistencyError, check_consistency, classify

KONCLUDE_AVAILABLE = Path("/home/hanke/rdf-reasoner-konclude/dist/cli.js").exists()
skip_no_konclude = pytest.mark.skipif(not KONCLUDE_AVAILABLE, reason="Konclude CLI not found")


def _write_ttl(tmp_path: Path, g: Graph) -> Path:
    out = tmp_path / "test.ttl"
    out.write_text(g.serialize(format="turtle"))
    return out


@skip_no_konclude
class TestEquivalenceAxiomsIntegration:
    def _tbox_with_equiv(self) -> Graph:
        g = Graph()
        build_tbox(g)
        add_equivalence_axioms_beverages(g)
        return g

    def test_tbox_with_equiv_axioms_consistent(self, tmp_path):
        g = self._tbox_with_equiv()
        ttl = _write_ttl(tmp_path, g)
        assert check_consistency(ttl) is True

    def test_beer_and_wine_individual_inconsistent(self, tmp_path):
        """Individual typed both Beer and Wine must trigger inconsistency (disjointWith)."""
        g = self._tbox_with_equiv()
        ind = EUCN["ind/test_beer_wine"]
        g.add((ind, RDF.type, EUCN.Beer))
        g.add((ind, RDF.type, EUCN.Wine))
        ttl = _write_ttl(tmp_path, g)
        with pytest.raises(KoncludeConsistencyError):
            check_consistency(ttl)

    def test_classify_returns_output(self, tmp_path):
        """Konclude classify on TBox with equivalence axioms returns non-error output."""
        g = self._tbox_with_equiv()
        ttl = _write_ttl(tmp_path, g)
        result = classify(ttl)
        # May be empty for a trivial TBox, but should not raise
        assert isinstance(result, str)
