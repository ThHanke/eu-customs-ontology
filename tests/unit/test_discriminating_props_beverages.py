import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from src.ontology.discriminating_props_beverages import add_discriminating_props_beverages
from src.ontology.namespaces import EUCN

# The 4 DatatypeProperties declared by this module
DATA_PROPS = [
    EUCN.alcoholByVolumePercent,
    EUCN.isCarbonated,
    EUCN.isDenatured,
    EUCN.maxContainerVolumeL,
]

EXPECTED_RANGES = {
    EUCN.alcoholByVolumePercent: XSD.decimal,
    EUCN.isCarbonated: XSD.boolean,
    EUCN.isDenatured: XSD.boolean,
    EUCN.maxContainerVolumeL: XSD.decimal,
}


class TestDiscriminatingPropsBeverages:
    def _graph(self) -> Graph:
        g = Graph()
        add_discriminating_props_beverages(g)
        return g

    def test_all_four_are_datatype_properties(self):
        g = self._graph()
        for p in DATA_PROPS:
            assert (p, RDF.type, OWL.DatatypeProperty) in g, f"{p} not a DatatypeProperty"

    def test_correct_ranges(self):
        g = self._graph()
        for p, expected in EXPECTED_RANGES.items():
            actual = list(g.objects(p, RDFS.range))
            assert expected in actual, f"{p} expected range {expected}, got {actual}"

    def test_en_labels(self):
        g = self._graph()
        for p in DATA_PROPS:
            labels = [o for o in g.objects(p, RDFS.label) if hasattr(o, "language") and o.language == "en"]
            assert labels, f"{p} missing rdfs:label@en"

    def test_de_labels(self):
        g = self._graph()
        for p in DATA_PROPS:
            labels = [o for o in g.objects(p, RDFS.label) if hasattr(o, "language") and o.language == "de"]
            assert labels, f"{p} missing rdfs:label@de"

    def test_en_definitions(self):
        g = self._graph()
        for p in DATA_PROPS:
            defs = [o for o in g.objects(p, SKOS.definition) if hasattr(o, "language") and o.language == "en"]
            assert defs, f"{p} missing skos:definition@en"

    def test_de_definitions(self):
        g = self._graph()
        for p in DATA_PROPS:
            defs = [o for o in g.objects(p, SKOS.definition) if hasattr(o, "language") and o.language == "de"]
            assert defs, f"{p} missing skos:definition@de"

    def test_data_props_not_functional(self):
        g = self._graph()
        for p in DATA_PROPS:
            assert (p, RDF.type, OWL.FunctionalProperty) not in g, f"{p} must not be FunctionalProperty"

    def test_produced_by_not_in_graph(self):
        """eucn:producedBy must not be declared here — it lives in core.py."""
        g = self._graph()
        assert (EUCN.producedBy, RDF.type, OWL.ObjectProperty) not in g

    def test_fermentation_base_not_in_graph(self):
        g = self._graph()
        assert (EUCN.fermentationBase, RDF.type, OWL.DatatypeProperty) not in g

    def test_idempotent(self):
        g = Graph()
        add_discriminating_props_beverages(g)
        count1 = len(g)
        add_discriminating_props_beverages(g)
        count2 = len(g)
        assert count1 == count2

    def test_turtle_roundtrip(self):
        g = self._graph()
        ttl = g.serialize(format="turtle")
        g2 = Graph()
        g2.parse(data=ttl, format="turtle")
        assert len(g2) == len(g)
