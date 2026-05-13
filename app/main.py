"""
AILife Backend - FastAPI 主入口

提供对话管理、说话人识别、记账、闪念胶囊、会议记录、AI 搜索等功能。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.db import init_db, close_db, check_db_health
from app.db_migration import run_migrations
from app.routers import (
    upload, speakers, utterances, search, chat,
    flash_memos, meetings, bills, reports
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器。

    - 启动 (startup): 初始化数据库连接与表结构，执行 Alembic 迁移
    - 关闭 (shutdown): 自动清理资源
    """
    await init_db()
    await run_migrations()  # 自动执行 Alembic 迁移
    yield
    await close_db()


app = FastAPI(
    title="AILife Backend",
    description="AILife 后端 API：对话管理、说话人识别、记账、闪念胶囊、会议记录、AI 搜索",
    version="1.0.0",
    lifespan=lifespan
)

# -- CORS 配置 ------------------------------------------------
# 生产环境应将 allow_origins 替换为具体的 App 域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- 注册路由 -------------------------------------------------
app.include_router(upload.router,      prefix="/upload",       tags=["Upload"])
app.include_router(speakers.router,    prefix="/speakers",     tags=["Speakers"])
app.include_router(utterances.router,  prefix="/utterances",   tags=["Utterances"])
app.include_router(search.router,      prefix="/search",       tags=["Search"])
app.include_router(chat.router,        prefix="/chat",         tags=["Chat"])
app.include_router(flash_memos.router, prefix="/flash-memos",  tags=["Flash Memos"])
app.include_router(meetings.router,    prefix="/meetings",     tags=["Meetings"])
app.include_router(bills.router,       prefix="/bills",        tags=["Bills"])
app.include_router(reports.router,     prefix="/reports",      tags=["Reports"])


@app.get("/health", tags=["Health"])
async def health():
    """
    健康检查端点。

    用于 NorthFrank / Docker / Kubernetes 健康探针，
    检查服务运行状态和数据库连接。
    """
    db_health = await check_db_health()
    status_code = 200 if db_health["status"] == "healthy" else 503
    return {
        "status": "ok" if db_health["status"] == "healthy" else "degraded",
        "database": db_health,
    }


@app.get("/", tags=["Root"])
async def root():
    """
    根路径，返回 API 基本信息。
    """
    return {
        "name": "AILife Backend",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }
