from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path / "local_data"))

    # Settings.model_config hardcodes env_file=<repo root>/.env, so
    # Settings() reads the real .env whenever a key is absent from
    # os.environ - monkeypatch.delenv alone does NOT hide a real .env value
    # from pydantic-settings, it only removes the os.environ override. Force
    # both to fixed, test-safe values here so the suite's behavior never
    # depends on whether (or what) the developer's own .env contains;
    # individual tests still override these via their own monkeypatch calls
    # exactly as before.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GEMINI_DEFAULT_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    return TestClient(app)
