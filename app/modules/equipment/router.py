from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import Role, require_role
from app.core.templating import get_module_templates
from app.database.session import get_db
from app.modules.equipment import services
from app.modules.equipment.schemas import EquipmentCreate, EquipmentOut, EquipmentUpdate
from app.modules.equipment_types import services as type_services
from app.modules.users.models import User
from app.modules.meter_readings import services as meter_services

router = APIRouter()
templates = get_module_templates("app/modules/equipment/templates")


@router.get("/equipment", response_class=HTMLResponse)
def equipment_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = services.list_equipment(db)
    types = type_services.list_types(db)
    return templates.TemplateResponse(
        "equipment_list.html",
        {"request": request, "items": items, "types": types, "user": current_user},
    )


@router.get("/equipment/{equipment_id}", response_class=HTMLResponse)
def equipment_detail_page(
    equipment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = services.get_equipment(db, equipment_id)

    if not item:
        raise HTTPException(status_code=404, detail="العتاد غير موجود")

    return templates.TemplateResponse(
        "equipment_detail.html",
        {
            "request": request,
            "item": item,
            "user": current_user,
        },
    )


@router.post("/equipment/create")
def equipment_create_form(
    request: Request,
    equipment_type_id: int = Form(...),
    equipment_model_id: Optional[str] = Form(None),
    acquisition_document: str = Form(""),
    registration_number: str = Form(""),
    vin: str = Form(""),
    current_odometer: str = Form("0"),
    current_hours: str = Form("0"),
    technical_condition: str = Form("ready"),
    operational_status: str = Form("available"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        services.create_equipment(
            db,
            EquipmentCreate(
                equipment_type_id=equipment_type_id,
                equipment_model_id=int(equipment_model_id) if equipment_model_id else None,
                acquisition_document=acquisition_document or None,
                registration_number=registration_number or None,
                vin=vin or None,
                current_odometer=current_odometer or 0,
                current_hours=current_hours or 0,
                technical_condition=technical_condition,
                operational_status=operational_status,
            ),
            user_id=current_user.id,
        )
    except ValueError:
        pass
    return RedirectResponse(url="/equipment", status_code=status.HTTP_302_FOUND)


@router.post("/equipment/{equipment_id}/delete")
def equipment_delete_form(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    item = services.get_equipment(db, equipment_id)
    if item:
        services.delete_equipment(db, item)
    return RedirectResponse(url="/equipment", status_code=status.HTTP_302_FOUND)



@router.get("/equipment/{equipment_id}/meters", response_class=HTMLResponse)
def equipment_meters_page(
    equipment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = services.get_equipment(db, equipment_id)

    if not item:
        raise HTTPException(status_code=404, detail="العتاد غير موجود")

    readings = meter_services.list_readings(db, equipment_id)

    return templates.TemplateResponse(
        "equipment_meters.html",
        {
            "request": request,
            "item": item,
            "readings": readings,
            "user": current_user,
        },
    )


@router.post("/equipment/{equipment_id}/meters/create")
def equipment_meter_create(
    equipment_id: int,
    reading_date: str = Form(...),
    odometer: str = Form(""),
    hours: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = services.get_equipment(db, equipment_id)

    if not item:
        raise HTTPException(status_code=404, detail="العتاد غير موجود")

    from datetime import datetime
    from decimal import Decimal

    odometer_value = Decimal(odometer) if odometer.strip() else None
    hours_value = Decimal(hours) if hours.strip() else None

    if odometer_value is None and hours_value is None:
        raise HTTPException(
            status_code=400,
            detail="يجب إدخال قراءة الكيلومترات أو قراءة الساعات"
        )

    reading = meter_services.create_reading(
        db,
        equipment_id=equipment_id,
        odometer=odometer_value,
        hours=hours_value,
    )

    reading.reading_date = datetime.strptime(reading_date, "%Y-%m-%d")
    reading.notes = notes or None

    if odometer_value is not None:
        item.current_odometer = odometer_value

    if hours_value is not None:
        item.current_hours = hours_value

    db.commit()

    return RedirectResponse(
        url=f"/equipment/{equipment_id}/meters",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/api/equipment", response_model=list[EquipmentOut])
def api_list_equipment(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return services.list_equipment(db)


@router.get("/api/equipment/{equipment_id}", response_model=EquipmentOut)
def api_get_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = services.get_equipment(db, equipment_id)
    if not item:
        raise HTTPException(status_code=404, detail="العتاد غير موجود")
    return item
