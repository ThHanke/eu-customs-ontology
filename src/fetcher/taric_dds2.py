from __future__ import annotations

import json
import logging
import re
import time
from datetime import date
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict

from src.schema.taric import (
    FootnoteRecord,
    GeographicAreaRecord,
    MeasureTypeRecord,
    RegulationRecord,
    TARICMeasure,
)

logger = logging.getLogger(__name__)

DDS2_BASE = "https://ec.europa.eu/taxation_customs/dds2/taric"
_DDS2_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
}


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
        resp = httpx.get(url, headers=_DDS2_HEADERS, timeout=30)
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


# ---------------------------------------------------------------------------
# Commodity measures (measures_details.jsp)
# ---------------------------------------------------------------------------

def _parse_dds2_date(s: str) -> date | None:
    """Parse DD-MM-YYYY from DDS2 HTML."""
    m = re.search(r'(\d{2})-(\d{2})-(\d{4})', s)
    if not m:
        return None
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def _parse_footnotes_js(html: str) -> dict[str, FootnoteRecord]:
    """Extract footnote map {code: FootnoteRecord} from pageDisplayedFootnotes JS block."""
    m = re.search(
        r'pageDisplayedFootnotes\s*=\s*new Array\((.*?)\)\s*;',
        html,
        re.DOTALL,
    )
    if not m:
        return {}
    block = m.group(1)
    footnotes: dict[str, FootnoteRecord] = {}
    # Match: new Array("CODE", new Footnote("CODE", "TEXT"
    for fn_m in re.finditer(r'new Array\s*\(\s*"([^"]+)"\s*,\s*new Footnote\s*\(\s*"([^"]+)"\s*,\s*"([^"]*)"', block):
        code = fn_m.group(2)
        text = fn_m.group(3)
        footnotes[code] = FootnoteRecord(code=code, description=text)
    return footnotes


def _parse_measures_details_html(html: str, code_10d: str) -> list[TARICMeasure]:
    """Parse measures_details.jsp HTML into a list of TARICMeasure objects."""
    soup = BeautifulSoup(html, "html.parser")

    footnote_map = _parse_footnotes_js(html)

    measures: list[TARICMeasure] = []

    # Walk the document tracking current geographic area from measure_area headers
    geo_name: str | None = None
    geo_code: str | None = None

    # Process all divs with class "measure_area" and id "measure_*" in document order
    for tag in soup.find_all(True):
        # Detect measure_area header
        if tag.name == "div" and "measure_area" in (tag.get("class") or []):
            header_text = tag.get_text(separator=" ", strip=True)
            area_m = re.search(r'\(([^()]+?)\s+(\d+)\)\s*$', header_text)
            if area_m:
                geo_name = area_m.group(1).strip()
                geo_code = area_m.group(2).strip()
            continue

        # Detect individual measure blocks
        tag_id = tag.get("id", "")
        if tag.name == "div" and tag_id.startswith("measure_"):
            sid = tag_id[len("measure_"):]

            # Measure type description: td with class td_measure_description
            mt_desc = ""
            mt_td = tag.find("td", class_=lambda c: c and "td_measure_description" in c)
            if mt_td:
                # Get text before first span
                parts = []
                for child in mt_td.children:
                    if hasattr(child, "name") and child.name is not None:
                        break
                    text = str(child).strip()
                    if text:
                        parts.append(text)
                mt_desc = " ".join(parts).strip()
                if not mt_desc:
                    # Fallback: get all text, strip span content
                    for span in mt_td.find_all("span"):
                        span.decompose()
                    mt_desc = mt_td.get_text(strip=True)

            # Validity from span text like "(01-01-1999 - )" or "(01-01-1999 - 31-12-2025)"
            v_start: date | None = None
            v_end: date | None = None
            validity_span = tag.find("span", string=re.compile(r'\d{2}-\d{2}-\d{4}'))
            if validity_span:
                span_text = validity_span.get_text()
                dates_found = re.findall(r'\d{2}-\d{2}-\d{4}', span_text)
                if dates_found:
                    v_start = _parse_dds2_date(dates_found[0])
                if len(dates_found) >= 2:
                    v_end = _parse_dds2_date(dates_found[1])

            # Duty rate
            duty_span = tag.find("span", class_="duty_rate")
            # (not stored in TARICMeasure directly — stored in duty_expression)

            # Regulation ID from hidden anchor
            regulation_id = ""
            reg_anchor = tag.find("a", id=re.compile(r"db_regulation_id_"))
            if reg_anchor:
                regulation_id = reg_anchor.get_text(strip=True)

            # Footnotes for this measure — currently the HTML doesn't map per-measure
            # so we attach all page footnotes (spec says footnotes_for_this_measure)
            measure_footnotes = list(footnote_map.values())

            geo_area = (
                GeographicAreaRecord(code=geo_code, description=geo_name)
                if geo_code else None
            )

            measure = TARICMeasure(
                sid=sid,
                commodity_code=code_10d,
                measure_type_id="",
                geographical_area_id=geo_code or "",
                validity_start=v_start or date(1972, 1, 1),
                validity_end=v_end,
                regulation_id=regulation_id or "",
                components=[],
                measure_type=MeasureTypeRecord(code="", description=mt_desc),
                geographical_area=geo_area,
                regulations=[RegulationRecord(regulation_id=regulation_id)] if regulation_id else [],
                footnotes=measure_footnotes,
            )
            measures.append(measure)

    return measures


def fetch_commodity_measures(
    code_10d: str,
    sim_date: date,
    cache_dir: Path,
    *,
    force: bool = False,
) -> list[TARICMeasure]:
    """Fetch regulatory measures for a 10-digit commodity code from DDS2.

    Two-step: first fetches measures.jsp to get the Sid, then fetches
    measures_details.jsp to get the full measure details.

    Returns list of TARICMeasure. Caches to cache_dir/{code_10d}.json.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{code_10d}.json"

    if cache_file.exists() and not force:
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
        return [TARICMeasure.model_validate(item) for item in raw]

    date_str = sim_date.strftime("%Y%m%d")

    with httpx.Client(timeout=30, headers=_DDS2_HEADERS) as client:
        # Step 1: get measures.jsp to extract Sid
        step1_url = (
            f"{DDS2_BASE}/measures.jsp"
            f"?Lang=en&Taric={code_10d}&SimDate={date_str}"
        )
        logger.info("DDS2 Step 1: %s", step1_url)
        try:
            resp1 = client.get(step1_url)
            resp1.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("DDS2 measures.jsp HTTP %s for %s", exc.response.status_code, code_10d)
            return []
        except httpx.HTTPError as exc:
            logger.warning("DDS2 measures.jsp error for %s: %s", code_10d, exc)
            return []
        html1 = resp1.text

        soup1 = BeautifulSoup(html1, "html.parser")
        iframe = soup1.find("iframe")
        if not iframe:
            logger.warning("DDS2: no iframe found for %s", code_10d)
            return []

        iframe_src = iframe.get("src", "")
        if "deferred_measures.jsp" in iframe_src:
            logger.warning("DDS2 deferred for %s", code_10d)
            cache_file.write_text("[]", encoding="utf-8")
            return []

        sid_m = re.search(r'Sid=([^&]+)', iframe_src)
        if not sid_m:
            logger.warning("DDS2: no Sid in iframe src for %s: %s", code_10d, iframe_src)
            return []
        sid = sid_m.group(1)

        time.sleep(0.2)

        # Step 2: get measures_details.jsp
        step2_url = (
            f"{DDS2_BASE}/measures_details.jsp"
            f"?Sid={sid}&Taric={code_10d}&Offset=0&Lang=en&SimDate={date_str}"
        )
        logger.info("DDS2 Step 2: %s", step2_url)
        try:
            resp2 = client.get(step2_url)
            resp2.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("DDS2 measures_details.jsp HTTP %s for %s", exc.response.status_code, code_10d)
            return []
        except httpx.HTTPError as exc:
            logger.warning("DDS2 measures_details.jsp error for %s: %s", code_10d, exc)
            return []
        html2 = resp2.text

    measures = _parse_measures_details_html(html2, code_10d)

    cache_file.write_text(
        json.dumps([m.model_dump(mode="json") for m in measures], indent=2),
        encoding="utf-8",
    )
    return measures


def fetch_chapter_commodities(
    chapter: int,
    cn_codes_8d: list[str],
    cache_dir: Path,
    *,
    force: bool = False,
) -> dict[str, list[TARICMeasure]]:
    """Fetch DDS2 measures for all CN codes in a chapter.

    cn_codes_8d: 8-digit codes; padded to 10d with '00' suffix.
    Returns {code_8d: [TARICMeasure, ...]}.
    Cache directory: cache_dir / f"dds2_ch{chapter:02d}".
    """
    from datetime import date as _date
    chapter_cache = cache_dir / f"dds2_ch{chapter:02d}"
    sim_date = _date.today()
    result: dict[str, list[TARICMeasure]] = {}
    for code in cn_codes_8d:
        code_10d = (code + "00")[:10]
        measures = fetch_commodity_measures(code_10d, sim_date, chapter_cache, force=force)
        result[code] = measures
    return result
