from __future__ import annotations

import pytest

from src.schema.legal_text import LegalSection
from src.agent.rule_extractor import extract_candidates, SKIP_NOTE_TYPES


def _section(source_text: str, note_type: str = "CNEN HS Subheading Notes") -> LegalSection:
    return LegalSection(
        note_id="test-note-id",
        chapter=22,
        cn_code="2208",
        note_type=note_type,
        source_text=source_text,
        ingestion_date="2023-10-06",
        language="en",
        source_url="https://webgate.ec.europa.eu/class-public-ui-web/#/search",
        fetched_at="2026-06-08",
    )


def test_abv_not_exceeding():
    section = _section("alcoholic strength by volume not exceeding 2.8%")
    candidates = extract_candidates(section, owl_class="Beer", chapter=22)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.restriction_type == "decimalRange"
    assert c.property_iri == "eucn:alcoholByVolumePercent"
    assert c.facet == "maxInclusive"
    assert c.value == "2.8"
    assert c.confidence == 0.95


def test_distillation_grape_wine():
    section = _section("obtained by distilling grape wine")
    candidates = extract_candidates(section, owl_class="Brandy", chapter=22)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.restriction_type == "someValuesFrom"
    assert c.property_iri == "eucn:producedBy"
    assert c.value == "GrapeDistillation"
    assert c.confidence == 0.90


def test_container_volume():
    section = _section("in containers holding 2 litres or less")
    candidates = extract_candidates(section, owl_class="Wine", chapter=22)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.restriction_type == "decimalRange"
    assert c.property_iri == "eucn:maxContainerVolumeL"
    assert c.facet == "maxInclusive"
    assert c.value == "2"


def test_carbonated_true():
    section = _section("carbonated")
    candidates = extract_candidates(section, owl_class="SparklingWine", chapter=22)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.restriction_type == "hasValue"
    assert c.property_iri == "eucn:isCarbonated"
    assert c.value == "true"


def test_not_carbonated():
    section = _section("not carbonated")
    candidates = extract_candidates(section, owl_class="StillWine", chapter=22)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.restriction_type == "hasValue"
    assert c.property_iri == "eucn:isCarbonated"
    assert c.value == "false"


def test_excess_pressure():
    section = _section("excess pressure of not less than 3 bar")
    candidates = extract_candidates(section, owl_class="SparklingWine", chapter=22)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.restriction_type == "decimalRange"
    assert c.property_iri == "eucn:pressureBar"
    assert c.facet == "minInclusive"
    assert c.value == "3"


def test_no_pattern_match_returns_empty():
    section = _section("This text contains no relevant patterns at all.")
    candidates = extract_candidates(section, owl_class="Wine", chapter=22)
    assert candidates == []


def test_skip_note_type_chapter_notes():
    section = _section(
        "alcoholic strength by volume not exceeding 2.8%",
        note_type="CN Chapter Notes",
    )
    candidates = extract_candidates(section, owl_class="Beer", chapter=22)
    assert candidates == []


def test_skip_note_type_section_notes():
    section = _section(
        "alcoholic strength by volume not exceeding 2.8%",
        note_type="CN Section Notes",
    )
    candidates = extract_candidates(section, owl_class="Beer", chapter=22)
    assert candidates == []


def test_abv_exceeding():
    section = _section("alcoholic strength by volume exceeding 10%")
    candidates = extract_candidates(section, owl_class="Wine", chapter=22)
    assert len(candidates) == 1
    assert candidates[0].facet == "minExclusive"
    assert candidates[0].value == "10"


def test_abv_less_than():
    section = _section("alcoholic strength by volume less than 15%")
    candidates = extract_candidates(section, owl_class="Wine", chapter=22)
    assert len(candidates) == 1
    assert candidates[0].facet == "maxExclusive"
    assert candidates[0].value == "15"


def test_abv_not_less_than():
    section = _section("alcoholic strength by volume not less than 80%")
    candidates = extract_candidates(section, owl_class="Spirits", chapter=22)
    assert len(candidates) == 1
    assert candidates[0].facet == "minInclusive"
    assert candidates[0].value == "80"


def test_denatured():
    section = _section("The product is denatured alcohol.")
    candidates = extract_candidates(section, owl_class="DenaturatedAlcohol", chapter=22)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.restriction_type == "hasValue"
    assert c.property_iri == "eucn:isDenatured"
    assert c.value == "true"


def test_multiple_patterns_same_text():
    section = _section(
        "alcoholic strength by volume not exceeding 2.8% in containers holding 2 litres or less"
    )
    candidates = extract_candidates(section, owl_class="Beer", chapter=22)
    assert len(candidates) == 2
    props = {c.property_iri for c in candidates}
    assert "eucn:alcoholByVolumePercent" in props
    assert "eucn:maxContainerVolumeL" in props


def test_candidate_id_is_deterministic():
    section = _section("alcoholic strength by volume not exceeding 2.8%")
    c1 = extract_candidates(section, owl_class="Beer", chapter=22)[0]
    c2 = extract_candidates(section, owl_class="Beer", chapter=22)[0]
    assert c1.candidate_id == c2.candidate_id


def test_fermentation_malted_barley():
    section = _section("obtained by fermentation of malted barley")
    candidates = extract_candidates(section, owl_class="Beer", chapter=22)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.value == "MaltFermentation"
    assert c.confidence == 0.90


def test_distillation_grain():
    section = _section("obtained by distillation of grain")
    candidates = extract_candidates(section, owl_class="GrainSpirit", chapter=22)
    assert len(candidates) == 1
    assert candidates[0].value == "GrainDistillation"
