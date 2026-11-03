from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path / "local_data"))

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    return TestClient(app)
