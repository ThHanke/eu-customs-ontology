from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class MeasureComponent(BaseModel):
    model_config = ConfigDict(frozen=True)

    duty_expression_id: str
    duty_amount: float | None = None
    monetary_unit: str | None = None
    measurement_unit: str | None = None


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


class ChapterData(BaseModel):
    chapter: int
    measures: list[TARICMeasure]
