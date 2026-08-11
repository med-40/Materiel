from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.database.base import Base
from app.shared.mixins import AuditMixin


class MaintenanceType(Base, AuditMixin):
    __tablename__ = "maintenance_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)


class MaintenanceSchedule(Base, AuditMixin):
    __tablename__ = "maintenance_schedules"

    id = Column(Integer, primary_key=True, index=True)

    # اسم عملية الصيانة الدورية نفسها
    # مثال: تغيير الزيت، فحص الفرامل، تغيير الفلاتر...
    name = Column(String(150), nullable=False)

    internal_code = Column(
        String(30),
        unique=True,
        nullable=False,
    )

    # نوع العتاد الذي تخصه عملية الصيانة
    equipment_type_id = Column(
        Integer,
        ForeignKey("equipment_types.id"),
        nullable=False,
    )

    equipment_type = relationship(
        "EquipmentType",
    )

    # هذا الحقل أبقيناه في قاعدة البيانات للمحافظة
    # على السجلات القديمة، لكنه لم يعد إجباريًا.
    #
    # العملية الجديدة لا تحتاج إلى اختياره من الصفحة.
    maintenance_type_id = Column(
        Integer,
        ForeignKey("maintenance_types.id"),
        nullable=True,
    )

    maintenance_type = relationship(
        "MaintenanceType",
    )

    # ========================================================
    # شروط الاستحقاق
    # ========================================================

    # لعتاد يعتمد على الكيلومترات
    interval_km = Column(
        Integer,
        nullable=True,
    )

    # لعتاد يعتمد على ساعات التشغيل
    interval_hours = Column(
        Integer,
        nullable=True,
    )

    # شرط زمني يمكن أن يعمل مع نوعي العتاد
    interval_days = Column(
        Integer,
        nullable=True,
    )

    # هل يصبح العتاد غير متاح أثناء تنفيذ هذه الصيانة؟
    makes_equipment_unavailable = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    # التنبيه قبل الاستحقاق بالأيام
    notify_offset_days = Column(
        Integer,
        nullable=True,
        default=0,
    )

    # الإجراءات المطلوبة أثناء الصيانة
    actions_required = Column(
        Text,
        nullable=True,
    )

    description = Column(
        Text,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )


class MaintenanceRecord(Base, AuditMixin):
    __tablename__ = "maintenance_records"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    equipment_id = Column(
        Integer,
        ForeignKey("equipment.id"),
        nullable=False,
    )

    equipment = relationship(
        "Equipment",
    )

    # العملية الدورية التي تم تنفيذها
    #
    # إذا كانت الصيانة دورية:
    # يكون لها maintenance_schedule_id.
    #
    # أما التصليحات التي سنعمل عليها لاحقًا
    # فيمكن أن تكون بدون خطة دورية.
    maintenance_schedule_id = Column(
        Integer,
        ForeignKey("maintenance_schedules.id"),
        nullable=True,
    )

    maintenance_schedule = relationship(
        "MaintenanceSchedule",
    )

    # أبقيناه للتوافق مع السجلات القديمة
    # ولن يكون مطلوبًا عند إنشاء صيانة دورية جديدة.
    maintenance_type_id = Column(
        Integer,
        ForeignKey("maintenance_types.id"),
        nullable=True,
    )

    maintenance_type = relationship(
        "MaintenanceType",
    )

    # هل السجل ناتج عن عملية صيانة دورية؟
    is_scheduled = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    reported_date = Column(
        Date,
        nullable=False,
    )

    resolved_date = Column(
        Date,
        nullable=True,
    )

    # قراءة العداد وقت تنفيذ الصيانة
    #
    # إذا كان العتاد km:
    # تكون قراءة الكيلومترات.
    #
    # إذا كان hours:
    # تكون قراءة ساعات التشغيل.
    meter_reading = Column(
        Numeric(10, 1),
        nullable=True,
    )

    location = Column(
        String(150),
        nullable=True,
    )

    performed_by = Column(
        String(150),
        nullable=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default="open",
    )

    description = Column(
        Text,
        nullable=True,
    )

    resolution_notes = Column(
        Text,
        nullable=True,
    )


class MeterReading(Base, AuditMixin):
    __tablename__ = "meter_readings"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    equipment_id = Column(
        Integer,
        ForeignKey("equipment.id"),
        nullable=False,
    )

    equipment = relationship(
        "Equipment",
    )

    reading_date = Column(
        Date,
        nullable=False,
    )

    # قراءة عداد الكيلومترات
    odometer_value = Column(
        Numeric(10, 1),
        nullable=True,
    )

    # قراءة ساعات التشغيل
    hours_value = Column(
        Numeric(10, 1),
        nullable=True,
    )

    source = Column(
        String(30),
        nullable=False,
        default="manual",
    )
