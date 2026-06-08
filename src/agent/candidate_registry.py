from __future__ import annotations

import json
import os
from pathlib import Path

from src.schema.axiom_candidate import AxiomCandidate


class CandidateRegistry:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._candidates: dict[str, AxiomCandidate] = {}

    def load(self) -> list[AxiomCandidate]:
        """Load from JSONL file. Returns all candidates sorted by candidate_id."""
        if not self._path.exists():
            self._candidates = {}
            return []
        self._candidates = {}
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                candidate = AxiomCandidate.model_validate(json.loads(line))
                self._candidates[candidate.candidate_id] = candidate
        return sorted(self._candidates.values(), key=lambda c: c.candidate_id)

    def upsert(self, candidate: AxiomCandidate) -> None:
        """Add or update a candidate.

        - If candidate_id not present: add with candidate's status
        - If candidate_id present and source_ingestion_date changed: set status="stale"
        - If candidate_id present and source_ingestion_date unchanged: preserve existing status
        """
        existing = self._candidates.get(candidate.candidate_id)
        if existing is None:
            self._candidates[candidate.candidate_id] = candidate
        elif candidate.source_ingestion_date != existing.source_ingestion_date:
            self._candidates[candidate.candidate_id] = candidate.model_copy(update={"status": "stale"})
        else:
            self._candidates[candidate.candidate_id] = candidate.model_copy(update={"status": existing.status})

    def get_active(self) -> list[AxiomCandidate]:
        """Return all candidates with status != "stale", sorted by candidate_id."""
        return sorted(
            [c for c in self._candidates.values() if c.status != "stale"],
            key=lambda c: c.candidate_id,
        )

    def stale_summary(self) -> list[dict]:
        """Return list of dicts with info about stale candidates."""
        return [
            {
                "candidate_id": c.candidate_id,
                "owl_class": c.owl_class,
                "restriction_type": c.restriction_type,
                "property_iri": c.property_iri,
                "source_note_id": c.source_note_id,
                "source_ingestion_date": c.source_ingestion_date,
            }
            for c in self._candidates.values()
            if c.status == "stale"
        ]

    def save(self) -> None:
        """Atomic write: write to temp file then rename."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".jsonl.tmp")
        lines = [
            c.model_dump_json()
            for c in sorted(self._candidates.values(), key=lambda c: c.candidate_id)
        ]
        tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        os.rename(tmp, self._path)
