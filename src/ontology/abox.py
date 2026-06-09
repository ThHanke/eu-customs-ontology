from __future__ import annotations

import re
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from src.ontology.iri import (
    additional_code_iri,
    certificate_iri,
    chapter_iri,
    classification_node_iri,
    cn_code_iri,
    duty_expression_iri,
    footnote_iri,
    geographic_area_iri,
    heading_iri,
    measure_condition_iri,
    measure_type_iri,
    regulation_iri,
    taric_measure_iri,
)
from src.ontology.namespaces import DCTERMS, EUCN
from src.ontology.chapter_registry import get_chapter
from src.ontology.wizard_axioms import WizardAxiomCoverage, transform
from src.schema.taric import (
    AdditionalCodeRecord,
    ChapterData,
    FootnoteRecord,
    MeasureConditionRecord,
    MeasureTypeRecord,
    GeographicAreaRecord,
    DutyExpressionRecord,
    RegulationRecord,
    TARICMeasure,
)
from src.schema.wizard import ClassificationNode, WizardTree

_HTML_TAGS = re.compile(r"<[^>]+>")

EZT_SOURCE = "https://auskunft.ezt-online.de/ezto/SeqEinreihungSucheAnzeige.do"
ADVISORY_DISCLAIMER = (
    "Advisory tool only. Classification paths sourced from EZT-Online do not "
    "constitute legally binding EU instruments."
)


def _strip_html(text: str) -> str:
    return _HTML_TAGS.sub("", text).strip()


def _ensure_measure_type(g: Graph, mt: MeasureTypeRecord) -> URIRef:
    iri = measure_type_iri(mt.code)
    g.add((iri, RDF.type, EUCN.MeasureType))
    g.add((iri, EUCN.measureTypeCode, Literal(mt.code, datatype=XSD.string)))
    if mt.description:
        g.add((iri, RDFS.label, Literal(mt.description, lang="en")))
    if mt.series_id:
        g.add((iri, EUCN.measureTypeSeries, Literal(mt.series_id, datatype=XSD.string)))
    return iri


def _ensure_geographic_area(g: Graph, area: GeographicAreaRecord) -> URIRef:
    iri = geographic_area_iri(area.code)
    g.add((iri, RDF.type, EUCN.GeographicArea))
    g.add((iri, EUCN.areaCode, Literal(area.code, datatype=XSD.string)))
    if area.description:
        g.add((iri, RDFS.label, Literal(area.description, lang="en")))
    return iri


def _ensure_footnote(g: Graph, fn: FootnoteRecord) -> URIRef:
    iri = footnote_iri(fn.code)
    g.add((iri, RDF.type, EUCN.Footnote))
    g.add((iri, EUCN.footnoteCode, Literal(fn.code, datatype=XSD.string)))
    if fn.description:
        g.add((iri, SKOS.definition, Literal(_strip_html(fn.description), lang="en")))
    return iri


def _ensure_certificate(g: Graph, doc_code: str) -> URIRef:
    iri = certificate_iri(doc_code)
    g.add((iri, RDF.type, EUCN.Certificate))
    g.add((iri, RDFS.label, Literal(doc_code, lang="en")))
    return iri


def _ensure_regulation(g: Graph, reg: RegulationRecord) -> URIRef:
    iri = regulation_iri(reg.regulation_id)
    g.add((iri, RDF.type, EUCN.Regulation))
    if reg.regulation_code:
        g.add((iri, EUCN.regulationRef, Literal(reg.regulation_code, datatype=XSD.string)))
    if reg.description:
        g.add((iri, RDFS.label, Literal(reg.description, lang="en")))
    if reg.regulation_url:
        g.add((iri, RDFS.seeAlso, URIRef(reg.regulation_url)))
    return iri


def _add_duty_expression(g: Graph, measure_iri: URIRef, duty: DutyExpressionRecord,
                         measure_sid: str) -> URIRef:
    iri = duty_expression_iri(measure_sid)
    g.add((iri, RDF.type, EUCN.DutyExpression))
    if duty.base:
        g.add((iri, EUCN.dutyRate, Literal(duty.base, datatype=XSD.string)))
    if duty.verbose_duty:
        g.add((iri, RDFS.label, Literal(duty.verbose_duty, lang="en")))
    g.add((measure_iri, EUCN.hasDutyExpression, iri))
    return iri


def _add_measure_condition(g: Graph, measure_iri: URIRef,
                            cond: MeasureConditionRecord) -> URIRef:
    iri = measure_condition_iri(cond.sid)
    g.add((iri, RDF.type, EUCN.MeasureCondition))
    if cond.condition_code:
        g.add((iri, EUCN.conditionCode, Literal(cond.condition_code, datatype=XSD.string)))
    if cond.document_code:
        cert_iri = _ensure_certificate(g, cond.document_code)
        g.add((iri, EUCN.hasCertificate, cert_iri))
    if cond.condition_duty_amount is not None:
        g.add((iri, EUCN.dutyAmount, Literal(cond.condition_duty_amount, datatype=XSD.decimal)))
    if cond.condition_measurement_unit_code:
        g.add((iri, EUCN.measureTypeCode,
               Literal(cond.condition_measurement_unit_code, datatype=XSD.string)))
    g.add((measure_iri, EUCN.hasCondition, iri))
    return iri


def _ensure_additional_code(g: Graph, ac: AdditionalCodeRecord) -> URIRef:
    iri = additional_code_iri(ac.code)
    g.add((iri, RDF.type, EUCN.AdditionalCode))
    g.add((iri, EUCN.additionalCodeValue, Literal(ac.code, datatype=XSD.string)))
    if ac.description:
        g.add((iri, RDFS.label, Literal(ac.description, lang="en")))
    return iri


def _add_measure(g: Graph, measure: TARICMeasure) -> URIRef:
    iri = taric_measure_iri(measure.sid)
    g.add((iri, RDF.type, EUCN.TARICMeasure))
    g.add((iri, EUCN.codeString, Literal(measure.commodity_code, datatype=XSD.string)))
    g.add((iri, EUCN.measureTypeId, Literal(measure.measure_type_id, datatype=XSD.string)))
    g.add((iri, EUCN.geographicScope, Literal(measure.geographical_area_id, datatype=XSD.string)))
    g.add((iri, EUCN.validityStart, Literal(measure.validity_start.isoformat(), datatype=XSD.date)))
    if measure.validity_end is not None:
        g.add((iri, EUCN.validityEnd, Literal(measure.validity_end.isoformat(), datatype=XSD.date)))
    g.add((iri, EUCN.regulationId, Literal(measure.regulation_id, datatype=XSD.string)))

    # Legacy flat components (XLSX source)
    for comp in measure.components:
        if comp.duty_amount is not None:
            g.add((iri, EUCN.dutyAmount, Literal(comp.duty_amount, datatype=XSD.decimal)))
            parts = [str(comp.duty_amount)]
            if comp.monetary_unit:
                parts.append(comp.monetary_unit)
            elif comp.measurement_unit:
                parts.append(comp.measurement_unit)
            else:
                parts.append("%")
            g.add((iri, EUCN.dutyRate, Literal(" ".join(parts), datatype=XSD.string)))

    # Rich entity graph (UK API source)
    if measure.measure_type is not None:
        mt_iri = _ensure_measure_type(g, measure.measure_type)
        g.add((iri, EUCN.hasMeasureType, mt_iri))

    if measure.geographical_area is not None:
        ga_iri = _ensure_geographic_area(g, measure.geographical_area)
        g.add((iri, EUCN.hasGeographicArea, ga_iri))

    if measure.duty_expression is not None:
        _add_duty_expression(g, iri, measure.duty_expression, measure.sid)

    for fn in measure.footnotes:
        fn_iri = _ensure_footnote(g, fn)
        g.add((iri, EUCN.hasFootnote, fn_iri))

    for cond in measure.conditions:
        _add_measure_condition(g, iri, cond)

    for reg in measure.regulations:
        reg_iri = _ensure_regulation(g, reg)
        g.add((iri, EUCN.hasRegulation, reg_iri))

    for ac in measure.additional_codes:
        ac_iri = _ensure_additional_code(g, ac)
        g.add((iri, EUCN.hasAdditionalCode, ac_iri))

    if measure.quota_order_number is not None:
        g.add((iri, EUCN.quotaOrderNumber,
               Literal(measure.quota_order_number, datatype=XSD.string)))

    if measure.is_uk_only:
        g.add((iri, EUCN.isUKOnlyMeasure, Literal(True, datatype=XSD.boolean)))

    return iri


def _ensure_cn_code(g: Graph, code: str, cn_iris: dict[str, URIRef]) -> URIRef:
    if code in cn_iris:
        return cn_iris[code]
    iri = cn_code_iri(code)
    cn_iris[code] = iri
    g.add((iri, RDF.type, EUCN.CNCode))
    g.add((iri, EUCN.codeString, Literal(code, datatype=XSD.string)))
    # Hierarchy: chapter + heading
    if len(code) >= 2:
        ch = chapter_iri(int(code[:2]))
        g.add((ch, RDF.type, EUCN.Chapter))
        g.add((iri, EUCN.belongsToChapter, ch))
    if len(code) >= 4:
        hd = heading_iri(code[:4])
        g.add((hd, RDF.type, EUCN.Heading))
        g.add((iri, EUCN.belongsToHeading, hd))
    return iri


def _add_node(g: Graph, node: ClassificationNode,
              all_nodes: dict[str, ClassificationNode],
              cn_iris: dict[str, URIRef]) -> None:
    iri = classification_node_iri(node.path_from_root)
    g.add((iri, RDF.type, EUCN.ClassificationNode))
    if node.question_text:
        g.add((iri, EUCN.questionText, Literal(node.question_text, datatype=XSD.string)))
    g.add((iri, RDFS.comment, Literal(ADVISORY_DISCLAIMER)))
    g.add((iri, DCTERMS.source, URIRef(EZT_SOURCE)))

    if node.is_terminal and node.cn_code:
        cn_iri = _ensure_cn_code(g, node.cn_code, cn_iris)
        g.add((iri, EUCN.classifiesAs, cn_iri))

    for opt in node.answer_options:
        if opt.next_node_id and opt.next_node_id in all_nodes:
            next_node = all_nodes[opt.next_node_id]
            next_iri = classification_node_iri(next_node.path_from_root)
            g.add((iri, EUCN.hasAnswer, next_iri))


def build_abox(
    chapter_data: ChapterData,
    wizard_tree: WizardTree,
    graph: Graph,
) -> tuple[Graph, WizardAxiomCoverage]:
    """Populate ABox from intermediate JSON. Idempotent.

    Returns (graph, coverage_report).
    """
    g = graph
    g.bind("eucn", EUCN)
    g.bind("dcterms", DCTERMS)
    g.bind("skos", SKOS)

    cn_iris: dict[str, URIRef] = {}

    # Measures
    measure_by_code: dict[str, list[URIRef]] = {}
    for measure in chapter_data.measures:
        m_iri = _add_measure(g, measure)
        measure_by_code.setdefault(measure.commodity_code, []).append(m_iri)

    # CN codes from TARIC measures
    for code, m_iris in measure_by_code.items():
        cn_iri = _ensure_cn_code(g, code, cn_iris)
        for m_iri in m_iris:
            g.add((cn_iri, EUCN.hasMeasure, m_iri))

    # Wizard nodes
    for node in wizard_tree.nodes.values():
        _add_node(g, node, wizard_tree.nodes, cn_iris)

    # Wizard-to-axiom transform
    wizard_triples, coverage = transform(wizard_tree)
    for triple in wizard_triples:
        g.add(triple)

    # Curated equivalence axioms: hand-authored always applied; approved registry candidates additive
    chapter_module = get_chapter(wizard_tree.chapter)
    if chapter_module.add_equivalence_axioms is not None:
        chapter_module.add_equivalence_axioms(g)

    registry_path = Path(__file__).parent.parent.parent / "data" / "axiom_candidates" / f"ch{wizard_tree.chapter:02d}.jsonl"
    if registry_path.exists():
        from src.agent.candidate_registry import CandidateRegistry
        from src.agent.axiom_builder import build_equivalence_axioms_from_candidates
        registry = CandidateRegistry(registry_path)
        registry.load()
        approved = [c for c in registry.get_active() if c.status == "approved"]
        if approved:
            build_equivalence_axioms_from_candidates(g, approved)

    # Node registry (LLM agent output) — additive on top of hand-authored
    node_registry_dir = (
        Path(__file__).parent.parent.parent
        / "data"
        / "axiom_candidates"
        / f"ch{wizard_tree.chapter:02d}"
    )
    if node_registry_dir.exists():
        from src.agent.node_registry import NodeRegistry
        from src.agent.axiom_builder import build_graph_from_node_axiom_set
        node_registry = NodeRegistry(node_registry_dir)
        for axiom_set in node_registry.iter_all():
            if axiom_set.status == "approved":
                build_graph_from_node_axiom_set(g, axiom_set)

    return g, coverage
