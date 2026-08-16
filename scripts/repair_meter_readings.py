from pathlib import Path


def replace_js_function(text: str, name: str, replacement: str) -> str:
    start = text.find(f"function {name}")
    if start < 0:
        raise SystemExit(f"function {name} not found")
    brace = text.find("{", start)
    depth = 0
    quote = None
    escaped = False
    for i in range(brace, len(text)):
        ch = text[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in "'\"`":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement + text[i + 1 :]
    raise SystemExit(f"unbalanced function {name}")


service = Path("app/modules/meter_readings/services.py")
s = service.read_text(encoding="utf-8")
if "def cleanup_invalid_readings" not in s:
    marker = "\ndef list_latest_rows("
    cleanup = '''\n\ndef cleanup_invalid_readings(db: Session):\n    """Remove legacy readings that violate the hard date/value rules."""\n    today = datetime.utcnow().date()\n    cutoff = datetime.combine(today, datetime.max.time())\n    invalid = db.query(MeterReading).filter(MeterReading.reading_date > cutoff).all()\n    invalid += db.query(MeterReading).filter((MeterReading.odometer < 0) | (MeterReading.hours < 0)).all()\n    unique = {item.id: item for item in invalid}\n    if not unique:\n        return 0\n    equipment_ids = {item.equipment_id for item in unique.values()}\n    for item in unique.values():\n        db.delete(item)\n    db.flush()\n    for equipment_id in equipment_ids:\n        equipment = get_equipment_with_readings(db, equipment_id)\n        if equipment:\n            _refresh_equipment_current(db, equipment, _unit(equipment))\n    db.commit()\n    return len(unique)\n'''
    s = s.replace(marker, cleanup + marker, 1)
needle = '''        equipment = equipment_map.get(registration)\n        if not equipment:\n            errors.append(f"الصف {row_number}: رقم التسجيل {registration_raw} غير موجود في النظام.")\n            continue\n'''
if "equipment_type_raw = row.get(\"equipment_type\")" not in s:
    replacement = needle + '''        equipment_type_raw = row.get("equipment_type")\n        if equipment_type_raw is None or not str(equipment_type_raw).strip():\n            errors.append(f"الصف {row_number}: نوع العتاد فارغ.")\n            continue\n        expected_type = str(equipment.equipment_type.name if equipment.equipment_type else "").strip()\n        pasted_type = " ".join(str(equipment_type_raw).strip().split()).casefold()\n        if expected_type and pasted_type != " ".join(expected_type.split()).casefold():\n            errors.append(f"الصف {row_number}: نوع العتاد «{equipment_type_raw}» لا يطابق النوع المسجل «{expected_type}» لرقم التسجيل {registration_raw}.")\n            continue\n'''
    if needle not in s:
        raise SystemExit("service validation marker not found")
    s = s.replace(needle, replacement, 1)
service.write_text(s, encoding="utf-8")

router = Path("app/modules/meter_readings/router.py")
r = router.read_text(encoding="utf-8")
if "services.cleanup_invalid_readings(db)" not in r:
    sig = "def meter_readings_page(request: Request,"
    pos = r.index(sig)
    body = r.index(":\n", pos) + 2
    r = r[:body] + "    services.cleanup_invalid_readings(db)\n" + r[body:]
old = '"registration": row.get("registration"),\n                "reading_date": _parse_date(row.get("reading_date")),'
new = '"equipment_type": row.get("equipment_type"),\n                "registration": row.get("registration"),\n                "reading_date": _parse_date(row.get("reading_date")),'
if old not in r:
    raise SystemExit("router paste marker not found")
r = r.replace(old, new, 1)
router.write_text(r, encoding="utf-8")

template = Path("app/modules/meter_readings/templates/meter_readings.html")
t = template.read_text(encoding="utf-8")
t = t.replace("رقم التسجيل | التاريخ | الكيلومترات | الساعات | الملاحظات | حالة العداد", "نوع العتاد | رقم التسجيل | التاريخ | الكيلومترات | الساعات | الملاحظات | حالة العداد", 1)
t = t.replace("123-001&#9;15/08/2026&#9;12500&#9;&#9;عادي\\n123-002&#9;15/08/2026&#9;&#9;8750&#9;صيانة", "شاحنة&#9;123-001&#9;15/08/2026&#9;12500&#9;&#9;عادي&#9;يعمل\\nسيارة&#9;123-002&#9;15/08/2026&#9;&#9;8750&#9;صيانة&#9;يعمل", 1)
new_submit = '''async function submitPastedReadings(){
 const box=document.getElementById('pasteData'); const result=document.getElementById('pasteResult'); const raw=(box?.value||'').trim(); result.innerHTML='';
 if(!raw){result.innerHTML='<div class="error-card">⚠️ ألصق بيانات Excel أولاً.</div>';return;}
 const lines=raw.split(/\\r?\\n/).filter(x=>x.trim()); const rows=[];
 for(let i=0;i<lines.length;i++){ const p=lines[i].split('\\t'); if(p.length<7){result.innerHTML+=`<div class="error-card">⚠️ الصف ${i+1}: يجب أن يحتوي على نوع العتاد ورقم التسجيل والتاريخ والكيلومترات والساعات والملاحظات وحالة العداد.</div>`; continue;} rows.push({equipment_type:p[0].trim(),registration:p[1].trim(),reading_date:p[2].trim(),km_value:p[3].trim(),hours_value:p[4].trim(),notes:p[5].trim(),equipment_status:p[6].trim()}); }
 if(!rows.length)return;
 try{ const response=await fetch('/meter-readings/bulk-create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows})}); const data=await response.json(); let html=`<div class="import-summary">تم قبول ${data.created||0} صف، ورفض ${data.skipped||0} صف.</div>`; if(data.errors?.length) html+=data.errors.join(''); result.innerHTML=html; if((data.created||0)>0 && !(data.errors?.length)) setTimeout(()=>window.location.reload(),500); }catch(e){result.innerHTML=`<div class="error-card">⚠️ تعذر الاتصال بالخادم: ${String(e)}</div>`;}
}'''
t = replace_js_function(t, "submitPastedReadings", new_submit)
template.write_text(t, encoding="utf-8")
