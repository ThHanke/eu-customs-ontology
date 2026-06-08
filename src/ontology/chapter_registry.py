from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from rdflib import Graph

from src.ontology.discriminating_props_beverages import add_discriminating_props_beverages
from src.ontology.product_classes_beverages import add_product_classes_beverages
from src.ontology.process_classes_beverages import add_process_classes_beverages
from src.ontology.equivalence_axioms_beverages import add_equivalence_axioms_beverages


@dataclass
class ChapterModule:
    label: str          # human name, e.g. "Beverages, spirits and vinegar"
    slug: str           # kebab-case, e.g. "beverages"
    add_discriminating_props: Callable[[Graph], None]
    add_product_classes: Callable[[Graph], None]
    add_process_classes: Callable[[Graph], None]
    add_equivalence_axioms: Callable[[Graph], None]


CHAPTERS: dict[int, ChapterModule] = {
    22: ChapterModule(
        label="Beverages, spirits and vinegar",
        slug="beverages",
        add_discriminating_props=add_discriminating_props_beverages,
        add_product_classes=add_product_classes_beverages,
        add_process_classes=add_process_classes_beverages,
        add_equivalence_axioms=add_equivalence_axioms_beverages,
    ),
}


def get_chapter(n: int) -> ChapterModule:
    if n not in CHAPTERS:
        raise ValueError(f"Chapter {n} not yet implemented. Add a module and register it.")
    return CHAPTERS[n]
