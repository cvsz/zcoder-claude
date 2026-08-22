"""tests/unit/application/test_messaging_service.py

Covers application/messaging_service.py — the use-case layer added
2026-08-15 (Phase B) so interfaces/cli/commands/messaging_commands.py
doesn't call infrastructure/anthropic_api/messaging_gateway.py directly.
These test the service functions as plain data in/data out, with fake
gateway classes substituted in — no print() capture, no real network.
"""

import json

import application.messaging_service as service

# ── streaming ────────────────────────────────────────────────────────────


def test_chat_turn_builds_coder_with_request_params(monkeypatch):
    calls = {}

    class FakeCoder:
        def __init__(
            self, api_key=None, model=None, temperature=None, max_tokens=None, personality_style=None
        ):
            calls["init"] = (api_key, model, temperature, max_tokens, personality_style)

        def generate(self, prompt, system=None, file_content=None, history=None):
            calls["generate"] = (prompt, system, history)
            return "reply"

    monkeypatch.setattr(service, "Coder", FakeCoder)
    result = service.chat_turn(
        "hi",
        api_key="k",
        model="claude-opus-5",
        temperature=0.7,
        max_tokens=1024,
        system="be brief",
        history=[{"role": "user", "content": "earlier"}],
        personality_style="concise",
    )
    assert result == "reply"
    assert calls["init"] == ("k", "claude-opus-5", 0.7, 1024, "concise")
    assert calls["generate"] == (
        "hi",
        "be brief",
        [{"role": "user", "content": "earlier"}],
    )


def test_chat_turn_defaults_and_empty_history(monkeypatch):
    calls = {}

    class FakeCoder:
        def __init__(
            self, api_key=None, model=None, temperature=None, max_tokens=None, personality_style=None
        ):
            calls["init"] = (api_key, model)

        def generate(self, prompt, system=None, history=None):
            calls["generate"] = (prompt, system, history)
            return "ok"

    monkeypatch.setattr(service, "Coder", FakeCoder)
    assert service.chat_turn("hi") == "ok"
    assert calls["init"] == (None, "claude-sonnet-5")
    assert calls["generate"] == ("hi", None, [])


def test_stream_chat_turn_passes_history_temperature_and_on_text(monkeypatch):
    calls = {}
    seen_chunks = []

    class FakeStreamCoder:
        def __init__(self, api_key, model, max_tokens=4096):
            calls["init"] = (api_key, model, max_tokens)

        def stream(
            self, prompt, system=None, tools=None, show_thinking=False, history=None, temperature=None, **cb
        ):
            calls["stream"] = {
                "prompt": prompt,
                "system": system,
                "history": history,
                "temperature": temperature,
                "on_text": cb.get("on_text"),
            }
            return "full text"

    monkeypatch.setattr(service, "StreamCoder", FakeStreamCoder)
    on_text_cb = seen_chunks.append
    result = service.stream_chat_turn(
        "hi",
        api_key="k",
        model="claude-sonnet-5",
        system="s",
        history=[{"role": "assistant", "content": "prev"}],
        temperature=0.5,
        max_tokens=2048,
        on_text=on_text_cb,
    )
    assert result == "full text"
    assert calls["init"] == ("k", "claude-sonnet-5", 2048)
    assert calls["stream"]["history"] == [{"role": "assistant", "content": "prev"}]
    assert calls["stream"]["temperature"] == 0.5
    assert calls["stream"]["on_text"] is on_text_cb


def test_stream_chat_turn_omits_temperature_when_none(monkeypatch):
    calls = {}

    class FakeStreamCoder:
        def __init__(self, api_key, model, max_tokens=4096):
            pass

        def stream(self, prompt, system=None, history=None, temperature=None, **cb):
            calls["temperature"] = temperature
            return ""

    monkeypatch.setattr(service, "StreamCoder", FakeStreamCoder)
    service.stream_chat_turn("hi", api_key="k", model="m")
    assert calls["temperature"] is None


def test_stream_text_plain(monkeypatch):
    calls = {}

    class FakeStreamCoder:
        def __init__(self, api_key, model):
            calls["init"] = (api_key, model)

        def stream(self, prompt, system=None, show_thinking=False, **cb):
            calls["stream"] = (prompt, system, show_thinking)
            return "hello"

    monkeypatch.setattr(service, "StreamCoder", FakeStreamCoder)
    result = service.stream_text("hi", "k", "claude-sonnet-5")
    assert result == "hello"
    assert calls["stream"] == ("hi", None, False)


def test_stream_text_with_file_content_uses_file_analysis(monkeypatch):
    calls = {}

    class FakeStreamCoder:
        def __init__(self, api_key, model):
            pass

        def stream_file_analysis(self, file_content, prompt, system=None, **cb):
            calls["args"] = (file_content, prompt, system)
            return "analysed"

    monkeypatch.setattr(service, "StreamCoder", FakeStreamCoder)
    result = service.stream_text("summarise", "k", "claude-sonnet-5", file_content="code here")
    assert result == "analysed"
    assert calls["args"] == ("code here", "summarise", None)


def test_stream_with_tools_passes_through(monkeypatch):
    class FakeStreamCoder:
        def __init__(self, api_key, model):
            pass

        def stream_with_tools(self, prompt, tools, system=None, **cb):
            return {"text": "", "tool_calls": tools, "stop_reason": "tool_use", "stop_details": None}

    monkeypatch.setattr(service, "StreamCoder", FakeStreamCoder)
    result = service.stream_with_tools("q", [{"name": "t1"}], "k", "claude-sonnet-5")
    assert result["tool_calls"] == [{"name": "t1"}]


# ── structured outputs ───────────────────────────────────────────────────


def test_generate_structured_json_object_mode(monkeypatch):
    class FakeStructuredCoder:
        def __init__(self, api_key, model):
            pass

        def json_object(self, prompt, system=None):
            return {"ok": True}

    monkeypatch.setattr(service, "StructuredCoder", FakeStructuredCoder)
    outcome = service.generate_structured("q", "k", "claude-sonnet-5")
    assert outcome == {"result": {"ok": True}, "mode": "json_object"}


def test_generate_structured_inline_schema_mode(monkeypatch):
    class FakeStructuredCoder:
        def __init__(self, api_key, model):
            pass

        def json_schema(self, prompt, schema, name="output", system=None):
            return {"schema_seen": schema}

    monkeypatch.setattr(service, "StructuredCoder", FakeStructuredCoder)
    outcome = service.generate_structured(
        "q", "k", "claude-sonnet-5", schema_inline=json.dumps({"type": "object"})
    )
    assert outcome["mode"] == "schema_inline"
    assert outcome["result"] == {"schema_seen": {"type": "object"}}


def test_analyse_code_structured_reads_file_and_infers_language(tmp_path, monkeypatch):
    f = tmp_path / "example.py"
    f.write_text("print('hi')")

    calls = {}

    class FakeStructuredCoder:
        def __init__(self, api_key, model):
            pass

        def analyse_code(self, code, language=""):
            calls["args"] = (code, language)
            return {"summary": "ok"}

    monkeypatch.setattr(service, "StructuredCoder", FakeStructuredCoder)
    result = service.analyse_code_structured(str(f), "k", "claude-sonnet-5")
    assert result == {"summary": "ok"}
    assert calls["args"] == ("print('hi')", "py")


# ── citations & RAG ──────────────────────────────────────────────────────


def test_cite_documents_reports_missing_files(tmp_path, monkeypatch):
    present = tmp_path / "doc1.txt"
    present.write_text("content")
    missing = str(tmp_path / "doc2.txt")

    class FakeCitationsCoder:
        def __init__(self, api_key, model):
            pass

        def cite_documents(self, question, docs, system=None):
            return {"answer": f"used {len(docs)} docs", "citations": []}

    monkeypatch.setattr(service, "CitationsCoder", FakeCitationsCoder)
    outcome = service.cite_documents("q", [str(present), missing], "k", "claude-sonnet-5")
    assert outcome["missing"] == [missing]
    assert outcome["result"]["answer"] == "used 1 docs"


def test_cite_documents_all_missing_returns_none_result(tmp_path):
    missing = str(tmp_path / "nope.txt")
    outcome = service.cite_documents("q", [missing], "k", "claude-sonnet-5")
    assert outcome["result"] is None
    assert outcome["missing"] == [missing]


def test_rag_query_delegates_to_gateway(monkeypatch):
    class FakeCitationsCoder:
        def __init__(self, api_key, model):
            pass

        def rag_from_directory(self, question, directory, pattern):
            return {"answer": f"{question}@{directory}/{pattern}", "citations": []}

    monkeypatch.setattr(service, "CitationsCoder", FakeCitationsCoder)
    result = service.rag_query("q", "docs/", "k", "claude-sonnet-5", pattern="*.txt")
    assert result["answer"] == "q@docs//*.txt"


# ── extended / adaptive thinking ─────────────────────────────────────────


def test_generate_thinking_non_streaming(monkeypatch):
    class FakeThinkingCoder:
        def __init__(self, api_key, model):
            pass

        def generate_with_thinking(self, prompt, **kwargs):
            return {"response": "answer", "usage": {}}

    monkeypatch.setattr(service, "ThinkingCoder", FakeThinkingCoder)
    result = service.generate_thinking("q", "k", "claude-sonnet-5", 8000, None, None, False, stream=False)
    assert result["response"] == "answer"


def test_generate_thinking_streaming(monkeypatch):
    class FakeThinkingCoder:
        def __init__(self, api_key, model):
            pass

        def stream_with_thinking(self, prompt, **kwargs):
            return "streamed answer"

    monkeypatch.setattr(service, "ThinkingCoder", FakeThinkingCoder)
    result = service.generate_thinking("q", "k", "claude-sonnet-5", 8000, None, None, False, stream=True)
    assert result == "streamed answer"


def test_resolve_thinking_mode_label(monkeypatch):
    class FakeThinkingCoder:
        def __init__(self, api_key, model):
            pass

        def _resolve_mode(self, adaptive, legacy_budget):
            return True

    monkeypatch.setattr(service, "ThinkingCoder", FakeThinkingCoder)
    assert service.resolve_thinking_mode_label("k", "claude-sonnet-5", None, False) == "adaptive"


# ── token counting ───────────────────────────────────────────────────────


def test_count_tokens_with_budget_under(monkeypatch):
    class FakeTokenCounter:
        def __init__(self, api_key, model):
            pass

        def count(self, prompt, system=None):
            return {"input_tokens": 100}

        def estimate_cost(self, token_count, model):
            return {
                "tokens": token_count,
                "model": model,
                "price_per_mtok": 3.0,
                "estimated_cost_usd": 0.0003,
            }

    monkeypatch.setattr(service, "TokenCounter", FakeTokenCounter)
    outcome = service.count_tokens("q", "k", "claude-sonnet-5", budget=1000)
    assert outcome["tokens"] == 100
    assert outcome["budget"]["over"] is False
    assert outcome["budget"]["remaining"] == 900


def test_count_tokens_exceeds_budget(monkeypatch):
    class FakeTokenCounter:
        def __init__(self, api_key, model):
            pass

        def count(self, prompt, system=None):
            return {"input_tokens": 1500}

        def estimate_cost(self, token_count, model):
            return {
                "tokens": token_count,
                "model": model,
                "price_per_mtok": 3.0,
                "estimated_cost_usd": 0.0045,
            }

    monkeypatch.setattr(service, "TokenCounter", FakeTokenCounter)
    outcome = service.count_tokens("q", "k", "claude-sonnet-5", budget=1000)
    assert outcome["budget"]["over"] is True
    assert outcome["budget"]["exceeded_by"] == 500


def test_count_tokens_no_budget_omits_budget_info(monkeypatch):
    class FakeTokenCounter:
        def __init__(self, api_key, model):
            pass

        def count(self, prompt, system=None):
            return {"input_tokens": 42}

        def estimate_cost(self, token_count, model):
            return {
                "tokens": token_count,
                "model": model,
                "price_per_mtok": 3.0,
                "estimated_cost_usd": 0.000126,
            }

    monkeypatch.setattr(service, "TokenCounter", FakeTokenCounter)
    outcome = service.count_tokens("q", "k", "claude-sonnet-5")
    assert outcome["budget"] is None


# ── zcoder-live session ──────────────────────────────────────────────────────


def test_create_live_session_and_send(monkeypatch):
    class FakeSession:
        def __init__(self, api_key, model, temperature, personality_prompt):
            self.args = (api_key, model, temperature, personality_prompt)

        def send(self, text, on_chunk=None):
            if on_chunk:
                on_chunk(text)
            return f"echo:{text}"

    monkeypatch.setattr(service, "LiveSession", FakeSession)
    session = service.create_live_session("k", "claude-sonnet-5", 0.5, "friendly")
    assert session.args == ("k", "claude-sonnet-5", 0.5, "friendly")

    seen = []
    result = service.live_send(session, "hi", on_chunk=seen.append)
    assert result == "echo:hi"
    assert seen == ["hi"]
