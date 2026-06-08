from __future__ import annotations

from pathlib import Path

import pytest

from src.agent.node_registry import NodeRegistry
from src.schema.node_axiom_set import NodeAxiomSet, NodeRestriction

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BFO_MATERIAL = "http://purl.obolibrary.org/obo/BFO_0000040"
EUCN_NS = "https://w3id.org/eucn/"

_RESTRICTION = dict(
    owl_class_iri=f"{EUCN_NS}Wine",
    restriction_type="someValuesFrom",
    property_iri=f"{EUCN_NS}producedFrom",
    value=f"{EUCN_NS}Grape",
    facet=None,
)


def _make_axiom_set(
    cn_code: str = "2204",
    source_text_hash: str = "aabbccdd",
    tbox_hash: str = "11223344",
    status: str = "proposed",
    restrictions: list | None = None,
    source_note_ids: list[str] | None = None,
    coverage_score: float = 0.8,
    generated_at: str = "2026-06-08T10:00:00Z",
) -> NodeAxiomSet:
    if restrictions is None:
        restrictions = [_RESTRICTION]
    if source_note_ids is None:
        source_note_ids = ["note_001"]
    return NodeAxiomSet(
        cn_code=cn_code,
        new_classes=[],
        new_properties=[],
        restrictions=restrictions,
        coverage_score=coverage_score,
        coverage_explanation="Test axiom set.",
        source_note_ids=source_note_ids,
        source_text_hash=source_text_hash,
        tbox_hash=tbox_hash,
        status=status,  # type: ignore[arg-type]
        agent_model="test-model",
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# Happy path: upsert then load returns same object
# ---------------------------------------------------------------------------


def test_upsert_then_load_returns_same_object(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    axiom_set = _make_axiom_set()
    reg.upsert(axiom_set)

    node_path = tmp_path / "node_2204.jsonl"
    assert node_path.exists()

    reg2 = NodeRegistry(tmp_path)
    loaded = reg2._load_one("2204")
    assert loaded is not None
    assert loaded.cn_code == axiom_set.cn_code
    assert loaded.source_text_hash == axiom_set.source_text_hash
    assert loaded.tbox_hash == axiom_set.tbox_hash
    assert loaded.candidate_id == axiom_set.candidate_id
    assert loaded.model_dump() == axiom_set.model_dump()


# ---------------------------------------------------------------------------
# Staleness: source hash differs → stale
# ---------------------------------------------------------------------------


def test_is_stale_returns_true_when_source_hash_differs(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    reg.upsert(_make_axiom_set(source_text_hash="original_hash", tbox_hash="tbox_hash"))

    assert reg.is_stale("2204", source_text_hash="different_hash", tbox_hash="tbox_hash") is True


# ---------------------------------------------------------------------------
# Staleness: both hashes match → not stale
# ---------------------------------------------------------------------------


def test_is_stale_returns_false_when_both_hashes_match(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    reg.upsert(_make_axiom_set(source_text_hash="src_hash", tbox_hash="tbox_hash"))

    assert reg.is_stale("2204", source_text_hash="src_hash", tbox_hash="tbox_hash") is False


# ---------------------------------------------------------------------------
# Staleness: tbox_hash differs even if source hash matches → stale
# ---------------------------------------------------------------------------


def test_is_stale_returns_true_when_tbox_hash_differs(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    reg.upsert(_make_axiom_set(source_text_hash="src_hash", tbox_hash="old_tbox"))

    assert reg.is_stale("2204", source_text_hash="src_hash", tbox_hash="new_tbox") is True


# ---------------------------------------------------------------------------
# Staleness: no entry exists → stale
# ---------------------------------------------------------------------------


def test_is_stale_returns_true_when_no_entry_exists(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    assert reg.is_stale("9999", source_text_hash="any", tbox_hash="any") is True


# ---------------------------------------------------------------------------
# All four hash-match combinations
# ---------------------------------------------------------------------------


def test_staleness_all_four_combinations(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    reg.upsert(_make_axiom_set(cn_code="2204", source_text_hash="src", tbox_hash="tbox"))

    assert reg.is_stale("2204", "src", "tbox") is False      # both match
    assert reg.is_stale("2204", "OTHER", "tbox") is True     # source differs
    assert reg.is_stale("2204", "src", "OTHER") is True      # tbox differs
    assert reg.is_stale("2204", "OTHER", "OTHER") is True    # both differ


# ---------------------------------------------------------------------------
# Edge case: get_approved for unknown cn_code returns None
# ---------------------------------------------------------------------------


def test_get_approved_unknown_cn_code_returns_none(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    result = reg.get_approved("0000")
    assert result is None


def test_get_approved_returns_none_for_proposed(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    reg.upsert(_make_axiom_set(status="proposed"))
    assert reg.get_approved("2204") is None


def test_get_approved_returns_axiom_set_when_approved(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    axiom_set = _make_axiom_set(status="approved")
    reg.upsert(axiom_set)
    result = reg.get_approved("2204")
    assert result is not None
    assert result.status == "approved"
    assert result.cn_code == "2204"


# ---------------------------------------------------------------------------
# Atomic save: no corrupt partial file if process dies mid-write
# ---------------------------------------------------------------------------


def test_atomic_save_no_tmp_file_remains(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    reg.upsert(_make_axiom_set())

    node_path = tmp_path / "node_2204.jsonl"
    tmp_file = node_path.with_suffix(".jsonl.tmp")
    assert node_path.exists()
    assert not tmp_file.exists()


# ---------------------------------------------------------------------------
# Round-trip upsert/load for 10 nodes
# ---------------------------------------------------------------------------


def test_round_trip_ten_nodes(tmp_path: Path):
    cn_codes = [f"22{i:02d}" for i in range(10)]
    reg = NodeRegistry(tmp_path)

    originals: dict[str, NodeAxiomSet] = {}
    for code in cn_codes:
        axiom_set = _make_axiom_set(
            cn_code=code,
            source_text_hash=f"src_{code}",
            tbox_hash=f"tbox_{code}",
        )
        reg.upsert(axiom_set)
        originals[code] = axiom_set

    reg2 = NodeRegistry(tmp_path)
    for code in cn_codes:
        loaded = reg2._load_one(code)
        assert loaded is not None, f"Node {code} not recoverable"
        assert loaded.cn_code == code
        assert loaded.source_text_hash == originals[code].source_text_hash
        assert loaded.tbox_hash == originals[code].tbox_hash
        assert loaded.model_dump() == originals[code].model_dump()


# ---------------------------------------------------------------------------
# iter_all: iterates all stored sets
# ---------------------------------------------------------------------------


def test_iter_all_returns_all_nodes(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    codes = ["2204", "2205", "2206"]
    for code in codes:
        reg.upsert(_make_axiom_set(cn_code=code))

    found = {s.cn_code for s in reg.iter_all()}
    assert found == set(codes)


def test_iter_all_empty_directory(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    result = list(reg.iter_all())
    assert result == []


def test_iter_all_nonexistent_directory(tmp_path: Path):
    reg = NodeRegistry(tmp_path / "nonexistent")
    result = list(reg.iter_all())
    assert result == []


# ---------------------------------------------------------------------------
# flatten_to_candidates: approved sets become AxiomCandidates
# ---------------------------------------------------------------------------


def test_flatten_to_candidates_only_approved(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    reg.upsert(_make_axiom_set(cn_code="2204", status="approved"))
    reg.upsert(_make_axiom_set(cn_code="2205", status="proposed"))
    reg.upsert(_make_axiom_set(cn_code="2206", status="failed"))

    out_path = tmp_path / "out" / "ch22.jsonl"
    reg.flatten_to_candidates(out_path)

    assert out_path.exists()
    import json
    lines = [l for l in out_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1  # only approved cn_code="2204", 1 restriction

    from src.schema.axiom_candidate import AxiomCandidate
    cand = AxiomCandidate.model_validate(json.loads(lines[0]))
    assert cand.chapter == 22
    assert cand.owl_class == f"{EUCN_NS}Wine"
    assert cand.extractor == "llm_axiom_agent"
    assert cand.status == "proposed"
    assert cand.confidence == 0.8
    assert cand.source_note_id == "note_001"
    assert cand.source_text == ""


def test_flatten_to_candidates_empty_restrictions_not_emitted(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    reg.upsert(_make_axiom_set(cn_code="2204", status="approved", restrictions=[]))

    out_path = tmp_path / "ch22.jsonl"
    reg.flatten_to_candidates(out_path)

    assert out_path.exists()
    lines = [l for l in out_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 0


def test_flatten_to_candidates_multiple_restrictions(tmp_path: Path):
    extra_restriction = dict(
        owl_class_iri=f"{EUCN_NS}SparklingWine",
        restriction_type="hasValue",
        property_iri=f"{EUCN_NS}hasStyle",
        value=f"{EUCN_NS}Sparkling",
        facet=None,
    )
    reg = NodeRegistry(tmp_path)
    reg.upsert(_make_axiom_set(
        cn_code="2204",
        status="approved",
        restrictions=[_RESTRICTION, extra_restriction],
    ))

    out_path = tmp_path / "ch22.jsonl"
    reg.flatten_to_candidates(out_path)

    import json
    lines = [l for l in out_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2


def test_flatten_to_candidates_empty_source_note_ids(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    reg.upsert(_make_axiom_set(cn_code="2204", status="approved", source_note_ids=[]))

    out_path = tmp_path / "ch22.jsonl"
    reg.flatten_to_candidates(out_path)

    import json
    from src.schema.axiom_candidate import AxiomCandidate
    lines = [l for l in out_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    cand = AxiomCandidate.model_validate(json.loads(lines[0]))
    assert cand.source_note_id == ""


def test_flatten_to_candidates_atomic_no_tmp_remains(tmp_path: Path):
    reg = NodeRegistry(tmp_path)
    reg.upsert(_make_axiom_set(cn_code="2204", status="approved"))

    out_path = tmp_path / "ch22.jsonl"
    reg.flatten_to_candidates(out_path)

    assert out_path.exists()
    assert not out_path.with_suffix(".jsonl.tmp").exists()
