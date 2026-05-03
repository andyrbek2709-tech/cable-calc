"""Тесты парсеров. Не требуют КЖ.PDF (тяжёлый OCR)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

results = []
def chk(name, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    print(f"  [{tag}]  {name}" + (f"  ({detail})" if detail else ""))
    results.append(condition)

# ── utils ──────────────────────────────────────────────────────────────
print("\n[1] utils.parse_section")
from parsers.utils import parse_section, parse_length, parse_cable_mark, parse_voltage

chk("4x9541x50 (OCR fix)", parse_section('4x9541x50') == (3, 95.0, 50.0, '4x95+1x50'))
chk("4x95+1x50",           parse_section('4x95+1x50') == (3, 95.0, 50.0, '4x95+1x50'))
chk("3x16",                parse_section('3x16')       == (3, 16.0,  0.0, '3x16'))
chk("5x150",               parse_section('5x150')      == (3, 150.0, 0.0, '5x150'))
ph, s, _, _ = parse_section('1x35')
chk("1x35 -> phases=1",    ph == 1 and s == 35.0)

print("\n[2] utils.parse_length")
chk("'260 м'  -> 260", parse_length('260 м') == 260.0)
chk("'L=100m' -> 100", parse_length('L=100m') == 100.0)
chk("'abc'    -> 0",   parse_length('abc') == 0.0)

print("\n[3] utils.parse_cable_mark")
chk("ZA-YWV22",   parse_cable_mark('ZA-YWV22 кабель') == 'ZA-YWV22')
chk("АВВГ",       parse_cable_mark('Марка АВВГ4x16') == 'АВВГ')
chk("NYY",        parse_cable_mark('кабель NYY 3x2.5') == 'NYY')
chk("нет марки",  parse_cable_mark('просто текст') == '')

print("\n[4] utils.parse_voltage")
chk("6 кВ",     parse_voltage('6 кВ') == 6.0)
chk("0.4 kV",   parse_voltage('0.4 kV') == 0.4)
chk("default",  parse_voltage('нет напряжения') == 0.4)

# ── Excel-парсер ────────────────────────────────────────────────────────
print("\n[5] Excel-парсер (синтетический файл)")
import openpyxl, tempfile, os as _os

wb = openpyxl.Workbook()
ws = wb.active
ws.append(["№", "Обозначение", "Марка кабеля", "Сечение", "Длина, м", "Напряжение, кВ"])
ws.append([1, "K-101",  "ВВГнг",    "3x16",       45,  0.4])
ws.append([2, "K-102",  "АВВГ",     "4x95+1x50",  130, 0.4])
ws.append([3, "K-103",  "ZA-YWV22", "5x150",      280, 6.0])
ws.append([4, "",       "",         "",            "",  ""])  # пустая

tmp = tempfile.mktemp(suffix=".xlsx")
wb.save(tmp)

from parsers.excel_parser import parse_excel
res = parse_excel(tmp)
_os.unlink(tmp)

chk("Строк распознано = 3", res.parsed_count == 3, f"got {res.parsed_count}")
chk("K-101 mark=ВВГнг",    any(r.cable_id == 'K-101' and 'ВВГнг' in r.cable_mark for r in res.rows))
chk("K-102 section=4x95+1x50", any(r.section_str == '4x95+1x50' for r in res.rows))
chk("K-103 L=280м",        any(abs(r.length_m - 280) < 1 for r in res.rows))
chk("K-103 voltage=6кВ",   any(r.voltage_kv == 6.0 for r in res.rows))

# Итог
passed = sum(results)
total  = len(results)
print(f"\n{'='*35}")
print(f"Итого: {passed}/{total}")
print("Все тесты прошли!" if passed == total else f"{total-passed} упало")
