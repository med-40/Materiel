from fastapi.templating import Jinja2Templates
from pathlib import Path

from fastapi import APIRouter, Request
from app.core.templating import get_module_templates


router = APIRouter(
    prefix="/meter-readings",
    tags=["Meter Readings"],
)

templates = Jinja2Templates(
    directory=str(Path(__file__).parent / "templates")
)


# بيانات تجريبية فقط في هذه المرحلة
# لا يوجد اتصال بقاعدة البيانات
DEMO_READINGS = [
    {
        "number": 1,
        "type": "حفارة",
        "model": "Excavator",
        "registration": "EX-1001",
        "location": "ورشة A",
        "unit": "ساعة عمل",
        "date": "14/08/2026",
        "reading": "1,245",
        "difference": "+45",
        "note": "عمل عادي",
        "status": "normal",
    },
    {
        "number": 2,
        "type": "شاحنة",
        "model": "شاحنة تفريغ",
        "registration": "TR-2050",
        "location": "الموقع العام",
        "unit": "كم",
        "date": "14/08/2026",
        "reading": "85,600",
        "difference": "+600",
        "note": "مهمة نقل",
        "status": "normal",
    },
    {
        "number": 3,
        "type": "مولد",
        "model": "150KVA",
        "registration": "GEN-150",
        "location": "الورشة B",
        "unit": "ساعة عمل",
        "date": "14/08/2026",
        "reading": "570",
        "difference": "+70",
        "note": "تشغيل مستمر",
        "status": "normal",
    },
    {
        "number": 4,
        "type": "رافعة",
        "model": "رافعة شوكية",
        "registration": "FL-30",
        "location": "المستودع",
        "unit": "ساعة عمل",
        "date": "14/08/2026",
        "reading": "340",
        "difference": "—",
        "note": "العداد مستقر",
        "status": "warning",
    },
    {
        "number": 5,
        "type": "لودر",
        "model": "LD-404",
        "registration": "LD-404",
        "location": "الموقع العام",
        "unit": "ساعة عمل",
        "date": "14/08/2026",
        "reading": "12,450",
        "difference": "+120",
        "note": "عمل عادي",
        "status": "normal",
    },
    {
        "number": 6,
        "type": "ضاغط هواء",
        "model": "COMP-80",
        "registration": "COMP-80",
        "location": "الورشة",
        "unit": "ساعة عمل",
        "date": "14/08/2026",
        "reading": "950",
        "difference": "-50",
        "note": "قراءة غير طبيعية",
        "status": "danger",
    },
    {
        "number": 7,
        "type": "ماكينة لحام",
        "model": "WEL-250",
        "registration": "WEL-250",
        "location": "ورشة A",
        "unit": "ساعة عمل",
        "date": "14/08/2026",
        "reading": "230",
        "difference": "+30",
        "note": "صيانة دورية",
        "status": "warning",
    },
]


@router.get("/")
async def meter_readings_page(request: Request):
    return templates.TemplateResponse(
        "meter_readings.html",
        {
            "request": request,
            "readings": DEMO_READINGS,
            "last_update": "14/08/2026",
        },
    )
