from __future__ import annotations

import json
import logging
import re
import time
from datetime import date
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

DDS2_BASE = "https://ec.europa.eu/taxation_customs/dds2/taric"


class SectionEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    roman_numeral: str          # e.g. "IV"
    label_en: str               # e.g. "Prepared foodstuffs..."
    label_de: str | None = None  # filled in bilingual merge; None in EN-only run
    chapter_codes: list[str]    # 2-digit zero-padded, e.g. ["22"]


def _parse_nomenclaturetree_js(content: str) -> list[SectionEntry]:
    """Strip the JS assignment wrapper and parse the sectiontree JSON."""
    # Find the start of the JSON array after the assignment
    match = re.search(r'sectiontree\s*=\s*(\[)', content)
    if not match:
        raise ValueError("Could not find 'sectiontree = [' in content")

    start = match.start(1)
    # Walk the string to find the matching closing bracket, respecting strings
    depth = 0
    in_string = False
    escape_next = False
    end = start
    for idx in range(start, len(content)):
        ch = content[idx]
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if not in_string:
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    end = idx
                    break

    json_text = content[start:end + 1]
    raw = json.loads(json_text)

    # Format: flat array of groups:
    #   [has_children_bool, "SECTION I", "description", [[ch_entry], ...], ...]
    # Each ch_entry: [has_children, "CHAPTER N", "description", "NN00000000", footnotes_or_null]
    entries = []
    i = 0
    while i < len(raw):
        _has_children = raw[i]
        section_name = raw[i + 1]   # "SECTION I"
        section_desc = raw[i + 2]   # "description"
        chapters_raw = raw[i + 3]   # [[...], ...]
        i += 4

        roman = section_name.split()[-1]  # last word, e.g. "I", "IV"

        chapter_codes = []
        for ch in chapters_raw:
            # ch_entry: [has_children, "CHAPTER N", "description", "NN00000000", footnotes_or_null]
            if len(ch) >= 4:
                ch_name = ch[1]  # "CHAPTER 22" or "CHAPTER 1"
                parts = str(ch_name).split()
                if parts:
                    try:
                        num = int(parts[-1])
                        chapter_codes.append(f"{num:02d}")
                    except ValueError:
                        pass

        entries.append(SectionEntry(
            roman_numeral=roman,
            label_en=section_desc,
            label_de=None,
            chapter_codes=chapter_codes,
        ))

    return entries


def fetch_nomenclaturetree(
    lang: str,
    sim_date: date,
    cache_dir: Path,
    *,
    force: bool = False,
) -> list[SectionEntry]:
    """Fetch and parse the DDS2 nomenclaturetree JS file.

    Returns list of SectionEntry. Caches to cache_dir/nomenclaturetree_{lang}_{YYYYMMDD}.js.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    date_str = sim_date.strftime("%Y%m%d")
    cache_file = cache_dir / f"nomenclaturetree_{lang}_{date_str}.js"

    if cache_file.exists() and not force:
        content = cache_file.read_text(encoding="utf-8")
        return _parse_nomenclaturetree_js(content)

    url = f"{DDS2_BASE}/nomenclaturetree/nomenclaturetree_{lang}_{date_str}.js"
    logger.info("Fetching nomenclaturetree: %s", url)
    time.sleep(0.2)
    try:
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("DDS2 nomenclaturetree fetch failed: %s", exc)
        return []

    content = resp.text
    cache_file.write_text(content, encoding="utf-8")
    return _parse_nomenclaturetree_js(content)


def fetch_section_hierarchy(
    lang: str,
    sim_date: date,
    cache_dir: Path,
    *,
    force: bool = False,
) -> list[SectionEntry]:
    """Alias for fetch_nomenclaturetree; used by pipeline."""
    return fetch_nomenclaturetree(lang, sim_date, cache_dir, force=force)
