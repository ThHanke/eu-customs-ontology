from __future__ import annotations

import datetime
import hashlib
import re
from typing import Optional

from src.schema.axiom_candidate import AxiomCandidate
from src.schema.legal_text import LegalSection

SKIP_NOTE_TYPES = frozenset({
    "CN Chapter Notes",
    "CN Section Notes",
})

PROCESS_MAP: dict[str, str] = {
    "distillation of grape wine": "GrapeDistillation",
    "distillation of grape marc": "GrapeDistillation",
    "distilling grape wine": "GrapeDistillation",
    "distilling grape marc": "GrapeDistillation",
    "fermentation of malted barley": "MaltFermentation",
    "fermented from malted barley": "MaltFermentation",
    "fermentation of grapes": "GrapeFermentation",
    "fermented grape": "GrapeFermentation",
    "distillation of grain": "GrainDistillation",
    "fermented from grain": "GrainDistillation",
    "distillation of sugar cane": "SugarCaneDistillation",
}

_FACET_MAP = {
    "not exceeding": "maxInclusive",
    "exceeding": "minExclusive",
    "less than": "maxExclusive",
    "not less than": "minInclusive",
}

_RE_ABV = re.compile(
    r"alcoholic strength by volume(?: of)?\s*(not exceeding|exceeding|less than|not less than)\s*(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
_RE_CONTAINER = re.compile(
    r"in containers holding (\d+(?:\.\d+)?)\s*litres? or less",
    re.IGNORECASE,
)
_RE_DISTIL = re.compile(
    r"obtained by(?: the)? distillation of (grape wine|grape marc|grain|sugar cane)"
    r"|distilling (grape wine|grape marc|grain)",
    re.IGNORECASE,
)
_RE_FERMENT = re.compile(
    r"obtained by(?: the)? fermentation of (malted barley|grapes|grain|fruit)"
    r"|fermented (?:from )?(?:\s*)(malted barley|grapes|grain)",
    re.IGNORECASE,
)
_RE_CARBONATED = re.compile(r"\b(not )?carbonated\b", re.IGNORECASE)
_RE_DENATURED = re.compile(r"\bdenatured\b", re.IGNORECASE)
_RE_PRESSURE = re.compile(
    r"excess pressure of not less than (\d+(?:\.\d+)?)\s*bar",
    re.IGNORECASE,
)


def _process_lookup(phrase: str) -> Optional[str]:
    key = phrase.strip().lower()
    if key in PROCESS_MAP:
        return PROCESS_MAP[key]
    return None


def extract_candidates(
    section: LegalSection,
    owl_class: str,
    chapter: int,
) -> list[AxiomCandidate]:
    """Extract AxiomCandidate list from a LegalSection using regex patterns.

    Returns empty list if note_type is in SKIP_NOTE_TYPES or no patterns match.
    """
    if section.note_type in SKIP_NOTE_TYPES:
        return []

    text = section.source_text
    source_text_hash = hashlib.sha256(text.encode()).hexdigest()
    today = datetime.date.today().isoformat()

    def _build(
        restriction_type: str,
        property_iri: str,
        value: str,
        facet: Optional[str],
        confidence: float,
    ) -> AxiomCandidate:
        return AxiomCandidate(
            chapter=chapter,
            owl_class=owl_class,
            restriction_type=restriction_type,
            property_iri=property_iri,
            value=value,
            facet=facet,
            source_note_id=section.note_id,
            source_text=text,
            source_text_hash=source_text_hash,
            source_ingestion_date=section.ingestion_date,
            status="proposed",
            confidence=confidence,
            extractor="rule-based",
            extracted_at=today,
        )

    candidates: list[AxiomCandidate] = []

    for m in _RE_ABV.finditer(text):
        operator = m.group(1).lower()
        num = m.group(2)
        facet = _FACET_MAP.get(operator)
        if facet:
            candidates.append(_build("decimalRange", "eucn:alcoholByVolumePercent", num, facet, 0.95))

    for m in _RE_CONTAINER.finditer(text):
        candidates.append(_build("decimalRange", "eucn:maxContainerVolumeL", m.group(1), "maxInclusive", 0.95))

    for m in _RE_DISTIL.finditer(text):
        commodity = (m.group(1) or m.group(2) or "").strip().lower()
        if m.group(2) is not None:
            lookup_key = f"distilling {commodity}"
        else:
            lookup_key = f"distillation of {commodity}"
        process_label = PROCESS_MAP.get(lookup_key) or _process_lookup(m.group(0).lower())
        if process_label is not None:
            candidates.append(_build("someValuesFrom", "eucn:producedBy", process_label, None, 0.90))

    for m in _RE_FERMENT.finditer(text):
        phrase = (m.group(1) or m.group(3) or "").strip().lower()
        if phrase == "grapes":
            lookup_key = "fermentation of grapes"
        elif phrase == "malted barley":
            lookup_key = "fermentation of malted barley"
        elif phrase == "grain":
            lookup_key = "fermented from grain"
        else:
            lookup_key = phrase
        process_label = PROCESS_MAP.get(lookup_key)
        if process_label is not None:
            candidates.append(_build("someValuesFrom", "eucn:producedBy", process_label, None, 0.90))

    for m in _RE_CARBONATED.finditer(text):
        negated = bool(m.group(1))
        value = "false" if negated else "true"
        candidates.append(_build("hasValue", "eucn:isCarbonated", value, None, 0.90))

    for _ in _RE_DENATURED.finditer(text):
        candidates.append(_build("hasValue", "eucn:isDenatured", "true", None, 0.90))

    for m in _RE_PRESSURE.finditer(text):
        candidates.append(_build("decimalRange", "eucn:pressureBar", m.group(1), "minInclusive", 0.95))

    return candidates
