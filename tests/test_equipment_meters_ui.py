from pathlib import Path
import re


TEMPLATE = Path(__file__).parents[1] / "app/modules/equipment/templates/equipment_meters.html"


def test_equipment_meter_history_has_exact_reviewed_columns():
    text = TEMPLATE.read_text(encoding="utf-8")
    header_row = re.search(r"<thead>\s*<tr>(.*?)</tr>\s*</thead>", text, flags=re.S)
    assert header_row
    headers = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value)).strip() for value in re.findall(r"<th[^>]*>(.*?)</th>", header_row.group(1), flags=re.S)]
    assert headers == ["#", "التاريخ", "الكيلومترات", "الساعات", "الفارق", "حالة القراءة", "ملاحظات"]
    assert "الإجراءات" not in headers
    assert "مصدر القراءة" not in headers
