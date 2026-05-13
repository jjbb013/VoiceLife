"""
pytest 共享配置和 fixtures。

所有测试文件可自动使用该模块中定义的 fixture，
无需显式 import。
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """
    提供 FastAPI TestClient 实例，用于发送模拟 HTTP 请求。

    Usage:
        def test_health(client):
            response = client.get("/health")
            assert response.status_code == 200
    """
    return TestClient(app)


@pytest.fixture
def sample_user_id():
    """
    提供一个固定的测试用户 UUID。

    在测试路由中可作为默认 user_id 参数使用。
    """
    return "00000000-0000-0000-0000-000000000001"
