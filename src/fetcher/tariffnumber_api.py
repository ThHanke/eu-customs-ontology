from __future__ import annotations

import logging
import re
import time

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.tariffnumber.com/api/v1"
_HTML_TAGS = re.compile(r"<[^>]+>")
_LEADING_CODE = re.compile(r"^\d[\d\s]*\s")


def _strip_html(value: str) -> str:
    """Strip HTML tags; also remove leading code digits left by <span><em>…</em></span>."""
    text = _HTML_TAGS.sub("", value).strip()
    return _LEADING_CODE.sub("", text).strip()


def fetch_code_labels(
    codes: list[str],
    year: int = 2026,
    languages: tuple[str, ...] = ("en", "de"),
) -> dict[str, dict[str, str]]:
    """Fetch bilingual labels for a list of CN codes from tariffnumber.com.

    Returns ``{code: {"en": "...", "de": "..."}}``; missing languages are omitted
    from the inner dict.  Skips codes for which no exact match is found.
    """
    result: dict[str, dict[str, str]] = {c: {} for c in codes}
    with httpx.Client(timeout=20) as client:
        for code in codes:
            for lang in languages:
                time.sleep(0.15)
                try:
                    resp = client.get(
                        f"{BASE_URL}/cnSuggest",
                        params={"term": code, "lang": lang, "year": str(year)},
                    )
                except httpx.HTTPError as exc:
                    logger.warning("tariffnumber API error for %s/%s: %s", code, lang, exc)
                    continue
                if resp.status_code != 200:
                    logger.warning("tariffnumber API %d for %s/%s", resp.status_code, code, lang)
                    continue
                # API may return padded codes (e.g. "220300" for query "2203").
                # Accept: exact match OR shortest suggestion that starts with our code.
                suggestions = resp.json().get("suggestions", [])
                match = next(
                    (s for s in suggestions if s["code"] == code),
                    None,
                )
                if match is None:
                    candidates = [s for s in suggestions if s["code"].startswith(code)]
                    if candidates:
                        match = min(candidates, key=lambda s: len(s["code"]))
                if match:
                    result[code][lang] = _strip_html(match["value"])
    return result
