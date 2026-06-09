from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path

import httpx

from src.schema.taric import (
    AdditionalCodeRecord,
    DutyExpressionRecord,
    FootnoteRecord,
    GeographicAreaRecord,
    MeasureConditionRecord,
    MeasureTypeRecord,
    RegulationRecord,
    TARICMeasure,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.trade-tariff.service.gov.uk/api/v2/commodities"


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    return date.fromisoformat(s[:10])


def fetch_commodity(code_10d: str, cache_dir: Path, *, force: bool = False) -> dict:
    """Fetch commodity JSON from UK Trade Tariff API v2; cache to filesystem."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{code_10d}.json"
    if cache_file.exists() and not force:
        return json.loads(cache_file.read_text())
    time.sleep(0.2)
    try:
        resp = httpx.get(f"{BASE_URL}/{code_10d}", timeout=20)
        if resp.status_code >= 500:
            time.sleep(2)
            resp = httpx.get(f"{BASE_URL}/{code_10d}", timeout=20)
    except httpx.HTTPError as exc:
        logger.warning("UK tariff API error for %s: %s", code_10d, exc)
        return {}
    if resp.status_code == 404:
        logger.warning("UK tariff API 404 for %s (UK-only or defunct code)", code_10d)
        return {}
    if resp.status_code != 200:
        logger.warning("UK tariff API %d for %s", resp.status_code, code_10d)
        return {}
    raw = resp.json()
    cache_file.write_text(json.dumps(raw))
    return raw


def parse_commodity_measures(raw: dict) -> list[TARICMeasure]:
    """Map a UK Trade Tariff API v2 commodity response to TARICMeasure list."""
    if not raw:
        return []
    included = raw.get("included", [])
    commodity_data = raw.get("data", {})
    commodity_code = commodity_data.get("attributes", {}).get(
        "goods_nomenclature_item_id", ""
    )

    idx: dict[tuple[str, str], dict] = {}
    for item in included:
        idx[(item["type"], str(item["id"]))] = item

    measures = []
    for item in included:
        if item["type"] != "measure":
            continue
        attrs = item["attributes"]
        rels = item.get("relationships", {})

        # measure_type
        mt_ref = rels.get("measure_type", {}).get("data") or {}
        mt_id = str(mt_ref.get("id", ""))
        mt_item = idx.get(("measure_type", mt_id), {})
        mt_attrs = mt_item.get("attributes", {})
        measure_type = MeasureTypeRecord(
            code=mt_id,
            description=mt_attrs.get("description", ""),
            series_id=mt_attrs.get("measure_type_series_id", ""),
        ) if mt_id else None

        # geographical_area
        ga_ref = rels.get("geographical_area", {}).get("data") or {}
        ga_id = str(ga_ref.get("id", ""))
        ga_item = idx.get(("geographical_area", ga_id), {})
        ga_attrs = ga_item.get("attributes", {})
        geographical_area = GeographicAreaRecord(
            code=ga_id,
            description=ga_attrs.get("description", ga_id),
        ) if ga_id else None

        # duty_expression
        de_ref = rels.get("duty_expression", {}).get("data") or {}
        de_id = str(de_ref.get("id", ""))
        de_item = idx.get(("duty_expression", de_id), {})
        de_attrs = de_item.get("attributes", {})
        duty_expression = DutyExpressionRecord(
            base=de_attrs.get("base", ""),
            verbose_duty=de_attrs.get("verbose_duty", ""),
        ) if de_id else None

        # legal_acts → regulations
        la_refs = rels.get("legal_acts", {}).get("data") or []
        la_list = []
        for ref in la_refs:
            la_item = idx.get(("legal_act", str(ref["id"])), {})
            la_a = la_item.get("attributes", {})
            la_list.append(la_a)
        regulations = [
            RegulationRecord(
                regulation_id=str(la_item_ref["id"]),
                regulation_code=la_a.get("regulation_code", ""),
                description=la_a.get("description", ""),
                regulation_url=la_a.get("regulation_url", ""),
                validity_start=la_a.get("validity_start_date", "")[:10],
            )
            for la_item_ref, la_a in zip(la_refs, la_list)
        ]

        # measure_conditions
        mc_refs = rels.get("measure_conditions", {}).get("data") or []
        conditions = []
        for ref in mc_refs:
            mc_item = idx.get(("measure_condition", str(ref["id"])), {})
            mc_a = mc_item.get("attributes", {})
            conditions.append(MeasureConditionRecord(
                sid=str(ref["id"]),
                condition_code=mc_a.get("condition_code", ""),
                document_code=mc_a.get("document_code", ""),
                action_code=mc_a.get("action_code", ""),
                condition_duty_amount=mc_a.get("condition_duty_amount"),
                condition_measurement_unit_code=mc_a.get("condition_measurement_unit_code"),
                measure_condition_class=mc_a.get("measure_condition_class", ""),
                requirement=mc_a.get("requirement") or "",
            ))

        # footnotes
        fn_refs = rels.get("footnotes", {}).get("data") or []
        footnotes = []
        for ref in fn_refs:
            fn_item = idx.get(("footnote", str(ref["id"])), {})
            fn_a = fn_item.get("attributes", {})
            footnotes.append(FootnoteRecord(
                code=fn_a.get("code", str(ref["id"])),
                description=fn_a.get("description", ""),
            ))

        # additional_codes (optional relationship on measure)
        ac_refs = rels.get("additional_codes", {}).get("data") or []
        additional_codes = []
        for ref in ac_refs:
            ac_item = idx.get(("additional_code", str(ref["id"])), {})
            ac_a = ac_item.get("attributes", {})
            code_val = ac_a.get("code", str(ref["id"]))
            additional_codes.append(AdditionalCodeRecord(
                code=code_val,
                description=ac_a.get("description", ""),
            ))

        # quota order_number
        on_ref = rels.get("order_number", {}).get("data")
        quota_order_number = str(on_ref["id"]) if on_ref else None

        # validity dates
        v_start_raw = attrs.get("effective_start_date")
        v_end_raw = attrs.get("effective_end_date")
        v_start = _parse_date(v_start_raw) or date(1972, 1, 1)
        v_end = _parse_date(v_end_raw)

        # first regulation id for backward-compat field
        first_reg_id = str(la_refs[0]["id"]) if la_refs else ""

        measures.append(TARICMeasure(
            sid=str(attrs["id"]),
            commodity_code=commodity_code,
            measure_type_id=mt_id,
            geographical_area_id=ga_id,
            validity_start=v_start,
            validity_end=v_end,
            regulation_id=first_reg_id,
            components=[],
            measure_type=measure_type,
            geographical_area=geographical_area,
            duty_expression=duty_expression,
            footnotes=footnotes,
            conditions=conditions,
            additional_codes=additional_codes,
            regulations=regulations,
            quota_order_number=quota_order_number,
        ))

    return measures


def fetch_chapter_commodities(
    chapter: int,
    cn_codes: list[str],
    cache_dir: Path,
    *,
    force: bool = False,
) -> dict[str, list[TARICMeasure]]:
    """Fetch and parse measures for all CN codes in a chapter.

    cn_codes may be 8-digit; 10-digit codes are formed by appending '00'.
    Returns {cn_code_8d: [TARICMeasure, ...]}.
    """
    result: dict[str, list[TARICMeasure]] = {}
    chapter_cache = cache_dir / f"uk_tariff_ch{chapter:02d}"
    for code in cn_codes:
        code_10d = code.ljust(10, "0")[:10] if len(code) <= 8 else code[:10]
        raw = fetch_commodity(code_10d, chapter_cache, force=force)
        result[code] = parse_commodity_measures(raw)
    return result
