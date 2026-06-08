from __future__ import annotations

from rdflib import Graph, Literal
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from src.ontology.namespaces import BFO_PROCESS, EUCN, RO_HAS_OUTPUT


def _dp(g: Graph, iri, label_en: str, label_de: str, def_en: str, def_de: str, range_) -> None:
    g.add((iri, RDF.type, OWL.DatatypeProperty))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    g.add((iri, RDFS.label, Literal(label_de, lang="de")))
    g.add((iri, SKOS.definition, Literal(def_en, lang="en")))
    g.add((iri, SKOS.definition, Literal(def_de, lang="de")))
    g.add((iri, RDFS.range, range_))


def _op(g: Graph, iri, label_en: str, label_de: str, def_en: str, def_de: str, range_=None) -> None:
    g.add((iri, RDF.type, OWL.ObjectProperty))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    g.add((iri, RDFS.label, Literal(label_de, lang="de")))
    g.add((iri, SKOS.definition, Literal(def_en, lang="en")))
    g.add((iri, SKOS.definition, Literal(def_de, lang="de")))
    if range_ is not None:
        g.add((iri, RDFS.range, range_))


def add_discriminating_props(graph: Graph) -> None:
    """Declare discriminating data properties for Ch22 classification. Idempotent."""
    g = graph

    _dp(
        g, EUCN.alcoholByVolumePercent,
        "alcohol by volume percent", "Alkoholgehalt in Volumenprozent",
        "alcohol content of a beverage expressed as a percentage of volume, "
        "used to discriminate between CN headings 2201–2208 in Chapter 22",
        "Alkoholgehalt eines Getränks, ausgedrückt als Volumenprozent, "
        "zur Unterscheidung zwischen den KN-Positionen 2201–2208 in Kapitel 22",
        XSD.decimal,
    )

    _dp(
        g, EUCN.isCarbonated,
        "is carbonated", "ist kohlensäurehaltig",
        "boolean flag indicating whether a beverage is carbonated (sparkling) rather than still, "
        "used to discriminate between CN subheadings 2204 10 (sparkling) and 2204 21/29 (still)",
        "boolesches Merkmal, das angibt, ob ein Getränk mit Kohlensäure versetzt (schäumend) "
        "statt still ist, zur Unterscheidung zwischen den KN-Unterpositionen 2204 10 und 2204 21/29",
        XSD.boolean,
    )

    _dp(
        g, EUCN.isDenatured,
        "is denatured", "ist vergällt",
        "boolean flag indicating whether ethyl alcohol has been denatured by addition of "
        "substances rendering it unfit for human consumption, used to discriminate between "
        "CN subheadings 2207 10 (undenatured) and 2207 20 (denatured)",
        "boolesches Merkmal, das angibt, ob Ethylalkohol durch Zusatz von Stoffen vergällt "
        "wurde, die ihn für den menschlichen Genuss ungeeignet machen, zur Unterscheidung "
        "zwischen den KN-Unterpositionen 2207 10 (unvergällt) und 2207 20 (vergällt)",
        XSD.boolean,
    )

    _dp(
        g, EUCN.maxContainerVolumeL,
        "maximum container volume in litres", "maximales Behältervolumen in Litern",
        "nominal volume in litres of the container in which a beverage is presented, "
        "used to discriminate between CN subheadings 2204 21 (≤ 2 L) and 2204 29 (> 2 L)",
        "Nennvolumen in Litern des Behälters, in dem ein Getränk aufgemacht ist, "
        "zur Unterscheidung zwischen den KN-Unterpositionen 2204 21 (≤ 2 L) und 2204 29 (> 2 L)",
        XSD.decimal,
    )

    _op(
        g, EUCN.producedBy,
        "produced by", "hergestellt durch",
        "production process by which a beverage is made; links a beverage individual to its "
        "named process singleton, used to discriminate between CN headings in Chapter 22",
        "Herstellungsprozess, durch den ein Getränk erzeugt wird; verknüpft ein Getränkeindividuum "
        "mit seinem benannten Prozesssingleton, zur Unterscheidung zwischen KN-Positionen in Kapitel 22",
        BFO_PROCESS,
    )
    # Functional: each beverage is produced by exactly one process.
    # inverseOf RO:has_output (RO_0002234) — the process outputs the beverage.
    g.add((EUCN.producedBy, RDF.type, OWL.FunctionalProperty))
    g.add((EUCN.producedBy, OWL.inverseOf, RO_HAS_OUTPUT))
