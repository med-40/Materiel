from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database.base import Base


class MeterReading(Base):
    __tablename__ = "meter_readings"

    id = Column(Integer, primary_key=True, index=True)

    equipment_id = Column(
        Integer,
        ForeignKey("equipment.id"),
        nullable=False,
        index=True,
    )

    odometer = Column(Numeric(10, 1), nullable=True)
    hours = Column(Numeric(10, 1), nullable=True)

    reading_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    equipment = relationship("Equipment")
