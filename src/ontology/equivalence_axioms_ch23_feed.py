"""Manually curated owl:equivalentClass axioms for Chapter 23 product classes.

All nine CN Chapter 23 main headings (2301-2309) are discriminated by a single
criterion: the class of the eucn:producedBy process individual.

eucn:producedBy is owl:FunctionalProperty — each feedstuff product has exactly
one producing process. The nine process classes are pairwise owl:disjointWith,
closing the open world for process-based discrimination.

No Phase 2 (negation) axioms are needed: every product class has a unique
positive someValuesFrom axiom on its process class.

DEPRECATION NOTICE
------------------
This module is superseded by the LLM axiom agent pipeline
(src/agent/axiom_builder.py + src/agent/candidate_registry.py).
Once agent output for Chapter 23 has been manually validated for quality and
consistency (run Konclude check), this module should be retired by calling::

    from src.scripts.retire_chapter import retire_chapter
    retire_chapter(23)

Do NOT retire before validation — this module remains the authoritative source
until the agent pipeline is confirmed correct for all Ch23 product classes.
"""
from __future__ import annotations

from rdflib import Graph

from src.ontology.namespaces import EUCN
from src.ontology.owl_helpers import _equiv, _some_values_class_restr


def add_equivalence_axioms_ch23_feed(graph: Graph) -> None:
    """Add curated owl:equivalentClass axioms for Ch23 product classes. Idempotent."""
    g = graph

    produced_by = EUCN.producedBy

    # CN 2301 — animal meal/pellets from rendering
    _equiv(
        g, EUCN.AnimalByProductMeal,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.AnimalMealRendering, "meal:proc"
            ),
        ],
        "meal",
    )

    # CN 2302 — bran and milling residues from cereals/legumes
    _equiv(
        g, EUCN.CerealMillingResidue,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.GrainMillingProcess, "bran:proc"
            ),
        ],
        "bran",
    )

    # CN 2303 — starch manufacture residues, beet-pulp, bagasse
    _equiv(
        g, EUCN.StarchManufactureResidue,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.StarchExtractionProcess, "starch:proc"
            ),
        ],
        "starch",
    )

    # CN 2304 — oilcake from soyabeans
    _equiv(
        g, EUCN.SoybeanOilcake,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.SoybeanOilExtraction, "soya:proc"
            ),
        ],
        "soya",
    )

    # CN 2305 — oilcake from groundnuts
    _equiv(
        g, EUCN.GroundnutOilcake,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.GroundnutOilExtraction, "groundnut:proc"
            ),
        ],
        "groundnut",
    )

    # CN 2306 — oilcake from other vegetable fats/oils
    _equiv(
        g, EUCN.VegetableOilcake,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.OtherOilseedExtraction, "vegoil:proc"
            ),
        ],
        "vegoil",
    )

    # CN 2307 — wine lees; argol
    _equiv(
        g, EUCN.WineLees,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.WineLeesByproduction, "lees:proc"
            ),
        ],
        "lees",
    )

    # CN 2308 — plant residues for animal feeding NESOI
    _equiv(
        g, EUCN.PlantResidue,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.PlantResidueCollection, "plantresidue:proc"
            ),
        ],
        "plantresidue",
    )

    # CN 2309 — preparations for animal feeding
    _equiv(
        g, EUCN.AnimalFeedPreparation,
        [
            _some_values_class_restr(
                g, produced_by, EUCN.AnimalFeedMixing, "feed:proc"
            ),
        ],
        "feed",
    )
