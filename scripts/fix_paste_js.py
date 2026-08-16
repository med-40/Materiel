from pathlib import Path
p=Path('app/modules/meter_readings/templates/meter_readings.html')
s=p.read_text(encoding='utf-8')
s=s.replace(r"split(/\\r?\\n/)", r"split(/\r?\n/)")
s=s.replace(r"split('\\t')", r"split('\t')")
p.write_text(s, encoding='utf-8')
