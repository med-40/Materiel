from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship
from app.database.base import Base

meter_reading_batch_items = Table(
    "meter_reading_batch_items", Base.metadata,
    Column("batch_id", Integer, ForeignKey("meter_reading_batches.id", ondelete="CASCADE"), primary_key=True),
    Column("reading_id", Integer, ForeignKey("meter_readings.id", ondelete="CASCADE"), primary_key=True),
)

class MeterReadingBatch(Base):
    __tablename__ = "meter_reading_batches"
    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String(30), nullable=False, default="manual")
    filename = Column(String(255), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String(30), nullable=False, default="active")
    count = Column(Integer, nullable=False, default=0)
    readings = relationship("MeterReading", secondary=meter_reading_batch_items, lazy="select")
