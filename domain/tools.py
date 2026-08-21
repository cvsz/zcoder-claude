"""
domain/tools.py — Tool Use & Retrieval bounded context: pure data + logic
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Domain layer: zero I/O, zero print(), zero HTTP. Extracted 2026-08-16 from
claude_tools.py and claude_rag.py, which previously mixed this pure logic
with HTTP transport (now in infrastructure/anthropic_api/tools_gateway.py,
.../search_gateway.py, .../rag_gateway.py, infrastructure/voyage_api/
embeddings_gateway.py) and local-disk persistence (now in
infrastructure/local_storage/rag_index_store.py) and CLI presentation
(now in interfaces/cli/commands/tools_commands.py) in the same files.
"""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# ── Server tool descriptors & beta-header routing (claude_tools.py) ────────

SERVER_TOOLS = {
    "web_search": {"type": "web_search_20260318", "name": "web_search"},
    "web_fetch": {"type": "web_fetch_20260318", "name": "web_fetch"},
    "code_execution": {"type": "code_execution_20260521", "name": "code_execution"},
    "bash": {"type": "bash_20250124", "name": "bash"},
    "text_editor": {"type": "text_editor_20250124", "name": "str_replace_based_edit_tool"},
    "computer_use": {
        "type": "computer_20251124",
        "name": "computer",
        "display_width_px": 1024,
        "display_height_px": 768,
    },
    "memory": {"type": "memory_20250818", "name": "memory"},
    "tool_search": {"type": "tool_search_tool_20251019", "name": "tool_search"},
}

COMPUTER_USE_TOOL_VERSIONS = {
    "2025-11-24": {"type": "computer_20251124", "beta": "computer-use-2025-11-24"},
    "2025-01-24": {"type": "computer_20250124", "beta": "computer-use-2025-01-24"},
}
_COMPUTER_USE_2025_01_24_MODELS = {
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-20250514",
    "claude-sonnet-4-0",
    "claude-opus-4-20250514",
    "claude-opus-4-0",
}

RETIRED_TOOL_VERSIONS: dict = {
    "web_search_20250305": {
        "replacement": "web_search_20260318",
        "notes": "Still works. 20260209 added dynamic content filtering; "
        "20260318 adds the response_inclusion param (drop a "
        "consumed result's blocks from the response — see "
        "programmatic tool calling).",
    },
    "web_search_20260209": {
        "replacement": "web_search_20260318",
        "notes": "Still works. 20260318 adds response_inclusion (v1.24.0).",
    },
    "web_fetch_20250910": {
        "replacement": "web_fetch_20260318",
        "notes": "Still works. 20260209 added dynamic content filtering, "
        "20260309 added use_cache, 20260318 adds response_inclusion "
        "(v1.24.0) — see Web fetch tool docs for the full chain.",
    },
    "web_fetch_20250124": {
        "replacement": "web_fetch_20260318",
        "notes": "Older than web_fetch_20250910 above — see that entry for "
        "the full upgrade chain to 20260318.",
    },
    "code_execution_20250522": {
        "replacement": "code_execution_20260521",
        "notes": "Still works, but 20260120 is the minimum version for "
        "programmatic tool calling (adds REPL-state persistence); "
        "20260521 additionally discloses the sandbox's 90-second "
        "per-cell wall-clock limit in the tool description "
        "(v1.24.0), so Claude budgets long-running cells.",
    },
    "code_execution_20250825": {
        "replacement": "code_execution_20260521",
        "notes": "Both 20250522 and 20250825 are accepted interchangeably "
        "in allowed_callers per the programmatic tool calling "
        "docs; 20260521 is current as of v1.24.0.",
    },
    "code_execution_20260120": {
        "replacement": "code_execution_20260521",
        "notes": "Still works and is still the minimum version for "
        "programmatic tool calling. 20260521 (v1.24.0) additionally "
        "discloses the sandbox's 90-second per-cell wall-clock "
        "limit in the tool description, so Claude budgets "
        "long-running cells instead of writing one loop that "
        "times out.",
    },
    "text_editor_20250124": {
        "replacement": "text_editor_20250728",
        "notes": "Model-keyed, not a strict upgrade: 20250124 is for pre-Claude-4 "
        "models, 20250728 is for Claude 4 series. Use the one matching "
        "your model, not automatically the newer string.",
    },
    "computer_20250124": {
        "replacement": "computer_20251124",
        "notes": "Model-keyed, see computer_use_tool_for_model() — current models "
        "(Sonnet 5, Opus 4.5+) use 20251124, older models still need "
        "20250124. Sending the wrong pairing 400s.",
    },
}


def check_retired_tool_version(tool_type: str) -> dict | None:
    """Return the retirement/upgrade record for a dated tool-type string,
    or None if it isn't tracked. Mirrors domain/models/catalog.py's
    check_retired() pattern — an unmatched string is just not tracked
    here, not necessarily current."""
    return RETIRED_TOOL_VERSIONS.get(tool_type)


def computer_use_tool_for_model(model: str, width: int = 1024, height: int = 768):
    """Return (tool_descriptor, beta_header_or_None) for the computer_use
    tool version this model actually supports."""
    key = "2025-01-24" if model in _COMPUTER_USE_2025_01_24_MODELS else "2025-11-24"
    v = COMPUTER_USE_TOOL_VERSIONS[key]
    tool = {"type": v["type"], "name": "computer", "display_width_px": width, "display_height_px": height}
    return tool, v["beta"]


SERVER_TOOL_BETAS = {
    "bash": "computer-use-2025-01-24",
    "text_editor": "computer-use-2025-01-24",
    "computer_use": "computer-use-2025-11-24",
    "tool_search": "tool-search-tool-2025-10-19",
}

CONTEXT_MANAGEMENT_BETA = "context-management-2025-06-27"
COMPACTION_BETA = "compact-2026-01-12"

TASK_BUDGET_BETA = "task-budgets-2026-03-13"
TASK_BUDGET_MODELS = {
    "claude-fable-5",
    "claude-mythos-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
}

ADVANCED_TOOL_USE_BETA = "advanced-tool-use-2025-11-20"

MID_CONVERSATION_TOOL_CHANGES_BETA = "mid-conversation-tool-changes-2026-07-01"
MID_CONVERSATION_TOOL_CHANGES_SUPPORTED = {
    "claude-fable-5",
    "claude-mythos-5",
    "claude-opus-4-8",
    "claude-opus-5",
}


def validate_mid_conversation_tool_change(model_id: str) -> str | None:
    """Return None if `model_id` supports mid-conversation tool changes,
    or a warning string if it doesn't. Not a hard block — the platform
    itself is the source of truth for whether a request 400s."""
    if model_id in MID_CONVERSATION_TOOL_CHANGES_SUPPORTED:
        return None
    return (
        f"{model_id} is not in MID_CONVERSATION_TOOL_CHANGES_SUPPORTED "
        f"(Fable 5, Mythos 5, Opus 4.8, Opus 5 only) — changing `tools` between "
        f"turns on this model may not preserve the prompt cache the way it does "
        f"on those four."
    )


def with_mid_conversation_tool_changes(headers: dict, model_id: str) -> dict:
    """Return `headers` with MID_CONVERSATION_TOOL_CHANGES_BETA appended
    to any existing `anthropic-beta` value, only when `model_id` supports
    the feature."""
    if model_id not in MID_CONVERSATION_TOOL_CHANGES_SUPPORTED:
        return headers
    existing = headers.get("anthropic-beta", "")
    parts = [p for p in existing.split(",") if p] if existing else []
    if MID_CONVERSATION_TOOL_CHANGES_BETA not in parts:
        parts.append(MID_CONVERSATION_TOOL_CHANGES_BETA)
    headers = dict(headers)
    headers["anthropic-beta"] = ",".join(parts)
    return headers


def build_context_management(
    clear_tool_uses: bool = True,
    clear_tool_uses_trigger_tokens: int = 30000,
    keep_last_n_tool_uses: int = 3,
    clear_thinking: bool = False,
    keep_last_n_thinking_turns: int = 2,
    compact: bool = False,
    compact_trigger_tokens: int = 150000,
    compact_instructions: str | None = None,
    compact_pause_after: bool = False,
) -> dict:
    """Build a context_management payload for long agent loops. See
    claude_tools.py's original docstring (preserved in the shim) for the
    full clear-vs-compact explanation."""
    edits = []
    if clear_tool_uses:
        edits.append(
            {
                "type": "clear_tool_uses_20250919",
                "trigger": {"type": "input_tokens", "value": clear_tool_uses_trigger_tokens},
                "keep": {"type": "tool_uses", "value": keep_last_n_tool_uses},
            }
        )
    if clear_thinking:
        edits.append(
            {
                "type": "clear_thinking_20251015",
                "keep": {"type": "thinking_turns", "value": keep_last_n_thinking_turns},
            }
        )
    if compact:
        edit = {
            "type": "compact_20260112",
            "trigger": {"type": "input_tokens", "value": compact_trigger_tokens},
        }
        if compact_instructions:
            edit["instructions"] = compact_instructions
        if compact_pause_after:
            edit["pause_after_compaction"] = True
        edits.append(edit)
    return {"edits": edits}


def resume_after_compaction(
    messages: list, compaction_response: dict, extra_content: list | None = None
) -> list:
    """After a call made with compact_pause_after=True returns
    stop_reason:"compaction", append the compaction block as an
    assistant turn before continuing."""
    content = list(compaction_response.get("content", []))
    if extra_content:
        content = content + extra_content
    return messages + [{"role": "assistant", "content": content}]


def build_task_budget(budget_tokens: int) -> dict:
    """Build the task_budget payload. Advisory only."""
    return {"budget_tokens": budget_tokens}


def with_input_examples(tool_def: dict, examples: list) -> dict:
    """Attach Tool Use Examples (input_examples) to a tool definition."""
    out = dict(tool_def)
    out["input_examples"] = examples
    return out


def with_allowed_callers(tool_def: dict, callers: list | None = None) -> dict:
    """Mark a custom tool definition as callable from Programmatic Tool
    Calling. callers defaults to the current code_execution tool type."""
    out = dict(tool_def)
    out["allowed_callers"] = callers or [SERVER_TOOLS["code_execution"]["type"]]
    return out


class ToolRegistry:
    """Register Python callables as Claude tools with pre-built schemas.
    Pure in-process dispatch — the callables it holds may do I/O when
    invoked (e.g. build_code_tools_registry()'s run_python/read_file), but
    the registry itself makes no HTTP calls and does no I/O of its own."""

    def __init__(self):
        self._tools: dict[str, dict] = {}
        self._funcs: dict[str, Callable] = {}

    def register(self, name: str, description: str, parameters: dict, func: Callable, strict: bool = False):
        defn = {"name": name, "description": description, "input_schema": parameters}
        if strict:
            defn["strict"] = True
        self._tools[name] = defn
        self._funcs[name] = func

    def definitions(self) -> list:
        return list(self._tools.values())

    def execute(self, name: str, inputs: dict):
        if name not in self._funcs:
            return f"[ERROR] Unknown tool: {name}"
        try:
            return self._funcs[name](**inputs)
        except Exception as e:
            return f"[TOOL ERROR] {e}"


# ── RAG: chunks, index shape, scoring (claude_rag.py) ───────────────────────

SUPPORTED_RAG_EXTS = {
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".go",
    ".java",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".html",
}


@dataclass
class Chunk:
    cid: str
    source: str
    content: str
    tokens: int = 0


@dataclass
class RAGIndex:
    name: str
    chunks: list[Chunk] = field(default_factory=list)
    idf: dict[str, float] = field(default_factory=dict)
    file_ids: dict[str, str] = field(default_factory=dict)  # cid → Files API id

    def to_dict(self):
        return {
            "name": self.name,
            "chunks": [
                {"cid": c.cid, "source": c.source, "content": c.content, "tokens": c.tokens}
                for c in self.chunks
            ],
            "idf": self.idf,
            "file_ids": self.file_ids,
        }

    @staticmethod
    def from_dict(d) -> RAGIndex:
        idx = RAGIndex(name=d["name"])
        idx.chunks = [Chunk(**c) for c in d.get("chunks", [])]
        idx.idf = d.get("idf", {})
        idx.file_ids = d.get("file_ids", {})
        return idx


def tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def chunk_text(source: str, text: str, size: int = 600, overlap: int = 100) -> list[Chunk]:
    words = text.split()
    chunks = []
    i = 0
    cid_base = Path(source).stem
    while i < len(words):
        end = min(i + size, len(words))
        content = " ".join(words[i:end])
        cid = f"{cid_base}_{i}"
        chunks.append(Chunk(cid=cid, source=source, content=content, tokens=end - i))
        i += size - overlap
    return chunks


def score_chunk(query_tokens: list[str], chunk: Chunk, idf: dict[str, float]) -> float:
    from collections import Counter

    tf = Counter(tokenize(chunk.content))
    score = 0.0
    for qt in query_tokens:
        if qt in tf:
            score += (tf[qt] / (tf[qt] + 1.5)) * idf.get(qt, 1.0)
    return score


def retrieve(idx: RAGIndex, query: str, k: int = 5) -> list[Chunk]:
    qt = tokenize(query)
    scored = [(c, score_chunk(qt, c, idx.idf)) for c in idx.chunks]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, s in scored[:k] if s > 0]


def build_idf(all_chunks_tokens: list[set], total: int) -> dict[str, float]:
    """Pure IDF computation given a list of per-chunk token sets — split
    out of build_index() (which does the file-walk I/O) so the actual
    math has no disk dependency."""
    from collections import Counter

    df: Counter = Counter()
    for token_set in all_chunks_tokens:
        for w in token_set:
            df[w] += 1
    return {w: math.log((total + 1) / (c + 1)) + 1 for w, c in df.items()}


# ── Embeddings: pure vector math (claude_embeddings.py) ─────────────────────


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Voyage embeddings are normalized to length 1, so dot product equals
    cosine similarity and is cheaper — but this stays a true cosine
    similarity so it's correct even against non-Voyage vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
