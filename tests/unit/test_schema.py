import pytest
from datetime import date
from pydantic import ValidationError

from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree
from src.schema.taric import ChapterData, MeasureComponent, TARICMeasure


def _make_node(is_terminal=False, cn_code=None, answers=None):
    return {
        "node_id": "n1",
        "question_text": "Is the product a beverage?",
        "answer_options": answers or [],
        "is_terminal": is_terminal,
        "cn_code": cn_code,
        "path_from_root": [],
    }


def _make_measure(**kwargs):
    base = {
        "sid": "12345",
        "commodity_code": "2204219100",
        "measure_type_id": "103",
        "geographical_area_id": "1011",
        "validity_start": date(2024, 1, 1),
        "validity_end": None,
        "regulation_id": "R2024/0001",
        "components": [],
    }
    base.update(kwargs)
    return base


class TestClassificationNode:
    def test_round_trip(self):
        data = _make_node()
        node = ClassificationNode.model_validate(data)
        dumped = node.model_dump()
        node2 = ClassificationNode.model_validate(dumped)
        assert node == node2

    def test_terminal_with_cn_code(self):
        data = _make_node(is_terminal=True, cn_code="2204219100")
        node = ClassificationNode.model_validate(data)
        assert node.cn_code == "2204219100"
        assert node.is_terminal is True

    def test_terminal_empty_answers(self):
        data = _make_node(is_terminal=True, cn_code="2204219100", answers=[])
        node = ClassificationNode.model_validate(data)
        assert node.answer_options == []

    def test_cn_code_on_nonterminal_raises(self):
        data = _make_node(is_terminal=False, cn_code="2204219100")
        with pytest.raises(ValidationError):
            ClassificationNode.model_validate(data)

    def test_missing_node_id_raises(self):
        data = _make_node()
        data.pop("node_id")
        with pytest.raises(ValidationError):
            ClassificationNode.model_validate(data)


class TestTARICMeasure:
    def test_round_trip(self):
        data = _make_measure(components=[
            {"duty_expression_id": "01", "duty_amount": 13.4, "monetary_unit": None, "measurement_unit": None}
        ])
        m = TARICMeasure.model_validate(data)
        assert m.components[0].duty_amount == 13.4
        dumped = m.model_dump()
        assert TARICMeasure.model_validate(dumped) == m

    def test_validity_end_none(self):
        m = TARICMeasure.model_validate(_make_measure(validity_end=None))
        assert m.validity_end is None

    def test_validity_end_date_string(self):
        m = TARICMeasure.model_validate(_make_measure(validity_end="2026-12-31"))
        assert m.validity_end == date(2026, 12, 31)

    def test_missing_sid_raises(self):
        data = _make_measure()
        data.pop("sid")
        with pytest.raises(ValidationError):
            TARICMeasure.model_validate(data)

    def test_empty_components(self):
        m = TARICMeasure.model_validate(_make_measure())
        assert m.components == []

    def test_monetary_unit(self):
        comp = {"duty_expression_id": "02", "duty_amount": 32.0, "monetary_unit": "EUR", "measurement_unit": "hl"}
        m = TARICMeasure.model_validate(_make_measure(components=[comp]))
        assert m.components[0].monetary_unit == "EUR"


class TestSchemaIntrospection:
    def test_wizard_tree_json_schema(self):
        schema = WizardTree.model_json_schema()
        assert "properties" in schema

    def test_chapter_data_json_schema(self):
        schema = ChapterData.model_json_schema()
        assert "properties" in schema
