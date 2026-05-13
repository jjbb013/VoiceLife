# -*- coding: utf-8 -*-
"""数据库自动迁移模块。

应用启动时自动执行 Alembic 迁移，确保数据库 schema 最新。
"""

import logging
import subprocess
import os

logger = logging.getLogger(__name__)


async def run_migrations():
    """执行 Alembic 迁移。"""
    try:
        logger.info("正在执行数据库迁移...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        if result.returncode == 0:
            logger.info("数据库迁移成功")
        else:
            logger.error("数据库迁移失败: %s", result.stderr)
    except Exception as exc:
        logger.error("执行迁移时出错: %s", exc)
