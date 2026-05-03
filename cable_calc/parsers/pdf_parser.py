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
    """OCR одной страницы. Fallback на eng если rus недоступен."""
    try:
        import pytesseract
        img = page.to_image(resolution=200).original  # PIL Image
        try:
            return pytesseract.image_to_string(img, lang=lang, config="--psm 6")
        except pytesseract.TesseractError:
            return pytesseract.image_to_string(img, lang="eng", config="--psm 6")
    except Exception as e:
        return ""


def _row_from_cells(cells: List[str], row_num: int) -> Optional[CableJournalRow]:
    """Строим CableJournalRow из списка ячеек одной строки таблицы."""
    # Фильтр пустых строк
    filled = [c for c in cells if c and c.strip()]
    if len(filled) < 2:
        return None

    row = CableJournalRow(row_num=row_num, source_line=" | ".join(cells))

    # Ищем поля по содержимому ячеек
    for cell in cells:
        if not cell:
            continue
        c = clean_ocr(cell)

        # Марка кабеля
        if not row.cable_mark:
            mark = parse_cable_mark(c)
            if mark:
                row.cable_mark = mark

        # Сечение
        if not row.section_str:
            phases, s, zs, raw = parse_section(c)
            if raw:
                row.phases = phases
                row.section_mm2 = s
                row.zero_section_mm2 = zs
                row.section_str = raw

        # Длина: число 1..9999
        if row.length_m == 0.0:
            length = parse_length(c)
            if length:
                row.length_m = length

        # Напряжение
        if parse_voltage(c) != 0.4:
            row.voltage_kv = parse_voltage(c)

    # Попытка вытащить ID из первой непустой ячейки
    for cell in cells:
        if cell and cell.strip():
            row.cable_id = cell.strip()[:40]
            break

    # Если ничего не нашли — пропускаем
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
