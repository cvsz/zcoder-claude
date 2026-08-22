"""
application/messaging_service.py — Use-case layer for Core Messaging
AI Model Coder CLI v1.46.0 (Clean Architecture refactor, Phase B)

Same pattern as models_service.py / admin_service.py / compliance_service.py
/ agents_service.py: plain functions, no print(), no argparse.
infrastructure.anthropic_api.messaging_gateway does the real HTTP/SDK
calls; this module orchestrates it and reads local input files (schema /
content files, plain read_text — not an HTTP call, so it stays here
rather than in infrastructure/anthropic_api/, matching the convention that
gateway.CitationsCoder.rag_from_directory already uses for its own local
directory scan).

Streaming callbacks (on_text, on_thinking, ...) are accepted here and
passed straight through to the gateway — this layer doesn't print, it
just threads the caller's callbacks (usually interfaces/cli's
print-based ones) down to where the SSE loop lives.
"""

import json
from collections.abc import Callable
from pathlib import Path

from infrastructure.anthropic_api.core_gateway import Coder
from infrastructure.anthropic_api.messaging_gateway import (
    CitationsCoder,
    LiveSession,
    StreamCoder,
    StructuredCoder,
    ThinkingCoder,
    TokenCounter,
)

_NOOP = lambda *a, **k: None  # noqa: E731


# ── Streaming ────────────────────────────────────────────────────────────


def chat_turn(
    prompt: str,
    api_key: str | None = None,
    model: str = "claude-sonnet-5",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    system: str | None = None,
    history: list | None = None,
    personality_style: str | None = None,
) -> str:
    """One complete non-streaming chat turn (multi-turn aware). Used by the
    webapp's POST /api/chat and the TUI's non-streaming send — both were
    constructing the core_gateway.Coder class directly before this
    extraction (2026-08-22, Phase F web/TUI audit)."""
    coder = Coder(
        api_key=api_key or None,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        personality_style=personality_style,
    )
    return coder.generate(prompt, system=system, history=list(history or []))


def stream_chat_turn(
    prompt: str,
    api_key: str,
    model: str,
    system: str | None = None,
    history: list | None = None,
    temperature: float | None = None,
    max_tokens: int = 4096,
    on_text: Callable[[str], None] = _NOOP,
) -> str:
    """One streaming chat turn (multi-turn aware): invokes on_text per
    text delta, returns the full response. Replaces the raw
    anthropic.Anthropic SSE loops that webapp/server.py and tui.py each
    maintained inline; the SSE event-shape handling lives in the gateway's
    StreamCoder.stream."""
    sc = StreamCoder(api_key=api_key, model=model, max_tokens=max_tokens)
    return sc.stream(
        prompt,
        system=system,
        history=list(history or []),
        temperature=temperature,
        on_text=on_text,
    )


def stream_text(
    prompt: str,
    api_key: str,
    model: str,
    system: str | None = None,
    file_content: str | None = None,
    show_thinking: bool = False,
    **callbacks,
) -> str:
    sc = StreamCoder(api_key=api_key, model=model)
    if file_content:
        return sc.stream_file_analysis(file_content, prompt, system=system, **callbacks)
    return sc.stream(prompt, system=system, show_thinking=show_thinking, **callbacks)


def stream_with_tools(
    prompt: str, tools: list, api_key: str, model: str, system: str | None = None, **callbacks
) -> dict:
    sc = StreamCoder(api_key=api_key, model=model)
    return sc.stream_with_tools(prompt, tools, system=system, **callbacks)


# ── Structured outputs ──────────────────────────────────────────────────


def generate_structured(
    prompt: str,
    api_key: str,
    model: str,
    schema_path: str | None = None,
    schema_inline: str | None = None,
) -> dict:
    """Returns {"result": dict, "mode": "schema_file"|"schema_inline"|"json_object"}."""
    sc = StructuredCoder(api_key=api_key, model=model)
    if schema_path:
        schema = json.loads(Path(schema_path).read_text())
        return {"result": sc.json_schema(prompt, schema), "mode": "schema_file"}
    if schema_inline:
        schema = json.loads(schema_inline)
        return {"result": sc.json_schema(prompt, schema), "mode": "schema_inline"}
    return {"result": sc.json_object(prompt), "mode": "json_object"}


def analyse_code_structured(file_path: str, api_key: str, model: str) -> dict:
    code = Path(file_path).read_text()
    lang = Path(file_path).suffix.lstrip(".")
    sc = StructuredCoder(api_key=api_key, model=model)
    return sc.analyse_code(code, lang)


def extract_structured(content_file: str, schema_path: str, api_key: str, model: str) -> dict:
    content = Path(content_file).read_text()
    schema = json.loads(Path(schema_path).read_text())
    sc = StructuredCoder(api_key=api_key, model=model)
    return sc.extract(content, schema)


# ── Citations & RAG ──────────────────────────────────────────────────────


def cite_documents(question: str, doc_files: list, api_key: str, model: str) -> dict:
    """Returns {"result": dict|None, "missing": [str, ...]} — `missing`
    lists doc_files that didn't exist on disk, so the CLI layer can warn
    about them without this function printing anything itself."""
    docs, missing = [], []
    for f in doc_files:
        p = Path(f)
        if p.exists():
            docs.append({"title": p.name, "content": p.read_text()[:8000]})
        else:
            missing.append(f)

    if not docs:
        return {"result": None, "missing": missing}

    cc = CitationsCoder(api_key=api_key, model=model)
    return {"result": cc.cite_documents(question, docs), "missing": missing}


def rag_query(question: str, directory: str, api_key: str, model: str, pattern: str = "*.md") -> dict:
    cc = CitationsCoder(api_key=api_key, model=model)
    return cc.rag_from_directory(question, directory, pattern)


# ── Extended / adaptive thinking ─────────────────────────────────────────


def generate_thinking(
    prompt: str,
    api_key: str,
    model: str,
    budget: int,
    effort: str | None,
    adaptive: bool | None,
    show_thinking: bool,
    stream: bool,
    system: str | None = None,
    display_omitted: bool = False,
    legacy_budget: bool = False,
    **callbacks,
):
    """Returns the ThinkingCoder result — a dict from generate_with_thinking
    (non-streaming) or the response string from stream_with_thinking."""
    tc = ThinkingCoder(api_key=api_key, model=model)
    if stream:
        return tc.stream_with_thinking(
            prompt,
            system=system,
            budget_tokens=budget,
            effort=effort,
            adaptive=adaptive,
            legacy_budget=legacy_budget,
            show_thinking=show_thinking,
            display_omitted=display_omitted,
            **callbacks,
        )
    return tc.generate_with_thinking(
        prompt,
        system=system,
        budget_tokens=budget,
        effort=effort,
        adaptive=adaptive,
        legacy_budget=legacy_budget,
        show_thinking=show_thinking,
        display_omitted=display_omitted,
        **callbacks,
    )


def resolve_thinking_mode_label(
    api_key: str, model: str, adaptive: bool | None, legacy_budget: bool
) -> str:
    """ "adaptive" or "manual budget_tokens" — used by the CLI layer to
    print the mode banner before making the call."""
    tc = ThinkingCoder(api_key=api_key, model=model)
    return "adaptive" if tc._resolve_mode(adaptive, legacy_budget) else "manual budget_tokens"


# ── Token counting ───────────────────────────────────────────────────────


def count_tokens(
    prompt: str,
    api_key: str,
    model: str,
    system: str | None = None,
    file_path: str | None = None,
    budget: int | None = None,
) -> dict:
    """Returns {"tokens": int, "estimate": dict, "budget": {...} | None}."""
    tc = TokenCounter(api_key=api_key, model=model)
    result = tc.count_file(file_path, prompt, system=system) if file_path else tc.count(prompt, system=system)

    tokens = result.get("input_tokens", 0)
    estimate = tc.estimate_cost(tokens, model)

    budget_info = None
    if budget:
        pct = tokens / budget * 100
        budget_info = {
            "pct": pct,
            "over": tokens > budget,
            "remaining": budget - tokens,
            "exceeded_by": tokens - budget,
        }

    return {"tokens": tokens, "estimate": estimate, "budget": budget_info}


# ── zai-live REPL session ────────────────────────────────────────────────


def create_live_session(
    api_key: str, model: str = "claude-sonnet-5", temperature: float = 0.7, personality_prompt: str = ""
) -> LiveSession:
    return LiveSession(api_key, model, temperature, personality_prompt)


def live_send(session: LiveSession, text: str, on_chunk: Callable[[str], None] = _NOOP) -> str:
    return session.send(text, on_chunk=on_chunk)
