from typing import Optional
from sqlalchemy.orm import Session, joinedload

from app.modules.equipment_types.models import EquipmentType, EquipmentModel
from app.modules.equipment_types.schemas import EquipmentTypeCreate, EquipmentModelCreate


def list_types(db: Session) -> list[EquipmentType]:
    return (
        db.query(EquipmentType)
        .options(joinedload(EquipmentType.models))
        .order_by(EquipmentType.name)
        .all()
    )


def get_type(db: Session, type_id: int) -> Optional[EquipmentType]:
    return db.query(EquipmentType).filter(EquipmentType.id == type_id).first()


def get_type_by_name(db: Session, name: str) -> Optional[EquipmentType]:
    return db.query(EquipmentType).filter(EquipmentType.name == name).first()


def create_type(db: Session, data: EquipmentTypeCreate) -> EquipmentType:
    if get_type_by_name(db, data.name):
        raise ValueError("نوع العتاد موجود مسبقًا")
    obj = EquipmentType(name=data.name, measurement_unit=data.measurement_unit)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def delete_type(db: Session, obj: EquipmentType) -> None:
    db.delete(obj)
    db.commit()


def list_models(db: Session, type_id: Optional[int] = None) -> list[EquipmentModel]:
    query = db.query(EquipmentModel)
    if type_id:
        query = query.filter(EquipmentModel.equipment_type_id == type_id)
    return query.order_by(EquipmentModel.name).all()


def get_model(db: Session, model_id: int) -> Optional[EquipmentModel]:
    return db.query(EquipmentModel).filter(EquipmentModel.id == model_id).first()


def create_model(db: Session, data: EquipmentModelCreate) -> EquipmentModel:
    exists = (
        db.query(EquipmentModel)
        .filter(
            EquipmentModel.equipment_type_id == data.equipment_type_id,
            EquipmentModel.name == data.name,
        )
        .first()
    )
    if exists:
        raise ValueError("الطراز موجود مسبقًا لهذا النوع")
    obj = EquipmentModel(name=data.name, equipment_type_id=data.equipment_type_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def delete_model(db: Session, obj: EquipmentModel) -> None:
    db.delete(obj)
    db.commit()
