from datetime import date, timedelta
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


def create_maintenance_type(db: Session, name: str, description: Optional[str] = None) -> MaintenanceType:
    name = name.strip()
    if not name:
        raise ValueError("اسم نوع الصيانة مطلوب")

    if db.query(MaintenanceType).filter(MaintenanceType.name == name).first():
        raise ValueError("نوع الصيانة موجود مسبقًا")

    item = MaintenanceType(name=name, description=(description.strip() if description else None))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_maintenance_types(db: Session) -> list[MaintenanceType]:
    return db.query(MaintenanceType).order_by(MaintenanceType.name).all()


def get_maintenance_type(db: Session, type_id: int) -> Optional[MaintenanceType]:
    return db.query(MaintenanceType).filter(MaintenanceType.id == type_id).first()


def generate_internal_code(db: Session, maintenance_type_id: int) -> str:
    prefix = f"MS-{maintenance_type_id}"
    count = (
        db.query(MaintenanceSchedule)
        .filter(MaintenanceSchedule.maintenance_type_id == maintenance_type_id)
        .count()
    )
    next_number = count + 1
    code = f"{prefix}-{next_number:04d}"
    while db.query(MaintenanceSchedule).filter(MaintenanceSchedule.internal_code == code).first():
        next_number += 1
        code = f"{prefix}-{next_number:04d}"
    return code


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

    if interval_km is None and interval_hours is None and interval_days is None:
        raise ValueError("يجب تحديد شرط واحد على الأقل: كم أو ساعات أو أيام")

    if not type_services.get_type(db, equipment_type_id):
        raise ValueError("نوع العتاد غير موجود")

    if not get_maintenance_type(db, maintenance_type_id):
        raise ValueError("نوع الصيانة غير موجود")

    internal_code = generate_internal_code(db, maintenance_type_id)

    schedule = MaintenanceSchedule(
        name=name,
        internal_code=internal_code,
        equipment_type_id=equipment_type_id,
        maintenance_type_id=maintenance_type_id,
        interval_km=interval_km,
        interval_hours=interval_hours,
        interval_days=interval_days,
        makes_equipment_unavailable=makes_equipment_unavailable,
        notify_offset_days=notify_offset_days,
        actions_required=(actions_required.strip() if actions_required else None),
        description=(description.strip() if description else None),
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def list_schedules_for_equipment_type(db: Session, equipment_type_id: int) -> list[MaintenanceSchedule]:
    return (
        db.query(MaintenanceSchedule)
        .filter(
            MaintenanceSchedule.equipment_type_id == equipment_type_id,
            MaintenanceSchedule.is_active.is_(True),
        )
        .all()
    )


def get_schedule(db: Session, schedule_id: int) -> Optional[MaintenanceSchedule]:
    return db.query(MaintenanceSchedule).filter(MaintenanceSchedule.id == schedule_id).first()


def get_last_meter_reading(db: Session, equipment_id: int) -> Optional[MeterReading]:
    return (
        db.query(MeterReading)
        .filter(MeterReading.equipment_id == equipment_id)
        .order_by(MeterReading.reading_date.desc(), MeterReading.id.desc())
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
    reading = MeterReading(
        equipment_id=equipment_id,
        reading_date=reading_date,
        odometer_value=odometer_value,
        hours_value=hours_value,
        source=source,
    )
    db.add(reading)

    equipment_services.update_meters(db, equipment_id, odometer=odometer_value, hours=hours_value)

    db.commit()
    db.refresh(reading)
    return reading


def get_last_execution(db: Session, equipment_id: int, schedule_id: int) -> Optional[MaintenanceRecord]:
    return (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.equipment_id == equipment_id,
            MaintenanceRecord.maintenance_schedule_id == schedule_id,
            MaintenanceRecord.status == "closed",
        )
        .order_by(MaintenanceRecord.resolved_date.desc())
        .first()
    )


def is_schedule_due(
    db: Session,
    equipment,
    schedule: MaintenanceSchedule,
    today: Optional[date] = None,
) -> bool:
    if today is None:
        today = date.today()

    last_execution = get_last_execution(db, equipment.id, schedule.id)
    base_date = last_execution.resolved_date if last_execution else equipment.acquisition_date
    base_meter = last_execution.meter_reading if last_execution else Decimal(0)

    if schedule.interval_days and base_date:
        if (today - base_date).days >= schedule.interval_days:
            return True

    if schedule.interval_km and equipment.current_odometer is not None:
        if (equipment.current_odometer - (base_meter or Decimal(0))) >= schedule.interval_km:
            return True

    if schedule.interval_hours and equipment.current_hours is not None:
        if (equipment.current_hours - (base_meter or Decimal(0))) >= schedule.interval_hours:
            return True

    return False


def get_due_schedules_for_equipment(db: Session, equipment_id: int) -> list[MaintenanceSchedule]:
    equipment = equipment_services.get_equipment(db, equipment_id)
    if not equipment:
        return []

    candidates = list_schedules_for_equipment_type(db, equipment.equipment_type_id)
    return [s for s in candidates if is_schedule_due(db, equipment, s)]


def create_maintenance_record(
    db: Session,
    equipment_id: int,
    reported_date: date,
    maintenance_schedule_id: Optional[int] = None,
    maintenance_type_id: Optional[int] = None,
    description: Optional[str] = None,
) -> MaintenanceRecord:
    equipment = equipment_services.get_equipment(db, equipment_id)
    if not equipment:
        raise ValueError("العتاد غير موجود")

    is_scheduled = maintenance_schedule_id is not None
    schedule = None
    makes_unavailable = False

    if is_scheduled:
        schedule = get_schedule(db, maintenance_schedule_id)
        if not schedule:
            raise ValueError("خطة الصيانة غير موجودة")
        if schedule.equipment_type_id != equipment.equipment_type_id:
            raise ValueError("خطة الصيانة لا تخص نوع هذا العتاد")
        maintenance_type_id = schedule.maintenance_type_id
        makes_unavailable = schedule.makes_equipment_unavailable

    record = MaintenanceRecord(
        equipment_id=equipment_id,
        maintenance_schedule_id=maintenance_schedule_id,
        maintenance_type_id=maintenance_type_id,
        is_scheduled=is_scheduled,
        reported_date=reported_date,
        status="open",
        description=(description.strip() if description else None),
    )
    db.add(record)

    if is_scheduled and makes_unavailable:
        equipment_services.update_operational_status(db, equipment_id, "in_maintenance")
    elif not is_scheduled:
        equipment_services.update_technical_condition(db, equipment_id, "broken")

    db.commit()
    db.refresh(record)
    return record


def complete_maintenance_record(
    db: Session,
    record_id: int,
    resolved_date: date,
    meter_reading: Optional[Decimal] = None,
    resolution_notes: Optional[str] = None,
    performed_by: Optional[str] = None,
    location: Optional[str] = None,
) -> Optional[MaintenanceRecord]:
    record = db.query(MaintenanceRecord).filter(MaintenanceRecord.id == record_id).first()
    if not record:
        return None

    record.status = "closed"
    record.resolved_date = resolved_date
    record.meter_reading = meter_reading
    record.resolution_notes = (resolution_notes.strip() if resolution_notes else None)
    record.performed_by = performed_by
    record.location = location

    if meter_reading is not None:
        equipment = equipment_services.get_equipment(db, record.equipment_id)
        if equipment and equipment.equipment_type and equipment.equipment_type.measurement_unit == "hours":
            record_meter_reading(db, record.equipment_id, resolved_date, hours_value=meter_reading, source="maintenance_record")
        else:
            record_meter_reading(db, record.equipment_id, resolved_date, odometer_value=meter_reading, source="maintenance_record")

    if record.is_scheduled:
        equipment_services.update_operational_status(db, record.equipment_id, "available")
    else:
        equipment_services.update_technical_condition(db, record.equipment_id, "ready")

    db.commit()
    db.refresh(record)
    return record


def list_open_records(db: Session) -> list[MaintenanceRecord]:
    return db.query(MaintenanceRecord).filter(MaintenanceRecord.status == "open").all()


def list_equipment_history(db: Session, equipment_id: int) -> list[MaintenanceRecord]:
    return (
        db.query(MaintenanceRecord)
        .filter(MaintenanceRecord.equipment_id == equipment_id)
        .order_by(MaintenanceRecord.reported_date.desc())
        .all()
    )


def get_maintenance_notifications(db: Session) -> list[dict]:
    """
    مزوّد إشعارات وحدة الصيانة — يُسجَّل عند وحدة notifications المركزية.
    يرجع الشكل الموحّد: key, source, severity, title, url.
    """
    from app.modules.equipment.models import Equipment

    notifications = []
    all_equipment = db.query(Equipment).all()

    for equipment in all_equipment:
        schedules = list_schedules_for_equipment_type(db, equipment.equipment_type_id)
        for schedule in schedules:
            key = f"maintenance:{equipment.id}:{schedule.id}"

            if is_schedule_due(db, equipment, schedule):
                notifications.append({
                    "key": key,
                    "source": "maintenance",
                    "severity": "overdue",
                    "title": f"{equipment.asset_code} — {schedule.name} (متأخرة)",
                    "url": f"/maintenance/{equipment.id}/due",
                })
            elif schedule.interval_days and schedule.notify_offset_days:
                last_execution = get_last_execution(db, equipment.id, schedule.id)
                base_date = last_execution.resolved_date if last_execution else equipment.acquisition_date
                if base_date:
                    days_since = (date.today() - base_date).days
                    days_remaining = schedule.interval_days - days_since
                    if 0 < days_remaining <= schedule.notify_offset_days:
                        notifications.append({
                            "key": key,
                            "source": "maintenance",
                            "severity": "upcoming",
                            "title": f"{equipment.asset_code} — {schedule.name} (بعد {days_remaining} يوم)",
                            "url": f"/maintenance/{equipment.id}/due",
                        })

    return notifications


def get_maintenance_notifications(db: Session) -> list[dict]:
    """
    مزوّد إشعارات وحدة الصيانة — يُسجَّل عند وحدة notifications المركزية.
    يرجع الشكل الموحّد: key, source, severity, title, url.
    """
    from app.modules.equipment.models import Equipment

    notifications = []
    all_equipment = db.query(Equipment).all()

    for equipment in all_equipment:
        schedules = list_schedules_for_equipment_type(db, equipment.equipment_type_id)
        for schedule in schedules:
            key = f"maintenance:{equipment.id}:{schedule.id}"

            if is_schedule_due(db, equipment, schedule):
                notifications.append({
                    "key": key,
                    "source": "maintenance",
                    "severity": "overdue",
                    "title": f"{equipment.asset_code} — {schedule.name} (متأخرة)",
                    "url": f"/maintenance/{equipment.id}/due",
                })
            elif schedule.interval_days and schedule.notify_offset_days:
                last_execution = get_last_execution(db, equipment.id, schedule.id)
                base_date = last_execution.resolved_date if last_execution else equipment.acquisition_date
                if base_date:
                    days_since = (date.today() - base_date).days
                    days_remaining = schedule.interval_days - days_since
                    if 0 < days_remaining <= schedule.notify_offset_days:
                        notifications.append({
                            "key": key,
                            "source": "maintenance",
                            "severity": "upcoming",
                            "title": f"{equipment.asset_code} — {schedule.name} (بعد {days_remaining} يوم)",
                            "url": f"/maintenance/{equipment.id}/due",
                        })

    return notifications
