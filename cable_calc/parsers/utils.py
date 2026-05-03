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

# Regex для вложенных сечений: 2х(1х20+1х70), 4х(1х150+1х50)
NESTED_SECTION_RE = re.compile(
    r'(\d+)\s*[xхXХ]\s*\('  # "Nх("
    r'(\d+)\s*[xхXХ]\s*(\d+(?:[.,]\d+)?)'  # "Nх основное"
    r'(?:\s*[\+\-]\s*(\d+)\s*[xхXХ]\s*(\d+(?:[.,]\d+)?))?\s*\)',  # "Nх доп"
    re.UNICODE
)

# Основной regex для простых сечений: 3х16, 4х95+1х50, 95, 2.5
SECTION_RE = re.compile(
    r'(?:(\d+)\s*[xхXХ]\s*)?'  # опциональное "Nх" (количество проводов)
    r'(\d+(?:[.,]\d+)?)'  # основное сечение (обязательное)
    r'(?:\s*[\+\-]\s*(\d+(?:[.,]\d+)?))?',  # опциональное доп сечение
    re.UNICODE
)

LENGTH_RE = re.compile(r'(\d{1,5}(?:[.,]\d+)?)\s*(?:м\b|m\b)?')
VOLTAGE_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:кВ|kV)\b', re.IGNORECASE)


def _normalize_section_text(text: str) -> str:
    """Нормализует текст сечения перед парсингом."""
    # Удалить мм² и прочие единицы
    text = text.replace('мм²', '').replace('мм', '')
    # Нормализовать латинскую/кириллицу X
    text = text.replace('Х', 'х').replace('х', 'x')
    # Пробелы после x
    text = re.sub(r'x\s+', 'x', text, flags=re.IGNORECASE)
    # Нормализовать пробелы
    text = re.sub(r'\s+', ' ', text).strip()
    # Запятые в числах → точки
    text = text.replace(',', '.')
    return text


def _fix_ocr_section(text: str) -> str:
    """Исправляет частые OCR ошибки в сечениях кабеля."""
    text = _normalize_section_text(text)

    # Ошибка: '+' читается как '4': 4x9541x50 -> 4x95+1x50
    text = re.sub(r'(\d+x\d+\.?\d*)4(1x\d+)', r'\1+\2', text, flags=re.IGNORECASE)
    # Ошибка: '0' вместо 'x': 4095+1050 -> 4x95+1x50
    text = re.sub(r'(\d)0(\d+\.?\d*)[+\-](\d)0(\d+)', r'\1x\2+\3x\4', text)

    return text


def parse_section(text: str) -> Tuple[int, float, float, str]:
    """Парсит сечение кабеля из текста. Поддерживает форматы:
    - Простые: 95, 2.5, 16
    - С жилами: 3x16, 4x95, 2x120
    - Сложные: 3x16+1x10, 4x95+1x50
    - Вложенные: 2x(1x20+1x70), 4x(1x150+1x50)
    """
    text = _fix_ocr_section(text)

    # 1. Сначала пробуем вложенные сечения: 2х(1х20+1х70)
    m = NESTED_SECTION_RE.search(text)
    if m:
        # groups: (outer_n, inner_n1, main, inner_n2, aux)
        outer_n = int(m.group(1))  # например, 2
        # основное сечение - это сечение первой жилы в скобках
        s_str = m.group(3).replace(',', '.')
        s = float(s_str)
        zs = 0.0
        if m.group(5):  # если есть дополнительное сечение
            zs_str = m.group(5).replace(',', '.')
            zs = float(zs_str)
        phases = outer_n if outer_n in (1, 2) else 3
        return phases, s, zs, m.group(0).strip()

    # 2. Затем пробуем обычные сечения
    m = SECTION_RE.search(text)
    if not m:
        return 3, 0.0, 0.0, ""

    # группа 1 = количество проводов (опционально)
    n = int(m.group(1)) if m.group(1) else 3
    # группа 2 = основное сечение
    s_str = m.group(2).replace(',', '.')
    s = float(s_str)
    zs = 0.0
    # группа 3 = доп сечение (опционально)
    if m.group(3):
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
