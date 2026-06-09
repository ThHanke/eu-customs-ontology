from __future__ import annotations

from datetime import date as Date

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from src.ontology.namespaces import DCTERMS, EUCN, ONTOLOGY_IRI, VANN
from src.ontology.bfo_stubs import add_bfo_stubs
from src.ontology.core import build_core_tbox
from src.ontology.chapter_registry import get_chapter


def _class(g: Graph, iri: URIRef, label_en: str, label_de: str, def_en: str, def_de: str) -> None:
    g.add((iri, RDF.type, OWL.Class))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    g.add((iri, RDFS.label, Literal(label_de, lang="de")))
    g.add((iri, SKOS.definition, Literal(def_en, lang="en")))
    g.add((iri, SKOS.definition, Literal(def_de, lang="de")))


def _obj_prop(g: Graph, iri: URIRef, label_en: str, label_de: str, def_en: str, def_de: str,
              domain: URIRef | None = None, range_: URIRef | None = None) -> None:
    g.add((iri, RDF.type, OWL.ObjectProperty))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    g.add((iri, RDFS.label, Literal(label_de, lang="de")))
    g.add((iri, SKOS.definition, Literal(def_en, lang="en")))
    g.add((iri, SKOS.definition, Literal(def_de, lang="de")))
    if domain:
        g.add((iri, RDFS.domain, domain))
    if range_:
        g.add((iri, RDFS.range, range_))


def _data_prop(g: Graph, iri: URIRef, label_en: str, label_de: str, def_en: str, def_de: str,
               range_: URIRef | None = None) -> None:
    g.add((iri, RDF.type, OWL.DatatypeProperty))
    g.add((iri, RDFS.label, Literal(label_en, lang="en")))
    g.add((iri, RDFS.label, Literal(label_de, lang="de")))
    g.add((iri, SKOS.definition, Literal(def_en, lang="en")))
    g.add((iri, SKOS.definition, Literal(def_de, lang="de")))
    if range_:
        g.add((iri, RDFS.range, range_))


def build_tbox(
    graph: Graph,
    extract_date: Date | None = None,
    chapter: int = 22,
    heading_labels: dict | None = None,
    uncovered_cn_codes: set | None = None,
) -> Graph:
    """Add all TBox triples to graph. Idempotent."""
    if extract_date is None:
        extract_date = Date.today()

    g = graph
    build_core_tbox(g, extract_date=extract_date)
    g.bind("eucn", EUCN)
    g.bind("owl", OWL)
    g.bind("skos", SKOS)
    g.bind("dcterms", DCTERMS)
    g.bind("vann", VANN)

    # ── Ontology metadata ──────────────────────────────────────────────────────
    ont = ONTOLOGY_IRI
    version_iri = URIRef(
        f"https://w3id.org/eucn/"
        f"{extract_date.year}/{extract_date.month:02d}/{extract_date.day:02d}"
    )
    g.add((ont, RDF.type, OWL.Ontology))
    g.add((ont, OWL.versionIRI, version_iri))
    g.add((ont, OWL.versionInfo, Literal(f"TARIC extract {extract_date.isoformat()}")))
    g.add((ont, RDFS.label,
           Literal("EU Customs Combined Nomenclature Ontology", lang="en")))
    g.add((ont, RDFS.label,
           Literal("Ontologie der EU-Kombinierten Nomenklatur (KN/TARIC)", lang="de")))
    g.add((ont, DCTERMS.title,
           Literal("EU Customs Combined Nomenclature Ontology", lang="en")))
    g.add((ont, DCTERMS.title,
           Literal("Ontologie der EU-Kombinierten Nomenklatur (KN/TARIC)", lang="de")))
    g.add((ont, DCTERMS.description, Literal(
        "OWL 2 DL ontology modelling the EU Combined Nomenclature (CN) and TARIC "
        "integrated tariff: commodity codes, duty measures, and EZT-Online "
        "classification guidance. Data extracted from the European Commission CIRCABC "
        "TARIC & Quota space. Classification paths sourced from the EZT-Online advisory "
        "wizard carry advisory status only and do not constitute legally binding EU instruments.",
        lang="en",
    )))
    g.add((ont, DCTERMS.description, Literal(
        "OWL-2-DL-Ontologie zur Modellierung der Kombinierten Nomenklatur (KN) der EU "
        "und des integrierten TARIC-Zolltarifs: Warenpositionen, Zollmaßnahmen und "
        "Einreihungshilfen aus EZT-Online. Einreihungspfade aus EZT-Online haben nur "
        "Beratungscharakter und stellen kein rechtsverbindliches EU-Instrument dar.",
        lang="de",
    )))
    # Council Regulation (EEC) No 2658/87 — legal basis for CN and TARIC
    g.add((ont, DCTERMS.source,
           URIRef("https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:31987R2658")))
    g.add((ont, DCTERMS.source,
           URIRef("https://circabc.europa.eu/ui/group/0e5f18c2-4b2f-42e9-aed4-dfe50ae1263b")))
    g.add((ont, DCTERMS.license,
           URIRef("https://creativecommons.org/licenses/by/4.0/")))
    g.add((ont, DCTERMS.issued,
           Literal(extract_date.isoformat(), datatype=XSD.date)))
    g.add((ont, VANN.preferredNamespacePrefix, Literal("eucn")))
    g.add((ont, VANN.preferredNamespaceUri, Literal("https://w3id.org/eucn/")))

    # ── BFO stubs ──────────────────────────────────────────────────────────────
    add_bfo_stubs(g)

    # ── Chapter-specific TBox (dispatched via registry) ───────────────────────
    ch = get_chapter(chapter)
    ch.add_discriminating_props(g)
    ch.add_product_classes(g)
    ch.add_process_classes(g)

    # ── Heading classes from tariffnumber.com labels (if available) ───────────
    if heading_labels:
        from src.ontology.heading_classes import add_heading_classes
        add_heading_classes(g, chapter, heading_labels, uncovered_cn_codes or set())

    # ── Classes ────────────────────────────────────────────────────────────────
    _class(g, EUCN.CNCode, "CN Code", "KN-Code",
           "commodity nomenclature code of eight digits assigned within the "
           "Combined Nomenclature of the European Union for the classification of goods in "
           "international trade",
           "Warenpositionsnummer aus acht Stellen, die innerhalb der Kombinierten "
           "Nomenklatur der Europäischen Union zur Einreihung von Waren im internationalen Handel "
           "vergeben wird")

    _class(g, EUCN.TARICCode, "TARIC Code", "TARIC-Code",
           "ten-digit extension of a CN code within the Integrated Tariff of the European "
           "Communities that specifies the applicable regulatory measures at the most granular "
           "commodity level",
           "Zehnstellige Erweiterung eines KN-Codes im Integrierten Zolltarif der Europäischen "
           "Gemeinschaften, die die anwendbaren Regelungsmaßnahmen auf der detailliertesten "
           "Warenebene festlegt")
    g.add((EUCN.TARICCode, RDFS.subClassOf, EUCN.CNCode))

    _class(g, EUCN.TARICMeasure, "TARIC Measure", "TARIC-Maßnahme",
           "regulatory instrument of the Integrated Tariff of the European Communities that "
           "specifies a tariff rate, restriction, suspension, quota, or licensing condition "
           "applicable to goods identified by a CN or TARIC code, valid within a defined "
           "geographical and temporal scope",
           "Regelungsinstrument des Integrierten Zolltarifs der Europäischen Gemeinschaften, "
           "das einen Zollsatz, eine Beschränkung, eine Aussetzung, ein Kontingent oder eine "
           "Genehmigungspflicht für Waren festlegt, die durch einen KN- oder TARIC-Code "
           "identifiziert werden, gültig innerhalb eines bestimmten geografischen und zeitlichen "
           "Geltungsbereichs")

    _class(g, EUCN.ClassificationNode, "Classification Node", "Einreihungsknoten",
           "step in a sequential commodity classification procedure that poses a single "
           "discriminating question to narrow the applicable nomenclature position; sourced "
           "from the EZT-Online advisory wizard and carrying advisory status only, not "
           "constituting a legally binding EU instrument",
           "Schritt in einem sequenziellen Wareneinreihungsverfahren, der eine einzelne "
           "unterscheidende Frage stellt, um die zutreffende Nomenklaturposition einzugrenzen; "
           "bezogen auf den Beratungsassistenten EZT-Online und ohne rechtsbindende Wirkung "
           "als EU-Instrument")

    _class(g, EUCN.Chapter, "Chapter", "Kapitel",
           "two-digit subdivision of the Harmonized System nomenclature that groups goods "
           "sharing a common material composition, functional category, or industrial origin",
           "zweistellige Unterteilung der Nomenklatur des Harmonisierten Systems, die Waren "
           "mit gemeinsamer Materialzusammensetzung, funktionaler Kategorie oder industriellem "
           "Ursprung zusammenfasst")

    _class(g, EUCN.Heading, "Heading", "Position",
           "four-digit subdivision of the Harmonized System nomenclature that identifies a "
           "specific group of goods within a chapter by further differentiating on material, "
           "process, or use",
           "vierstellige Unterteilung der Nomenklatur des Harmonisierten Systems, die eine "
           "bestimmte Warengruppe innerhalb eines Kapitels durch weitere Differenzierung nach "
           "Material, Verarbeitungsstufe oder Verwendungszweck identifiziert")

    _class(g, EUCN.TARICSection, "TARIC Section", "TARIC-Abschnitt",
           "Roman-numeral top-level grouping in the TARIC and Harmonized System nomenclature "
           "that aggregates related chapters under a common thematic heading",
           "Gliederungsebene mit römischer Nummerierung im TARIC und Harmonisierten System, "
           "die verwandte Kapitel unter einem gemeinsamen Thema zusammenfasst")

    _class(g, EUCN.TARICSubheading, "TARIC Subheading", "TARIC-Unterposition",
           "six-digit subdivision of the Harmonized System nomenclature that further "
           "differentiates goods within a four-digit heading",
           "sechsstellige Unterteilung des Harmonisierten Systems, die Waren innerhalb einer "
           "vierstelligen Position weiter differenziert")
    g.add((EUCN.TARICSubheading, RDFS.subClassOf, EUCN.CNCode))

    _class(g, EUCN.MeasureType, "Measure Type", "Maßnahmetyp",
           "controlled-vocabulary individual identifying the regulatory category of a TARIC "
           "measure, such as third-country duty (103), tariff preference (142), or licence "
           "condition (750)",
           "Controlled-Vocabulary-Instanz, die die Regelungskategorie einer TARIC-Maßnahme "
           "identifiziert, z. B. Drittlandszollsatz (103), Zollpräferenz (142) oder "
           "Genehmigungspflicht (750)")

    _class(g, EUCN.GeographicArea, "Geographic Area", "Geografisches Gebiet",
           "named individual representing a country, customs union, trade bloc, or the "
           "catch-all designation ERGA OMNES (code 1011) that delimits the geographic scope "
           "of a TARIC measure",
           "benannte Instanz, die ein Land, eine Zollunion, einen Handelsblock oder die "
           "Sammelbezeichnung ERGA OMNES (Code 1011) repräsentiert, die den geografischen "
           "Geltungsbereich einer TARIC-Maßnahme bestimmt")

    _class(g, EUCN.DutyExpression, "Duty Expression", "Zollausdruck",
           "structured representation of the duty rate applicable under a single TARIC measure, "
           "combining a numeric amount with its unit of measurement",
           "strukturierte Darstellung des im Rahmen einer TARIC-Maßnahme geltenden Zollsatzes, "
           "bestehend aus einem numerischen Betrag und seiner Maßeinheit")

    _class(g, EUCN.MeasureCondition, "Measure Condition", "Maßnahmebedingung",
           "prerequisite or restriction attached to a TARIC measure specifying a certificate "
           "to be presented, a quantity threshold to be observed, or an exemption clause",
           "Voraussetzung oder Einschränkung einer TARIC-Maßnahme, die ein vorzulegendes "
           "Zertifikat, einen einzuhaltenden Mengenschwellenwert oder eine Ausnahmeklausel "
           "festlegt")

    _class(g, EUCN.Certificate, "Certificate", "Zertifikat",
           "trade or regulatory document identified by a D-, C-, or Y-prefix code required "
           "as a condition for the application of a TARIC measure",
           "Handels- oder Verwaltungsdokument, das durch einen D-, C- oder Y-Präfix-Code "
           "identifiziert wird und als Bedingung für die Anwendung einer TARIC-Maßnahme "
           "erforderlich ist")

    _class(g, EUCN.Footnote, "Footnote", "Fußnote",
           "legal annotation identified by a TN-prefix code that qualifies or restricts the "
           "scope of a TARIC measure or nomenclature position",
           "rechtliche Anmerkung, identifiziert durch einen TN-Präfix-Code, die den "
           "Geltungsbereich einer TARIC-Maßnahme oder Nomenklaturstelle qualifiziert oder "
           "einschränkt")

    _class(g, EUCN.AdditionalCode, "Additional Code", "Zusatzcode",
           "four-character TARIC code appended to a commodity code to specify sub-categories "
           "for trade-remedy, authorised-use, or excise-duty purposes",
           "vierstelliger TARIC-Code, der einem Warencode angehängt wird, um Unterkategorien "
           "für Handelsschutzmaßnahmen, besondere Verwendung oder Verbrauchsteuerzwecke "
           "anzugeben")

    _class(g, EUCN.Regulation, "Regulation", "Verordnung",
           "EU Regulation, Decision, or Directive that creates or amends one or more TARIC "
           "measures, identified by its official journal reference",
           "EU-Verordnung, -Beschluss oder -Richtlinie, die eine oder mehrere TARIC-Maßnahmen "
           "erlässt oder ändert, identifiziert durch ihre Amtsblatt-Fundstelle")

    _class(g, EUCN.MeasurementUnit, "Measurement Unit", "Maßeinheit",
           "unit used in a TARIC duty expression or measure condition, such as ASV "
           "(percentage by volume), HLT (hectolitre), or SPR (standard percentage of alcohol)",
           "Einheit, die in einem TARIC-Zollausdruck oder einer Maßnahmebedingung verwendet "
           "wird, z. B. ASV (Volumenprozent), HLT (Hektoliter) oder SPR "
           "(Standardalkoholgehalt in Prozent)")

    # ── Object properties ──────────────────────────────────────────────────────
    _obj_prop(g, EUCN.classifiesAs, "classifies as", "wird eingereiht als",
              "relation between a terminal classification node and the CN code to which goods "
              "are assigned upon completion of the sequential classification procedure initiated "
              "at the root node",
              "Beziehung zwischen einem terminalen Einreihungsknoten und dem KN-Code, unter den "
              "Waren nach Abschluss des sequenziellen Einreihungsverfahrens, das am Wurzelknoten "
              "beginnt, eingereiht werden",
              domain=EUCN.ClassificationNode, range_=EUCN.CNCode)

    _obj_prop(g, EUCN.hasAnswer, "has answer", "hat Antwort",
              "relation between a classification node and a subsequent classification node "
              "reached by selecting a particular answer to the discriminating question posed at "
              "the source node",
              "Beziehung zwischen einem Einreihungsknoten und einem nachfolgenden "
              "Einreihungsknoten, der durch Auswahl einer bestimmten Antwort auf die am "
              "Ausgangsknoten gestellte unterscheidende Frage erreicht wird",
              domain=EUCN.ClassificationNode, range_=EUCN.ClassificationNode)

    _obj_prop(g, EUCN.hasMeasure, "has measure", "hat Maßnahme",
              "relation between a CN code and a TARIC measure under which goods classified by "
              "that CN code are subject to the regulatory conditions specified by the measure",
              "Beziehung zwischen einem KN-Code und einer TARIC-Maßnahme, deren "
              "Regelungsbedingungen für Waren gelten, die unter diesen KN-Code eingereiht sind",
              domain=EUCN.CNCode, range_=EUCN.TARICMeasure)

    _obj_prop(g, EUCN.belongsToChapter, "belongs to chapter", "gehört zu Kapitel",
              "relation between a CN code and the two-digit Harmonized System chapter in whose "
              "nomenclature scope the code is situated",
              "Beziehung zwischen einem KN-Code und dem zweistelligen Kapitel des Harmonisierten "
              "Systems, in dessen Nomenklaturgeltungsbereich der Code fällt",
              domain=EUCN.CNCode, range_=EUCN.Chapter)

    _obj_prop(g, EUCN.belongsToHeading, "belongs to heading", "gehört zu Position",
              "relation between a CN code and the four-digit heading that it subdivides",
              "Beziehung zwischen einem KN-Code und der vierstelligen Position, die er "
              "unterteilt",
              domain=EUCN.CNCode, range_=EUCN.Heading)

    _obj_prop(g, EUCN.belongsToSection, "belongs to section", "gehört zu Abschnitt",
              "relation between a chapter and the Roman-numeral TARIC section that contains it",
              "Beziehung zwischen einem Kapitel und dem TARIC-Abschnitt mit römischer Nummerierung, "
              "der es enthält",
              domain=EUCN.Chapter, range_=EUCN.TARICSection)

    _obj_prop(g, EUCN.hasMeasureType, "has measure type", "hat Maßnahmetyp",
              "relation between a TARIC measure and its regulatory category individual",
              "Beziehung zwischen einer TARIC-Maßnahme und ihrer Regelungskategorie-Instanz",
              domain=EUCN.TARICMeasure, range_=EUCN.MeasureType)

    _obj_prop(g, EUCN.hasGeographicArea, "has geographic area", "hat geografisches Gebiet",
              "relation between a TARIC measure and the geographic area individual defining "
              "its territorial scope",
              "Beziehung zwischen einer TARIC-Maßnahme und der geografischen Gebiet-Instanz, "
              "die ihren territorialen Geltungsbereich definiert",
              domain=EUCN.TARICMeasure, range_=EUCN.GeographicArea)

    _obj_prop(g, EUCN.hasDutyExpression, "has duty expression", "hat Zollausdruck",
              "relation between a TARIC measure and its duty expression individual",
              "Beziehung zwischen einer TARIC-Maßnahme und ihrer Zollausdruck-Instanz",
              domain=EUCN.TARICMeasure, range_=EUCN.DutyExpression)

    _obj_prop(g, EUCN.hasCondition, "has condition", "hat Bedingung",
              "relation between a TARIC measure and a measure condition it imposes",
              "Beziehung zwischen einer TARIC-Maßnahme und einer von ihr auferlegten "
              "Maßnahmebedingung",
              domain=EUCN.TARICMeasure, range_=EUCN.MeasureCondition)

    _obj_prop(g, EUCN.hasFootnote, "has footnote", "hat Fußnote",
              "relation between a TARIC measure or CN code and a footnote that qualifies "
              "its scope",
              "Beziehung zwischen einer TARIC-Maßnahme oder einem KN-Code und einer Fußnote, "
              "die deren Geltungsbereich qualifiziert")

    _obj_prop(g, EUCN.hasRegulation, "has regulation", "hat Verordnung",
              "relation between a TARIC measure and the EU legal act that created it",
              "Beziehung zwischen einer TARIC-Maßnahme und dem EU-Rechtsakt, der sie erlassen "
              "hat",
              domain=EUCN.TARICMeasure, range_=EUCN.Regulation)

    _obj_prop(g, EUCN.hasCertificate, "has certificate", "hat Zertifikat",
              "relation between a measure condition and the certificate document required to "
              "satisfy it",
              "Beziehung zwischen einer Maßnahmebedingung und dem Zertifikatsdokument, das "
              "zu ihrer Erfüllung erforderlich ist",
              domain=EUCN.MeasureCondition, range_=EUCN.Certificate)

    _obj_prop(g, EUCN.hasAdditionalCode, "has additional code", "hat Zusatzcode",
              "relation between a TARIC measure and the additional code that further "
              "qualifies the goods it applies to",
              "Beziehung zwischen einer TARIC-Maßnahme und dem Zusatzcode, der die Waren, "
              "auf die sie zutrifft, weiter qualifiziert",
              domain=EUCN.TARICMeasure, range_=EUCN.AdditionalCode)

    _obj_prop(g, EUCN.hasMeasurementUnit, "has measurement unit", "hat Maßeinheit",
              "relation between a duty expression or measure condition and the unit of "
              "measurement used for the rate or threshold",
              "Beziehung zwischen einem Zollausdruck oder einer Maßnahmebedingung und der "
              "für den Satz oder Schwellenwert verwendeten Maßeinheit",
              range_=EUCN.MeasurementUnit)

    # ── Data properties ────────────────────────────────────────────────────────
    _data_prop(g, EUCN.codeString, "code string", "Codenummer",
               "digit string uniquely identifying a nomenclature position without separating "
               "punctuation, derived by concatenating the numeric segments of the code, "
               "e.g. '22042100' for CN code 2204 21 00",
               "Ziffernfolge, die eine Nomenklaturstelle ohne Trennzeichen eindeutig "
               "identifiziert, gebildet durch Aneinanderreihung der numerischen Segmente des "
               "Codes, z. B. '22042100' für KN-Code 2204 21 00",
               range_=XSD.string)

    _data_prop(g, EUCN.description, "description", "Warenbezeichnung",
               "official textual designation of a commodity as established in the legal text of "
               "the Combined Nomenclature, expressed in a specified natural language and carrying "
               "legal force within EU customs classification",
               "amtliche Warenbezeichnung, wie sie im Rechtstext der Kombinierten Nomenklatur "
               "festgelegt ist, in einer bestimmten natürlichen Sprache und mit rechtlicher "
               "Wirkung innerhalb der EU-Zolleinreihung",
               range_=XSD.string)

    _data_prop(g, EUCN.questionText, "question text", "Fragetext",
               "textual formulation of the discriminating question posed at a classification "
               "node in the EZT-Online wizard, expressed in a specified natural language, used "
               "to guide the classifier toward the applicable nomenclature branch",
               "textliche Formulierung der unterscheidenden Frage, die an einem "
               "Einreihungsknoten des EZT-Online-Assistenten gestellt wird, in einer bestimmten "
               "natürlichen Sprache, zur Führung des Einreihenden zur zutreffenden "
               "Nomenklaturstelle",
               range_=XSD.string)

    _data_prop(g, EUCN.answerText, "answer text", "Antworttext",
               "textual formulation of the answer option that, when selected at a parent "
               "classification node, determines the transition to this classification node in "
               "the sequential classification procedure",
               "textliche Formulierung der Antwortoption, die bei Auswahl an einem "
               "übergeordneten Einreihungsknoten den Übergang zu diesem Einreihungsknoten im "
               "sequenziellen Einreihungsverfahren bestimmt",
               range_=XSD.string)

    _data_prop(g, EUCN.dutyRate, "duty rate", "Zollsatz",
               "textual expression of the duty or charge rate applicable under a TARIC measure "
               "as published in the TARIC bulk data, combining a numeric value with a unit of "
               "measurement, e.g. '12.0 %' or '32.0 EUR/hl'",
               "textliche Darstellung des Zoll- oder Abgabensatzes, der im Rahmen einer "
               "TARIC-Maßnahme gilt, wie in den TARIC-Massendaten veröffentlicht, bestehend "
               "aus einem numerischen Wert und einer Maßeinheit, z. B. '12,0 %' oder "
               "'32,0 EUR/hl'",
               range_=XSD.string)

    _data_prop(g, EUCN.dutyAmount, "duty amount", "Zollbetrag",
               "numeric value of the duty or charge rate applicable under a TARIC measure",
               "numerischer Wert des Zoll- oder Abgabensatzes im Rahmen einer TARIC-Maßnahme",
               range_=XSD.decimal)

    _data_prop(g, EUCN.geographicScope, "geographic scope", "geografischer Geltungsbereich",
               "identifier of the country or country group to whose originating goods a TARIC "
               "measure applies, expressed as an ISO 3166-1 alpha-2 country code or a "
               "TARIC-assigned group code, e.g. '1011' for ERGA OMNES (all third countries)",
               "Kennung des Landes oder der Ländergruppe, deren Ursprungswaren einer "
               "TARIC-Maßnahme unterliegen, ausgedrückt als ISO 3166-1-Alpha-2-Ländercode oder "
               "als TARIC-Gruppencode, z. B. '1011' für ERGA OMNES (alle Drittländer)",
               range_=XSD.string)

    _data_prop(g, EUCN.measureTypeId, "measure type ID", "Maßnahmetyp-Kennung",
               "numeric code assigned by TARIC that designates the regulatory category of a "
               "measure, distinguishing between duty types, prohibitions, suspensions, quotas, "
               "and licence requirements, e.g. '103' for Most Favoured Nation ad-valorem duty",
               "von TARIC zugewiesener numerischer Code, der die Regelungskategorie einer "
               "Maßnahme bezeichnet und zwischen Zollarten, Verboten, Aussetzungen, Kontingenten "
               "und Genehmigungspflichten unterscheidet, z. B. '103' für den "
               "Meistbegünstigungs-Wertzollsatz",
               range_=XSD.string)

    _data_prop(g, EUCN.validityStart, "validity start", "Gültigkeitsbeginn",
               "date from which a TARIC measure is in force",
               "Datum, ab dem eine TARIC-Maßnahme in Kraft tritt",
               range_=XSD.date)

    _data_prop(g, EUCN.validityEnd, "validity end", "Gültigkeitsende",
               "date on which a TARIC measure ceases to be in force; absent when the measure "
               "has no fixed expiry",
               "Datum, an dem eine TARIC-Maßnahme außer Kraft tritt; fehlt, wenn die Maßnahme "
               "kein festgelegtes Ablaufdatum hat",
               range_=XSD.date)

    _data_prop(g, EUCN.regulationId, "regulation ID", "Verordnungskennung",
               "identifier of the EU regulation or measure generating regulation that created "
               "or last amended a TARIC measure",
               "Kennung der EU-Verordnung oder der maßnahmenerzeugenden Verordnung, die eine "
               "TARIC-Maßnahme erlassen oder zuletzt geändert hat",
               range_=XSD.string)

    _data_prop(g, EUCN.measureTypeCode, "measure type code", "Maßnahmetyp-Code",
               "numeric string identifying a TARIC measure type, e.g. '103' for third-country "
               "duty or '142' for tariff preference",
               "numerische Zeichenfolge zur Identifizierung eines TARIC-Maßnahmetyps, z. B. "
               "'103' für Drittlandszollsatz oder '142' für Zollpräferenz",
               range_=XSD.string)

    _data_prop(g, EUCN.measureTypeSeries, "measure type series", "Maßnahmetyp-Reihe",
               "single-character series identifier (A–Q) grouping related TARIC measure types "
               "by regulatory function",
               "einstelliger Reihenbezeichner (A–Q), der verwandte TARIC-Maßnahmetypen nach "
               "ihrer Regelungsfunktion zusammenfasst",
               range_=XSD.string)

    _data_prop(g, EUCN.areaCode, "area code", "Gebietskennung",
               "ISO 3166-1 alpha-2 country code or TARIC-assigned group code identifying a "
               "geographic area, e.g. 'DE' for Germany or '1011' for ERGA OMNES",
               "ISO 3166-1 Alpha-2-Ländercode oder TARIC-Gruppencode zur Identifizierung eines "
               "geografischen Gebiets, z. B. 'DE' für Deutschland oder '1011' für ERGA OMNES",
               range_=XSD.string)

    _data_prop(g, EUCN.footnoteCode, "footnote code", "Fußnotencode",
               "TN-prefix code uniquely identifying a TARIC footnote, e.g. 'TN207'",
               "TN-Präfix-Code zur eindeutigen Identifizierung einer TARIC-Fußnote, "
               "z. B. 'TN207'",
               range_=XSD.string)

    _data_prop(g, EUCN.conditionCode, "condition code", "Bedingungscode",
               "single-character code identifying the type of a measure condition, "
               "e.g. 'B' for document presentation or 'E' for quantity threshold",
               "einstelliger Code zur Identifizierung des Typs einer Maßnahmebedingung, "
               "z. B. 'B' für Dokumentenvorlage oder 'E' für Mengenschwellenwert",
               range_=XSD.string)

    _data_prop(g, EUCN.additionalCodeValue, "additional code value", "Zusatzcode-Wert",
               "four-character TARIC additional code string, e.g. 'X301' for the low-alcohol "
               "excise category",
               "vierstellige TARIC-Zusatzcode-Zeichenfolge, z. B. 'X301' für die "
               "Verbrauchsteuerkategorie Alkoholarme Getränke",
               range_=XSD.string)

    _data_prop(g, EUCN.quotaOrderNumber, "quota order number", "Kontingentordnungsnummer",
               "six-digit quota order number gating a preferential tariff rate under a TARIC "
               "tariff quota measure",
               "sechsstellige Kontingentordnungsnummer, die einen Präferenzzollsatz im Rahmen "
               "einer TARIC-Tarifkontingenmaßnahme bedingt",
               range_=XSD.string)

    _data_prop(g, EUCN.regulationRef, "regulation reference", "Verordnungsreferenz",
               "official journal reference or regulation code of the legal act underlying a "
               "TARIC measure, e.g. 'R2658/87'",
               "Amtsblatt-Fundstelle oder Verordnungscode des einer TARIC-Maßnahme zugrunde "
               "liegenden Rechtsakts, z. B. 'R2658/87'",
               range_=XSD.string)

    return g
