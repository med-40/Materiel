from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.modules.users.models import User
from app.modules.meter_readings.batch_services import list_batches, rollback_batch

router = APIRouter(prefix='/meter-readings/batches', tags=['Meter Reading Batches'])

@router.get('')
def batches(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = list_batches(db)
    return {'batches': [{'id': b.id, 'kind': b.kind, 'filename': b.filename, 'created_at': b.created_at.strftime('%d/%m/%Y %H:%M'), 'status': b.status, 'count': b.count} for b in rows]}

@router.post('/{batch_id}/rollback')
def rollback(batch_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    batch, count = rollback_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail='عملية الإدخال غير موجودة.')
    if count == 0 and batch.status != 'active':
        return JSONResponse({'ok': False, 'message': 'هذه العملية تم التراجع عنها سابقًا.'}, status_code=400)
    return {'ok': True, 'message': f'تم التراجع عن العملية #{batch.id} وإزالة {count} قراءة أدخلتها هذه العملية فقط.'}
