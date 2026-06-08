from rdflib import Graph

from src.ontology.discriminating_props_ch23_feed import add_discriminating_props_ch23_feed


class TestDiscriminatingPropsCh23Feed:
    def _graph(self) -> Graph:
        g = Graph()
        add_discriminating_props_ch23_feed(g)
        return g

    def test_no_op_adds_no_triples(self):
        g = self._graph()
        assert len(g) == 0

    def test_idempotent(self):
        g = Graph()
        add_discriminating_props_ch23_feed(g)
        add_discriminating_props_ch23_feed(g)
        assert len(g) == 0
