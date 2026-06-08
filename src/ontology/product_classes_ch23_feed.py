"""Named OWL product class hierarchy for CN Chapter 23 (Residues, Waste, Animal Feed).

All nine heading-level siblings are pairwise disjoint (owl:disjointWith).
Root eucn:FeedstuffProduct is a subClassOf BFO:Object (BFO_0000030).
No owl:AllDisjointClasses — pairwise only (Konclude WASM constraint).

Each product class carries a rdfs:subClassOf owl:hasValue restriction on
eucn:cnHeadingCode so that the OWL reasoner propagates the CN code to
classified individuals automatically.

DEPRECATION NOTICE
------------------
This module is superseded by the LLM axiom agent pipeline
(src/agent/axiom_builder.py + src/agent/candidate_registry.py).
Once agent output for Chapter 23 has been manually validated, retire via::

    from src.scripts.retire_chapter import retire_chapter
    retire_chapter(23)

Do NOT retire before validation — the TBox product class hierarchy defined
here is required for correct OWL reasoning until the agent pipeline is
confirmed correct for all Ch23 product classes.
"""
from __future__ import annotations

from rdflib import Graph

from src.ontology.namespaces import BFO_OBJECT, EUCN
from src.ontology.owl_helpers import _cls, _cn_heading, _disjoint_pairs, _sub


def add_product_classes_ch23_feed(graph: Graph) -> None:
    """Declare Chapter 23 product class hierarchy. Idempotent."""
    g = graph

    # ── Root ──────────────────────────────────────────────────────────────────
    _cls(
        g, EUCN.FeedstuffProduct,
        "Feedstuff Product", "Futterstoff",
        "residue, waste, or prepared feed classified under CN Chapter 23; "
        "a subclass of BFO Object (BFO_0000030)",
        "Rückstand, Abfall oder Futtermittelerzeugnis, eingereiht in Kapitel 23 der KN; "
        "Unterklasse von BFO-Objekt (BFO_0000030)",
    )
    _sub(g, EUCN.FeedstuffProduct, BFO_OBJECT)

    # ── Heading-level classes ─────────────────────────────────────────────────
    _cls(
        g, EUCN.AnimalByProductMeal,
        "Animal By-Product Meal", "Tierisches Mehl und Pellets",
        "flours, meals and pellets of meat or meat offal, fish, crustaceans, molluscs "
        "or other aquatic invertebrates, or insects, unfit for human consumption, "
        "classified under CN heading 2301 (Chapter 23)",
        "Mehl, Griess und Pellets von Fleisch oder Fleischabfällen, Fischen, Krebstieren, "
        "Weichtieren oder anderen wirbellosen Wassertieren oder von Insekten, zum "
        "menschlichen Genuss nicht geeignet, eingereiht in KN-Position 2301 (Kapitel 23)",
    )
    _sub(g, EUCN.AnimalByProductMeal, EUCN.FeedstuffProduct)
    _cn_heading(g, EUCN.AnimalByProductMeal, "2301")

    _cls(
        g, EUCN.CerealMillingResidue,
        "Cereal Milling Residue", "Kleie und Müllerei-Nebenerzeugnisse",
        "bran, sharps and other residues, whether or not in the form of pellets, derived "
        "by the sifting, milling or other working of cereals or of leguminous plants, "
        "classified under CN heading 2302 (Chapter 23)",
        "Kleie, Schrot und andere Rückstände, auch in Form von Pellets, vom Sieben, "
        "Mahlen oder anderen Bearbeiten von Getreide oder Hülsenfrüchten, "
        "eingereiht in KN-Position 2302 (Kapitel 23)",
    )
    _sub(g, EUCN.CerealMillingResidue, EUCN.FeedstuffProduct)
    _cn_heading(g, EUCN.CerealMillingResidue, "2302")

    _cls(
        g, EUCN.StarchManufactureResidue,
        "Starch Manufacture Residue", "Rückstände aus der Stärkeherstellung",
        "residues of starch manufacture and similar residues, beet-pulp, bagasse and "
        "other waste of sugar manufacture, brewing or distilling dregs and waste, "
        "classified under CN heading 2303 (Chapter 23)",
        "Rückstände aus der Stärkeherstellung und ähnliche Rückstände, Rübenschnitzel, "
        "Bagasse und andere Abfälle der Zuckerherstellung, Treber, Schlempen und "
        "Abfälle aus Brauereien und Brennereien, eingereiht in KN-Position 2303 (Kapitel 23)",
    )
    _sub(g, EUCN.StarchManufactureResidue, EUCN.FeedstuffProduct)
    _cn_heading(g, EUCN.StarchManufactureResidue, "2303")

    _cls(
        g, EUCN.SoybeanOilcake,
        "Soybean Oilcake", "Ölkuchen aus Sojabohnen",
        "oil-cake and other solid residues, whether or not ground or in the form of "
        "pellets, resulting from the extraction of soyabean oil, classified under "
        "CN heading 2304 (Chapter 23)",
        "Ölkuchen und andere feste Rückstände aus der Gewinnung von Sojaöl, auch gemahlen "
        "oder in Form von Pellets, eingereiht in KN-Position 2304 (Kapitel 23)",
    )
    _sub(g, EUCN.SoybeanOilcake, EUCN.FeedstuffProduct)
    _cn_heading(g, EUCN.SoybeanOilcake, "2304")

    _cls(
        g, EUCN.GroundnutOilcake,
        "Groundnut Oilcake", "Ölkuchen aus Erdnüssen",
        "oil-cake and other solid residues, whether or not ground or in the form of "
        "pellets, resulting from the extraction of groundnut oil, classified under "
        "CN heading 2305 (Chapter 23)",
        "Ölkuchen und andere feste Rückstände aus der Gewinnung von Erdnussöl, auch "
        "gemahlen oder in Form von Pellets, eingereiht in KN-Position 2305 (Kapitel 23)",
    )
    _sub(g, EUCN.GroundnutOilcake, EUCN.FeedstuffProduct)
    _cn_heading(g, EUCN.GroundnutOilcake, "2305")

    _cls(
        g, EUCN.VegetableOilcake,
        "Vegetable Oilcake", "Pflanzliches Extraktionsschrot",
        "oil-cake and other solid residues, whether or not ground or in the form of "
        "pellets, resulting from the extraction of vegetable fats or oils other than "
        "those of soyabean or groundnut oil, including cotton seed, linseed, sunflower "
        "seed, palm kernel and coconut, classified under CN heading 2306 (Chapter 23)",
        "Ölkuchen und andere feste Rückstände aus der Gewinnung von pflanzlichen Fetten "
        "oder Ölen, ausgenommen solche von Sojabohnen- oder Erdnussöl, einschließlich "
        "Baumwollsaat, Leinsamen, Sonnenblumenkerne, Palmkernöl und Kokosnuss, "
        "eingereiht in KN-Position 2306 (Kapitel 23)",
    )
    _sub(g, EUCN.VegetableOilcake, EUCN.FeedstuffProduct)
    _cn_heading(g, EUCN.VegetableOilcake, "2306")

    _cls(
        g, EUCN.WineLees,
        "Wine Lees", "Weingeläger und Weinsteinrohstein",
        "wine lees and crude argol (argol being the crude potassium bitartrate deposited "
        "during wine fermentation), classified under CN heading 2307 (Chapter 23)",
        "Weingeläger und Weinsteinrohstein, eingereiht in KN-Position 2307 (Kapitel 23)",
    )
    _sub(g, EUCN.WineLees, EUCN.FeedstuffProduct)
    _cn_heading(g, EUCN.WineLees, "2307")

    _cls(
        g, EUCN.PlantResidue,
        "Plant Residue", "Pflanzliche Abfälle zur Tierfütterung",
        "vegetable materials and vegetable waste, vegetable residues and by-products, "
        "whether or not in the form of pellets, of a kind used in animal feeding, "
        "not elsewhere specified or included, classified under CN heading 2308 (Chapter 23)",
        "Pflanzliche Stoffe und pflanzliche Abfälle, pflanzliche Rückstände und "
        "Nebenerzeugnisse, auch in Form von Pellets, zur Tierfütterung, anderweitig "
        "weder genannt noch inbegriffen, eingereiht in KN-Position 2308 (Kapitel 23)",
    )
    _sub(g, EUCN.PlantResidue, EUCN.FeedstuffProduct)
    _cn_heading(g, EUCN.PlantResidue, "2308")

    _cls(
        g, EUCN.AnimalFeedPreparation,
        "Animal Feed Preparation", "Zubereitungen zur Tierernährung",
        "preparations of a kind used in animal feeding, including compound feeds, "
        "premixes, supplements, and pet food (whether or not containing meat, fish, "
        "cereals, vegetables, or other ingredients), classified under CN heading 2309 "
        "(Chapter 23)",
        "Zubereitungen zur Tierernährung, einschließlich Mischfuttermittel, Vormischungen, "
        "Ergänzungsfutter und Heimtierfutter (mit oder ohne Fleisch, Fisch, Getreide, "
        "Gemüse oder anderen Zutaten), eingereiht in KN-Position 2309 (Kapitel 23)",
    )
    _sub(g, EUCN.AnimalFeedPreparation, EUCN.FeedstuffProduct)
    _cn_heading(g, EUCN.AnimalFeedPreparation, "2309")

    # ── Pairwise owl:disjointWith (world-closure for producedBy FunctionalProperty) ──
    _disjoint_pairs(g, [
        EUCN.AnimalByProductMeal,
        EUCN.CerealMillingResidue,
        EUCN.StarchManufactureResidue,
        EUCN.SoybeanOilcake,
        EUCN.GroundnutOilcake,
        EUCN.VegetableOilcake,
        EUCN.WineLees,
        EUCN.PlantResidue,
        EUCN.AnimalFeedPreparation,
    ])
