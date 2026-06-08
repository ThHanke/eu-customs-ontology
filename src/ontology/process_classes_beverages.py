"""Named BFO Process subclasses for CN Chapter 22 beverages.

Process classes are pairwise owl:disjointWith — the load-bearing world-closure
mechanism: eucn:producedBy is owl:FunctionalProperty, so if the unique producedBy
value is typed as (e.g.) MaltFermentation, Konclude can infer
NOT(producedBy someValuesFrom GrapeFermentation) via class disjointness.

DEPRECATION NOTICE
------------------
This module is superseded by the LLM axiom agent pipeline
(src/agent/axiom_builder.py + src/agent/candidate_registry.py).
Once agent output for Chapter 22 has been manually validated, retire via::

    from src.scripts.retire_chapter import retire_chapter
    retire_chapter(22)

Do NOT retire before validation — the TBox process class vocabulary defined
here is required for correct OWL reasoning until the agent pipeline is
confirmed correct for all Ch22 process classes.
"""
from __future__ import annotations

from rdflib import Graph

from src.ontology.namespaces import EUCN
from src.ontology.owl_helpers import _disjoint_pairs, _proc


def add_process_classes_beverages(graph: Graph) -> None:
    """Declare Ch22 process class vocabulary. Idempotent."""
    g = graph

    # ── Process classes ───────────────────────────────────────────────────────
    _proc(
        g, EUCN.MaltFermentation,
        "malt fermentation", "Malzfermentation",
        "process of fermenting malted barley or other cereals to produce beer; "
        "each individual represents the unique malt-fermentation process type in the "
        "CN Chapter 22 classification",
        "Prozess der Vergärung von Gerstenmalz oder anderen Getreidearten zur Herstellung "
        "von Bier; jedes Individuum repräsentiert den einzigartigen "
        "Malzfermentationsprozesstyp in der KN-Kapitel-22-Einreihung",
    )

    _proc(
        g, EUCN.GrapeFermentation,
        "grape fermentation", "Traubenfermentation",
        "process of fermenting fresh grapes or grape must to produce wine; "
        "each individual represents the unique grape-fermentation process type in the "
        "CN Chapter 22 classification",
        "Prozess der Vergärung von frischen Weintrauben oder Traubenmost zur Herstellung "
        "von Wein; jedes Individuum repräsentiert den einzigartigen "
        "Traubenfermentationsprozesstyp in der KN-Kapitel-22-Einreihung",
    )

    _proc(
        g, EUCN.GrapeFlavouringProcess,
        "grape flavouring process", "Traubenaromatisierungsprozess",
        "process of flavouring grape-based wine with plants or aromatic substances to "
        "produce vermouth or other flavoured wines; each individual represents the unique "
        "grape-flavouring process type in the CN Chapter 22 classification",
        "Prozess der Aromatisierung von traubenbasiertem Wein mit Pflanzen oder aromatischen "
        "Stoffen zur Herstellung von Wermutein oder anderen aromatisierten Weinen; "
        "jedes Individuum repräsentiert den einzigartigen "
        "Traubenaromatisierungsprozesstyp in der KN-Kapitel-22-Einreihung",
    )

    _proc(
        g, EUCN.FruitFermentation,
        "fruit fermentation", "Fruchtfermentation",
        "process of fermenting fruit (other than grapes) to produce cider, perry, or other "
        "fermented beverages; each individual represents the unique fruit-fermentation process "
        "type in the CN Chapter 22 classification",
        "Prozess der Vergärung von Früchten (außer Weintrauben) zur Herstellung von Apfelwein, "
        "Birnenwein oder anderen Gärerzeugnissen; jedes Individuum repräsentiert den "
        "einzigartigen Fruchtfermentationsprozesstyp in der KN-Kapitel-22-Einreihung",
    )

    _proc(
        g, EUCN.GrainDistillation,
        "grain distillation", "Getreidebrennerei",
        "process of distilling fermented grain mash to produce spirits or high-strength ethyl "
        "alcohol; each individual represents the unique grain-distillation process type in the "
        "CN Chapter 22 classification",
        "Prozess der Destillation von vergorenem Getreidebrei zur Herstellung von Spirituosen "
        "oder hochprozentigem Ethylalkohol; jedes Individuum repräsentiert den einzigartigen "
        "Getreidedestillationsprozesstyp in der KN-Kapitel-22-Einreihung",
    )

    _proc(
        g, EUCN.AceticFermentation,
        "acetic fermentation", "Essigsäuregärung",
        "process of acetic acid fermentation of ethyl alcohol to produce vinegar; "
        "each individual represents the unique acetic-fermentation process type in the "
        "CN Chapter 22 classification",
        "Prozess der Essigsäuregärung von Ethylalkohol zur Herstellung von Essig; "
        "jedes Individuum repräsentiert den einzigartigen "
        "Essigsäuregärungsprozesstyp in der KN-Kapitel-22-Einreihung",
    )

    _proc(
        g, EUCN.SweetenedWaterProcess,
        "sweetened water process", "Süßwasserprozess",
        "process of producing sweetened or flavoured non-alcoholic beverages by adding sugar "
        "or flavouring to water; each individual represents the unique sweetened-water-process "
        "type in the CN Chapter 22 classification",
        "Prozess zur Herstellung von gesüßten oder aromatisierten nichtalkoholischen Getränken "
        "durch Zugabe von Zucker oder Aromen zu Wasser; jedes Individuum repräsentiert den "
        "einzigartigen Süßwasserprozesstyp in der KN-Kapitel-22-Einreihung",
    )

    # ── Pairwise owl:disjointWith (world-closure for producedBy FunctionalProperty) ──
    _disjoint_pairs(g, [
        EUCN.MaltFermentation,
        EUCN.GrapeFermentation,
        EUCN.GrapeFlavouringProcess,
        EUCN.FruitFermentation,
        EUCN.GrainDistillation,
        EUCN.AceticFermentation,
        EUCN.SweetenedWaterProcess,
    ])
