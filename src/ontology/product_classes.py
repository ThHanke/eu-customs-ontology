"""Named OWL product class hierarchy for CN Chapter 22 (Beverages).

All heading-level siblings are pairwise disjoint (owl:disjointWith).
Root eucn:Beverage is a subClassOf BFO:Object (BFO_0000030).
No owl:AllDisjointClasses — pairwise only (Konclude WASM constraint).

Each product class carries a rdfs:subClassOf owl:hasValue restriction on
eucn:cnHeadingCode so that the OWL reasoner propagates the CN code to
classified individuals automatically.
"""
from __future__ import annotations

import hashlib
import itertools

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from src.ontology.namespaces import BFO_OBJECT, EUCN


def _bnode(key: str) -> BNode:
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return BNode(h)


def _cls(g: Graph, iri: URIRef, label_en: str, label_de: str,
         def_en: str, def_de: str) -> None:
    g.add((iri, RDF.type, OWL.Class))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    g.add((iri, RDFS.label, Literal(label_de, lang="de")))
    g.add((iri, SKOS.definition, Literal(def_en, lang="en")))
    g.add((iri, SKOS.definition, Literal(def_de, lang="de")))


def _sub(g: Graph, child: URIRef, parent: URIRef) -> None:
    g.add((child, RDFS.subClassOf, parent))


def _cn_heading(g: Graph, cls_iri: URIRef, code: str) -> None:
    """Add rdfs:subClassOf [hasValue code] so the reasoner propagates the CN code."""
    r = _bnode(f"cn:heading:{code}")
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, EUCN.cnHeadingCode))
    g.add((r, OWL.hasValue, Literal(code, datatype=XSD.string)))
    g.add((cls_iri, RDFS.subClassOf, r))


def _disjoint_pairs(g: Graph, classes: list[URIRef]) -> None:
    """Assert pairwise owl:disjointWith for all pairs in classes (symmetric)."""
    for a, b in itertools.combinations(classes, 2):
        g.add((a, OWL.disjointWith, b))
        g.add((b, OWL.disjointWith, a))


def add_product_classes_ch22(graph: Graph) -> None:
    """Declare Chapter 22 product class hierarchy. Idempotent."""
    g = graph

    # ── Root ──────────────────────────────────────────────────────────────────
    _cls(
        g, EUCN.Beverage,
        "Beverage", "Getränk",
        "liquid intended for human consumption, classified under CN Chapter 22; "
        "a subclass of BFO Object (BFO_0000030)",
        "für den menschlichen Genuss bestimmte Flüssigkeit, eingereiht in Kapitel 22 der KN; "
        "Unterklasse von BFO-Objekt (BFO_0000030)",
    )
    _sub(g, EUCN.Beverage, BFO_OBJECT)

    # ── Heading-level classes ─────────────────────────────────────────────────
    _cls(
        g, EUCN.Water,
        "Water", "Wasser",
        "water (including natural or artificial mineral waters and aerated waters), ice, "
        "and snow, classified under CN heading 2201 (Chapter 22)",
        "Wasser (einschließlich natürliches oder künstliches Mineralwasser und kohlensäurehaltiges Wasser), "
        "Eis und Schnee, eingereiht in KN-Position 2201 (Kapitel 22)",
    )
    _sub(g, EUCN.Water, EUCN.Beverage)
    _cn_heading(g, EUCN.Water, "2201")

    _cls(
        g, EUCN.NonAlcoholicBeverage,
        "Non-Alcoholic Beverage", "Nichtalkoholisches Getränk",
        "waters (including mineral waters and aerated waters) containing added sugar or "
        "other sweetening matter or flavoured, and other non-alcoholic beverages, classified "
        "under CN heading 2202 (Chapter 22)",
        "Wasser (einschließlich Mineralwasser und kohlensäurehaltiges Wasser) mit Zusatz von "
        "Zucker oder anderen Süßungsmitteln oder Aromastoffen sowie andere nichtalkoholische "
        "Getränke, eingereiht in KN-Position 2202 (Kapitel 22)",
    )
    _sub(g, EUCN.NonAlcoholicBeverage, EUCN.Beverage)
    _cn_heading(g, EUCN.NonAlcoholicBeverage, "2202")

    _cls(
        g, EUCN.Beer,
        "Beer", "Bier",
        "beer made from malt, a fermented beverage with alcoholic strength derived from the "
        "fermentation of malted barley or other cereals, classified under CN heading 2203 "
        "(Chapter 22)",
        "Bier aus Malz, fermentiertes Getränk mit einem Alkoholgehalt, der durch Vergärung "
        "von Gerstenmalz oder anderen Getreidearten entsteht, eingereiht in KN-Position 2203 "
        "(Kapitel 22)",
    )
    _sub(g, EUCN.Beer, EUCN.Beverage)
    _cn_heading(g, EUCN.Beer, "2203")

    _cls(
        g, EUCN.Wine,
        "Wine", "Wein",
        "wine of fresh grapes, including grape must with fermentation arrested by the addition "
        "of alcohol, classified under CN heading 2204 (Chapter 22)",
        "Wein aus frischen Weintrauben, einschließlich mit Alkohol stummgemachten Weins, "
        "eingereiht in KN-Position 2204 (Kapitel 22)",
    )
    _sub(g, EUCN.Wine, EUCN.Beverage)
    _cn_heading(g, EUCN.Wine, "2204")

    _cls(
        g, EUCN.FlavouredWine,
        "Flavoured Wine", "Wermutwein und andere aromatisierte Weine",
        "vermouth and other wines of fresh grapes, flavoured with plants or aromatic substances, "
        "classified under CN heading 2205 (Chapter 22)",
        "Wermutwein und andere Weine aus frischen Weintrauben, mit Pflanzen oder aromatischen "
        "Stoffen versetzt, eingereiht in KN-Position 2205 (Kapitel 22)",
    )
    _sub(g, EUCN.FlavouredWine, EUCN.Beverage)
    _cn_heading(g, EUCN.FlavouredWine, "2205")

    _cls(
        g, EUCN.FermentedBeverage,
        "Fermented Beverage", "Anderes Gärerzeugnis",
        "other fermented beverages (for example, cider, perry, mead, saké) and mixtures of "
        "fermented beverages and non-alcoholic beverages not elsewhere specified or included, "
        "classified under CN heading 2206 (Chapter 22)",
        "Andere Gärerzeugnisse (z. B. Apfelwein, Birnenwein, Met, Sake) sowie Mischungen von "
        "Gärerzeugnissen und nichtalkoholischen Getränken, anderweit weder genannt noch inbegriffen, "
        "eingereiht in KN-Position 2206 (Kapitel 22)",
    )
    _sub(g, EUCN.FermentedBeverage, EUCN.Beverage)
    _cn_heading(g, EUCN.FermentedBeverage, "2206")

    _cls(
        g, EUCN.EthylAlcohol,
        "Ethyl Alcohol", "Ethylalkohol",
        "undenatured ethyl alcohol of an alcoholic strength by volume of 80 % vol or higher; "
        "ethyl alcohol and other spirits, denatured, of any strength, classified under "
        "CN heading 2207 (Chapter 22)",
        "Unvergällter Ethylalkohol mit einem Alkoholgehalt von 80 % vol oder mehr; "
        "Ethylalkohol und andere Spirituosen, vergällt, jedes Alkoholgehalts, eingereiht in "
        "KN-Position 2207 (Kapitel 22)",
    )
    _sub(g, EUCN.EthylAlcohol, EUCN.Beverage)
    _cn_heading(g, EUCN.EthylAlcohol, "2207")

    _cls(
        g, EUCN.Spirit,
        "Spirit", "Spirituose",
        "undenatured ethyl alcohol of an alcoholic strength by volume of less than 80 % vol; "
        "spirits, liqueurs and other spirituous beverages, classified under CN heading 2208 "
        "(Chapter 22)",
        "Unvergällter Ethylalkohol mit einem Alkoholgehalt von weniger als 80 % vol; "
        "Spirituosen, Likör und andere alkoholische Getränke, eingereiht in KN-Position 2208 "
        "(Kapitel 22)",
    )
    _sub(g, EUCN.Spirit, EUCN.Beverage)
    _cn_heading(g, EUCN.Spirit, "2208")

    _cls(
        g, EUCN.Vinegar,
        "Vinegar", "Essig",
        "vinegar and substitutes for vinegar obtained from acetic acid, classified under "
        "CN heading 2209 (Chapter 22)",
        "Essig und Essigsäureersatz, aus Essigsäure gewonnen, eingereiht in KN-Position 2209 "
        "(Kapitel 22)",
    )
    _sub(g, EUCN.Vinegar, EUCN.Beverage)
    _cn_heading(g, EUCN.Vinegar, "2209")

    # ── Pairwise disjointness at heading level ─────────────────────────────────
    heading_classes = [
        EUCN.Water,
        EUCN.NonAlcoholicBeverage,
        EUCN.Beer,
        EUCN.Wine,
        EUCN.FlavouredWine,
        EUCN.FermentedBeverage,
        EUCN.EthylAlcohol,
        EUCN.Spirit,
        EUCN.Vinegar,
    ]
    _disjoint_pairs(g, heading_classes)

    # ── Wine sub-classes (2204) ────────────────────────────────────────────────
    _cls(
        g, EUCN.SparklingWine,
        "Sparkling Wine", "Schaumwein",
        "wine of fresh grapes that is effervescent by reason of the addition of carbon dioxide "
        "or by secondary fermentation in bottle, classified under CN subheading 2204 10 "
        "(Chapter 22)",
        "Wein aus frischen Weintrauben, der durch Zusatz von Kohlendioxid oder durch "
        "Flaschengärung schäumend ist, eingereiht in KN-Unterposition 2204 10 (Kapitel 22)",
    )
    _sub(g, EUCN.SparklingWine, EUCN.Wine)
    _cn_heading(g, EUCN.SparklingWine, "220410")

    _cls(
        g, EUCN.StillWine,
        "Still Wine", "Stillwein",
        "non-sparkling wine of fresh grapes in containers, classified under CN subheadings "
        "2204 21 (≤ 2 L) and 2204 29 (> 2 L) (Chapter 22)",
        "Nicht schäumender Wein aus frischen Weintrauben in Behältnissen, eingereiht in "
        "KN-Unterpositionen 2204 21 (≤ 2 L) und 2204 29 (> 2 L) (Kapitel 22)",
    )
    _sub(g, EUCN.StillWine, EUCN.Wine)
    _cn_heading(g, EUCN.StillWine, "220421")

    _cls(
        g, EUCN.GrapeMust,
        "Grape Must", "Traubenmost",
        "grape must with fermentation arrested by the addition of alcohol, classified under "
        "CN subheading 2204 30 (Chapter 22)",
        "Traubenmost, dessen Gärung durch Alkoholzusatz unterbrochen wurde, eingereiht in "
        "KN-Unterposition 2204 30 (Kapitel 22)",
    )
    _sub(g, EUCN.GrapeMust, EUCN.Wine)
    _cn_heading(g, EUCN.GrapeMust, "220430")

    # Pairwise disjointness within Wine sub-classes
    _disjoint_pairs(g, [EUCN.SparklingWine, EUCN.StillWine, EUCN.GrapeMust])
