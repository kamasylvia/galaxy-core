# galaxy-web: Finanalyzer frontend (OpenBB Workspace app backend)
# py3.12 (openbb-provider needs >=3.12; akshare plugins are 1.x-only,
# so openbb-core stays 1.4.8 and the amazingdata fetcher is vendored).
FROM docker.io/python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libcurl4-openssl-dev \
        libssl-dev \
        libffi-dev \
        libxml2-dev \
        libxslt-dev \
        python3-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*
# uv for reproducible installs from uv.lock
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# deps first (cache-friendly): pyproject + lock, no source
COPY pyproject.toml uv.lock .python-version ./
RUN /bin/uv sync --frozen --no-dev --no-install-project

# app source (vendor/ included: no external path deps anymore)
COPY . .

# project itself into the venv (editable-style: importable)
RUN /bin/uv sync --frozen --no-dev

EXPOSE 8000

# PG + credentials via env / mounted files (see docker-compose.yml + docs/deploy.md)
CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
