from datetime import date, datetime
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.modules.equipment.models import Equipment
from app.modules.equipment_types.models import EquipmentModel, EquipmentType
from app.modules.meter_readings.models import MeterReading
from app.modules.meter_readings.excel_reader import load_meter_workbook
from app.modules.meter_readings import services


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def seed(db):
    equipment_type = EquipmentType(name="سيارة", measurement_unit="km")
    db.add(equipment_type)
    db.flush()
    model = EquipmentModel(name="طراز-اختبار", equipment_type_id=equipment_type.id)
    db.add(model)
    db.flush()
    equipment = Equipment(
        asset_code="A-REG-1",
        registration_number="688",
        equipment_type_id=equipment_type.id,
        equipment_model_id=model.id,
        operational_status="available",
    )
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    return equipment


def test_duplicate_value_same_date_is_rejected_on_update():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = Session()
    try:
        equipment = seed(db)
        first = services.create_reading(db, equipment.id, odometer=999, reading_date=datetime(2026, 8, 13))
        second = services.create_reading(db, equipment.id, odometer=1000, reading_date=datetime(2026, 8, 14))

        second.odometer = 999
        try:
            db.flush()
            raise AssertionError("duplicate update was accepted")
        except ValueError as exc:
            assert "999" in str(exc)
            assert "13/08/2026" in str(exc)
        finally:
            db.rollback()

        assert db.query(MeterReading).count() == 2
        assert db.get(MeterReading, first.id).odometer == 999
    finally:
        db.close()


def test_excel_headers_with_bidi_marks_are_normalized():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "\u200fالطراز",
        "\u200fرقم التسجيل",
        "\u200fالتاريخ",
        "\u200fالكيلومترات",
        "\u200fالساعات",
        "\u200fحالة العداد",
    ])
    sheet.append(["طراز-اختبار", "688", date(2026, 8, 13), 999, None, "يعمل"])
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)

    loaded = load_meter_workbook(stream)
    headers = list(next(loaded.active.iter_rows(min_row=1, max_row=1, values_only=True)))
    assert headers == ["الطراز", "رقم التسجيل", "التاريخ", "الكيلومترات", "الساعات", "حالة العداد"]
