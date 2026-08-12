from app.database.base import Base
from app.database.session import engine

from app.modules.users import models as users_models                    # noqa: F401
from app.modules.equipment_types import models as equipment_types_models  # noqa: F401
from app.modules.equipment import models as equipment_models            # noqa: F401
from app.modules.maintenance import models as maintenance_models            # noqa: F401

from app.modules.meter_readings import models as meter_readings_models  # noqa: F401
from app.modules.odometer_readings import models as odometer_readings_models  # noqa: F401
from app.modules.hour_meter_readings import models as hour_meter_readings_models  # noqa: F401
def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def create_default_admin() -> None:
    from app.database.session import SessionLocal
    from app.modules.users.services import get_user_by_username, create_user
    from app.modules.users.schemas import UserCreate

    db = SessionLocal()
    try:
        existing = get_user_by_username(db, "admin")
        if not existing:
            create_user(
                db,
                UserCreate(
                    username="admin",
                    full_name="مدير النظام",
                    password="Admin@123",
                    role="admin",
                ),
            )
            print("[init_db] تم إنشاء مستخدم افتراضي: admin / Admin@123")
    finally:
        db.close()
