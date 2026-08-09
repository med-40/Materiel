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


@router.post("/equipment/create")
def equipment_create_form(
    request: Request,
    asset_code: str = Form(...),
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
                asset_code=asset_code,
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


@router.post("/api/equipment", response_model=EquipmentOut, status_code=201)
def api_create_equipment(
    data: EquipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.FLEET_MANAGER)),
):
    try:
        return services.create_equipment(db, data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/api/equipment/{equipment_id}", response_model=EquipmentOut)
def api_update_equipment(
    equipment_id: int,
    data: EquipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.FLEET_MANAGER)),
):
    item = services.get_equipment(db, equipment_id)
    if not item:
        raise HTTPException(status_code=404, detail="العتاد غير موجود")
    return services.update_equipment(db, item, data, user_id=current_user.id)


@router.delete("/api/equipment/{equipment_id}", status_code=204)
def api_delete_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    item = services.get_equipment(db, equipment_id)
    if not item:
        raise HTTPException(status_code=404, detail="العتاد غير موجود")
    services.delete_equipment(db, item)
