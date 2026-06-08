import hashlib
import pytest
from pydantic import ValidationError

from src.schema.legal_text import LegalSection


def _make_legal_section(**kwargs):
    base = {
        "note_id": "NOTE001",
        "chapter": 22,
        "cn_code": "220820",
        "note_type": "CNEN HS Subheading Notes",
        "source_text": "This is a test source text.",
        "source_text_hash": hashlib.sha256("This is a test source text.".encode()).hexdigest(),
        "ingestion_date": "2026-06-08",
        "language": "en",
        "source_url": "https://webgate.ec.europa.eu/class-public-ui-web/#/search",
        "fetched_at": "2026-06-08T10:00:00Z",
    }
    base.update(kwargs)
    return base


class TestLegalSectionSourceTextHash:
    def test_source_text_hash_auto_computed(self):
        data = _make_legal_section()
        del data["source_text_hash"]
        section = LegalSection.model_validate(data)
        expected_hash = hashlib.sha256("This is a test source text.".encode()).hexdigest()
        assert section.source_text_hash == expected_hash

    def test_source_text_hash_provided_not_rehashed(self):
        custom_hash = "custom_hash_value_123"
        data = _make_legal_section(source_text_hash=custom_hash)
        section = LegalSection.model_validate(data)
        assert section.source_text_hash == custom_hash

    def test_source_text_hash_matches_sha256(self):
        test_text = "Another test source text with special chars: αβγ 中文"
        data = _make_legal_section(source_text=test_text)
        del data["source_text_hash"]
        section = LegalSection.model_validate(data)
        expected_hash = hashlib.sha256(test_text.encode()).hexdigest()
        assert section.source_text_hash == expected_hash


class TestLegalSectionValidation:
    def test_missing_note_id_raises(self):
        data = _make_legal_section()
        del data["note_id"]
        with pytest.raises(ValidationError):
            LegalSection.model_validate(data)

    def test_missing_chapter_raises(self):
        data = _make_legal_section()
        del data["chapter"]
        with pytest.raises(ValidationError):
            LegalSection.model_validate(data)

    def test_missing_cn_code_raises(self):
        data = _make_legal_section()
        del data["cn_code"]
        with pytest.raises(ValidationError):
            LegalSection.model_validate(data)

    def test_missing_source_text_raises(self):
        data = _make_legal_section()
        del data["source_text"]
        with pytest.raises(ValidationError):
            LegalSection.model_validate(data)


class TestLegalSectionCNCode:
    def test_cn_code_two_digit(self):
        data = _make_legal_section(cn_code="22")
        section = LegalSection.model_validate(data)
        assert section.cn_code == "22"

    def test_cn_code_four_digit(self):
        data = _make_legal_section(cn_code="2208")
        section = LegalSection.model_validate(data)
        assert section.cn_code == "2208"

    def test_cn_code_six_digit(self):
        data = _make_legal_section(cn_code="220820")
        section = LegalSection.model_validate(data)
        assert section.cn_code == "220820"

    def test_cn_code_ten_digit(self):
        data = _make_legal_section(cn_code="2208201080")
        section = LegalSection.model_validate(data)
        assert section.cn_code == "2208201080"


class TestLegalSectionNoteType:
    def test_note_type_standard(self):
        data = _make_legal_section(note_type="CNEN HS Subheading Notes")
        section = LegalSection.model_validate(data)
        assert section.note_type == "CNEN HS Subheading Notes"

    def test_note_type_arbitrary_string(self):
        data = _make_legal_section(note_type="Some arbitrary note type")
        section = LegalSection.model_validate(data)
        assert section.note_type == "Some arbitrary note type"

    def test_note_type_empty_string(self):
        data = _make_legal_section(note_type="")
        section = LegalSection.model_validate(data)
        assert section.note_type == ""


class TestLegalSectionRoundTrip:
    def test_round_trip(self):
        data = _make_legal_section()
        del data["source_text_hash"]
        section = LegalSection.model_validate(data)
        dumped = section.model_dump()
        section2 = LegalSection.model_validate(dumped)
        assert section == section2

    def test_round_trip_with_provided_hash(self):
        data = _make_legal_section(source_text_hash="custom_hash")
        section = LegalSection.model_validate(data)
        dumped = section.model_dump()
        section2 = LegalSection.model_validate(dumped)
        assert section == section2
        assert section2.source_text_hash == "custom_hash"
