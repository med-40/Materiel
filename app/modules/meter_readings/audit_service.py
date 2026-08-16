from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.equipment.models import Equipment
from app.modules.meter_readings.audit import MeterReadingOperation, MeterReadingOperationEvent
from app.modules.meter_readings.models import MeterReading


def create_operation(
    db: Session,
    kind: str,
    user_id=None,
    equipment_id=None,
    filename=None,
    total_rows=0,
    reading_ids=None,
    rejected_rows=0,
):
    ids = [int(x) for x in (reading_ids or [])]
    op = MeterReadingOperation(
        kind=kind,
        created_by_id=user_id,
        equipment_id=equipment_id,
        filename=filename,
        total_rows=total_rows,
        status='completed' if not rejected_rows else 'completed_with_errors',
        accepted_rows=len(ids),
        rejected_rows=rejected_rows,
        reading_ids=ids,
    )
    db.add(op)
    db.flush()
    add_event(db, op.id, 'created', user_id, 'تم إنشاء عملية الإدخال.')
    add_event(
        db,
        op.id,
        'completed',
        user_id,
        f'تمت العملية: {len(ids)} مقبولة و{rejected_rows} مرفوضة من أصل {total_rows}.',
        payload={
            'total_rows': total_rows,
            'accepted_rows': len(ids),
            'rejected_rows': rejected_rows,
            'reading_ids': ids,
        },
    )
    return op


def add_event(db: Session, operation_id, event_type, actor_id, details, payload=None):
    event = MeterReadingOperationEvent(
        operation_id=operation_id,
        event_type=event_type,
        actor_id=actor_id,
        details=details,
        payload=payload,
    )
    db.add(event)
    db.flush()
    return event


def add_validation_details(db: Session, operation_id, actor_id, errors=None, warnings=None):
    errors = list(errors or [])
    warnings = list(warnings or [])
    if errors:
        add_event(
            db, operation_id, 'validation_errors', actor_id,
            f'تم رفض {len(errors)} صف/صفوف بسبب أخطاء في البيانات.',
            payload={'errors': errors},
        )
    if warnings:
        add_event(
            db, operation_id, 'warnings', actor_id,
            f'تم تسجيل {len(warnings)} تنبيهًا دون منع الإدخال.',
            payload={'warnings': warnings},
        )


def _refresh_equipment_after_rollback(db: Session, equipment_ids):
    """بعد التراجع، أعد العداد الحالي لكل عتاد تأثر بالعملية."""
    for equipment_id in equipment_ids:
        equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not equipment:
            continue
        latest = (
            db.query(MeterReading)
            .filter(MeterReading.equipment_id == equipment_id)
            .order_by(MeterReading.reading_date.desc(), MeterReading.id.desc())
            .first()
        )
        unit = equipment.equipment_type.measurement_unit if equipment.equipment_type else 'hours'
        if unit == 'km':
            equipment.current_odometer = latest.odometer if latest else None
        else:
            equipment.current_hours = latest.hours if latest else None


def rollback_operation(db: Session, op, actor_id):
    if op.status == 'rolled_back':
        return 0

    ids = [int(x) for x in (op.reading_ids or []) if str(x).isdigit()]
    equipment_ids = []
    if ids:
        equipment_ids = [
            row[0]
            for row in db.query(MeterReading.equipment_id)
            .filter(MeterReading.id.in_(ids))
            .distinct()
            .all()
        ]

    count = (
        db.query(MeterReading)
        .filter(MeterReading.id.in_(ids))
        .delete(synchronize_session=False)
        if ids else 0
    )

    _refresh_equipment_after_rollback(db, equipment_ids)
    op.status = 'rolled_back'
    op.rolled_back_at = datetime.utcnow()
    op.rolled_back_by_id = actor_id
    add_event(db, op.id, 'rollback', actor_id, f'تم التراجع عن العملية وإلغاء {count} قراءة مرتبطة بها فقط.')
    db.commit()
    return count
