from tests.test_meter_input_matrix import make_excel, seed, user
from app.modules.meter_readings.router import meter_readings_import_excel
from fastapi import UploadFile
from datetime import date


def test_diagnose_excel_matrix(db):
    seed(db, "E-400", "km")
    seed(db, "E-401", "hours")
    actor = user(db, "excel-diagnose")
    buffer = make_excel([
        ["working", "E-400", date(2026, 8, 15), "نوع-E-400", "2,000.5", None],
        ["لا يعمل", "E-401", 46250, "نوع-E-401", None, "٧٥٫٢"],
        ["available", "E-400", "17/08/2026", "نوع-E-400", "2,100", None],
    ], ["Status", "registration number", "Date", "Equipment Type", "Odometer", "Hour meter"])
    response = meter_readings_import_excel(UploadFile(filename="matrix.xlsx", file=buffer), None, db, actor)
    print("EXCEL_DIAGNOSTIC", response.body.decode("utf-8"), flush=True)
