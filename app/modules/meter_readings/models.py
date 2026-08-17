from datetime import datetime, timezone

from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, String, event, func, select, insert
from sqlalchemy.orm import relationship

from app.database.base import Base
from app.modules.equipment.models import Equipment
from app.modules.meter_readings.audit import MeterReadingChange, utc_now


class MeterReading(Base):
    __tablename__ = "meter_readings"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, index=True)
    reading_date = Column(DateTime, nullable=False, default=utc_now)
    created_at = Column(DateTime, nullable=False, default=utc_now, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, default=utc_now, server_default=func.current_timestamp(), onupdate=utc_now)
    odometer = Column(Numeric(10, 1), nullable=True)
    hours = Column(Numeric(10, 1), nullable=True)
    source = Column(String(50), nullable=False, default="manual")
    equipment_status = Column(String(30), nullable=False, default="available", server_default="available")
    notes = Column(String(300), nullable=True)
    equipment = relationship("Equipment")


@event.listens_for(MeterReading, "before_insert")
def _validate_meter_reading(mapper, connection, target):
    now = datetime.now(timezone.utc)
    if target.created_at is None:
        target.created_at = now
    if target.updated_at is None:
        target.updated_at = now
    if target.reading_date is not None and target.reading_date.date() > now.date():
        raise ValueError("لا يمكن إدخال قراءة بتاريخ مستقبلي.")
    status = connection.execute(select(Equipment.operational_status).where(Equipment.id == target.equipment_id)).scalar_one_or_none()
    if status:
        target.equipment_status = status


@event.listens_for(MeterReading, "after_insert")
def _audit_meter_insert(mapper, connection, target):
    unit = "km" if target.odometer is not None else "hours"
    value = target.odometer if unit == "km" else target.hours
    connection.execute(insert(MeterReadingChange.__table__).values(
        reading_id=target.id,
        equipment_id=target.equipment_id,
        changed_at=utc_now(),
        action="add",
        source=target.source or "manual",
        reading_date=target.reading_date,
        unit=unit,
        old_value=None,
        new_value=value,
        details="إضافة قراءة جديدة إلى النظام.",
    ))


@event.listens_for(MeterReading, "after_update")
def _audit_meter_update(mapper, connection, target):
    from sqlalchemy import inspect
    state = inspect(target)
    unit = "km" if target.odometer is not None else "hours"
    attr = "odometer" if unit == "km" else "hours"
    history = state.attrs[attr].history
    if not history.has_changes():
        return
    old_value = history.deleted[0] if history.deleted else None
    new_value = history.added[0] if history.added else None
    connection.execute(insert(MeterReadingChange.__table__).values(
        reading_id=target.id,
        equipment_id=target.equipment_id,
        changed_at=utc_now(),
        action="update",
        source=target.source or "manual",
        reading_date=target.reading_date,
        unit=unit,
        old_value=old_value,
        new_value=new_value,
        details="تعديل قيمة قراءة مسجلة.",
    ))
