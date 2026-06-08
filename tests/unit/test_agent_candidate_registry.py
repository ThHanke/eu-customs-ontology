from __future__ import annotations

from pathlib import Path

from src.schema.axiom_candidate import AxiomCandidate
from src.agent.candidate_registry import CandidateRegistry


def _cand(owl_class="Beer", value="MaltFermentation", ingestion_date="2023-10-06", status="proposed"):
    return AxiomCandidate(
        chapter=22,
        owl_class=owl_class,
        restriction_type="someValuesFrom",
        property_iri="eucn:producedBy",
        value=value,
        facet=None,
        source_note_id="test-note-id",
        source_text="fermented from malted barley",
        source_text_hash="deadbeef",
        source_ingestion_date=ingestion_date,
        status=status,
        confidence=0.90,
        extractor="rule-based",
        extracted_at="2026-06-08",
    )


def test_upsert_new_appears_after_save_reload(tmp_path: Path):
    path = tmp_path / "ch22.jsonl"
    reg = CandidateRegistry(path)
    reg.load()
    c = _cand()
    reg.upsert(c)
    reg.save()

    reg2 = CandidateRegistry(path)
    candidates = reg2.load()
    assert len(candidates) == 1
    assert candidates[0].candidate_id == c.candidate_id
    assert candidates[0].status == "proposed"


def test_upsert_new_ingestion_date_sets_stale(tmp_path: Path):
    path = tmp_path / "ch22.jsonl"
    reg = CandidateRegistry(path)
    reg.load()
    c1 = _cand(ingestion_date="2023-10-06")
    reg.upsert(c1)

    c2 = _cand(ingestion_date="2024-01-01")
    reg.upsert(c2)

    assert reg._candidates[c1.candidate_id].status == "stale"


def test_upsert_same_ingestion_date_preserves_approved(tmp_path: Path):
    path = tmp_path / "ch22.jsonl"
    reg = CandidateRegistry(path)
    reg.load()
    c_approved = _cand(status="approved")
    reg.upsert(c_approved)

    c_proposed = _cand(status="proposed")
    reg.upsert(c_proposed)

    assert reg._candidates[c_approved.candidate_id].status == "approved"


def test_get_active_excludes_stale(tmp_path: Path):
    path = tmp_path / "ch22.jsonl"
    reg = CandidateRegistry(path)
    reg.load()

    c_beer = _cand(owl_class="Beer", value="MaltFermentation", ingestion_date="2023-10-06")
    reg.upsert(c_beer)
    c_beer_new = _cand(owl_class="Beer", value="MaltFermentation", ingestion_date="2024-01-01")
    reg.upsert(c_beer_new)

    c_wine = _cand(owl_class="Wine", value="GrapeFermentation", ingestion_date="2023-10-06")
    reg.upsert(c_wine)

    active = reg.get_active()
    active_ids = {c.candidate_id for c in active}
    assert c_beer.candidate_id not in active_ids
    assert c_wine.candidate_id in active_ids


def test_round_trip_save_load(tmp_path: Path):
    path = tmp_path / "ch22.jsonl"
    reg = CandidateRegistry(path)
    reg.load()
    c = _cand()
    reg.upsert(c)
    reg.save()

    reg2 = CandidateRegistry(path)
    loaded = reg2.load()
    assert len(loaded) == 1
    reloaded = loaded[0]
    assert reloaded.model_dump() == c.model_dump()


def test_atomic_write_no_tmp_file_remains(tmp_path: Path):
    path = tmp_path / "ch22.jsonl"
    reg = CandidateRegistry(path)
    reg.load()
    reg.upsert(_cand())
    reg.save()

    tmp_file = path.with_suffix(".jsonl.tmp")
    assert not tmp_file.exists()
    assert path.exists()
