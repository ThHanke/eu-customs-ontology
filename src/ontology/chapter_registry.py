"""Chapter registry: maps CN chapter numbers to hand-authored ontology modules.

DEPRECATION NOTICE
------------------
The hand-authored modules registered here (Ch22, Ch23) are superseded by the
LLM axiom agent pipeline (src/agent/axiom_builder.py).  Once agent output for
a chapter has been manually validated and a Konclude consistency check passes,
run ``scripts/retire_chapter.py <N>`` to convert the module functions to
no-op stubs and set ``add_equivalence_axioms=None`` here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from rdflib import Graph, URIRef

from src.ontology.namespaces import EUCN
from src.ontology.discriminating_props_beverages import add_discriminating_props_beverages
from src.ontology.product_classes_beverages import add_product_classes_beverages
from src.ontology.process_classes_beverages import add_process_classes_beverages
from src.ontology.equivalence_axioms_beverages import add_equivalence_axioms_beverages

from src.ontology.discriminating_props_ch23_feed import add_discriminating_props_ch23_feed
from src.ontology.product_classes_ch23_feed import add_product_classes_ch23_feed
from src.ontology.process_classes_ch23_feed import add_process_classes_ch23_feed
from src.ontology.equivalence_axioms_ch23_feed import add_equivalence_axioms_ch23_feed


@dataclass
class ChapterModule:
    label: str          # human name, e.g. "Beverages, spirits and vinegar"
    slug: str           # kebab-case, e.g. "beverages"
    add_discriminating_props: Callable[[Graph], None]
    add_product_classes: Callable[[Graph], None]
    add_process_classes: Callable[[Graph], None]
    add_equivalence_axioms: Callable[[Graph], None] | None = None
    root_class_iri: URIRef | None = None


CHAPTERS: dict[int, ChapterModule] = {
    22: ChapterModule(
        label="Beverages, spirits and vinegar",
        slug="beverages",
        add_discriminating_props=add_discriminating_props_beverages,
        add_product_classes=add_product_classes_beverages,
        add_process_classes=add_process_classes_beverages,
        add_equivalence_axioms=None,  # retired 2026-06-08
        root_class_iri=EUCN.Beverage,
    ),
    23: ChapterModule(
        label="Residues and waste from the food industries; prepared animal fodder",
        slug="residues-feed",
        add_discriminating_props=add_discriminating_props_ch23_feed,
        add_product_classes=add_product_classes_ch23_feed,
        add_process_classes=add_process_classes_ch23_feed,
        add_equivalence_axioms=add_equivalence_axioms_ch23_feed,
    ),
}


def get_chapter(n: int) -> ChapterModule:
    if n not in CHAPTERS:
        raise ValueError(f"Chapter {n} not yet implemented. Add a module and register it.")
    return CHAPTERS[n]
