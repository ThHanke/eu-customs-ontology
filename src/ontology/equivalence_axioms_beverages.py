"""Manually curated owl:equivalentClass axioms for Chapter 22 product classes.

Encodes the discriminating physical criteria for each CN heading/subheading
using the canonical data properties from discriminating_props_beverages.py.

OWL 2 DL: no punning issues — named product classes (eucn:Beer etc.) are the
subjects of owl:equivalentClass. BNode intersection class is the object.
"""
from __future__ import annotations

from rdflib import Graph, Literal
from rdflib.namespace import XSD

from src.ontology.namespaces import EUCN
from src.ontology.owl_helpers import (
    _bnode,
    _build_list,
    _decimal_range_restr,
    _equiv,
    _has_value_restr,
    _neg_hasvalue_from_disjoint_equiv,
    _some_values_class_restr,
)


def add_equivalence_axioms_beverages(graph: Graph) -> None:
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
