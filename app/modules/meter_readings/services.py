from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.modules.equipment.models import Equipment
from app.modules.equipment_types.models import EquipmentType
from app.modules.meter_readings.models import MeterReading


def _unit(equipment: Equipment) -> str:
    return equipment.equipment_type.measurement_unit if equipment.equipment_type else "hours"


def _value(reading: MeterReading | None, unit: str):
    if reading is None:
        return None
    return reading.odometer if unit == "km" else reading.hours


def _fmt(value) -> str:
    if value is None:
        return "—"
    value = Decimal(value)
    if value == value.to_integral_value():
        return f"{int(value):,}"
    return f"{value:,.1f}"


def _fmt_difference(value) -> str:
    if value is None:
        return "—"
    value = Decimal(value)
    if value == value.to_integral_value():
        return f"{int(value):+,}"
    return f"{value:+,.1f}"


def _difference(current: MeterReading, previous: MeterReading | None, unit: str):
    current_value = _value(current, unit)
    previous_value = _value(previous, unit)
    if current_value is None or previous_value is None:
        return None
    return Decimal(current_value) - Decimal(previous_value)


def _status(difference):
    if difference is None:
        return "مرجعية", "reference"
    difference = Decimal(difference)
    if difference < 0:
        return "قراءة غير طبيعية", "danger"
    if difference == 0:
        return "تحتاج مراجعة", "warning"
    return "طبيعي", "success"


def list_readings(db: Session, equipment_id: int) -> list[MeterReading]:
    return (
        db.query(MeterReading)
        .filter(MeterReading.equipment_id == equipment_id)
        .order_by(MeterReading.reading_date.asc(), MeterReading.id.asc())
        .all()
    )


def list_latest_rows(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: str = "",
    type_id: Optional[int] = None,
    unit: str = "",
    sort: str = "date_desc",
):
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    latest_dates = (
        db.query(
            MeterReading.equipment_id.label("equipment_id"),
            func.max(MeterReading.reading_date).label("latest_date"),
        )
        .group_by(MeterReading.equipment_id)
        .subquery()
    )

    query = (
        db.query(Equipment, latest_dates.c.latest_date)
        .join(EquipmentType, Equipment.equipment_type_id == EquipmentType.id)
        .outerjoin(latest_dates, latest_dates.c.equipment_id == Equipment.id)
        .options(joinedload(Equipment.equipment_type), joinedload(Equipment.equipment_model))
    )

    if type_id:
        query = query.filter(Equipment.equipment_type_id == type_id)
    if unit in {"km", "hours"}:
        query = query.filter(EquipmentType.measurement_unit == unit)
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Equipment.asset_code.ilike(term),
                Equipment.registration_number.ilike(term),
                Equipment.vin.ilike(term),
                EquipmentType.name.ilike(term),
            )
        )

    total = query.count()

    if sort == "registration":
        query = query.order_by(Equipment.registration_number.asc(), Equipment.id.asc())
    elif sort == "type":
        query = query.order_by(EquipmentType.name.asc(), Equipment.id.asc())
    elif sort == "date_asc":
        query = query.order_by(latest_dates.c.latest_date.asc(), Equipment.id.asc())
    else:
        query = query.order_by(latest_dates.c.latest_date.desc(), Equipment.id.asc())

    selected = query.offset((page - 1) * page_size).limit(page_size).all()
    equipment_ids = [equipment.id for equipment, _ in selected]

    history = {equipment_id: [] for equipment_id in equipment_ids}
    if equipment_ids:
        readings = (
            db.query(MeterReading)
            .filter(MeterReading.equipment_id.in_(equipment_ids))
            .order_by(
                MeterReading.equipment_id.asc(),
                MeterReading.reading_date.desc(),
                MeterReading.id.desc(),
            )
            .all()
        )
        for reading in readings:
            bucket = history[reading.equipment_id]
            if len(bucket) < 2:
                bucket.append(reading)

    rows = []
    for number, (equipment, _) in enumerate(
        selected, start=(page - 1) * page_size + 1
    ):
        unit_code = _unit(equipment)
        latest = history[equipment.id][0] if history[equipment.id] else None
        previous = history[equipment.id][1] if len(history[equipment.id]) > 1 else None
        difference = _difference(latest, previous, unit_code) if latest else None
        status, status_class = _status(difference) if latest else ("لا توجد قراءة", "empty")

        rows.append(
            {
                "number": number,
                "equipment_id": equipment.id,
                "type": equipment.equipment_type.name if equipment.equipment_type else "—",
                "model": equipment.equipment_model.name if equipment.equipment_model else "—",
                "registration": equipment.registration_number or equipment.asset_code or "—",
                "location": "—",
                "unit": "كم" if unit_code == "km" else "ساعة عمل",
                "unit_code": unit_code,
                "date": latest.reading_date.strftime("%d/%m/%Y") if latest else "—",
                "reading": _fmt(_value(latest, unit_code)),
                "difference": _fmt_difference(difference),
                "note": latest.notes if latest and latest.notes else "—",
                "status": status,
                "status_class": status_class,
            }
        )

    last_update = db.query(func.max(MeterReading.reading_date)).scalar()
    last_update_text = last_update.strftime("%d/%m/%Y") if last_update else "—"
    pages = (total + page_size - 1) // page_size if total else 1

    return rows, total, pages, last_update_text


def get_equipment_with_readings(db: Session, equipment_id: int):
    return (
        db.query(Equipment)
        .options(joinedload(Equipment.equipment_type), joinedload(Equipment.equipment_model))
        .filter(Equipment.id == equipment_id)
        .first()
    )


def history_rows(db: Session, equipment_id: int):
    equipment = get_equipment_with_readings(db, equipment_id)
    if not equipment:
        return None, []

    unit_code = _unit(equipment)
    readings = list_readings(db, equipment_id)
    rows = []
    previous = None

    for number, reading in enumerate(readings, start=1):
        difference = _difference(reading, previous, unit_code)
        status, status_class = _status(difference)
        rows.append(
            {
                "number": number,
                "id": reading.id,
                "date": reading.reading_date.strftime("%d/%m/%Y"),
                "odometer": _fmt(reading.odometer),
                "hours": _fmt(reading.hours),
                "reading": _fmt(_value(reading, unit_code)),
                "difference": _fmt_difference(difference),
                "note": reading.notes or "—",
                "status": status,
                "status_class": status_class,
                "unit": "كم" if unit_code == "km" else "ساعة عمل",
                "unit_code": unit_code,
            }
        )
        previous = reading

    return equipment, rows


def create_reading(
    db: Session,
    equipment_id: int,
    odometer=None,
    hours=None,
    reading_date: datetime | None = None,
    notes: str | None = None,
) -> MeterReading:
    equipment = get_equipment_with_readings(db, equipment_id)
    if not equipment:
        raise ValueError("العتاد غير موجود")

    unit_code = _unit(equipment)
    value = odometer if unit_code == "km" else hours
    if value is None:
        raise ValueError("يجب إدخال قراءة العداد الخاصة بوحدة العتاد")
    if Decimal(value) < 0:
        raise ValueError("قيمة العداد لا يمكن أن تكون سالبة")

    reading = MeterReading(
        equipment_id=equipment_id,
        odometer=odometer,
        hours=hours,
        reading_date=reading_date or datetime.utcnow(),
        notes=notes,
        source="manual",
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading
