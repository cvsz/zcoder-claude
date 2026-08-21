"""
domain/messaging.py — Core Messaging bounded context: pure data + pure logic
AI Model Coder CLI v1.46.0 (Clean Architecture refactor, Phase B)

Domain layer: zero I/O, zero print(), zero HTTP. Extracted 2026-08-15 from
claude_stream.py, claude_thinking.py, and claude_live.py, which previously
mixed this pure logic with HTTP transport (now in
infrastructure/anthropic_api/messaging_gateway.py) and CLI presentation
(now in interfaces/cli/commands/messaging_commands.py) in the same files.

Nothing here depends on infrastructure/ or interfaces/ — the Dependency
Rule points inward only, same convention as domain/models/catalog.py and
domain/agents/agent_config.py.
"""

import threading

# ── Streaming / tool-use helpers (from claude_stream.py) ───────────────────

# Legacy header — GA now, per-tool eager_input_streaming is the current way
# to opt in, but this still works for requests that send it and leave the
# field unset on individual tools.
FINE_GRAINED_TOOL_STREAMING_BETA = "fine-grained-tool-streaming-2025-05-14"


def with_eager_input_streaming(tools: list[dict], enabled: bool = True) -> list[dict]:
    """Return a copy of tools with eager_input_streaming set on each —
    turns on fine-grained streaming for those tools. Pass enabled=False to
    explicitly force buffered streaming for a tool even under the legacy
    beta header (an explicit false overrides the header, per the docs)."""
    out = []
    for t in tools:
        t2 = dict(t)
        t2["eager_input_streaming"] = enabled
        out.append(t2)
    return out


def handle_refusal(response_or_stop_details) -> dict | None:
    """Read stop_details off a (non-streaming) response dict or a
    message_delta event's stop_details field. Returns {"category": ...,
    "explanation": ...} when the response was a refusal with no output
    generated, or None otherwise. category is "cyber", "bio", or null per
    the current docs — use it to route to a different fallback/support flow
    instead of just showing the raw refusal text. Refusal-only responses
    (stop_reason:"refusal" with no generated output) are documented as not
    billed, so this is also useful as a signal to skip cost bookkeeping for
    that call — see claude_cost_optimizer.py / claude_metrics.py."""
    if isinstance(response_or_stop_details, dict) and "stop_reason" in response_or_stop_details:
        if response_or_stop_details.get("stop_reason") != "refusal":
            return None
        details = response_or_stop_details.get("stop_details") or {}
    else:
        details = response_or_stop_details or {}
    return {
        "category": details.get("category"),
        "explanation": details.get("explanation", ""),
    }


# ── Extended / adaptive thinking routing (from claude_thinking.py) ─────────

# "xhigh" (live since April 16, 2026 on Opus 4.7, and part of Opus 5's
# advertised ladder — see the Opus 5 wrapper, which stays the authoritative
# source for Opus 5 specifically) sits between "high" and "max" here,
# matching the budget_tokens value Opus 5's dedicated code already uses for
# it, so the two ladders agree.
EFFORT_BUDGETS = {
    "low": 2_000,
    "medium": 8_000,
    "high": 16_000,
    "xhigh": 24_000,
    "max": 32_000,
}

# Models where adaptive thinking is the modern, correct path.
# On Opus 4.6 / Sonnet 4.6, manual budget_tokens is deprecated but still
# accepted (--effort-legacy-budget can still target these). On every
# other model in this set, manual budget_tokens is a hard 400 error.
ADAPTIVE_THINKING_MODELS = {
    "claude-mythos-5",
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-5",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-mythos-preview",
}

# Models where budget_tokens is a hard 400 — adaptive is the *only*
# working mode, --effort-legacy-budget must refuse rather than fail late.
BUDGET_TOKENS_UNSUPPORTED_MODELS = {
    "claude-mythos-5",
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-5",
    "claude-mythos-preview",
}


def _model_key(model: str) -> str:
    # domain/models/catalog.py ids are mostly bare ("claude-sonnet-5"), but
    # claude-haiku-4-5-20251001 carries a snapshot date — normalize by
    # matching on prefix membership so a dated snapshot id of a listed
    # model still routes correctly.
    if model in ADAPTIVE_THINKING_MODELS or model in BUDGET_TOKENS_UNSUPPORTED_MODELS:
        return model
    for known in ADAPTIVE_THINKING_MODELS | BUDGET_TOKENS_UNSUPPORTED_MODELS:
        if model.startswith(known):
            return known
    return model


def supports_adaptive_thinking(model: str) -> bool:
    return _model_key(model) in ADAPTIVE_THINKING_MODELS


def supports_manual_budget_tokens(model: str) -> bool:
    return _model_key(model) not in BUDGET_TOKENS_UNSUPPORTED_MODELS


class ThinkingModeError(ValueError):
    """Raised when the requested thinking mode can't work on this model
    (e.g. --effort-legacy-budget on a model where budget_tokens is a
    400), so the caller gets a clear message before an API round trip
    instead of after one."""


def resolve_thinking_mode(model: str, adaptive: bool | None, legacy_budget: bool) -> bool:
    """Returns True for adaptive mode, False for legacy manual mode.
    Raises ThinkingModeError instead of building a request known to
    fail with a 400. Pure decision logic — no client, no I/O."""
    if legacy_budget:
        if not supports_manual_budget_tokens(model):
            raise ThinkingModeError(
                f"--effort-legacy-budget can't be used with {model}: "
                f"budget_tokens is not accepted by this model (400 error). "
                f"Drop --effort-legacy-budget and use --effort instead."
            )
        return False
    if adaptive is not None:
        if adaptive and not supports_adaptive_thinking(model):
            raise ThinkingModeError(
                f"{model} doesn't support adaptive thinking. "
                f"Use --effort-legacy-budget with --thinking-budget/--effort instead."
            )
        return adaptive
    # Auto-select: prefer adaptive when the model supports it.
    return supports_adaptive_thinking(model)


# ── Live session ambient context (from claude_live.py) ─────────────────────

LIVE_SYSTEM = (
    "You are an always-on assistant. Respond to the user's message directly. "
    "Ambient context events (background observations) are provided in the system "
    "prompt for awareness — address them only if the user refers to them."
)


class AmbientBuffer:
    """In-memory ring buffer of background events. No I/O — the lock guards
    concurrent access from multiple threads, it isn't itself an I/O wait."""

    def __init__(self, maxlen: int = 20):
        self._events: list[dict[str, str]] = []
        self._lock = threading.Lock()
        self._maxlen = maxlen

    def push(self, source: str, content: str):
        with self._lock:
            self._events.append({"source": source, "content": content})
            if len(self._events) > self._maxlen:
                self._events = self._events[-self._maxlen :]

    def block(self) -> str:
        with self._lock:
            if not self._events:
                return ""
            lines = ["## Ambient Context"]
            for e in self._events[-10:]:
                lines.append(f"- [{e['source']}] {e['content']}")
            return "\n".join(lines)

    def clear(self):
        with self._lock:
            self._events = []

    def build_system_prompt(self, personality: str = "") -> str:
        """Pure assembly of the live-session system prompt — was
        LiveSession._system() in claude_live.py. Kept here (not on
        LiveSession, which now lives in the gateway) since it's pure string
        assembly with no client/I/O dependency."""
        parts = [LIVE_SYSTEM]
        if personality:
            parts.append(personality)
        amb = self.block()
        if amb:
            parts.append(amb)
        return "\n\n".join(parts)
