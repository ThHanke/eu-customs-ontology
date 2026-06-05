import pytest
from pathlib import Path

from src.fetcher.taric_xml import fetch_and_parse

pytestmark = pytest.mark.skip(reason="requires local TARIC XML file; run with --xml-path")


def test_chapter22_has_mfn_measures(tmp_path):
    xml_path = Path("data/intermediate/taric_full.xml")
    if not xml_path.exists():
        pytest.skip("TARIC XML not present")

    data = fetch_and_parse(chapter=22, xml_path=xml_path)
    assert len(data.measures) >= 10
    mfn = [m for m in data.measures if m.measure_type_id == "103" and m.geographical_area_id == "1011"]
    assert len(mfn) >= 1
    for m in data.measures:
        assert m.sid, "sid must be non-null"
