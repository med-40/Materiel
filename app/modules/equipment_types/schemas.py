from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

MEASUREMENT_UNITS = {"km", "hours"}


class EquipmentTypeCreate(BaseModel):
    name: str
    measurement_unit: str  # "km" أو "hours"

    @field_validator("measurement_unit")
    @classmethod
    def measurement_unit_valid(cls, v: str) -> str:
        if v not in MEASUREMENT_UNITS:
            raise ValueError(f"وحدة القياس يجب أن تكون أحد: {MEASUREMENT_UNITS}")
        return v


class EquipmentTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    measurement_unit: str


class EquipmentModelCreate(BaseModel):
    name: str
    equipment_type_id: int


class EquipmentModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    equipment_type_id: int
