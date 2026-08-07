"""
core/dependencies.py
---------------------
Dependencies عامة يُعاد استخدامها في كل الوحدات. الأهم هنا get_current_user
الذي يقرأ الجلسة (Cookie) ويرجع المستخدم المسجل دخوله، ليستخدمه أي router
بحاجة لمعرفة "من الذي يقوم بهذا الإجراء" (لأجل الصلاحيات وسجل التدقيق).
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.database.session import get_db


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    يقرأ التوكن من الكوكي، يفك تشفيره، ويرجع كائن المستخدم من قاعدة البيانات.
    يرمي 401 لو الجلسة غير موجودة أو منتهية - هذا يُستخدم لحماية أي صفحة أو
    API endpoint في أي وحدة.
    """
    # استيراد داخلي لتفادي دائرة استيراد (circular import) مع modules.users
    from app.modules.users.services import get_user_by_username

    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="غير مصرح لك - الرجاء تسجيل الدخول",
    )

    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise credentials_exception

    user = get_user_by_username(db, payload["sub"])
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    """نسخة لا ترمي خطأ - تستخدم بصفحات تحتاج تعرف "هل يوجد مستخدم؟" فقط."""
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None
