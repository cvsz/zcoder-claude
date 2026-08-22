"""
# mypy: ignore-errors
infrastructure/anthropic_api/code_agent_loop_gateway.py — the Claude Code
/ Agent SDK agentic loop (Messages API), reimplemented in pure stdlib
Python
AI Model Coder CLI v1.49.0 (Clean Architecture refactor, Phase C)

Extracted 2026-08-17 from claude_code.py's CodeAgent and
StructuredAgentOutput classes.

CodeAgent._execute_tool() previously had a non-interactive-mode fallback
that called print() + input() directly inline, to ask the terminal user
whether to approve a tool call when no `can_use_tool` callback was
supplied — this only ran for non-read-only tools; when a callback WAS
supplied, the original called it for every tool including read-only
ones. Converted to a required callback parameter that's now always
called under permission="askPermission" (matching the "callback
supplied" branch's every-tool behavior exactly): `can_use_tool` defaults
to `default_can_use_tool`, a safe non-interactive function that
auto-approves read-only tools and denies everything else, instead of
blocking on stdin. interfaces/cli/commands/code_agent_loop_commands.py
supplies the real input()-based interactive callback for a
terminal-attached CLI, reproducing the original's exact interactive
behavior (auto-approve reads, prompt for the rest) — see that module's
_interactive_can_use_tool.
"""

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from core.exceptions import ZCoderError
from domain.agent_execution import SandboxViolation, enforce
from domain.code_agent import READ_ONLY_TOOLS, build_tool_definitions
from domain.tools import CONTEXT_MANAGEMENT_BETA
from infrastructure.anthropic_api.http_client import CircuitBreaker, raise_for_http_error, retry, urlopen_json
from infrastructure.local_storage.code_agent_store import CodeSession, HooksEngine, MemoryManager, TodoManager

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)
_NOOP = lambda *a, **k: None  # noqa: E731


def default_can_use_tool(tool_name: str, tool_input: dict) -> bool:
    """Safe non-interactive default: auto-approve read-only tools, deny
    everything else. Called for EVERY tool under permission="askPermission"
    — matching the original's "if can_use_tool: call it for every tool"
    branch exactly. interfaces/cli/commands/code_agent_loop_commands.py's
    interactive callback also auto-approves read-only tools immediately
    (matching this policy) and only calls input() for the rest — so a
    terminal-attached CLI reproduces the original's exact interactive
    behavior, while any other caller gets this safe default instead of
    silently blocking on stdin."""
    return tool_name in READ_ONLY_TOOLS


class CodeAgent:
    """Full Claude Code / Agent SDK implementation using the Messages
    API. Replicates the Agent SDK's query() loop in pure stdlib Python."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5", max_tokens: int = 8192):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict, betas: list | None = None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        if betas:
            headers["anthropic-beta"] = ",".join(betas)
        req = urllib.request.Request(
            MESSAGES_ENDPOINT, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict, betas: list | None = None) -> dict:
        try:
            return self._call(payload, betas)
        except ZCoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    # No CircuitBreaker: WebFetch targets a different, arbitrary URL each
    # time (agent-chosen), not one fixed downstream dependency.
    @retry(max_attempts=2, base_delay=1.0, max_delay=5.0)
    def _webfetch_retrying(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "zcoder-agent/1.8"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8", errors="replace")[:4000]
        except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
            raise_for_http_error(e)

    def _build_tools(self, preset: str, allowed: list) -> list:
        return build_tool_definitions(preset, allowed)

    def _execute_tool(
        self,
        name: str,
        inputs: dict,
        session: CodeSession,
        hooks: HooksEngine,
        permission: str,
        can_use_tool: Callable[[str, dict], bool] = default_can_use_tool,
        on_permission_prompt: Callable[[str, dict], None] = _NOOP,
        on_warning: Callable[[str], None] = _NOOP,
    ) -> str:
        """Execute a tool call with permission checking and hooks."""
        hook_result = hooks.pre_tool_use(name, inputs, session, on_warning=on_warning)
        if not hook_result["allowed"]:
            return f"[BLOCKED by hook] {hook_result['message']}"

        if permission == "planMode":
            return "[PLAN MODE] Tool not executed — plan only."
        if permission == "dontAsk":
            return "[DENIED] Tool not in allowed list."
        if permission == "askPermission":
            on_permission_prompt(name, inputs)
            if not can_use_tool(name, inputs):
                return "[DENIED by user]"

        result = self._run_tool(name, inputs, session)
        session.add_tool_call(name, inputs, result[:200])
        hooks.post_tool_use(name, inputs, result, session, on_warning=on_warning)
        return result

    def _run_tool(self, name: str, inputs: dict, session: CodeSession) -> str:
        """Actually execute a built-in tool."""
        cwd = session.cwd
        try:
            if name == "Read":
                p = Path(cwd) / inputs["path"]
                return p.read_text()[:8000]

            elif name == "Write":
                p = Path(cwd) / inputs["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(inputs["content"])
                return f"Written {len(inputs['content'])} chars to {inputs['path']}"

            elif name == "Edit":
                p = Path(cwd) / inputs["path"]
                content = p.read_text()
                new = content.replace(inputs["old_string"], inputs["new_string"], 1)
                if new == content:
                    return f"[WARN] old_string not found in {inputs['path']}"
                p.write_text(new)
                return f"Edited {inputs['path']}"

            elif name == "Bash":
                cmd = inputs["command"]
                timeout = inputs.get("timeout", 30)
                if os.environ.get("ZCODER_SANDBOX") == "1":
                    try:
                        roots = json.loads(os.environ.get("ZCODER_SANDBOX_ROOTS", "[]"))
                        allow_net = os.environ.get("ZCODER_SANDBOX_NET") == "1"
                        enforce(cmd, cwd, allow_net=allow_net, extra_roots=roots)
                    except SandboxViolation as e:
                        return f"[SANDBOX BLOCKED] {e}"
                r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
                out, err = r.stdout.strip(), r.stderr.strip()
                if r.returncode != 0:
                    return f"EXIT {r.returncode}\nSTDOUT:\n{out}\nSTDERR:\n{err}"
                return out or "(no output)"

            elif name == "Glob":
                pattern = inputs["pattern"]
                base = Path(cwd) / inputs.get("path", ".")
                matches = sorted(base.glob(pattern))
                return "\n".join(str(m.relative_to(cwd)) for m in matches[:100])

            elif name == "Grep":
                pattern = inputs["pattern"]
                base = Path(cwd) / inputs.get("path", ".")
                include = inputs.get("include", "*")
                results = []
                for f in base.rglob(include):
                    if not f.is_file():
                        continue
                    try:
                        for i, line in enumerate(f.read_text().splitlines(), 1):
                            if re.search(pattern, line):
                                results.append(f"{f.relative_to(cwd)}:{i}: {line.strip()}")
                    except Exception:
                        pass
                return "\n".join(results[:200]) or "(no matches)"

            elif name == "LS":
                p = Path(cwd) / inputs.get("path", ".")
                return "\n".join(sorted(str(c.name) for c in p.iterdir()))

            elif name == "WebSearch":
                return f"[WebSearch] {inputs['query']} — requires live network"

            elif name == "WebFetch":
                try:
                    return self._webfetch_retrying(inputs["url"])
                except Exception as e:
                    return f"[WebFetch error] {e}"

            elif name == "TodoRead":
                tm = TodoManager()
                return json.dumps(tm.list(), indent=2)

            elif name == "TodoWrite":
                tm = TodoManager()
                todos = inputs.get("todos", [])
                for t in todos:
                    if t.get("status") == "done":
                        tm.complete(t.get("id", ""))
                    else:
                        tm.add(t.get("content", ""), t.get("priority", "medium"))
                return f"Updated {len(todos)} todos"

            else:
                return f"[Tool {name} not implemented in local runner]"

        except Exception as e:
            return f"[Tool {name} error] {e}"

    # ── Main agent loop ────────────────────────────────────────────────

    def query(
        self,
        prompt: str,
        session: CodeSession,
        tools: str = "all",
        allowed: list = None,
        disallowed: list = None,
        permission: str = "askPermission",
        hooks: HooksEngine = None,
        max_turns: int = 10,
        can_use_tool: Callable[[str, dict], bool] = default_can_use_tool,
        output_mode: str = "stream",
        system_extra: str = "",
        context_management: dict | None = None,
        on_turn_start: Callable[[int], None] = _NOOP,
        on_text: Callable[[str], None] = _NOOP,
        on_tool_call: Callable[[str, dict], None] = _NOOP,
        on_permission_prompt: Callable[[str, dict], None] = _NOOP,
        on_warning: Callable[[str], None] = _NOOP,
    ) -> str:
        """Full agentic query loop. `output_mode="stream"` invokes
        on_turn_start/on_text/on_tool_call live as the loop runs (the CLI
        layer wires these to print()); `output_mode="json"` returns a
        JSON summary string instead of the final text; anything else
        returns just the final text, silently.

        context_management: pass a payload built by
        domain.agent_execution.build_context_management() [was
        claude_tools.build_context_management() pre-migration] to
        auto-clear stale tool results once the conversation crosses a
        token trigger.
        """
        hooks = hooks or HooksEngine()
        memory = MemoryManager()

        sys_parts = []
        mem = memory.combined()
        if mem:
            sys_parts.append(mem)
        if session.system_prompt:
            sys_parts.append(session.system_prompt)
        if system_extra:
            sys_parts.append(system_extra)
        sys_parts.append(
            f"You are working in directory: {session.cwd}\n"
            f"Permission mode: {permission}\n"
            f"Use the available tools to complete the task."
        )
        system = "\n\n".join(sys_parts)

        tool_defs = self._build_tools(tools, allowed or [])
        if disallowed:
            tool_defs = [t for t in tool_defs if t["name"] not in disallowed]

        session.add_turn("user", prompt)

        turn = 0
        final_text = ""

        while turn < max_turns:
            payload: dict = {
                "model": session.model or self.model,
                "max_tokens": self.max_tokens,
                "system": system,
                "messages": session.messages(),
            }
            if tool_defs and permission != "planMode":
                payload["tools"] = tool_defs

            betas = []
            if context_management is not None:
                payload["context_management"] = context_management
                betas.append(CONTEXT_MANAGEMENT_BETA)

            if output_mode == "stream":
                on_turn_start(turn + 1)

            data = self._post(payload, betas=betas or None)
            if "error" in data:
                return f"[ERROR] {data['error']}"

            stop_reason = data.get("stop_reason", "end_turn")
            content = data.get("content", [])
            usage = data.get("usage", {})

            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            if text:
                final_text = text
                if output_mode == "stream":
                    on_text(text)

            session.add_turn("assistant", text or "[tool use]", usage)
            session.save()

            if stop_reason == "end_turn":
                break
            if stop_reason != "tool_use":
                break

            tool_results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                tname = block["name"]
                tinput = block.get("input", {})
                tid = block["id"]

                if output_mode == "stream":
                    on_tool_call(tname, tinput)

                if disallowed and tname in disallowed:
                    result = f"[DENIED] {tname} is in disallowed_tools"
                else:
                    result = self._execute_tool(
                        tname,
                        tinput,
                        session,
                        hooks,
                        permission,
                        can_use_tool,
                        on_permission_prompt,
                        on_warning,
                    )

                tool_results.append({"type": "tool_result", "tool_use_id": tid, "content": str(result)})

            if tool_results:
                session.add_turn("user", json.dumps(tool_results))

            turn += 1

        if output_mode == "json":
            return json.dumps(
                {
                    "session_id": session.id,
                    "result": final_text,
                    "turns": turn,
                    "cost": session.cost_summary(),
                }
            )

        return final_text


class StructuredAgentOutput:
    """Get JSON-structured output from the agent loop."""

    def __init__(self, agent: CodeAgent):
        self.agent = agent

    def query_json(self, prompt: str, schema: dict, session: CodeSession) -> dict:
        full_prompt = (
            f"{prompt}\n\nRespond ONLY with a valid JSON object matching this schema:\n"
            f"{json.dumps(schema, indent=2)}\nNo markdown, no explanation — pure JSON only."
        )
        result = self.agent.query(
            full_prompt, session, tools="none", permission="dontAsk", output_mode="text"
        )
        try:
            clean = result.strip()
            if clean.startswith("```"):
                clean = "\n".join(clean.split("\n")[1:]).rstrip("`").strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            return {"raw": result, "parse_error": True}
