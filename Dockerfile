# HoopLife NBA - Railway (veya herhangi bir Docker sunucusu) icin.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PRODUCTION=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Tek surec: mock draft durumu ve onbellekler bellekte tutuluyor. Istekler
# bu surecin is parcacigi havuzunda paralel isleniyor.
CMD ["sh", "-c", "uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 30"]
