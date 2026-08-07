"""
database/init_db.py
--------------------
النقطة الوحيدة التي "تعرف" بكل الوحدات الموجودة في المشروع، لغرض واحد فقط:
استيراد موديلاتها حتى تُسجَّل في Base.metadata قبل استدعاء create_all().

عند إضافة وحدة جديدة مستقبلًا (مثل spare_parts)، الخطوة الوحيدة المطلوبة هنا
هي إضافة سطر استيراد واحد. هذا لا يخالف مبدأ استقلالية الوحدات، لأن هذا
الملف ليس جزءًا من منطق أي وحدة - هو فقط "قائمة تسجيل" (registry).
"""

from app.database.base import Base
from app.database.session import engine

# --- تسجيل موديلات كل وحدة ---
# ملاحظة: الاستيراد نفسه (حتى لو غير مستخدم مباشرة بهذا الملف) كافٍ لتسجيل
# الجدول في Base.metadata. لذلك نُبقي الاستيراد حتى لو أظهر المحرر تحذير
# "unused import".
from app.modules.users import models as users_models          # noqa: F401
from app.modules.equipment import models as equipment_models  # noqa: F401


def init_db() -> None:
    """ينشئ كل الجداول غير الموجودة. لا يحذف أو يعدّل جداول موجودة."""
    Base.metadata.create_all(bind=engine)


def create_default_admin() -> None:
    """
    ينشئ مستخدم Admin افتراضي في أول تشغيل فقط (إذا لم يوجد أي مستخدم).
    مفيد جدًا في بيئة الاختبار: تدخل مباشرة بدون خطوات يدوية بقاعدة البيانات.
    """
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
