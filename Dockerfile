# galaxy-core 容器化验证（2026-10-26 测试）
# docker.io python:3.14-slim + uv sync; wheels 本地拷贝（私有 SDK 不进公开镜像源）
FROM docker.io/library/python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PROJECT_ROOT=/app

WORKDIR /app

# tgw native bundle 依赖的系统库（libpcap 等）；slim 缺的补上
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpcap0.8 \
    libssl3 \
    libkrb5-3 \
    libgssapi-krb5-2 \
    libcom-err2 \
    libk5crypto3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# uv 二进制
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 先拷依赖声明层（缓存 pip 层）
# 拷全量（验证优先；README/pyproject 同层，setuptools find src 生效）
COPY pyproject.toml uv.lock README.md ./
COPY wheels/ ./wheels/
COPY provider/ ./provider/
COPY data/src/ ./data/src/
COPY config/ ./config/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# 只装主包 + provider extra（不含 dev 组）;greenlet 供 sqlalchemy[asyncio]
RUN uv pip install --system ".[openbb]" greenlet
