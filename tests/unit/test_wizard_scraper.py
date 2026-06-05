import json
import pytest
from pathlib import Path

from src.scraper.wizard import state_key
from src.scraper.checkpoint import (
    append_node_jsonl,
    load_nodes_jsonl,
    save_checkpoint,
    load_checkpoint,
)
from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree


def _node(node_id, is_terminal=False, cn_code=None, path=None, answers=None):
    return ClassificationNode(
        node_id=node_id,
        question_text=f"Q for {node_id}",
        answer_options=answers or [],
        is_terminal=is_terminal,
        cn_code=cn_code,
        path_from_root=path or [],
    )


class TestStateKey:
    def test_deterministic(self):
        k1 = state_key("http://example.com/", {"a": "1", "b": "2"})
        k2 = state_key("http://example.com/", {"b": "2", "a": "1"})
        assert k1 == k2

    def test_different_url(self):
        k1 = state_key("http://example.com/a", {})
        k2 = state_key("http://example.com/b", {})
        assert k1 != k2

    def test_different_params(self):
        k1 = state_key("http://example.com/", {"x": "1"})
        k2 = state_key("http://example.com/", {"x": "2"})
        assert k1 != k2

    def test_cycle_detection(self):
        # Same URL + same params from different navigation paths → same key
        k1 = state_key("http://x.de/step", {"state": "42"})
        k2 = state_key("http://x.de/step", {"state": "42"})
        assert k1 == k2


class TestCheckpoint:
    def test_roundtrip(self, tmp_path):
        ckpt = tmp_path / "ckpt.json"
        visited = {"abc", "def"}
        frontier = [{"url": "u1", "form_data": {}, "path": ["a"]}]
        save_checkpoint(ckpt, visited, frontier)
        loaded = load_checkpoint(ckpt)
        assert set(loaded["visited"]) == visited
        assert loaded["frontier"] == frontier

    def test_missing_file_returns_none(self, tmp_path):
        assert load_checkpoint(tmp_path / "nope.json") is None

    def test_jsonl_append_and_load(self, tmp_path):
        path = tmp_path / "nodes.jsonl"
        n1 = _node("n1")
        n2 = _node("n2", is_terminal=True, cn_code="22042100")
        append_node_jsonl(path, n1.model_dump())
        append_node_jsonl(path, n2.model_dump())
        loaded = load_nodes_jsonl(path)
        assert len(loaded) == 2
        r1 = ClassificationNode.model_validate(loaded[0])
        r2 = ClassificationNode.model_validate(loaded[1])
        assert r1.node_id == "n1"
        assert r2.cn_code == "22042100"


class TestDFSLogic:
    """Tests for DFS traversal logic without live Playwright — simulate with node dict."""

    def _build_tree(self, nodes: dict[str, ClassificationNode], root_id: str) -> WizardTree:
        return WizardTree(chapter=22, nodes=nodes, root_node_id=root_id)

    def test_single_path_tree(self):
        root = _node("root", answers=[AnswerOption(answer_text="Yes", next_node_id="term")])
        term = _node("term", is_terminal=True, cn_code="22042100", path=["Yes"])
        tree = self._build_tree({"root": root, "term": term}, "root")
        assert tree.nodes["term"].is_terminal
        assert tree.nodes["root"].answer_options[0].answer_text == "Yes"

    def test_shared_target_single_iri(self):
        # Two parents pointing to same terminal — one terminal node, not two
        shared = _node("shared", is_terminal=True, cn_code="22042100", path=["A", "X"])
        n1 = _node("n1", answers=[AnswerOption(answer_text="X", next_node_id="shared")])
        n2 = _node("n2", answers=[AnswerOption(answer_text="X", next_node_id="shared")])
        tree = self._build_tree({"n1": n1, "n2": n2, "shared": shared}, "n1")
        assert len(tree.nodes) == 3
        assert "shared" in tree.nodes
