from datetime import date
from typing import Optional
from pydantic import BaseModel


class MaintenanceCreate(BaseModel):
    equipment_id: int
    reported_date: date
    description: Optional[str] = None


class MaintenanceClose(BaseModel):
    resolved_date: date
    resolution_notes: Optional[str] = None


class MaintenanceOut(BaseModel):
    id: int
    equipment_id: int
    status: str
    reported_date: date
    resolved_date: Optional[date]
    description: Optional[str]
    resolution_notes: Optional[str]

    class Config:
        from_attributes = True
