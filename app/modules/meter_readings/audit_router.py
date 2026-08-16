from html import escape

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.meter_readings.models import MeterReading
from app.modules.meter_readings.audit import MeterReadingOperation

router = APIRouter(prefix='/meter-readings/operations', tags=['Meter Reading Operations'])


def _fmt(value):
    if value is None:
        return '—'
    try:
        n = float(value)
        return f'{int(n):,}' if n.is_integer() else f'{n:,.1f}'
    except Exception:
        return str(value)


def _kind_label(kind):
    return {'excel': 'Excel', 'paste': 'لصق', 'manual': 'يدوي'}.get(kind, kind)


def _value_and_unit(reading):
    equipment = reading.equipment
    unit = equipment.equipment_type.measurement_unit if equipment and equipment.equipment_type else 'hours'
    value = reading.odometer if unit == 'km' else reading.hours
    return value, ('كم' if unit == 'km' else 'ساعة عمل')


def _build_changes(db: Session, op: MeterReadingOperation):
    ids = [int(x) for x in (op.reading_ids or []) if str(x).isdigit()]
    if not ids:
        return []
    readings = (
        db.query(MeterReading)
        .filter(MeterReading.id.in_(ids))
        .order_by(MeterReading.equipment_id.asc(), MeterReading.reading_date.asc(), MeterReading.id.asc())
        .all()
    )
    result = []
    for reading in readings:
        equipment = reading.equipment
        if not equipment:
            continue
        new_value, unit = _value_and_unit(reading)
        previous = (
            db.query(MeterReading)
            .filter(
                MeterReading.equipment_id == reading.equipment_id,
                ~MeterReading.id.in_(ids),
                ((MeterReading.reading_date < reading.reading_date) |
                 ((MeterReading.reading_date == reading.reading_date) & (MeterReading.id < reading.id)))
            )
            .order_by(MeterReading.reading_date.desc(), MeterReading.id.desc())
            .first()
        )
        old_value = None
        if previous:
            old_value, _ = _value_and_unit(previous)
        result.append({
            'operation_id': op.id,
            'reading': reading,
            'equipment': equipment,
            'old': old_value,
            'new': new_value,
            'unit': unit,
            'source': _kind_label(op.kind),
            'created_at': op.created_at,
            'user_id': op.created_by_id,
            'rolled_back': op.status == 'rolled_back',
        })
    return result


@router.get('', response_class=HTMLResponse)
def operations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kind: str = Query('', description='نوع التعديل'),
):
    query = (
        db.query(MeterReadingOperation)
        .filter(MeterReadingOperation.accepted_rows > 0)
        .order_by(MeterReadingOperation.created_at.desc(), MeterReadingOperation.id.desc())
        .limit(100)
    )
    if kind in {'excel', 'paste', 'manual'}:
        query = query.filter(MeterReadingOperation.kind == kind)
    operations_rows = query.all()
    names = {u.id: f'{u.full_name} ({u.username})' for u in db.query(User).filter(User.id.in_([o.created_by_id for o in operations_rows if o.created_by_id])).all()}

    changes = []
    for op in operations_rows:
        changes.extend(_build_changes(db, op))
    changes.sort(key=lambda x: (x['created_at'], x['reading'].reading_date, x['reading'].id), reverse=True)

    body = '''<html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>سجل تعديلات قراءات العدادات</title><style>
body{font-family:Arial,sans-serif;margin:18px;background:#f8fafc;color:#172b4d}h2{margin:0 0 5px}.hint{color:#64748b;font-size:13px;margin:0 0 14px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.toolbar a{padding:8px 12px;border:1px solid #dbe3ec;border-radius:7px;background:#fff;color:#173f67;text-decoration:none}.toolbar a.active{background:#1769d1;color:#fff;border-color:#1769d1}.card{background:#fff;border:1px solid #dbe3ec;border-radius:10px;overflow:auto}table{width:100%;min-width:1100px;border-collapse:collapse}th,td{padding:9px;border:1px solid #dbe3ec;text-align:center;white-space:nowrap}th{background:#173f67;color:#fff}.old{color:#b45309;font-weight:700}.new{color:#166534;font-weight:800}.arrow{font-size:18px;color:#64748b}.user{font-weight:600}.source{color:#475569}.rolled{color:#991b1b;font-weight:700}.empty{padding:32px;text-align:center;color:#64748b}.badge{display:inline-block;background:#eef5ff;border:1px solid #c9ddfb;border-radius:999px;padding:5px 9px;font-size:12px;margin-left:5px}
</style></head><body>'''
    body += '<h2>سجل تعديلات قراءات العدادات</h2>'
    body += '<p class="hint">هذا السجل مخصص للتعديلات الفعلية فقط: من عدّل، أي عتاد، متى، والقراءة السابقة والجديدة. لا يعرض ملفات Excel أو تفاصيل الاستيراد أو أخطاء الصفوف.</p>'
    body += '<div class="toolbar"><a href="/meter-readings">← قراءات العدادات</a>'
    body += f'<a class="{"active" if not kind else ""}" href="/meter-readings/operations">كل التعديلات</a>'
    for value, label in [('manual','يدوي'),('excel','Excel'),('paste','لصق')]:
        body += f'<a class="{"active" if kind == value else ""}" href="/meter-readings/operations?kind={value}">{label}</a>'
    body += '</div>'
    body += f'<p><span class="badge">عدد التعديلات: {len(changes)}</span></p>'
    body += '<div class="card"><table><thead><tr><th>وقت التعديل</th><th>المستخدم</th><th>الطراز</th><th>رقم التسجيل</th><th>تاريخ القراءة</th><th>القراءة السابقة</th><th></th><th>القراءة الجديدة</th><th>الوحدة</th><th>طريقة الإدخال</th><th>حالة التعديل</th></tr></thead><tbody>'

    if not changes:
        body += '<tr><td colspan="11" class="empty">لا توجد تعديلات فعلية مسجلة.</td></tr>'
    else:
        for change in changes:
            equipment = change['equipment']
            reading = change['reading']
            model = equipment.equipment_model.name if equipment.equipment_model else '—'
            registration = equipment.registration_number or '—'
            old = 'لا توجد قراءة سابقة' if change['old'] is None else _fmt(change['old'])
            status = 'تم التراجع عنها' if change['rolled_back'] else 'موجودة'
            body += f'<tr><td>{change["created_at"]:%d/%m/%Y %H:%M:%S}</td><td class="user">{escape(names.get(change["user_id"], "—"))}</td><td>{escape(model)}</td><td>{escape(registration)}</td><td>{reading.reading_date:%d/%m/%Y}</td><td class="old">{old}</td><td class="arrow">→</td><td class="new">{_fmt(change["new"])}</td><td>{change["unit"]}</td><td class="source">{escape(change["source"])}</td><td class="rolled">{status if change["rolled_back"] else "موجودة"}</td></tr>'
    body += '</tbody></table></div>'
    body += '<p class="hint">إدارة الجلسات والتراجع والأخطاء تبقى خارج هذا السجل، حتى يبقى سجل التعديلات واضحًا ومخصصًا لما تغيّر في البيانات فقط.</p>'
    body += '</body></html>'
    return HTMLResponse(body)
