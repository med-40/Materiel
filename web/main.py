from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.database.init_db import init_db, create_default_admin

from app.modules.users.router import router as users_router
from app.modules.equipment_types.router import router as equipment_types_router
from app.modules.equipment.router import router as equipment_router
from app.modules.dashboard.router import router as dashboard_router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

    app.mount("/static", StaticFiles(directory="static"), name="static")

    app.include_router(users_router, tags=["users"])
    app.include_router(equipment_types_router, tags=["equipment_types"])
    app.include_router(equipment_router, tags=["equipment"])
    app.include_router(dashboard_router, tags=["dashboard"])

    @app.on_event("startup")
    def on_startup():
        init_db()
        create_default_admin()

    @app.get("/")
    def root():
        return RedirectResponse(url="/dashboard")

    return app


app = create_app()
