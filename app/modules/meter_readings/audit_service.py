from datetime import datetime
from sqlalchemy.orm import Session
from app.modules.meter_readings.audit import MeterReadingOperation, MeterReadingOperationEvent

def create_operation(db: Session, kind: str, user_id=None, equipment_id=None, filename=None, total_rows=0):
    op = MeterReadingOperation(kind=kind, created_by_id=user_id, equipment_id=equipment_id, filename=filename, total_rows=total_rows, status='draft')
    db.add(op); db.flush()
    add_event(db, op.id, 'created', user_id, 'تم إنشاء عملية الإدخال.')
    return op

def add_event(db: Session, operation_id, event_type, actor_id, details, payload=None):
    event = MeterReadingOperationEvent(operation_id=operation_id, event_type=event_type, actor_id=actor_id, details=details, payload=payload)
    db.add(event); db.flush(); return event

def finish_operation(db: Session, op, accepted, rejected, actor_id):
    op.accepted_rows = accepted; op.rejected_rows = rejected
    op.status = 'completed' if rejected == 0 else 'completed_with_errors'
    add_event(db, op.id, 'completed', actor_id, f'تمت العملية: {accepted} مقبولة و{rejected} مرفوضة.')
    return op

def rollback_operation(db: Session, op, actor_id, count):
    op.status = 'rolled_back'; op.rolled_back_at = datetime.utcnow(); op.rolled_back_by_id = actor_id
    add_event(db, op.id, 'rollback', actor_id, f'تم التراجع عن العملية وإلغاء {count} قراءة.')
    return op
