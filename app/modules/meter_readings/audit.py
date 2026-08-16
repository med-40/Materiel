from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from app.database.base import Base

class MeterReadingOperation(Base):
    __tablename__ = "meter_reading_operations"
    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String(30), nullable=False)
    filename = Column(String(255), nullable=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String(30), nullable=False, default="draft")
    total_rows = Column(Integer, nullable=False, default=0)
    accepted_rows = Column(Integer, nullable=False, default=0)
    rejected_rows = Column(Integer, nullable=False, default=0)
    reading_ids = Column(JSON, nullable=False, default=list)
    rolled_back_at = Column(DateTime, nullable=True)
    rolled_back_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

class MeterReadingOperationEvent(Base):
    __tablename__ = "meter_reading_operation_events"
    id = Column(Integer, primary_key=True, index=True)
    operation_id = Column(Integer, ForeignKey("meter_reading_operations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    details = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
