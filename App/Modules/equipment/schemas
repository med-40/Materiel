from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

TECHNICAL_CONDITIONS = {"ready", "broken"}
OPERATIONAL_STATUSES = {
    "available",
    "in_mission",
    "in_maintenance",
    "in_external_workshop",
    "unavailable",
}


class EquipmentBase(BaseModel):
    asset_code: str
    registration_number: Optional[str] = None
    vin: Optional[str] = None
    category: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    acquisition_document: Optional[str] = None
    acquisition_date: Optional[date] = None
    technical_condition: str = "ready"
    operational_status: str = "available"
    current_odometer: Optional[Decimal] = 0
    current_hours: Optional[Decimal] = 0
    notes: Optional[str] = None

    @field_validator("technical_condition")
    @classmethod
    def technical_condition_valid(cls, v: str) -> str:
        if v not in TECHNICAL_CONDITIONS:
            raise ValueError(f"الحالة الفنية يجب أن تكون أحد: {TECHNICAL_CONDITIONS}")
        return v

    @field_validator("operational_status")
    @classmethod
    def operational_status_valid(cls, v: str) -> str:
        if v not in OPERATIONAL_STATUSES:
            raise ValueError(f"الوضعية يجب أن تكون أحد: {OPERATIONAL_STATUSES}")
        return v


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    registration_number: Optional[str] = None
    vin: Optional[str] = None
    category: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    acquisition_document: Optional[str] = None
    acquisition_date: Optional[date] = None
    technical_condition: Optional[str] = None
    operational_status: Optional[str] = None
    current_odometer: Optional[Decimal] = None
    current_hours: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("technical_condition")
    @classmethod
    def technical_condition_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in TECHNICAL_CONDITIONS:
            raise ValueError(f"الحالة الفنية يجب أن تكون أحد: {TECHNICAL_CONDITIONS}")
        return v

    @field_validator("operational_status")
    @classmethod
    def operational_status_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in OPERATIONAL_STATUSES:
            raise ValueError(f"الوضعية يجب أن تكون أحد: {OPERATIONAL_STATUSES}")
        return v


class EquipmentOut(EquipmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
