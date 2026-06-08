from __future__ import annotations

import pytest
from rdflib import Graph

from src.agent.context_builder import (
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
        bfo_ind_cont = BFO["BFO_0000040"]
        bfo_occurrent = BFO["BFO_0000003"]
        assert (bfo_object, RDFS.subClassOf, bfo_ind_cont) in g, \
            "BFO_0000030 must have rdfs:subClassOf BFO_0000040 (independent continuant)"
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


# ── build_node_context ────────────────────────────────────────────────────────

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


class TestBuildNodeContext:
    def test_happy_path_2204_includes_ancestor_22(self):
        node_22 = _make_node("n_22", "What is the chapter?", path_from_root=[])
        node_2204 = _make_node("n_2204", "Is it wine?", cn_code="2204", path_from_root=["n_22"])

        wizard_nodes = {
            "22": [node_22],
            "2204": [node_2204],
        }

        result = build_node_context(
            cn_code="2204",
            legal_sections=[],
            wizard_nodes=wizard_nodes,
            running_tbox_ttl="",
        )

        hierarchy = result["hierarchy_path"]
        ancestor_codes = [entry["cn_code"] for entry in hierarchy]
        assert "22" in ancestor_codes

    def test_happy_path_2204_ancestor_22_has_question_text(self):
        node_22 = _make_node("n_22", "What is the chapter?", path_from_root=[])

        wizard_nodes = {
            "22": [node_22],
            "2204": [_make_node("n_2204", "Is it wine?", cn_code="2204", path_from_root=["n_22"])],
        }

        result = build_node_context("2204", [], wizard_nodes, "")
        hierarchy = result["hierarchy_path"]
        entry_22 = next(e for e in hierarchy if e["cn_code"] == "22")
        assert "What is the chapter?" in entry_22["question_texts"]

    def test_hierarchy_path_ordered_shortest_first(self):
        wizard_nodes = {
            "22": [_make_node("n_22", "Chapter?")],
            "2204": [_make_node("n_2204", "Heading?")],
            "220421": [_make_node("n_220421", "Sub?", cn_code="220421", path_from_root=[])],
        }
        result = build_node_context("220421", [], wizard_nodes, "")
        codes = [e["cn_code"] for e in result["hierarchy_path"]]
        assert codes == sorted(codes, key=len)

    def test_en_notes_included(self):
        section = _make_legal_section("2204", "en", "Wines of fresh grapes.")
        result = build_node_context("2204", [section], {}, "")
        assert "Wines of fresh grapes." in result["notes_en"]

    def test_de_notes_included(self):
        section = _make_legal_section("2204", "de", "Wein aus frischen Weintrauben.")
        result = build_node_context("2204", [section], {}, "")
        assert "Wein aus frischen Weintrauben." in result["notes_de"]

    def test_notes_filtered_by_cn_code(self):
        section_match = _make_legal_section("2204", "en", "Wines.")
        section_other = _make_legal_section("2203", "en", "Beer.")
        result = build_node_context("2204", [section_match, section_other], {}, "")
        assert "Wines." in result["notes_en"]
        assert "Beer." not in result["notes_en"]

    def test_node_with_no_notes_returns_empty_lists_not_error(self):
        result = build_node_context("2204", [], {}, "")
        assert result["notes_en"] == []
        assert result["notes_de"] == []

    def test_running_tbox_included_in_result(self):
        ttl = "@prefix eucn: <https://w3id.org/eucn/> .\neucn:Wine a owl:Class ."
        result = build_node_context("2204", [], {}, ttl)
        assert result["running_tbox"] == ttl

    def test_existing_axioms_contains_matching_lines(self):
        ttl = "eucn:Wine2204 a owl:Class .\neucn:Beer2203 a owl:Class ."
        result = build_node_context("2204", [], {}, ttl)
        assert any("2204" in line for line in result["existing_axioms"])
        assert not any("2203" in line for line in result["existing_axioms"])

    def test_existing_axioms_empty_when_no_tbox(self):
        result = build_node_context("2204", [], {}, "")
        assert result["existing_axioms"] == []

    def test_result_has_required_keys(self):
        result = build_node_context("2204", [], {}, "")
        assert set(result.keys()) == {
            "hierarchy_path",
            "notes_en",
            "notes_de",
            "running_tbox",
            "existing_axioms",
        }

    def test_node_not_its_own_ancestor(self):
        wizard_nodes = {
            "2204": [_make_node("n_2204", "Is it wine?", cn_code="2204")],
        }
        result = build_node_context("2204", [], wizard_nodes, "")
        ancestor_codes = [e["cn_code"] for e in result["hierarchy_path"]]
        assert "2204" not in ancestor_codes
