from datetime import datetime, timedelta
from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import UploadFile

from app.database.base import Base
from app.modules.users.models import User
from app.modules.equipment_types.models import EquipmentType, EquipmentModel
from app.modules.equipment.models import Equipment
from app.modules.meter_readings.models import MeterReading
from app.modules.meter_readings import services
from app.modules.meter_readings.router import meter_readings_import_excel

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(engine)


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


def seed_equipment(db, registration="688", unit="km"):
    et = EquipmentType(name=f"نوع-{registration}", measurement_unit=unit)
    db.add(et)
    db.flush()
    model = EquipmentModel(name=f"طراز-{registration}", equipment_type_id=et.id)
    db.add(model)
    db.flush()
    equipment = Equipment(
        asset_code=f"A-{registration}", registration_number=registration,
        equipment_type_id=et.id, equipment_model_id=model.id,
        operational_status="available",
    )
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    return equipment


def test_manual_reading_and_monotonic_validation(db):
    equipment = seed_equipment(db)
    base = datetime(2026, 8, 10)

    first = services.create_reading(db, equipment.id, odometer=100, reading_date=base, equipment_status="available")
    assert first.odometer == 100

    second = services.create_reading(db, equipment.id, odometer=120, reading_date=base + timedelta(days=1), equipment_status="unavailable")
    assert second.odometer == 120
    assert equipment.operational_status == "unavailable"

    with pytest.raises(ValueError, match="أقل من القراءة المسجلة"):
        services.create_reading(db, equipment.id, odometer=110, reading_date=base + timedelta(days=2))
    assert db.query(MeterReading).filter(MeterReading.equipment_id == equipment.id).count() == 2

    with pytest.raises(ValueError, match="أكبر من القراءة اللاحقة"):
        services.create_reading(db, equipment.id, odometer=130, reading_date=base - timedelta(days=1))
    assert db.query(MeterReading).filter(MeterReading.equipment_id == equipment.id).count() == 2

    with pytest.raises(ValueError, match="تاريخ مستقبلي"):
        services.create_reading(db, equipment.id, odometer=125, reading_date=datetime.utcnow() + timedelta(days=1))
    assert db.query(MeterReading).filter(MeterReading.equipment_id == equipment.id).count() == 2


def test_bulk_import_saves_valid_rows_skips_invalid_rows_and_blank_is_zero(db):
    equipment = seed_equipment(db, "688")
    base = datetime(2026, 8, 10)
    services.create_reading(db, equipment.id, odometer=100, reading_date=base)

    rows = [
        {"registration": "688", "reading_date": base + timedelta(days=1), "km_value": 120, "equipment_status": "available", "_row_number": 2},
        {"registration": "688", "reading_date": base + timedelta(days=2), "km_value": 110, "equipment_status": "available", "_row_number": 3},
        {"registration": "688", "reading_date": base + timedelta(days=3), "km_value": None, "hours_value": None, "equipment_status": "unavailable", "_row_number": 4},
    ]
    created, rejected, errors, warnings, reading_ids = services.create_bulk_readings(db, rows)

    assert created == 2
    assert rejected == 1
    assert len(reading_ids) == 2
    assert any("أقل من القراءة المسجلة" in e for e in errors)
    assert any("تم اعتبار القراءة صفرًا" in w for w in warnings)

    saved = db.query(MeterReading).filter(MeterReading.id.in_(reading_ids)).order_by(MeterReading.reading_date).all()
    assert [float(x.odometer) for x in saved] == [120.0, 0.0]
    assert equipment.operational_status == "unavailable"


def test_excel_arabic_headers_in_reverse_order_and_blank_value_are_accepted(db):
    equipment = seed_equipment(db, "688")

    wb = Workbook()
    ws = wb.active
    ws.append(["الملاحظات", "الساعات", "رقم التسجيل", "التاريخ", "الكيلومترات"])
    ws.append(["قراءة سليمة", None, "688", "15/08/2026", 333])
    ws.append(["قراءة صفرية", None, "688", "16/08/2026", None])
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    upload = UploadFile(filename="قراءات-عربية.xlsx", file=buffer)
    user = User(username="tester", full_name="مختبر", hashed_password="x", role="admin")
    db.add(user)
    db.commit()
    db.refresh(user)

    response = meter_readings_import_excel(upload, "available", db, user)
    assert response.status_code == 200
    payload = response.body.decode("utf-8")
    assert '"created": 2' in payload

    readings = db.query(MeterReading).filter(MeterReading.equipment_id == equipment.id).order_by(MeterReading.reading_date).all()
    assert len(readings) == 2
    assert float(readings[0].odometer) == 333.0
    assert float(readings[1].odometer) == 0.0


def test_operation_rollback_removes_only_its_readings(db):
    equipment = seed_equipment(db, "688")
    base = datetime(2026, 8, 10)
    permanent = services.create_reading(db, equipment.id, odometer=100, reading_date=base)
    created, rejected, errors, warnings, ids = services.create_bulk_readings(
        db,
        [{"registration": "688", "reading_date": base + timedelta(days=1), "km_value": 120, "equipment_status": "available", "_row_number": 2}],
    )
    assert created == 1 and not errors

    from app.modules.meter_readings.audit_service import create_operation, rollback_operation
    op = create_operation(db, "paste", user_id=None, total_rows=1, reading_ids=ids, rejected_rows=0)
    db.commit()
    removed = rollback_operation(db, op, None)
    assert removed == 1
    assert db.query(MeterReading).filter(MeterReading.id == permanent.id).count() == 1
    assert db.query(MeterReading).filter(MeterReading.id.in_(ids)).count() == 0
    assert op.status == "rolled_back"
