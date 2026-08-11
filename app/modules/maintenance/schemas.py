from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MaintenanceCreate(BaseModel):
    """
    إنشاء سجل صيانة.

    في الصيانة الدورية:
    - يختار المستخدم العتاد.
    - يختار عملية الصيانة من العمليات المتاحة لذلك العتاد.
    - النظام يعرف شروط الاستحقاق من MaintenanceSchedule.
    """

    equipment_id: int

    maintenance_schedule_id: Optional[int] = None

    maintenance_type_id: Optional[int] = None

    reported_date: date

    description: Optional[str] = None

    @field_validator("equipment_id")
    @classmethod
    def equipment_id_valid(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("معرف العتاد غير صحيح")
        return value

    @field_validator("maintenance_schedule_id")
    @classmethod
    def maintenance_schedule_id_valid(
        cls,
        value: Optional[int],
    ) -> Optional[int]:
        if value is not None and value <= 0:
            raise ValueError("معرف عملية الصيانة غير صحيح")
        return value

    @field_validator("maintenance_type_id")
    @classmethod
    def maintenance_type_id_valid(
        cls,
        value: Optional[int],
    ) -> Optional[int]:
        if value is not None and value <= 0:
            raise ValueError("معرف نوع الصيانة غير صحيح")
        return value

    @field_validator("description")
    @classmethod
    def description_clean(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is not None:
            value = value.strip()
            return value or None

        return None


class MaintenanceClose(BaseModel):
    """
    إغلاق سجل الصيانة.

    meter_reading:
    - km إذا كان نوع العتاد يعتمد على الكيلومترات.
    - hours إذا كان نوع العتاد يعتمد على ساعات التشغيل.

    تحديد أي عداد يستخدم يتم من EquipmentType.measurement_unit،
    وليس من المستخدم.
    """

    resolved_date: date

    meter_reading: Optional[Decimal] = Field(
        default=None,
        ge=0,
    )

    resolution_notes: Optional[str] = None

    performed_by: Optional[str] = None

    location: Optional[str] = None

    @field_validator("resolution_notes")
    @classmethod
    def resolution_notes_clean(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is not None:
            value = value.strip()
            return value or None

        return None

    @field_validator("performed_by")
    @classmethod
    def performed_by_clean(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is not None:
            value = value.strip()
            return value or None

        return None

    @field_validator("location")
    @classmethod
    def location_clean(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is not None:
            value = value.strip()
            return value or None

        return None


class MaintenanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

    equipment_id: int

    maintenance_schedule_id: Optional[int] = None

    maintenance_type_id: Optional[int] = None

    is_scheduled: bool

    status: str

    reported_date: date

    resolved_date: Optional[date] = None

    meter_reading: Optional[Decimal] = None

    location: Optional[str] = None

    performed_by: Optional[str] = None

    description: Optional[str] = None

    resolution_notes: Optional[str] = None
