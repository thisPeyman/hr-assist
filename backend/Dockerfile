FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Persian/English OCR is used by the existing scanned-resume extraction path.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates ghostscript ocrmypdf tesseract-ocr-eng tesseract-ocr-fas \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

RUN groupadd --system hr-assist \
    && useradd --system --gid hr-assist --home-dir /app hr-assist \
    && mkdir -p /app/.data/inbound \
    && chown -R hr-assist:hr-assist /app
USER hr-assist

EXPOSE 8000
CMD ["sh", "-c", "exec fastapi run app/main.py --host 0.0.0.0 --port ${PORT:-8000}"]
