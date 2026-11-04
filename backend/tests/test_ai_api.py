from __future__ import annotations

from app.ai import service as ai_service


def test_list_models_includes_default(client):
    resp = client.get("/api/ai/models")
    assert resp.status_code == 200
    models = resp.json()
    assert len(models) >= 1
    assert any(m["is_default"] for m in models)
    assert sum(1 for m in models if m["is_default"]) == 1


def test_get_config_defaults_to_registry_default(client):
    resp = client.get("/api/ai/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["selected_model"] == "gemini-2.0-flash"
    assert body["temperature"] == 0.2


def test_update_config_persists(client):
    resp = client.put("/api/ai/config", json={"selected_model": "gemini-1.5-pro", "temperature": 0.7})
    assert resp.status_code == 200
    body = resp.json()
    assert body["selected_model"] == "gemini-1.5-pro"
    assert body["temperature"] == 0.7

    resp2 = client.get("/api/ai/config")
    assert resp2.json()["selected_model"] == "gemini-1.5-pro"


def test_update_config_rejects_unknown_model(client):
    resp = client.put("/api/ai/config", json={"selected_model": "not-a-real-model"})
    assert resp.status_code == 422


def test_test_connection_not_configured_returns_success_false(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    ai_service.reset_client()

    resp = client.post("/api/ai/test-connection")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "GEMINI_API_KEY" in body["error"]

    get_settings.cache_clear()


def test_usage_stats_empty_by_default(client):
    resp = client.get("/api/ai/usage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_requests"] == 0
    assert body["by_model"] == {}


def test_record_usage_reflected_in_usage_endpoint(client):
    ai_service.record_usage("gemini-2.0-flash", {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})

    resp = client.get("/api/ai/usage")
    body = resp.json()
    assert body["total_requests"] == 1
    assert body["total_tokens"] == 150
    assert body["by_model"]["gemini-2.0-flash"]["total_tokens"] == 150

    ai_service.record_usage("gemini-2.0-flash", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    resp2 = client.get("/api/ai/usage")
    body2 = resp2.json()
    assert body2["total_requests"] == 2
    assert body2["by_model"]["gemini-2.0-flash"]["total_tokens"] == 165
    assert body2["by_model"]["gemini-2.0-flash"]["request_count"] == 2
