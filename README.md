# Fleet & Assets Manager

نظام ويب متعدد المستخدمين لإدارة الأسطول والعتاد، مبني على معمارية معيارية
(Modular) بحيث تُضاف/تُعدّل الوحدات دون كسر بقية النظام.

## البنية

```
app/
├── core/           # النواة: إعدادات، أمان، صلاحيات، dependencies
├── database/       # اتصال قاعدة البيانات وتهيئتها فقط
├── shared/         # عناصر مشتركة عابرة للوحدات (mixins) - بدون منطق وحدة معينة
└── modules/        # كل وحدة مستقلة بذاتها:
    ├── users/          # المستخدمون، الأدوار، تسجيل الدخول
    ├── equipment/      # العتاد والسيارات
    └── dashboard/      # لوحة تحكم تجمّع مؤشرات من الوحدات الأخرى
        ├── models.py       # بيانات (SQLAlchemy)
        ├── schemas.py      # تحقق (Pydantic)
        ├── services.py     # منطق العمل
        ├── router.py       # الربط (FastAPI routes)
        └── templates/      # واجهة الوحدة (HTML خاص بها)

web/
├── main.py         # تشغيل وربط الراوترز فقط - بدون منطق عمل
└── templates/       # base.html المشترك بين كل الوحدات

static/             # CSS / JS / صور
```

## القاعدة المعمارية

- **كل وحدة تحت `modules/<name>/` تحتوي طبقاتها الأربع كاملة** (models,
  schemas, services, router) بدل تفريقها في مجلدات عامة. هذا يسمح بحذف أو
  تعطيل وحدة كاملة دون البحث في أماكن متفرقة.
- **الربط بين الوحدات يمر عبر services، لا عبر استيراد models مباشرة** قدر
  الإمكان، لتقليل الترابط (coupling).
- **إضافة وحدة جديدة** = مجلد جديد بنفس النمط + تسجيل الموديل في
  `database/init_db.py` + تسجيل الراوتر في `web/main.py`. لا تعديل على أي
  وحدة قائمة.

## التشغيل محليًا

```bash
python -m venv venv
source venv/bin/activate   # ويندوز: venv\Scripts\activate
pip install -r requirements.txt
python run_web.py
```

الدخول: `http://localhost:8000` — مستخدم افتراضي أول تشغيل: `admin / Admin@123`
(**غيّر كلمة المرور فورًا في أي بيئة غير تطوير محلي**).

## متغيرات البيئة (اختياري - للإنتاج)

| المتغير | الوصف | الافتراضي |
|---|---|---|
| `DATABASE_URL` | رابط قاعدة البيانات | `sqlite:///./fleet_assets.db` |
| `SECRET_KEY` | مفتاح تشفير الجلسات - **غيّره وجوبًا بالإنتاج** | قيمة تطوير غير آمنة |
| `APP_ENV` | `development` أو `production` | `development` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | مدة صلاحية الجلسة بالدقائق | `480` |

## حالة الوحدات

| الوحدة | الحالة |
|---|---|
| users | ✅ مكتملة (مصادقة، أدوار) |
| equipment | ✅ مكتملة (CRUD + API) |
| dashboard | 🟡 أساسي - سيتوسع مع كل وحدة جديدة |
| drivers | ⏳ لم تُبنَ بعد |
| maintenance | ⏳ لم تُبنَ بعد |
| missions | ⏳ لم تُبنَ بعد |
| fuel | ⏳ لم تُبنَ بعد |
| faults | ⏳ لم تُبنَ بعد |
| batteries / tires | ⏳ لم تُبنَ بعد |
| spare_parts | ⏳ لم تُبنَ بعد |
| audit log (تفصيلي) | ⏳ لم يُبنَ بعد |
