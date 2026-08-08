"""
core/config.py
---------------
مصدر واحد لكل الإعدادات. أي وحدة تحتاج إعداد (اسم قاعدة البيانات، مدة صلاحية
الجلسة، مفتاح التشفير...) تستورده من هنا، ولا يوجد "hardcoded" قيم متفرقة
داخل الوحدات.

الإعدادات تُقرأ من متغيرات البيئة (Environment Variables) مع قيم افتراضية
مناسبة للتطوير المحلي فقط. في الإنتاج يجب تعيين متغيرات البيئة الحقيقية
(خصوصًا SECRET_KEY وبيانات قاعدة البيانات) ولا يجب الاعتماد على الافتراضي.
"""

import os
from functools import lru_cache


class Settings:
    # ---- عام ----
    APP_NAME: str = "Fleet & Assets Manager"
    ENV: str = os.getenv("APP_ENV", "development")  # development | production
    DEBUG: bool = ENV != "production"

    # ---- قاعدة البيانات ----
    # في التطوير: SQLite محلي. في الإنتاج: يُستبدل بـ PostgreSQL عبر متغير البيئة
    # DATABASE_URL دون تعديل أي كود آخر في المشروع.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./fleet_assets.db"
    )

    # ---- الأمان ----
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "dev-only-secret-change-me-in-production"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480")  # 8 ساعات عمل
    )

    # ---- الجلسة (Cookie) ----
    SESSION_COOKIE_NAME: str = "fleet_session"

    # ---- الشبكة ----
    HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("APP_PORT", "8000"))


@lru_cache
def get_settings() -> Settings:
    """
    يُستخدم كـ Dependency في FastAPI أو يُستدعى مباشرة.
    lru_cache يضمن قراءة الإعدادات مرة واحدة فقط طوال عمر التطبيق.
    """
    return Settings()


settings = get_settings()
