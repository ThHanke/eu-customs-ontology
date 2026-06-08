"""Integration: wizard axiom triples pass Konclude consistency check."""
import pytest
from pathlib import Path
from rdflib import Graph
from rdflib.namespace import OWL, RDF

from src.ontology.tbox import build_tbox
from src.ontology.wizard_axioms import transform
from src.reasoning.konclude import KoncludeConsistencyError, check_consistency
from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree

KONCLUDE_AVAILABLE = Path("/home/hanke/rdf-reasoner-konclude/dist/cli.js").exists()
skip_no_konclude = pytest.mark.skipif(not KONCLUDE_AVAILABLE, reason="Konclude CLI not found")


def _boolean_tree() -> WizardTree:
    root = ClassificationNode(
        node_id="root",
        question_text="Ist das Erzeugnis ein Bier?",
        answer_options=[
            AnswerOption(answer_text="Ja", next_node_id="t1"),
            AnswerOption(answer_text="Nein", next_node_id=None),
        ],
        is_terminal=False,
        path_from_root=[],
    )
    t1 = ClassificationNode(
        node_id="t1",
        question_text="",
        answer_options=[],
        is_terminal=True,
        cn_code="220300",
        path_from_root=["Ja"],
    )
    return WizardTree(chapter=22, nodes={"root": root, "t1": t1}, root_node_id="root")


@skip_no_konclude
class TestWizardAxiomsIntegration:
    def test_wizard_axioms_tbox_consistent(self, tmp_path):
        g = Graph()
        build_tbox(g)
        triples, coverage = transform(_boolean_tree())
        for triple in triples:
            g.add(triple)
        ttl = tmp_path / "test.ttl"
        ttl.write_text(g.serialize(format="turtle"))
        assert check_consistency(ttl) is True

    def test_stub_tree_zero_terminal_nodes(self):
        """Current 1-node wizard stub has 0 terminal nodes — transform handles gracefully."""
        root = ClassificationNode(
            node_id="root",
            question_text="Ist das Erzeugnis ein Getränk (Kapitel 22)?",
            answer_options=[AnswerOption(answer_text="Ja", next_node_id=None)],
            is_terminal=False,
            path_from_root=[],
        )
        tree = WizardTree(chapter=22, nodes={"root": root}, root_node_id="root")
        triples, coverage = transform(tree)
        assert triples == []
        assert coverage.total_terminal_nodes == 0
        assert coverage.coverage_pct == 100.0
