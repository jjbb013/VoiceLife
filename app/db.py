# -*- coding: utf-8 -*-
"""
AILife 数据库连接层 - NorthFrank PostgreSQL 适配版

使用 asyncpg 连接池提供原生 PostgreSQL 访问。
NorthFrank PostgreSQL addon 通过 DATABASE_URL 环境变量注入连接信息。

pgvector 扩展支持向量类型，用于声纹相似度搜索和语义检索。

数据库接口规范（所有子代理必须遵循）：
    from app.db import db

    # db 对象提供以下方法：
    # - db.fetch(query, *args) -> list[asyncpg.Record]
    # - db.fetchrow(query, *args) -> asyncpg.Record | None
    # - db.fetchval(query, *args) -> Any
    # - db.execute(query, *args) -> str (INSERT/UPDATE 返回如 'INSERT 0 1')
    # - db.executemany(query, argslist) -> str
    # - db.acquire() -> 连接上下文管理器 (用于事务)

    使用示例：
        rows = await db.fetch("SELECT * FROM speakers WHERE user_id = $1", user_id)
        row = await db.fetchrow(
            "INSERT INTO speakers (user_id, name) VALUES ($1, $2) RETURNING *",
            uid, name
        )
        await db.execute("UPDATE speakers SET name = $1 WHERE id = $2", name, spk_id)
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

import asyncpg
from asyncpg import Pool, Record

from app.config import settings

logger = logging.getLogger(__name__)

# 全局连接池
_pool: Optional[Pool] = None


class Database:
    """数据库操作封装类。

    提供与 asyncpg 连接池的便捷交互接口，所有路由通过此类的实例访问数据库。
    所有方法均使用 $1, $2, ... 作为参数占位符（PostgreSQL 原生语法）。
    """

    async def fetch(self, query: str, *args) -> List[Record]:
        """执行查询，返回多条记录。

        Args:
            query: SQL 查询语句，使用 $1, $2, ... 作为参数占位符
            *args: 查询参数

        Returns:
            List[Record]: 查询结果记录列表
        """
        global _pool
        async with _pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[Record]:
        """执行查询，返回单条记录或 None。

        Args:
            query: SQL 查询语句，使用 $1, $2, ... 作为参数占位符
            *args: 查询参数

        Returns:
            Optional[Record]: 单条记录，无结果时返回 None
        """
        global _pool
        async with _pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args) -> Any:
        """执行查询，返回单个标量值。

        Args:
            query: SQL 查询语句，使用 $1, $2, ... 作为参数占位符
            *args: 查询参数

        Returns:
            Any: 单个标量值
        """
        global _pool
        async with _pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute(self, query: str, *args) -> str:
        """执行 INSERT/UPDATE/DELETE，返回操作结果字符串。

        Args:
            query: SQL 语句，使用 $1, $2, ... 作为参数占位符
            *args: 语句参数

        Returns:
            str: 操作结果字符串（如 'INSERT 0 1', 'UPDATE 3'）
        """
        global _pool
        async with _pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def executemany(self, query: str, argslist: List[tuple]) -> str:
        """批量执行 SQL 语句。

        Args:
            query: SQL 语句模板，使用 $1, $2, ... 作为参数占位符
            argslist: 参数元组列表

        Returns:
            str: 操作结果字符串
        """
        global _pool
        async with _pool.acquire() as conn:
            return await conn.executemany(query, argslist)

    async def acquire(self):
        """获取连接上下文管理器（用于事务）。

        用法示例：
            async with db.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("INSERT INTO ...", ...)
                    await conn.execute("UPDATE ...", ...)

        Returns:
            异步上下文管理器，yield asyncpg.Connection
        """
        return _pool.acquire()


# 全局 Database 实例 - 所有路由通过此实例访问数据库
db = Database()


async def _init_connection(conn: asyncpg.Connection):
    """连接初始化回调。

    在每个新连接上执行初始化操作：
    1. 设置搜索路径为 public
    """
    await conn.execute("SET search_path TO public")


async def create_pool() -> Pool:
    """创建 asyncpg 连接池。

    从 DATABASE_URL 环境变量解析连接参数。
    NorthFrank 会自动注入 DATABASE_URL。

    Returns:
        Pool: asyncpg 连接池实例

    Raises:
        RuntimeError: 当连接池创建失败时
    """
    try:
        pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
            init=_init_connection,
        )
        logger.info("PostgreSQL 连接池创建成功")
        return pool
    except Exception as exc:
        logger.error("创建连接池失败: %s", exc)
        raise RuntimeError(f"数据库连接失败: {exc}") from exc


async def init_db() -> None:
    """初始化数据库。

    1. 创建连接池
    2. 启用 pgvector 扩展（如果不存在）
    3. 启用 uuid-ossp 扩展（如果不存在）
    4. 验证连接

    Raises:
        RuntimeError: 当初始化过程中发生错误时
    """
    global _pool

    # 脱敏日志输出（隐藏密码）
    safe_url = settings.DATABASE_URL
    if "://" in safe_url and "@" in safe_url:
        # postgresql://user:pass@host -> postgresql://user:***@host
        prefix, rest = safe_url.split("://", 1)
        if "@" in rest:
            creds, hostpart = rest.split("@", 1)
            safe_url = f"{prefix}://{creds.split(':')[0]}:***@{hostpart}"

    logger.info("正在初始化数据库连接... DATABASE_URL=%s", safe_url)

    _pool = await create_pool()

    # 启用 pgvector 和 uuid-ossp 扩展
    async with _pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
        logger.info("pgvector 和 uuid-ossp 扩展已就绪")

    logger.info("数据库初始化完成")


async def close_db() -> None:
    """关闭数据库连接池。

    优雅关闭所有连接，清理资源。
    """
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("数据库连接池已关闭")


async def check_db_health() -> dict[str, Any]:
    """检查数据库连接健康状态。

    执行简单的 SELECT 1 查询验证数据库连接。

    Returns:
        dict: 包含 status 和 database 键的健康状态字典
    """
    try:
        val = await db.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:
        logger.error("数据库健康检查失败: %s", exc)
        return {"status": "unhealthy", "error": str(exc)}


def get_pool() -> Pool:
    """获取连接池实例（用于 Alembic 等同步代码）。

    Returns:
        Pool: 当前全局连接池实例

    Raises:
        RuntimeError: 连接池尚未初始化时
    """
    if _pool is None:
        raise RuntimeError("数据库连接池尚未初始化，请先调用 init_db()")
    return _pool
