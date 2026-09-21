FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY worker ./worker
COPY engine ./engine
COPY frontend ./frontend
COPY README.md .
COPY .env.example .

RUN useradd -m -u 10001 appuser && \
    mkdir -p /data/uploads /data/versions && \
    chown -R appuser:appuser /app /data

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]