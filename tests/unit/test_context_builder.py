from __future__ import annotations

import pytest
from rdflib import Graph

from src.agent.context_builder import (
    _compute_hierarchy_path,
    build_node_context,
    build_static_context,
    compute_tbox_hash,
)
from src.schema.legal_text import LegalSection
from src.schema.wizard import AnswerOption, ClassificationNode


# ── build_static_context ──────────────────────────────────────────────────────

class TestBuildStaticContext:
    def test_happy_path_chapter22_returns_valid_turtle(self):
        ttl = build_static_context(22)
        g = Graph()
        g.parse(data=ttl, format="turtle")
        assert len(g) > 0

    def test_happy_path_chapter22_under_600_triples(self):
        ttl = build_static_context(22)
        g = Graph()
        g.parse(data=ttl, format="turtle")
        assert len(g) <= 600

    def test_chapter_with_no_specific_props_still_valid(self):
        """A chapter that has no chapter-specific props must still return valid Turtle."""
        ttl = build_static_context(23)
        g = Graph()
        g.parse(data=ttl, format="turtle")
        assert len(g) > 0

    def test_returns_string(self):
        result = build_static_context(22)
        assert isinstance(result, str)

    def test_turtle_contains_bfo_classes(self):
        ttl = build_static_context(22)
        assert "BFO_0000030" in ttl or "bfo" in ttl.lower()

    def test_turtle_contains_bfo_subclass_triples(self):
        """BFO stubs must include rdfs:subClassOf for hierarchy (spec requirement)."""
        ttl = build_static_context(22)
        g = Graph()
        g.parse(data=ttl, format="turtle")
        from rdflib.namespace import RDFS
        from src.ontology.namespaces import BFO
        bfo_object = BFO["BFO_0000030"]
        bfo_process = BFO["BFO_0000015"]
        bfo_ind_cont = BFO["BFO_0000004"]
        bfo_occurrent = BFO["BFO_0000003"]
        assert (bfo_object, RDFS.subClassOf, bfo_ind_cont) in g, \
            "BFO_0000030 must have rdfs:subClassOf BFO_0000004 (independent continuant)"
        assert (bfo_process, RDFS.subClassOf, bfo_occurrent) in g, \
            "BFO_0000015 must have rdfs:subClassOf BFO_0000003 (occurrent)"


# ── compute_tbox_hash ─────────────────────────────────────────────────────────

class TestComputeTboxHash:
    def test_returns_64_char_hex_string(self):
        h = compute_tbox_hash(22)
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        assert compute_tbox_hash(22) == compute_tbox_hash(22)

    def test_different_chapters_differ(self):
        h22 = compute_tbox_hash(22)
        h23 = compute_tbox_hash(23)
        assert h22 != h23


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_node(node_id: str, question_text: str, cn_code: str | None = None,
               path_from_root: list[str] | None = None) -> ClassificationNode:
    return ClassificationNode(
        node_id=node_id,
        question_text=question_text,
        answer_options=[AnswerOption(answer_text="Yes", next_node_id=None)],
        is_terminal=cn_code is not None,
        cn_code=cn_code,
        path_from_root=path_from_root or [],
    )


def _make_legal_section(cn_code: str, language: str, source_text: str) -> LegalSection:
    return LegalSection(
        note_id="note001",
        chapter=22,
        cn_code=cn_code,
        note_type="chapter_note",
        source_text=source_text,
        source_text_hash="",
        ingestion_date="2024-01-01",
        language=language,
        source_url="https://example.com",
        fetched_at="2024-01-01T00:00:00",
    )


# ── _compute_hierarchy_path ───────────────────────────────────────────────────

class TestComputeHierarchyPath:
    """Tests for the rewritten _compute_hierarchy_path using all_wizard_nodes."""

    def test_happy_path_two_ancestors(self):
        """node 22041013 with path_from_root=[22000000, 22040000] returns 2 ancestor dicts."""
        node_chapter = _make_node("22000000", "Is it an alcoholic beverage?", path_from_root=[])
        node_heading = _make_node("22040000", "Is it wine?", path_from_root=["22000000"])
        node_target = _make_node(
            "22041013", "Is it sparkling?",
            cn_code="22041013",
            path_from_root=["22000000", "22040000"],
        )
        all_wizard_nodes = {
            "22000000": node_chapter,
            "22040000": node_heading,
            "22041013": node_target,
        }
        result = _compute_hierarchy_path("22041013", all_wizard_nodes)
        assert len(result) == 2
        assert result[0]["cn_code"] == "22000000"
        assert result[1]["cn_code"] == "22040000"

    def test_happy_path_ancestor_question_texts_included(self):
        """Question texts from ancestor nodes are included in result dicts."""
        node_chapter = _make_node("22000000", "Is it an alcoholic beverage?", path_from_root=[])
        node_heading = _make_node("22040000", "Is it wine?", path_from_root=["22000000"])
        node_target = _make_node(
            "22041013", "Is it sparkling?",
            cn_code="22041013",
            path_from_root=["22000000", "22040000"],
        )
        all_wizard_nodes = {
            "22000000": node_chapter,
            "22040000": node_heading,
            "22041013": node_target,
        }
        result = _compute_hierarchy_path("22041013", all_wizard_nodes)
        assert "Is it an alcoholic beverage?" in result[0]["question_texts"]
        assert "Is it wine?" in result[1]["question_texts"]

    def test_cn_code_padded_to_8_digits_for_lookup(self):
        """A 4-digit heading code is padded to 8 chars before lookup."""
        node_chapter = _make_node("22000000", "Chapter question?", path_from_root=[])
        node_heading = _make_node("22050000", "Heading question?", path_from_root=["22000000"])
        all_wizard_nodes = {
            "22000000": node_chapter,
            "22050000": node_heading,
        }
        # "2205" pads to "22050000" which exists and has path_from_root=["22000000"]
        result = _compute_hierarchy_path("2205", all_wizard_nodes)
        assert len(result) == 1
        assert result[0]["cn_code"] == "22000000"

    def test_cn_code_not_found_returns_empty_list(self):
        """A cn_code that doesn't exist after padding returns empty list, no exception."""
        all_wizard_nodes = {
            "22000000": _make_node("22000000", "Chapter?", path_from_root=[]),
        }
        result = _compute_hierarchy_path("99999999", all_wizard_nodes)
        assert result == []

    def test_empty_all_wizard_nodes_returns_empty_list(self):
        """Empty all_wizard_nodes dict returns empty list."""
        result = _compute_hierarchy_path("22041013", {})
        assert result == []

    def test_chapter_root_with_empty_path_from_root_returns_empty(self):
        """A chapter root node (path_from_root=[]) yields no ancestors."""
        node_chapter = _make_node("22000000", "Chapter question?", path_from_root=[])
        all_wizard_nodes = {"22000000": node_chapter}
        # "22" pads to "22000000"
        result = _compute_hierarchy_path("22", all_wizard_nodes)
        assert result == []

    def test_ancestor_not_in_dict_is_skipped(self):
        """An ancestor_id in path_from_root that has no entry in all_wizard_nodes is skipped."""
        node_target = _make_node(
            "22041013", "Is it sparkling?",
            cn_code="22041013",
            path_from_root=["22000000", "22040000"],
        )
        # Only include target node, not its ancestors
        all_wizard_nodes = {"22041013": node_target}
        result = _compute_hierarchy_path("22041013", all_wizard_nodes)
        assert result == []

    def test_node_with_empty_question_text_has_empty_question_texts_list(self):
        """Nodes with empty question_text produce question_texts=[]."""
        node_chapter = _make_node("22000000", "", path_from_root=[])
        node_target = _make_node(
            "22041013", "Is it sparkling?",
            cn_code="22041013",
            path_from_root=["22000000"],
        )
        all_wizard_nodes = {
            "22000000": node_chapter,
            "22041013": node_target,
        }
        result = _compute_hierarchy_path("22041013", all_wizard_nodes)
        assert len(result) == 1
        assert result[0]["question_texts"] == []

    def test_order_follows_path_from_root_order(self):
        """Ancestors are returned in path_from_root order (root first)."""
        node_a = _make_node("22000000", "A?", path_from_root=[])
        node_b = _make_node("22040000", "B?", path_from_root=["22000000"])
        node_c = _make_node("22041000", "C?", path_from_root=["22000000", "22040000"])
        node_target = _make_node(
            "22041013", "D?",
            cn_code="22041013",
            path_from_root=["22000000", "22040000", "22041000"],
        )
        all_wizard_nodes = {
            "22000000": node_a,
            "22040000": node_b,
            "22041000": node_c,
            "22041013": node_target,
        }
        result = _compute_hierarchy_path("22041013", all_wizard_nodes)
        assert [r["cn_code"] for r in result] == ["22000000", "22040000", "22041000"]


# ── build_node_context ────────────────────────────────────────────────────────

class TestBuildNodeContext:
    def test_happy_path_2204_includes_ancestor_22_via_all_wizard_nodes(self):
        """Ancestor 22000000 appears when all_wizard_nodes is passed correctly."""
        node_22 = _make_node("22000000", "What is the chapter?", path_from_root=[])
        node_2204 = _make_node(
            "22040000", "Is it wine?",
            cn_code=None,
            path_from_root=["22000000"],
        )
        # Terminal node for cn_code "22041013" padded to "22041013"
        node_terminal = _make_node(
            "22041013", "Is it sparkling?",
            cn_code="22041013",
            path_from_root=["22000000", "22040000"],
        )
        all_wizard_nodes = {
            "22000000": node_22,
            "22040000": node_2204,
            "22041013": node_terminal,
        }

        result = build_node_context(
            cn_code="22041013",
            legal_sections=[],
            running_tbox_ttl="",
            all_wizard_nodes=all_wizard_nodes,
        )

        hierarchy = result["hierarchy_path"]
        ancestor_codes = [entry["cn_code"] for entry in hierarchy]
        assert "22000000" in ancestor_codes

    def test_happy_path_ancestor_has_question_text(self):
        node_22 = _make_node("22000000", "What is the chapter?", path_from_root=[])
        node_terminal = _make_node(
            "22041013", "Is it sparkling?",
            cn_code="22041013",
            path_from_root=["22000000"],
        )
        all_wizard_nodes = {
            "22000000": node_22,
            "22041013": node_terminal,
        }

        result = build_node_context("22041013", [], "", all_wizard_nodes=all_wizard_nodes)
        hierarchy = result["hierarchy_path"]
        entry = next(e for e in hierarchy if e["cn_code"] == "22000000")
        assert "What is the chapter?" in entry["question_texts"]

    def test_no_all_wizard_nodes_returns_empty_hierarchy(self):
        """Without all_wizard_nodes, hierarchy_path is empty (safe default)."""
        result = build_node_context(
            cn_code="22041013",
            legal_sections=[],
            running_tbox_ttl="",
        )
        assert result["hierarchy_path"] == []

    def test_en_notes_included(self):
        section = _make_legal_section("2204", "en", "Wines of fresh grapes.")
        result = build_node_context("2204", [section], "")
        assert "Wines of fresh grapes." in result["notes_en"]

    def test_de_notes_included(self):
        section = _make_legal_section("2204", "de", "Wein aus frischen Weintrauben.")
        result = build_node_context("2204", [section], "")
        assert "Wein aus frischen Weintrauben." in result["notes_de"]

    def test_notes_filtered_by_cn_code(self):
        section_match = _make_legal_section("2204", "en", "Wines.")
        section_other = _make_legal_section("2203", "en", "Beer.")
        result = build_node_context("2204", [section_match, section_other], "")
        assert "Wines." in result["notes_en"]
        assert "Beer." not in result["notes_en"]

    def test_node_with_no_notes_returns_empty_lists_not_error(self):
        result = build_node_context("2204", [], "")
        assert result["notes_en"] == []
        assert result["notes_de"] == []

    def test_running_tbox_included_in_result(self):
        ttl = "@prefix eucn: <https://w3id.org/eucn/> .\neucn:Wine a owl:Class ."
        result = build_node_context("2204", [], ttl)
        assert result["running_tbox"] == ttl

    def test_existing_axioms_contains_matching_lines(self):
        ttl = "eucn:Wine2204 a owl:Class .\neucn:Beer2203 a owl:Class ."
        result = build_node_context("2204", [], ttl)
        assert any("2204" in line for line in result["existing_axioms"])
        assert not any("2203" in line for line in result["existing_axioms"])

    def test_existing_axioms_empty_when_no_tbox(self):
        result = build_node_context("2204", [], "")
        assert result["existing_axioms"] == []

    def test_result_has_required_keys(self):
        result = build_node_context("2204", [], "")
        assert set(result.keys()) == {
            "hierarchy_path",
            "notes_en",
            "notes_de",
            "running_tbox",
            "existing_axioms",
        }
