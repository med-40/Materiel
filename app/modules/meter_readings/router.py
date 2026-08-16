from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from html import escape

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from openpyxl import load_workbook
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.templating import get_module_templates
from app.database.session import get_db
from app.modules.equipment import services as equipment_services
from app.modules.equipment_types import services as type_services
from app.modules.meter_readings import services
from app.modules.users.models import User

router = APIRouter(prefix="/meter-readings", tags=["Meter Readings"])
templates = get_module_templates("app/modules/meter_readings/templates")


def _parse_type_id(value: str | None) -> Optional[int]:
    if value is None or not str(value).strip():
        return None
    try:
        parsed = int(str(value).strip())
    except (ValueError, TypeError):
        return None
    return parsed if parsed > 0 else None


def _parse_decimal(value):
    if value is None or str(value).strip() == "":
        raise ValueError("قيمة العداد فارغة")
    text = str(value).strip().replace(",", "")
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    text = text.replace("٫", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("قيمة العداد غير صحيحة") from exc


def _parse_date(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError("تاريخ القراءة غير صحيح")


def _error_card(message: str, title: str = "خطأ في البيانات"):
    safe = escape(str(message))
    return (
        f'<div style="display:flex;gap:10px;align-items:flex-start;margin:8px 0;padding:10px 12px;'
        f'border:1px solid #fecaca;border-radius:9px;background:#fff1f2;color:#991b1b;">'
        f'<span style="font-size:25px;line-height:1">⚠️</span>'
        f'<div><strong style="font-size:14px;display:block;margin-bottom:3px">{escape(title)}</strong>'
        f'<span style="font-size:13px">{safe}</span></div></div>'
    )


def _page_context(request, db, current_user, page, page_size, search, type_id, unit, sort):
    rows, total, pages, last_update = services.list_latest_rows(
        db, page=page, page_size=page_size, search=search, type_id=type_id, unit=unit, sort=sort
    )
    return {
        "request": request,
        "user": current_user,
        "readings": rows,
        "equipment_options": equipment_services.list_equipment(db, limit=10000),
        "types": type_services.list_types(db),
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "search": search,
        "type_id": type_id,
        "unit": unit,
        "sort": sort,
        "last_update": last_update,
    }


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def meter_readings_page(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=5, le=100), search: str = Query(""), type_id: str | None = Query(default=None), unit: str = Query(""), sort: str = Query("date_desc"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("meter_readings.html", _page_context(request, db, current_user, page, page_size, search, _parse_type_id(type_id), unit, sort))


@router.post("/create")
def meter_reading_create(equipment_id: int = Form(...), reading_date: str = Form(...), value: str = Form(...), notes: str = Form(""), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        date_value = _parse_date(reading_date)
        meter_value = _parse_decimal(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    equipment = equipment_services.get_equipment(db, equipment_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="العتاد غير موجود")

    unit = equipment.equipment_type.measurement_unit if equipment.equipment_type else "hours"
    try:
        services.create_reading(
            db,
            equipment_id=equipment_id,
            odometer=meter_value if unit == "km" else None,
            hours=meter_value if unit == "hours" else None,
            reading_date=date_value,
            notes=notes,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except SQLAlchemyError as exc:
        db.rollback()
        # لا نترك FastAPI يعرض 500 عامًا؛ أرسل سبب فشل قاعدة البيانات للواجهة
        # حتى يستطيع المستخدم/المطور معرفة الخطأ الحقيقي، مع عدم حفظ أي جزء من القراءة.
        detail = str(getattr(exc, "orig", None) or exc)
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": "تعذر حفظ القراءة بسبب خطأ في قاعدة البيانات.",
                "errors": [_error_card(detail, "خطأ في قاعدة البيانات")],
            },
        )
    except Exception as exc:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": "تعذر حفظ القراءة بسبب خطأ غير متوقع.",
                "errors": [_error_card(str(exc), "خطأ غير متوقع")],
            },
        )

    return JSONResponse({"ok": True, "message": "تم حفظ القراءة بنجاح"})


@router.post("/bulk-create")
def meter_readings_bulk_create(payload: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    raw_rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(raw_rows, list):
        raise HTTPException(status_code=400, detail="بيانات اللصق غير صحيحة.")
    valid_rows, parse_errors = [], []
    for index, row in enumerate(raw_rows, start=1):
        if not isinstance(row, dict):
            parse_errors.append(_error_card(f"الصف {index}: بيانات غير صحيحة."))
            continue
        try:
            valid_rows.append({"registration": row.get("registration"), "reading_date": _parse_date(row.get("reading_date")), "km_value": _parse_decimal(row.get("km_value")) if row.get("km_value") not in (None, "") else None, "hours_value": _parse_decimal(row.get("hours_value")) if row.get("hours_value") not in (None, "") else None, "notes": row.get("notes", ""), "_row_number": index})
        except ValueError as exc:
            parse_errors.append(_error_card(f"الصف {index}: {exc}"))
    if parse_errors:
        return JSONResponse(status_code=400, content={"created": 0, "skipped": len(raw_rows), "errors": parse_errors[:100], "message": "لم يتم حفظ أي صف لأن البيانات تحتوي على أخطاء. صحح الأخطاء ثم أعد المحاولة."})
    try:
        created, skipped, service_errors = services.create_bulk_readings(db, valid_rows)
    except SQLAlchemyError as exc:
        db.rollback()
        detail = str(getattr(exc, "orig", None) or exc)
        return JSONResponse(status_code=500, content={"created": 0, "skipped": len(valid_rows), "errors": [_error_card(detail, "خطأ في قاعدة البيانات")], "message": "تعذر حفظ القراءات بسبب خطأ في قاعدة البيانات. لم يتم حفظ أي صف."})
    errors = [_error_card(x) for x in service_errors]
    status_code = 400 if errors else 200
    return JSONResponse(status_code=status_code, content={"created": created, "skipped": skipped, "errors": errors[:100], "message": "لم يتم حفظ أي قراءة بسبب وجود أخطاء. صححها ثم أعد المحاولة." if errors else "تم الحفظ بنجاح."})


@router.post("/import-excel")
def meter_readings_import_excel(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        return JSONResponse(status_code=400, content={"created": 0, "skipped": 0, "errors": [_error_card("الملف يجب أن يكون بصيغة Excel .xlsx.")]})
    try:
        workbook = load_workbook(file.file, read_only=True, data_only=True)
        sheet = workbook.active
        rows_iter = sheet.iter_rows(values_only=True)
        preview = []
        for row_number, values in enumerate(rows_iter, start=1):
            preview.append((row_number, values))
            if row_number >= 30:
                break

        def normalize_header(value):
            if value is None:
                return ""
            text = str(value).strip().lower()
            for old, new in {"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"}.items():
                text = text.replace(old, new)
            return "".join(ch for ch in text if ch.isalnum())

        def find_header(headers, *aliases):
            aliases_normalized = {normalize_header(alias) for alias in aliases}
            for idx, header in enumerate(headers):
                if normalize_header(header) in aliases_normalized:
                    return idx
            return None

        header_info = None
        for row_number, values in preview:
            registration_idx = find_header(values, "رقم التسجيل", "التسجيل", "registration", "registration number", "immatriculation", "matricule", "reg")
            date_idx = find_header(values, "التاريخ", "تاريخ القراءة", "reading date", "date", "reading_date")
            km_idx = find_header(values, "الكيلومترات", "كيلومترات", "الكلم", "كلم", "عداد الكلم", "عداد الكيلومترات", "كم", "km", "kilometers", "kilometres", "odometer")
            hours_idx = find_header(values, "الساعات", "ساعات", "ساعة", "عداد الساعات", "عداد ساعة", "hours", "hour meter", "hourmeter")
            legacy_value_idx = find_header(values, "القراءة", "قيمة العداد", "reading", "value", "meter", "meter reading")
            if registration_idx is not None and date_idx is not None and (km_idx is not None or hours_idx is not None or legacy_value_idx is not None):
                header_info = (row_number, registration_idx, date_idx, km_idx, hours_idx, legacy_value_idx)
                break

        if header_info is None:
            raise ValueError("لم يتم التعرف على صف عناوين Excel. يجب أن يحتوي صف العناوين على: رقم التسجيل، التاريخ، الكيلومترات و/أو الساعات، والملاحظات.")

        header_row, registration_idx, date_idx, km_idx, hours_idx, legacy_value_idx = header_info
        header_values = next(values for number, values in preview if number == header_row)
        notes_idx = find_header(header_values, "الملاحظات", "ملاحظات", "notes", "note")
        import_rows, parse_errors = [], []

        def process_row(row_number, values):
            if not any(value is not None and str(value).strip() for value in values):
                return
            registration = values[registration_idx] if registration_idx < len(values) else None
            raw_date = values[date_idx] if date_idx < len(values) else None
            raw_km = values[km_idx] if km_idx is not None and km_idx < len(values) else None
            raw_hours = values[hours_idx] if hours_idx is not None and hours_idx < len(values) else None
            raw_legacy = values[legacy_value_idx] if legacy_value_idx is not None and legacy_value_idx < len(values) else None
            notes = values[notes_idx] if notes_idx is not None and notes_idx < len(values) else ""
            try:
                import_rows.append({"registration": registration, "reading_date": _parse_date(raw_date), "km_value": _parse_decimal(raw_km) if raw_km not in (None, "") else None, "hours_value": _parse_decimal(raw_hours) if raw_hours not in (None, "") else None, "value": _parse_decimal(raw_legacy) if raw_legacy not in (None, "") else None, "notes": notes or "", "_row_number": row_number})
            except ValueError as exc:
                parse_errors.append(_error_card(f"صف Excel {row_number}: {exc}"))

        for row_number, values in preview:
            if row_number > header_row:
                process_row(row_number, values)
        preview_last = preview[-1][0] if preview else 0
        for row_number, values in enumerate(rows_iter, start=preview_last + 1):
            process_row(row_number, values)

        if parse_errors:
            return JSONResponse(status_code=400, content={"created": 0, "skipped": len(import_rows) + len(parse_errors), "errors": parse_errors[:100], "message": "لم يتم حفظ أي صف لأن الملف يحتوي على أخطاء. صحح الأخطاء الظاهرة ثم أعد الاستيراد."})

        try:
            created, skipped, service_errors = services.create_bulk_readings(db, import_rows)
        except SQLAlchemyError as exc:
            db.rollback()
            detail = str(getattr(exc, "orig", None) or exc)
            return JSONResponse(status_code=500, content={"created": 0, "skipped": len(import_rows), "errors": [_error_card(detail, "خطأ في قاعدة البيانات")], "message": "تعذر استيراد القراءات بسبب خطأ في قاعدة البيانات. لم يتم حفظ أي صف."})
        errors = [_error_card(x) for x in service_errors]
        status_code = 400 if errors else 200
        return JSONResponse(status_code=status_code, content={"created": created, "skipped": skipped, "errors": errors[:100], "message": "لم يتم حفظ أي قراءة بسبب وجود أخطاء. صحح الأخطاء الظاهرة ثم أعد الاستيراد." if errors else "تم استيراد القراءات بنجاح."})
    except ValueError as exc:
        db.rollback()
        return JSONResponse(status_code=400, content={"created": 0, "skipped": 0, "errors": [_error_card(str(exc))]})
    except Exception as exc:
        db.rollback()
        return JSONResponse(status_code=400, content={"created": 0, "skipped": 0, "errors": [_error_card(f"تعذر قراءة ملف Excel: {exc}", "تعذر قراءة ملف Excel")]})


@router.get("/history/{equipment_id}", response_class=HTMLResponse)
def meter_history_page(equipment_id: int, request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=5, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    equipment, rows, total, pages, page = services.history_rows(db, equipment_id, page=page, page_size=page_size)
    if not equipment:
        raise HTTPException(status_code=404, detail="العتاد غير موجود")
    return templates.TemplateResponse("meter_readings_list.html", {"request": request, "user": current_user, "equipment": equipment, "rows": rows, "total": total, "pages": pages, "page": page, "page_size": page_size})
