"""Tests for legal-text axiom dispatch in abox.py and pipeline integration."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.agent.candidate_registry import CandidateRegistry
from src.schema.axiom_candidate import AxiomCandidate


def _make_candidate(**overrides) -> AxiomCandidate:
    import hashlib

    source_text = overrides.pop("source_text", "fermented from malted barley")
    defaults = dict(
        chapter=22,
        owl_class="Beer",
        restriction_type="someValuesFrom",
        property_iri="eucn:producedBy",
        value="MaltFermentation",
        facet=None,
        source_note_id="n1",
        source_text=source_text,
        source_text_hash=hashlib.sha256(source_text.encode()).hexdigest(),
        source_ingestion_date="2023-10-06",
        status="approved",
        confidence=0.90,
        extractor="rule-based",
        extracted_at="2026-06-08",
    )
    defaults.update(overrides)
    return AxiomCandidate(**defaults)


def test_chapter_module_optional_equivalence_axioms():
    """ChapterModule.add_equivalence_axioms can be None."""
    from src.ontology.chapter_registry import ChapterModule

    m = ChapterModule(
        label="test",
        slug="test",
        add_discriminating_props=lambda g: None,
        add_product_classes=lambda g: None,
        add_process_classes=lambda g: None,
        add_equivalence_axioms=None,
    )
    assert m.add_equivalence_axioms is None


def test_chapter_module_existing_chapters_still_have_equivalence_axioms():
    """Unretired chapters carry add_equivalence_axioms callables; retired ones have None."""
    from src.ontology.chapter_registry import get_chapter

    # ch22 retired — agent output took over
    assert get_chapter(22).add_equivalence_axioms is None
    # ch23 still hand-authored
    module23 = get_chapter(23)
    assert module23.add_equivalence_axioms is not None
    assert callable(module23.add_equivalence_axioms)


def test_registry_returns_active_candidates(tmp_path):
    """Registry loaded from JSONL returns active (non-stale) candidates correctly."""
    reg_path = tmp_path / "ch22.jsonl"
    cand = _make_candidate()

    reg = CandidateRegistry(reg_path)
    reg.upsert(cand)
    reg.save()

    reg2 = CandidateRegistry(reg_path)
    reg2.load()
    active = reg2.get_active()
    assert len(active) == 1
    assert active[0].owl_class == "Beer"
    assert active[0].status == "approved"


def test_stale_candidate_in_summary(tmp_path):
    """Stale candidates appear in stale_summary after ingestion_date change."""
    reg_path = tmp_path / "ch22.jsonl"
    cand = _make_candidate()

    reg = CandidateRegistry(reg_path)
    reg.upsert(cand)

    updated = cand.model_copy(update={"source_ingestion_date": "2024-01-15", "status": "proposed"})
    reg.upsert(updated)

    stale = reg.stale_summary()
    assert len(stale) == 1
    assert stale[0]["owl_class"] == "Beer"
    assert stale[0]["source_ingestion_date"] == "2024-01-15"


def test_stale_candidate_not_in_active(tmp_path):
    """Stale candidates are excluded from get_active()."""
    reg_path = tmp_path / "ch22.jsonl"
    cand = _make_candidate()

    reg = CandidateRegistry(reg_path)
    reg.upsert(cand)
    updated = cand.model_copy(update={"source_ingestion_date": "2024-01-15"})
    reg.upsert(updated)

    assert reg.get_active() == []


def test_pipeline_run_accepts_skip_legal_text():
    """Pipeline run() signature includes skip_legal_text parameter."""
    from src.pipeline import run

    sig = inspect.signature(run)
    assert "skip_legal_text" in sig.parameters
    assert sig.parameters["skip_legal_text"].default is False
