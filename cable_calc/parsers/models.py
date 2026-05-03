from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class CableJournalRow:
    """Единая строка кабельного журнала."""
    row_num: int = 0
    cable_id: str = ""        # Обозначение (позиция) кабеля
    cable_name: str = ""      # Наименование/назначение
    from_point: str = ""      # Начало
    to_point: str = ""        # Конец
    cable_mark: str = ""      # Марка кабеля
    section_str: str = ""     # Сечение как строка: "3x16", "4x95+1x50"
    phases: int = 3           # Кол-во фаз (из сечения)
    section_mm2: float = 0.0  # Основное сечение, мм²
    zero_section_mm2: float = 0.0  # Сечение нуля, мм²
    length_m: float = 0.0     # Длина, м
    voltage_kv: float = 0.4   # Напряжение, кВ
    notes: str = ""
    source_line: str = ""     # Исходная строка (для отладки)

@dataclass
class ParseResult:
    rows: List[CableJournalRow] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_file: str = ""
    total_pages: int = 0
    parsed_count: int = 0
    skipped_count: int = 0
