from .models import CableJournalRow, ParseResult
from .pdf_parser import parse_pdf
from .excel_parser import parse_excel
from .word_parser import parse_word

def parse_file(path: str) -> "ParseResult":
    ext = path.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        return parse_pdf(path)
    elif ext in ("xlsx", "xls", "xlsm"):
        return parse_excel(path)
    elif ext in ("docx", "doc"):
        return parse_word(path)
    raise ValueError(f"Неподдерживаемый формат: {ext}")
