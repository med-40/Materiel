from html import escape
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.equipment.models import Equipment
from app.modules.meter_readings.audit import MeterReadingChange

router = APIRouter(prefix='/meter-readings/operations', tags=['Meter Reading Operations'])


def _fmt(value):
    if value is None: return '—'
    try:
        n = float(value)
        return f'{int(n):,}' if n.is_integer() else f'{n:,.1f}'
    except Exception: return str(value)


def _action(value): return {'add': 'إضافة قراءة', 'update': 'تعديل قراءة'}.get(value, value)


@router.get('', response_class=HTMLResponse)
def operations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user), action: str = Query('')):
    query = db.query(MeterReadingChange).order_by(MeterReadingChange.changed_at.desc(), MeterReadingChange.id.desc())
    if action in {'add', 'update'}: query = query.filter(MeterReadingChange.action == action)
    changes = query.limit(500).all()
    actor_ids = [x.actor_id for x in changes if x.actor_id]
    equipment_ids = [x.equipment_id for x in changes if x.equipment_id]
    names = {u.id: f'{u.full_name} ({u.username})' for u in db.query(User).filter(User.id.in_(actor_ids)).all()} if actor_ids else {}
    equipment_map = {e.id: e for e in db.query(Equipment).filter(Equipment.id.in_(equipment_ids)).all()} if equipment_ids else {}

    body = '''<html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>سجل تعديلات قراءات العدادات</title><style>body{font-family:Arial,sans-serif;margin:20px;background:#f8fafc;color:#172b4d}h2{margin-bottom:6px}.hint{color:#64748b;font-size:13px;margin:0 0 14px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.toolbar a{padding:8px 12px;border:1px solid #dbe3ec;border-radius:7px;background:#fff;color:#173f67;text-decoration:none}.toolbar a.active{background:#1769d1;color:#fff;border-color:#1769d1}.card{background:#fff;border:1px solid #dbe3ec;border-radius:10px;overflow:auto}table{width:100%;min-width:1050px;border-collapse:collapse}th,td{padding:9px;border:1px solid #dbe3ec;text-align:center;white-space:nowrap}th{background:#173f67;color:white}.new{font-weight:700;color:#166534}.old{font-weight:700;color:#92400e}.empty{padding:30px;text-align:center;color:#64748b}.badge{background:#eef5ff;border:1px solid #c9ddfb;border-radius:999px;padding:5px 9px;font-size:12px}</style></head><body>'''
    body += '<h2>سجل تعديلات قراءات العدادات</h2><p class="hint">يعرض التغيير الفعلي فقط: من قام به، متى، والقيمة قبل التعديل وبعده. تفاصيل ملفات الاستيراد والأخطاء ليست جزءًا من هذا السجل.</p>'
    body += '<div class="toolbar"><a href="/meter-readings">← قراءات العدادات</a>'
    body += f'<a class="{"active" if not action else ""}" href="/meter-readings/operations">كل التعديلات</a><a class="{"active" if action == "add" else ""}" href="/meter-readings/operations?action=add">الإضافات</a><a class="{"active" if action == "update" else ""}" href="/meter-readings/operations?action=update">التعديلات</a></div>'
    body += f'<p><span class="badge">عدد التغييرات المعروضة: {len(changes)}</span></p>'
    body += '<div class="card"><table><thead><tr><th>التاريخ والوقت</th><th>المستخدم</th><th>نوع التغيير</th><th>العتاد</th><th>رقم التسجيل</th><th>تاريخ القراءة</th><th>القيمة السابقة</th><th>القيمة الجديدة</th><th>الوحدة</th><th>المصدر</th></tr></thead><tbody>'
    for change in changes:
        equipment = equipment_map.get(change.equipment_id)
        model = '—'
        registration = '—'
        if equipment:
            registration = equipment.registration_number or equipment.asset_code or '—'
            model = equipment.equipment_model.name if equipment.equipment_model else '—'
        body += '<tr>'
        body += f'<td>{change.changed_at:%d/%m/%Y %H:%M:%S}</td><td>{escape(names.get(change.actor_id, "غير محدد"))}</td><td>{escape(_action(change.action))}</td><td>{escape(model)}</td><td>{escape(registration)}</td>'
        body += f'<td>{change.reading_date:%d/%m/%Y}</td>' if change.reading_date else '<td>—</td>'
        body += f'<td class="old">{_fmt(change.old_value)}</td><td class="new">{_fmt(change.new_value)}</td><td>{"كم" if change.unit == "km" else "ساعة عمل"}</td><td>{escape(change.source or "—")}</td></tr>'
    if not changes: body += '<tr><td colspan="10" class="empty">لا توجد تعديلات مسجلة بعد.</td></tr>'
    body += '</tbody></table></div></body></html>'
    return HTMLResponse(body)
