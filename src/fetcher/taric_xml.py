from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from typing import IO

import httpx
from lxml import etree

from src.schema.taric import ChapterData, MeasureComponent, TARICMeasure

_ENV = "urn:publicid:-:DGTAXUD:TARIC3.0:ENV"
_OUB = "urn:publicid:-:DGTAXUD:TARIC3.0:OUB"

_T = f"{{{_OUB}}}"
_E = f"{{{_ENV}}}"

CIRCABC_BASE = (
    "https://circabc.europa.eu/ui/group/0e5f18c2-4b2f-42e9-aed4-dfe50ae1263b"
)

# Direct download URL for the June 2026 Duties Import xlsx (all chapters 01-99).
# Pattern: https://circabc.europa.eu/d/d/workspace/SpacesStore/{uuid}/{filename}
# File UUID discovered by browsing:
#   Library → Taric data → 2026 → 06 - June → Duties Import 01-99.xlsx
CIRCABC_DUTIES_IMPORT_URL = (
    "https://circabc.europa.eu/d/d/workspace/SpacesStore/"
    "0c2f56a5-0716-45bf-938e-a5987e9a1951/Duties%20Import%2001-99.xlsx"
)


def _text(el: etree._Element, tag: str) -> str:
    child = el.find(f"{_T}{tag}")
    if child is None:
        return ""
    return (child.text or "").strip()


def _date_or_none(s: str) -> date | None:
    if not s:
        return None
    return date.fromisoformat(s)


def _str_or_none(s: str) -> str | None:
    return s if s else None


def parse_taric_xml(source: IO[bytes], *, chapter: int) -> ChapterData:
    """Parse a TARIC3 XML stream, returning measures for the given chapter."""
    chapter_prefix = f"{chapter:02d}"

    measures: dict[str, dict] = {}
    components: dict[str, list[dict]] = {}

    for _event, elem in etree.iterparse(source, events=("end",)):
        if elem.tag == f"{_E}transaction":
            rc_el = elem.find(f"{_E}record.code")
            if rc_el is None:
                elem.clear()
                continue
            rc = (rc_el.text or "").strip()

            if rc == "271":
                meas_el = elem.find(f"{_T}measure")
                if meas_el is not None:
                    sid = _text(meas_el, "sid")
                    code = _text(meas_el, "goods.nomenclature.item.id")
                    if sid and code.startswith(chapter_prefix):
                        measures[sid] = {
                            "sid": sid,
                            "commodity_code": code,
                            "measure_type_id": _text(meas_el, "measure.type.id"),
                            "geographical_area_id": _text(meas_el, "geographical.area.id"),
                            "validity_start": _text(meas_el, "validity.start.date"),
                            "validity_end": _text(meas_el, "validity.end.date") or None,
                            "regulation_id": _text(meas_el, "measure.generating.regulation.id"),
                        }

            elif rc == "430":
                comp_el = elem.find(f"{_T}measure.component")
                if comp_el is not None:
                    msid = _text(comp_el, "measure.sid")
                    amt_str = _text(comp_el, "duty.amount")
                    components.setdefault(msid, []).append({
                        "duty_expression_id": _text(comp_el, "duty.expression.id"),
                        "duty_amount": float(amt_str) if amt_str else None,
                        "monetary_unit": _str_or_none(_text(comp_el, "monetary.unit.code")),
                        "measurement_unit": _str_or_none(_text(comp_el, "measurement.unit.code")),
                    })

            elem.clear()

    result: list[TARICMeasure] = []
    for sid, m in measures.items():
        comps = [MeasureComponent.model_validate(c) for c in components.get(sid, [])]
        result.append(TARICMeasure(
            sid=m["sid"],
            commodity_code=m["commodity_code"],
            measure_type_id=m["measure_type_id"],
            geographical_area_id=m["geographical_area_id"],
            validity_start=date.fromisoformat(m["validity_start"]),
            validity_end=_date_or_none(m["validity_end"] or ""),
            regulation_id=m["regulation_id"],
            components=comps,
        ))

    return ChapterData(chapter=chapter, measures=result)


def _parse_duty_string(duty: str) -> tuple[float | None, str | None, str | None]:
    """Parse duty strings like '13.100 EUR HLT', '9.600 % ', '1.750 EUR ASV X'."""
    duty = duty.strip()
    m = re.match(r"^([\d.]+)\s*(%|[A-Z]+)?\s*([A-Z]*)?\s*", duty)
    if not m:
        return None, None, None
    amount = float(m.group(1))
    unit1 = m.group(2) or None
    unit2 = m.group(3) or None
    if unit1 == "%":
        return amount, None, None
    monetary = unit1
    measurement = unit2 if unit2 else None
    return amount, monetary, measurement


def _synthetic_sid(code: str, mtype: str, origin: str, start: str, regulation: str) -> str:
    """Deterministic SID hash for Excel-sourced measures (no oub:sid field)."""
    key = f"{code}|{mtype}|{origin}|{start}|{regulation}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def parse_duties_xlsx(xlsx_path: Path, *, chapter: int) -> ChapterData:
    """Parse CIRCABC Duties Import xlsx, returning measures for the given chapter.

    Column layout (confirmed June 2026):
      Goods code | Add code | Order No. | Start date | End date | RED_IND |
      Origin | Measure type | Legal base | Duty | Origin code | Meas. type code
    """
    import openpyxl  # optional dep — installed alongside this project

    chapter_prefix = f"{chapter:02d}"
    wb = openpyxl.load_workbook(str(xlsx_path), read_only=True, data_only=True)
    ws = wb.active

    measures: list[TARICMeasure] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) < 12:
            continue
        (goods_code, _add, _order, start_str, end_str, _red,
         _origin_name, _mtype_name, legal, duty_str, origin_code, mtype_code) = row[:12]

        if not goods_code:
            continue
        code = str(goods_code)
        if not code.startswith(chapter_prefix):
            continue

        start_str = str(start_str or "").strip()
        end_str = str(end_str or "").strip()
        duty_str = str(duty_str or "").strip()
        origin_code = str(origin_code or "").strip()
        mtype_code = str(mtype_code or "").strip()
        legal = str(legal or "").strip()

        try:
            validity_start = date.fromisoformat(
                start_str.replace("-", "-") if "-" in start_str
                else date(*(int(x) for x in reversed(start_str.split("-")))).isoformat()
            )
        except (ValueError, TypeError):
            # Try DD-MM-YYYY
            try:
                parts = start_str.split("-")
                validity_start = date(int(parts[2]), int(parts[1]), int(parts[0]))
            except Exception:
                continue

        validity_end: date | None = None
        if end_str and end_str != "None":
            try:
                parts = end_str.split("-")
                validity_end = date(int(parts[2]), int(parts[1]), int(parts[0]))
            except Exception:
                validity_end = None

        amount, monetary, measurement = _parse_duty_string(duty_str)
        comp = MeasureComponent(
            duty_expression_id="01",
            duty_amount=amount,
            monetary_unit=monetary,
            measurement_unit=measurement,
        )

        sid = _synthetic_sid(code, mtype_code, origin_code,
                             validity_start.isoformat(), legal)
        measures.append(TARICMeasure(
            sid=sid,
            commodity_code=code,
            measure_type_id=mtype_code,
            geographical_area_id=origin_code,
            validity_start=validity_start,
            validity_end=validity_end,
            regulation_id=legal,
            components=[comp],
        ))

    return ChapterData(chapter=chapter, measures=measures)


def download_duties_xlsx(dest: Path) -> Path:
    """Download the CIRCABC Duties Import xlsx to dest. Returns dest path."""
    r = httpx.get(CIRCABC_DUTIES_IMPORT_URL, timeout=120, follow_redirects=True)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def fetch_and_parse(
    chapter: int,
    xml_path: Path | None = None,
    xlsx_path: Path | None = None,
) -> ChapterData:
    """Load TARIC data for the given chapter.

    Priority: xlsx_path > xml_path > auto-download from CIRCABC (xlsx).
    """
    if xlsx_path is not None:
        return parse_duties_xlsx(xlsx_path, chapter=chapter)

    if xml_path is not None:
        with open(xml_path, "rb") as fh:
            return parse_taric_xml(fh, chapter=chapter)

    # Auto-download: CIRCABC Excel is publicly accessible via direct URL
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        download_duties_xlsx(tmp_path)
        return parse_duties_xlsx(tmp_path, chapter=chapter)
    finally:
        tmp_path.unlink(missing_ok=True)


def write_chapter_json(data: ChapterData, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"taric_ch{data.chapter:02d}.json"
    out.write_text(data.model_dump_json(indent=2))
    return out
