from __future__ import annotations

import hashlib

from pydantic import BaseModel, model_validator


class LegalSection(BaseModel):
    note_id: str
    chapter: int
    cn_code: str
    note_type: str
    source_text: str
    source_text_hash: str
    ingestion_date: str
    language: str
    source_url: str
    fetched_at: str

    @model_validator(mode="before")
    @classmethod
    def _compute_source_text_hash(cls, data: dict) -> dict:
        if isinstance(data, dict) and "source_text_hash" not in data and "source_text" in data:
            data["source_text_hash"] = hashlib.sha256(data["source_text"].encode()).hexdigest()
        return data
