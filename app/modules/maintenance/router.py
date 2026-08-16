from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.core.dependencies import get_current_user
from app.core.templating import get_module_templates
from app.modules.users.models import User

router = APIRouter()
templates = get_module_templates("app/modules/maintenance/templates")


@router.get("/maintenance/periodic", response_class=HTMLResponse)
def periodic_maintenance_page(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "periodic_maintenance.html",
        {"request": request, "user": current_user},
    )
