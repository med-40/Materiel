from datetime import datetime

from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.database.base import Base


class OdometerReading(Base):
    __tablename__ = "odometer_readings"

    id = Column(Integer, primary_key=True, index=True)

    equipment_id = Column(
        Integer,
        ForeignKey("equipment.id"),
        nullable=False,
        index=True,
    )

    reading_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    odometer = Column(Numeric(10, 1), nullable=False)

    source = Column(String(30), nullable=True)

    notes = Column(Text, nullable=True)

    created_by_id = Column(Integer, nullable=True)
    updated_by_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    equipment = relationship("Equipment")
