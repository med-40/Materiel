from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.meter_readings.models import MeterReading
from app.modules.meter_readings.audit import MeterReadingOperation, MeterReadingOperationEvent
from app.modules.meter_readings.audit_service import rollback_operation

router = APIRouter(prefix='/meter-readings/operations', tags=['Meter Reading Operations'])

def _user_names(db, ids):
    ids = [x for x in ids if x]
    return {u.id: f'{u.full_name} ({u.username})' for u in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}

def _fmt(value):
    if value is None: return '—'
    try:
        n = float(value)
        return f'{int(n):,}' if n.is_integer() else f'{n:,.1f}'
    except Exception: return str(value)

@router.get('', response_class=HTMLResponse)
def operations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(MeterReadingOperation).order_by(MeterReadingOperation.created_at.desc(), MeterReadingOperation.id.desc()).limit(100).all()
    names = _user_names(db, [x.created_by_id for x in rows] + [x.rolled_back_by_id for x in rows])
    body = '<html dir="rtl"><head><meta charset="utf-8"><title>سجل عمليات الإدخال</title></head><body><h2>سجل عمليات الإدخال</h2><p><a href="/meter-readings">← قراءات العدادات</a></p><table class="data-table"><thead><tr><th>العملية</th><th>النوع</th><th>التاريخ والوقت</th><th>المستخدم</th><th>العتاد</th><th>القراءات</th><th>الحالة</th><th></th></tr></thead><tbody>'
    for op in rows:
        label = {'excel':'استيراد Excel','paste':'لصق جماعي','manual':'إدخال يدوي'}.get(op.kind, op.kind)
        status = 'تم التراجع عنها' if op.status == 'rolled_back' else 'مكتملة'
        body += f'<tr><td>#{op.id}</td><td>{label}</td><td>{op.created_at:%d/%m/%Y %H:%M}</td><td>{names.get(op.created_by_id, "—")}</td><td>{op.equipment_id or "متعدد/—"}</td><td>{op.accepted_rows}/{op.total_rows}</td><td>{status}</td><td><a href="/meter-readings/operations/{op.id}">التفاصيل</a></td></tr>'
    return HTMLResponse(body + '</tbody></table></body></html>')

@router.get('/{operation_id}', response_class=HTMLResponse)
def operation_details(operation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    op = db.query(MeterReadingOperation).filter(MeterReadingOperation.id == operation_id).first()
    if not op: raise HTTPException(404, 'عملية الإدخال غير موجودة.')
    events = db.query(MeterReadingOperationEvent).filter(MeterReadingOperationEvent.operation_id == op.id).order_by(MeterReadingOperationEvent.created_at.asc(), MeterReadingOperationEvent.id.asc()).all()
    readings = db.query(MeterReading).filter(MeterReading.id.in_(op.reading_ids or [])).order_by(MeterReading.reading_date.asc(), MeterReading.id.asc()).all() if op.reading_ids else []
    names = _user_names(db, [op.created_by_id, op.rolled_back_by_id] + [e.actor_id for e in events])
    status = 'تم التراجع عنها' if op.status == 'rolled_back' else 'مكتملة'
    label = {'excel':'استيراد Excel','paste':'لصق جماعي','manual':'إدخال يدوي'}.get(op.kind, op.kind)
    body = f'<html dir="rtl"><head><meta charset="utf-8"><title>تفاصيل العملية #{op.id}</title></head><body><h2>تفاصيل عملية الإدخال #{op.id}</h2><p>النوع: <strong>{label}</strong> | التاريخ: {op.created_at:%d/%m/%Y %H:%M} | المستخدم: <strong>{names.get(op.created_by_id, "—")}</strong> | الحالة: <strong>{status}</strong></p><p>العتاد: {op.equipment_id or "متعدد"} | الإجمالي: {op.total_rows} | المقبول: {op.accepted_rows} | المرفوض: {op.rejected_rows}</p><h3>القراءات التي أنشأتها العملية</h3><table class="data-table"><thead><tr><th>#</th><th>العتاد</th><th>التاريخ</th><th>الكيلومترات</th><th>الساعات</th><th>الملاحظات</th></tr></thead><tbody>'
    for n, r in enumerate(readings, 1):
        body += f'<tr><td>{n}</td><td>{r.equipment_id}</td><td>{r.reading_date:%d/%m/%Y}</td><td>{_fmt(r.odometer)}</td><td>{_fmt(r.hours)}</td><td>{r.notes or "—"}</td></tr>'
    body += '</tbody></table><h3>سجل الأحداث</h3><table class="data-table"><thead><tr><th>التاريخ والوقت</th><th>المستخدم</th><th>الحدث</th><th>التفاصيل</th></tr></thead><tbody>'
    for e in events:
        body += f'<tr><td>{e.created_at:%d/%m/%Y %H:%M:%S}</td><td>{names.get(e.actor_id, "النظام")}</td><td>{e.event_type}</td><td>{e.details or "—"}</td></tr>'
    body += '</tbody></table>'
    if op.status != 'rolled_back' and op.reading_ids:
        body += f'<p><form method="post" action="/meter-readings/operations/{op.id}/rollback" onsubmit="return confirm(\'سيتم التراجع عن {len(op.reading_ids)} قراءة أدخلتها هذه العملية فقط. هل تريد المتابعة؟\')"><button type="submit">↩ التراجع عن العملية</button></form></p>'
    return HTMLResponse(body + '<p><a href="/meter-readings/operations">← سجل العمليات</a></p></body></html>')

@router.post('/{operation_id}/rollback')
def rollback(operation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    op = db.query(MeterReadingOperation).filter(MeterReadingOperation.id == operation_id).first()
    if not op: raise HTTPException(404, 'عملية الإدخال غير موجودة.')
    if op.status == 'rolled_back': raise HTTPException(400, 'تم التراجع عن هذه العملية سابقًا.')
    rollback_operation(db, op, getattr(current_user, 'id', None))
    return RedirectResponse(url=f'/meter-readings/operations/{operation_id}', status_code=303)
