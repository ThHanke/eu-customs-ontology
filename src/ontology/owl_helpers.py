"""Shared OWL builder helper functions for all chapter ontology modules.

Provides deterministic, idempotent primitives for constructing OWL TBox
triples (classes, properties, restrictions, equivalence axioms). These
helpers are consumed by product_classes.py, process_classes_ch22.py,
equivalence_axioms.py, and discriminating_props.py — and by any future
chapter-specific modules that follow the same pattern.

All functions are idempotent: calling them twice on the same graph
produces no extra triples (rdflib.Graph.add is a set operation).
"""
from __future__ import annotations

import hashlib
import itertools

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from src.ontology.namespaces import BFO_PROCESS, EUCN


# ── Deterministic BNode ───────────────────────────────────────────────────────

def _bnode(key: str) -> BNode:
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return BNode(h)


# ── Class / property declarations ─────────────────────────────────────────────

def _cls(g: Graph, iri: URIRef, label_en: str, label_de: str,
         def_en: str, def_de: str) -> None:
    """Declare an OWL class with bilingual rdfs:label and skos:definition (5 triples)."""
    g.add((iri, RDF.type, OWL.Class))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    g.add((iri, RDFS.label, Literal(label_de, lang="de")))
    g.add((iri, SKOS.definition, Literal(def_en, lang="en")))
    g.add((iri, SKOS.definition, Literal(def_de, lang="de")))


def _proc(g: Graph, iri: URIRef, label_en: str, label_de: str,
          def_en: str, def_de: str) -> None:
    """Declare a bfo:Process subclass with bilingual labels and definitions."""
    g.add((iri, RDF.type, OWL.Class))
    g.add((iri, RDFS.subClassOf, BFO_PROCESS))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    g.add((iri, RDFS.label, Literal(label_de, lang="de")))
    g.add((iri, SKOS.definition, Literal(def_en, lang="en")))
    g.add((iri, SKOS.definition, Literal(def_de, lang="de")))


def _dp(g: Graph, iri, label_en: str, label_de: str,
        def_en: str, def_de: str, range_) -> None:
    """Declare an owl:DatatypeProperty with bilingual annotations and rdfs:range."""
    g.add((iri, RDF.type, OWL.DatatypeProperty))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    g.add((iri, RDFS.label, Literal(label_de, lang="de")))
    g.add((iri, SKOS.definition, Literal(def_en, lang="en")))
    g.add((iri, SKOS.definition, Literal(def_de, lang="de")))
    g.add((iri, RDFS.range, range_))


def _op(g: Graph, iri, label_en: str, label_de: str,
        def_en: str, def_de: str, range_=None) -> None:
    """Declare an owl:ObjectProperty with bilingual annotations and optional rdfs:range."""
    g.add((iri, RDF.type, OWL.ObjectProperty))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    g.add((iri, RDFS.label, Literal(label_de, lang="de")))
    g.add((iri, SKOS.definition, Literal(def_en, lang="en")))
    g.add((iri, SKOS.definition, Literal(def_de, lang="de")))
    if range_ is not None:
        g.add((iri, RDFS.range, range_))


# ── Hierarchy helpers ─────────────────────────────────────────────────────────

def _sub(g: Graph, child: URIRef, parent: URIRef) -> None:
    """Assert rdfs:subClassOf."""
    g.add((child, RDFS.subClassOf, parent))


def _cn_heading(g: Graph, cls_iri: URIRef, code: str) -> None:
    """Add rdfs:subClassOf [hasValue code] so the reasoner propagates the CN code."""
    r = _bnode(f"cn:heading:{code}")
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, EUCN.cnHeadingCode))
    g.add((r, OWL.hasValue, Literal(code, datatype=XSD.string)))
    g.add((cls_iri, RDFS.subClassOf, r))


def _disjoint_pairs(g: Graph, classes: list[URIRef]) -> None:
    """Assert pairwise owl:disjointWith for all pairs in classes (symmetric)."""
    for a, b in itertools.combinations(classes, 2):
        g.add((a, OWL.disjointWith, b))
        g.add((b, OWL.disjointWith, a))


# ── Equivalence axiom helpers ─────────────────────────────────────────────────

def _build_list(g: Graph, items: list[BNode], key: str) -> BNode:
    """Build an RDF list of BNodes using deterministic node identifiers."""
    if not items:
        return RDF.nil  # type: ignore[return-value]
    head = _bnode(f"list:{key}")
    current = head
    for i, item in enumerate(items):
        rest = _bnode(f"list:{key}:rest:{i}") if i < len(items) - 1 else RDF.nil
        g.add((current, RDF.first, item))
        g.add((current, RDF.rest, rest))
        if i < len(items) - 1:
            current = rest
    return head


def _neg_hasvalue_from_disjoint_equiv(g: Graph, cls_iri, key: str) -> list[BNode]:
    """Return NOT(producedBy someValuesFrom C) BNodes derived from disjoint siblings.

    Walks each disjoint sibling's equivalentClass intersectionOf list, finds
    owl:Restriction someValuesFrom members whose value is a named class (URIRef,
    not a datatype BNode), and emits owl:complementOf [Restriction someValuesFrom C]
    for each.

    Deterministic: siblings and values are sorted by IRI string.
    """
    exclusions: list[BNode] = []
    for j, sibling in enumerate(sorted(g.objects(cls_iri, OWL.disjointWith), key=str)):
        for inter in g.objects(sibling, OWL.equivalentClass):
            lst = list(g.objects(inter, OWL.intersectionOf))
            if not lst:
                continue
            node = lst[0]
            while node != RDF.nil:
                first = list(g.objects(node, RDF.first))
                if first:
                    member = first[0]
                    if ((member, RDF.type, OWL.Restriction) in g
                            and (member, OWL.someValuesFrom, None) in g):
                        for prop in sorted(g.objects(member, OWL.onProperty), key=str):
                            for val in sorted(g.objects(member, OWL.someValuesFrom), key=str):
                                # Skip datatype restrictions (BNode = anonymous datatype)
                                if isinstance(val, BNode):
                                    continue
                                neg_key = f"{key}:neg:{j}:{str(prop)}:{str(val)}"
                                inner = _bnode(f"r:sv_cls:{neg_key}")
                                g.add((inner, RDF.type, OWL.Restriction))
                                g.add((inner, OWL.onProperty, prop))
                                g.add((inner, OWL.someValuesFrom, val))
                                outer = _bnode(f"r:compl:{neg_key}")
                                g.add((outer, RDF.type, OWL.Class))
                                g.add((outer, OWL.complementOf, inner))
                                if outer not in exclusions:
                                    exclusions.append(outer)
                rest = list(g.objects(node, RDF.rest))
                node = rest[0] if rest else RDF.nil
    return exclusions


def _some_values_class_restr(g: Graph, prop, class_iri, key: str) -> BNode:
    """owl:someValuesFrom <NamedClass> — links process type to product class."""
    r = _bnode(f"r:sv_cls:{key}")
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, prop))
    g.add((r, OWL.someValuesFrom, class_iri))
    return r


def _has_value_restr(g: Graph, prop, value, key: str) -> BNode:
    """owl:hasValue restriction on a property."""
    r = _bnode(f"r:hv:{key}")
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, prop))
    g.add((r, OWL.hasValue, value))
    return r


def _decimal_range_restr(g: Graph, prop, facet_iri, threshold: float, key: str) -> BNode:
    """owl:someValuesFrom [rdfs:Datatype xsd:decimal facet threshold]"""
    facet_b = _bnode(f"facet:{key}")
    g.add((facet_b, facet_iri, Literal(str(threshold), datatype=XSD.decimal)))

    dtype = _bnode(f"dtype:{key}")
    g.add((dtype, RDF.type, RDFS.Datatype))
    g.add((dtype, OWL.onDatatype, XSD.decimal))
    fl = _build_list(g, [facet_b], f"fl:{key}")
    g.add((dtype, OWL.withRestrictions, fl))

    r = _bnode(f"r:sv:{key}")
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, prop))
    g.add((r, OWL.someValuesFrom, dtype))
    return r


def _equiv(g: Graph, cls_iri, parts: list[BNode], key: str) -> None:
    """Assert cls_iri owl:equivalentClass [intersectionOf parts]."""
    inter = _bnode(f"inter:{key}")
    g.add((inter, RDF.type, OWL.Class))
    lst = _build_list(g, parts, f"lst:{key}")
    g.add((inter, OWL.intersectionOf, lst))
    g.add((cls_iri, OWL.equivalentClass, inter))
