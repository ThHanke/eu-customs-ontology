from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.fetcher.taric_dds2 import (
    SectionEntry,
    _parse_measures_details_html,
    _parse_nomenclaturetree_js,
    fetch_commodity_measures,
    fetch_nomenclaturetree,
)

# ---------------------------------------------------------------------------
# Fixture JS — two sections, chapter 22 in section IV
# ---------------------------------------------------------------------------
FIXTURE_JS = (
    'sectiontree = ['
    '["false","SECTION I","Live animals; animal products",'
    '[["false","CHAPTER 1","Live animals","0100000000",null],'
    '["false","CHAPTER 2","Meat and edible meat offal","0200000000",null]]],'
    '["false","SECTION IV","Prepared foodstuffs; beverages, spirits and vinegar; '
    'tobacco and manufactured tobacco substitutes",'
    '[["false","CHAPTER 17","Sugars and sugar confectionery","1700000000",null],'
    '["false","CHAPTER 18","Cocoa and cocoa preparations","1800000000",null],'
    '["false","CHAPTER 22","Beverages, spirits and vinegar","2200000000",null]]]'
    '];\nchapterfootnotes = [];\n'
)


# ---------------------------------------------------------------------------
# 1. Parse fixture → correct SectionEntry list
# ---------------------------------------------------------------------------

def test_parse_returns_two_sections():
    entries = _parse_nomenclaturetree_js(FIXTURE_JS)
    assert len(entries) == 2


def test_parse_section_labels():
    entries = _parse_nomenclaturetree_js(FIXTURE_JS)
    assert entries[0].label_en == "Live animals; animal products"
    assert entries[1].label_en.startswith("Prepared foodstuffs")


# ---------------------------------------------------------------------------
# 2. Chapter 22 maps to section IV
# ---------------------------------------------------------------------------

def test_chapter_22_in_section_iv():
    entries = _parse_nomenclaturetree_js(FIXTURE_JS)
    section_iv = next(e for e in entries if e.roman_numeral == "IV")
    assert "22" in section_iv.chapter_codes


# ---------------------------------------------------------------------------
# 3. Roman numerals preserved as-is
# ---------------------------------------------------------------------------

def test_roman_numerals_preserved():
    entries = _parse_nomenclaturetree_js(FIXTURE_JS)
    romans = [e.roman_numeral for e in entries]
    assert "I" in romans
    assert "IV" in romans


# ---------------------------------------------------------------------------
# 4. chapter_codes are 2-digit zero-padded strings
# ---------------------------------------------------------------------------

def test_chapter_codes_two_digit():
    entries = _parse_nomenclaturetree_js(FIXTURE_JS)
    for entry in entries:
        for code in entry.chapter_codes:
            assert len(code) == 2, f"Expected 2-digit code, got {code!r}"
            assert code.isdigit(), f"Expected digits, got {code!r}"


def test_chapter_1_zero_padded():
    entries = _parse_nomenclaturetree_js(FIXTURE_JS)
    section_i = next(e for e in entries if e.roman_numeral == "I")
    assert "01" in section_i.chapter_codes
    assert "02" in section_i.chapter_codes


# ---------------------------------------------------------------------------
# 5. Cache file written on first call; second call reads cache (no network)
# ---------------------------------------------------------------------------

def test_cache_written_on_first_call(tmp_path: Path):
    sim_date = date(2026, 6, 9)
    cache_file = tmp_path / "nomenclaturetree_en_20260609.js"

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.text = FIXTURE_JS
    mock_response.raise_for_status = MagicMock()

    with patch("src.fetcher.taric_dds2.httpx.get", return_value=mock_response) as mock_get:
        result = fetch_nomenclaturetree("en", sim_date, tmp_path)

    assert cache_file.exists(), "Cache file should be written after first call"
    assert len(result) == 2
    mock_get.assert_called_once()


def test_second_call_reads_cache_no_network(tmp_path: Path):
    sim_date = date(2026, 6, 9)
    cache_file = tmp_path / "nomenclaturetree_en_20260609.js"
    cache_file.write_text(FIXTURE_JS, encoding="utf-8")

    with patch("src.fetcher.taric_dds2.httpx.get") as mock_get:
        result = fetch_nomenclaturetree("en", sim_date, tmp_path)

    mock_get.assert_not_called()
    assert len(result) == 2


# ---------------------------------------------------------------------------
# 6. force=True re-downloads even when cache exists
# ---------------------------------------------------------------------------

def test_force_redownloads_even_with_cache(tmp_path: Path):
    sim_date = date(2026, 6, 9)
    cache_file = tmp_path / "nomenclaturetree_en_20260609.js"
    cache_file.write_text(FIXTURE_JS, encoding="utf-8")

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.text = FIXTURE_JS
    mock_response.raise_for_status = MagicMock()

    with patch("src.fetcher.taric_dds2.httpx.get", return_value=mock_response) as mock_get:
        result = fetch_nomenclaturetree("en", sim_date, tmp_path, force=True)

    mock_get.assert_called_once()
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Extra: SectionEntry is a valid Pydantic model (frozen)
# ---------------------------------------------------------------------------

def test_section_entry_frozen():
    entry = SectionEntry(
        roman_numeral="I",
        label_en="Live animals",
        chapter_codes=["01", "02"],
    )
    with pytest.raises(Exception):
        entry.roman_numeral = "X"  # type: ignore[misc]


def test_section_entry_label_de_defaults_none():
    entry = SectionEntry(
        roman_numeral="I",
        label_en="Live animals",
        chapter_codes=["01"],
    )
    assert entry.label_de is None


# ---------------------------------------------------------------------------
# TestFetchCommodityMeasures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
MEASURES_FIXTURE = FIXTURES_DIR / "dds2_measures_2203000100.html"

CODE_10D = "2203000100"
SIM_DATE = date(2026, 6, 9)


class TestFetchCommodityMeasures:
    # 1. Parse fixture HTML directly via internal helper -------------------

    def test_parse_measures_from_fixture(self):
        html = MEASURES_FIXTURE.read_text(encoding="utf-8")
        measures = _parse_measures_details_html(html, CODE_10D)
        assert len(measures) == 1
        m = measures[0]
        assert m.sid == "2146370"
        assert m.measure_type is not None
        assert m.measure_type.description == "Third country duty"
        assert m.geographical_area_id == "1011"
        assert m.validity_start == date(1999, 1, 1)
        assert m.validity_end is None
        assert m.regulation_id == "R0002658/87"

    # 2. Deferred iframe → return [] --------------------------------------

    def test_deferred_returns_empty(self, tmp_path: Path):
        step1_html = '<html><body><iframe src="deferred_measures.jsp?Sid=xxx&Taric=2203000100"></iframe></body></html>'
        mock_resp1 = MagicMock(spec=httpx.Response)
        mock_resp1.text = step1_html
        mock_resp1.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = MagicMock(return_value=mock_resp1)

        with patch("src.fetcher.taric_dds2.httpx.Client", return_value=mock_client):
            result = fetch_commodity_measures(CODE_10D, SIM_DATE, tmp_path)

        assert result == []

    # 3. Missing iframe → return [] ---------------------------------------

    def test_missing_iframe_returns_empty(self, tmp_path: Path):
        step1_html = "<html><body><p>No iframe here</p></body></html>"
        mock_resp1 = MagicMock(spec=httpx.Response)
        mock_resp1.text = step1_html
        mock_resp1.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = MagicMock(return_value=mock_resp1)

        with patch("src.fetcher.taric_dds2.httpx.Client", return_value=mock_client):
            result = fetch_commodity_measures(CODE_10D, SIM_DATE, tmp_path)

        assert result == []

    # 4. Cache written on first call; second call reads cache -------------

    def test_cache_written_and_read(self, tmp_path: Path):
        step1_html = '<html><body><iframe src="measures_details.jsp?Sid=12345&Taric=2203000100"></iframe></body></html>'
        step2_html = MEASURES_FIXTURE.read_text(encoding="utf-8")

        mock_resp1 = MagicMock(spec=httpx.Response)
        mock_resp1.text = step1_html
        mock_resp1.raise_for_status = MagicMock()

        mock_resp2 = MagicMock(spec=httpx.Response)
        mock_resp2.text = step2_html
        mock_resp2.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = MagicMock(side_effect=[mock_resp1, mock_resp2])

        with patch("src.fetcher.taric_dds2.httpx.Client", return_value=mock_client):
            result1 = fetch_commodity_measures(CODE_10D, SIM_DATE, tmp_path)

        cache_file = tmp_path / f"{CODE_10D}.json"
        assert cache_file.exists(), "Cache file should be written after first call"
        assert len(result1) == 1

        # Second call — no HTTP
        with patch("src.fetcher.taric_dds2.httpx.Client") as mock_client_cls2:
            result2 = fetch_commodity_measures(CODE_10D, SIM_DATE, tmp_path)
        mock_client_cls2.assert_not_called()
        assert len(result2) == 1
        assert result2[0].sid == "2146370"

    # 5. force=True re-fetches even when cache exists ---------------------

    def test_force_refetches(self, tmp_path: Path):
        cache_file = tmp_path / f"{CODE_10D}.json"
        cache_file.write_text("[]", encoding="utf-8")

        step1_html = '<html><body><iframe src="measures_details.jsp?Sid=12345&Taric=2203000100"></iframe></body></html>'
        step2_html = MEASURES_FIXTURE.read_text(encoding="utf-8")

        mock_resp1 = MagicMock(spec=httpx.Response)
        mock_resp1.text = step1_html
        mock_resp1.raise_for_status = MagicMock()

        mock_resp2 = MagicMock(spec=httpx.Response)
        mock_resp2.text = step2_html
        mock_resp2.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = MagicMock(side_effect=[mock_resp1, mock_resp2])

        with patch("src.fetcher.taric_dds2.httpx.Client", return_value=mock_client):
            result = fetch_commodity_measures(CODE_10D, SIM_DATE, tmp_path, force=True)

        assert mock_client.get.call_count == 2
        assert len(result) == 1
