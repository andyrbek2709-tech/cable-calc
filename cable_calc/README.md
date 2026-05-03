# Расчёт кабелей до 1кВ

Веб-приложение для расчёта кабелей по методике **МЭК 60364-5-52**.

## Возможности
- **Подбор сечения** по нагрузке (ток, ΔU, КЗ, защита)
- **Проверка сечения** кабельного журнала
- **Максимальная нагрузка** для заданного сечения
- **Парсинг журналов**: PDF (OCR), Excel, Word
- **Отчёты**: Excel с методологией, Word с формулами
- **Подсказки** при ошибках: что изменить и на сколько

## Быстрый старт

```bash
pip install -r requirements.txt
cd cable_calc
python main.py
# Открыть: http://localhost:8000
```

## API
- `POST /api/v1/calculate/single` — одиночный расчёт
- `POST /api/v1/calculate/check` — проверка сечения
- `POST /api/v1/calculate/max_load` — макс. нагрузка
- `POST /api/v1/calculate/batch` — пакетный расчёт
- `POST /api/v1/parse/journal` — парсинг файла (PDF/xlsx/docx)
- `POST /api/v1/report/excel` — скачать Excel-отчёт
- `POST /api/v1/report/word` — скачать Word-отчёт
- `GET  /api/v1/methods` — справочник методов прокладки
- `GET  /docs` — Swagger UI

## OCR для PDF-журналов
Для сканированных PDF нужен tesseract с русским языком:
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-rus
```

## Структура
```
cable_calc/
├── engine/         # Расчётный движок (МЭК 60364-5-52)
│   ├── tables.py   # Справочные таблицы
│   └── calc.py     # Функции расчёта
├── parsers/        # Парсеры журналов
├── reports/        # Генераторы Excel/Word
├── api/            # FastAPI маршруты
├── static/         # Frontend (React CDN)
└── main.py         # Точка входа
```
