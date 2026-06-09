"""Chapter-agnostic EUCN core TBox.

Declares the shared OWL content that applies across all CN chapters:
ontology header for <https://w3id.org/eucn/core>, BFO stubs, eucn:producedBy,
and eucn:cnHeadingCode.  All chapter-specific classes and properties are
handled in separate chapter modules.

This module is idempotent: calling build_core_tbox twice on the same graph
produces no extra triples.
"""
from __future__ import annotations

from datetime import date as Date

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

from src.ontology.namespaces import (
    BFO_HAS_PART, BFO_OBJECT, BFO_PROCESS, BFO_QUALITY, EUCN, RO_HAS_OUTPUT, RO_HAS_QUALITY,
)
from src.ontology.bfo_stubs import add_bfo_stubs
from src.ontology.owl_helpers import _bnode, _build_list, _cls, _decimal_range_restr, _equiv, _sub

# Stable IRI for the core ontology
CORE_IRI = URIRef("https://w3id.org/eucn/core")

# Raw GitHub URL for owl:imports (used when referencing core from chapter files)
CORE_RAW_URL = (
    "https://raw.githubusercontent.com/ThHanke/eu-customs-ontology"
    "/refs/heads/main/data/ontology/eucn-core-latest.ttl"
)


def build_core_tbox(g: Graph, extract_date: Date | None = None) -> Graph:
    """Add all core TBox triples to *g*.  Idempotent.

    Parameters
    ----------
    g:
        Target RDF graph.
    extract_date:
        Date used for owl:versionIRI and owl:versionInfo.
        Defaults to ``datetime.date.today()``.

    Returns
    -------
    Graph
        The same graph *g* with core triples added.
    """
    if extract_date is None:
        extract_date = Date.today()

    g.bind("eucn", EUCN)
    g.bind("owl", OWL)
    g.bind("skos", SKOS)
    g.bind("dcterms", DCTERMS)

    # ── Ontology header ────────────────────────────────────────────────────────
    version_iri = URIRef(
        f"https://w3id.org/eucn/core"
        f"/{extract_date.year}/{extract_date.month:02d}/{extract_date.day:02d}"
    )
    g.add((CORE_IRI, RDF.type, OWL.Ontology))
    g.add((CORE_IRI, OWL.versionIRI, version_iri))
    g.add((CORE_IRI, OWL.versionInfo,
           Literal(f"EUCN core ontology {extract_date.isoformat()}")))
    g.add((CORE_IRI, RDFS.label, Literal("EU CN Core Ontology", lang="en")))
    g.add((CORE_IRI, RDFS.label, Literal("EU KN Kern-Ontologie", lang="de")))
    g.add((CORE_IRI, DCTERMS.creator,
           URIRef("https://github.com/ThHanke")))
    g.add((CORE_IRI, DCTERMS.license,
           URIRef("https://creativecommons.org/licenses/by/4.0/")))
    g.add((CORE_IRI, DCTERMS.source,
           URIRef("https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:31987R2658")))

    # ── BFO stubs ──────────────────────────────────────────────────────────────
    add_bfo_stubs(g)

    # ── eucn:producedBy ────────────────────────────────────────────────────────
    g.add((EUCN.producedBy, RDF.type, OWL.ObjectProperty))
    g.add((EUCN.producedBy, RDFS.label, Literal("produced by", lang="en")))
    g.add((EUCN.producedBy, RDFS.label, Literal("hergestellt durch", lang="de")))
    g.add((EUCN.producedBy, SKOS.definition, Literal(
        "production process by which a beverage is made; links a beverage individual to its "
        "named process singleton, used to discriminate between CN headings in Chapter 22",
        lang="en",
    )))
    g.add((EUCN.producedBy, SKOS.definition, Literal(
        "Herstellungsprozess, durch den ein Getränk erzeugt wird; verknüpft ein Getränkeindividuum "
        "mit seinem benannten Prozesssingleton, zur Unterscheidung zwischen KN-Positionen in Kapitel 22",
        lang="de",
    )))
    g.add((EUCN.producedBy, RDFS.range, BFO_PROCESS))
    g.add((EUCN.producedBy, RDF.type, OWL.FunctionalProperty))
    g.add((EUCN.producedBy, OWL.inverseOf, RO_HAS_OUTPUT))

    # ── eucn:cnHeadingCode ─────────────────────────────────────────────────────
    g.add((EUCN.cnHeadingCode, RDF.type, OWL.DatatypeProperty))
    g.add((EUCN.cnHeadingCode, RDFS.label, Literal("CN heading code", lang="en")))
    g.add((EUCN.cnHeadingCode, RDFS.label, Literal("KN-Positionsnummer", lang="de")))
    g.add((EUCN.cnHeadingCode, SKOS.definition, Literal(
        "four-digit (or six-digit for subheadings) CN heading code inferred by the OWL reasoner "
        "from the product class membership; e.g. '2203' for Beer, '220410' for Sparkling Wine",
        lang="en",
    )))
    g.add((EUCN.cnHeadingCode, SKOS.definition, Literal(
        "Vierstellige (bzw. sechsstellige für Unterpositionen) KN-Positionsnummer, die der "
        "OWL-Reasoner aus der Produktklassenzugehörigkeit ableitet; z. B. '2203' für Bier, "
        "'220410' für Schaumwein",
        lang="de",
    )))
    g.add((EUCN.cnHeadingCode, RDFS.range, XSD.string))

    # ── Packaging model ────────────────────────────────────────────────────────
    # eucn:Packaging — material entity that is the container of a product
    _cls(g, EUCN.Packaging,
         "packaging", "Verpackung",
         "A material entity that serves as the container or packaging of a product.",
         "Eine materielle Entität, die als Behälter oder Verpackung eines Produkts dient.")
    _sub(g, EUCN.Packaging, BFO_OBJECT)

    # eucn:Volume — quality borne by packaging; its value is measured in litres
    _cls(g, EUCN.Volume,
         "volume", "Volumen",
         "A quality of a packaging entity that represents its capacity, measured in litres.",
         "Eine Eigenschaft einer Verpackungsentität, die ihre Kapazität in Litern angibt.")
    _sub(g, EUCN.Volume, BFO_QUALITY)

    # eucn:inLitres — datatype property relating a Volume quality to its decimal value
    g.add((EUCN.inLitres, RDF.type, OWL.DatatypeProperty))
    g.add((EUCN.inLitres, RDF.type, OWL.FunctionalProperty))
    g.add((EUCN.inLitres, RDFS.label, Literal("in litres", lang="en")))
    g.add((EUCN.inLitres, RDFS.label, Literal("in Litern", lang="de")))
    g.add((EUCN.inLitres, SKOS.definition, Literal(
        "the numeric volume value in litres of a Volume quality individual", lang="en")))
    g.add((EUCN.inLitres, RDFS.domain, EUCN.Volume))
    g.add((EUCN.inLitres, RDFS.range, XSD.decimal))

    # eucn:SmallContainer ≡ Packaging ⊓ (hasQuality some (Volume ⊓ ∃inLitres.[< 2.0]))
    vol_small = _decimal_range_restr(g, EUCN.inLitres, XSD.maxExclusive, 2.0, "pkg:small:vol")
    cv_small = _bnode("pkg:small:vol_inter")
    g.add((cv_small, RDF.type, OWL.Class))
    g.add((cv_small, OWL.intersectionOf, _build_list(g, [EUCN.Volume, vol_small], "pkg:small:cv")))
    hq_small = _bnode("pkg:small:hq")
    g.add((hq_small, RDF.type, OWL.Restriction))
    g.add((hq_small, OWL.onProperty, RO_HAS_QUALITY))
    g.add((hq_small, OWL.someValuesFrom, cv_small))
    _cls(g, EUCN.SmallContainer,
         "small container (< 2 L)", "Kleinbehälter (< 2 L)",
         "Packaging whose Volume quality has a value of less than 2 litres.",
         "Verpackung, deren Volumeneigenschaft einen Wert von weniger als 2 Litern hat.")
    _equiv(g, EUCN.SmallContainer, [EUCN.Packaging, hq_small], "pkg:small")

    # eucn:LargeContainer ≡ Packaging ⊓ (hasQuality some (Volume ⊓ ∃inLitres.[≥ 2.0]))
    vol_large = _decimal_range_restr(g, EUCN.inLitres, XSD.minInclusive, 2.0, "pkg:large:vol")
    cv_large = _bnode("pkg:large:vol_inter")
    g.add((cv_large, RDF.type, OWL.Class))
    g.add((cv_large, OWL.intersectionOf, _build_list(g, [EUCN.Volume, vol_large], "pkg:large:cv")))\

    hq_large = _bnode("pkg:large:hq")
    g.add((hq_large, RDF.type, OWL.Restriction))
    g.add((hq_large, OWL.onProperty, RO_HAS_QUALITY))
    g.add((hq_large, OWL.someValuesFrom, cv_large))
    _cls(g, EUCN.LargeContainer,
         "large container (≥ 2 L)", "Großbehälter (≥ 2 L)",
         "Packaging whose Volume quality has a value of at least 2 litres.",
         "Verpackung, deren Volumeneigenschaft einen Wert von mindestens 2 Litern hat.")
    _equiv(g, EUCN.LargeContainer, [EUCN.Packaging, hq_large], "pkg:large")

    # hasPart scoped to Packaging: Beverage hasPart some Packaging
    g.add((BFO_HAS_PART, RDFS.domain, BFO_OBJECT))
    g.add((BFO_HAS_PART, RDFS.range, BFO_OBJECT))

    return g
