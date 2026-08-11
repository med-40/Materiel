from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import Role, require_role
from app.core.templating import get_module_templates
from app.database.session import get_db

from app.modules.equipment import services as equipment_services
from app.modules.equipment_types import services as type_services
from app.modules.maintenance import services
from app.modules.notifications import services as notifications_services
from app.modules.users.models import User


router = APIRouter()

templates = get_module_templates(
    "app/modules/maintenance/templates"
)


notifications_services.register_provider(
    services.get_maintenance_notifications
)


# =========================================================
# الصفحة الرئيسية للصيانة
# =========================================================

@router.get("/maintenance", response_class=HTMLResponse)
def maintenance_hub(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifications = notifications_services.get_all_notifications(db)

    return templates.TemplateResponse(
        "maintenance_hub.html",
        {
            "request": request,
            "notifications": notifications,
            "user": current_user,
        },
    )


# =========================================================
# التصليحات
# =========================================================

@router.get(
    "/maintenance/repairs",
    response_class=HTMLResponse,
)
def maintenance_repairs_placeholder(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "maintenance_placeholder.html",
        {
            "request": request,
            "user": current_user,
            "section_title": "التصليحات",
        },
    )


# =========================================================
# يوم الحضيرة
# =========================================================

@router.get(
    "/maintenance/depot-day",
    response_class=HTMLResponse,
)
def maintenance_depot_day_placeholder(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "maintenance_placeholder.html",
        {
            "request": request,
            "user": current_user,
            "section_title": "يوم الحضيرة",
        },
    )


# =========================================================
# مخطط الصيانة السنوي
# =========================================================

@router.get(
    "/maintenance/annual-plan",
    response_class=HTMLResponse,
)
def maintenance_annual_plan_placeholder(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "maintenance_placeholder.html",
        {
            "request": request,
            "user": current_user,
            "section_title": "مخطط الصيانة السنوي",
        },
    )


# =========================================================
# التفتيشات الدورية
# =========================================================

@router.get(
    "/maintenance/inspections",
    response_class=HTMLResponse,
)
def maintenance_inspections_placeholder(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "maintenance_placeholder.html",
        {
            "request": request,
            "user": current_user,
            "section_title": "التفتيشات الدورية",
        },
    )


# =========================================================
# الصيانة الدورية
# =========================================================

@router.get(
    "/maintenance/periodic",
    response_class=HTMLResponse,
)
def maintenance_periodic_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    open_records = services.list_open_records(db)

    equipment_list = equipment_services.list_equipment(db)

    # أنواع الصيانة التي أنشأها مدير النظام
    maintenance_types = services.list_maintenance_types(db)

    return templates.TemplateResponse(
        "maintenance_list.html",
        {
            "request": request,
            "records": open_records,
            "equipment_list": equipment_list,
            "maintenance_types": maintenance_types,
            "user": current_user,
        },
    )


# =========================================================
# الصيانات المستحقة لعتاد معين
# =========================================================

@router.get(
    "/maintenance/{equipment_id}/due",
    response_class=HTMLResponse,
)
def maintenance_due_for_equipment(
    request: Request,
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    equipment = equipment_services.get_equipment(
        db,
        equipment_id,
    )

    if not equipment:
        raise HTTPException(
            status_code=404,
            detail="العتاد غير موجود",
        )

    due_schedules = services.get_due_schedules_for_equipment(
        db,
        equipment_id,
    )

    return templates.TemplateResponse(
        "maintenance_due.html",
        {
            "request": request,
            "equipment": equipment,
            "due_schedules": due_schedules,
            "user": current_user,
        },
    )


# =========================================================
# فتح أمر صيانة
# =========================================================

@router.post("/maintenance/create")
def maintenance_create_form(
    request: Request,

    equipment_id: int = Form(...),

    maintenance_type_id: int = Form(...),

    reported_date: date = Form(...),

    maintenance_schedule_id: Optional[str] = Form(None),

    description: str = Form(""),

    db: Session = Depends(get_db),

    current_user: User = Depends(get_current_user),
):
    try:

        schedule_id = (
            int(maintenance_schedule_id)
            if maintenance_schedule_id
            else None
        )

        services.create_maintenance_record(
            db,

            equipment_id=equipment_id,

            reported_date=reported_date,

            maintenance_schedule_id=schedule_id,

            maintenance_type_id=maintenance_type_id,

            description=description or None,
        )

    except ValueError:
        pass

    return RedirectResponse(
        url="/maintenance/periodic",
        status_code=status.HTTP_302_FOUND,
    )


# =========================================================
# إغلاق أمر الصيانة
# =========================================================

@router.post(
    "/maintenance/{record_id}/close"
)
def maintenance_close_form(
    record_id: int,

    resolved_date: date = Form(...),

    meter_reading: str = Form(""),

    resolution_notes: str = Form(""),

    performed_by: str = Form(""),

    location: str = Form(""),

    db: Session = Depends(get_db),

    current_user: User = Depends(get_current_user),
):
    record = services.complete_maintenance_record(
        db,

        record_id,

        resolved_date=resolved_date,

        meter_reading=(
            Decimal(meter_reading)
            if meter_reading
            else None
        ),

        resolution_notes=(
            resolution_notes
            if resolution_notes
            else None
        ),

        performed_by=(
            performed_by
            if performed_by
            else None
        ),

        location=(
            location
            if location
            else None
        ),
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="سجل الصيانة غير موجود",
        )

    return RedirectResponse(
        url="/maintenance/periodic",
        status_code=status.HTTP_302_FOUND,
    )


# =========================================================
# إعدادات الصيانة
# =========================================================

@router.get(
    "/maintenance/settings",
    response_class=HTMLResponse,
)
def maintenance_settings_page(
    request: Request,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(Role.ADMIN)
    ),
):
    maintenance_types = services.list_maintenance_types(
        db
    )

    equipment_types = type_services.list_types(
        db
    )

    return templates.TemplateResponse(
        "maintenance
