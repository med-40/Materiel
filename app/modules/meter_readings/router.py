from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from openpyxl import load_workbook
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


def _page_context(request, db, current_user, page, page_size, search, type_id, unit, sort):
    rows, total, pages, last_update = services.list_latest_rows(db, page=page, page_size=page_size, search=search, type_id=type_id, unit=unit, sort=sort)
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
        services.create_reading(db, equipment_id=equipment_id, odometer=meter_value if unit == "km" else None, hours=meter_value if unit == "hours" else None, reading_date=date_value, notes=notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url="/meter-readings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/bulk-create")
def meter_readings_bulk_create(payload: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    raw_rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(raw_rows, list):
        raise HTTPException(status_code=400, detail="بيانات اللصق غير صحيحة.")
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
                "notes": row.get("notes", ""),
            })
        except ValueError as exc:
            parse_errors.append(f"الصف {index}: {exc}")
    created, skipped, service_errors = services.create_bulk_readings(db, valid_rows)
    return JSONResponse({"created": created, "skipped": skipped + len(parse_errors), "errors": (parse_errors + service_errors)[:100]})


@router.post("/import-excel")
def meter_readings_import_excel(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="الرجاء اختيار ملف Excel بصيغة .xlsx")
    try:
        workbook = load_workbook(file.file, read_only=True, data_only=True)
        sheet = workbook.active
        rows_iter = sheet.iter_rows(values_only=True)
        headers = next(rows_iter, None)
        if not headers:
            raise ValueError("ملف Excel فارغ.")

        def normalize_header(value):
            if value is None:
                return ""
            text = str(value).strip().lower()
            for old, new in {"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"}.items():
                text = text.replace(old, new)
            return "".join(ch for ch in text if ch.isalnum())

        normalized_headers = [normalize_header(h) for h in headers]

        def find_header(*aliases):
            aliases_normalized = {normalize_header(alias) for alias in aliases}
            for idx, header in enumerate(normalized_headers):
                if header in aliases_normalized:
                    return idx
            return None

        registration_idx = find_header("رقم التسجيل", "التسجيل", "registration", "registration number", "immatriculation", "matricule", "reg")
        date_idx = find_header("التاريخ", "تاريخ القراءة", "reading date", "date", "reading_date")
        km_idx = find_header("الكيلومترات", "كيلومترات", "كم", "km", "kilometers", "kilometres", "odometer")
        hours_idx = find_header("الساعات", "ساعات", "ساعة", "hours", "hour meter", "hourmeter")
        notes_idx = find_header("الملاحظات", "ملاحظات", "notes", "note")
        legacy_value_idx = find_header("القراءة", "قيمة العداد", "reading", "value", "meter", "meter reading")

        if registration_idx is None:
            raise ValueError("لم يتم العثور على عمود رقم التسجيل.")
        if date_idx is None:
            raise ValueError("لم يتم العثور على عمود التاريخ.")
        if km_idx is None and hours_idx is None and legacy_value_idx is None:
            raise ValueError("لم يتم العثور على عمود الكيلومترات أو الساعات.")

        import_rows, parse_errors = [], []
        for row_number, values in enumerate(rows_iter, start=2):
            if not any(value is not None and str(value).strip() for value in values):
                continue
            registration = values[registration_idx] if registration_idx < len(values) else None
            raw_date = values[date_idx] if date_idx < len(values) else None
            raw_km = values[km_idx] if km_idx is not None and km_idx < len(values) else None
            raw_hours = values[hours_idx] if hours_idx is not None and hours_idx < len(values) else None
            raw_legacy = values[legacy_value_idx] if legacy_value_idx is not None and legacy_value_idx < len(values) else None
            notes = values[notes_idx] if notes_idx is not None and notes_idx < len(values) else ""
            try:
                import_rows.append({
                    "registration": registration,
                    "reading_date": _parse_date(raw_date),
                    "km_value": _parse_decimal(raw_km) if raw_km not in (None, "") else None,
                    "hours_value": _parse_decimal(raw_hours) if raw_hours not in (None, "") else None,
                    "value": _parse_decimal(raw_legacy) if raw_legacy not in (None, "") else None,
                    "notes": notes or "",
                })
            except ValueError as exc:
                parse_errors.append(f"صف Excel {row_number}: {exc}")
        created, skipped, service_errors = services.create_bulk_readings(db, import_rows)
        return JSONResponse({"created": created, "skipped": skipped + len(parse_errors), "errors": (parse_errors + service_errors)[:100]})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"created": 0, "skipped": 0, "errors": [str(exc)]})
    except Exception as exc:
        return JSONResponse(status_code=400, content={"created": 0, "skipped": 0, "errors": [f"تعذر قراءة ملف Excel: {exc}"]})


@router.get("/history/{equipment_id}", response_class=HTMLResponse)
def meter_history_page(equipment_id: int, request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=5, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    equipment, rows, total, pages, page = services.history_rows(db, equipment_id, page=page, page_size=page_size)
    if not equipment:
        raise HTTPException(status_code=404, detail="العتاد غير موجود")
    return templates.TemplateResponse("meter_readings_list.html", {"request": request, "user": current_user, "equipment": equipment, "rows": rows, "total": total, "pages": pages, "page": page, "page_size": page_size})
