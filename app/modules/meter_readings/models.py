from datetime import datetime

from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, String, event, func
from sqlalchemy.orm import relationship

from app.database.base import Base


class MeterReading(Base):
    __tablename__ = "meter_readings"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, index=True)
    reading_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.current_timestamp(), onupdate=datetime.utcnow)
    odometer = Column(Numeric(10, 1), nullable=True)
    hours = Column(Numeric(10, 1), nullable=True)
    source = Column(String(50), nullable=False, default="manual")
    notes = Column(String(300), nullable=True)
    equipment = relationship("Equipment")


@event.listens_for(MeterReading, "before_insert")
def _validate_meter_reading(mapper, connection, target):
    now = datetime.utcnow()
    if target.created_at is None:
        target.created_at = now
    if target.updated_at is None:
        target.updated_at = now
    # لا يسمح النظام بتسجيل قراءة بتاريخ مستقبلي.
    if target.reading_date is not None and target.reading_date.date() > now.date():
        raise ValueError("لا يمكن إدخال قراءة بتاريخ مستقبلي.")
    # إذا وصل صف من استيراد/لصق بدون قيمة عداد، تعتبر القراءة صفرية.
    if target.odometer is None and target.hours is None:
        target.odometer = 0
