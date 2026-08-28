from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NameQuickIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    kind: Literal["personal", "business"] = "personal"


class NameFullIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    dob: date
    gender: str | None = ""
    kind: Literal["personal", "business"] = "personal"
    accept_terms: bool = True


class NewBornIn(BaseModel):
    dob: date
    time: str | None = ""
    place: str | None = ""
    gender: str | None = ""


class MobileIn(BaseModel):
    number: str = Field(min_length=6, max_length=24)
    name: str | None = ""
    dob: date | None = None


class MobileCompareIn(BaseModel):
    current: str = Field(min_length=6, max_length=24)
    candidate: str = Field(min_length=6, max_length=24)
    dob: date | None = None
    name: str | None = ""


class VehicleIn(BaseModel):
    registration: str = Field(min_length=2, max_length=24)
    dob: date | None = None
    vehicle_type: Literal["car", "bike", "commercial", "other"] = "car"
    owner_name: str | None = ""


class PlateSuggestIn(BaseModel):
    dob: date
    length: int = Field(default=4, ge=2, le=4)


class AnalysisOut(BaseModel):
    report_id: str | None = None
    saved: bool = False
    tier: str = "free"
    result: dict[str, Any]


class ReportOut(BaseModel):
    id: str
    type: str
    tier: str
    title: str
    subtitle: str
    score: float | None
    payload: dict[str, Any]
    result: dict[str, Any]
    created_at: Any

    model_config = ConfigDict(from_attributes=True)
