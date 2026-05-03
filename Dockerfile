FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-rus \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY cable_calc/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cable_calc .

EXPOSE 8000
CMD ["python", "main.py"]
