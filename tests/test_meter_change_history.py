from datetime import datetime

from app.modules.meter_readings import services
from app.modules.meter_readings.audit import MeterReadingChange
from app.modules.meter_readings.audit_service import create_operation
from app.modules.users.models import User
from test_meter_readings import db, seed_equipment


def test_meter_change_history_records_old_and_new_values(db):
    equipment = seed_equipment(db, "900", "km")
    first = services.create_reading(db, equipment.id, odometer=100, reading_date=datetime(2026, 8, 10))
    db.commit()
    change_add = db.query(MeterReadingChange).filter(MeterReadingChange.reading_id == first.id, MeterReadingChange.action == "add").one()
    assert change_add.old_value is None
    assert float(change_add.new_value) == 100.0

    first.odometer = 120
    db.commit()
    update = db.query(MeterReadingChange).filter(MeterReadingChange.reading_id == first.id, MeterReadingChange.action == "update").order_by(MeterReadingChange.id.desc()).first()
    assert update is not None
    assert float(update.old_value) == 100.0
    assert float(update.new_value) == 120.0


def test_bulk_operation_attaches_user_and_operation_to_changes(db):
    equipment = seed_equipment(db, "901", "km")
    reading = services.create_reading(db, equipment.id, odometer=200, reading_date=datetime(2026, 8, 10))
    user = User(username="audit-user", full_name="مستخدم الاختبار", hashed_password="x", role="admin")
    db.add(user)
    db.commit()
    op = create_operation(db, "paste", user_id=user.id, total_rows=1, reading_ids=[reading.id], rejected_rows=0)
    db.commit()
    change = db.query(MeterReadingChange).filter(MeterReadingChange.reading_id == reading.id).order_by(MeterReadingChange.id.desc()).first()
    assert change.operation_id == op.id
    assert change.actor_id == user.id
    assert change.source == "paste"
