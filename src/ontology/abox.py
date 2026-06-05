from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from src.ontology.iri import (
    chapter_iri,
    classification_node_iri,
    cn_code_iri,
    heading_iri,
    taric_measure_iri,
)
from src.ontology.namespaces import CUSTOMS, DCTERMS
from src.schema.taric import ChapterData, TARICMeasure
from src.schema.wizard import ClassificationNode, WizardTree

EZT_SOURCE = "https://auskunft.ezt-online.de/ezto/SeqEinreihungSucheAnzeige.do"
ADVISORY_DISCLAIMER = (
    "Advisory tool only. Classification paths sourced from EZT-Online do not "
    "constitute legally binding EU instruments."
)


def _add_measure(g: Graph, measure: TARICMeasure) -> URIRef:
    iri = taric_measure_iri(measure.sid)
    g.add((iri, RDF.type, CUSTOMS.TARICMeasure))
    g.add((iri, CUSTOMS.codeString, Literal(measure.commodity_code, datatype=XSD.string)))
    g.add((iri, CUSTOMS.measureTypeId, Literal(measure.measure_type_id, datatype=XSD.string)))
    g.add((iri, CUSTOMS.geographicScope, Literal(measure.geographical_area_id, datatype=XSD.string)))
    g.add((iri, CUSTOMS.validityStart, Literal(measure.validity_start.isoformat(), datatype=XSD.date)))
    if measure.validity_end is not None:
        g.add((iri, CUSTOMS.validityEnd, Literal(measure.validity_end.isoformat(), datatype=XSD.date)))
    g.add((iri, CUSTOMS.regulationId, Literal(measure.regulation_id, datatype=XSD.string)))

    for comp in measure.components:
        if comp.duty_amount is not None:
            g.add((iri, CUSTOMS.dutyAmount, Literal(comp.duty_amount, datatype=XSD.decimal)))
            # Build human-readable duty rate string
            parts = [str(comp.duty_amount)]
            if comp.monetary_unit:
                parts.append(comp.monetary_unit)
            elif comp.measurement_unit:
                parts.append(comp.measurement_unit)
            else:
                parts.append("%")
            g.add((iri, CUSTOMS.dutyRate, Literal(" ".join(parts), datatype=XSD.string)))

    return iri


def _ensure_cn_code(g: Graph, code: str, cn_iris: dict[str, URIRef]) -> URIRef:
    if code in cn_iris:
        return cn_iris[code]
    iri = cn_code_iri(code)
    cn_iris[code] = iri
    g.add((iri, RDF.type, CUSTOMS.CNCode))
    g.add((iri, CUSTOMS.codeString, Literal(code, datatype=XSD.string)))
    # Hierarchy: chapter + heading
    if len(code) >= 2:
        ch = chapter_iri(int(code[:2]))
        g.add((ch, RDF.type, CUSTOMS.Chapter))
        g.add((iri, CUSTOMS.belongsToChapter, ch))
    return iri


def _add_node(g: Graph, node: ClassificationNode,
              all_nodes: dict[str, ClassificationNode],
              cn_iris: dict[str, URIRef]) -> None:
    iri = classification_node_iri(node.path_from_root)
    g.add((iri, RDF.type, CUSTOMS.ClassificationNode))
    if node.question_text:
        g.add((iri, CUSTOMS.questionText, Literal(node.question_text, datatype=XSD.string)))
    g.add((iri, RDFS.comment, Literal(ADVISORY_DISCLAIMER)))
    g.add((iri, DCTERMS.source, URIRef(EZT_SOURCE)))

    if node.is_terminal and node.cn_code:
        cn_iri = _ensure_cn_code(g, node.cn_code, cn_iris)
        g.add((iri, CUSTOMS.classifiesAs, cn_iri))

    for opt in node.answer_options:
        if opt.next_node_id and opt.next_node_id in all_nodes:
            next_node = all_nodes[opt.next_node_id]
            next_iri = classification_node_iri(next_node.path_from_root)
            g.add((iri, CUSTOMS.hasAnswer, next_iri))


def build_abox(
    chapter_data: ChapterData,
    wizard_tree: WizardTree,
    graph: Graph,
) -> Graph:
    """Populate ABox from intermediate JSON. Idempotent."""
    g = graph
    g.bind("customs", CUSTOMS)
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
            g.add((cn_iri, CUSTOMS.hasMeasure, m_iri))

    # Wizard nodes
    for node in wizard_tree.nodes.values():
        _add_node(g, node, wizard_tree.nodes, cn_iris)

    return g
