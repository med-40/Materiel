from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

services_path = ROOT / "app/modules/meter_readings/services.py"
text = services_path.read_text(encoding="utf-8")

old = '''def create_reading(db: Session, equipment_id: int, odometer=None, hours=None, reading_date: datetime | None = None, notes: str | None = None, equipment_status: str = "available") -> MeterReading:\n    equipment = get_equipment_with_readings(db, equipment_id)\n'''
new = '''def _ensure_not_duplicate_reading(db: Session, equipment_id: int, reading_date: datetime, value: Decimal, unit: str, exclude_id: int | None = None):\n    for existing in list_readings(db, equipment_id):\n        if exclude_id is not None and existing.id == exclude_id:\n            continue\n        existing_value = _value(existing, unit)\n        if existing_value is None:\n            continue\n        if existing.reading_date.date() == reading_date.date() and Decimal(existing_value) == value:\n            raise ValueError(\n                f"لا يمكن إضافة نفس قراءة العداد مرتين للعتاد في تاريخ {reading_date:%d/%m/%Y}: "\n                f"القيمة ({value:g}) موجودة مسبقًا. لم يتم حفظ قراءة مكررة."\n            )\n\ndef create_reading(db: Session, equipment_id: int, odometer=None, hours=None, reading_date: datetime | None = None, notes: str | None = None, equipment_status: str = "available") -> MeterReading:\n    equipment = get_equipment_with_readings(db, equipment_id)\n'''
if old not in text:
    raise SystemExit("services create_reading anchor not found")
text = text.replace(old, new, 1)
old = '    if date_value.date() > datetime.now(timezone.utc).date(): raise ValueError("لا يمكن إدخال قراءة بتاريخ مستقبلي. اختر تاريخ اليوم أو تاريخًا سابقًا.")\n    _validate_reading_position(db, equipment_id, date_value, value, unit_code); equipment.operational_status = normalize_equipment_status(equipment_status)\n'
new = '    if date_value.date() > datetime.now(timezone.utc).date(): raise ValueError("لا يمكن إدخال قراءة بتاريخ مستقبلي. اختر تاريخ اليوم أو تاريخًا سابقًا.")\n    _ensure_not_duplicate_reading(db, equipment_id, date_value, value, unit_code)\n    _validate_reading_position(db, equipment_id, date_value, value, unit_code); equipment.operational_status = normalize_equipment_status(equipment_status)\n'
if old not in text:
    raise SystemExit("services manual validation anchor not found")
text = text.replace(old, new, 1)
old = '''            if not item["blank_value"]:\n                comparisons = existing + [MeterReading(equipment_id=equipment_id, reading_date=x["reading_date"], odometer=x["value"] if unit_code == "km" else None, hours=x["value"] if unit_code == "hours" else None) for x in accepted_for_equipment]\n                for other in comparisons:\n'''
new = '''            comparisons = existing + [MeterReading(equipment_id=equipment_id, reading_date=x["reading_date"], odometer=x["value"] if unit_code == "km" else None, hours=x["value"] if unit_code == "hours" else None) for x in accepted_for_equipment]\n            for other in comparisons:\n                other_value = _value(other, unit_code)\n                if other_value is None:\n                    continue\n                if other.reading_date.date() == item["reading_date"].date() and Decimal(other_value) == value:\n                    invalid_reason = (\n                        f"الصف {item['_row_number']}: القراءة ({value:g}) مكررة للعتاد بتاريخ "\n                        f"{item['reading_date']:%d/%m/%Y}، ولم يتم حفظ القراءة المكررة."\n                    )\n                    break\n            if invalid_reason is None and not item["blank_value"]:\n                for other in comparisons:\n'''
if old not in text:
    raise SystemExit("services bulk validation anchor not found")
text = text.replace(old, new, 1)
services_path.write_text(text, encoding="utf-8")

template_path = ROOT / "app/modules/meter_readings/templates/meter_readings.html"
text = template_path.read_text(encoding="utf-8")
old = "if(r.ok&&!d.errors?.length&&d.created)setTimeout(()=>location.reload(),700)"
new_paste = "if(r.ok&&!d.errors?.length&&d.created){closeModal('pasteModal');location.reload()}"
if text.count(old) != 2:
    raise SystemExit(f"expected 2 bulk refresh anchors, found {text.count(old)}")
text = text.replace(old, new_paste, 1)
text = text.replace(old, "if(r.ok&&!d.errors?.length&&d.created){closeModal('importModal');location.reload()}", 1)
old = "if(!r.ok){result.innerHTML='<div class=\"error-card\">⚠️ '+(d.detail||'تعذر الحفظ.')+'</div>';button.disabled=false;return}location.reload()"
new = "if(!r.ok){result.innerHTML='<div class=\"error-card\">⚠️ '+(d.detail||'تعذر الحفظ.')+'</div>';button.disabled=false;return}closeModal('readingModal');location.reload()"
if old not in text:
    raise SystemExit("manual refresh anchor not found")
text = text.replace(old, new, 1)
template_path.write_text(text, encoding="utf-8")

test_path = ROOT / "tests/test_meter_readings.py"
test = test_path.read_text(encoding="utf-8")
marker = "\ndef test_meter_change_history_records_old_and_new_values(db):\n"
addition = '''\ndef test_duplicate_manual_reading_same_date_and_value_is_rejected(db):\n    equipment = seed_equipment(db, "DUP-1", "km")\n    reading_date = datetime(2026, 8, 17)\n    services.create_reading(db, equipment.id, odometer=500, reading_date=reading_date)\n    with pytest.raises(ValueError, match="مكررة|مكرر"):\n        services.create_reading(db, equipment.id, odometer=500, reading_date=reading_date)\n    assert db.query(MeterReading).filter(MeterReading.equipment_id == equipment.id).count() == 1\n\n\ndef test_duplicate_bulk_reading_same_date_and_value_is_rejected(db):\n    equipment = seed_equipment(db, "DUP-2", "km")\n    reading_date = datetime(2026, 8, 17)\n    services.create_reading(db, equipment.id, odometer=700, reading_date=reading_date)\n    created, rejected, errors, warnings, reading_ids = services.create_bulk_readings(\n        db, [bulk_row(equipment, reading_date, 700, row_number=2)]\n    )\n    assert created == 0\n    assert rejected == 1\n    assert not reading_ids\n    assert any("مكررة" in error for error in errors)\n    assert db.query(MeterReading).filter(MeterReading.equipment_id == equipment.id).count() == 1\n\n'''
if "test_duplicate_manual_reading_same_date_and_value_is_rejected" not in test:
    if marker not in test:
        raise SystemExit("test insertion marker not found")
    test = test.replace(marker, addition + marker, 1)
test_path.write_text(test, encoding="utf-8")

print("Meter duplicate/date and successful-modal-refresh patch applied")
