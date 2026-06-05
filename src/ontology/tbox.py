from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from src.ontology.namespaces import CUSTOMS, DCTERMS


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


def build_tbox(graph: Graph) -> Graph:
    """Add all TBox triples to graph. Idempotent."""
    g = graph
    g.bind("customs", CUSTOMS)
    g.bind("owl", OWL)
    g.bind("skos", SKOS)
    g.bind("dcterms", DCTERMS)

    # Ontology declaration
    ont = CUSTOMS[""]
    g.add((ont, RDF.type, OWL.Ontology))

    # ── Classes ────────────────────────────────────────────────────────────
    _class(g, CUSTOMS.CNCode, "CN Code", "KN-Code",
           "commodity nomenclature code of eight digits assigned within the "
           "Combined Nomenclature of the European Union for the classification of goods in "
           "international trade",
           "Warenpositionsnummer aus acht Stellen, die innerhalb der Kombinierten "
           "Nomenklatur der Europäischen Union zur Einreihung von Waren im internationalen Handel "
           "vergeben wird")

    _class(g, CUSTOMS.TARICCode, "TARIC Code", "TARIC-Code",
           "ten-digit extension of a CN code within the Integrated Tariff of the European "
           "Communities that specifies the applicable regulatory measures at the most granular "
           "commodity level",
           "Zehnstellige Erweiterung eines KN-Codes im Integrierten Zolltarif der Europäischen "
           "Gemeinschaften, die die anwendbaren Regelungsmaßnahmen auf der detailliertesten "
           "Warenebene festlegt")
    g.add((CUSTOMS.TARICCode, RDFS.subClassOf, CUSTOMS.CNCode))

    _class(g, CUSTOMS.TARICMeasure, "TARIC Measure", "TARIC-Maßnahme",
           "regulatory instrument of the Integrated Tariff of the European Communities that "
           "specifies a tariff rate, restriction, suspension, quota, or licensing condition "
           "applicable to goods identified by a CN or TARIC code, valid within a defined "
           "geographical and temporal scope",
           "Regelungsinstrument des Integrierten Zolltarifs der Europäischen Gemeinschaften, "
           "das einen Zollsatz, eine Beschränkung, eine Aussetzung, ein Kontingent oder eine "
           "Genehmigungspflicht für Waren festlegt, die durch einen KN- oder TARIC-Code "
           "identifiziert werden, gültig innerhalb eines bestimmten geografischen und zeitlichen "
           "Geltungsbereichs")

    _class(g, CUSTOMS.ClassificationNode, "Classification Node", "Einreihungsknoten",
           "step in a sequential commodity classification procedure that poses a single "
           "discriminating question to narrow the applicable nomenclature position; sourced "
           "from the EZT-Online advisory wizard and carrying advisory status only, not "
           "constituting a legally binding EU instrument",
           "Schritt in einem sequenziellen Wareneinreihungsverfahren, der eine einzelne "
           "unterscheidende Frage stellt, um die zutreffende Nomenklaturposition einzugrenzen; "
           "bezogen auf den Beratungsassistenten EZT-Online und ohne rechtsbindende Wirkung "
           "als EU-Instrument")

    _class(g, CUSTOMS.Chapter, "Chapter", "Kapitel",
           "two-digit subdivision of the Harmonized System nomenclature that groups goods "
           "sharing a common material composition, functional category, or industrial origin",
           "zweistellige Unterteilung der Nomenklatur des Harmonisierten Systems, die Waren "
           "mit gemeinsamer Materialzusammensetzung, funktionaler Kategorie oder industriellem "
           "Ursprung zusammenfasst")

    _class(g, CUSTOMS.Heading, "Heading", "Position",
           "four-digit subdivision of the Harmonized System nomenclature that identifies a "
           "specific group of goods within a chapter by further differentiating on material, "
           "process, or use",
           "vierstellige Unterteilung der Nomenklatur des Harmonisierten Systems, die eine "
           "bestimmte Warengruppe innerhalb eines Kapitels durch weitere Differenzierung nach "
           "Material, Verarbeitungsstufe oder Verwendungszweck identifiziert")

    # ── Object properties ──────────────────────────────────────────────────
    _obj_prop(g, CUSTOMS.classifiesAs, "classifies as", "wird eingereiht als",
              "relation between a terminal classification node and the CN code to which goods "
              "are assigned upon completion of the sequential classification procedure initiated "
              "at the root node",
              "Beziehung zwischen einem terminalen Einreihungsknoten und dem KN-Code, unter den "
              "Waren nach Abschluss des sequenziellen Einreihungsverfahrens, das am Wurzelknoten "
              "beginnt, eingereiht werden",
              domain=CUSTOMS.ClassificationNode, range_=CUSTOMS.CNCode)

    _obj_prop(g, CUSTOMS.hasAnswer, "has answer", "hat Antwort",
              "relation between a classification node and a subsequent classification node "
              "reached by selecting a particular answer to the discriminating question posed at "
              "the source node",
              "Beziehung zwischen einem Einreihungsknoten und einem nachfolgenden "
              "Einreihungsknoten, der durch Auswahl einer bestimmten Antwort auf die am "
              "Ausgangsknoten gestellte unterscheidende Frage erreicht wird",
              domain=CUSTOMS.ClassificationNode, range_=CUSTOMS.ClassificationNode)

    _obj_prop(g, CUSTOMS.hasMeasure, "has measure", "hat Maßnahme",
              "relation between a CN code and a TARIC measure under which goods classified by "
              "that CN code are subject to the regulatory conditions specified by the measure",
              "Beziehung zwischen einem KN-Code und einer TARIC-Maßnahme, deren "
              "Regelungsbedingungen für Waren gelten, die unter diesen KN-Code eingereiht sind",
              domain=CUSTOMS.CNCode, range_=CUSTOMS.TARICMeasure)

    _obj_prop(g, CUSTOMS.belongsToChapter, "belongs to chapter", "gehört zu Kapitel",
              "relation between a CN code and the two-digit Harmonized System chapter in whose "
              "nomenclature scope the code is situated",
              "Beziehung zwischen einem KN-Code und dem zweistelligen Kapitel des Harmonisierten "
              "Systems, in dessen Nomenklaturgeltungsbereich der Code fällt",
              domain=CUSTOMS.CNCode, range_=CUSTOMS.Chapter)

    # ── Data properties ────────────────────────────────────────────────────
    _data_prop(g, CUSTOMS.codeString, "code string", "Codenummer",
               "digit string uniquely identifying a nomenclature position without separating "
               "punctuation, derived by concatenating the numeric segments of the code, "
               "e.g. '22042100' for CN code 2204 21 00",
               "Ziffernfolge, die eine Nomenklaturstelle ohne Trennzeichen eindeutig "
               "identifiziert, gebildet durch Aneinanderreihung der numerischen Segmente des "
               "Codes, z. B. '22042100' für KN-Code 2204 21 00",
               range_=XSD.string)

    _data_prop(g, CUSTOMS.description, "description", "Warenbezeichnung",
               "official textual designation of a commodity as established in the legal text of "
               "the Combined Nomenclature, expressed in a specified natural language and carrying "
               "legal force within EU customs classification",
               "amtliche Warenbezeichnung, wie sie im Rechtstext der Kombinierten Nomenklatur "
               "festgelegt ist, in einer bestimmten natürlichen Sprache und mit rechtlicher "
               "Wirkung innerhalb der EU-Zolleinreihung",
               range_=XSD.string)

    _data_prop(g, CUSTOMS.questionText, "question text", "Fragetext",
               "textual formulation of the discriminating question posed at a classification "
               "node in the EZT-Online wizard, expressed in a specified natural language, used "
               "to guide the classifier toward the applicable nomenclature branch",
               "textliche Formulierung der unterscheidenden Frage, die an einem "
               "Einreihungsknoten des EZT-Online-Assistenten gestellt wird, in einer bestimmten "
               "natürlichen Sprache, zur Führung des Einreihenden zur zutreffenden "
               "Nomenklaturstelle",
               range_=XSD.string)

    _data_prop(g, CUSTOMS.answerText, "answer text", "Antworttext",
               "textual formulation of the answer option that, when selected at a parent "
               "classification node, determines the transition to this classification node in "
               "the sequential classification procedure",
               "textliche Formulierung der Antwortoption, die bei Auswahl an einem "
               "übergeordneten Einreihungsknoten den Übergang zu diesem Einreihungsknoten im "
               "sequenziellen Einreihungsverfahren bestimmt",
               range_=XSD.string)

    _data_prop(g, CUSTOMS.dutyRate, "duty rate", "Zollsatz",
               "textual expression of the duty or charge rate applicable under a TARIC measure "
               "as published in the TARIC bulk data, combining a numeric value with a unit of "
               "measurement, e.g. '12.0 %' or '32.0 EUR/hl'",
               "textliche Darstellung des Zoll- oder Abgabensatzes, der im Rahmen einer "
               "TARIC-Maßnahme gilt, wie in den TARIC-Massendaten veröffentlicht, bestehend "
               "aus einem numerischen Wert und einer Maßeinheit, z. B. '12,0 %' oder "
               "'32,0 EUR/hl'",
               range_=XSD.string)

    _data_prop(g, CUSTOMS.dutyAmount, "duty amount", "Zollbetrag",
               "numeric value of the duty or charge rate applicable under a TARIC measure",
               "numerischer Wert des Zoll- oder Abgabensatzes im Rahmen einer TARIC-Maßnahme",
               range_=XSD.decimal)

    _data_prop(g, CUSTOMS.geographicScope, "geographic scope", "geografischer Geltungsbereich",
               "identifier of the country or country group to whose originating goods a TARIC "
               "measure applies, expressed as an ISO 3166-1 alpha-2 country code or a "
               "TARIC-assigned group code, e.g. '1011' for ERGA OMNES (all third countries)",
               "Kennung des Landes oder der Ländergruppe, deren Ursprungswaren einer "
               "TARIC-Maßnahme unterliegen, ausgedrückt als ISO 3166-1-Alpha-2-Ländercode oder "
               "als TARIC-Gruppencode, z. B. '1011' für ERGA OMNES (alle Drittländer)",
               range_=XSD.string)

    _data_prop(g, CUSTOMS.measureTypeId, "measure type ID", "Maßnahmetyp-Kennung",
               "numeric code assigned by TARIC that designates the regulatory category of a "
               "measure, distinguishing between duty types, prohibitions, suspensions, quotas, "
               "and licence requirements, e.g. '103' for Most Favoured Nation ad-valorem duty",
               "von TARIC zugewiesener numerischer Code, der die Regelungskategorie einer "
               "Maßnahme bezeichnet und zwischen Zollarten, Verboten, Aussetzungen, Kontingenten "
               "und Genehmigungspflichten unterscheidet, z. B. '103' für den "
               "Meistbegünstigungs-Wertzollsatz",
               range_=XSD.string)

    _data_prop(g, CUSTOMS.validityStart, "validity start", "Gültigkeitsbeginn",
               "date from which a TARIC measure is in force",
               "Datum, ab dem eine TARIC-Maßnahme in Kraft tritt",
               range_=XSD.date)

    _data_prop(g, CUSTOMS.validityEnd, "validity end", "Gültigkeitsende",
               "date on which a TARIC measure ceases to be in force; absent when the measure "
               "has no fixed expiry",
               "Datum, an dem eine TARIC-Maßnahme außer Kraft tritt; fehlt, wenn die Maßnahme "
               "kein festgelegtes Ablaufdatum hat",
               range_=XSD.date)

    _data_prop(g, CUSTOMS.regulationId, "regulation ID", "Verordnungskennung",
               "identifier of the EU regulation or measure generating regulation that created "
               "or last amended a TARIC measure",
               "Kennung der EU-Verordnung oder der maßnahmenerzeugenden Verordnung, die eine "
               "TARIC-Maßnahme erlassen oder zuletzt geändert hat",
               range_=XSD.string)

    return g
