"""
modules/users/schemas.py
--------------------------
Pydantic schemas: تتحقق من شكل البيانات القادمة من الـ API/Forms، وتحدد
شكل البيانات الراجعة للمستخدم. الفصل بين UserCreate و UserOut مهم جدًا:
لا يجب أن ترجع كلمة المرور (حتى المشفّرة) في أي استجابة أبدًا.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class UserBase(BaseModel):
    username: str
    full_name: str
    role: str = "viewer"


class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("كلمة المرور يجب ألا تقل عن 6 خانات")
        return v

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        allowed = {"admin", "fleet_manager", "operator", "viewer"}
        if v not in allowed:
            raise ValueError(f"الدور يجب أن يكون أحد: {allowed}")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class LoginRequest(BaseModel):
    username: str
    password: str
