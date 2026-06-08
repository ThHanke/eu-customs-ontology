"""Unit tests for shared OWL builder helpers in src/ontology/owl_helpers.py."""
from __future__ import annotations

import itertools

import pytest
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from src.ontology.namespaces import EUCN
from src.ontology.owl_helpers import (
    _bnode,
    _build_list,
    _cls,
    _cn_heading,
    _decimal_range_restr,
    _disjoint_pairs,
    _dp,
    _equiv,
    _has_value_restr,
    _neg_hasvalue_from_disjoint_equiv,
    _op,
    _proc,
    _some_values_class_restr,
    _sub,
)

# ── _bnode ────────────────────────────────────────────────────────────────────

class TestBnode:
    def test_determinism_same_key(self):
        """Same key must always produce the same BNode identifier."""
        b1 = _bnode("test:key")
        b2 = _bnode("test:key")
        assert b1 == b2

    def test_different_keys_produce_different_bnodes(self):
        """Different keys must produce different BNode identifiers."""
        b1 = _bnode("key:alpha")
        b2 = _bnode("key:beta")
        assert b1 != b2


# ── _cls ──────────────────────────────────────────────────────────────────────

class TestCls:
    _IRI = URIRef("https://example.org/TestClass")

    def test_emits_exactly_5_triples(self):
        """_cls should emit exactly 5 triples on a fresh graph."""
        g = Graph()
        _cls(g, self._IRI, "label en", "label de", "def en", "def de")
        assert len(g) == 5

    def test_triples_are_correct_types(self):
        g = Graph()
        _cls(g, self._IRI, "label en", "label de", "def en", "def de")
        assert (self._IRI, RDF.type, OWL.Class) in g
        assert (self._IRI, RDFS.label, Literal("label en", lang="en")) in g
        assert (self._IRI, RDFS.label, Literal("label de", lang="de")) in g
        assert (self._IRI, SKOS.definition, Literal("def en", lang="en")) in g
        assert (self._IRI, SKOS.definition, Literal("def de", lang="de")) in g

    def test_idempotent(self):
        """Calling _cls twice on the same graph must not add extra triples."""
        g = Graph()
        _cls(g, self._IRI, "label en", "label de", "def en", "def de")
        count1 = len(g)
        _cls(g, self._IRI, "label en", "label de", "def en", "def de")
        count2 = len(g)
        assert count1 == count2


# ── _cn_heading ───────────────────────────────────────────────────────────────

class TestCnHeading:
    _CLS = URIRef("https://example.org/TestBeverage")
    _CODE = "2201"

    def _build(self) -> Graph:
        g = Graph()
        _cn_heading(g, self._CLS, self._CODE)
        return g

    def test_restriction_is_typed_owl_restriction(self):
        g = self._build()
        restrictions = list(g.subjects(RDF.type, OWL.Restriction))
        assert len(restrictions) == 1

    def test_restriction_on_cn_heading_code_property(self):
        g = self._build()
        r = list(g.subjects(RDF.type, OWL.Restriction))[0]
        assert (r, OWL.onProperty, EUCN.cnHeadingCode) in g

    def test_restriction_has_value_is_code_literal(self):
        g = self._build()
        r = list(g.subjects(RDF.type, OWL.Restriction))[0]
        assert (r, OWL.hasValue, Literal(self._CODE, datatype=XSD.string)) in g

    def test_cls_subclass_of_restriction(self):
        g = self._build()
        r = list(g.subjects(RDF.type, OWL.Restriction))[0]
        assert (self._CLS, RDFS.subClassOf, r) in g

    def test_idempotent(self):
        g = Graph()
        _cn_heading(g, self._CLS, self._CODE)
        count1 = len(g)
        _cn_heading(g, self._CLS, self._CODE)
        count2 = len(g)
        assert count1 == count2


# ── _disjoint_pairs ───────────────────────────────────────────────────────────

class TestDisjointPairs:
    def _make_classes(self, n: int) -> list[URIRef]:
        return [URIRef(f"https://example.org/C{i}") for i in range(n)]

    def test_n3_produces_6_triples(self):
        """3 classes → C(3,2)*2 = 6 triples (symmetric pairs)."""
        g = Graph()
        classes = self._make_classes(3)
        _disjoint_pairs(g, classes)
        disjoint_triples = list(g.triples((None, OWL.disjointWith, None)))
        assert len(disjoint_triples) == 6

    def test_n4_produces_12_triples(self):
        """4 classes → C(4,2)*2 = 12 triples."""
        g = Graph()
        classes = self._make_classes(4)
        _disjoint_pairs(g, classes)
        disjoint_triples = list(g.triples((None, OWL.disjointWith, None)))
        assert len(disjoint_triples) == 12

    def test_symmetric(self):
        """Both (a, disjointWith, b) and (b, disjointWith, a) must be present."""
        g = Graph()
        a, b = self._make_classes(2)
        _disjoint_pairs(g, [a, b])
        assert (a, OWL.disjointWith, b) in g
        assert (b, OWL.disjointWith, a) in g

    def test_idempotent(self):
        g = Graph()
        classes = self._make_classes(4)
        _disjoint_pairs(g, classes)
        count1 = len(g)
        _disjoint_pairs(g, classes)
        count2 = len(g)
        assert count1 == count2


# ── _neg_hasvalue_from_disjoint_equiv ────────────────────────────────────────

class TestNegHasvalueFromDisjointEquiv:
    def _build_sibling_graph(self) -> tuple[Graph, URIRef, URIRef]:
        """Build a minimal graph with two disjoint classes: target and sibling.

        The sibling has a someValuesFrom restriction on a named class (URIRef).
        """
        from src.ontology.owl_helpers import _equiv, _some_values_class_restr
        g = Graph()
        target = URIRef("https://example.org/Target")
        sibling = URIRef("https://example.org/Sibling")
        named_process = URIRef("https://example.org/SomeProcess")
        some_prop = URIRef("https://example.org/producedBy")

        g.add((target, OWL.disjointWith, sibling))
        g.add((sibling, OWL.disjointWith, target))

        # Give sibling an equivalentClass with a someValuesFrom named-class restriction
        restr = _some_values_class_restr(g, some_prop, named_process, "sib:proc")
        _equiv(g, sibling, [restr], "sib")

        return g, target, sibling

    def test_skips_bnode_somevalues_from_values(self):
        """BNode someValuesFrom values (datatype restrictions) must be skipped."""
        from src.ontology.owl_helpers import _decimal_range_restr, _equiv
        g = Graph()
        target = URIRef("https://example.org/Target")
        sibling = URIRef("https://example.org/Sibling")
        abv_prop = URIRef("https://example.org/abv")

        g.add((target, OWL.disjointWith, sibling))
        g.add((sibling, OWL.disjointWith, target))

        # Sibling has only a datatype restriction (BNode someValuesFrom)
        restr = _decimal_range_restr(g, abv_prop, XSD.maxInclusive, 0.0, "sib:abv")
        _equiv(g, sibling, [restr], "sib")

        result = _neg_hasvalue_from_disjoint_equiv(g, target, "target")
        assert result == [], (
            "BNode someValuesFrom values must be skipped; expected no complement BNodes"
        )

    def test_produces_complement_for_named_class_somevalues(self):
        """URIRef someValuesFrom values must produce complement BNodes."""
        g, target, sibling = self._build_sibling_graph()
        result = _neg_hasvalue_from_disjoint_equiv(g, target, "target")
        assert len(result) == 1

    def test_complement_bnode_typed_owl_class(self):
        """Each returned BNode must be typed owl:Class with a complementOf restriction."""
        g, target, sibling = self._build_sibling_graph()
        result = _neg_hasvalue_from_disjoint_equiv(g, target, "target")
        for outer in result:
            assert (outer, RDF.type, OWL.Class) in g
            inner_list = list(g.objects(outer, OWL.complementOf))
            assert inner_list, "Outer BNode must have owl:complementOf"
            assert (inner_list[0], RDF.type, OWL.Restriction) in g

    def test_idempotent(self):
        """Calling twice must not add extra triples or duplicate BNodes in result."""
        g, target, sibling = self._build_sibling_graph()
        result1 = _neg_hasvalue_from_disjoint_equiv(g, target, "target")
        count1 = len(g)
        result2 = _neg_hasvalue_from_disjoint_equiv(g, target, "target")
        count2 = len(g)
        assert count1 == count2
        assert result1 == result2


# ── Additional helpers idempotency ────────────────────────────────────────────

class TestHelpersIdempotent:
    def test_sub_idempotent(self):
        g = Graph()
        a = URIRef("https://example.org/A")
        b = URIRef("https://example.org/B")
        _sub(g, a, b)
        count1 = len(g)
        _sub(g, a, b)
        assert len(g) == count1

    def test_proc_idempotent(self):
        g = Graph()
        iri = URIRef("https://example.org/SomeProcess")
        _proc(g, iri, "label en", "label de", "def en", "def de")
        count1 = len(g)
        _proc(g, iri, "label en", "label de", "def en", "def de")
        assert len(g) == count1

    def test_dp_idempotent(self):
        g = Graph()
        iri = URIRef("https://example.org/someDataProp")
        _dp(g, iri, "label en", "label de", "def en", "def de", XSD.decimal)
        count1 = len(g)
        _dp(g, iri, "label en", "label de", "def en", "def de", XSD.decimal)
        assert len(g) == count1

    def test_op_idempotent(self):
        g = Graph()
        iri = URIRef("https://example.org/someObjectProp")
        range_iri = URIRef("https://example.org/SomeClass")
        _op(g, iri, "label en", "label de", "def en", "def de", range_iri)
        count1 = len(g)
        _op(g, iri, "label en", "label de", "def en", "def de", range_iri)
        assert len(g) == count1

    def test_some_values_class_restr_idempotent(self):
        g = Graph()
        prop = URIRef("https://example.org/p")
        cls = URIRef("https://example.org/C")
        _some_values_class_restr(g, prop, cls, "key1")
        count1 = len(g)
        _some_values_class_restr(g, prop, cls, "key1")
        assert len(g) == count1

    def test_has_value_restr_idempotent(self):
        g = Graph()
        prop = URIRef("https://example.org/p")
        val = Literal(True, datatype=XSD.boolean)
        _has_value_restr(g, prop, val, "hvkey")
        count1 = len(g)
        _has_value_restr(g, prop, val, "hvkey")
        assert len(g) == count1

    def test_decimal_range_restr_idempotent(self):
        g = Graph()
        prop = URIRef("https://example.org/abv")
        _decimal_range_restr(g, prop, XSD.minExclusive, 0.5, "abv:min")
        count1 = len(g)
        _decimal_range_restr(g, prop, XSD.minExclusive, 0.5, "abv:min")
        assert len(g) == count1

    def test_equiv_idempotent(self):
        g = Graph()
        cls = URIRef("https://example.org/MyClass")
        prop = URIRef("https://example.org/p")
        restr = _some_values_class_restr(g, prop, URIRef("https://example.org/C"), "k")
        _equiv(g, cls, [restr], "mykey")
        count1 = len(g)
        _equiv(g, cls, [restr], "mykey")
        assert len(g) == count1
