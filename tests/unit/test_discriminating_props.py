import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from src.ontology.discriminating_props import add_discriminating_props
from src.ontology.namespaces import BFO_PROCESS, EUCN, RO_HAS_OUTPUT

# The 4 remaining DatatypeProperties
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

# ObjectProperties
OBJ_PROPS = [EUCN.producedBy]


class TestDiscriminatingProps:
    def _graph(self) -> Graph:
        g = Graph()
        add_discriminating_props(g)
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

    def test_produced_by_is_functional(self):
        g = self._graph()
        assert (EUCN.producedBy, RDF.type, OWL.FunctionalProperty) in g

    def test_other_props_not_functional(self):
        g = self._graph()
        for p in DATA_PROPS:
            assert (p, RDF.type, OWL.FunctionalProperty) not in g, f"{p} must not be FunctionalProperty"

    def test_produced_by_is_object_property(self):
        g = self._graph()
        assert (EUCN.producedBy, RDF.type, OWL.ObjectProperty) in g

    def test_produced_by_inverse_of_ro_has_output(self):
        g = self._graph()
        assert (EUCN.producedBy, OWL.inverseOf, RO_HAS_OUTPUT) in g

    def test_produced_by_range_is_bfo_process(self):
        g = self._graph()
        assert (EUCN.producedBy, RDFS.range, BFO_PROCESS) in g

    def test_produced_by_en_label(self):
        g = self._graph()
        labels = [o for o in g.objects(EUCN.producedBy, RDFS.label) if hasattr(o, "language") and o.language == "en"]
        assert labels, "eucn:producedBy missing rdfs:label@en"

    def test_produced_by_de_label(self):
        g = self._graph()
        labels = [o for o in g.objects(EUCN.producedBy, RDFS.label) if hasattr(o, "language") and o.language == "de"]
        assert labels, "eucn:producedBy missing rdfs:label@de"

    def test_produced_by_en_definition(self):
        g = self._graph()
        defs = [o for o in g.objects(EUCN.producedBy, SKOS.definition) if hasattr(o, "language") and o.language == "en"]
        assert defs, "eucn:producedBy missing skos:definition@en"

    def test_produced_by_de_definition(self):
        g = self._graph()
        defs = [o for o in g.objects(EUCN.producedBy, SKOS.definition) if hasattr(o, "language") and o.language == "de"]
        assert defs, "eucn:producedBy missing skos:definition@de"

    def test_fermentation_base_not_in_graph(self):
        g = self._graph()
        assert (EUCN.fermentationBase, RDF.type, OWL.DatatypeProperty) not in g

    def test_idempotent(self):
        g = Graph()
        add_discriminating_props(g)
        count1 = len(g)
        add_discriminating_props(g)
        count2 = len(g)
        assert count1 == count2

    def test_turtle_roundtrip(self):
        g = self._graph()
        ttl = g.serialize(format="turtle")
        g2 = Graph()
        g2.parse(data=ttl, format="turtle")
        assert len(g2) == len(g)
