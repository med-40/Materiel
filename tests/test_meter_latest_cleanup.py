from datetime import datetime

from app.modules.meter_readings import services
from app.modules.meter_readings.legacy_cleanup import cleanup_legacy_readings
from app.modules.meter_readings.models import MeterReading

from test_meter_readings import seed_equipment


def test_legacy_lower_latest_reading_is_removed_and_main_uses_valid_latest(db):
    equipment = seed_equipment(db, "356", "km")
    old_valid = MeterReading(
        equipment_id=equipment.id,
        reading_date=datetime(2023, 8, 16),
        odometer=3333333,
        source="manual",
    )
    legacy_invalid = MeterReading(
        equipment_id=equipment.id,
        reading_date=datetime(2026, 8, 11),
        odometer=500,
        source="manual",
    )
    db.add_all([old_valid, legacy_invalid])
    db.commit()

    removed = cleanup_legacy_readings(db)
    assert removed == 1
    assert db.query(MeterReading).filter(MeterReading.id == legacy_invalid.id).count() == 0

    rows, total, pages, _ = services.list_latest_rows(db, page=1, page_size=20)
    assert total == 1
    assert pages == 1
    assert rows[0]["equipment_id"] == equipment.id
    assert rows[0]["date"] == "16/08/2023"
    assert rows[0]["reading"] == "3,333,333"
    assert rows[0]["difference"] == "—"
    assert equipment.current_odometer == 3333333
