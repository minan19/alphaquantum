# ==============================================================================
# FINOS Platform — Dockerfile
# Multi-stage build: builder (derleme) + runtime (çalışma) aşamaları
# Base image: python:3.11-slim (FINOS_MASTER.md B.2 — Python 3.11 kilitleme)
# Non-root kullanıcı: appuser (uid=1000) — güvenlik gereği
# PostgreSQL hazırlığı: libpq-dev / libpq5 (P0.2 geçişine hazırlık)
# ==============================================================================

# ------------------------------------------------------------------------------
# Aşama 1: builder — bağımlılıkları --user modunda derle
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Build araçları + libpq-dev (asyncpg / psycopg2 derleme gereksinimi)
# --no-install-recommends: gereksiz paketleri dışarıda bırak
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# --user: paketleri /root/.local'e kur — runtime aşamasına kopyalanacak
# --no-cache-dir: image boyutunu küçük tut
RUN pip install --no-cache-dir --user -r requirements.txt

# ------------------------------------------------------------------------------
# Aşama 2: runtime — minimal, güvenli çalışma ortamı
# ------------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# libpq5: PostgreSQL istemci runtime kütüphanesi (asyncpg için)
# curl: HEALTHCHECK komutu için
# appuser: non-root kullanıcı (uid=1000) — production güvenlik standardı
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser

# Builder aşamasından kullanıcı bağımlılıklarını taşı
COPY --from=builder /root/.local /home/appuser/.local

# Proje dosyalarını appuser sahipliğiyle kopyala
COPY --chown=appuser:appuser . .

# Non-root kullanıcıya geç
USER appuser

# pip --user ile kurulan paketlerin PATH'i
ENV PATH=/home/appuser/.local/bin:$PATH

# Python davranış ayarları (production standardı)
# PYTHONUNBUFFERED: stdout/stderr'i buffer'lamadan yaz — log akışı için kritik
# PYTHONDONTWRITEBYTECODE: .pyc dosyası üretme — container'da gereksiz
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Sağlık kontrolü — /api/v1/health endpoint'i (mevcut, ALPHA_QUANTUM_AUDIT.md onaylı)
# interval: 30s, timeout: 5s, retries: 3 başarısız → unhealthy
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Giriş noktası: proje kökündeki main.py (from app import create_app)
# NOT: FINOS_MASTER.md C.1 şablonu app.main:app diyor — ancak mevcut yapı
# main.py'ı proje kökünde tutuyor. PostgreSQL geçişinde app/main.py'a taşınınca
# bu satır app.main:app olarak güncellenecek (Hafta 2 refactor).
# --workers 2: production için; docker-compose.yml geliştirme modunda override eder.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
