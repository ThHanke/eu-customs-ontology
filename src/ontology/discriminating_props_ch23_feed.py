"""Discriminating data properties for CN Chapter 23 (Residues, Waste, Animal Feed).

Classification of Ch23 products is driven entirely by eucn:producedBy (declared in
core.py). The source process class (AnimalMealRendering, GrainMillingProcess, etc.)
uniquely identifies the CN heading — no additional data properties are required for
main-heading (2301-2309) discrimination.

This module is intentionally empty for the initial implementation. Additional
properties (e.g. eucn:crudeProteinPercent, eucn:isForRetailPets) can be added here
when sub-heading (8-digit) classification within 2306 or 2309 is implemented.
"""
from __future__ import annotations

from rdflib import Graph


def add_discriminating_props_ch23_feed(graph: Graph) -> None:
    """Declare Ch23 discriminating data properties. Idempotent.

    Currently a no-op: eucn:producedBy (core.py) is the sole discriminating
    property for all nine CN Chapter 23 main headings (2301-2309).
    """
