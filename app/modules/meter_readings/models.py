from datetime import datetime

from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.database.base import Base


class MeterReading(Base):
    __tablename__ = "meter_readings"

    id = Column(Integer, primary_key=True, index=True)

    equipment_id = Column(
        Integer,
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reading_date = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # تاريخ إنشاء السجل في النظام، مستقل عن تاريخ القراءة.
    # مهم خصوصًا عند إدخال قراءات تاريخية قديمة.
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    odometer = Column(Numeric(10, 1), nullable=True)
    hours = Column(Numeric(10, 1), nullable=True)

    source = Column(String(50), nullable=False, default="manual")
    notes = Column(String(300), nullable=True)

    equipment = relationship("Equipment")
