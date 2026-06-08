from __future__ import annotations

import base64
import datetime
import json
import time
from pathlib import Path

import httpx

from src.schema.legal_text import LegalSection

BASE_URL = "https://webgate.ec.europa.eu/class-public-ui-rest/api"
CLASS_SOURCE_URL = "https://webgate.ec.europa.eu/class-public-ui-web/#/search"


def _post_with_retry(client: httpx.Client, url: str, json_body: dict) -> httpx.Response:
    resp = client.post(url, json=json_body)
    if resp.status_code >= 500:
        time.sleep(2)
        resp = client.post(url, json=json_body)
    return resp


def fetch_chapter_notes(
    chapter: int,
    out_dir: Path,
    *,
    languages: list[str] = ("en", "de"),
    sim_date: str | None = None,
    force: bool = False,
) -> list[LegalSection]:
    """Fetch CN Notes for chapter in all requested languages.

    Writes to out_dir/notes.jsonl. Checkpoint keyed on (note_id, language):
    - skip if present and ingestion_date unchanged (unless force=True)
    - update if ingestion_date changed
    Returns combined list of LegalSection across all languages.
    """
    if sim_date is None:
        sim_date = datetime.date.today().isoformat()

    today = datetime.date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "notes.jsonl"

    existing: dict[tuple[str, str], LegalSection] = {}
    if jsonl_path.exists():
        for line in jsonl_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            section = LegalSection.model_validate_json(line)
            existing[(section.note_id, section.language)] = section

    all_sections: dict[tuple[str, str], LegalSection] = dict(existing)

    with httpx.Client(timeout=30) as client:
        for i, lang in enumerate(languages):
            if i > 0:
                time.sleep(1)

            url = f"{BASE_URL}/consultation/searchSecondLevel"
            body = {
                "language": lang,
                "simDate": sim_date,
                "informationTypes": ["CN"],
                "cnCodes": [{"valueType": "NUMBER", "value": f"{chapter:02d}"}],
            }

            resp = _post_with_retry(client, url, body)
            if resp.status_code != 200:
                raise ValueError(
                    f"CLASS API error {resp.status_code}: chapter={chapter} lang={lang}"
                )

            cn_notes = resp.json()["cnNotes"]
            for note in cn_notes:
                note_id = note["noteId"]
                new_ingestion_date = note["ingestionDate"]
                key = (note_id, lang)

                if key in existing and not force:
                    if existing[key].ingestion_date == new_ingestion_date:
                        continue

                section = LegalSection(
                    note_id=note_id,
                    chapter=chapter,
                    cn_code=note["cnCode"],
                    note_type=note["noteType"],
                    source_text=note["noteDescrSnippet"],
                    ingestion_date=new_ingestion_date,
                    language=lang,
                    source_url=CLASS_SOURCE_URL,
                    fetched_at=today,
                )
                all_sections[key] = section

    sorted_sections = sorted(all_sections.values(), key=lambda s: (s.note_id, s.language))
    lines = [s.model_dump_json() for s in sorted_sections]
    jsonl_path.write_text("\n".join(lines) + "\n" if lines else "")

    return sorted_sections


def fetch_note_pdf(note_id: str) -> bytes:
    """Fetch full note PDF via /classification/getNotesById?referenceId={note_id}."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{BASE_URL}/classification/getNotesById",
            params={"referenceId": note_id},
        )
    if resp.status_code != 200:
        raise ValueError(f"CLASS API error {resp.status_code} for note {note_id}")
    return base64.b64decode(resp.json()["base64"])
