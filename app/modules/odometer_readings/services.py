from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session

from .models import OdometerReading


def list_readings(db: Session, equipment_id: int | None = None):
    query = db.query(OdometerReading)

    if equipment_id is not None:
        query = query.filter(
            OdometerReading.equipment_id == equipment_id
        )

    return query.order_by(
        OdometerReading.reading_date.desc(),
        OdometerReading.id.desc(),
    ).all()


def get_reading(db: Session, reading_id: int):
    return db.query(OdometerReading).filter(
        OdometerReading.id == reading_id
    ).first()


def create_reading(
    db: Session,
    equipment_id: int,
    reading_date: datetime,
    odometer: Decimal,
    source: str | None = None,
    notes: str | None = None,
    user_id: int | None = None,
):
    reading = OdometerReading(
        equipment_id=equipment_id,
        reading_date=reading_date,
        odometer=odometer,
        source=source,
        notes=notes,
        created_by_id=user_id,
        updated_by_id=user_id,
    )

    db.add(reading)
    db.commit()
    db.refresh(reading)

    return reading
