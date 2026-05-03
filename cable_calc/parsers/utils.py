import re
from typing import Tuple

# Марки кабелей - расширенный список для таблиц кабельных журналов
CABLE_MARK_RE = re.compile(
    r'(?<!\w)('
    # Экранированные кабели (ZA-Y...)
    r'ZA-?Y[CW]?V\d*|ZA-?KYW?V\d*|'
    # ВВГ серия
    r'ВВГ(?:(?:нг)?(?:-LS|-CS)?|Э|П)?|'
    # Броненосные и специальные
    r'ВБШв?|ВБШп|ВБШнг|'
    # АВВ/АВВГ
    r'АВВГ(?:нг)?|АВВ|ААБ2л(?:Шв)?|ААШв|'
    # Контрольные и специальные
    r'КГ(?:Ш)?|КГ-ХС|КВВ(?:Г)?|КВВГЭ(?:НГ)?|КНР(?:нг)?|'
    # Прочие
    r'ПВС|СБ|АСБ(?:2л)?|'
    # IEC стандарты
    r'N[AY]?[Y2]?X?Y|NYM|N2XY|NA2XY'
    r')(?![a-zA-Zа-яА-Я0-9])',
    re.IGNORECASE | re.UNICODE
)

SECTION_RE = re.compile(
    r'(\d+)\s*[xхXХ]\s*\(?\s*(?:(?:\d+\s*[xхXХ]\s*)*)?(\d+(?:[.,]\d+)?)'
    r'(?:\s*[\+\-]\s*\(?\s*(?:(?:\d+\s*[xхXХ]\s*)*)?(\d+(?:[.,]\d+)?))?\s*\)?',
    re.UNICODE
)

LENGTH_RE = re.compile(r'(\d{1,5}(?:[.,]\d+)?)\s*(?:м\b|m\b)?')
VOLTAGE_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:кВ|kV)\b', re.IGNORECASE)


def _fix_ocr_section(text: str) -> str:
    """Исправляет частые OCR ошибки в сечениях кабеля."""
    # Удалить "мм²" и скобки (из формата "2х (101 мм²)")
    text = text.replace('мм²', '').replace('(', '').replace(')', '')
    # Ошибка: '+' читается как '4': 4x9541x50 -> 4x95+1x50
    text = re.sub(r'(\d+[xхXХ]\d+?)4(1[xхXХ]\d+)', r'\g<1>+\2', text)
    # Замена запятых на точки (OCR может путать)
    text = text.replace(',', '.')
    return text


def parse_section(text: str) -> Tuple[int, float, float, str]:
    text = _fix_ocr_section(text)
    m = SECTION_RE.search(text)
    if not m:
        return 3, 0.0, 0.0, ""
    n = int(m.group(1))
    s_str = m.group(2).replace(',', '.')
    s = float(s_str)
    zs = 0.0
    if m.group(3):  # теперь группа 3 - доп сечение
        zs_str = m.group(3).replace(',', '.')
        zs = float(zs_str)
    phases = n if n in (1, 2) else 3
    return phases, s, zs, m.group(0).strip()


def parse_length(text: str) -> float:
    for raw in LENGTH_RE.findall(text):
        try:
            v = float(raw.replace(",", "."))
            if 1 <= v <= 9999:
                return v
        except ValueError:
            pass
    return 0.0


def parse_cable_mark(text: str) -> str:
    m = CABLE_MARK_RE.search(text)
    return m.group(1) if m else ""


def parse_voltage(value) -> float:
    """Принимает строку или число. Числа 0.4, 6, 10 возвращает как есть."""
    if isinstance(value, (int, float)):
        v = float(value)
        return v if 0.1 <= v <= 35 else 0.4
    text = str(value)
    m = VOLTAGE_RE.search(text)
    if m:
        return float(m.group(1).replace(",", "."))
    # Попробуем просто число в строке
    try:
        v = float(text.strip())
        if 0.1 <= v <= 35:
            return v
    except ValueError:
        pass
    return 0.4


def clean_ocr(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()
