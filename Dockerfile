# syntax=docker/dockerfile:1.7
# Free AI Gateway — production image
# Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST

FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip wheel setuptools \
 && /opt/venv/bin/pip install -r requirements.txt

FROM python:3.12-slim AS runtime
LABEL org.opencontainers.image.title="Free AI Gateway" \
      org.opencontainers.image.version="1.2.0" \
      org.opencontainers.image.authors="Mourad Soltani - 2026 Mourad Soltani Technologies (TM) @MST" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HOST=0.0.0.0 PORT=4000 WORKERS=2 \
    GATEWAY_URL=http://localhost:4000

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl tini \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --create-home --uid 10001 gateway \
 && mkdir -p /app /data && chown -R gateway:gateway /app /data

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=gateway:gateway config.yaml tracker.py client.py async_client.py healthcheck.py ./

USER gateway
VOLUME ["/data"]
EXPOSE 4000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fsS http://localhost:${PORT}/health/liveliness || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "litellm --config /app/config.yaml --host ${HOST} --port ${PORT} --num_workers ${WORKERS}"]
