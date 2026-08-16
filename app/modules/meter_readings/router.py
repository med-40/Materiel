from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html import escape
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from openpyxl.utils.datetime import from_excel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.templating import get_module_templates
from app.database.session import get_db
from app.modules.equipment import services as equipment_services
from app.modules.equipment_types import services as type_services
from app.modules.meter_readings import services
from app.modules.meter_readings.audit_service import add_validation_details, create_operation, record_changes_for_readings
from app.modules.meter_readings.excel_reader import load_meter_workbook
from app.modules.users.models import User

router = APIRouter(prefix="/meter-readings", tags=["Meter Readings"])
templates = get_module_templates("app/modules/meter_readings/templates")


def _parse_type_id(value: str | None) -> Optional[int]:
    if value is None or not str(value).strip(): return None
    try: parsed = int(str(value).strip())
    except (ValueError, TypeError): return None
    return parsed if parsed > 0 else None


def _parse_decimal(value):
    if value is None or str(value).strip() == "": raise ValueError("قيمة العداد فارغة")
    text = str(value).strip().replace(" ", "").replace(",", "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).replace("٫", ".")
    try: return Decimal(text)
    except InvalidOperation as exc: raise ValueError("قيمة العداد غير صحيحة") from exc


def _parse_date(value):
    if isinstance(value, datetime): return value
    if isinstance(value, date): return datetime.combine(value, datetime.min.time())
    if isinstance(value, (int, float)):
        try:
            parsed = from_excel(value)
            return parsed if isinstance(parsed, datetime) else datetime.combine(parsed, datetime.min.time())
        except Exception: pass
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try: return datetime.strptime(text, fmt)
        except ValueError: continue
    raise ValueError("تاريخ القراءة غير صحيح")


def _error_card(message: str, title: str = "خطأ في البيانات"):
    return f'<div class="error-card">⚠️ <strong>{escape(title)}</strong><span>{escape(str(message))}</span></div>'


def _warning_card(message: str): return f'<div class="warning-card">⚠️ <strong>تنبيه</strong><span>{escape(str(message))}</span></div>'


def _page_context(request, db, current_user, page, page_size, search, type_id, unit, sort):
    rows, total, pages, last_update = services.list_latest_rows(db, page=page, page_size=page_size, search=search, type_id=type_id, unit=unit, sort=sort)
    return {"request": request, "user": current_user, "readings": rows, "equipment_options": equipment_services.list_equipment(db, limit=10000), "types": type_services.list_types(db), "total": total, "page": page, "page_size": page_size, "pages": pages, "search": search, "type_id": type_id, "unit": unit, "sort": sort, "last_update": last_update}


def _finish_operation(db: Session, current_user: User, kind: str, filename: str | None, total_rows: int, reading_ids: list[int], rejected_rows: int, errors: list[str], warnings: list[str]):
    op = create_operation(db, kind=kind, user_id=getattr(current_user, "id", None), filename=filename, total_rows=total_rows, reading_ids=reading_ids, rejected_rows=rejected_rows)
    add_validation_details(db, op.id, getattr(current_user, "id", None), errors=errors, warnings=warnings)
    record_changes_for_readings(db, reading_ids, getattr(current_user, "id", None), operation_id=op.id, source=kind)
    db.commit()
    return op


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def meter_readings_page(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=5, le=100), search: str = Query(""), type_id: str | None = Query(default=None), unit: str = Query(""), sort: str = Query("date_desc"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    services.cleanup_invalid_readings(db)
    return templates.TemplateResponse("meter_readings.html", _page_context(request, db, current_user, page, page_size, search, _parse_type_id(type_id), unit, sort))


@router.post("/create")
def meter_reading_create(equipment_id: int = Form(...), reading_date: str = Form(...), value: str = Form(...), equipment_status: str | None = Form(None), notes: str = Form(""), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        date_value = _parse_date(reading_date); meter_value = _parse_decimal(value); equipment = equipment_services.get_equipment(db, equipment_id)
        if not equipment: raise ValueError("العتاد غير موجود")
        unit = equipment.equipment_type.measurement_unit if equipment.equipment_type else "hours"
        reading = services.create_reading(db, equipment_id=equipment_id, odometer=meter_value if unit == "km" else None, hours=meter_value if unit == "hours" else None, reading_date=date_value, notes=notes, equipment_status=equipment_status or "available")
        op = create_operation(db, kind="manual", user_id=getattr(current_user, "id", None), equipment_id=equipment_id, total_rows=1, reading_ids=[reading.id], rejected_rows=0)
        record_changes_for_readings(db, [reading.id], getattr(current_user, "id", None), operation_id=op.id, source="manual")
        db.commit()
    except ValueError as exc:
        db.rollback(); raise HTTPException(status_code=400, detail=str(exc))
    except SQLAlchemyError:
        db.rollback(); raise HTTPException(status_code=500, detail="تعذر حفظ القراءة بسبب خطأ في قاعدة البيانات.")
    return JSONResponse({"ok": True, "message": "تم حفظ القراءة بنجاح", "reading_id": reading.id})


def _prepare_paste_rows(raw_rows):
    valid_rows, parse_errors = [], []
    for index, row in enumerate(raw_rows, start=1):
        if not isinstance(row, dict): parse_errors.append(f"الصف {index}: بيانات غير صحيحة."); continue
        try:
            valid_rows.append({"equipment_type": row.get("equipment_type"), "registration": row.get("registration"), "reading_date": _parse_date(row.get("reading_date")), "km_value": _parse_decimal(row.get("km_value")) if row.get("km_value") not in (None, "") else None, "hours_value": _parse_decimal(row.get("hours_value")) if row.get("hours_value") not in (None, "") else None, "value": _parse_decimal(row.get("value")) if row.get("value") not in (None, "") else None, "equipment_status": row.get("equipment_status"), "_row_number": index})
        except ValueError as exc: parse_errors.append(f"الصف {index}: {exc}")
    return valid_rows, parse_errors


@router.post("/bulk-create")
def meter_readings_bulk_create(payload: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    raw_rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(raw_rows, list): raise HTTPException(status_code=400, detail="بيانات اللصق غير صحيحة.")
    valid_rows, parse_errors = _prepare_paste_rows(raw_rows)
    try:
        created, rejected, service_errors, warnings, reading_ids = services.create_bulk_readings(db, valid_rows)
        errors = parse_errors + service_errors; rejected_total = len(raw_rows) - created
        if raw_rows: _finish_operation(db, current_user, "paste", None, len(raw_rows), reading_ids, rejected_total, errors, warnings)
    except SQLAlchemyError:
        db.rollback(); return JSONResponse(status_code=500, content={"created": 0, "skipped": len(raw_rows), "errors": [_error_card("تعذر حفظ القراءات بسبب خطأ في قاعدة البيانات.")]})
    cards = [_error_card(x) for x in errors[:100]] + [_warning_card(x) for x in warnings[:100]]
    return JSONResponse({"ok": not errors, "created": created, "skipped": rejected_total, "errors": cards, "message": "تم حفظ القراءات الصحيحة، مع وجود أخطاء تحتاج للمراجعة." if errors else "تم الحفظ بنجاح."})
