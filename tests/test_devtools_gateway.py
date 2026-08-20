"""tests/test_devtools_gateway.py

Covers infrastructure/anthropic_api/devtools_gateway.py — real HTTP calls
for the Dev-tool Integrations bounded context, extracted 2026-08-20
(Phase D, Context #8). A fake anthropic.Anthropic client, a fake Coder,
and a monkeypatched urllib.request.urlopen are substituted in — no real
network, no real SDK calls.
"""
import urllib.error

import infrastructure.anthropic_api.devtools_gateway as gateway


class FakeContentBlock:
    def __init__(self, text):
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeContentBlock(text)]


class FakeMessages:
    def __init__(self, response_text):
        self._text = response_text
        self.create_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return FakeResponse(self._text)


class FakeAnthropicClient:
    _next_text = "response"

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.messages = FakeMessages(FakeAnthropicClient._next_text)


def _install_fake_anthropic(monkeypatch, text):
    FakeAnthropicClient._next_text = text
    monkeypatch.setattr(gateway.anthropic, "Anthropic", FakeAnthropicClient)


# ── git_generate / github_generate ───────────────────────────────────

def test_git_generate_returns_stripped_text(monkeypatch):
    _install_fake_anthropic(monkeypatch, "  a commit message  \n")
    assert gateway.git_generate("key", "claude-sonnet-5", "prompt") == "a commit message"


def test_github_generate_uses_given_system_prompt(monkeypatch):
    seen = {}

    class RecordingMessages(FakeMessages):
        def create(self, **kwargs):
            seen.update(kwargs)
            return super().create(**kwargs)

    _install_fake_anthropic(monkeypatch, "review text")
    monkeypatch.setattr(gateway.anthropic.Anthropic, "__init__",
                        lambda self, api_key=None: setattr(self, "messages", RecordingMessages("review text")))
    result = gateway.github_generate("key", "claude-sonnet-5", "SYSTEM X", "user text")
    assert result == "review text"
    assert seen["system"] == "SYSTEM X"


# ── fetch_page / _fetch_retrying ──────────────────────────────────────

class FakeHTTPResp:
    def __init__(self, body: bytes):
        self._body = body
        self.headers = type("H", (), {"get_content_charset": lambda self: "utf-8"})()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_page_success(monkeypatch):
    html = b"<html><body><p>Hello <a href='/x'>link</a></p></body></html>"
    monkeypatch.setattr(gateway.urllib.request, "urlopen", lambda req, timeout=None: FakeHTTPResp(html))
    text, links, error = gateway.fetch_page("https://example.com")
    assert error is None
    assert "Hello" in text
    assert links == [("link", "/x")]


def test_fetch_page_http_error_returns_error_string(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "not found", {}, None)
    monkeypatch.setattr(gateway.urllib.request, "urlopen", fake_urlopen)
    text, links, error = gateway.fetch_page("https://example.com/missing")
    assert text is None
    assert links == []
    assert "404" in error


def test_fetch_page_connection_error_returns_error_string(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise ConnectionError("refused")
    monkeypatch.setattr(gateway.urllib.request, "urlopen", fake_urlopen)
    text, links, error = gateway.fetch_page("https://example.com/down")
    assert text is None
    assert "fetching https://example.com/down" in error


# ── make_coder / browse_decide ────────────────────────────────────────

def test_make_coder_constructs_real_coder(monkeypatch):
    coder = gateway.make_coder("key", "claude-sonnet-5", temperature=0.5, max_tokens=512)
    assert coder.model == "claude-sonnet-5"
    assert coder.temperature == 0.5


def test_browse_decide_calls_generate_with_system_prompt():
    calls = []

    class FakeCoder:
        def generate(self, prompt, system=None, history=None):
            calls.append((prompt, system, history))
            return '{"action": "answer", "text": "done"}'

    result = gateway.browse_decide(FakeCoder(), "turn prompt")
    assert result == '{"action": "answer", "text": "done"}'
    assert calls[0][0] == "turn prompt"
    assert calls[0][1] == gateway.BROWSE_SYSTEM_PROMPT
    assert calls[0][2] == []
