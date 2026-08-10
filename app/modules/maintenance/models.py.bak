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
    name = Column(String(150), nullable=False)
    internal_code = Column(String(30), unique=True, nullable=False)

    equipment_type_id = Column(Integer, ForeignKey("equipment_types.id"), nullable=False)
    equipment_type = relationship("EquipmentType")

    maintenance_type_id = Column(Integer, ForeignKey("maintenance_types.id"), nullable=False)
    maintenance_type = relationship("MaintenanceType")

    interval_km = Column(Integer, nullable=True)
    interval_hours = Column(Integer, nullable=True)
    interval_days = Column(Integer, nullable=True)

    makes_equipment_unavailable = Column(Boolean, nullable=False, default=False)
    notify_offset_days = Column(Integer, nullable=True, default=0)

    actions_required = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)


class MaintenanceRecord(Base, AuditMixin):
    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, index=True)

    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    equipment = relationship("Equipment")

    maintenance_schedule_id = Column(Integer, ForeignKey("maintenance_schedules.id"), nullable=True)
    maintenance_schedule = relationship("MaintenanceSchedule")

    maintenance_type_id = Column(Integer, ForeignKey("maintenance_types.id"), nullable=True)
    maintenance_type = relationship("MaintenanceType")

    is_scheduled = Column(Boolean, nullable=False, default=False)

    reported_date = Column(Date, nullable=False)
    resolved_date = Column(Date, nullable=True)

    meter_reading = Column(Numeric(10, 1), nullable=True)

    location = Column(String(150), nullable=True)
    performed_by = Column(String(150), nullable=True)

    status = Column(String(20), nullable=False, default="open")
    description = Column(Text, nullable=True)
    resolution_notes = Column(Text, nullable=True)


class MeterReading(Base, AuditMixin):
    __tablename__ = "meter_readings"

    id = Column(Integer, primary_key=True, index=True)

    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    equipment = relationship("Equipment")

    reading_date = Column(Date, nullable=False)
    odometer_value = Column(Numeric(10, 1), nullable=True)
    hours_value = Column(Numeric(10, 1), nullable=True)

    source = Column(String(30), nullable=False, default="manual")
