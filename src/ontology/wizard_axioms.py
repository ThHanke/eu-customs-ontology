"""Wizard-to-axiom transformer: converts WizardTree into OWL 2 DL equivalence axioms.

Purely functional — no side effects, no NLP, no LLM.
Three question-type tiers (detection order: quantitative > boolean > fallback).
"""
from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict
from rdflib import BNode, Graph, Literal as RLiteral, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from src.ontology.iri import cn_code_iri, mint_iri
from src.schema.wizard import ClassificationNode, WizardTree

# regex: comparator keyword + numeric value + unit
_QUANT_RE = re.compile(
    r"(mehr als|mindestens|höchstens|weniger als|bis unter|über|unter)"
    r"\s*([\d]+(?:[,.][\d]+)?)\s*"
    r"(%\s*vol|vol\.?-?%|%|[lL]iter|Liter|kg)",
    re.IGNORECASE,
)

_COMPARATOR_FACET_JA: dict[str, URIRef] = {
    "mehr als": XSD.minExclusive,
    "über": XSD.minExclusive,
    "mindestens": XSD.minInclusive,
    "höchstens": XSD.maxInclusive,
    "weniger als": XSD.maxExclusive,
    "bis unter": XSD.maxExclusive,
    "unter": XSD.maxExclusive,
}

_FLIP_FACET: dict[URIRef, URIRef] = {
    XSD.minExclusive: XSD.maxInclusive,
    XSD.minInclusive: XSD.maxExclusive,
    XSD.maxInclusive: XSD.minExclusive,
    XSD.maxExclusive: XSD.minInclusive,
}

Triple = tuple[URIRef | BNode, URIRef, URIRef | BNode | RLiteral]


class QuestionAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_text: str
    property_iri: str
    tier: Literal["boolean", "quantitative", "fallback"]
    regex_match: str | None = None
    extracted_threshold: float | None = None
    extracted_facet: str | None = None
    cn_codes_affected: list[str]
    success: bool
    failure_reason: str | None = None


class WizardAxiomCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapter: int
    total_terminal_nodes: int
    covered_boolean: int
    covered_quantitative: int
    fallback_count: int
    coverage_pct: float
    questions: list[QuestionAnalysis]


def _bnode(key: str) -> BNode:
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return BNode(h)


def _build_rdf_list(g: Graph, items: list[BNode | URIRef], key: str) -> BNode:
    """Build an RDF list from items and return the head BNode."""
    if not items:
        return RDF.nil  # type: ignore[return-value]
    head = _bnode(f"list_head:{key}")
    current = head
    for i, item in enumerate(items):
        next_key = f"list_next:{key}:{i}"
        rest = _bnode(next_key) if i < len(items) - 1 else RDF.nil
        g.add((current, RDF.first, item))
        g.add((current, RDF.rest, rest))
        if i < len(items) - 1:
            current = rest
    return head


def _prop_iri(question_text: str) -> URIRef:
    return mint_iri(f"wizardQ:{question_text.strip()}")


def _classify_question(
    question_text: str, answer_text: str, cn_code: str
) -> tuple[QuestionAnalysis, BNode | None]:
    """Classify a wizard question and produce OWL restriction triples.

    Returns (QuestionAnalysis, restriction_bnode).
    restriction_bnode is None for fallback tier.
    """
    prop = _prop_iri(question_text)
    prop_str = str(prop)
    answer_lower = answer_text.strip().lower()
    is_yes = answer_lower in {"ja", "yes"}
    is_no = answer_lower in {"nein", "no"}

    # Tier 2: quantitative (checked before boolean because threshold questions
    # are often answered with Ja/Nein — the polarity comes from the answer)
    m = _QUANT_RE.search(question_text)
    if m:
        comparator = m.group(1).lower()
        raw_value = m.group(2).replace(",", ".")
        try:
            threshold = float(raw_value)
        except ValueError:
            pass
        else:
            facet_ja = _COMPARATOR_FACET_JA.get(comparator)
            if facet_ja is not None:
                if is_no:
                    facet = _FLIP_FACET[facet_ja]
                else:
                    facet = facet_ja
                facet_local = str(facet).rsplit("#", 1)[-1]

                restr_key = f"restr:quant:{prop}:{facet_local}:{threshold}:{cn_code}"
                restr = _bnode(restr_key)

                analysis = QuestionAnalysis(
                    question_text=question_text,
                    property_iri=prop_str,
                    tier="quantitative",
                    regex_match=m.group(0),
                    extracted_threshold=threshold,
                    extracted_facet=facet_local,
                    cn_codes_affected=[cn_code],
                    success=True,
                )
                return analysis, restr

    # Tier 1: boolean
    if is_yes or is_no:
        value = True if is_yes else False
        restr_key = f"restr:bool:{prop}:{value}:{cn_code}"
        restr = _bnode(restr_key)
        analysis = QuestionAnalysis(
            question_text=question_text,
            property_iri=prop_str,
            tier="boolean",
            cn_codes_affected=[cn_code],
            success=True,
        )
        return analysis, restr

    # Tier 3: fallback
    restr_key = f"restr:fallback:{prop}:{answer_text}:{cn_code}"
    restr = _bnode(restr_key)
    analysis = QuestionAnalysis(
        question_text=question_text,
        property_iri=prop_str,
        tier="fallback",
        cn_codes_affected=[cn_code],
        success=False,
        failure_reason=f"answer '{answer_text}' not boolean and no quantitative regex match",
    )
    return analysis, restr


def _add_restriction_triples(
    g: Graph,
    restr: BNode,
    prop: URIRef,
    tier: str,
    answer_text: str,
    threshold: float | None,
    facet_name: str | None,
    restr_key: str,
) -> None:
    """Add the triples for one OWL restriction to g."""
    is_yes = answer_text.strip().lower() in {"ja", "yes"}

    if tier == "quantitative" and threshold is not None and facet_name is not None:
        facet_iri = XSD[facet_name]
        facet_bnode = _bnode(f"facet:{restr_key}")
        g.add((facet_bnode, facet_iri, RLiteral(str(threshold), datatype=XSD.decimal)))

        dtype = _bnode(f"dtype:{restr_key}")
        g.add((dtype, RDF.type, RDFS.Datatype))
        g.add((dtype, OWL.onDatatype, XSD.decimal))
        facet_list = _build_rdf_list(g, [facet_bnode], f"facet_list:{restr_key}")
        g.add((dtype, OWL.withRestrictions, facet_list))

        g.add((restr, RDF.type, OWL.Restriction))
        g.add((restr, OWL.onProperty, prop))
        g.add((restr, OWL.someValuesFrom, dtype))

    elif tier == "boolean":
        value = RLiteral(is_yes, datatype=XSD.boolean)
        g.add((restr, RDF.type, OWL.Restriction))
        g.add((restr, OWL.onProperty, prop))
        g.add((restr, OWL.hasValue, value))

    else:  # fallback
        g.add((restr, RDF.type, OWL.Restriction))
        g.add((restr, OWL.onProperty, prop))
        g.add((restr, OWL.hasValue, RLiteral(answer_text, datatype=XSD.string)))


def _build_parent_map(tree: WizardTree) -> dict[str, tuple[str, str]]:
    """Build {child_node_id: (parent_node_id, answer_text)} map."""
    parent_map: dict[str, tuple[str, str]] = {}
    for node in tree.nodes.values():
        for opt in node.answer_options:
            if opt.next_node_id:
                parent_map[opt.next_node_id] = (node.node_id, opt.answer_text)
    return parent_map


def _path_steps(
    tree: WizardTree,
    terminal_id: str,
    parent_map: dict[str, tuple[str, str]],
) -> list[tuple[ClassificationNode, str]]:
    """Return [(parent_node, answer_text)] from root to terminal (inclusive)."""
    steps: list[tuple[ClassificationNode, str]] = []
    current = terminal_id
    while current in parent_map:
        parent_id, answer_text = parent_map[current]
        steps.append((tree.nodes[parent_id], answer_text))
        current = parent_id
    steps.reverse()
    return steps


def transform(tree: WizardTree) -> tuple[list[Triple], WizardAxiomCoverage]:
    """Transform a WizardTree into OWL equivalence axioms and a coverage report.

    Pure function — no graph mutations. Returns (triples, coverage).
    Deterministic: same input → same output.
    """
    g = Graph()
    all_analyses: list[QuestionAnalysis] = []
    parent_map = _build_parent_map(tree)

    terminal_nodes = [
        n for n in tree.nodes.values() if n.is_terminal and n.cn_code
    ]

    for terminal in terminal_nodes:
        cn_code = terminal.cn_code
        assert cn_code is not None
        cn_iri = cn_code_iri(cn_code)
        steps = _path_steps(tree, terminal.node_id, parent_map)

        restrictions: list[BNode] = []
        for parent_node, answer_text in steps:
            question_text = parent_node.question_text
            analysis, restr = _classify_question(question_text, answer_text, cn_code)
            all_analyses.append(analysis)

            if restr is not None:
                prop = URIRef(analysis.property_iri)
                _add_restriction_triples(
                    g, restr, prop,
                    analysis.tier, answer_text,
                    analysis.extracted_threshold, analysis.extracted_facet,
                    f"restr:{analysis.tier}:{prop}:{answer_text}:{cn_code}",
                )
                # Declare the property
                if analysis.tier == "fallback":
                    g.add((prop, RDF.type, OWL.AnnotationProperty))
                else:
                    g.add((prop, RDF.type, OWL.DatatypeProperty))
                    if analysis.tier == "boolean":
                        g.add((prop, RDFS.range, XSD.boolean))
                    else:
                        g.add((prop, RDFS.range, XSD.decimal))
                g.add((prop, RDFS.label, RLiteral(question_text[:200], lang="de")))
                restrictions.append(restr)

        if not restrictions:
            continue

        # Build owl:equivalentClass [owl:intersectionOf (restr1 restr2 ...)]
        inter_key = f"inter:{cn_code}"
        inter = _bnode(inter_key)
        g.add((inter, RDF.type, OWL.Class))
        list_head = _build_rdf_list(g, restrictions, inter_key)
        g.add((inter, OWL.intersectionOf, list_head))
        g.add((cn_iri, OWL.equivalentClass, inter))

    # Coverage report
    total_q = len(all_analyses)
    n_bool = sum(1 for a in all_analyses if a.tier == "boolean")
    n_quant = sum(1 for a in all_analyses if a.tier == "quantitative")
    n_fall = sum(1 for a in all_analyses if a.tier == "fallback")
    coverage_pct = 100.0 if total_q == 0 else (n_bool + n_quant) / total_q * 100.0

    coverage = WizardAxiomCoverage(
        chapter=tree.chapter,
        total_terminal_nodes=len(terminal_nodes),
        covered_boolean=n_bool,
        covered_quantitative=n_quant,
        fallback_count=n_fall,
        coverage_pct=coverage_pct,
        questions=all_analyses,
    )

    triples = list(g)
    return triples, coverage
