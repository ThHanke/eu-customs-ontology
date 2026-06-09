"""Unit tests for add_heading_classes — IU1: chapter root IRI wiring."""
from __future__ import annotations

from rdflib import Graph
from rdflib.namespace import RDFS

from src.ontology.heading_classes import add_heading_classes
from src.ontology.namespaces import BFO_OBJECT, EUCN

LABELS: dict[str, dict[str, str]] = {
    "2204": {"en": "Wine of fresh grapes", "de": "Wein aus frischen Weintrauben"},
    "2205": {"en": "Vermouth", "de": "Wermutwein"},
}


EUCN_BASE = "https://w3id.org/eucn/"


def _heading_iris(g: Graph) -> list:
    """Return (heading_iri, parent_iri) pairs for eucn: 4-digit heading classes only."""
    results = []
    for s, _, o in g.triples((None, RDFS.subClassOf, None)):
        s_str = str(s)
        if not s_str.startswith(EUCN_BASE):
            continue
        local = s_str[len(EUCN_BASE):]
        # Heading classes end with exactly 4 digits (the CN code)
        if local[-4:].isdigit() and len(local) > 4:
            results.append((s, o))
    return results


class TestAddHeadingClassesWithChapterRootIri:
    """Happy path: chapter_root_iri supplied — headings subclass it."""

    def test_heading_subclasses_eucn_beverage(self):
        g = Graph()
        add_heading_classes(g, 22, LABELS, chapter_root_iri=EUCN.Beverage)
        pairs = _heading_iris(g)
        assert len(pairs) == 2, f"Expected 2 heading subClassOf triples, got {pairs}"
        for iri, parent in pairs:
            assert parent == EUCN.Beverage, (
                f"{iri} has parent {parent!r}, expected eucn:Beverage"
            )

    def test_bfo_object_not_used_when_root_iri_given(self):
        g = Graph()
        add_heading_classes(g, 22, LABELS, chapter_root_iri=EUCN.Beverage)
        bfo_parents = [
            (s, o)
            for s, _, o in g.triples((None, RDFS.subClassOf, BFO_OBJECT))
        ]
        assert bfo_parents == [], (
            f"Found unexpected BFO_OBJECT parents: {bfo_parents}"
        )


class TestAddHeadingClassesBackwardCompat:
    """Backward compat: no chapter_root_iri — headings fall back to BFO_OBJECT."""

    def test_heading_subclasses_bfo_object_by_default(self):
        g = Graph()
        add_heading_classes(g, 22, LABELS)
        pairs = _heading_iris(g)
        assert len(pairs) == 2, f"Expected 2 heading subClassOf triples, got {pairs}"
        for iri, parent in pairs:
            assert parent == BFO_OBJECT, (
                f"{iri} has parent {parent!r}, expected BFO_OBJECT"
            )

    def test_explicit_none_also_uses_bfo_object(self):
        g = Graph()
        add_heading_classes(g, 22, LABELS, chapter_root_iri=None)
        for _, _, o in g.triples((None, RDFS.subClassOf, None)):
            local = str(o).split("/")[-1]
            if "Beverage" in local:
                raise AssertionError("eucn:Beverage found when chapter_root_iri=None")


class TestBuildTboxIntegration:
    """Integration: build_tbox for chapter 22 uses eucn:Beverage as heading parent."""

    def test_build_tbox_ch22_headings_subclass_beverage(self):
        from src.ontology.tbox import build_tbox

        g = Graph()
        build_tbox(g, chapter=22, heading_labels=LABELS)
        pairs = _heading_iris(g)
        assert len(pairs) == 2, f"Expected 2 heading subClassOf triples, got {pairs}"
        for iri, parent in pairs:
            assert parent == EUCN.Beverage, (
                f"{iri} has parent {parent!r}; expected eucn:Beverage after build_tbox ch22"
            )
