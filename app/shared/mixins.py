"""
shared/mixins.py
-----------------
كل موديل جديد بأي وحدة (equipment, maintenance, fuel...) يرث من هذه الـ
Mixins بدل ما يعيد كتابة نفس الأعمدة (created_at, created_by...) يدويًا في
كل مرة. هذا هو المكان الوحيد المسموح فيه لكود "عابر للوحدات" أن يوجد، لأنه
ليس منطق عمل (Business Logic) لوحدة معينة، بل بنية بيانات مشتركة.

قاعدة: shared/ لا يجوز أن يحتوي أي شيء يعرف تفاصيل وحدة معينة (مثل استيراد
موديل equipment هنا). فقط تعريفات عامة.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, ForeignKey
from sqlalchemy.orm import declared_attr


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    """تاريخ الإنشاء والتعديل تلقائيًا لأي جدول."""

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class AuditMixin(TimestampMixin):
    """
    سجل تدقيق أساسي على مستوى كل سجل: من أنشأه ومن آخر من عدّله.
    هذا هو الأساس الذي يُبنى عليه لاحقًا "سجل التدقيق" الكامل (جدول منفصل
    audit_log يسجّل كل تغيير بالتفصيل) بدون ما يتعارض مع هذا الـ mixin.
    """

    @declared_attr
    def created_by_id(cls):
        return Column(Integer, ForeignKey("users.id"), nullable=True)

    @declared_attr
    def updated_by_id(cls):
        return Column(Integer, ForeignKey("users.id"), nullable=True)
