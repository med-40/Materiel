from contextvars import ContextVar
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.modules.meter_readings.models import MeterReading
from app.modules.meter_readings.audit import MeterReadingOperation, MeterReadingOperationEvent
from app.database.session import SessionLocal

_current_actor = ContextVar('meter_audit_actor', default=None)
_current_kind = ContextVar('meter_audit_kind', default='manual')

def set_request_actor(user_id, kind='manual'):
    _current_actor.set(user_id)
    _current_kind.set(kind)

def _kind_from_source(source):
    kind = _current_kind.get()
    if kind in {'excel', 'paste', 'manual'}:
        return kind
    return 'excel' if source == 'import' else 'manual'

@event.listens_for(Session, 'after_flush')
def _collect_meter_readings(session, flush_context):
    ids = session.info.setdefault('_meter_audit_reading_ids', [])
    for obj in session.new:
        if isinstance(obj, MeterReading) and obj.id is not None:
            ids.append(obj.id)

@event.listens_for(Session, 'after_commit')
def _write_meter_operation(session):
    ids = session.info.pop('_meter_audit_reading_ids', [])
    if not ids:
        return
    ids = list(dict.fromkeys(ids))
    actor = _current_actor.get()
    kind = _kind_from_source('import' if kind_has_import(session, ids) else 'manual')
    try:
        with SessionLocal() as audit_db:
            readings = audit_db.query(MeterReading).filter(MeterReading.id.in_(ids)).all()
            if not readings:
                return
            equipment_ids = sorted({r.equipment_id for r in readings})
            op = MeterReadingOperation(kind=kind, filename=None, equipment_id=equipment_ids[0] if len(equipment_ids) == 1 else None, created_by_id=actor, status='completed', total_rows=len(readings), accepted_rows=len(readings), rejected_rows=0, reading_ids=[r.id for r in readings])
            audit_db.add(op); audit_db.flush()
            audit_db.add(MeterReadingOperationEvent(operation_id=op.id, event_type='created', actor_id=actor, details='تم إنشاء العملية وتسجيل القراءات التي أُدخلت خلالها.'))
            audit_db.add(MeterReadingOperationEvent(operation_id=op.id, event_type='completed', actor_id=actor, details=f'تم حفظ {len(readings)} قراءة.'))
            audit_db.commit()
    except Exception:
        # التدقيق لا يجب أن يعطل حفظ القراءة نفسها.
        return

def kind_has_import(session, ids):
    return False
