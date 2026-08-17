from pathlib import Path
import re
import shutil
import subprocess
import tempfile


TEMPLATE = Path(__file__).parents[1] / "app/modules/meter_readings/templates/meter_readings.html"
HISTORY_TEMPLATE = Path(__file__).parents[1] / "app/modules/meter_readings/templates/meter_readings_list.html"


def _scripts(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", text, flags=re.S | re.I)


def test_meter_readings_page_javascript_is_syntax_valid():
    node = shutil.which("node")
    if not node:
        return
    scripts = _scripts(TEMPLATE)
    assert scripts, "صفحة قراءات العدادات يجب أن تحتوي على JavaScript"
    for index, script in enumerate(scripts, start=1):
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
            handle.write(script)
            filename = handle.name
        try:
            result = subprocess.run([node, "--check", filename], text=True, capture_output=True)
        finally:
            Path(filename).unlink(missing_ok=True)
        assert result.returncode == 0, f"خطأ JavaScript في script #{index}: {result.stderr}"


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
