import textwrap
import pytest
from io import BytesIO

from src.fetcher.taric_xml import parse_taric_xml


FIXTURE_XML = textwrap.dedent("""\
<?xml version="1.0" encoding="UTF-8"?>
<env:envelope xmlns:env="urn:publicid:-:DGTAXUD:TARIC3.0:ENV"
              xmlns:oub="urn:publicid:-:DGTAXUD:TARIC3.0:OUB">
  <env:transaction>
    <env:record.code>271</env:record.code>
    <oub:measure>
      <oub:sid>1001</oub:sid>
      <oub:goods.nomenclature.item.id>2204219100</oub:goods.nomenclature.item.id>
      <oub:measure.type.id>103</oub:measure.type.id>
      <oub:geographical.area.id>1011</oub:geographical.area.id>
      <oub:validity.start.date>2024-01-01</oub:validity.start.date>
      <oub:validity.end.date></oub:validity.end.date>
      <oub:measure.generating.regulation.id>R2024/001</oub:measure.generating.regulation.id>
    </oub:measure>
  </env:transaction>
  <env:transaction>
    <env:record.code>430</env:record.code>
    <oub:measure.component>
      <oub:measure.sid>1001</oub:measure.sid>
      <oub:duty.expression.id>01</oub:duty.expression.id>
      <oub:duty.amount>13.4</oub:duty.amount>
      <oub:monetary.unit.code></oub:monetary.unit.code>
      <oub:measurement.unit.code></oub:measurement.unit.code>
    </oub:measure.component>
  </env:transaction>
  <env:transaction>
    <env:record.code>271</env:record.code>
    <oub:measure>
      <oub:sid>1002</oub:sid>
      <oub:goods.nomenclature.item.id>2204219200</oub:goods.nomenclature.item.id>
      <oub:measure.type.id>103</oub:measure.type.id>
      <oub:geographical.area.id>1011</oub:geographical.area.id>
      <oub:validity.start.date>2024-01-01</oub:validity.start.date>
      <oub:validity.end.date>2026-12-31</oub:validity.end.date>
      <oub:measure.generating.regulation.id>R2024/001</oub:measure.generating.regulation.id>
    </oub:measure>
  </env:transaction>
  <env:transaction>
    <env:record.code>430</env:record.code>
    <oub:measure.component>
      <oub:measure.sid>1002</oub:measure.sid>
      <oub:duty.expression.id>01</oub:duty.expression.id>
      <oub:duty.amount>32.0</oub:duty.amount>
      <oub:monetary.unit.code>EUR</oub:monetary.unit.code>
      <oub:measurement.unit.code>hl</oub:measurement.unit.code>
    </oub:measure.component>
  </env:transaction>
  <env:transaction>
    <env:record.code>271</env:record.code>
    <oub:measure>
      <oub:sid>2001</oub:sid>
      <oub:goods.nomenclature.item.id>0101210000</oub:goods.nomenclature.item.id>
      <oub:measure.type.id>103</oub:measure.type.id>
      <oub:geographical.area.id>1011</oub:geographical.area.id>
      <oub:validity.start.date>2024-01-01</oub:validity.start.date>
      <oub:validity.end.date></oub:validity.end.date>
      <oub:measure.generating.regulation.id>R2024/999</oub:measure.generating.regulation.id>
    </oub:measure>
  </env:transaction>
</env:envelope>
""").encode()

FIXTURE_NO_COMPONENTS_XML = textwrap.dedent("""\
<?xml version="1.0" encoding="UTF-8"?>
<env:envelope xmlns:env="urn:publicid:-:DGTAXUD:TARIC3.0:ENV"
              xmlns:oub="urn:publicid:-:DGTAXUD:TARIC3.0:OUB">
  <env:transaction>
    <env:record.code>271</env:record.code>
    <oub:measure>
      <oub:sid>3001</oub:sid>
      <oub:goods.nomenclature.item.id>2201100000</oub:goods.nomenclature.item.id>
      <oub:measure.type.id>105</oub:measure.type.id>
      <oub:geographical.area.id>1011</oub:geographical.area.id>
      <oub:validity.start.date>2023-06-01</oub:validity.start.date>
      <oub:validity.end.date></oub:validity.end.date>
      <oub:measure.generating.regulation.id>R2023/042</oub:measure.generating.regulation.id>
    </oub:measure>
  </env:transaction>
</env:envelope>
""").encode()


class TestParseTaricXml:
    def test_chapter_filter(self):
        data = parse_taric_xml(BytesIO(FIXTURE_XML), chapter=22)
        assert data.chapter == 22
        sids = {m.sid for m in data.measures}
        assert sids == {"1001", "1002"}
        assert "2001" not in sids

    def test_validity_end_empty_is_none(self):
        data = parse_taric_xml(BytesIO(FIXTURE_XML), chapter=22)
        m = next(m for m in data.measures if m.sid == "1001")
        assert m.validity_end is None

    def test_validity_end_date_parsed(self):
        from datetime import date
        data = parse_taric_xml(BytesIO(FIXTURE_XML), chapter=22)
        m = next(m for m in data.measures if m.sid == "1002")
        assert m.validity_end == date(2026, 12, 31)

    def test_component_monetary_unit(self):
        data = parse_taric_xml(BytesIO(FIXTURE_XML), chapter=22)
        m = next(m for m in data.measures if m.sid == "1002")
        assert m.components[0].monetary_unit == "EUR"
        assert m.components[0].measurement_unit == "hl"
        assert m.components[0].duty_amount == 32.0

    def test_component_empty_monetary_unit_is_none(self):
        data = parse_taric_xml(BytesIO(FIXTURE_XML), chapter=22)
        m = next(m for m in data.measures if m.sid == "1001")
        assert m.components[0].monetary_unit is None
        assert m.components[0].measurement_unit is None

    def test_no_components_is_valid(self):
        data = parse_taric_xml(BytesIO(FIXTURE_NO_COMPONENTS_XML), chapter=22)
        assert len(data.measures) == 1
        assert data.measures[0].components == []

    def test_10digit_commodity_filtered(self):
        data = parse_taric_xml(BytesIO(FIXTURE_XML), chapter=22)
        codes = {m.commodity_code for m in data.measures}
        assert "2204219100" in codes

    def test_chapter_01_excluded(self):
        data = parse_taric_xml(BytesIO(FIXTURE_XML), chapter=1)
        sids = {m.sid for m in data.measures}
        assert sids == {"2001"}
