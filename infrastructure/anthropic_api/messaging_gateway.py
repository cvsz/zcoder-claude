"""
infrastructure/anthropic_api/messaging_gateway.py — Live Anthropic API
# mypy: ignore-errors
adapters for Core Messaging (streaming, structured outputs, citations/RAG,
extended thinking, token counting, the zai-live REPL session)
AI Model Coder CLI v1.46.0 (Clean Architecture refactor, Phase B)

Infrastructure layer: everything here makes a real call to
api.anthropic.com (either raw urllib or the anthropic SDK client).
Extracted 2026-08-15 from claude_stream.py, claude_structured.py,
claude_citations.py, claude_thinking.py, claude_tokens.py, and
claude_live.py, which previously mixed this transport code with pure
domain logic (now in domain/messaging.py) and CLI presentation/print()
(now in interfaces/cli/commands/messaging_commands.py) in the same files.

Real-time streaming previously called print()/sys.stdout.write() directly
inside the SSE consumption loop. That violates "no print() outside
interfaces/", so every streaming method here takes optional callback
hooks instead (default: no-op) — same convention already established in
application/agents_service.py's `on_step` callback for managed-agent
progress. interfaces/cli/commands/messaging_commands.py supplies the
print-based callbacks; a future Web caller can supply different ones
(e.g. push to a websocket) or none at all.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

import anthropic

from domain.messaging import (
    EFFORT_BUDGETS,
    FINE_GRAINED_TOOL_STREAMING_BETA,
    AmbientBuffer,
    handle_refusal,
    resolve_thinking_mode,
    with_eager_input_streaming,
)
from domain.models.catalog import get_price
from exceptions import AICoderError
from infrastructure.anthropic_api.http_client import CircuitBreaker, retry, urlopen_json

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
COUNT_TOKENS_ENDPOINT = "https://api.anthropic.com/v1/messages/count_tokens"

# Shared per-process so repeated failures across coder instances trip the
# breaker once, same rationale as the other migrated gateways.
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

_NOOP = lambda *a, **k: None  # noqa: E731


# ── Streaming (claude_stream.py) ────────────────────────────────────────────


class StreamCoder:
    """Claude client with streaming support."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5", max_tokens: int = 4096):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def stream(
        self,
        prompt: str,
        system: str | None = None,
        tools: list = None,
        show_thinking: bool = False,
        history: list | None = None,
        temperature: float | None = None,
        on_text: Callable[[str], None] = _NOOP,
        on_thinking: Callable[[str], None] = _NOOP,
        on_thinking_start: Callable[[], None] = _NOOP,
        on_thinking_stop: Callable[[], None] = _NOOP,
        on_usage: Callable[[dict], None] = _NOOP,
    ) -> str:
        """Stream a response, invoking callbacks live. Returns full text.

        history: prior [{"role", "content"}, ...] turns prepended to the
        prompt (multi-turn chat shape used by the webapp/TUI front ends).
        temperature: sent only when not None — omitting it lets the API
        apply its model default.
        """
        messages = list(history or []) + [{"role": "user", "content": prompt}]

        kwargs = dict(model=self.model, max_tokens=self.max_tokens, messages=messages)
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        if temperature is not None:
            kwargs["temperature"] = temperature

        full_text = ""
        in_thinking = False
        usage_data: dict = {}

        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                etype = getattr(event, "type", "")

                if etype == "content_block_start":
                    btype = getattr(event.content_block, "type", "")
                    if btype == "thinking":
                        in_thinking = True
                        if show_thinking:
                            on_thinking_start()
                    elif btype == "text":
                        in_thinking = False

                elif etype == "content_block_delta":
                    delta = event.delta
                    dtype = getattr(delta, "type", "")
                    if dtype == "thinking_delta":
                        chunk = getattr(delta, "thinking", "")
                        if show_thinking:
                            on_thinking(chunk)
                    elif dtype == "text_delta":
                        text = getattr(delta, "text", "")
                        full_text += text
                        on_text(text)

                elif etype == "content_block_stop" and in_thinking and show_thinking:
                    on_thinking_stop()
                    in_thinking = False

                elif etype == "message_delta":
                    usage = getattr(event, "usage", None)
                    if usage:
                        usage_data["output_tokens"] = getattr(usage, "output_tokens", 0)

                elif etype == "message_start":
                    msg = getattr(event, "message", None)
                    usage = getattr(msg, "usage", None) if msg else None
                    if usage:
                        usage_data["input_tokens"] = getattr(usage, "input_tokens", 0)

        if usage_data:
            on_usage(usage_data)
        return full_text

    def stream_file_analysis(
        self, file_content: str, prompt: str, system: str | None = None, **callbacks
    ) -> str:
        """Stream analysis of a file."""
        full_prompt = f"```\n{file_content}\n```\n\n{prompt}"
        return self.stream(full_prompt, system=system, **callbacks)

    def stream_with_tools(
        self,
        prompt: str,
        tools: list,
        system: str | None = None,
        eager_input_streaming: bool = True,
        use_legacy_beta: bool = False,
        on_text: Callable[[str], None] = _NOOP,
        on_tool_start: Callable[[str], None] = _NOOP,
        on_tool_delta: Callable[[str], None] = _NOOP,
        on_tool_stop: Callable[[], None] = _NOOP,
        on_refusal: Callable[[dict | None], None] = _NOOP,
    ) -> dict:
        """Stream a single turn with tool_use fine-grained input streaming.
        Invokes callbacks as fragments arrive (so a large parameter — a
        generated file, a long string — is observable incrementally
        instead of all at once when the block closes), then returns
        {"text": ..., "tool_calls": [{"name","id","input_raw","input"}],
        "stop_reason": ...}. input is the parsed dict when the accumulated
        JSON was valid, input_raw always has the raw accumulated string —
        check both, since fine-grained streaming doesn't guarantee valid
        JSON on truncation (stop_reason == "max_tokens" mid-parameter)."""
        if eager_input_streaming:
            tools = with_eager_input_streaming(tools)

        messages = [{"role": "user", "content": prompt}]
        kwargs = dict(model=self.model, max_tokens=self.max_tokens, messages=messages, tools=tools)
        if system:
            kwargs["system"] = system
        extra_headers = {}
        if use_legacy_beta:
            extra_headers["anthropic-beta"] = FINE_GRAINED_TOOL_STREAMING_BETA
        if extra_headers:
            kwargs["extra_headers"] = extra_headers

        full_text = ""
        tool_calls = []
        current = None  # in-progress tool_use block accumulator
        stop_reason = None
        stop_details = None

        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                etype = getattr(event, "type", "")

                if etype == "content_block_start":
                    block = event.content_block
                    if getattr(block, "type", "") == "tool_use":
                        current = {
                            "name": getattr(block, "name", ""),
                            "id": getattr(block, "id", ""),
                            "json": "",
                        }
                        on_tool_start(current["name"])

                elif etype == "content_block_delta":
                    delta = event.delta
                    dtype = getattr(delta, "type", "")
                    if dtype == "text_delta":
                        text = getattr(delta, "text", "")
                        full_text += text
                        on_text(text)
                    elif dtype == "input_json_delta" and current is not None:
                        frag = getattr(delta, "partial_json", "")
                        current["json"] += frag
                        on_tool_delta(frag)

                elif etype == "content_block_stop" and current is not None:
                    on_tool_stop()
                    parsed = None
                    try:
                        parsed = json.loads(current["json"]) if current["json"] else {}
                    except json.JSONDecodeError:
                        pass  # expected possibility with eager_input_streaming
                    tool_calls.append(
                        {
                            "name": current["name"],
                            "id": current["id"],
                            "input_raw": current["json"],
                            "input": parsed,
                        }
                    )
                    current = None

                elif etype == "message_delta":
                    stop_reason = getattr(event, "delta", None) and getattr(event.delta, "stop_reason", None)
                    sd = getattr(event, "delta", None) and getattr(event.delta, "stop_details", None)
                    if sd:
                        stop_details = sd

        if stop_reason == "refusal":
            refusal = handle_refusal({"stop_reason": stop_reason, "stop_details": stop_details or {}})
            on_refusal(refusal)

        return {
            "text": full_text,
            "tool_calls": tool_calls,
            "stop_reason": stop_reason,
            "stop_details": stop_details,
        }


# ── Structured outputs (claude_structured.py) ───────────────────────────────


class StructuredCoder:
    """Claude client for structured / JSON outputs."""

    ENDPOINT = MESSAGES_ENDPOINT

    def __init__(self, api_key: str, model: str = "claude-sonnet-5", max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=120)

    def _post(self, payload: dict) -> dict:
        # Preserves the pre-existing {"error": ...} contract callers below
        # already check for, while retrying transient failures in _call().
        try:
            return self._call(payload)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def json_object(self, prompt: str, system: str | None = None) -> dict:
        """Return any valid JSON object. No schema enforcement."""
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "output_config": {"format": {"type": "json_object"}},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        data = self._post(payload)
        if "error" in data:
            raise RuntimeError(data["error"])
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return json.loads(text)

    def json_schema(self, prompt: str, schema: dict, name: str = "output", system: str | None = None) -> dict:
        """Return JSON validated against a JSON Schema."""
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "output_config": {
                "format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}
            },
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        data = self._post(payload)
        if "error" in data:
            raise RuntimeError(data["error"])
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        parsed = json.loads(text)
        self._validate(parsed, schema)
        return parsed

    def extract(self, content: str, schema: dict, instruction: str = "") -> dict:
        """Extract structured data from unstructured text."""
        prompt = (
            f"Extract structured data from the following content.\n"
            f"{('Instructions: ' + instruction) if instruction else ''}\n\n"
            f"Content:\n{content}"
        )
        return self.json_schema(
            prompt,
            schema,
            system="Extract exactly the fields defined in the schema. "
            "If a field is missing from the content, use null.",
        )

    def analyse_code(self, code: str, language: str = "") -> dict:
        """Return a structured code analysis report."""
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "language": {"type": "string"},
                "complexity": {"type": "string", "enum": ["low", "medium", "high"]},
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "severity": {"type": "string", "enum": ["info", "warning", "error"]},
                            "line": {"type": ["integer", "null"]},
                            "description": {"type": "string"},
                        },
                        "required": ["severity", "description"],
                    },
                },
                "suggestions": {"type": "array", "items": {"type": "string"}},
                "security_flags": {"type": "array", "items": {"type": "string"}},
                "test_coverage": {"type": "string"},
            },
            "required": ["summary", "complexity", "issues", "suggestions"],
        }
        prompt = f"Analyse this {language} code:\n```\n{code}\n```"
        return self.json_schema(
            prompt,
            schema,
            name="code_analysis",
            system="You are a senior code reviewer. Be concise and precise.",
        )

    def _validate(self, data: dict, schema: dict):
        """Lightweight required-field check."""
        required = schema.get("required", [])
        missing = [r for r in required if r not in data]
        if missing:
            raise ValueError(f"Schema validation: missing required fields: {missing}")


# ── Citations & RAG (claude_citations.py) ───────────────────────────────────


class CitationsCoder:
    """Claude client with source-grounded citations."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5", max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict, beta: str = "") -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        if beta:
            headers["anthropic-beta"] = beta
        req = urllib.request.Request(
            MESSAGES_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=120)

    def _post(self, payload: dict, beta: str = "") -> dict:
        try:
            return self._call(payload, beta)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}

    def cite_documents(self, question: str, documents: list, system: str | None = None) -> dict:
        """documents: list of {"title": str, "content": str}"""
        content = []
        for doc in documents:
            content.append(
                {
                    "type": "document",
                    "source": {"type": "text", "media_type": "text/plain", "data": doc["content"]},
                    "title": doc.get("title", "Document"),
                    "citations": {"enabled": True},
                }
            )
        content.append({"type": "text", "text": question})

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": content}],
        }
        if system:
            payload["system"] = system

        data = self._post(payload)
        if "error" in data:
            return {"answer": f"[ERROR] {data['error']}", "citations": []}

        answer, citations = "", []
        for block in data.get("content", []):
            bt = block.get("type", "")
            if bt == "text":
                answer += block.get("text", "")
            elif bt == "citations":
                for c in block.get("citations", []):
                    citations.append(
                        {
                            "text": c.get("cited_text", ""),
                            "document": c.get("document_title", ""),
                            "start_char": c.get("start_char_index"),
                            "end_char": c.get("end_char_index"),
                        }
                    )
        return {"answer": answer, "citations": citations, "usage": data.get("usage", {})}

    def cite_search_results(self, question: str, results: list) -> dict:
        """results: [{"title": str, "url": str, "content": str}]. beta:
        search-results-2025-06-09"""
        content = []
        for r in results:
            content.append(
                {
                    "type": "search_result",
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": [{"type": "text", "text": r["content"]}],
                }
            )
        content.append({"type": "text", "text": question})

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": content}],
        }
        data = self._post(payload, beta="search-results-2025-06-09")
        if "error" in data:
            return {"answer": f"[ERROR] {data['error']}", "citations": []}

        answer = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return {"answer": answer, "citations": [], "usage": data.get("usage", {})}

    def rag_from_directory(self, question: str, directory: str, glob_pattern: str = "*.md") -> dict:
        """Load local docs from a directory and answer with citations."""
        docs = []
        for p in sorted(Path(directory).glob(glob_pattern)):
            try:
                docs.append({"title": p.name, "content": p.read_text()[:8000]})
            except Exception:
                pass
        if not docs:
            return {"answer": f"No documents found in {directory}", "citations": []}
        return self.cite_documents(question, docs)


# ── Extended / adaptive thinking (claude_thinking.py) ───────────────────────


class ThinkingCoder:
    """Claude client with extended / adaptive thinking support."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6", max_tokens: int = 8000):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def _resolve_mode(self, adaptive: bool | None, legacy_budget: bool) -> bool:
        return resolve_thinking_mode(self.model, adaptive, legacy_budget)

    def _build_kwargs(
        self,
        prompt: str,
        system: str | None,
        budget_tokens: int,
        effort: str | None,
        use_adaptive: bool,
        display_omitted: bool,
    ) -> dict:
        kwargs = dict(model=self.model, messages=[{"role": "user", "content": prompt}])
        if system:
            kwargs["system"] = system
        if use_adaptive:
            thinking_cfg = {"type": "adaptive"}
            if display_omitted:
                thinking_cfg["display"] = "omitted"
            kwargs["thinking"] = thinking_cfg
            kwargs["output_config"] = {"effort": effort or "high"}
            kwargs["max_tokens"] = self.max_tokens
        else:
            if effort and effort in EFFORT_BUDGETS:
                budget_tokens = EFFORT_BUDGETS[effort]
            thinking_cfg = {"type": "enabled", "budget_tokens": budget_tokens}
            if display_omitted:
                thinking_cfg["display"] = "omitted"
            kwargs["thinking"] = thinking_cfg
            kwargs["max_tokens"] = max(self.max_tokens, budget_tokens + 1000)
        return kwargs

    def generate_with_thinking(
        self,
        prompt: str,
        system: str | None = None,
        budget_tokens: int = 8_000,
        effort: str | None = None,
        adaptive: bool | None = None,
        legacy_budget: bool = False,
        show_thinking: bool = False,
        display_omitted: bool = False,
        on_thinking: Callable[[str], None] = _NOOP,
    ) -> dict:
        """Returns {"thinking": str, "response": str, "usage": dict}. Mode
        selection is delegated to domain.messaging.resolve_thinking_mode —
        see its docstring for the adaptive-vs-legacy decision rules."""
        use_adaptive = self._resolve_mode(adaptive, legacy_budget)
        kwargs = self._build_kwargs(prompt, system, budget_tokens, effort, use_adaptive, display_omitted)

        resp = self.client.messages.create(**kwargs)

        thinking_text = ""
        response_text = ""
        for block in resp.content:
            if block.type == "thinking":
                thinking_text = block.thinking
            elif block.type == "text":
                response_text += block.text

        if show_thinking and thinking_text:
            on_thinking(thinking_text)

        return {
            "thinking": thinking_text,
            "response": response_text,
            "usage": resp.usage.model_dump() if hasattr(resp.usage, "model_dump") else {},
            "model": self.model,
        }

    def stream_with_thinking(
        self,
        prompt: str,
        system: str | None = None,
        budget_tokens: int = 8_000,
        effort: str | None = None,
        adaptive: bool | None = None,
        legacy_budget: bool = False,
        show_thinking: bool = False,
        display_omitted: bool = False,
        on_text: Callable[[str], None] = _NOOP,
        on_thinking: Callable[[str], None] = _NOOP,
        on_thinking_start: Callable[[], None] = _NOOP,
        on_thinking_stop: Callable[[], None] = _NOOP,
    ) -> str:
        """Stream response, invoking thinking callbacks live when
        show_thinking is set. Mode selection and display_omitted behave
        exactly as in generate_with_thinking()."""
        use_adaptive = self._resolve_mode(adaptive, legacy_budget)
        kwargs = self._build_kwargs(prompt, system, budget_tokens, effort, use_adaptive, display_omitted)

        full_response = ""
        in_thinking = False

        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                etype = getattr(event, "type", "")

                if etype == "content_block_start":
                    bt = getattr(event.content_block, "type", "")
                    if bt == "thinking":
                        in_thinking = True
                        if show_thinking:
                            on_thinking_start()
                    elif bt == "text":
                        in_thinking = False

                elif etype == "content_block_delta":
                    delta = event.delta
                    dt = getattr(delta, "type", "")
                    if dt == "thinking_delta" and show_thinking:
                        on_thinking(delta.thinking)
                    elif dt == "text_delta":
                        on_text(delta.text)
                        full_response += delta.text

                elif etype == "content_block_stop" and in_thinking and show_thinking:
                    on_thinking_stop()
                    in_thinking = False

        return full_response


# ── Token counting (claude_tokens.py) ───────────────────────────────────────


class TokenCounter:
    """Count tokens without sending to the model."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5"):
        self.api_key = api_key
        self.model = model

    def count(self, prompt: str, system: str | None = None, tools: list = None, history: list = None) -> dict:
        messages = list(history or [])
        messages.append({"role": "user", "content": prompt})

        payload: dict = {"model": self.model, "messages": messages}
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            COUNT_TOKENS_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            return self._call(req)
        except AICoderError as e:
            raise RuntimeError(f"Token count failed: {e.message}") from e

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, req: urllib.request.Request) -> dict:
        return urlopen_json(req, timeout=30)

    def count_file(self, file_path: str, prompt: str, system: str | None = None) -> dict:
        content = Path(file_path).read_text()
        full = f"File:\n```\n{content}\n```\n\n{prompt}"
        return self.count(full, system=system)

    def estimate_cost(self, token_count: int, model: str = None) -> dict:
        """Rough cost estimate based on current pricing tiers.

        Was a locally-defined `prices_per_mtok` dict in claude_tokens.py —
        exactly the pricing-duplication anti-pattern §0 of the master
        execution plan documents (Claude Sonnet 5's price went stale in 3
        files simultaneously). Fixed 2026-08-15 to read from
        domain/models/catalog.py's single source of truth (get_price)
        instead of carrying its own table."""
        m = model or self.model
        price = get_price(m)["in"]
        cost = (token_count / 1_000_000) * price
        return {
            "tokens": token_count,
            "model": m,
            "price_per_mtok": price,
            "estimated_cost_usd": round(cost, 6),
        }


# ── zai-live REPL session (claude_live.py) ──────────────────────────────────


class LiveSession:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-5",
        temperature: float = 0.7,
        personality_prompt: str = "",
    ):
        from utils import sampling_kwargs  # local import: avoids a hard

        # dependency on utils.py for callers that only need the other
        # classes in this module (matches the original file's shape).
        self._sampling_kwargs = sampling_kwargs

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.personality = personality_prompt
        self.history: list = []
        self.ambient = AmbientBuffer()
        self.streaming = False

    def send(self, text: str, on_chunk: Callable[[str], None] = _NOOP) -> str:
        self.history.append({"role": "user", "content": text})
        full: list = []
        self.streaming = True
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                # Was hardcoded temperature=self.temperature, unguarded —
                # 400s (invalid_request_error) the moment self.model is
                # claude-sonnet-5 (the default), which rejects any explicit
                # sampling param. Route through sampling_kwargs() like
                # coder.py/claude_eval.py do.
                **self._sampling_kwargs(self.model, temperature=self.temperature),
                system=self.ambient.build_system_prompt(self.personality),
                messages=self.history,
            ) as stream:
                for chunk in stream.text_stream:
                    full.append(chunk)
                    on_chunk(chunk)
        finally:
            self.streaming = False
        result = "".join(full)
        self.history.append({"role": "assistant", "content": result})
        return result

    def stats(self) -> dict:
        return {
            "model": self.model,
            "turns": len(self.history),
            "ambient_events": len(self.ambient._events),
            "streaming": self.streaming,
        }
