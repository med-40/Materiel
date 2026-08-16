from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.meter_readings.audit import MeterReadingOperation, MeterReadingOperationEvent

router = APIRouter(prefix='/meter-readings/operations', tags=['Meter Reading Operations'])

@router.get('', response_class=HTMLResponse)
def operations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(MeterReadingOperation).order_by(MeterReadingOperation.created_at.desc(), MeterReadingOperation.id.desc()).limit(100).all()
    body = '<h2>سجل عمليات الإدخال</h2><table class="data-table"><thead><tr><th>العملية</th><th>النوع</th><th>التاريخ</th><th>المستخدم</th><th>العتاد</th><th>القراءات</th><th>الحالة</th><th></th></tr></thead><tbody>'
    for op in rows:
        body += f'<tr><td>#{op.id}</td><td>{op.kind}</td><td>{op.created_at:%d/%m/%Y %H:%M}</td><td>{op.created_by_id or "—"}</td><td>{op.equipment_id or "—"}</td><td>{op.accepted_rows}/{op.total_rows}</td><td>{op.status}</td><td><a href="/meter-readings/operations/{op.id}">التفاصيل</a></td></tr>'
    return HTMLResponse(body + '</tbody></table>')

@router.get('/{operation_id}', response_class=HTMLResponse)
def operation_details(operation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    op = db.query(MeterReadingOperation).filter(MeterReadingOperation.id == operation_id).first()
    if not op: raise HTTPException(404, 'عملية الإدخال غير موجودة.')
    events = db.query(MeterReadingOperationEvent).filter(MeterReadingOperationEvent.operation_id == op.id).order_by(MeterReadingOperationEvent.created_at.asc(), MeterReadingOperationEvent.id.asc()).all()
    body = f'<h2>تفاصيل عملية الإدخال #{op.id}</h2><p>النوع: {op.kind} | التاريخ: {op.created_at:%d/%m/%Y %H:%M} | المستخدم: {op.created_by_id or "—"} | الحالة: {op.status}</p><p>الإجمالي: {op.total_rows} | المقبول: {op.accepted_rows} | المرفوض: {op.rejected_rows}</p><h3>سجل الأحداث</h3><table class="data-table"><thead><tr><th>التاريخ والوقت</th><th>المستخدم</th><th>الحدث</th><th>التفاصيل</th></tr></thead><tbody>'
    for e in events: body += f'<tr><td>{e.created_at:%d/%m/%Y %H:%M:%S}</td><td>{e.actor_id or "النظام"}</td><td>{e.event_type}</td><td>{e.details or "—"}</td></tr>'
    body += '</tbody></table>'
    if op.status in ('completed','completed_with_errors'):
        body += f'<form method="post" action="/meter-readings/operations/{op.id}/rollback" onsubmit="return confirm(\'سيتم التراجع عن هذه العملية. هل أنت متأكد؟\')"><button type="submit">↩ التراجع عن العملية</button></form>'
    return HTMLResponse(body)
