"""Unit tests for the wizard-to-axiom transformer."""
import pytest
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS, XSD

from src.ontology.iri import cn_code_iri
from src.ontology.namespaces import EUCN
from src.ontology.wizard_axioms import (
    WizardAxiomCoverage,
    transform,
)
from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _node(node_id: str, question: str, answers: list[tuple[str, str | None]],
          is_terminal: bool = False, cn_code: str | None = None,
          path: list[str] | None = None) -> ClassificationNode:
    return ClassificationNode(
        node_id=node_id,
        question_text=question,
        answer_options=[AnswerOption(answer_text=a, next_node_id=n) for a, n in answers],
        is_terminal=is_terminal,
        cn_code=cn_code,
        path_from_root=path or [],
    )


def _boolean_tree() -> WizardTree:
    """root → Q1(Ja) → terminal(220300)"""
    root = _node("root", "Ist das Erzeugnis ein Bier?", [("Ja", "t1"), ("Nein", None)])
    t1 = _node("t1", "", [], is_terminal=True, cn_code="220300", path=["Ja"])
    return WizardTree(chapter=22, nodes={"root": root, "t1": t1}, root_node_id="root")


def _boolean_nein_tree() -> WizardTree:
    """root → Q1(Nein) → terminal(220100)"""
    root = _node("root", "Ist das Erzeugnis Bier?", [("Ja", None), ("Nein", "t1")])
    t1 = _node("t1", "", [], is_terminal=True, cn_code="220100", path=["Nein"])
    return WizardTree(chapter=22, nodes={"root": root, "t1": t1}, root_node_id="root")


def _quantitative_tree() -> WizardTree:
    """root → Q1(Ja) → terminal, where question has 'mehr als 0,5 % vol'"""
    root = _node("root", "Hat das Erzeugnis einen Alkoholgehalt von mehr als 0,5 % vol?",
                 [("Ja", "t1"), ("Nein", None)])
    t1 = _node("t1", "", [], is_terminal=True, cn_code="220300", path=["Ja"])
    return WizardTree(chapter=22, nodes={"root": root, "t1": t1}, root_node_id="root")


def _hoch_tree() -> WizardTree:
    """root → Q1(Ja) → terminal, where question has 'höchstens 2 Liter'"""
    root = _node("root", "Ist das Behältnis höchstens 2 Liter?",
                 [("Ja", "t1"), ("Nein", None)])
    t1 = _node("t1", "", [], is_terminal=True, cn_code="220421", path=["Ja"])
    return WizardTree(chapter=22, nodes={"root": root, "t1": t1}, root_node_id="root")


def _fallback_tree() -> WizardTree:
    """root → Q1(Brandy) → terminal, answer is not boolean and no numeric"""
    root = _node("root", "Welche Spirituose liegt vor?",
                 [("Brandy", "t1"), ("Whisky", None)])
    t1 = _node("t1", "", [], is_terminal=True, cn_code="220830", path=["Brandy"])
    return WizardTree(chapter=22, nodes={"root": root, "t1": t1}, root_node_id="root")


def _multi_step_tree() -> WizardTree:
    """root → Q1(Ja) → Q2(Nein) → terminal"""
    root = _node("root", "Ist das Erzeugnis ein Getränk?", [("Ja", "n2"), ("Nein", None)])
    n2 = _node("n2", "Ist das Erzeugnis Bier?", [("Ja", None), ("Nein", "t1")], path=["Ja"])
    t1 = _node("t1", "", [], is_terminal=True, cn_code="220100", path=["Ja", "Nein"])
    return WizardTree(chapter=22, nodes={"root": root, "n2": n2, "t1": t1}, root_node_id="root")


def _empty_tree() -> WizardTree:
    """Root only, no terminal nodes."""
    root = _node("root", "Ist das Erzeugnis ein Getränk (Kapitel 22)?",
                 [("Ja", None)])
    return WizardTree(chapter=22, nodes={"root": root}, root_node_id="root")


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestTransformBoolean:
    def test_boolean_ja_hasvalue_true(self):
        triples, coverage = transform(_boolean_tree())
        g = Graph()
        for t in triples:
            g.add(t)
        values = [
            o for s, p, o in g.triples((None, OWL.hasValue, None))
            if str(o) == "True" or str(o).lower() == "true"
        ]
        assert values, "Expected owl:hasValue true"

    def test_boolean_nein_hasvalue_false(self):
        triples, coverage = transform(_boolean_nein_tree())
        g = Graph()
        for t in triples:
            g.add(t)
        values = [
            o for s, p, o in g.triples((None, OWL.hasValue, None))
            if str(o).lower() == "false"
        ]
        assert values, "Expected owl:hasValue false"

    def test_boolean_tier_in_coverage(self):
        _, coverage = transform(_boolean_tree())
        assert coverage.covered_boolean >= 1
        assert any(q.tier == "boolean" for q in coverage.questions)

    def test_boolean_success(self):
        _, coverage = transform(_boolean_tree())
        assert all(q.success for q in coverage.questions if q.tier == "boolean")


class TestTransformQuantitative:
    def test_quant_mehr_als_min_exclusive(self):
        triples, coverage = transform(_quantitative_tree())
        g = Graph()
        for t in triples:
            g.add(t)
        # Should have minExclusive facet
        facets = [o for s, p, o in g.triples((None, XSD.minExclusive, None))]
        assert facets, "Expected xsd:minExclusive"
        assert str(facets[0]) == "0.5"

    def test_quant_tier_in_coverage(self):
        _, coverage = transform(_quantitative_tree())
        assert coverage.covered_quantitative >= 1
        assert any(q.tier == "quantitative" for q in coverage.questions)

    def test_quant_threshold_extracted(self):
        _, coverage = transform(_quantitative_tree())
        quant_qs = [q for q in coverage.questions if q.tier == "quantitative"]
        assert quant_qs[0].extracted_threshold == pytest.approx(0.5)
        assert quant_qs[0].extracted_facet == "minExclusive"

    def test_quant_hochstens_max_inclusive(self):
        triples, coverage = transform(_hoch_tree())
        g = Graph()
        for t in triples:
            g.add(t)
        facets = [o for s, p, o in g.triples((None, XSD.maxInclusive, None))]
        assert facets, "Expected xsd:maxInclusive for höchstens 2 Liter"
        assert str(facets[0]) == "2.0"


class TestTransformFallback:
    def test_fallback_tier(self):
        _, coverage = transform(_fallback_tree())
        assert coverage.fallback_count >= 1
        assert any(q.tier == "fallback" for q in coverage.questions)

    def test_fallback_not_success(self):
        _, coverage = transform(_fallback_tree())
        fallbacks = [q for q in coverage.questions if q.tier == "fallback"]
        assert all(not q.success for q in fallbacks)

    def test_fallback_has_reason(self):
        _, coverage = transform(_fallback_tree())
        fallbacks = [q for q in coverage.questions if q.tier == "fallback"]
        assert all(q.failure_reason for q in fallbacks)


class TestTransformMultiStep:
    def test_intersection_has_two_restrictions(self):
        triples, _ = transform(_multi_step_tree())
        g = Graph()
        for t in triples:
            g.add(t)
        restrictions = list(g.subjects(RDF.type, OWL.Restriction))
        assert len(restrictions) >= 2, f"Expected ≥2 restrictions, got {len(restrictions)}"

    def test_intersection_of_present(self):
        triples, _ = transform(_multi_step_tree())
        g = Graph()
        for t in triples:
            g.add(t)
        intersections = list(g.subjects(OWL.intersectionOf, None))
        assert intersections, "Expected owl:intersectionOf"


class TestTransformIdempotency:
    def test_same_triples_on_two_calls(self):
        tree = _multi_step_tree()
        triples1, _ = transform(tree)
        triples2, _ = transform(tree)

        def triple_key(t):
            return tuple(str(x) for x in t)

        s1 = sorted(triple_key(t) for t in triples1)
        s2 = sorted(triple_key(t) for t in triples2)
        assert s1 == s2, "transform must be idempotent"


class TestTransformIRIStability:
    def test_same_question_same_iri(self):
        tree = _boolean_tree()
        _, cov1 = transform(tree)
        _, cov2 = transform(tree)
        iris1 = [q.property_iri for q in cov1.questions]
        iris2 = [q.property_iri for q in cov2.questions]
        assert iris1 == iris2, "property IRIs must be stable across runs"


class TestTransformCoverageReport:
    def test_total_terminal_nodes_matches(self):
        tree = _multi_step_tree()
        _, coverage = transform(tree)
        terminal_count = sum(1 for n in tree.nodes.values() if n.is_terminal and n.cn_code)
        assert coverage.total_terminal_nodes == terminal_count

    def test_coverage_pct_formula(self):
        tree = _multi_step_tree()
        _, coverage = transform(tree)
        total_q = len(coverage.questions)
        if total_q == 0:
            assert coverage.coverage_pct == pytest.approx(100.0)
        else:
            expected = (coverage.covered_boolean + coverage.covered_quantitative) / total_q * 100.0
            assert coverage.coverage_pct == pytest.approx(expected)

    def test_empty_tree_vacuously_covered(self):
        triples, coverage = transform(_empty_tree())
        assert triples == []
        assert coverage.total_terminal_nodes == 0
        assert coverage.coverage_pct == pytest.approx(100.0)


class TestTransformCNCodeIRI:
    def test_subject_is_cn_code_iri(self):
        triples, _ = transform(_boolean_tree())
        g = Graph()
        for t in triples:
            g.add(t)
        expected_iri = cn_code_iri("220300")
        subjects = list(g.subjects(OWL.equivalentClass, None))
        assert expected_iri in subjects, f"Expected {expected_iri} as subject of equivalentClass"
