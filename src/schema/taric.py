from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class MeasureComponent(BaseModel):
    model_config = ConfigDict(frozen=True)

    duty_expression_id: str
    duty_amount: float | None = None
    monetary_unit: str | None = None
    measurement_unit: str | None = None


class MeasureTypeRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    description: str
    series_id: str = ""


class GeographicAreaRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    description: str


class DutyExpressionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    base: str = ""
    verbose_duty: str = ""


class FootnoteRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    description: str = ""


class CertificateRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_code: str
    description: str = ""


class MeasureConditionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    sid: str
    condition_code: str = ""
    document_code: str = ""
    action_code: str = ""
    condition_duty_amount: float | None = None
    condition_measurement_unit_code: str | None = None
    measure_condition_class: str = ""
    requirement: str = ""


class AdditionalCodeRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    description: str = ""


class RegulationRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    regulation_id: str
    regulation_code: str = ""
    description: str = ""
    regulation_url: str = ""
    validity_start: str = ""


class TARICMeasure(BaseModel):
    model_config = ConfigDict(frozen=True)

    sid: str
    commodity_code: str
    measure_type_id: str
    geographical_area_id: str
    validity_start: date
    validity_end: date | None = None
    regulation_id: str
    components: list[MeasureComponent]

    measure_type: MeasureTypeRecord | None = None
    geographical_area: GeographicAreaRecord | None = None
    duty_expression: DutyExpressionRecord | None = None
    footnotes: list[FootnoteRecord] = []
    conditions: list[MeasureConditionRecord] = []
    additional_codes: list[AdditionalCodeRecord] = []
    regulations: list[RegulationRecord] = []
    quota_order_number: str | None = None


class ChapterData(BaseModel):
    chapter: int
    measures: list[TARICMeasure]
