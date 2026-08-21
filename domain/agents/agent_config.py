"""
domain/agents/agent_config.py — Agent SDK domain layer: config, sessions, validation
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

Pure data/config classes and validation for the Agent SDK / Managed Agents
surface. AgentSession persists to local disk (~/.ai-coder/agent_sessions) --
not an Anthropic API call, so it's kept here as a pragmatic simplification
rather than pushed into infrastructure/, but note this is local persistence,
not a network-free domain in the strictest Clean Architecture sense.
Everything else here (PermissionMode, TOOL_PRESETS, McpServerConfig, budget
en/decoding, dreaming validation, multiagent config building) has zero I/O.

The real Anthropic API clients that use these (ManagedAgent, McpTunnel,
ManagedAgentsClient) live in infrastructure/anthropic_api/agents_gateway.py.
CLI presentation lives in interfaces/cli/commands/agent_commands.py.
Extracted 2026-08-14 from claude_agents_sdk.py.
"""

import json
import os
import time
import uuid
from pathlib import Path

SESSIONS_DIR = Path(os.path.expanduser("~/.ai-coder/agent_sessions"))

# Session budgets (v1.39.0) — platform.claude.com/docs/en/managed-agents/
# budgets, released Aug 7 2026, checked 2026-08-14. A budget is a hard USD
# spend cap on one session, encoded as whole US cents in a *string* (never
# a float, to avoid rounding). Pure validation constant, hence domain (the
# HTTP encoding that uses it, _encode_session_budget, is right below).
SESSION_BUDGET_MIN_CENTS = 1  # amount must be > 0


class PermissionMode:
    ACCEPT_EDITS = "acceptEdits"  # auto-approve all tool calls
    ASK_PERMISSION = "askPermission"  # ask user for each tool call
    SUPERVISED = "supervised"  # auto-approve reads, ask for writes


# ── Tool presets ───────────────────────────────────────────────────────────

TOOL_PRESETS = {
    "all": ["bash", "text_editor", "web_search", "code_execution"],
    "code": ["bash", "text_editor", "code_execution"],
    "web": ["web_search", "web_fetch"],
    "readonly": ["web_search", "web_fetch", "code_execution"],
    "filesystem": ["bash", "text_editor"],
}


class AgentSession:
    """Persistent session with message history and tool state."""

    def __init__(
        self, session_id: str = None, name: str = "", permission_mode: str = PermissionMode.ASK_PERMISSION
    ):
        self.id = session_id or str(uuid.uuid4())[:12]
        self.name = name or f"session-{self.id}"
        self.permission_mode = permission_mode
        self.history: list = []
        self.mcp_servers: list = []
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.updated_at = self.created_at
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, session_id: str) -> AgentSession:
        p = SESSIONS_DIR / f"{session_id}.json"
        if not p.exists():
            raise FileNotFoundError(f"Session {session_id} not found.")
        data = json.loads(p.read_text())
        s = cls.__new__(cls)
        s.__dict__.update(data)
        return s

    def save(self):
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        p = SESSIONS_DIR / f"{self.id}.json"
        p.write_text(json.dumps(self.__dict__, indent=2))

    def add_turn(self, role: str, content: str):
        self.history.append({"role": role, "content": content, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ")})

    def messages(self) -> list[dict]:
        return [{"role": t["role"], "content": t["content"]} for t in self.history]


# ── MCP connector config ───────────────────────────────────────────────────


class McpServerConfig:
    def __init__(self, type: str, name: str, **kwargs):
        self.type = type
        self.name = name
        self.extra = kwargs

    def to_dict(self) -> dict:
        return {"type": self.type, "name": self.name, **self.extra}

    @classmethod
    def stdio(cls, name: str, command: str, args: list = None) -> McpServerConfig:
        return cls("stdio", name, command=command, args=args or [])

    @classmethod
    def sse(cls, name: str, url: str, headers: dict = None) -> McpServerConfig:
        return cls("sse", name, url=url, headers=headers or {})

    @classmethod
    def http(cls, name: str, url: str, headers: dict = None) -> McpServerConfig:
        return cls("http", name, url=url, headers=headers or {})


# ── MCP tunnels (research preview) ─────────────────────────────────────────
# New surface (checked platform.claude.com/docs, 2026-07-02) for exposing a
# local MCP server — one only reachable on your machine/private network —
# to the Claude API without deploying it publicly first. Distinct from
# McpServerConfig above, which connects to an MCP server that's already
# reachable at a URL (sse/http) or spawnable as a local subprocess (stdio):
# a tunnel is what makes a *local* server reachable in the first place, so
# you can then hand its public tunnel URL to McpServerConfig.sse/http.
# Moved off the Admin API onto its own /v1/tunnels surface in the last
# couple of months per the release notes; research preview, so this can
# still change shape — re-verify before depending on it for anything but
# local dev/testing.
# (MCP_TUNNELS_BETA / TUNNELS_ENDPOINT themselves live in
# infrastructure/anthropic_api/agents_gateway.py, alongside the McpTunnel
# class that's the only consumer — an HTTP endpoint constant belongs with
# the transport code, not the domain layer.)


def _encode_session_budget(usd_cents: int) -> dict:
    if not isinstance(usd_cents, int) or isinstance(usd_cents, bool):
        raise ValueError(f"budget_usd_cents must be an int, got {type(usd_cents).__name__}")
    if usd_cents < SESSION_BUDGET_MIN_CENTS:
        raise ValueError(
            f"budget_usd_cents must be > 0 (got {usd_cents}); the platform "
            f"rejects zero/negative caps with a 400"
        )
    return {"type": "limit", "max_list_cost": {"amount": str(usd_cents), "currency": "USD"}}


def _budget_to_dict(budget) -> dict | None:
    """Normalize the SDK's budget object/dict/None into a plain dict for
    local use (e.g. `mac.get_session(...)["budget"]`), without assuming
    the SDK response object shape beyond attribute access."""
    if budget is None:
        return None
    if isinstance(budget, dict):
        return budget
    max_list_cost = getattr(budget, "max_list_cost", None)
    return {
        "type": getattr(budget, "type", "limit"),
        "max_list_cost": (
            {
                "amount": getattr(max_list_cost, "amount", None),
                "currency": getattr(max_list_cost, "currency", "USD"),
            }
            if max_list_cost is not None
            else None
        ),
    }


def _list_cost_cents(usage) -> int | None:
    """Best-effort extraction of usage.list_cost.amount (whole US cents,
    as a string per the API) from a session's usage object, if present.
    Returns None rather than raising when a session has no budget (and
    so no list_cost is being tracked) or usage is otherwise absent."""
    if usage is None:
        return None
    list_cost = getattr(usage, "list_cost", None) if not isinstance(usage, dict) else usage.get("list_cost")
    if list_cost is None:
        return None
    amount = (
        getattr(list_cost, "amount", None) if not isinstance(list_cost, dict) else list_cost.get("amount")
    )
    return int(amount) if amount is not None else None


# Managed Agents memory stores (v1.19.0) — a workspace-scoped, persistent,
# versioned file directory mountable into a session's `resources`. Found via
# the anthropic-sdk-python v0.116.0 release note "api: add
# agent-memory-2026-07-22 beta header" (checked 2026-07-08); confirmed
# against platform.claude.com/docs' Managed Agents memory pages the same
# day. Not to be confused with the memory_20250818 client-side tool in
# claude_memory.py, which is a completely separate, older (2025-09-29,
# now GA) feature with different scope and storage model.
MEMORY_STORE_BETA = "agent-memory-2026-07-22"

# Dreaming (v1.20.0) — research preview: reads a memory store plus past
# session transcripts and produces a new, curated output memory store.
# Found via this cycle's audit re-checking Managed Agents docs for what
# shipped alongside the memory-store feature closed in v1.19.0 (per that
# cycle's own note that "Dreaming" was mentioned alongside it). Confirmed
# genuinely absent: a first grep for "dream" found zero matches, and a
# second, differently-worded grep for "curat|reflect.*session|memory.*
# consolidat" also came up empty before this was written up as a gap.
DREAMING_BETA = "dreaming-2026-04-21"

# Dreaming's supported-models list (v1.35.0) — per
# platform.claude.com/docs/en/managed-agents/dreams#limits and the July 10,
# 2026 release note ("Dreams (research preview) now supports Claude Fable 5
# and Claude Sonnet 5. See Supported models."), checked 2026-07-26. This
# was flagged as a real, confirmed-but-deferred finding as far back as the
# v1.23.0 audit cycle (CHECKLIST.md: "Deliberately out of scope: Dreaming's
# July 10 Fable 5/Sonnet 5 expansion — Managed Agents concern, not a
# per-model-module concern") — deferred each time because it belongs here,
# in the Dreaming code itself, not in any of the per-model client modules
# that kept correctly declining to own it. This cycle is the first
# Dreaming-focused audit since the expansion shipped, so it's the first
# one positioned to actually close it.
DREAMING_SUPPORTED_MODELS = {
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-fable-5",
    "claude-sonnet-5",
}

# Limits#instructions-length: 4,096 characters. Not re-enforced server-side
# validation (the platform is the source of truth for the 400), just a
# client-side heads-up before an async job is queued only to fail later.
DREAMING_INSTRUCTIONS_MAX_CHARS = 4096


def validate_dreaming_model(model_id: str) -> str | None:
    """Return None if `model_id` is a supported Dreaming pipeline model, or
    a warning string if it isn't. Not a hard block — the platform itself is
    the source of truth for whether a request 400s — but every other
    per-model validator in this project (Opus 5 effort/thinking, Sonnet 5
    sampling params, mid-conversation tool changes) warns rather than
    silently proceeding, so this matches that convention."""
    if model_id in DREAMING_SUPPORTED_MODELS:
        return None
    return (
        f"{model_id} is not in claude_agents_sdk.DREAMING_SUPPORTED_MODELS "
        f"({', '.join(sorted(DREAMING_SUPPORTED_MODELS))}) — the dreaming "
        f"pipeline may reject this model with a 400."
    )


def validate_dreaming_instructions(instructions: str | None) -> str | None:
    """Return None if `instructions` is unset or within the documented
    4,096-character limit, or a warning string if it's over. Same
    not-a-hard-block convention as validate_dreaming_model() — the
    platform enforces the real limit, this just surfaces it before an
    async job gets queued only to fail minutes later."""
    if not instructions or len(instructions) <= DREAMING_INSTRUCTIONS_MAX_CHARS:
        return None
    return (
        f"dreaming instructions are {len(instructions)} chars, over the "
        f"documented {DREAMING_INSTRUCTIONS_MAX_CHARS}-char limit — the "
        f"platform will likely reject this with a 400."
    )


# Vaults & credentials (v1.21.0, public beta) — per
# platform.claude.com/docs/en/managed-agents/vaults (checked 2026-07-08):
# no separate beta header beyond managed-agents-2026-04-01. A vault is a
# workspace-scoped collection of third-party credentials (MCP OAuth,
# static bearer, or environment-variable secrets for CLIs/SDKs) keyed to
# an end user; referenced by vault_ids at session creation. The agent's
# sandbox only ever sees an opaque placeholder for environment_variable
# credentials — the real secret is substituted at the network egress
# boundary, only on allow-listed domains. Distinct from
# claude_admin_api.py's API-key management (Anthropic's own platform
# keys) and from this project's own local .env (never sent to a
# sandbox).

# Scheduled deployments (v1.21.0, public beta) — per
# platform.claude.com/docs/en/managed-agents/scheduled-deployments
# (checked 2026-07-08): no separate beta header beyond
# managed-agents-2026-04-01 either. A deployment pairs an agent +
# environment + initial user.message event with a cron `schedule`
# ({"type": "cron", "expression": ..., "timezone": ...}); each firing
# starts a brand-new session. Distinct from --agent-orchestrate (one-
# shot, client-invoked) and from claude_workflow.py (sequences steps
# within a single invocation, never starts new sessions on a timer).
MULTIAGENT_MAX_ROSTER = 20

# Files API beta header, needed alongside MANAGED_AGENTS_BETA when an
# Outcomes rubric is passed by file_id instead of inline text (v1.21.0).
FILES_API_BETA = "files-api-2025-04-14"


def build_multiagent_config(agents: list, advisor_model: str | None = None) -> dict:
    """Build the {"type": "coordinator", "agents": [...]} dict passed as
    `multiagent` to create_agent(), per platform.claude.com/docs/en/
    managed-agents/multi-agent (checked 2026-07-08).

    Each entry in `agents` may be:
      - a plain agent_id string -> expanded to {"type": "agent", "id": id}
      - {"type": "self"} -> lets the coordinator spawn copies of itself
      - an already-shaped dict (e.g. {"type": "agent", "id": ..., "version": ...})
        -> passed through unchanged

    `advisor_model` (v1.39.0, public beta, per platform.claude.com/docs/en/
    agents-and-tools/tool-use/advisor-tool and managed-agents/multi-agent,
    checked 2026-08-14), when given, appends a {"type": "advisor", "model":
    advisor_model} entry so the session's primary thread can consult that
    model mid-turn. This is the Managed Agents surface's version of the
    Messages API Advisor Tool (see claude_advisor.py) -- distinct
    configuration (roster entry, not a tool definition) and distinct
    delivery (thread events on the session's event stream, not
    advisor_tool_result content blocks). The roster entry takes no
    max_uses/max_tokens/caching options; those only apply to the Messages
    API tool form. The advisor occupies the reserved roster name
    "anthropic.advisor" -- the platform rejects a roster (400) that has
    both an advisor entry and a member literally named that. The
    platform also enforces (400 at save time, not checked here) that the
    advisor's model isn't *less* capable than the agent's own model --
    equal-capability pairs are fine, but an agent cannot "advise itself
    down". Raises ValueError only for the client-side-checkable roster
    size limit; model-pairing validity is left to the API.

    Raises ValueError if more than MULTIAGENT_MAX_ROSTER (20) entries are
    given — the API itself enforces this limit, but failing fast client-
    side gives a clearer error than a 4xx from the roster snapshot step."""
    if len(agents) > MULTIAGENT_MAX_ROSTER:
        raise ValueError(
            f"multiagent coordinator supports at most {MULTIAGENT_MAX_ROSTER} "
            f"agents in the roster, got {len(agents)}"
        )
    roster = []
    for a in agents:
        if isinstance(a, dict):
            roster.append(a)
        else:
            roster.append({"type": "agent", "id": a})
    if advisor_model is not None:
        roster.append({"type": "advisor", "model": advisor_model})
    return {"type": "coordinator", "agents": roster}


# Small built-in system-prompt presets for the --agent-review-multiagent
# CLI convenience wrapper (parallel specialist code review over one shared
# sandbox — the concrete zcoder use case that un-deferred Multiagent
# orchestration this cycle; see docs/35_upgrade_v1.21.0.md).
REVIEW_SPECIALIST_PRESETS = {
    "security": (
        "You are a security reviewer. Read the code at the given path and "
        "report vulnerabilities, unsafe input handling, secrets in source, "
        "and unsafe dependency usage. Be specific: file, line, and fix."
    ),
    "style": (
        "You are a style/lint reviewer. Read the code at the given path and "
        "report style inconsistencies, naming issues, dead code, and "
        "readability problems. Be specific: file, line, and fix."
    ),
    "test-coverage": (
        "You are a test-coverage reviewer. Read the code at the given path "
        "and report untested code paths, missing edge-case tests, and weak "
        "assertions. Be specific: file, function, and what test to add."
    ),
}
