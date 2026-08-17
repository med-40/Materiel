from datetime import date
from io import BytesIO
from fastapi import UploadFile
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.base import Base
from app.modules.equipment.models import Equipment
from app.modules.equipment_types.models import EquipmentModel, EquipmentType
from app.modules.meter_readings.router import meter_readings_import_excel, _read_excel_rows
from app.modules.users.models import User

engine=create_engine('sqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
Session=sessionmaker(bind=engine,autoflush=False,autocommit=False)

def test_debug():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine); db=Session()
    try:
        for reg,unit in [('E-400','km'),('E-401','hours')]:
            et=EquipmentType(name=f'نوع-{reg}',measurement_unit=unit); db.add(et); db.flush()
            model=EquipmentModel(name=f'طراز-{reg}',equipment_type_id=et.id); db.add(model); db.flush()
            db.add(Equipment(asset_code=f'A-{reg}',registration_number=reg,equipment_type_id=et.id,equipment_model_id=model.id,operational_status='available'))
        db.commit()
        actor=User(username='debug-excel',full_name='debug',hashed_password='x',role='admin'); db.add(actor); db.commit(); db.refresh(actor)
        wb=Workbook(); ws=wb.active; ws.append(['Status','registration number','Date','Equipment Type','Odometer','Hour meter']); ws.append(['working','E-400',date(2026,8,15),'نوع-E-400','2,000.5',None]); ws.append(['لا يعمل','E-401',46250,'نوع-E-401',None,'٧٥٫٢']); ws.append(['available','E-400','17/08/2026','نوع-E-400','2,100',None]); b=BytesIO(); wb.save(b); b.seek(0)
        response=meter_readings_import_excel(UploadFile(filename='debug.xlsx',file=b),None,db,actor)
        b.seek(0); rows,errs,count=_read_excel_rows(b,db)
        assert False, f'BODY={response.body.decode("utf-8")} ROWS={rows} PARSE_ERRORS={errs} COUNT={count}'
    finally: db.close()
