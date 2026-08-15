from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.templating import get_module_templates
from app.database.session import get_db
from app.modules.equipment import services as equipment_services
from app.modules.equipment_types import services as type_services
from app.modules.meter_readings import services
from app.modules.users.models import User


router = APIRouter(
    prefix="/meter-readings",
    tags=["Meter Readings"],
)

templates = get_module_templates("app/modules/meter_readings/templates")


def _page_context(
    request: Request,
    db: Session,
    current_user: User,
    page: int,
    page_size: int,
    search: str,
    type_id: Optional[int],
    unit: str,
    sort: str,
):
    rows, total, pages, last_update = services.list_latest_rows(
        db,
        page=page,
        page_size=page_size,
        search=search,
        type_id=type_id,
        unit=unit,
        sort=sort,
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
def meter_readings_page(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=5, le=100),
    search: str = Query(""),
    type_id: Optional[int] = Query(None),
    unit: str = Query(""),
    sort: str = Query("date_desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "meter_readings.html",
        _page_context(
            request,
            db,
            current_user,
            page,
            page_size,
            search,
            type_id,
            unit,
            sort,
        ),
    )


@router.post("/create")
def meter_reading_create(
    equipment_id: int = Form(...),
    reading_date: str = Form(...),
    value: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        date_value = datetime.strptime(reading_date, "%Y-%m-%d")
        meter_value = Decimal(value.strip())
    except (ValueError, InvalidOperation):
        raise HTTPException(status_code=400, detail="تاريخ أو قيمة عداد غير صحيحة")

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
        raise HTTPException(status_code=400, detail=str(exc))

    return RedirectResponse(
        url="/meter-readings",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/history/{equipment_id}", response_class=HTMLResponse)
def meter_history_page(
    equipment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    equipment, rows = services.history_rows(db, equipment_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="العتاد غير موجود")

    return templates.TemplateResponse(
        "meter_readings_list.html",
        {
            "request": request,
            "user": current_user,
            "equipment": equipment,
            "rows": rows,
        },
    )
