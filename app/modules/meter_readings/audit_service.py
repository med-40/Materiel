from datetime import datetime
from sqlalchemy.orm import Session
from app.modules.meter_readings.audit import MeterReadingOperation, MeterReadingOperationEvent
from app.modules.meter_readings.models import MeterReading

def create_operation(db: Session, kind: str, user_id=None, equipment_id=None, filename=None, total_rows=0, reading_ids=None, rejected_rows=0):
    ids = [int(x) for x in (reading_ids or [])]
    op = MeterReadingOperation(kind=kind, created_by_id=user_id, equipment_id=equipment_id, filename=filename, total_rows=total_rows, status='completed' if not rejected_rows else 'completed_with_errors', accepted_rows=len(ids), rejected_rows=rejected_rows, reading_ids=ids)
    db.add(op); db.flush()
    add_event(db, op.id, 'created', user_id, 'تم إنشاء عملية الإدخال.')
    add_event(db, op.id, 'completed', user_id, f'تمت العملية: {len(ids)} مقبولة و{rejected_rows} مرفوضة.')
    return op

def add_event(db: Session, operation_id, event_type, actor_id, details, payload=None):
    event = MeterReadingOperationEvent(operation_id=operation_id, event_type=event_type, actor_id=actor_id, details=details, payload=payload)
    db.add(event); db.flush(); return event

def rollback_operation(db: Session, op, actor_id):
    if op.status == 'rolled_back':
        return 0
    ids = [int(x) for x in (op.reading_ids or []) if str(x).isdigit()]
    count = db.query(MeterReading).filter(MeterReading.id.in_(ids)).delete(synchronize_session=False) if ids else 0
    op.status = 'rolled_back'; op.rolled_back_at = datetime.utcnow(); op.rolled_back_by_id = actor_id
    add_event(db, op.id, 'rollback', actor_id, f'تم التراجع عن العملية وإلغاء {count} قراءة مرتبطة بها فقط.')
    db.commit()
    return count
