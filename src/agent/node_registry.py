from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

from src.schema.axiom_candidate import AxiomCandidate
from src.schema.node_axiom_set import NodeAxiomSet


class NodeRegistry:
    def __init__(self, chapter_dir: Path) -> None:
        self._dir = chapter_dir

    def _node_path(self, cn_code: str) -> Path:
        return self._dir / f"node_{cn_code}.jsonl"

    def _load_one(self, cn_code: str) -> NodeAxiomSet | None:
        path = self._node_path(cn_code)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return None
        last_line = text.splitlines()[-1].strip()
        if not last_line:
            return None
        return NodeAxiomSet.model_validate(json.loads(last_line))

    def is_stale(self, cn_code: str, source_text_hash: str, tbox_hash: str) -> bool:
        stored = self._load_one(cn_code)
        if stored is None:
            return True
        return stored.source_text_hash != source_text_hash or stored.tbox_hash != tbox_hash

    def upsert(self, axiom_set: NodeAxiomSet) -> None:
        path = self._node_path(axiom_set.cn_code)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".jsonl.tmp")
        tmp.write_text(axiom_set.model_dump_json() + "\n", encoding="utf-8")
        os.rename(tmp, path)

    def get_approved(self, cn_code: str) -> NodeAxiomSet | None:
        stored = self._load_one(cn_code)
        if stored is None or stored.status != "approved":
            return None
        return stored

    def iter_all(self) -> Iterator[NodeAxiomSet]:
        if not self._dir.exists():
            return
        for path in sorted(self._dir.glob("node_*.jsonl")):
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            last_line = text.splitlines()[-1].strip()
            if last_line:
                yield NodeAxiomSet.model_validate(json.loads(last_line))

    def flatten_to_candidates(self, out_path: Path) -> None:
        candidates: list[AxiomCandidate] = []
        for axiom_set in self.iter_all():
            if axiom_set.status != "approved":
                continue
            chapter = int(axiom_set.cn_code[:2])
            source_note_id = axiom_set.source_note_ids[0] if axiom_set.source_note_ids else ""
            for restriction in axiom_set.restrictions:
                cand = AxiomCandidate(
                    chapter=chapter,
                    owl_class=restriction.owl_class_iri,
                    restriction_type=restriction.restriction_type,
                    property_iri=restriction.property_iri,
                    value=restriction.value,
                    facet=restriction.facet,
                    source_note_id=source_note_id,
                    source_text="",
                    source_text_hash=axiom_set.source_text_hash,
                    source_ingestion_date=axiom_set.generated_at,
                    status="proposed",
                    confidence=axiom_set.coverage_score,
                    extractor="llm_axiom_agent",
                    extracted_at=axiom_set.generated_at,
                )
                candidates.append(cand)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(".jsonl.tmp")
        lines = [c.model_dump_json() for c in candidates]
        tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        os.rename(tmp, out_path)
