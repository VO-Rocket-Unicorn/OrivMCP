# === base ===
FROM python:3.12-slim-bookworm

ARG BUILD_DATE
ARG GIT_SHA
ARG VERSION

LABEL org.opencontainers.image.title="OCR Extraction" \
    org.opencontainers.image.description="OCR extraction service for US ORIV documents" \
    org.opencontainers.image.vendor="Oriv" \
    org.opencontainers.image.created="${BUILD_DATE}" \
    org.opencontainers.image.revision="${GIT_SHA}" \
    org.opencontainers.image.version="${VERSION}"

# ---- runtime env hardening ----
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_PYTHON_PREFERENCE=only-system \
    PYTHONFAULTHANDLER=1

# ---- system dependencies (minimal) ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# ---- install uv globally (not in /root) ----
RUN curl -fsSL https://astral.sh/uv/install.sh | \
    UV_INSTALL_DIR=/usr/local/bin sh

# ---- create non-root user ----
RUN useradd \
    --system \
    --uid 10001 \
    --create-home \
    --shell /usr/sbin/nologin \
    appuser

WORKDIR /app

# ---- copy project files ----
COPY . /app

# ---- ensure correct ownership ----
RUN chown -R 10001:10001 /app

# ---- drop privileges early ----
USER 10001:10001

# ---- dependency resolution as non-root ----
RUN uv sync --locked --link-mode=copy

# ---- expose port if this is an API ----
# EXPOSE 8000

# ---- runtime command ----
CMD ["uv", "run", "app"]