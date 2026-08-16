from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from html import escape

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.templating import get_module_templates
from app.database.session import get_db
from app.modules.equipment import services as equipment_services
from app.modules.equipment_types import services as type_services
from app.modules.meter_readings import services
from app.modules.meter_readings.audit_service import add_validation_details, create_operation
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
    text = str(value).strip().replace(" ", "").replace(",", "")
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
    if isinstance(value, (int, float)):
        try:
            parsed = from_excel(value)
            if isinstance(parsed, datetime):
                return parsed
            if isinstance(parsed, date):
                return datetime.combine(parsed, datetime.min.time())
        except Exception:
            pass
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
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


def _warning_card(message: str):
    safe = escape(str(message))
    return (
        f'<div style="display:flex;gap:10px;align-items:flex-start;margin:8px 0;padding:10px 12px;'
        f'border:1px solid #fde68a;border-radius:9px;background:#fffbeb;color:#92400e;">'
        f'<span style="font-size:25px;line-height:1">⚠️</span>'
        f'<div><strong style="font-size:14px;display:block;margin-bottom:3px">تنبيه</strong>'
        f'<span style="font-size:13px">{safe}</span></div></div>'
    )


def _page_context(request, db, current_user, page, page_size, search, type_id, unit, sort):
    rows, total, pages, last_update = services.list_latest_rows(
        db, page=page, page_size=page_size, search=search, type_id=type_id, unit=unit, sort=sort
    )
    return {
        "request": request, "user": current_user, "readings": rows,
        "equipment_options": equipment_services.list_equipment(db, limit=10000),
        "types": type_services.list_types(db), "total": total, "page": page,
        "page_size": page_size, "pages": pages, "search": search, "type_id": type_id,
        "unit": unit, "sort": sort, "last_update": last_update,
    }


def _finish_operation(db: Session, current_user: User, kind: str, filename: str | None, total_rows: int,
                      reading_ids: list[int], rejected_rows: int, errors: list[str], warnings: list[str]):
    op = create_operation(
        db, kind=kind, user_id=getattr(current_user, "id", None), filename=filename,
        total_rows=total_rows, reading_ids=reading_ids, rejected_rows=rejected_rows,
    )
    add_validation_details(db, op.id, getattr(current_user, "id", None), errors=errors, warnings=warnings)
    db.commit()
    return op


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def meter_readings_page(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=5, le=100), search: str = Query(""), type_id: str | None = Query(default=None), unit: str = Query(""), sort: str = Query("date_desc"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        "meter_readings.html",
        _page_context(request, db, current_user, page, page_size, search, _parse_type_id(type_id), unit, sort),
    )


@router.post("/create")
def meter_reading_create(equipment_id: int = Form(...), reading_date: str = Form(...), value: str = Form(...), equipment_status: str = Form("available"), notes: str = Form(""), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
        reading = services.create_reading(
            db, equipment_id=equipment_id,
            odometer=meter_value if unit == "km" else None,
            hours=meter_value if unit == "hours" else None,
            reading_date=date_value, notes=notes, equipment_status=equipment_status,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except SQLAlchemyError as exc:
        db.rollback()
        detail = str(getattr(exc, "orig", None) or exc)
        return JSONResponse(status_code=500, content={"ok": False, "message": "تعذر حفظ القراءة بسبب خطأ في قاعدة البيانات.", "errors": [_error_card(detail, "خطأ في قاعدة البيانات")]})
    except Exception as exc:
        db.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "message": "تعذر حفظ القراءة بسبب خطأ غير متوقع.", "errors": [_error_card(str(exc), "خطأ غير متوقع")]})
    return JSONResponse({"ok": True, "message": "تم حفظ القراءة بنجاح", "reading_id": reading.id})


def _prepare_paste_rows(raw_rows):
    valid_rows, parse_errors = [], []
    for index, row in enumerate(raw_rows, start=1):
        if not isinstance(row, dict):
            parse_errors.append(f"الصف {index}: بيانات غير صحيحة.")
            continue
        try:
            valid_rows.append({
                "registration": row.get("registration"),
                "reading_date": _parse_date(row.get("reading_date")),
                "km_value": _parse_decimal(row.get("km_value")) if row.get("km_value") not in (None, "") else None,
                "hours_value": _parse_decimal(row.get("hours_value")) if row.get("hours_value") not in (None, "") else None,
                "value": _parse_decimal(row.get("value")) if row.get("value") not in (None, "") else None,
                "notes": row.get("notes", ""),
                "equipment_status": row.get("equipment_status", "available"),
                "_row_number": index,
            })
        except ValueError as exc:
            parse_errors.append(f"الصف {index}: {exc}")
    return valid_rows, parse_errors


@router.post("/bulk-create")
def meter_readings_bulk_create(payload: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    raw_rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(raw_rows, list):
        raise HTTPException(status_code=400, detail="بيانات اللصق غير صحيحة.")
    equipment_status = payload.get("equipment_status", "available")
    valid_rows, parse_errors = _prepare_paste_rows(raw_rows)
    try:
        created, rejected, service_errors, warnings, reading_ids = services.create_bulk_readings(
            db, [{**row, "equipment_status": equipment_status} for row in valid_rows]
        )
        errors = parse_errors + service_errors
        rejected_total = len(raw_rows) - created
        if raw_rows:
            _finish_operation(db, current_user, "paste", None, len(raw_rows), reading_ids, rejected_total, errors, warnings)
    except SQLAlchemyError as exc:
        db.rollback()
        detail = str(getattr(exc, "orig", None) or exc)
        return JSONResponse(status_code=500, content={"created": 0, "skipped": len(raw_rows), "errors": [_error_card(detail, "خطأ في قاعدة البيانات")], "message": "تعذر حفظ القراءات بسبب خطأ في قاعدة البيانات."})
    cards = [_error_card(x) for x in errors[:100]] + [_warning_card(x) for x in warnings[:100]]
    return JSONResponse(status_code=200, content={
        "ok": not errors, "created": created, "skipped": rejected_total, "errors": cards,
        "message": "تم حفظ القراءات الصحيحة، مع وجود أخطاء تحتاج للمراجعة." if errors else "تم الحفظ بنجاح.",
        "operation_id": None,
    })


@router.post("/import-excel")
def meter_readings_import_excel(file: UploadFile = File(...), equipment_status: str = Form("available"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        return JSONResponse(status_code=400, content={"created": 0, "skipped": 0, "errors": [_error_card("الملف يجب أن يكون بصيغة Excel .xlsx.")]})
    try:
        workbook = load_workbook(file.file, read_only=True, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            raise ValueError("ملف Excel فارغ.")

        def normalize_header(value):
            if value is None:
                return ""
            text = str(value).strip().lower()
            for old, new in {"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي", "ـ": "", "ٱ": "ا", "ؤ": "و", "ئ": "ي"}.items():
                text = text.replace(old, new)
            return "".join(ch for ch in text if ch.isalnum())

        def header_kind(value):
            text = normalize_header(value)
            if not text:
                return None
            exact = {
                "رقمالتسجيل": "registration", "التسجيل": "registration", "registration": "registration",
                "registrationnumber": "registration", "immatriculation": "registration", "matricule": "registration", "reg": "registration",
                "التاريخ": "date", "تاريخالقراءه": "date", "تاريخالقراءة": "date", "readingdate": "date", "date": "date", "reading_date": "date",
                "الملاحظات": "notes", "ملاحظات": "notes", "notes": "notes", "note": "notes",
                "الكيلومترات": "km", "كيلومترات": "km", "الكيلومتر": "km", "كيلومتر": "km", "الكم": "km", "الكلم": "km", "كلم": "km", "عدادالكلم": "km", "عدادالكيلومترات": "km", "عدادالكيلومتر": "km", "عدادالكم": "km", "كم": "km", "km": "km", "kilometers": "km", "kilometres": "km", "odometer": "km", "odometre": "km",
                "الساعات": "hours", "ساعات": "hours", "ساعة": "hours", "عدادالساعات": "hours", "عدادساعة": "hours", "hours": "hours", "hour": "hours", "hourmeter": "hours", "hourmeterreading": "hours",
                "القراءة": "legacy", "قيمهالعداد": "legacy", "قيمةالعداد": "legacy", "reading": "legacy", "value": "legacy", "meter": "legacy", "meterreading": "legacy",
            }
            if text in exact:
                return exact[text]
            if "تسجيل" in text or "registration" in text or "immatriculation" in text or "matricule" in text: return "registration"
            if "تاريخ" in text or text.endswith("date") or "readingdate" in text: return "date"
            if "كيلو" in text or "كلم" in text or "odometer" in text or text.endswith("km"): return "km"
            if "ساع" in text or "hour" in text: return "hours"
            if "ملاحظ" in text or "note" in text: return "notes"
            if "قراء" in text or "value" in text or "meter" in text: return "legacy"
            return None

        header_info = None
        for row_number, values in enumerate(rows[:20], start=1):
            kinds = {}
            for idx, value in enumerate(values):
                kind = header_kind(value)
                if kind and kind not in kinds:
                    kinds[kind] = idx
            if "registration" in kinds and "date" in kinds and ("km" in kinds or "hours" in kinds or "legacy" in kinds):
                header_info = (row_number, kinds)
                break
        if header_info is None:
            raise ValueError("لم يتم التعرف على عناوين Excel. يجب أن يحتوي الملف على رقم التسجيل والتاريخ وعمود العداد المناسب.")

        header_row, columns = header_info
        registration_idx = columns["registration"]
        date_idx = columns["date"]
        km_idx = columns.get("km")
        hours_idx = columns.get("hours")
        legacy_value_idx = columns.get("legacy")
        notes_idx = columns.get("notes")
        import_rows, parse_errors = [], []
        previous_registration = None
        data_row_count = 0

        def cell(values, idx):
            return values[idx] if idx is not None and idx < len(values) else None

        for row_number, values in enumerate(rows[header_row:], start=header_row + 1):
            if not any(value is not None and str(value).strip() for value in values):
                continue
            data_row_count += 1
            registration = cell(values, registration_idx)
            if registration is None or str(registration).strip() == "":
                registration = previous_registration
            else:
                previous_registration = registration
            raw_date = cell(values, date_idx)
            raw_km = cell(values, km_idx)
            raw_hours = cell(values, hours_idx)
            raw_legacy = cell(values, legacy_value_idx)
            notes = cell(values, notes_idx) or ""
            try:
                if registration is None or str(registration).strip() == "":
                    raise ValueError("رقم التسجيل فارغ.")
                import_rows.append({
                    "registration": registration,
                    "reading_date": _parse_date(raw_date),
                    "km_value": _parse_decimal(raw_km) if raw_km not in (None, "") else None,
                    "hours_value": _parse_decimal(raw_hours) if raw_hours not in (None, "") else None,
                    "value": _parse_decimal(raw_legacy) if raw_legacy not in (None, "") else None,
                    "notes": notes, "equipment_status": equipment_status, "_row_number": row_number,
                })
            except ValueError as exc:
                parse_errors.append(f"صف Excel {row_number}: {exc}")

        created, rejected, service_errors, warnings, reading_ids = services.create_bulk_readings(db, import_rows)
        errors = parse_errors + service_errors
        rejected_total = data_row_count - created
        op = None
        if data_row_count:
            op = _finish_operation(db, current_user, "excel", filename, data_row_count, reading_ids, rejected_total, errors, warnings)
        cards = [_error_card(x) for x in errors[:100]] + [_warning_card(x) for x in warnings[:100]]
        return JSONResponse(status_code=200, content={
            "ok": not errors, "created": created, "skipped": rejected_total, "errors": cards,
            "message": "تم استيراد القراءات الصحيحة، مع وجود أخطاء تحتاج للمراجعة." if errors else "تم استيراد القراءات بنجاح.",
            "operation_id": op.id if op else None,
        })
    except ValueError as exc:
        db.rollback()
        return JSONResponse(status_code=400, content={"created": 0, "skipped": 0, "errors": [_error_card(str(exc))]})
    except SQLAlchemyError as exc:
        db.rollback()
        detail = str(getattr(exc, "orig", None) or exc)
        return JSONResponse(status_code=500, content={"created": 0, "skipped": data_row_count if 'data_row_count' in locals() else 0, "errors": [_error_card(detail, "خطأ في قاعدة البيانات")]})
    except Exception as exc:
        db.rollback()
        return JSONResponse(status_code=400, content={"created": 0, "skipped": 0, "errors": [_error_card(f"تعذر قراءة ملف Excel: {exc}", "تعذر قراءة ملف Excel")]})


@router.get("/history/{equipment_id}", response_class=HTMLResponse)
def meter_history_page(equipment_id: int, request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=5, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    equipment, rows, total, pages, page = services.history_rows(db, equipment_id, page=page, page_size=page_size)
    if not equipment:
        raise HTTPException(status_code=404, detail="العتاد غير موجود")
    return templates.TemplateResponse(
        "meter_readings_list.html",
        {"request": request, "user": current_user, "equipment": equipment, "rows": rows, "total": total, "pages": pages, "page": page, "page_size": page_size},
    )
