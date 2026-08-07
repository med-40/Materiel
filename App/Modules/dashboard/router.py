"""
modules/dashboard/router.py
------------------------------
لوحة التحكم لا تملك بياناتها الخاصة - هي فقط "تجمّع" مؤشرات من خدمات
الوحدات الأخرى (equipment الآن، وlaحقًا maintenance, fuel, faults...).
هذا يحافظ على مبدأ استقلالية الوحدات: dashboard يستدعي services الجاهزة
لكل وحدة، ولا يكتب استعلامات SQL خاصة به على جداول وحدات أخرى.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.templating import get_module_templates
from app.database.session import get_db
from app.modules.equipment import services as equipment_services
from app.modules.users.models import User

router = APIRouter()
templates = get_module_templates("app/modules/dashboard/templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    status_counts = equipment_services.count_by_status(db)
    total_equipment = sum(status_counts.values())

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "total_equipment": total_equipment,
            "status_counts": status_counts,
        },
    )
