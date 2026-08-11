from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.modules.equipment import services as equipment_services
from app.modules.equipment_types import services as type_services
from app.modules.maintenance.models import (
    MaintenanceRecord,
    MaintenanceSchedule,
    MaintenanceType,
    MeterReading,
)


MAINTENANCE_STATUSES = {"open", "closed"}
MEASUREMENT_UNITS = {"km", "hours"}


# ============================================================
# Maintenance Types
# ============================================================

def create_maintenance_type(
    db: Session,
    name: str,
    description: Optional[str] = None,
) -> MaintenanceType:

    name = name.strip()

    if not name:
        raise ValueError("اسم نوع الصيانة مطلوب")

    existing = (
        db.query(MaintenanceType)
        .filter(MaintenanceType.name == name)
        .first()
    )

    if existing:
        raise ValueError("نوع الصيانة موجود مسبقًا")

    item = MaintenanceType(
        name=name,
        description=description.strip() if description else None,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


def list_maintenance_types(
    db: Session,
) -> list[MaintenanceType]:

    return (
        db.query(MaintenanceType)
        .order_by(MaintenanceType.name)
        .all()
    )


def get_maintenance_type(
    db: Session,
    type_id: int,
) -> Optional[MaintenanceType]:

    return (
        db.query(MaintenanceType)
        .filter(MaintenanceType.id == type_id)
        .first()
    )


# ============================================================
# Internal code
# ============================================================

def generate_internal_code(
    db: Session,
    maintenance_type_id: int,
) -> str:

    prefix = f"MS-{maintenance_type_id}"

    count = (
        db.query(MaintenanceSchedule)
        .filter(
            MaintenanceSchedule.maintenance_type_id
            == maintenance_type_id
        )
        .count()
    )

    next_number = count + 1

    while True:
        code = f"{prefix}-{next_number:04d}"

        exists = (
            db.query(MaintenanceSchedule)
            .filter(
                MaintenanceSchedule.internal_code == code
            )
            .first()
        )

        if not exists:
            return code

        next_number += 1


# ============================================================
# Maintenance Schedule
# ============================================================

def create_maintenance_schedule(
    db: Session,
    name: str,
    equipment_type_id: int,
    maintenance_type_id: int,
    interval_km: Optional[int] = None,
    interval_hours: Optional[int] = None,
    interval_days: Optional[int] = None,
    makes_equipment_unavailable: bool = False,
    notify_offset_days: Optional[int] = 0,
    actions_required: Optional[str] = None,
    description: Optional[str] = None,
) -> MaintenanceSchedule:

    name = name.strip()

    if not name:
        raise ValueError("اسم خطة الصيانة مطلوب")

    equipment_type = type_services.get_type(
        db,
        equipment_type_id,
    )

    if not equipment_type:
        raise ValueError("نوع العتاد غير موجود")

    maintenance_type = get_maintenance_type(
        db,
        maintenance_type_id,
    )

    if not maintenance_type:
        raise ValueError("نوع الصيانة غير موجود")

    if equipment_type.measurement_unit not in MEASUREMENT_UNITS:
        raise ValueError(
            "وحدة قياس نوع العتاد يجب أن تكون km أو hours"
        )

    # --------------------------------------------------------
    # التحقق من شروط الاستحقاق
    # --------------------------------------------------------

    if (
        interval_km is None
        and interval_hours is None
        and interval_days is None
    ):
        raise ValueError(
            "يجب تحديد شرط واحد على الأقل: الكيلومترات أو الساعات أو الأيام"
        )

    if interval_km is not None and interval_km <= 0:
        raise ValueError(
            "فترة الكيلومترات يجب أن تكون أكبر من صفر"
        )

    if interval_hours is not None and interval_hours <= 0:
        raise ValueError(
            "فترة الساعات يجب أن تكون أكبر من صفر"
        )

    if interval_days is not None and interval_days <= 0:
        raise ValueError(
            "فترة الأيام يجب أن تكون أكبر من صفر"
        )

    if notify_offset_days is not None and notify_offset_days < 0:
        raise ValueError(
            "عدد أيام التنبيه لا يمكن أن يكون سالبًا"
        )

    # --------------------------------------------------------
    # منع استخدام عداد غير مناسب لنوع العتاد
    # --------------------------------------------------------

    if equipment_type.measurement_unit == "km":
        if interval_hours is not None:
            raise ValueError(
                "هذا النوع من العتاد يعتمد على الكيلومترات، "
                "ولا يمكن تحديد فترة بالساعات"
            )

    elif equipment_type.measurement_unit == "hours":
        if interval_km is not None:
            raise ValueError(
                "هذا النوع من العتاد يعتمد على الساعات، "
                "ولا يمكن تحديد فترة بالكيلومترات"
            )

    internal_code = generate_internal_code(
        db,
        maintenance_type_id,
    )

    schedule = MaintenanceSchedule(
        name=name,
        internal_code=internal_code,
        equipment_type_id=equipment_type_id,
        maintenance_type_id=maintenance_type_id,
        interval_km=interval_km,
        interval_hours=interval_hours,
        interval_days=interval_days,
        makes_equipment_unavailable=makes_equipment_unavailable,
        notify_offset_days=notify_offset_days or 0,
        actions_required=(
            actions_required.strip()
            if actions_required
            else None
        ),
        description=(
            description.strip()
            if description
            else None
        ),
    )

    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    return schedule


def list_schedules_for_equipment_type(
    db: Session,
    equipment_type_id: int,
) -> list[MaintenanceSchedule]:

    return (
        db.query(MaintenanceSchedule)
        .filter(
            MaintenanceSchedule.equipment_type_id
            == equipment_type_id,
            MaintenanceSchedule.is_active.is_(True),
        )
        .order_by(MaintenanceSchedule.name)
        .all()
    )


def get_schedule(
    db: Session,
    schedule_id: int,
) -> Optional[MaintenanceSchedule]:

    return (
        db.query(MaintenanceSchedule)
        .filter(MaintenanceSchedule.id == schedule_id)
        .first()
    )


# ============================================================
# Meter readings
# ============================================================

def get_last_meter_reading(
    db: Session,
    equipment_id: int,
) -> Optional[MeterReading]:

    return (
        db.query(MeterReading)
        .filter(
            MeterReading.equipment_id == equipment_id
        )
        .order_by(
            MeterReading.reading_date.desc(),
            MeterReading.id.desc(),
        )
        .first()
    )


def record_meter_reading(
    db: Session,
    equipment_id: int,
    reading_date: date,
    odometer_value: Optional[Decimal] = None,
    hours_value: Optional[Decimal] = None,
    source: str = "manual",
) -> MeterReading:

    equipment = equipment_services.get_equipment(
        db,
        equipment_id,
    )

    if not equipment:
        raise ValueError("العتاد غير موجود")

    if odometer_value is not None and odometer_value < 0:
        raise ValueError(
            "قراءة الكيلومترات لا يمكن أن تكون سالبة"
        )

    if hours_value is not None and hours_value < 0:
        raise ValueError(
            "قراءة الساعات لا يمكن أن تكون سالبة"
        )

    if (
        odometer_value is not None
        and hours_value is not None
    ):
        raise ValueError(
            "لا يمكن تسجيل الكيلومترات والساعات معًا في نفس القراءة"
        )

    if odometer_value is None and hours_value is None:
        raise ValueError(
            "يجب إدخال قراءة الكيلومترات أو الساعات"
        )

    # --------------------------------------------------------
    # التأكد من أن العداد يطابق نوع العتاد
    # --------------------------------------------------------

    equipment_type = equipment.equipment_type

    if not equipment_type:
        raise ValueError(
            "نوع العتاد غير مرتبط بهذا العتاد"
        )

    if equipment_type.measurement_unit == "km":

        if hours_value is not None:
            raise ValueError(
                "هذا العتاد يعتمد على الكيلومترات"
            )

        if (
            equipment.current_odometer is not None
            and odometer_value is not None
            and odometer_value < equipment.current_odometer
        ):
            raise ValueError(
                "قراءة الكيلومترات الجديدة أقل من القراءة الحالية للعتاد"
            )

    elif equipment_type.measurement_unit == "hours":

        if odometer_value is not None:
            raise ValueError(
                "هذا العتاد يعتمد على ساعات التشغيل"
            )

        if (
            equipment.current_hours is not None
            and hours_value is not None
            and hours_value < equipment.current_hours
        ):
            raise ValueError(
                "قراءة الساعات الجديدة أقل من القراءة الحالية للعتاد"
            )

    else:
        raise ValueError(
            "وحدة قياس نوع العتاد غير صحيحة"
        )

    reading = MeterReading(
        equipment_id=equipment_id,
        reading_date=reading_date,
        odometer_value=odometer_value,
        hours_value=hours_value,
        source=source,
    )

    db.add(reading)

    equipment_services.update_meters(
        db,
        equipment_id,
        odometer=odometer_value,
        hours=hours_value,
    )

    db.commit()
    db.refresh(reading)

    return reading


# ============================================================
# Last maintenance execution for a schedule
# ============================================================

def get_last_execution(
    db: Session,
    equipment_id: int,
    schedule_id: int,
) -> Optional[MaintenanceRecord]:

    return (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.equipment_id
            == equipment_id,
            MaintenanceRecord.maintenance_schedule_id
            == schedule_id,
            MaintenanceRecord.status == "closed",
        )
        .order_by(
            MaintenanceRecord.resolved_date.desc(),
            MaintenanceRecord.id.desc(),
        )
        .first()
    )


# ============================================================
# Calculate whether a schedule is due
# ============================================================

def is_schedule_due(
    db: Session,
    equipment,
    schedule: MaintenanceSchedule,
    today: Optional[date] = None,
) -> bool:

    if today is None:
        today = date.today()

    equipment_type = equipment.equipment_type

    if not equipment_type:
        return False

    measurement_unit = equipment_type.measurement_unit

    if measurement_unit not in MEASUREMENT_UNITS:
        return False

    last_execution = get_last_execution(
        db,
        equipment.id,
        schedule.id,
    )

    # --------------------------------------------------------
    # نقطة البداية الزمنية
    # --------------------------------------------------------

    if last_execution:
        base_date = (
            last_execution.resolved_date
            or last_execution.reported_date
        )
    else:
        base_date = equipment.acquisition_date

    # --------------------------------------------------------
    # شرط الأيام
    # --------------------------------------------------------

    if (
        schedule.interval_days
        and base_date
    ):
        days_elapsed = (
            today - base_date
        ).days

        if days_elapsed >= schedule.interval_days:
            return True

    # --------------------------------------------------------
    # شرط العداد
    #
    # إذا كانت هناك صيانة مرتبطة بالخطة وتم تسجيل العداد
    # عند تنفيذها، فإن هذه القراءة هي نقطة البداية الجديدة.
    # --------------------------------------------------------

    if measurement_unit == "km":

        if not schedule.interval_km:
            return False

        current_value = equipment.current_odometer

        if current_value is None:
            return False

        if last_execution and last_execution.meter_reading is not None:
            base_value = last_execution.meter_reading
        else:
            base_value = Decimal("0")

        difference = (
            current_value - base_value
        )

        return difference >= schedule.interval_km

    if measurement_unit == "hours":

        if not schedule.interval_hours:
            return False

        current_value = equipment.current_hours

        if current_value is None:
            return False

        if last_execution and last_execution.meter_reading is not None:
            base_value = last_execution.meter_reading
        else:
            base_value = Decimal("0")

        difference = (
            current_value - base_value
        )

        return difference >= schedule.interval_hours

    return False


# ============================================================
# Due schedules for equipment
# ============================================================

def get_due_schedules_for_equipment(
    db: Session,
    equipment_id: int,
) -> list[MaintenanceSchedule]:

    equipment = equipment_services.get_equipment(
        db,
        equipment_id,
    )

    if not equipment:
        return []

    schedules = list_schedules_for_equipment_type(
        db,
        equipment.equipment_type_id,
    )

    return [
        schedule
        for schedule in schedules
        if is_schedule_due(
            db,
            equipment,
            schedule,
        )
    ]


# ============================================================
# Create maintenance record
# ============================================================

def create_maintenance_record(
    db: Session,
    equipment_id: int,
    reported_date: date,
    maintenance_schedule_id: Optional[int] = None,
    maintenance_type_id: Optional[int] = None,
    description: Optional[str] = None,
) -> MaintenanceRecord:

    equipment = equipment_services.get_equipment(
        db,
        equipment_id,
    )

    if not equipment:
        raise ValueError("العتاد غير موجود")

    is_scheduled = maintenance_schedule_id is not None

    schedule = None
    makes_unavailable = False

    # --------------------------------------------------------
    # إذا كانت العملية مرتبطة بخطة دورية
    # --------------------------------------------------------

    if maintenance_schedule_id is not None:

        schedule = get_schedule(
            db,
            maintenance_schedule_id,
        )

        if not schedule:
            raise ValueError(
                "عملية الصيانة الدورية غير موجودة"
            )

        if not schedule.is_active:
            raise ValueError(
                "عملية الصيانة الدورية غير مفعلة"
            )

        if (
            schedule.equipment_type_id
            != equipment.equipment_type_id
        ):
            raise ValueError(
                "عملية الصيانة لا تخص نوع هذا العتاد"
            )

        # العملية المختارة هي التي تحدد نوع الصيانة
        maintenance_type_id = (
            schedule.maintenance_type_id
        )

        makes_unavailable = (
            schedule.makes_equipment_unavailable
        )

    # --------------------------------------------------------
    # إنشاء السجل
    # --------------------------------------------------------

    record = MaintenanceRecord(
        equipment_id=equipment_id,
        maintenance_schedule_id=maintenance_schedule_id,
        maintenance_type_id=maintenance_type_id,
        is_scheduled=is_scheduled,
        reported_date=reported_date,
        status="open",
        description=(
            description.strip()
            if description
            else None
        ),
    )

    db.add(record)

    # الصيانة الدورية التي تتطلب توقف العتاد
    if (
        is_scheduled
        and makes_unavailable
    ):
        equipment_services.update_operational_status(
            db,
            equipment_id,
            "in_maintenance",
        )

    db.commit()
    db.refresh(record)

    return record


# ============================================================
# Complete maintenance
# ============================================================

def complete_maintenance_record(
    db: Session,
    record_id: int,
    resolved_date: date,
    meter_reading: Optional[Decimal] = None,
    resolution_notes: Optional[str] = None,
    performed_by: Optional[str] = None,
    location: Optional[str] = None,
) -> Optional[MaintenanceRecord]:

    record = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.id == record_id
        )
        .first()
    )

    if not record:
        return None

    if record.status == "closed":
        raise ValueError(
            "سجل الصيانة مغلق مسبقًا"
        )

    if resolved_date < record.reported_date:
        raise ValueError(
            "تاريخ إتمام الصيانة لا يمكن أن يكون قبل تاريخ تسجيلها"
        )

    equipment = equipment_services.get_equipment(
        db,
        record.equipment_id,
    )

    if not equipment:
        raise ValueError(
            "العتاد المرتبط بسجل الصيانة غير موجود"
        )

    # --------------------------------------------------------
    # التحقق من قراءة العداد
    # --------------------------------------------------------

    if meter_reading is not None:

        if meter_reading < 0:
            raise ValueError(
                "قراءة العداد لا يمكن أن تكون سالبة"
            )

        equipment_type = equipment.equipment_type

        if not equipment_type:
            raise ValueError(
                "نوع العتاد غير مرتبط بالعتاد"
            )

        if equipment_type.measurement_unit == "km":

            if (
                equipment.current_odometer is not None
                and meter_reading
                < equipment.current_odometer
            ):
                raise ValueError(
                    "قراءة الكيلومترات عند الصيانة أقل من القراءة الحالية"
                )

        elif equipment_type.measurement_unit == "hours":

            if (
                equipment.current_hours is not None
                and meter_reading
                < equipment.current_hours
            ):
                raise ValueError(
                    "قراءة الساعات عند الصيانة أقل من القراءة الحالية"
                )

        else:
            raise ValueError(
                "وحدة قياس نوع العتاد غير صحيحة"
            )

    # --------------------------------------------------------
    # تحديث السجل
    # --------------------------------------------------------

    record.status = "closed"
    record.resolved_date = resolved_date
    record.meter_reading = meter_reading

    record.resolution_notes = (
        resolution_notes.strip()
        if resolution_notes
        else None
    )

    record.performed_by = (
        performed_by.strip()
        if performed_by
        else None
    )

    record.location = (
        location.strip()
        if location
        else None
    )

    # --------------------------------------------------------
    # تحديث عداد العتاد
    # --------------------------------------------------------

    if meter_reading is not None:

        equipment_type = equipment.equipment_type

        if equipment_type.measurement_unit == "hours":

            record_meter_reading(
                db,
                record.equipment_id,
                resolved_date,
                hours_value=meter_reading,
                source="maintenance_record",
            )

        else:

            record_meter_reading(
                db,
                record.equipment_id,
                resolved_date,
                odometer_value=meter_reading,
                source="maintenance_record",
            )

    # --------------------------------------------------------
    # إعادة العتاد إلى الحالة المتاحة للصيانة الدورية
    # --------------------------------------------------------

    if record.is_scheduled:
        equipment_services.update_operational_status(
            db,
            record.equipment_id,
            "available",
        )

    db.commit()
    db.refresh(record)

    return record


# ============================================================
# Open maintenance records
# ============================================================

def list_open_records(
    db: Session,
) -> list[MaintenanceRecord]:

    return (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.status == "open"
        )
        .order_by(
            MaintenanceRecord.reported_date.desc()
        )
        .all()
    )


# ============================================================
# Equipment maintenance history
# ============================================================

def list_equipment_history(
    db: Session,
    equipment_id: int,
) -> list[MaintenanceRecord]:

    return (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.equipment_id
            == equipment_id
        )
        .order_by(
            MaintenanceRecord.reported_date.desc(),
            MaintenanceRecord.id.desc(),
        )
        .all()
    )


# ============================================================
# Maintenance notifications
# ============================================================

def get_maintenance_notifications(
    db: Session,
) -> list[dict]:

    from app.modules.equipment.models import Equipment

    notifications = []

    all_equipment = (
        db.query(Equipment)
        .all()
    )

    today = date.today()

    for equipment in all_equipment:

        schedules = list_schedules_for_equipment_type(
            db,
            equipment.equipment_type_id,
        )

        for schedule in schedules:

            key = (
                f"maintenance:"
                f"{equipment.id}:"
                f"{schedule.id}"
            )

            last_execution = get_last_execution(
                db,
                equipment.id,
                schedule.id,
            )

            # ------------------------------------------------
            # هل توجد صيانة مفتوحة لنفس الخطة؟
            # ------------------------------------------------

            open_record = (
                db.query(MaintenanceRecord)
                .filter(
                    MaintenanceRecord.equipment_id
                    == equipment.id,
                    MaintenanceRecord.maintenance_schedule_id
                    == schedule.id,
                    MaintenanceRecord.status == "open",
                )
                .first()
            )

            # إذا كانت العملية قيد التنفيذ فلا نكرر
            # إشعار الاستحقاق
            if open_record:
                continue

            # ------------------------------------------------
            # الاستحقاق
            # ------------------------------------------------

            if is_schedule_due(
                db,
                equipment,
                schedule,
                today=today,
            ):

                notifications.append(
                    {
                        "key": key,
                        "source": "maintenance",
                        "severity": "overdue",
                        "title": (
                            f"{equipment.asset_code} — "
                            f"{schedule.name} "
                            f"(مستحقة)"
                        ),
                        "url": (
                            f"/maintenance/"
                            f"{equipment.id}/due"
                        ),
                    }
                )

                continue

            # ------------------------------------------------
            # تنبيه الاستحقاق القادم حسب الأيام
            # ------------------------------------------------

            if (
                schedule.interval_days
                and schedule.notify_offset_days
            ):

                if last_execution:

                    base_date = (
                        last_execution.resolved_date
                        or last
