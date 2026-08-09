from typing import Optional
from sqlalchemy.orm import Session

from app.modules.equipment.models import Equipment
from app.modules.equipment.schemas import EquipmentCreate, EquipmentUpdate


def list_equipment(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    operational_status: Optional[str] = None,
    technical_condition: Optional[str] = None,
) -> list[Equipment]:
    query = db.query(Equipment)
    if operational_status:
        query = query.filter(Equipment.operational_status == operational_status)
    if technical_condition:
        query = query.filter(Equipment.technical_condition == technical_condition)
    return query.order_by(Equipment.id.desc()).offset(skip).limit(limit).all()


def get_equipment(db: Session, equipment_id: int) -> Optional[Equipment]:
    return db.query(Equipment).filter(Equipment.id == equipment_id).first()


def get_by_asset_code(db: Session, asset_code: str) -> Optional[Equipment]:
    return db.query(Equipment).filter(Equipment.asset_code == asset_code).first()


def create_equipment(
    db: Session, data: EquipmentCreate, user_id: Optional[int] = None
) -> Equipment:
    if get_by_asset_code(db, data.asset_code):
        raise ValueError("رقم العتاد (asset_code) موجود مسبقًا")

    equipment = Equipment(**data.model_dump(), created_by_id=user_id, updated_by_id=user_id)
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    return equipment


def update_equipment(
    db: Session, equipment: Equipment, data: EquipmentUpdate, user_id: Optional[int] = None
) -> Equipment:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(equipment, field, value)
    equipment.updated_by_id = user_id
    db.commit()
    db.refresh(equipment)
    return equipment


def delete_equipment(db: Session, equipment: Equipment) -> None:
    db.delete(equipment)
    db.commit()


def count_by_operational_status(db: Session) -> dict[str, int]:
    from sqlalchemy import func

    rows = (
        db.query(Equipment.operational_status, func.count(Equipment.id))
        .group_by(Equipment.operational_status)
        .all()
    )
    return {status: count for status, count in rows}


def count_broken(db: Session) -> int:
    return db.query(Equipment).filter(Equipment.technical_condition == "broken").count()
