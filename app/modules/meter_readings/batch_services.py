from sqlalchemy import delete
from sqlalchemy.orm import Session
from app.modules.meter_readings.batches import MeterReadingBatch, meter_reading_batch_items
from app.modules.meter_readings.models import MeterReading

def create_batch(db: Session, kind: str, filename: str | None, user_id: int | None, readings: list[MeterReading]) -> MeterReadingBatch:
    batch = MeterReadingBatch(kind=kind, filename=(filename or '')[:255] or None, created_by_id=user_id, status='active', count=len(readings))
    db.add(batch)
    db.flush()
    for reading in readings:
        db.execute(meter_reading_batch_items.insert().values(batch_id=batch.id, reading_id=reading.id))
    return batch

def list_batches(db: Session, limit: int = 50):
    return db.query(MeterReadingBatch).order_by(MeterReadingBatch.created_at.desc(), MeterReadingBatch.id.desc()).limit(limit).all()

def rollback_batch(db: Session, batch_id: int):
    batch = db.query(MeterReadingBatch).filter(MeterReadingBatch.id == batch_id).first()
    if not batch:
        return None, 0
    if batch.status != 'active':
        return batch, 0
    ids = [row[0] for row in db.query(meter_reading_batch_items.c.reading_id).filter(meter_reading_batch_items.c.batch_id == batch.id).all()]
    count = len(ids)
    if ids:
        db.query(MeterReading).filter(MeterReading.id.in_(ids)).delete(synchronize_session=False)
    db.execute(delete(meter_reading_batch_items).where(meter_reading_batch_items.c.batch_id == batch.id))
    batch.status = 'rolled_back'
    db.commit()
    return batch, count
