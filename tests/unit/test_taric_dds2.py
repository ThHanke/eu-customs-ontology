from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.fetcher.taric_dds2 import (
    SectionEntry,
    _parse_nomenclaturetree_js,
    fetch_nomenclaturetree,
)

# ---------------------------------------------------------------------------
# Fixture JS — two sections, chapter 22 in section IV
# ---------------------------------------------------------------------------
FIXTURE_JS = (
    'sectiontree = ['
    'true,"SECTION I","Live animals; animal products",'
    '[[true,"CHAPTER 1","Live animals","0100000000",null],'
    '[true,"CHAPTER 2","Meat and edible meat offal","0200000000",null]],'
    'true,"SECTION IV","Prepared foodstuffs; beverages, spirits and vinegar; '
    'tobacco and manufactured tobacco substitutes",'
    '[[true,"CHAPTER 17","Sugars and sugar confectionery","1700000000",null],'
    '[true,"CHAPTER 18","Cocoa and cocoa preparations","1800000000",null],'
    '[true,"CHAPTER 22","Beverages, spirits and vinegar","2200000000",null]]'
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
