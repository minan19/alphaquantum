# ==============================================================================
# Alpha Quantum — Dockerfile
# Multi-stage build: builder (derleme) + runtime (çalışma)
# Base image: python:3.11-slim
# Non-root kullanıcı: appuser (uid=1000)
# PostgreSQL hazırlığı: libpq-dev / libpq5 (gelecekteki migrasyon için)
# ==============================================================================

# ------------------------------------------------------------------------------
# Aşama 1: builder — bağımlılıkları --user modunda derle
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Build araçları + libpq-dev (gelecekteki psycopg2/asyncpg derleme için)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --user -r requirements.txt

# ------------------------------------------------------------------------------
# Aşama 2: runtime — minimal, güvenli çalışma ortamı
# ------------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# libpq5: PostgreSQL istemci runtime (gelecekteki migrasyon için hazır)
# curl: HEALTHCHECK için
# appuser: non-root kullanıcı (uid=1000) — production güvenlik standardı
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser \
    && mkdir -p /data && chown -R appuser:appuser /data

# Builder aşamasından kullanıcı bağımlılıklarını taşı
COPY --from=builder /root/.local /home/appuser/.local

# Proje dosyalarını appuser sahipliğiyle kopyala
COPY --chown=appuser:appuser . .

USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH

# Python davranış ayarları
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Varsayılan SQLite veritabanı yolu — compose volume mount eder
ENV AQ_DATABASE_PATH=/data/alpha_quantum.db

EXPOSE 8000

# /api/v1/health endpoint'i mevcut (Sprint 2.2 sağlık kontrolü)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# main.py kökte (`app = create_app()`)
# --workers 1: SQLite bootstrap race condition'ı önlemek için tek worker.
# Production'da yatay ölçekleme container replica'ları (k8s/ECS) üzerinden,
# ya da bir process manager (gunicorn) ile yapılmalı.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
