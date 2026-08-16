from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.modules.equipment.models import Equipment
from app.modules.meter_readings.models import MeterReading


def cleanup_legacy_readings(db: Session) -> int:
    """Remove legacy meter readings that violate permanent date/value rules.

    Readings are evaluated chronologically for each equipment. Once a valid
    reading establishes the running value, a later reading with a smaller
    value is considered legacy-invalid and removed. Future and negative
    readings are also removed. New data is still protected by the normal
    service validation; this repair only cleans data that predates those
    protections.
    """
    today = datetime.utcnow().date()
    readings = (
        db.query(MeterReading)
        .options(joinedload(MeterReading.equipment).joinedload(Equipment.equipment_type))
        .order_by(MeterReading.equipment_id.asc(), MeterReading.reading_date.asc(), MeterReading.id.asc())
        .all()
    )

    last_value: dict[int, Decimal] = {}
    deleted_ids: list[int] = []
    affected_equipment: set[int] = set()

    for reading in readings:
        value = reading.odometer if reading.odometer is not None else reading.hours
        invalid = reading.reading_date.date() > today
        if value is not None and Decimal(value) < 0:
            invalid = True

        if not invalid and value is not None:
            current = Decimal(value)
            previous = last_value.get(reading.equipment_id)
            if previous is not None and current < previous:
                invalid = True
            else:
                last_value[reading.equipment_id] = current

        if invalid:
            deleted_ids.append(reading.id)
            affected_equipment.add(reading.equipment_id)
            db.delete(reading)

    if not deleted_ids:
        return 0

    db.flush()
    for equipment_id in affected_equipment:
        equipment = db.query(Equipment).options(joinedload(Equipment.equipment_type)).filter(Equipment.id == equipment_id).first()
        if not equipment:
            continue
        unit = equipment.equipment_type.measurement_unit if equipment.equipment_type else "hours"
        latest = (
            db.query(MeterReading)
            .filter(MeterReading.equipment_id == equipment_id)
            .order_by(MeterReading.reading_date.desc(), MeterReading.id.desc())
            .first()
        )
        value = None if latest is None else (latest.odometer if unit == "km" else latest.hours)
        if unit == "km":
            equipment.current_odometer = value
        else:
            equipment.current_hours = value

    db.commit()
    return len(deleted_ids)
