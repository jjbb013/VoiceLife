# -*- coding: utf-8 -*-
"""AILife 应用配置模块 - NorthFrank 适配版

使用 Pydantic Settings 管理所有应用配置，从环境变量读取配置项。
适配 NorthFrank 云平台部署规范：
- PORT 环境变量由平台动态分配
- DATABASE_URL 由 PostgreSQL addon 自动注入
"""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AILife 应用配置类。

    所有配置项从环境变量读取，提供合理的默认值。
    使用 Pydantic Settings 进行类型验证和自动转换。

    Attributes:
        PORT: 服务监听端口，默认 8000（NorthFrank 动态分配）
        HOST: 服务监听地址，默认 0.0.0.0
        DATABASE_URL: PostgreSQL 连接字符串（NorthFrank 自动注入）
        KIMI_API_KEY: Moonshot Kimi API 密钥
        KIMI_MODEL: Moonshot 模型名称，默认 moonshot-v1-128k
        WHISPER_MODEL: Whisper 模型名称，默认 large-v3
        HF_TOKEN: HuggingFace Token（用于下载 pyannote 等模型）
        STORAGE_PATH: 本地存储路径（容器内持久化目录）
        CORS_ORIGINS: CORS 允许来源，默认 *（生产环境应配置具体域名）
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 服务器配置 - NorthFrank 动态分配 PORT
    PORT: int = int(os.environ.get("PORT", "8000"))  # NorthFrank 动态分配
    HOST: str = "0.0.0.0"

    # 数据库配置 - NorthFrank PostgreSQL addon 通过 DATABASE_URL 注入
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/ailife"
    )

    # AI API 配置
    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "moonshot-v1-128k"

    # 语音模型配置
    WHISPER_MODEL: str = "large-v3"

    # 功能开关
    ENABLE_DIARIZATION: bool = True  # 是否启用说话人分离（禁用可节省内存）

    # HuggingFace 配置
    HF_TOKEN: str = ""

    # 对象存储（可选）
    STORAGE_PATH: str = "/app/data"  # 本地存储路径（NorthFrank 容器内）

    # 安全配置
    CORS_ORIGINS: str = "*"  # 生产环境应配置具体域名

    def get_cors_origins(self) -> list:
        """解析 CORS_ORIGINS 为列表格式。

        Returns:
            list: CORS 允许来源列表，"*" 表示允许所有来源
        """
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


# 全局配置实例
settings = Settings()
