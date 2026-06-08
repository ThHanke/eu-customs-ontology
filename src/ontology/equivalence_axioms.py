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
    """Add curated owl:equivalentClass axioms for Ch22 product classes. Idempotent."""
    g = graph

    abv = EUCN.alcoholByVolumePercent
    carb = EUCN.isCarbonated
    denature = EUCN.isDenatured
    vol = EUCN.maxContainerVolumeL
    ferm = EUCN.fermentationBase

    # ── eucn:Water (CN 2201) ──────────────────────────────────────────────────
    # Water = Beverage with ABV ≤ 0 (no measurable alcohol) and not fermented
    _equiv(
        g, EUCN.Water,
        [
            _decimal_range_restr(
                g, abv, XSD.maxInclusive, 0.0, "water:abv"
            ),
        ],
        "water",
    )

    # ── eucn:NonAlcoholicBeverage (CN 2202) ────────────────────────────────────
    # NonAlcoholicBeverage = Beverage with fermentationBase "sweetened-water"
    # (sweetened/flavoured water, distinct from pure Water CN 2201)
    _equiv(
        g, EUCN.NonAlcoholicBeverage,
        [
            _has_value_restr(
                g, ferm, Literal("sweetened-water", datatype=XSD.string), "nonalco:ferm"
            ),
        ],
        "nonalco",
    )

    # ── eucn:Beer (CN 2203) ────────────────────────────────────────────────────
    # Beer = Beverage with fermentationBase "malt" and ABV > 0.5%
    _equiv(
        g, EUCN.Beer,
        [
            _has_value_restr(
                g, ferm, Literal("malt", datatype=XSD.string), "beer:ferm"
            ),
            _decimal_range_restr(
                g, abv, XSD.minExclusive, 0.5, "beer:abv"
            ),
        ],
        "beer",
    )

    # ── eucn:Wine (CN 2204) ────────────────────────────────────────────────────
    # Wine = Beverage with fermentationBase "grape"
    _equiv(
        g, EUCN.Wine,
        [
            _has_value_restr(
                g, ferm, Literal("grape", datatype=XSD.string), "wine:ferm"
            ),
        ],
        "wine",
    )

    # ── eucn:SparklingWine (CN 2204 10) ────────────────────────────────────────
    # SparklingWine = Wine and isCarbonated true
    _equiv(
        g, EUCN.SparklingWine,
        [
            _has_value_restr(
                g, ferm, Literal("grape", datatype=XSD.string), "sparkling:ferm"
            ),
            _has_value_restr(
                g, carb, Literal(True, datatype=XSD.boolean), "sparkling:carb"
            ),
        ],
        "sparkling",
    )

    # ── eucn:StillWine (CN 2204 21/29) ────────────────────────────────────────
    # StillWine = Wine and isCarbonated false
    _equiv(
        g, EUCN.StillWine,
        [
            _has_value_restr(
                g, ferm, Literal("grape", datatype=XSD.string), "still:ferm"
            ),
            _has_value_restr(
                g, carb, Literal(False, datatype=XSD.boolean), "still:carb"
            ),
        ],
        "stillwine",
    )

    # ── eucn:FlavouredWine (CN 2205) ──────────────────────────────────────────
    # FlavouredWine = Beverage with fermentationBase "grape-flavoured"
    # (distinct string distinguishes from plain grape Wine)
    _equiv(
        g, EUCN.FlavouredWine,
        [
            _has_value_restr(
                g, ferm, Literal("grape-flavoured", datatype=XSD.string), "flavoured:ferm"
            ),
        ],
        "flavoured",
    )

    # ── eucn:FermentedBeverage (CN 2206) ──────────────────────────────────────
    # FermentedBeverage = Beverage with fermentationBase "fruit"
    _equiv(
        g, EUCN.FermentedBeverage,
        [
            _has_value_restr(
                g, ferm, Literal("fruit", datatype=XSD.string), "fermented:ferm"
            ),
        ],
        "fermented",
    )

    # ── eucn:EthylAlcohol (CN 2207) ───────────────────────────────────────────
    # EthylAlcohol = Beverage with ABV >= 80%
    _equiv(
        g, EUCN.EthylAlcohol,
        [
            _decimal_range_restr(
                g, abv, XSD.minInclusive, 80.0, "ethyl:abv"
            ),
        ],
        "ethyl",
    )

    # ── eucn:Spirit (CN 2208) ─────────────────────────────────────────────────
    # Spirit = Beverage with ABV < 80% (and > 0.5%, so not non-alcoholic)
    _equiv(
        g, EUCN.Spirit,
        [
            _decimal_range_restr(
                g, abv, XSD.minExclusive, 0.5, "spirit:abv_min"
            ),
            _decimal_range_restr(
                g, abv, XSD.maxExclusive, 80.0, "spirit:abv_max"
            ),
        ],
        "spirit",
    )

    # ── eucn:Vinegar (CN 2209) ────────────────────────────────────────────────
    # Vinegar = Beverage with fermentationBase "acetic"
    _equiv(
        g, EUCN.Vinegar,
        [
            _has_value_restr(
                g, ferm, Literal("acetic", datatype=XSD.string), "vinegar:ferm"
            ),
        ],
        "vinegar",
    )
