FROM python:3.11-alpine AS builder

WORKDIR /build

RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    rust

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-alpine

RUN apk add --no-cache \
    libffi \
    openssl \
    libstdc++

WORKDIR /app

COPY --from=builder /install /usr/local

RUN adduser -D -s /bin/sh appuser

COPY --chown=appuser:appuser . /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:8000/ || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
