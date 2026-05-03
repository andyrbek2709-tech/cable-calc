"""
PDF-парсер кабельных журналов.
Стратегия:
  1. pdfplumber: попытка извлечь структурированные таблицы (для цифровых PDF)
  2. Если нет текста — OCR через pytesseract (для сканов)
"""
import os
import re
from typing import List, Optional

import pdfplumber
from PIL import Image

from .models import CableJournalRow, ParseResult
from .utils import parse_section, parse_length, parse_cable_mark, parse_voltage, clean_ocr


def _has_text(page) -> bool:
    txt = page.extract_text() or ""
    return len(txt.strip()) > 20


def _ocr_page(page, lang: str = "rus+eng") -> str:
    """OCR одной страницы с предобработкой для улучшения распознавания."""
    try:
        import pytesseract
        from PIL import ImageOps, ImageFilter, ImageEnhance

        img = page.to_image(resolution=300).original  # Увеличиваем DPI для мелкого текста

        # Предобработка: контраст и резкость
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)

        # Попытка с русским языком и режимом 6 (унифицированный блок текста)
        try:
            result = pytesseract.image_to_string(img, lang=lang, config="--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789ВВГПКуАБГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдежзийклмнопрстуфхцчшщъыьэюя.,-–—()[] ")
            if result.strip():
                return result
        except pytesseract.TesseractError:
            pass

        # Fallback: режим 3 (автоматический) с русским
        try:
            return pytesseract.image_to_string(img, lang="rus", config="--psm 3")
        except pytesseract.TesseractError:
            # Последний fallback: английский
            return pytesseract.image_to_string(img, lang="eng", config="--psm 3")
    except Exception as e:
        return ""


def _row_from_cells(cells: List[str], row_num: int) -> Optional[CableJournalRow]:
    """Строим CableJournalRow из списка ячеек одной строки таблицы.

    Извлекает данные о кабеле из структурированной таблицы кабельного журнала:
    - Марку кабеля (ВВГ, КГ и т.д.)
    - Сечение в мм²
    - Длину в метрах
    - Напряжение
    """
    # Фильтр пустых строк
    filled = [c for c in cells if c and c.strip()]
    if len(filled) < 2:
        return None

    row = CableJournalRow(row_num=row_num, source_line=" | ".join(cells))

    # Применяем очистку ко всем ячейкам один раз
    cleaned_cells = [clean_ocr(c) if c else "" for c in cells]

    # Ищем поля по содержимому ячеек
    for cleaned in cleaned_cells:
        if not cleaned:
            continue

        # Марка кабеля (приоритет выше всех остальных)
        if not row.cable_mark:
            mark = parse_cable_mark(cleaned)
            if mark:
                row.cable_mark = mark
                continue  # Скип остальных проверок для этой ячейки

        # Сечение (формат типа "4x95+1x50" или "3x25")
        if not row.section_str:
            phases, s, zs, raw = parse_section(cleaned)
            if raw and s > 0:  # Убеждаемся что есть корректное сечение
                row.phases = phases
                row.section_mm2 = s
                row.zero_section_mm2 = zs
                row.section_str = raw
                continue

        # Длина: число от 1 до 9999 м
        if row.length_m == 0.0:
            length = parse_length(cleaned)
            if length > 0:
                row.length_m = length
                continue

        # Напряжение (кВ)
        voltage = parse_voltage(cleaned)
        if voltage != 0.4 and row.voltage_kv == 0.4:
            row.voltage_kv = voltage
            continue

    # Попытка вытащить ID из первой непустой ячейки (если ещё не установлена)
    if not row.cable_id:
        for cell in cells:
            if cell and cell.strip():
                potential_id = cell.strip()[:50]
                # Пропускаем если это уже извлеченные данные
                if not any(x in potential_id.lower() for x in ['кв', 'мм', 'м ']):
                    row.cable_id = potential_id
                    break

    # Если ничего существенного не нашли — пропускаем
    if not row.cable_mark and not row.section_str and row.length_m == 0:
        return None
    return row


def _parse_text_lines(text: str, start_row: int) -> List[CableJournalRow]:
    """Парсим OCR-текст построчно."""
    rows = []
    row_num = start_row
    for line in text.splitlines():
        line = clean_ocr(line)
        if len(line) < 5:
            continue
        cells = re.split(r'\s{2,}|\|', line)
        row = _row_from_cells(cells, row_num)
        if row:
            rows.append(row)
            row_num += 1
    return rows


def parse_pdf(path: str) -> ParseResult:
    result = ParseResult(source_file=os.path.basename(path))
    row_num = 1

    with pdfplumber.open(path) as pdf:
        result.total_pages = len(pdf.pages)

        for page_idx, page in enumerate(pdf.pages):
            if _has_text(page):
                # Цифровой PDF — берём таблицы
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for cells in table:
                            cells_str = [str(c or "").strip() for c in cells]
                            row = _row_from_cells(cells_str, row_num)
                            if row:
                                result.rows.append(row)
                                row_num += 1
                            else:
                                result.skipped_count += 1
                else:
                    # Текст есть, таблиц нет — построчно
                    txt = page.extract_text() or ""
                    new_rows = _parse_text_lines(txt, row_num)
                    result.rows.extend(new_rows)
                    row_num += len(new_rows)
            else:
                # Скан — OCR
                txt = _ocr_page(page)
                if not txt.strip():
                    result.warnings.append(f"Стр.{page_idx+1}: OCR вернул пустой результат")
                    continue
                new_rows = _parse_text_lines(txt, row_num)
                result.rows.extend(new_rows)
                row_num += len(new_rows)

    result.parsed_count = len(result.rows)
    return result
