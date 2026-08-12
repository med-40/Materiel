from typing import Optional

from sqlalchemy.orm import Session

from app.modules.meter_readings.models import MeterReading


def list_readings(
    db: Session,
    equipment_id: int,
) -> list[MeterReading]:
    return (
        db.query(MeterReading)
        .filter(MeterReading.equipment_id == equipment_id)
        .order_by(MeterReading.reading_date.desc(), MeterReading.id.desc())
        .all()
    )


def create_reading(
    db: Session,
    equipment_id: int,
    odometer=None,
    hours=None,
) -> MeterReading:
    reading = MeterReading(
        equipment_id=equipment_id,
        odometer=odometer,
        hours=hours,
    )

    db.add(reading)
    db.commit()
    db.refresh(reading)

    return reading
