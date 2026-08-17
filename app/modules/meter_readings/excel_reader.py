from __future__ import annotations
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from openpyxl import load_workbook

NS="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL="http://schemas.openxmlformats.org/officeDocument/2006/relationships"

def tag(n): return f"{{{NS}}}{n}"

def col_index(ref):
    n=0
    for ch in "".join(c for c in ref if c.isalpha()).upper(): n=n*26+ord(ch)-64
    return max(0,n-1)

class RawSheet:
    def __init__(self,rows): self.rows=rows
    def iter_rows(self,values_only=True): return iter(self.rows)

class RawWorkbook:
    def __init__(self,rows): self.active=RawSheet(rows)

def _clean_header_text(value):
    if value is None: return ""
    # Keep Excel numbers/dates as their original types; only clean text cells.
    if not isinstance(value, str): return value
    # Excel may preserve RTL/LTR marks and zero-width characters in copied headers.
    text = value.replace("\ufeff", "")
    text = "".join(ch for ch in text if ch not in "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
    return text.strip()

def _normalize_import_headers(workbook):
    """Normalize historical/exported headers without changing the user's data."""
    try:
        sheet = workbook.active
        for row in sheet.iter_rows(min_row=1, max_row=20):
            for cell in row:
                value = _clean_header_text(cell.value)
                if value == "نوع العداد":
                    cell.value = "نوع العتاد"
                elif value == "حاله العداد":
                    cell.value = "حالة العداد"
                elif isinstance(value, str) and value:
                    cell.value = value
    except Exception:
        pass
    return workbook

def _normalize_raw_headers(rows):
    for row in rows[:20]:
        for idx, value in enumerate(row):
            value = _clean_header_text(value)
            if value == "نوع العداد":
                value = "نوع العتاد"
            elif value == "حاله العداد":
                value = "حالة العداد"
            row[idx] = value
    return rows

def raw_xlsx(data):
    with ZipFile(BytesIO(data)) as z:
        names=set(z.namelist()); shared=[]
        if "xl/sharedStrings.xml" in names:
            root=ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(tag("si")): shared.append("".join(t.text or "" for t in si.iter(tag("t"))))
        sheet="xl/worksheets/sheet1.xml"
        if "xl/workbook.xml" in names and "xl/_rels/workbook.xml.rels" in names:
            wb=ET.fromstring(z.read("xl/workbook.xml")); rr=ET.fromstring(z.read("xl/_rels/workbook.xml.rels")); rels={r.attrib.get("Id"):r.attrib.get("Target") for r in rr}; sheets=wb.find(tag("sheets")); first=next(iter(sheets),None) if sheets is not None else None
            if first is not None:
                target=rels.get(first.attrib.get(f"{{{REL}}}id"))
                if target: target=target.lstrip("/"); sheet=target if target.startswith("xl/") else "xl/"+target
        root=ET.fromstring(z.read(sheet)); sd=root.find(tag("sheetData")); rows=[]
        if sd is None: return RawWorkbook([])
        for row in sd.findall(tag("row")):
            cells={}; mx=-1
            for c in row.findall(tag("c")):
                idx=col_index(c.attrib.get("r","A1")); mx=max(mx,idx); typ=c.attrib.get("t"); v=c.find(tag("v")); raw=v.text if v is not None else None; value=None
                if typ=="inlineStr":
                    el=c.find(tag("is")); value="".join(t.text or "" for t in el.iter(tag("t"))) if el is not None else ""
                elif raw is not None and typ=="s":
                    try: value=shared[int(raw)]
                    except (ValueError,IndexError): value=raw
                elif raw is not None and typ=="b": value=raw=="1"
                elif raw is not None:
                    try: value=float(raw); value=int(value) if value.is_integer() else value
                    except (TypeError,ValueError): value=raw
                cells[idx]=value
            rows.append([cells.get(i) for i in range(mx+1)])
        return RawWorkbook(_normalize_raw_headers(rows))

def load_meter_workbook(stream):
    data=stream.read()
    if hasattr(stream,"seek"): stream.seek(0)
    try: return _normalize_import_headers(load_workbook(BytesIO(data),read_only=False,data_only=True))
    except Exception as exc:
        try: return raw_xlsx(data)
        except Exception as raw_exc: raise ValueError(f"تعذر قراءة ملف Excel. تأكد أن الملف بصيغة XLSX سليمة. التفاصيل: {exc}") from raw_exc
