from datetime import datetime

from app.modules.meter_readings import services
from app.modules.meter_readings.models import MeterReading
from app.modules.meter_readings.router import meter_reading_delete, meter_reading_update

from test_meter_readings import db, seed_equipment


def test_edit_reading_error_can_be_corrected_and_identifies_equipment(db):
    equipment = seed_equipment(db, "356", "km")
    first = services.create_reading(db, equipment.id, odometer=100, reading_date=datetime(2026, 8, 10))
    second = services.create_reading(db, equipment.id, odometer=120, reading_date=datetime(2026, 8, 11))

    invalid = meter_reading_update(
        equipment_id=equipment.id,
        reading_id=second.id,
        reading_date="2026-08-11",
        value="90",
        notes="",
        db=db,
        current_user=None,
    )
    assert invalid.status_code == 400
    assert "طراز-356" in invalid.body.decode("utf-8")
    assert "356" in invalid.body.decode("utf-8")
    assert float(db.get(MeterReading, second.id).odometer) == 120.0

    corrected = meter_reading_update(
        equipment_id=equipment.id,
        reading_id=second.id,
        reading_date="2026-08-11",
        value="130",
        notes="تم التصحيح",
        db=db,
        current_user=None,
    )
    assert corrected.status_code == 200
    db.refresh(second)
    assert float(second.odometer) == 130.0
    assert second.notes == "تم التصحيح"
    assert float(equipment.current_odometer) == 130.0


def test_delete_reading_refreshes_current_value(db):
    equipment = seed_equipment(db, "688", "km")
    first = services.create_reading(db, equipment.id, odometer=100, reading_date=datetime(2026, 8, 10))
    second = services.create_reading(db, equipment.id, odometer=120, reading_date=datetime(2026, 8, 11))

    response = meter_reading_delete(
        equipment_id=equipment.id,
        reading_id=second.id,
        db=db,
        current_user=None,
    )
    assert response.status_code == 200
    assert db.get(MeterReading, second.id) is None
    db.refresh(equipment)
    assert float(equipment.current_odometer) == 100.0
    assert db.get(MeterReading, first.id) is not None
