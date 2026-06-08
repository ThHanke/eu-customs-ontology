"""Unit tests for src.ontology.chapter_registry."""
from __future__ import annotations

import re

import pytest
from rdflib import Graph

from src.ontology.chapter_registry import ChapterModule, CHAPTERS, get_chapter


class TestGetChapter:
    def test_returns_chapter_module_instance(self):
        result = get_chapter(22)
        assert isinstance(result, ChapterModule)

    def test_slug_is_beverages(self):
        assert get_chapter(22).slug == "beverages"

    def test_label_is_correct(self):
        assert get_chapter(22).label == "Beverages, spirits and vinegar"

    def test_unknown_chapter_raises_value_error(self):
        with pytest.raises(ValueError, match="Chapter 99 not yet implemented"):
            get_chapter(99)

    def test_add_discriminating_props_is_callable(self):
        assert callable(get_chapter(22).add_discriminating_props)

    def test_add_product_classes_is_callable(self):
        assert callable(get_chapter(22).add_product_classes)

    def test_add_process_classes_is_callable(self):
        assert callable(get_chapter(22).add_process_classes)

    def test_add_equivalence_axioms_is_callable(self):
        assert callable(get_chapter(22).add_equivalence_axioms)

    def test_slug_is_kebab_case(self):
        slug = get_chapter(22).slug
        # kebab-case: only lowercase letters, digits, and hyphens — no spaces or underscores
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug), (
            f"slug {slug!r} is not kebab-case"
        )

    def test_calling_all_functions_does_not_raise(self):
        ch = get_chapter(22)
        g = Graph()
        ch.add_discriminating_props(g)
        ch.add_product_classes(g)
        ch.add_process_classes(g)
        ch.add_equivalence_axioms(g)
