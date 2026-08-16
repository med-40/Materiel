"""
core/dependencies.py
---------------------
Dependencies عامة لحماية الصفحات وربط العملية بالمستخدم الحالي.
"""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import decode_access_token
from app.database.session import get_db


def get_current_user(request: Request, db: Session = Depends(get_db)):
    from app.modules.users.services import get_user_by_username
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="غير مصرح لك - الرجاء تسجيل الدخول")
    if not token:
        raise credentials_exception
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise credentials_exception
    user = get_user_by_username(db, payload["sub"])
    if user is None or not user.is_active:
        raise credentials_exception
    try:
        from app.modules.meter_readings.audit_events import set_request_actor
        path = request.url.path
        kind = 'excel' if path.endswith('/import-excel') else ('paste' if path.endswith('/bulk-create') else 'manual')
        set_request_actor(user.id, kind)
    except Exception:
        pass
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None
