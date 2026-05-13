# ═══════════════════════════════════════════════════════════════
# AILife Backend - NorthFrank 部署 Dockerfile
# ═══════════════════════════════════════════════════════════════
# 构建命令:  docker build -t ailife-backend .
# 运行命令:  docker run -p 8000:8000 --env-file .env ailife-backend
# ═══════════════════════════════════════════════════════════════

FROM python:3.10-slim

WORKDIR /app

# ── 系统依赖 ────────────────────────────────────────────
# ffmpeg:       音频格式转换 (Whisper 转录前置处理)
# libsndfile1:  音频文件读写支持
# gcc:          编译 Python C 扩展（asyncpg 等）
# libpq-dev:    PostgreSQL 客户端库（asyncpg 依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Python 依赖 ────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── 应用代码 ────────────────────────────────────────────
COPY . .

# ── 数据持久化目录 ──────────────────────────────────────
RUN mkdir -p /app/data

# ── NorthFrank 使用 PORT 环境变量 ──────────────────────
# 暴露端口（NorthFrank 自动检测）
EXPOSE 8000

# 生产环境启动命令
# 使用 shell 形式以支持 $PORT 环境变量（NorthFrank 动态分配）
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
