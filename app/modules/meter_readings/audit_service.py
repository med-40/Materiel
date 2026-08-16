from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.modules.equipment.models import Equipment
from app.modules.meter_readings.audit import MeterReadingOperation, MeterReadingOperationEvent, MeterReadingChange
from app.modules.meter_readings.models import MeterReading


def create_operation(db: Session, kind: str, user_id=None, equipment_id=None, filename=None, total_rows=0, reading_ids=None, rejected_rows=0):
    ids = [int(x) for x in (reading_ids or [])]
    op = MeterReadingOperation(kind=kind, created_by_id=user_id, equipment_id=equipment_id, filename=filename, total_rows=total_rows, status='completed' if not rejected_rows else 'completed_with_errors', accepted_rows=len(ids), rejected_rows=rejected_rows, reading_ids=ids)
    db.add(op)
    db.flush()
    if ids:
        db.query(MeterReadingChange).filter(MeterReadingChange.reading_id.in_(ids), MeterReadingChange.operation_id.is_(None)).update({MeterReadingChange.operation_id: op.id, MeterReadingChange.actor_id: user_id, MeterReadingChange.source: kind}, synchronize_session=False)
    add_event(db, op.id, 'created', user_id, 'تم إنشاء عملية الإدخال.')
    add_event(db, op.id, 'completed', user_id, f'تمت العملية: {len(ids)} مقبولة و{rejected_rows} مرفوضة من أصل {total_rows}.', payload={'total_rows': total_rows, 'accepted_rows': len(ids), 'rejected_rows': rejected_rows, 'reading_ids': ids})
    return op


def add_event(db: Session, operation_id, event_type, actor_id, details, payload=None):
    event = MeterReadingOperationEvent(operation_id=operation_id, event_type=event_type, actor_id=actor_id, details=details, payload=payload)
    db.add(event)
    db.flush()
    return event


def add_validation_details(db: Session, operation_id, actor_id, errors=None, warnings=None):
    errors = list(errors or []); warnings = list(warnings or [])
    if errors: add_event(db, operation_id, 'validation_errors', actor_id, f'تم رفض {len(errors)} صف/صفوف بسبب أخطاء في البيانات.', payload={'errors': errors})
    if warnings: add_event(db, operation_id, 'warnings', actor_id, f'تم تسجيل {len(warnings)} تنبيهًا دون منع الإدخال.', payload={'warnings': warnings})


def record_changes_for_readings(db: Session, reading_ids, actor_id, operation_id=None, source='manual'):
    ids = [int(x) for x in (reading_ids or []) if str(x).isdigit()]
    if not ids: return 0
    readings = db.query(MeterReading).filter(MeterReading.id.in_(ids)).all()
    count = 0
    for reading in readings:
        equipment = db.query(Equipment).filter(Equipment.id == reading.equipment_id).first()
        unit = equipment.equipment_type.measurement_unit if equipment and equipment.equipment_type else ('km' if reading.odometer is not None else 'hours')
        value = reading.odometer if unit == 'km' else reading.hours
        existing = db.query(MeterReadingChange).filter(MeterReadingChange.reading_id == reading.id, MeterReadingChange.action == 'add').first()
        if existing:
            existing.actor_id = actor_id; existing.operation_id = operation_id; existing.source = source
        else:
            db.add(MeterReadingChange(reading_id=reading.id, equipment_id=reading.equipment_id, operation_id=operation_id, actor_id=actor_id, changed_at=datetime.now(timezone.utc), action='add', source=source, reading_date=reading.reading_date, unit=unit, old_value=None, new_value=value, details='إضافة قراءة جديدة إلى النظام.'))
        count += 1
    db.flush()
    return count


def _refresh_equipment_after_rollback(db: Session, equipment_ids):
    for equipment_id in equipment_ids:
        equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not equipment: continue
        latest = db.query(MeterReading).filter(MeterReading.equipment_id == equipment_id).order_by(MeterReading.reading_date.desc(), MeterReading.id.desc()).first()
        unit = equipment.equipment_type.measurement_unit if equipment.equipment_type else 'hours'
        if unit == 'km': equipment.current_odometer = latest.odometer if latest else None
        else: equipment.current_hours = latest.hours if latest else None


def rollback_operation(db: Session, op, actor_id):
    if op.status == 'rolled_back': return 0
    ids = [int(x) for x in (op.reading_ids or []) if str(x).isdigit()]
    equipment_ids = [row[0] for row in db.query(MeterReading.equipment_id).filter(MeterReading.id.in_(ids)).distinct().all()] if ids else []
    count = db.query(MeterReading).filter(MeterReading.id.in_(ids)).delete(synchronize_session=False) if ids else 0
    _refresh_equipment_after_rollback(db, equipment_ids)
    op.status = 'rolled_back'; op.rolled_back_at = datetime.now(timezone.utc); op.rolled_back_by_id = actor_id
    add_event(db, op.id, 'rollback', actor_id, f'تم التراجع عن العملية وإلغاء {count} قراءة مرتبطة بها فقط.')
    db.commit()
    return count
