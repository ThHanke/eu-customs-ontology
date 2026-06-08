from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.fetcher.class_api import fetch_all_full_notes, fetch_chapter_notes, fetch_full_note_text
from src.schema.legal_text import LegalSection

_NOTE_EN = {
    "noteId": "NOTE001",
    "cnCode": "2200000000",
    "noteType": "CN",
    "noteDescrSnippet": "English text for note 001",
    "ingestionDate": "2026-01-15",
}

_NOTE_DE = {
    "noteId": "NOTE001",
    "cnCode": "2200000000",
    "noteType": "CN",
    "noteDescrSnippet": "Deutschsprachiger Text für Notiz 001",
    "ingestionDate": "2026-01-15",
}


def _make_response(notes: list[dict], status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"cnNotes": notes}
    return resp


@patch("src.fetcher.class_api.time.sleep")
@patch("src.fetcher.class_api.httpx.Client")
def test_successful_bilingual_fetch(mock_client_cls, mock_sleep, tmp_path):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.side_effect = [
        _make_response([_NOTE_EN]),
        _make_response([_NOTE_DE]),
    ]

    result = fetch_chapter_notes(22, tmp_path, languages=["en", "de"])

    assert len(result) == 2
    langs = {s.language for s in result}
    assert langs == {"en", "de"}
    note_ids = {s.note_id for s in result}
    assert note_ids == {"NOTE001"}

    jsonl_path = tmp_path / "notes.jsonl"
    assert jsonl_path.exists()
    lines = [l for l in jsonl_path.read_text().splitlines() if l.strip()]
    assert len(lines) == 2


@patch("src.fetcher.class_api.time.sleep")
@patch("src.fetcher.class_api.httpx.Client")
def test_checkpoint_same_ingestion_date(mock_client_cls, mock_sleep, tmp_path):
    existing = LegalSection(
        note_id="NOTE001",
        chapter=22,
        cn_code="2200000000",
        note_type="CN",
        source_text="Existing English text",
        source_text_hash="dummy",
        ingestion_date="2026-01-15",
        language="en",
        source_url="https://example.com",
        fetched_at="2026-01-01",
    )
    jsonl_path = tmp_path / "notes.jsonl"
    jsonl_path.write_text(existing.model_dump_json() + "\n")

    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.side_effect = [
        _make_response([_NOTE_EN]),
        _make_response([_NOTE_DE]),
    ]

    result = fetch_chapter_notes(22, tmp_path, languages=["en", "de"])

    en_entries = [s for s in result if s.language == "en"]
    de_entries = [s for s in result if s.language == "de"]
    assert len(en_entries) == 1
    assert len(de_entries) == 1
    assert en_entries[0].source_text == "Existing English text"


@patch("src.fetcher.class_api.time.sleep")
@patch("src.fetcher.class_api.httpx.Client")
def test_checkpoint_ingestion_date_changed(mock_client_cls, mock_sleep, tmp_path):
    existing_en = LegalSection(
        note_id="NOTE001",
        chapter=22,
        cn_code="2200000000",
        note_type="CN",
        source_text="Old English text",
        source_text_hash="dummy",
        ingestion_date="2025-12-01",
        language="en",
        source_url="https://example.com",
        fetched_at="2025-12-01",
    )
    jsonl_path = tmp_path / "notes.jsonl"
    jsonl_path.write_text(existing_en.model_dump_json() + "\n")

    updated_note_en = dict(_NOTE_EN, ingestionDate="2026-01-15", noteDescrSnippet="Updated English text")
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.side_effect = [
        _make_response([updated_note_en]),
        _make_response([_NOTE_DE]),
    ]

    result = fetch_chapter_notes(22, tmp_path, languages=["en", "de"])

    en_entries = [s for s in result if s.language == "en"]
    de_entries = [s for s in result if s.language == "de"]
    assert len(en_entries) == 1
    assert len(de_entries) == 1
    assert en_entries[0].source_text == "Updated English text"
    assert en_entries[0].ingestion_date == "2026-01-15"


@patch("src.fetcher.class_api.time.sleep")
@patch("src.fetcher.class_api.httpx.Client")
def test_api_error_raises_value_error(mock_client_cls, mock_sleep, tmp_path):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.return_value = _make_response([], status_code=420)

    with pytest.raises(ValueError, match="chapter"):
        fetch_chapter_notes(22, tmp_path, languages=["en"])


@patch("src.fetcher.class_api.time.sleep")
@patch("src.fetcher.class_api.httpx.Client")
def test_missing_note_id_raises_key_error(mock_client_cls, mock_sleep, tmp_path):
    bad_note = {
        "cnCode": "2200000000",
        "noteType": "CN",
        "noteDescrSnippet": "Missing noteId field",
        "ingestionDate": "2026-01-15",
    }
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.return_value = _make_response([bad_note])

    with pytest.raises(KeyError):
        fetch_chapter_notes(22, tmp_path, languages=["en"])


# ---------------------------------------------------------------------------
# fetch_full_note_text tests
# ---------------------------------------------------------------------------


def _make_get_response(payload: dict | None = None, status_code: int = 200, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if payload is not None:
        resp.json.return_value = payload
    else:
        resp.json.side_effect = Exception("no JSON")
    return resp


@patch("src.fetcher.class_api.time.sleep")
def test_full_note_cached_no_http_call(mock_sleep, tmp_path):
    """Cached file is returned directly without making an HTTP call."""
    cache_file = tmp_path / "NOTE001.txt"
    cache_file.write_text("cached legal text", encoding="utf-8")

    with patch("src.fetcher.class_api.httpx.Client") as mock_client_cls:
        result = fetch_full_note_text("NOTE001", tmp_path)

    assert result == "cached legal text"
    mock_client_cls.assert_not_called()
    mock_sleep.assert_not_called()


@patch("src.fetcher.class_api.time.sleep")
@patch("src.fetcher.class_api.httpx.Client")
def test_full_note_uncached_fetched_and_written(mock_client_cls, mock_sleep, tmp_path):
    """Uncached note is fetched, decoded, written to disk, and returned."""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.return_value = _make_get_response({"text": "full legal text for NOTE002"})

    result = fetch_full_note_text("NOTE002", tmp_path)

    assert result == "full legal text for NOTE002"
    cache_file = tmp_path / "NOTE002.txt"
    assert cache_file.exists()
    assert cache_file.read_text(encoding="utf-8") == "full legal text for NOTE002"
    mock_sleep.assert_called_once_with(0.5)


@patch("src.fetcher.class_api.time.sleep")
@patch("src.fetcher.class_api.httpx.Client")
def test_full_note_http_4xx_raises_value_error(mock_client_cls, mock_sleep, tmp_path):
    """HTTP 4xx raises ValueError containing the note_id."""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.return_value = _make_get_response(status_code=404)

    with pytest.raises(ValueError, match="NOTE003"):
        fetch_full_note_text("NOTE003", tmp_path)


@patch("src.fetcher.class_api.time.sleep")
@patch("src.fetcher.class_api.httpx.Client")
def test_full_note_empty_response_returns_empty_string(mock_client_cls, mock_sleep, tmp_path):
    """Empty response body returns empty string and does not raise."""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.return_value = _make_get_response(payload=None, text="")

    result = fetch_full_note_text("NOTE004", tmp_path)

    assert result == ""
    cache_file = tmp_path / "NOTE004.txt"
    assert cache_file.exists()


# ---------------------------------------------------------------------------
# Issue 1: Path traversal guard
# ---------------------------------------------------------------------------


def test_path_traversal_raises_value_error(tmp_path):
    """note_id with path traversal sequences raises ValueError."""
    with pytest.raises(ValueError, match="Unsafe note_id"):
        fetch_full_note_text("../evil", tmp_path)


# ---------------------------------------------------------------------------
# Issue 2: Bad base64 raises ValueError (not binascii.Error)
# ---------------------------------------------------------------------------


@patch("src.fetcher.class_api.time.sleep")
@patch("src.fetcher.class_api.httpx.Client")
def test_bad_base64_raises_value_error(mock_client_cls, mock_sleep, tmp_path):
    """Invalid base64 in API response raises ValueError, not binascii.Error."""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.return_value = _make_get_response({"base64": "not-valid-base64!!!"})

    with pytest.raises(ValueError, match="Failed to decode base64"):
        fetch_full_note_text("NOTE005", tmp_path)


# ---------------------------------------------------------------------------
# Issue 3: 3xx responses are rejected (not silently cached)
# ---------------------------------------------------------------------------


@patch("src.fetcher.class_api.time.sleep")
@patch("src.fetcher.class_api.httpx.Client")
def test_3xx_response_raises_value_error(mock_client_cls, mock_sleep, tmp_path):
    """HTTP 301 response raises ValueError containing the note_id."""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.return_value = _make_get_response(status_code=301)

    with pytest.raises(ValueError, match="NOTE006"):
        fetch_full_note_text("NOTE006", tmp_path)


# ---------------------------------------------------------------------------
# Issue 4: fetch_all_full_notes continues after partial errors
# ---------------------------------------------------------------------------


@patch("src.fetcher.class_api.time.sleep")
@patch("src.fetcher.class_api.httpx.Client")
def test_fetch_all_full_notes_partial_failure(mock_client_cls, mock_sleep, tmp_path):
    """fetch_all_full_notes returns partial results when one note fails."""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client

    ok_resp = _make_get_response({"text": "good note text"})
    bad_resp = _make_get_response(status_code=500)
    mock_client.get.side_effect = [ok_resp, bad_resp]

    results = fetch_all_full_notes(tmp_path, ["NOTE_OK", "NOTE_BAD"])

    assert "NOTE_OK" in results
    assert results["NOTE_OK"] == "good note text"
    assert "NOTE_BAD" not in results
