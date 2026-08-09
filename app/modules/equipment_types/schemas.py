from typing import Optional
from pydantic import BaseModel, ConfigDict


class EquipmentTypeCreate(BaseModel):
    name: str
    has_hour_meter: bool = False


class EquipmentTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    has_hour_meter: bool


class EquipmentModelCreate(BaseModel):
    name: str
    equipment_type_id: int


class EquipmentModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    equipment_type_id: int
