"""Manually curated owl:equivalentClass axioms for Chapter 22 product classes.

Encodes the discriminating physical criteria for each CN heading/subheading
using the canonical data properties from discriminating_props.py.

OWL 2 DL: no punning issues — named product classes (eucn:Beer etc.) are the
subjects of owl:equivalentClass. BNode intersection class is the object.
"""
from __future__ import annotations

import hashlib

from rdflib import BNode, Graph, Literal
from rdflib.namespace import OWL, RDF, RDFS, XSD

from src.ontology.namespaces import EUCN


def _bnode(key: str) -> BNode:
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return BNode(h)


def _build_list(g: Graph, items: list[BNode], key: str) -> BNode:
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


def add_ch22_equivalence_axioms(graph: Graph) -> None:
    """Add curated owl:equivalentClass axioms for Ch22 product classes. Idempotent.

    Two-phase structure:
      Phase 1 — unconditional axioms (someValuesFrom NamedClass / someValuesFrom DataRange).
      Phase 2 — axioms that derive NOT(producedBy someValuesFrom C) complements from
                sibling equivalentClass axioms already set in Phase 1; runs after Phase 1.

    World-closure: eucn:producedBy is owl:FunctionalProperty + process classes are
    pairwise owl:disjointWith. Together these let Konclude infer ¬(∃producedBy.C) for
    each sibling process class when the individual's unique producedBy value is typed
    as a disjoint class.
    """
    g = graph

    abv = EUCN.alcoholByVolumePercent
    carb = EUCN.isCarbonated
    produced_by = EUCN.producedBy

    # ── Phase 1: unconditional axioms ─────────────────────────────────────────

    # eucn:Water (CN 2201) — ABV ≤ 0 (no measurable alcohol)
    _equiv(
        g, EUCN.Water,
        [
            _decimal_range_restr(g, abv, XSD.maxInclusive, 0.0, "water:abv"),
        ],
        "water",
    )

    # eucn:NonAlcoholicBeverage (CN 2202) — sweetened/flavoured water process
    _equiv(
        g, EUCN.NonAlcoholicBeverage,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.SweetenedWaterProcess, "nonalco:proc"
            ),
        ],
        "nonalco",
    )

    # eucn:Beer (CN 2203) — malt fermentation, ABV > 0.5%
    _equiv(
        g, EUCN.Beer,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.MaltFermentation, "beer:proc"
            ),
            _decimal_range_restr(g, abv, XSD.minExclusive, 0.5, "beer:abv"),
        ],
        "beer",
    )

    # eucn:Wine (CN 2204) — grape fermentation
    _equiv(
        g, EUCN.Wine,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.GrapeFermentation, "wine:proc"
            ),
        ],
        "wine",
    )

    # eucn:SparklingWine (CN 2204 10) — grape fermentation + carbonated
    _equiv(
        g, EUCN.SparklingWine,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.GrapeFermentation, "sparkling:proc"
            ),
            _has_value_restr(
                g, carb, Literal(True, datatype=XSD.boolean), "sparkling:carb"
            ),
        ],
        "sparkling",
    )

    # eucn:StillWine (CN 2204 21/29) — grape fermentation + not carbonated
    _equiv(
        g, EUCN.StillWine,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.GrapeFermentation, "stillwine:proc"
            ),
            _has_value_restr(
                g, carb, Literal(False, datatype=XSD.boolean), "stillwine:carb"
            ),
        ],
        "stillwine",
    )

    # eucn:FlavouredWine (CN 2205) — grape flavouring process
    _equiv(
        g, EUCN.FlavouredWine,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.GrapeFlavouringProcess, "flavoured:proc"
            ),
        ],
        "flavoured",
    )

    # eucn:FermentedBeverage (CN 2206) — fruit fermentation
    _equiv(
        g, EUCN.FermentedBeverage,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.FruitFermentation, "fermented:proc"
            ),
        ],
        "fermented",
    )

    # eucn:Vinegar (CN 2209) — acetic fermentation
    _equiv(
        g, EUCN.Vinegar,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.AceticFermentation, "vinegar:proc"
            ),
        ],
        "vinegar",
    )

    # ── Phase 2: axioms derived from sibling equivalentClass conditions ────────

    # eucn:EthylAlcohol (CN 2207) — ABV >= 80% + NOT(producedBy someValuesFrom C) for each sibling
    _equiv(
        g, EUCN.EthylAlcohol,
        [
            _decimal_range_restr(g, abv, XSD.minInclusive, 80.0, "ethyl:abv"),
            *_neg_hasvalue_from_disjoint_equiv(g, EUCN.EthylAlcohol, "ethyl"),
        ],
        "ethyl",
    )

    # eucn:Spirit (CN 2208) — 0.5% < ABV < 80% + NOT(producedBy someValuesFrom C) for each sibling
    _equiv(
        g, EUCN.Spirit,
        [
            _decimal_range_restr(g, abv, XSD.minExclusive, 0.5, "spirit:abv_min"),
            _decimal_range_restr(g, abv, XSD.maxExclusive, 80.0, "spirit:abv_max"),
            *_neg_hasvalue_from_disjoint_equiv(g, EUCN.Spirit, "spirit"),
        ],
        "spirit",
    )
