"""
web/main.py
------------
هذا الملف "تشغيل وربط فقط" كما هو مخطط له بالمعمارية: يُنشئ تطبيق FastAPI،
يسجّل كل راوترز الوحدات، ويقدّم الملفات الثابتة. لا يحتوي أي منطق عمل.

عند إضافة وحدة جديدة مستقبلًا (مثل fuel أو maintenance)، الإضافة هنا تكون
سطرين فقط: import + include_router. هذا هو المكان الوحيد الذي يحتاج تعديل
عند إضافة وحدة جديدة (بالإضافة لتسجيل الموديل في database/init_db.py).
"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.database.init_db import init_db, create_default_admin

# --- راوترز الوحدات ---
from app.modules.users.router import router as users_router
from app.modules.equipment.router import router as equipment_router
from app.modules.dashboard.router import router as dashboard_router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

    app.mount("/static", StaticFiles(directory="static"), name="static")

    # تسجيل كل وحدة براوترها الخاص - بدون prefix مشترك حاليًا لإبقاء المسارات
    # بسيطة (/equipment بدل /api/v1/equipment/equipment). يمكن لاحقًا إضافة
    # prefix موحّد لكل الـ API عند الحاجة دون التأثير على بقية الوحدات.
    app.include_router(users_router, tags=["users"])
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
