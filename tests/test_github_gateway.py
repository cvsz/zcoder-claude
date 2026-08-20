"""tests/test_github_gateway.py

Covers infrastructure/github_api/github_gateway.py — the GitHub REST API
adapter for the Dev-tool Integrations bounded context, extracted
2026-08-20 (Phase D, Context #8). `urllib.request.urlopen` is
monkeypatched at its actual call site
(infrastructure.anthropic_api.http_client, which get()/fetch_diff()
route through) so the real retry loop and error translation run, not a
reimplementation of them — same pattern as
tests/test_claude_compliance_api.py's `_request()` tests.
"""
import io
import json
import urllib.error

import pytest

import infrastructure.anthropic_api.http_client as http_client
import infrastructure.github_api.github_gateway as gateway


class FakeResp:
    def __init__(self, body: bytes, headers=None):
        self._body = body
        self.headers = headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(url, code, body: bytes):
    return urllib.error.HTTPError(url, code, "error", {}, io.BytesIO(body))


@pytest.fixture(autouse=True)
def fresh_breaker(monkeypatch):
    """The module-level circuit breaker is shared across all GitHub calls;
    give each test its own so failures in one test don't trip the breaker
    for the next."""
    from infrastructure.anthropic_api.http_client import CircuitBreaker
    monkeypatch.setattr(gateway, "_breaker", CircuitBreaker(failure_threshold=5, reset_timeout=30))


# ── resolve_token ─────────────────────────────────────────────────────

def test_resolve_token_prefers_explicit():
    assert gateway.resolve_token("explicit-token") == "explicit-token"


def test_resolve_token_falls_back_to_env(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    assert gateway.resolve_token(None) == "env-token"


def test_resolve_token_raises_when_missing(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GitHub token not found"):
        gateway.resolve_token(None)


# ── get() ─────────────────────────────────────────────────────────────

def test_get_returns_parsed_json(monkeypatch):
    def fake_urlopen(req, timeout=None):
        assert req.full_url == "https://api.github.com/repos/x/y/pulls/1"
        assert req.headers["Authorization"] == "Bearer tok123"
        return FakeResp(json.dumps({"title": "hi"}).encode())
    monkeypatch.setattr(http_client.urllib.request, "urlopen", fake_urlopen)

    result = gateway.get("/repos/x/y/pulls/1", "tok123")
    assert result == {"title": "hi"}


def test_get_translates_401_to_runtime_error(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise _http_error(req.full_url, 401, b'{"message": "Bad credentials"}')
    monkeypatch.setattr(http_client.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="GitHub API error"):
        gateway.get("/repos/x/y/issues", "bad-token")


# ── fetch_diff() ──────────────────────────────────────────────────────

def test_fetch_diff_returns_truncated_text(monkeypatch):
    def fake_urlopen(req, timeout=None):
        return FakeResp(b"diff --git a b\n" + b"x" * 100)
    monkeypatch.setattr(http_client.urllib.request, "urlopen", fake_urlopen)

    result = gateway.fetch_diff("https://github.com/x/y/pull/1.diff", "tok", max_chars=20)
    assert len(result) == 20


def test_fetch_diff_translates_error(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise _http_error(req.full_url, 404, b"not found")
    monkeypatch.setattr(http_client.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="GitHub diff fetch error"):
        gateway.fetch_diff("https://github.com/x/y/pull/1.diff", "tok", max_chars=100)
