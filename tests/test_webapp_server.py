"""tests/test_webapp_server.py — webapp/backend/server.py

Uses FastAPI's TestClient (httpx-based, no real network/socket). The
application-layer generation functions (chat_turn / stream_chat_turn) are
monkeypatched so no real API calls happen anywhere in this file, same
convention as tests/test_coder.py. Since the 2026-08-22 Phase F audit,
server.py goes through application/messaging_service instead of
core_gateway.Coder / raw anthropic — these patches were re-pointed
accordingly (the standard "second repoint" pattern).
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import webapp.backend.server as server  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_state():
    """Each test gets an empty session store and a fresh rate-limit
    bucket, so tests can't leak state into each other via the
    process-local dicts server.py uses."""
    server._sessions.clear()
    server._rate_buckets.clear()
    yield
    server._sessions.clear()
    server._rate_buckets.clear()


@pytest.fixture
def client():
    return TestClient(server.app)


def test_version_endpoint(client):
    resp = client.get("/api/version")
    assert resp.status_code == 200
    assert "version" in resp.json()


def test_chat_rejects_empty_prompt(client):
    resp = client.post("/api/chat", json={"prompt": "   "})
    assert resp.status_code == 400


def test_chat_rejects_out_of_range_temperature(client):
    resp = client.post("/api/chat", json={"prompt": "hi", "temperature": 5.0})
    assert resp.status_code == 422  # pydantic validation error


def test_chat_rejects_out_of_range_max_tokens(client):
    resp = client.post("/api/chat", json={"prompt": "hi", "max_tokens": 0})
    assert resp.status_code == 422


def test_chat_happy_path(client, monkeypatch):
    monkeypatch.setattr(server.messaging_service, "chat_turn", lambda prompt, **k: "mock reply")
    resp = client.post("/api/chat", json={"prompt": "hello", "api_key": "sk-ant-test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "mock reply"
    assert "session_id" in data


def test_chat_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(server.messaging_service, "chat_turn", lambda prompt, **k: "ok")
    monkeypatch.setattr(server, "_RATE_LIMIT", 2)
    for _ in range(2):
        resp = client.post("/api/chat", json={"prompt": "hi", "api_key": "sk-ant-test"})
        assert resp.status_code == 200
    resp = client.post("/api/chat", json={"prompt": "hi", "api_key": "sk-ant-test"})
    assert resp.status_code == 429


def test_sessions_list_empty_by_default(client):
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_sessions_list_reflects_chat_history(client, monkeypatch):
    monkeypatch.setattr(server.messaging_service, "chat_turn", lambda prompt, **k: "reply text")
    chat_resp = client.post("/api/chat", json={"prompt": "what is python", "api_key": "sk-ant-test"})
    sid = chat_resp.json()["session_id"]

    listing = client.get("/api/sessions").json()
    assert len(listing) == 1
    assert listing[0]["session_id"] == sid
    assert listing[0]["turns"] == 1
    assert "what is python" in listing[0]["preview"]


def test_sessions_get_and_delete(client, monkeypatch):
    monkeypatch.setattr(server.messaging_service, "chat_turn", lambda prompt, **k: "reply")
    sid = client.post("/api/chat", json={"prompt": "hi", "api_key": "sk-ant-test"}).json()["session_id"]

    got = client.get(f"/api/sessions/{sid}")
    assert got.status_code == 200
    assert len(got.json()["history"]) == 2

    deleted = client.delete(f"/api/sessions/{sid}")
    assert deleted.status_code == 200
    assert client.get(f"/api/sessions/{sid}").status_code == 404


def test_chat_stream_requires_api_key(client, monkeypatch):
    monkeypatch.setattr(server.Config, "get", lambda self, key, default=None: None)
    resp = client.post("/api/chat/stream", json={"prompt": "hi"})
    assert resp.status_code == 400


def test_chat_stream_yields_tokens_and_done(client, monkeypatch):
    def fake_stream_chat_turn(prompt, api_key, model, system=None, history=None,
                              temperature=None, max_tokens=4096, on_text=None):
        assert prompt == "hi"
        for chunk in ("Hel", "lo", "!"):
            on_text(chunk)
        return "Hello!"

    monkeypatch.setattr(server.messaging_service, "stream_chat_turn", fake_stream_chat_turn)

    resp = client.post("/api/chat/stream", json={"prompt": "hi", "api_key": "sk-ant-test"})
    assert resp.status_code == 200
    body = resp.text
    assert '"type": "token"' in body or '"type":"token"' in body
    assert "Hel" in body and "lo" in body and '"type": "done"' in body


def test_chat_stream_error_event_when_service_raises(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(server.messaging_service, "stream_chat_turn", boom)
    resp = client.post("/api/chat/stream", json={"prompt": "hi", "api_key": "sk-ant-test"})
    assert resp.status_code == 200
    assert '"type": "error"' in resp.text
    assert "network down" in resp.text


def test_streamed_turn_is_persisted_to_session_store(client, monkeypatch):
    def fake_stream_chat_turn(prompt, api_key, model, system=None, history=None,
                              temperature=None, max_tokens=4096, on_text=None):
        on_text("streamed reply")
        return "streamed reply"

    monkeypatch.setattr(server.messaging_service, "stream_chat_turn", fake_stream_chat_turn)
    resp = client.post("/api/chat/stream", json={"prompt": "hi", "api_key": "sk-ant-test"})
    assert resp.status_code == 200
    listing = client.get("/api/sessions").json()
    assert len(listing) == 1
    got = client.get(f"/api/sessions/{listing[0]['session_id']}")
    roles = [m["role"] for m in got.json()["history"]]
    assert roles == ["user", "assistant"]


def test_server_has_no_presentation_layer_imports():
    """Architectural rule (exec-planning §2/§7): non-CLI front ends call the
    application layer, never interfaces/cli. Guard the webapp against
    regressing to dispatcher/cmd_* imports."""
    import inspect

    src = inspect.getsource(server)
    assert "from interfaces" not in src
    assert "import interfaces" not in src
