"""
modules/equipment/models.py
------------------------------
موديل السيارة/العتاد. هذا هو "المحور" الذي سترتبط به وحدات أخرى لاحقًا
(maintenance, fuel, faults, tires, batteries...) عبر ForeignKey على
equipment.id - دون أن تحتاج وحدة equipment نفسها تعرف بوجودهم.

ملاحظة مهمة: يوجد حقلان منفصلان للحالة، ولا يجوز دمجهما:
- technical_condition: حالة العتاد الفنية/الميكانيكية (جاهز / عاطل)
- operational_status: أين العتاد الآن تشغيليًا (متاح / في مهمة / في الصيانة...)

مثال يوضح سبب الفصل: عتاد ممكن يكون "جاهز" فنيًا لكنه "في مهمة" وضعيًا،
أو "عاطل" فنيًا وبنفس الوقت "في ورشة خارجية" وضعيًا. حقل واحد لا يكفي
لتمثيل الحالتين معًا.
"""

from sqlalchemy import Column, Integer, String, Date, Numeric
from app.database.base import Base
from app.shared.mixins import AuditMixin


class Equipment(Base, AuditMixin):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, index=True)

    # ---- بيانات تعريفية ----
    asset_code = Column(String(50), unique=True, index=True, nullable=False)  # رقم داخلي بالمؤسسة
    registration_number = Column(String(30), unique=True, index=True, nullable=True)  # رقم التسجيل
    vin = Column(String(50), unique=True, nullable=True)  # رقم الهيكل
    category = Column(String(50), nullable=False)   # نوع العتاد: سيارة / شاحنة / معدة ثقيلة...
    make = Column(String(80), nullable=True)         # الصانع (اختياري - معلومة إضافية)
    model = Column(String(80), nullable=True)         # الطراز
    year = Column(Integer, nullable=True)

    # وثيقة الاقتناء - رقم/مرجع الوثيقة (رفع الملف نفسه يُضاف لاحقًا كوحدة مرفقات)
    acquisition_document = Column(String(100), nullable=True)
    acquisition_date = Column(Date, nullable=True)

    # ---- الحالة الفنية: جاهز أو عاطل ----
    technical_condition = Column(String(20), nullable=False, default="ready")
    # ready | broken

    # ---- الوضعية: أين العتاد الآن تشغيليًا ----
    operational_status = Column(String(30), nullable=False, default="available")
    # available | in_mission | in_maintenance | in_external_workshop | unavailable

    # عدادات (تُستخدم لاحقًا في وحدة الصيانة لحساب الاستحقاقات بالكم أو بالتاريخ)
    current_odometer = Column(Numeric(10, 1), nullable=True, default=0)  # عداد الكم
    current_hours = Column(Numeric(10, 1), nullable=True, default=0)     # عداد الساعة

    notes = Column(String(500), nullable=True)
