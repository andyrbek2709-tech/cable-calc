import re
from typing import Tuple

# Марки: правый \b -> (?!\w) чтобы работало перед цифрами (АВВГ4x16)
CABLE_MARK_RE = re.compile(
    r'(?<!\w)(ZA-?Y[CW]?V\d*|ZA-?KYW?V\d*|АВВГнг|АСБ2л|ВВГнг-LS|ВВГнг|АВВГ|ВВГ|ААБ2лШв|ААШв|АСБ|СБ|ПВС|КГ|КВВ|'
    r'КВВГЭНГ|КВВГЭ|КВВГ|КНРнг|'
    r'NYY|NYM|N2XY|NA2XY)',
    re.IGNORECASE | re.UNICODE
)

SECTION_RE = re.compile(
    r'(\d+)\s*[xхXХ]\s*(\d+(?:\.\d+)?)'
    r'(?:\s*\+\s*(\d+)\s*[xхXХ]\s*(\d+(?:\.\d+)?))?',
    re.UNICODE
)

LENGTH_RE = re.compile(r'(\d{1,5}(?:[.,]\d+)?)\s*(?:м\b|m\b)?')
VOLTAGE_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:кВ|kV)\b', re.IGNORECASE)


def _fix_ocr_section(text: str) -> str:
    """4x9541x50 -> 4x95+1x50 (OCR: '+' читается как '4')."""
    return re.sub(r'(\d+[xхXХ]\d+?)4(1[xхXХ]\d+)', r'\g<1>+\2', text)


def parse_section(text: str) -> Tuple[int, float, float, str]:
    text = _fix_ocr_section(text)
    m = SECTION_RE.search(text)
    if not m:
        return 3, 0.0, 0.0, ""
    n = int(m.group(1))
    s = float(m.group(2))
    zs = float(m.group(4)) if m.group(3) and m.group(4) else 0.0
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
