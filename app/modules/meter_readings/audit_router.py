from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

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
    if value is None:
        return '—'
    try:
        n = float(value)
        return f'{int(n):,}' if n.is_integer() else f'{n:,.1f}'
    except Exception:
        return str(value)


def _kind_label(kind):
    return {'excel': 'استيراد Excel', 'paste': 'لصق جماعي', 'manual': 'إدخال يدوي'}.get(kind, kind)


def _status_label(status):
    return 'تم التراجع عنها' if status == 'rolled_back' else ('مكتملة مع أخطاء' if status == 'completed_with_errors' else 'مكتملة')


def _event_extra(event):
    if not event.payload:
        return ''
    payload = event.payload if isinstance(event.payload, dict) else {}
    parts = []
    for key, title in (("errors", "الأخطاء"), ("warnings", "التنبيهات")):
        values = payload.get(key) or []
        if values:
            items = ''.join(f'<li>{escape(str(v))}</li>' for v in values[:100])
            parts.append(f'<details><summary>{title} ({len(values)})</summary><ul>{items}</ul></details>')
    return ''.join(parts)


def _reading_value(reading):
    equipment = reading.equipment
    unit = equipment.equipment_type.measurement_unit if equipment and equipment.equipment_type else 'hours'
    value = reading.odometer if unit == 'km' else reading.hours
    return _fmt(value), ('كم' if unit == 'km' else 'ساعة عمل')


@router.get('', response_class=HTMLResponse)
def operations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kind: str = Query('', description='نوع العملية'),
):
    # هذه الصفحة تعرض التعديلات التي أثرت فعليًا على البيانات فقط؛
    # الصفوف المرفوضة/الفارغة تبقى في تفاصيل العملية وسجل الأحداث.
    query = (
        db.query(MeterReadingOperation)
        .filter(MeterReadingOperation.accepted_rows > 0)
        .order_by(MeterReadingOperation.created_at.desc(), MeterReadingOperation.id.desc())
        .limit(100)
    )
    if kind in {'excel', 'paste', 'manual'}:
        query = query.filter(MeterReadingOperation.kind == kind)
    operations_rows = query.all()

    reading_ids = [int(rid) for op in operations_rows for rid in (op.reading_ids or []) if str(rid).isdigit()]
    readings = (
        db.query(MeterReading)
        .options(joinedload(MeterReading.equipment).joinedload('equipment_type'), joinedload(MeterReading.equipment).joinedload('equipment_model'))
        .filter(MeterReading.id.in_(reading_ids))
        .order_by(MeterReading.reading_date.desc(), MeterReading.id.desc())
        .all()
        if reading_ids else []
    )
    reading_map = {r.id: r for r in readings}
    names = _user_names(db, [x.created_by_id for x in operations_rows] + [x.rolled_back_by_id for x in operations_rows])

    body = '''<html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>سجل تعديلات قراءات العدادات</title><style>
body{font-family:Arial,sans-serif;margin:20px;background:#f8fafc;color:#172b4d}h2{margin-bottom:6px}.hint{color:#64748b;font-size:13px;margin:0 0 14px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.toolbar a,.toolbar button{padding:8px 12px;border:1px solid #dbe3ec;border-radius:7px;background:#fff;color:#173f67;text-decoration:none}.toolbar a.active{background:#1769d1;color:#fff;border-color:#1769d1}.card{background:#fff;border:1px solid #dbe3ec;border-radius:10px;overflow:auto}table{width:100%;min-width:1050px;border-collapse:collapse}th,td{padding:9px;border:1px solid #dbe3ec;text-align:center;white-space:nowrap}th{background:#173f67;color:white}td strong{color:#173f67}.muted{color:#64748b}.changed{font-weight:700;color:#166534}.rolled{color:#991b1b;font-weight:700}.details{color:#1769d1;text-decoration:none;font-weight:700}.empty{padding:30px;text-align:center;color:#64748b}.summary{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.badge{background:#eef5ff;border:1px solid #c9ddfb;border-radius:999px;padding:5px 9px;font-size:12px}
</style></head><body>'''
    body += '<h2>سجل تعديلات قراءات العدادات</h2>'
    body += '<p class="hint">يعرض فقط القراءات التي أُضيفت فعليًا إلى النظام بواسطة عمليات الإدخال. الأخطاء والصفوف المرفوضة لا تختفي؛ تجدها داخل تفاصيل العملية.</p>'
    body += '<div class="toolbar">'
    body += '<a href="/meter-readings">← العودة إلى قراءات العدادات</a>'
    body += f'<a class="{"active" if not kind else ""}" href="/meter-readings/operations">كل التعديلات</a>'
    for value, label in [('excel','استيراد Excel'),('paste','لصق جماعي'),('manual','إدخال يدوي')]:
        body += f'<a class="{"active" if kind == value else ""}" href="/meter-readings/operations?kind={value}">{label}</a>'
    body += '</div>'
    body += f'<div class="summary"><span class="badge">عدد العمليات المؤثرة: {len(operations_rows)}</span><span class="badge">عدد القراءات المعروضة: {len(readings)}</span></div>'
    body += '<div class="card"><table><thead><tr><th>العملية</th><th>النوع</th><th>المستخدم</th><th>وقت التعديل</th><th>العتاد</th><th>رقم التسجيل</th><th>تاريخ القراءة</th><th>القراءة الجديدة</th><th>الوحدة</th><th>الملاحظة</th><th>حالة العملية</th><th></th></tr></thead><tbody>'
    found = 0
    for op in operations_rows:
        for rid in (op.reading_ids or []):
            reading = reading_map.get(int(rid)) if str(rid).isdigit() else None
            if not reading:
                # القراءة قد تكون أزيلت بعد التراجع؛ تبقى العملية ظاهرة في التفاصيل فقط.
                continue
            found += 1
            equipment = reading.equipment
            model = equipment.equipment_model.name if equipment and equipment.equipment_model else '—'
            registration = equipment.registration_number if equipment else '—'
            value, unit = _reading_value(reading)
            status_class = 'rolled' if op.status == 'rolled_back' else 'changed'
            body += f'<tr><td>#{op.id}</td><td>{escape(_kind_label(op.kind))}</td><td>{escape(names.get(op.created_by_id, "—"))}</td><td>{op.created_at:%d/%m/%Y %H:%M:%S}</td><td><strong>{escape(model)}</strong></td><td>{escape(registration or "—")}</td><td>{reading.reading_date:%d/%m/%Y}</td><td class="{status_class}">{value}</td><td>{unit}</td><td>{escape(reading.notes or "—")}</td><td>{escape(_status_label(op.status))}</td><td><a class="details" href="/meter-readings/operations/{op.id}">التفاصيل</a></td></tr>'
    if found == 0:
        body += '<tr><td colspan="12" class="empty">لا توجد تعديلات فعلية مطابقة للفلتر.</td></tr>'
    body += '</tbody></table></div>'
    body += '<p class="hint">ملاحظة: التراجع عن عملية يحذف القراءات التي أنشأتها تلك العملية فقط، ويسجل ذلك في تاريخ العملية.</p>'
    body += '</body></html>'
    return HTMLResponse(body)


@router.get('/{operation_id}', response_class=HTMLResponse)
def operation_details(operation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    op = db.query(MeterReadingOperation).filter(MeterReadingOperation.id == operation_id).first()
    if not op:
        raise HTTPException(404, 'عملية الإدخال غير موجودة.')
    events = db.query(MeterReadingOperationEvent).filter(MeterReadingOperationEvent.operation_id == op.id).order_by(MeterReadingOperationEvent.created_at.asc(), MeterReadingOperationEvent.id.asc()).all()
    readings = db.query(MeterReading).options(joinedload(MeterReading.equipment).joinedload('equipment_type'), joinedload(MeterReading.equipment).joinedload('equipment_model')).filter(MeterReading.id.in_(op.reading_ids or [])).order_by(MeterReading.reading_date.asc(), MeterReading.id.asc()).all() if op.reading_ids else []
    names = _user_names(db, [op.created_by_id, op.rolled_back_by_id] + [e.actor_id for e in events])
    status = _status_label(op.status)
    label = _kind_label(op.kind)
    body = f'''<html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تفاصيل التعديل #{op.id}</title><style>body{{font-family:Arial,sans-serif;margin:20px;background:#f8fafc;color:#172b4d}}section{{background:white;border:1px solid #dbe3ec;border-radius:10px;padding:14px;margin:12px 0}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:9px;border:1px solid #dbe3ec;text-align:center}}th{{background:#173f67;color:white}}a{{color:#1769d1;text-decoration:none}}button{{padding:9px 14px;border-radius:7px;border:1px solid #b91c1c;background:#fff;color:#b91c1c}}summary{{cursor:pointer;color:#92400e}}</style></head><body>'''
    body += f'<h2>تفاصيل التعديل #{op.id}</h2>'
    body += f'<section><p>النوع: <strong>{escape(label)}</strong></p><p>التاريخ والوقت: <strong>{op.created_at:%d/%m/%Y %H:%M:%S}</strong></p><p>المستخدم: <strong>{escape(names.get(op.created_by_id, "—"))}</strong></p><p>الملف: <strong>{escape(op.filename or "—")}</strong></p><p>الحالة: <strong>{escape(status)}</strong></p><p>الإجمالي: {op.total_rows} | تم إدخاله: {op.accepted_rows} | المرفوض: {op.rejected_rows}</p></section>'
    body += '<section><h3>التعديلات التي أدخلتها هذه العملية</h3><table><thead><tr><th>#</th><th>الطراز</th><th>رقم التسجيل</th><th>تاريخ القراءة</th><th>القراءة</th><th>الوحدة</th><th>الملاحظات</th></tr></thead><tbody>'
    for n, r in enumerate(readings, 1):
        equipment = r.equipment
        model = equipment.equipment_model.name if equipment and equipment.equipment_model else '—'
        registration = equipment.registration_number if equipment else '—'
        value, unit = _reading_value(r)
        body += f'<tr><td>{n}</td><td>{escape(model)}</td><td>{escape(registration or "—")}</td><td>{r.reading_date:%d/%m/%Y}</td><td>{value}</td><td>{unit}</td><td>{escape(r.notes or "—")}</td></tr>'
    body += '</tbody></table></section>'
    body += '<section><h3>سجل الأحداث</h3><table><thead><tr><th>التاريخ والوقت</th><th>المستخدم</th><th>الحدث</th><th>التفاصيل</th></tr></thead><tbody>'
    for e in events:
        body += f'<tr><td>{e.created_at:%d/%m/%Y %H:%M:%S}</td><td>{escape(names.get(e.actor_id, "النظام"))}</td><td>{escape(e.event_type)}</td><td>{escape(e.details or "—")}{_event_extra(e)}</td></tr>'
    body += '</tbody></table></section>'
    if op.status != 'rolled_back' and op.reading_ids:
        body += f'<section><form method="post" action="/meter-readings/operations/{op.id}/rollback" onsubmit="return confirm(\'سيتم التراجع عن القراءات التي أنشأتها هذه العملية فقط. هل تريد المتابعة؟\')"><button type="submit">↩ التراجع عن العملية</button></form></section>'
    body += '<p><a href="/meter-readings/operations">← سجل التعديلات</a> | <a href="/meter-readings">قراءات العدادات</a></p></body></html>'
    return HTMLResponse(body)


@router.post('/{operation_id}/rollback')
def rollback(operation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    op = db.query(MeterReadingOperation).filter(MeterReadingOperation.id == operation_id).first()
    if not op:
        raise HTTPException(404, 'عملية الإدخال غير موجودة.')
    if op.status == 'rolled_back':
        raise HTTPException(400, 'تم التراجع عن هذه العملية سابقًا.')
    rollback_operation(db, op, getattr(current_user, 'id', None))
    return RedirectResponse(url=f'/meter-readings/operations/{operation_id}', status_code=303)
