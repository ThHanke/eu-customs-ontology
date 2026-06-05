import pytest
from datetime import date
from rdflib import Graph
from rdflib.namespace import RDF

from src.schema.taric import ChapterData, MeasureComponent, TARICMeasure
from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree
from src.ontology.abox import build_abox
from src.ontology.namespaces import EUCN
from src.ontology.iri import cn_code_iri, taric_measure_iri, classification_node_iri


def _measure(sid="999", code="22042100", validity_end=None, components=None):
    return TARICMeasure(
        sid=sid,
        commodity_code=code,
        measure_type_id="103",
        geographical_area_id="1011",
        validity_start=date(2024, 1, 1),
        validity_end=validity_end,
        regulation_id="R2024/001",
        components=components or [],
    )


def _chapter_data(measures):
    return ChapterData(chapter=22, measures=measures)


def _wizard_tree(nodes, root_id):
    return WizardTree(chapter=22, nodes=nodes, root_node_id=root_id)


def _simple_tree():
    root = ClassificationNode(
        node_id="root",
        question_text="Is it a beverage?",
        answer_options=[AnswerOption(answer_text="Yes", next_node_id="term")],
        is_terminal=False,
        path_from_root=[],
    )
    term = ClassificationNode(
        node_id="term",
        question_text="",
        answer_options=[],
        is_terminal=True,
        cn_code="22042100",
        path_from_root=["Yes"],
    )
    return _wizard_tree({"root": root, "term": term}, "root")


class TestBuildABox:
    def test_cn_code_individual_present(self):
        cd = _chapter_data([_measure()])
        g = build_abox(_chapter_data([_measure()]), _simple_tree(), Graph())
        iri = cn_code_iri("22042100")
        assert (iri, RDF.type, EUCN.CNCode) in g

    def test_cn_code_string_triple(self):
        from rdflib import Literal
        g = build_abox(_chapter_data([_measure()]), _simple_tree(), Graph())
        iri = cn_code_iri("22042100")
        code_strs = list(g.objects(iri, EUCN.codeString))
        assert any(str(c) == "22042100" for c in code_strs)

    def test_measure_individual_present(self):
        g = build_abox(_chapter_data([_measure(sid="999")]), _simple_tree(), Graph())
        m_iri = taric_measure_iri("999")
        assert (m_iri, RDF.type, EUCN.TARICMeasure) in g

    def test_cn_links_to_measure(self):
        g = build_abox(_chapter_data([_measure(sid="999")]), _simple_tree(), Graph())
        cn_iri = cn_code_iri("22042100")
        m_iri = taric_measure_iri("999")
        assert (cn_iri, EUCN.hasMeasure, m_iri) in g

    def test_terminal_node_classifies_as(self):
        g = build_abox(_chapter_data([]), _simple_tree(), Graph())
        node_iri = classification_node_iri(["Yes"])
        cn_iri = cn_code_iri("22042100")
        assert (node_iri, EUCN.classifiesAs, cn_iri) in g

    def test_validity_end_none_no_triple(self):
        from rdflib import Literal
        g = build_abox(_chapter_data([_measure(validity_end=None)]), _simple_tree(), Graph())
        m_iri = taric_measure_iri("999")
        end_vals = list(g.objects(m_iri, EUCN.validityEnd))
        assert end_vals == [], f"Expected no validityEnd, got {end_vals}"

    def test_determinism(self):
        cd = _chapter_data([_measure()])
        wt = _simple_tree()
        g1 = build_abox(cd, wt, Graph())
        g2 = build_abox(cd, wt, Graph())
        nt1 = sorted(g1.serialize(format="nt").splitlines())
        nt2 = sorted(g2.serialize(format="nt").splitlines())
        assert nt1 == nt2

    def test_shared_cn_code_single_individual(self):
        # Two wizard paths resolving to same CN code → one individual
        root = ClassificationNode(
            node_id="root", question_text="Q", path_from_root=[],
            answer_options=[
                AnswerOption(answer_text="A", next_node_id="t1"),
                AnswerOption(answer_text="B", next_node_id="t2"),
            ], is_terminal=False
        )
        t1 = ClassificationNode(node_id="t1", question_text="", path_from_root=["A"],
                                answer_options=[], is_terminal=True, cn_code="22042100")
        t2 = ClassificationNode(node_id="t2", question_text="", path_from_root=["B"],
                                answer_options=[], is_terminal=True, cn_code="22042100")
        wt = _wizard_tree({"root": root, "t1": t1, "t2": t2}, "root")
        g = build_abox(_chapter_data([]), wt, Graph())
        cn_individuals = list(g.subjects(RDF.type, EUCN.CNCode))
        # Only one unique CNCode IRI for 22042100
        assert len(set(cn_individuals)) == 1

    def test_measure_without_validity_end_no_triple(self):
        g = build_abox(_chapter_data([_measure(validity_end=None)]), _simple_tree(), Graph())
        m_iri = taric_measure_iri("999")
        assert list(g.objects(m_iri, EUCN.validityEnd)) == []

    def test_measure_with_validity_end_has_triple(self):
        g = build_abox(_chapter_data([_measure(validity_end=date(2026, 12, 31))]),
                       _simple_tree(), Graph())
        m_iri = taric_measure_iri("999")
        assert list(g.objects(m_iri, EUCN.validityEnd)) != []
