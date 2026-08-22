"""
# mypy: ignore-errors
infrastructure/anthropic_api/tools_gateway.py — Live Anthropic API adapter
for custom + server tool use, and the local memory-tool handler
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Extracted 2026-08-16 from claude_tools.py, which mixed this HTTP/local-I/O
code with pure domain logic (now in domain/tools.py) and CLI
presentation/print() (now in interfaces/cli/commands/tools_commands.py).
Verbose per-tool-call logging inside run_agent()/generate_with_server_tools()
/run_agent_with_memory() previously called print() directly — converted to
optional callback hooks, same convention as messaging_gateway.py's
on_text/on_thinking (Phase B) and agents_service.py's on_step.

MemoryToolHandler does local-disk I/O (not an HTTP call), but stays here
rather than in a separate infrastructure/local_storage/ module — it's a
tool-use *adapter* (translates memory_20250818 tool_use blocks into
filesystem operations) in exactly the same sense ToolCoder is an adapter
for the Messages API, and the two are used together in
run_agent_with_memory().
"""

import json
import os
import shutil
import urllib.request
from collections.abc import Callable

from core.exceptions import ZCoderError
from domain.tools import (
    ADVANCED_TOOL_USE_BETA,
    COMPACTION_BETA,
    CONTEXT_MANAGEMENT_BETA,
    SERVER_TOOL_BETAS,
    SERVER_TOOLS,
    TASK_BUDGET_BETA,
    TASK_BUDGET_MODELS,
    ToolRegistry,
    build_context_management,
    computer_use_tool_for_model,
)
from infrastructure.anthropic_api.http_client import CircuitBreaker, retry, urlopen_json

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)
_NOOP = lambda *a, **k: None  # noqa: E731


class MemoryToolHandler:
    """Client-side handler for the memory_20250818 server tool. The memory
    tool is server-declared but client-executed: Claude emits tool_use
    blocks with a `command` field (view/create/str_replace/insert/delete/
    rename), and this class carries them out against a local directory,
    returning tool_result content for the next turn.

    All paths are confined to base_dir — every command's `path` argument
    is resolved and checked to still be inside base_dir before touching
    disk, per Anthropic's documented path-traversal-protection
    requirement for memory tool implementations."""

    def __init__(self, base_dir: str = "~/.zcoder/memory"):
        self.base_dir = os.path.abspath(os.path.expanduser(base_dir))
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve(self, rel_path: str) -> str:
        rel_path = rel_path.lstrip("/")
        if rel_path == "memories":
            rel_path = ""
        elif rel_path.startswith("memories/"):
            rel_path = rel_path[len("memories/") :]
        full = os.path.abspath(os.path.join(self.base_dir, rel_path))
        if not (full == self.base_dir or full.startswith(self.base_dir + os.sep)):
            raise PermissionError(f"Path escapes memory directory: {rel_path}")
        return full

    def handle(self, command_input: dict) -> str:
        cmd = command_input.get("command")
        try:
            if cmd == "view":
                path = self._resolve(command_input.get("path", "/memories"))
                if os.path.isdir(path):
                    entries = sorted(os.listdir(path))
                    return "\n".join(entries) if entries else "(empty directory)"
                with open(path) as f:
                    return f.read()
            elif cmd == "create":
                path = self._resolve(command_input["path"])
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(command_input.get("file_text", ""))
                return f"Created {command_input['path']}"
            elif cmd == "str_replace":
                path = self._resolve(command_input["path"])
                with open(path) as f:
                    content = f.read()
                old, new = command_input["old_str"], command_input.get("new_str", "")
                if content.count(old) != 1:
                    return f"[ERROR] old_str must match exactly once, found {content.count(old)}"
                with open(path, "w") as f:
                    f.write(content.replace(old, new, 1))
                return f"Edited {command_input['path']}"
            elif cmd == "insert":
                path = self._resolve(command_input["path"])
                with open(path) as f:
                    lines = f.readlines()
                idx = command_input.get("insert_line", len(lines))
                lines.insert(idx, command_input.get("insert_text", "") + "\n")
                with open(path, "w") as f:
                    f.writelines(lines)
                return f"Inserted into {command_input['path']} at line {idx}"
            elif cmd == "delete":
                path = self._resolve(command_input["path"])
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                return f"Deleted {command_input['path']}"
            elif cmd == "rename":
                src = self._resolve(command_input["old_path"])
                dst = self._resolve(command_input["new_path"])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.rename(src, dst)
                return f"Renamed {command_input['old_path']} -> {command_input['new_path']}"
            else:
                return f"[ERROR] Unknown memory command: {cmd}"
        except FileNotFoundError:
            return f"[ERROR] Not found: {command_input.get('path')}"
        except PermissionError as e:
            return f"[ERROR] {e}"
        except Exception as e:
            return f"[ERROR] {e}"


class ToolCoder:
    """Claude client with full tool-use support."""

    ENDPOINT = MESSAGES_ENDPOINT

    def __init__(self, api_key: str, model: str = "claude-sonnet-5", max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, req: urllib.request.Request) -> dict:
        return urlopen_json(req, timeout=120)

    def _post(self, payload: dict, extra_headers: dict | None = None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            **(extra_headers or {}),
        }
        req = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            return self._call(req)
        except ZCoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def generate_with_tools(
        self,
        prompt: str,
        tools: list,
        system: str | None = None,
        parallel: bool = True,
        strict: bool = False,
    ) -> dict:
        """Call Claude with tools. Returns raw response dict."""
        if strict:
            tools = [dict(t, **{"strict": True}) for t in tools]
        payload: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "tools": tools,
        }
        if not parallel:
            payload["parallel_tool_use"] = False
        if system:
            payload["system"] = system
        return self._post(payload)

    def run_agent(
        self,
        prompt: str,
        registry: ToolRegistry,
        system: str | None = None,
        max_turns: int = 10,
        on_tool_call: Callable[[str, dict], None] = _NOOP,
    ) -> str:
        """Full agentic loop: Claude calls tools, we execute them and
        return results, repeat until stop_reason == 'end_turn'."""
        messages = [{"role": "user", "content": prompt}]
        tools = registry.definitions()
        turn = 0

        while turn < max_turns:
            payload: dict = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": messages,
                "tools": tools,
            }
            if system:
                payload["system"] = system

            data = self._post(payload)
            if "error" in data:
                return f"[ERROR] {data['error']}"

            stop_reason = data.get("stop_reason", "")
            content = data.get("content", [])
            messages.append({"role": "assistant", "content": content})

            if stop_reason == "end_turn":
                return "".join(b.get("text", "") for b in content if b.get("type") == "text")
            if stop_reason != "tool_use":
                return f"[UNEXPECTED stop_reason={stop_reason}]"

            tool_results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                tool_name = block["name"]
                tool_id = block["id"]
                tool_input = block.get("input", {})
                on_tool_call(tool_name, tool_input)
                result = registry.execute(tool_name, tool_input)
                tool_results.append({"type": "tool_result", "tool_use_id": tool_id, "content": str(result)})

            messages.append({"role": "user", "content": tool_results})
            turn += 1

        return "[MAX TURNS REACHED]"

    def generate_with_server_tools(
        self,
        prompt: str,
        tool_names: list,
        system: str | None = None,
        context_management: dict | None = None,
        task_budget: dict | None = None,
        extra_tools: list | None = None,
        response_inclusion: str | None = None,
        on_warning: Callable[[str], None] = _NOOP,
    ) -> str:
        """Use Anthropic-hosted server tools (web_search, code_execution,
        memory, tool_search, etc.). Beta headers are assembled
        automatically from whichever features are actually used."""
        tools = []
        betas = []
        for name in tool_names:
            if name not in SERVER_TOOLS:
                raise ValueError(f"Unknown server tool: {name}. Available: {list(SERVER_TOOLS)}")
            if name == "computer_use":
                _cu_defaults = SERVER_TOOLS["computer_use"]
                tool, beta = computer_use_tool_for_model(
                    self.model,
                    width=_cu_defaults["display_width_px"],
                    height=_cu_defaults["display_height_px"],
                )
                tools.append(tool)
                if beta:
                    betas.append(beta)
                continue
            tool = dict(SERVER_TOOLS[name])
            if response_inclusion is not None and name in ("web_search", "web_fetch"):
                tool["response_inclusion"] = response_inclusion
            tools.append(tool)
            beta = SERVER_TOOL_BETAS.get(name)
            if beta:
                betas.append(beta)

        for t in extra_tools or []:
            tools.append(t)
            if "input_examples" in t or "allowed_callers" in t:
                betas.append(ADVANCED_TOOL_USE_BETA)

        headers_extra = {}
        payload: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "tools": tools,
        }
        if system:
            payload["system"] = system
        if context_management is not None:
            payload["context_management"] = context_management
            betas.append(CONTEXT_MANAGEMENT_BETA)
            if any(e.get("type") == "compact_20260112" for e in context_management.get("edits", [])):
                betas.append(COMPACTION_BETA)
        if task_budget is not None:
            if self.model not in TASK_BUDGET_MODELS:
                on_warning(
                    f"task_budget requested but {self.model} isn't in "
                    f"TASK_BUDGET_MODELS ({sorted(TASK_BUDGET_MODELS)}) — sending anyway, "
                    f"the API will reject it if unsupported."
                )
            payload["task_budget"] = task_budget
            betas.append(TASK_BUDGET_BETA)
        if betas:
            headers_extra["anthropic-beta"] = ",".join(sorted(set(betas)))

        data = self._post(payload, extra_headers=headers_extra)
        if "error" in data:
            return f"[API ERROR {data.get('status', '')}] {data['error']}"
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    def run_agent_with_memory(
        self,
        prompt: str,
        memory: MemoryToolHandler,
        extra_tools: list | None = None,
        system: str | None = None,
        max_turns: int = 10,
        use_context_management: bool = True,
        on_memory_op: Callable[[str, str], None] = _NOOP,
    ) -> str:
        """Agentic loop wired to the native memory tool: any tool_use block
        named 'memory' is dispatched to MemoryToolHandler instead of a
        registry lookup, so the memory directory persists across calls."""
        tools = [dict(SERVER_TOOLS["memory"])] + (extra_tools or [])
        betas = [CONTEXT_MANAGEMENT_BETA] if use_context_management else []
        messages = [{"role": "user", "content": prompt}]
        turn = 0

        while turn < max_turns:
            payload: dict = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": messages,
                "tools": tools,
            }
            if system:
                payload["system"] = system
            if use_context_management:
                payload["context_management"] = build_context_management()

            headers_extra = {}
            if betas:
                headers_extra["anthropic-beta"] = ",".join(sorted(set(betas)))
            data = self._post(payload, extra_headers=headers_extra)
            if "error" in data:
                return f"[API ERROR {data.get('status', '')}] {data['error']}"

            stop_reason = data.get("stop_reason", "")
            content = data.get("content", [])
            messages.append({"role": "assistant", "content": content})

            if stop_reason == "end_turn":
                return "".join(b.get("text", "") for b in content if b.get("type") == "text")
            if stop_reason != "tool_use":
                return f"[UNEXPECTED stop_reason={stop_reason}]"

            tool_results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                on_memory_op(block["input"].get("command", ""), block["input"].get("path", ""))
                result = memory.handle(block.get("input", {}))
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block["id"], "content": str(result)}
                )
            messages.append({"role": "user", "content": tool_results})
            turn += 1

        return "[MAX TURNS REACHED]"
