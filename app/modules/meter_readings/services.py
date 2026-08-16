from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Iterable

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
    if value < 0:
        return "غير صالح"
    if value == value.to_integral_value():
        return f"+{int(value):,}"
    return f"+{value:,.1f}"


def _difference(current: MeterReading, previous: MeterReading | None, unit: str):
    current_value = _value(current, unit)
    previous_value = _value(previous, unit)
    if current_value is None or previous_value is None:
        return None
    return Decimal(current_value) - Decimal(previous_value)


def _status(difference, has_previous: bool = True):
    if not has_previous:
        return "أولى قراءة", "reference"
    if difference is None:
        return "قراءة غير طبيعية", "danger"
    difference = Decimal(difference)
    if difference < 0:
        return "قراءة غير طبيعية", "danger"
    return "طبيعية", "success"


def normalize_registration(value) -> str:
    if value is None:
        return ""
    text = str(value).strip().upper()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return "".join(ch for ch in text if ch.isalnum())


def list_readings(db: Session, equipment_id: int) -> list[MeterReading]:
    return (
        db.query(MeterReading)
        .filter(MeterReading.equipment_id == equipment_id)
        .order_by(MeterReading.reading_date.asc(), MeterReading.id.asc())
        .all()
    )


def list_latest_rows(db: Session, page: int = 1, page_size: int = 10, search: str = "", type_id: Optional[int] = None, unit: str = "", sort: str = "date_desc"):
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    latest_dates = db.query(MeterReading.equipment_id.label("equipment_id"), func.max(MeterReading.reading_date).label("latest_date")).group_by(MeterReading.equipment_id).subquery()
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
        query = query.filter(or_(Equipment.asset_code.ilike(term), Equipment.registration_number.ilike(term), Equipment.vin.ilike(term), EquipmentType.name.ilike(term)))
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
        readings = db.query(MeterReading).filter(MeterReading.equipment_id.in_(equipment_ids)).order_by(MeterReading.equipment_id.asc(), MeterReading.reading_date.desc(), MeterReading.id.desc()).all()
        for reading in readings:
            bucket = history[reading.equipment_id]
            if len(bucket) < 2:
                bucket.append(reading)
    rows = []
    for number, (equipment, _) in enumerate(selected, start=(page - 1) * page_size + 1):
        unit_code = _unit(equipment)
        latest = history[equipment.id][0] if history[equipment.id] else None
        previous = history[equipment.id][1] if len(history[equipment.id]) > 1 else None
        difference = _difference(latest, previous, unit_code) if latest else None
        status, status_class = _status(difference, previous is not None) if latest else ("لا توجد قراءة", "empty")
        rows.append({"number": number, "equipment_id": equipment.id, "type": equipment.equipment_type.name if equipment.equipment_type else "—", "model": equipment.equipment_model.name if equipment.equipment_model else "—", "registration": equipment.registration_number or equipment.asset_code or "—", "location": "—", "unit": "كم" if unit_code == "km" else "ساعة عمل", "unit_code": unit_code, "date": latest.reading_date.strftime("%d/%m/%Y") if latest else "—", "reading": _fmt(_value(latest, unit_code)), "difference": _fmt_difference(difference), "note": latest.notes if latest and latest.notes else "—", "status": status, "status_class": status_class})
    last_update = db.query(func.max(MeterReading.reading_date)).scalar()
    last_update_text = last_update.strftime("%d/%m/%Y") if last_update else "—"
    pages = (total + page_size - 1) // page_size if total else 1
    return rows, total, pages, last_update_text


def get_equipment_with_readings(db: Session, equipment_id: int):
    return db.query(Equipment).options(joinedload(Equipment.equipment_type), joinedload(Equipment.equipment_model)).filter(Equipment.id == equipment_id).first()


def history_rows(db: Session, equipment_id: int, page: int = 1, page_size: int = 20):
    equipment = get_equipment_with_readings(db, equipment_id)
    if not equipment:
        return None, [], 0, 1, 1
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    unit_code = _unit(equipment)
    ordered = db.query(
        MeterReading.id.label("id"), MeterReading.reading_date.label("reading_date"), MeterReading.odometer.label("odometer"), MeterReading.hours.label("hours"), MeterReading.notes.label("notes"),
        func.lag(MeterReading.odometer).over(partition_by=MeterReading.equipment_id, order_by=(MeterReading.reading_date.asc(), MeterReading.id.asc())).label("previous_odometer"),
        func.lag(MeterReading.hours).over(partition_by=MeterReading.equipment_id, order_by=(MeterReading.reading_date.asc(), MeterReading.id.asc())).label("previous_hours"),
    ).filter(MeterReading.equipment_id == equipment_id).subquery()
    total = db.query(func.count()).select_from(ordered).scalar() or 0
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, pages)
    rows_data = db.query(ordered).order_by(ordered.c.reading_date.asc(), ordered.c.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    rows = []
    for number, row in enumerate(rows_data, start=(page - 1) * page_size + 1):
        current_value = row.odometer if unit_code == "km" else row.hours
        previous_value = row.previous_odometer if unit_code == "km" else row.previous_hours
        has_previous = previous_value is not None
        difference = Decimal(current_value) - Decimal(previous_value) if current_value is not None and has_previous else None
        status, status_class = _status(difference, has_previous)
        rows.append({"number": number, "id": row.id, "date": row.reading_date.strftime("%d/%m/%Y"), "odometer": _fmt(row.odometer), "hours": _fmt(row.hours), "reading": _fmt(current_value), "difference": _fmt_difference(difference), "note": row.notes or "—", "status": status, "status_class": status_class, "unit": "كم" if unit_code == "km" else "ساعة عمل"})
    return equipment, rows, total, pages, page


def create_reading(db: Session, equipment_id: int, odometer=None, hours=None, reading_date: datetime | None = None, notes: str | None = None) -> MeterReading:
    equipment = get_equipment_with_readings(db, equipment_id)
    if not equipment:
        raise ValueError("العتاد غير موجود")
    unit_code = _unit(equipment)
    value = odometer if unit_code == "km" else hours
    if value is None:
        raise ValueError("يجب إدخال قراءة العداد الخاصة بوحدة العتاد")
    try:
        value = Decimal(str(value).replace(",", "").strip())
    except Exception as exc:
        raise ValueError("قيمة العداد غير صحيحة") from exc
    if value < 0:
        raise ValueError("قيمة العداد لا يمكن أن تكون سالبة")
    reading = MeterReading(equipment_id=equipment_id, reading_date=reading_date or datetime.utcnow(), odometer=value if unit_code == "km" else None, hours=value if unit_code == "hours" else None, source="manual", notes=(notes or "").strip()[:300] or None)
    db.add(reading)
    db.flush()
    latest = db.query(MeterReading).filter(MeterReading.equipment_id == equipment_id).order_by(MeterReading.reading_date.desc(), MeterReading.id.desc()).first()
    if unit_code == "km":
        equipment.current_odometer = _value(latest, unit_code)
    else:
        equipment.current_hours = _value(latest, unit_code)
    db.commit()
    db.refresh(reading)
    return reading


def create_bulk_readings(db: Session, rows: Iterable[dict]):
    clean_rows = list(rows)
    if not clean_rows:
        return 0, 0, []
    equipment_list = db.query(Equipment).options(joinedload(Equipment.equipment_type)).filter(Equipment.registration_number.isnot(None)).all()
    equipment_map = {normalize_registration(item.registration_number): item for item in equipment_list if normalize_registration(item.registration_number)}
    created = 0
    errors = []
    affected = {}
    for index, row in enumerate(clean_rows, start=1):
        registration_raw = row.get("registration")
        registration = normalize_registration(registration_raw)
        if not registration:
            errors.append(f"الصف {index}: رقم التسجيل فارغ.")
            continue
        equipment = equipment_map.get(registration)
        if not equipment:
            errors.append(f"الصف {index}: رقم التسجيل {registration_raw} غير موجود.")
            continue
        reading_date = row.get("reading_date")
        if not isinstance(reading_date, datetime):
            errors.append(f"الصف {index}: تاريخ القراءة غير صحيح.")
            continue
        try:
            value = Decimal(str(row.get("value")).replace(",", "").strip())
        except Exception:
            errors.append(f"الصف {index}: قيمة العداد غير صحيحة.")
            continue
        if value < 0:
            errors.append(f"الصف {index}: قيمة العداد لا يمكن أن تكون سالبة.")
            continue
        unit_code = _unit(equipment)
        db.add(MeterReading(equipment_id=equipment.id, reading_date=reading_date, odometer=value if unit_code == "km" else None, hours=value if unit_code == "hours" else None, source="import", notes=(str(row.get("notes") or "").strip()[:300] or None)))
        affected[equipment.id] = equipment
        created += 1
    if created:
        db.flush()
        for equipment in affected.values():
            latest = db.query(MeterReading).filter(MeterReading.equipment_id == equipment.id).order_by(MeterReading.reading_date.desc(), MeterReading.id.desc()).first()
            if _unit(equipment) == "km":
                equipment.current_odometer = _value(latest, "km")
            else:
                equipment.current_hours = _value(latest, "hours")
        db.commit()
    else:
        db.rollback()
    return created, len(clean_rows) - created, errors
