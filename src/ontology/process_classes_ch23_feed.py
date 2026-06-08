"""Named BFO Process subclasses for CN Chapter 23 (Residues, Waste, Animal Feed).

Process classes are pairwise owl:disjointWith — the load-bearing world-closure
mechanism: eucn:producedBy is owl:FunctionalProperty, so if the unique producedBy
value is typed as (e.g.) AnimalMealRendering, Konclude can infer
NOT(producedBy someValuesFrom GrainMillingProcess) via class disjointness.

Nine process classes map one-to-one to CN headings 2301-2309.

DEPRECATION NOTICE
------------------
This module is superseded by the LLM axiom agent pipeline
(src/agent/axiom_builder.py + src/agent/candidate_registry.py).
Once agent output for Chapter 23 has been manually validated, retire via::

    from src.scripts.retire_chapter import retire_chapter
    retire_chapter(23)

Do NOT retire before validation — the TBox process class vocabulary defined
here is required for correct OWL reasoning until the agent pipeline is
confirmed correct for all Ch23 process classes.
"""
from __future__ import annotations

from rdflib import Graph

from src.ontology.namespaces import EUCN
from src.ontology.owl_helpers import _disjoint_pairs, _proc


def add_process_classes_ch23_feed(graph: Graph) -> None:
    """Declare Ch23 process class vocabulary. Idempotent."""
    g = graph

    # ── Process classes ───────────────────────────────────────────────────────
    _proc(
        g, EUCN.AnimalMealRendering,
        "animal meal rendering", "Tiermehlherstellung",
        "process of rendering or processing animal by-products (meat offal, fish, "
        "crustaceans, insects) into flours, meals and pellets unfit for human "
        "consumption; produces residues classified under CN heading 2301",
        "Prozess der Aufbereitung von tierischen Nebenprodukten (Fleischabfälle, Fische, "
        "Krebstiere, Insekten) zu Mehl, Griess und Pellets, die zum menschlichen Genuss "
        "nicht geeignet sind; erzeugt Rückstände eingereiht in KN-Position 2301",
    )

    _proc(
        g, EUCN.GrainMillingProcess,
        "grain milling process", "Getreidemahlprozess",
        "process of sifting, milling or other working of cereals or leguminous plants "
        "to produce flour; produces bran, sharps and other milling residues classified "
        "under CN heading 2302",
        "Prozess des Siebens, Mahlens oder anderer Bearbeitung von Getreide oder "
        "Hülsenfrüchten zur Mehlherstellung; erzeugt Kleie, Schrot und andere "
        "Müllerei-Nebenerzeugnisse eingereiht in KN-Position 2302",
    )

    _proc(
        g, EUCN.StarchExtractionProcess,
        "starch extraction process", "Stärkegewinnungsprozess",
        "process of extracting starch from cereals, potatoes or other plant materials; "
        "produces starch manufacture residues, beet-pulp, bagasse and brewing/distilling "
        "wastes classified under CN heading 2303",
        "Prozess der Gewinnung von Stärke aus Getreide, Kartoffeln oder anderen "
        "pflanzlichen Materialien; erzeugt Rückstände aus der Stärkeherstellung, "
        "Rübenschnitzel, Bagasse und Brauereiabfälle eingereiht in KN-Position 2303",
    )

    _proc(
        g, EUCN.SoybeanOilExtraction,
        "soybean oil extraction", "Sojaölgewinnung",
        "process of pressing or solvent-extracting oil from soybeans; produces oil-cake "
        "and other solid soyabean residues classified under CN heading 2304",
        "Prozess des Pressens oder Lösungsmittelextrahierens von Öl aus Sojabohnen; "
        "erzeugt Ölkuchen und andere feste Rückstände aus Sojabohnen eingereiht "
        "in KN-Position 2304",
    )

    _proc(
        g, EUCN.GroundnutOilExtraction,
        "groundnut oil extraction", "Erdnussölgewinnung",
        "process of pressing or solvent-extracting oil from groundnuts (peanuts); "
        "produces oil-cake and other solid groundnut residues classified under "
        "CN heading 2305",
        "Prozess des Pressens oder Lösungsmittelextrahierens von Öl aus Erdnüssen; "
        "erzeugt Ölkuchen und andere feste Rückstände aus Erdnüssen eingereiht "
        "in KN-Position 2305",
    )

    _proc(
        g, EUCN.OtherOilseedExtraction,
        "other oilseed extraction", "Sonstige Pflanzenölgewinnung",
        "process of pressing or solvent-extracting oil from vegetable oilseeds other "
        "than soyabean or groundnut (including cotton seed, linseed, sunflower seed, "
        "palm kernel, coconut and others); produces oil-cake residues classified under "
        "CN heading 2306",
        "Prozess des Pressens oder Lösungsmittelextrahierens von Öl aus anderen "
        "Ölpflanzen als Sojabohnen oder Erdnüssen (einschließlich Baumwollsaat, "
        "Leinsamen, Sonnenblumenkerne, Palmkerne, Kokosnuss und andere); erzeugt "
        "Ölkuchen eingereiht in KN-Position 2306",
    )

    _proc(
        g, EUCN.WineLeesByproduction,
        "wine lees byproduction", "Weingeläger-Nebenproduktion",
        "process of grape fermentation or wine production that generates wine lees "
        "(the sediment deposited in wine vats) and crude argol (crude potassium "
        "bitartrate); produces residues classified under CN heading 2307",
        "Prozess der Traubenfermentation oder Weinherstellung, bei dem Weingeläger "
        "(der in Weinfässern abgesetzte Bodensatz) und Weinsteinrohstein entstehen; "
        "erzeugt Rückstände eingereiht in KN-Position 2307",
    )

    _proc(
        g, EUCN.PlantResidueCollection,
        "plant residue collection", "Pflanzliche Rückstandserfassung",
        "process of collecting, drying or minimally processing plant materials, "
        "vegetable waste and vegetable by-products of a kind used in animal feeding "
        "(e.g. grape marc, acorns, horse chestnuts) that are not elsewhere classified; "
        "produces plant residues classified under CN heading 2308",
        "Prozess des Sammelns, Trocknens oder der minimalen Verarbeitung von "
        "pflanzlichen Materialien, pflanzlichen Abfällen und Nebenprodukten zur "
        "Tierfütterung (z.B. Trester, Eicheln, Rosskastanien), die anderweitig nicht "
        "eingereiht sind; erzeugt Rückstände eingereiht in KN-Position 2308",
    )

    _proc(
        g, EUCN.AnimalFeedMixing,
        "animal feed mixing", "Futtermittelherstellung",
        "process of deliberately mixing, compounding or preparing ingredients to "
        "produce preparations of a kind used in animal feeding, including compound "
        "feeds, premixes, supplements, and pet food; produces preparations classified "
        "under CN heading 2309",
        "Prozess des gezielten Mischens, Zusammenstellens oder Aufbereitens von "
        "Zutaten zur Herstellung von Zubereitungen zur Tierernährung, einschließlich "
        "Mischfuttermittel, Vormischungen, Ergänzungsfutter und Heimtierfutter; "
        "erzeugt Zubereitungen eingereiht in KN-Position 2309",
    )

    # ── Pairwise owl:disjointWith (world-closure for producedBy FunctionalProperty) ──
    _disjoint_pairs(g, [
        EUCN.AnimalMealRendering,
        EUCN.GrainMillingProcess,
        EUCN.StarchExtractionProcess,
        EUCN.SoybeanOilExtraction,
        EUCN.GroundnutOilExtraction,
        EUCN.OtherOilseedExtraction,
        EUCN.WineLeesByproduction,
        EUCN.PlantResidueCollection,
        EUCN.AnimalFeedMixing,
    ])
