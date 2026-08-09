from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.base import Base
from app.shared.mixins import TimestampMixin


class EquipmentType(Base, TimestampMixin):
    __tablename__ = "equipment_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), unique=True, nullable=False)
    has_hour_meter = Column(Boolean, nullable=False, default=False)

    models = relationship(
        "EquipmentModel", back_populates="equipment_type", cascade="all, delete-orphan"
    )


class EquipmentModel(Base, TimestampMixin):
    __tablename__ = "equipment_models"
    __table_args__ = (
        UniqueConstraint("equipment_type_id", "name", name="uq_model_per_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    equipment_type_id = Column(Integer, ForeignKey("equipment_types.id"), nullable=False)

    equipment_type = relationship("EquipmentType", back_populates="models")
