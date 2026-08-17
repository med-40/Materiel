from pathlib import Path
import re


TEMPLATE = Path(__file__).parents[1] / "app/modules/meter_readings/templates/meter_readings.html"
HISTORY_TEMPLATE = Path(__file__).parents[1] / "app/modules/meter_readings/templates/meter_readings_list.html"


def _scripts(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", text, flags=re.S | re.I)


def test_meter_readings_page_contains_script_and_core_client_handlers():
    scripts = _scripts(TEMPLATE)
    assert scripts, "صفحة قراءات العدادات يجب أن تحتوي على JavaScript"
    script = "\n".join(scripts)
    for marker in (
        "function openReadingModal()",
        "function openPasteModal()",
        "function openImportModal()",
        "function openDateModal()",
        "function openSelectedHistory()",
        "function toggleMoreFilters()",
        "function applyDateFilter()",
        "function clearDateFilter()",
        "function submitPastedReadings()",
        "function submitExcelImport()",
        "function printReadings()",
        "function exportPDF()",
        "function exportExcel()",
        "raw.split(/\\r?\\n/)",
    ):
        assert marker in script, f"معالج JavaScript مفقود: {marker}"


def test_meter_readings_page_keeps_all_core_actions():
    text = TEMPLATE.read_text(encoding="utf-8")
    for marker in (
        "openReadingModal()",
        "openPasteModal()",
        "openImportModal()",
        "openDateModal()",
        "openSelectedHistory()",
        "toggleMoreFilters()",
        "applyDateFilter()",
        "clearDateFilter()",
        "submitPastedReadings()",
        "submitExcelImport()",
        "printReadings()",
        "exportPDF()",
        "exportExcel()",
        "meter-readings/bulk-create",
        "meter-readings/import-excel",
    ):
        assert marker in text, f"وظيفة واجهة مفقودة: {marker}"


def test_meter_history_page_keeps_edit_delete_actions():
    text = HISTORY_TEMPLATE.read_text(encoding="utf-8")
    assert 'class="action-btn edit"' in text
    assert 'class="action-btn delete"' in text
    assert '/meter-readings/history/{{ equipment.id }}/update' in text
    assert '/meter-readings/history/{{ equipment.id }}/delete' in text
