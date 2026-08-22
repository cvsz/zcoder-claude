"""
# mypy: ignore-errors
infrastructure/local_storage/code_agent_store.py — local-disk persistence
and subprocess execution for Claude Code / Agent SDK sessions, hooks,
MCP config, subagents, skills, todos, and memory (CLAUDE.md)
AI Model Coder CLI v1.49.0 (Clean Architecture refactor, Phase C)

Extracted 2026-08-17 from claude_code.py's CodeSession, HooksEngine,
McpConnector, SubagentRegistry, SkillsRegistry, TodoManager, and
MemoryManager classes — all local-disk-backed (some also run subprocess
hook commands), none make an HTTP call, so none belong in
infrastructure/anthropic_api/. That package instead holds CodeAgent (the
class in this bounded context that actually calls the Messages API) —
see infrastructure/anthropic_api/code_agent_loop_gateway.py.
"""

import json
import os
import subprocess
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from domain.code_agent import (
    AGENTS_DIR,
    ANTHROPIC_MANAGED_SKILLS,
    HOOKS_DIR,
    MCP_JSON,
    SESSIONS_DIR,
    SETTINGS_JSON,
    SKILLS_DIR,
    TODO_FILE,
    USER_MEMORY,
    extract_skill_description,
    parse_frontmatter,
)

for _d in (SESSIONS_DIR, HOOKS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

_NOOP = lambda *a, **k: None  # noqa: E731


# ── Session ──────────────────────────────────────────────────────────────


class CodeSession:
    """Persistent Agent SDK session with full history and metadata."""

    def __init__(
        self,
        session_id: str = None,
        cwd: str = ".",
        model: str = "claude-sonnet-5",
        permission_mode: str = "askPermission",
        system_prompt: str = None,
    ):
        self.id = session_id or str(uuid.uuid4())[:16]
        self.cwd = str(Path(cwd).resolve())
        self.model = model
        self.permission_mode = permission_mode
        self.system_prompt = system_prompt or ""
        self.turns: list = []
        self.tool_calls: list = []
        self.mcp_servers: dict = {}
        self.allowed_tools: list = []
        self.hooks: dict = {}
        self.cost_usd: float = 0.0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.updated_at = self.created_at
        self.checkpoints: list = []

    @classmethod
    def load(cls, session_id: str) -> CodeSession:
        p = SESSIONS_DIR / f"{session_id}.json"
        if not p.exists():
            raise FileNotFoundError(f"Session '{session_id}' not found.")
        data = json.loads(p.read_text())
        s = cls.__new__(cls)
        s.__dict__.update(data)
        return s

    def save(self):
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        (SESSIONS_DIR / f"{self.id}.json").write_text(json.dumps(self.__dict__, indent=2))

    def add_turn(self, role: str, content: str, usage: dict = None):
        self.turns.append(
            {
                "role": role,
                "content": content,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "usage": usage or {},
            }
        )
        if usage:
            self.input_tokens += usage.get("input_tokens", 0)
            self.output_tokens += usage.get("output_tokens", 0)
            # Cost estimate now reads the actual session model's price
            # from the catalog instead of a hardcoded "Sonnet 4.5 rates"
            # $3/$15 literal — found 2026-08-16 while reading this file
            # ahead of migration (docs/54_bugfix_upgrade_target_opus5_sonnet5.md
            # neighbor finding), same duplication anti-pattern §0
            # describes; fixed as part of this migration rather than
            # left for a second pass, since the old constant would
            # otherwise need translating into the new module anyway.
            from domain.models.catalog import get_price

            price = get_price(self.model)
            self.cost_usd += (
                usage.get("input_tokens", 0) / 1e6 * price["in"]
                + usage.get("output_tokens", 0) / 1e6 * price["out"]
            )

    def add_tool_call(self, name: str, inputs: dict, result: str, approved: bool = True):
        self.tool_calls.append(
            {
                "name": name,
                "inputs": inputs,
                "result": result,
                "approved": approved,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )

    def checkpoint(self, label: str = ""):
        cp = {
            "id": str(uuid.uuid4())[:8],
            "label": label or f"checkpoint-{len(self.checkpoints)+1}",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "turn": len(self.turns),
        }
        self.checkpoints.append(cp)
        return cp

    def messages(self) -> list:
        return [{"role": t["role"], "content": t["content"]} for t in self.turns]

    def cost_summary(self) -> str:
        return (
            f"Session {self.id[:8]}  |  in={self.input_tokens:,}  "
            f"out={self.output_tokens:,}  cost≈${self.cost_usd:.4f}"
        )


# ── Hooks Engine (claude_code.py's own — see domain/code_agent.py note) ────


class HooksEngine:
    """Execute hook scripts/callbacks at agent lifecycle events. Hooks
    receive JSON via stdin and return: exit 0 → proceed, exit 2 → block
    (message in stdout fed back to Claude), exit 1 → non-blocking warning."""

    def __init__(self, hooks_config: dict = None):
        self.config = hooks_config or {}

    @classmethod
    def from_settings(cls, settings_path: Path = SETTINGS_JSON) -> HooksEngine:
        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text())
                return cls(data.get("hooks", {}))
            except Exception:
                pass
        return cls()

    @classmethod
    def from_file(cls, hooks_file: str, on_warning: Callable[[str], None] = _NOOP) -> HooksEngine:
        try:
            data = json.loads(Path(hooks_file).read_text())
            return cls(data)
        except Exception as e:
            on_warning(f"Could not load hooks from {hooks_file}: {e}")
            return cls()

    @classmethod
    def with_plugins(cls, base: HooksEngine) -> HooksEngine:
        """Merge plugin-bundled hooks.json files into an existing engine's config."""
        try:
            from domain.plugins import enabled_plugin_dirs, load_plugin_hooks
            from infrastructure.local_storage.plugins_store import _load_registry

            plugin_hooks = load_plugin_hooks(
                enabled_plugin_dirs(_load_registry().get("installed", {}))
            )
        except ImportError:
            return base
        merged = dict(base.config)
        for event, handlers in plugin_hooks.items():
            merged.setdefault(event, [])
            merged[event] = merged[event] + handlers
        return cls(merged)

    def fire(self, event: str, payload: dict, on_warning: Callable[[str], None] = _NOOP) -> dict:
        """Fire a hook event. Returns {"allowed": bool, "message": str}."""
        handlers = self.config.get(event, [])
        if not handlers:
            return {"allowed": True, "message": ""}

        stdin_data = json.dumps(payload)
        for handler in handlers:
            cmd = handler.get("command", "")
            env = {**os.environ, **handler.get("env", {})}
            if not cmd:
                continue
            try:
                result = subprocess.run(
                    cmd, shell=True, input=stdin_data, capture_output=True, text=True, timeout=30, env=env
                )
                if result.returncode == 2:
                    msg = result.stdout.strip() or result.stderr.strip()
                    return {"allowed": False, "message": msg}
                if result.returncode == 1:
                    on_warning(f"[hook:{event}] {result.stdout.strip()}")
            except subprocess.TimeoutExpired:
                on_warning(f"[hook:{event}] timed out")
            except Exception as e:
                on_warning(f"[hook:{event}] error: {e}")

        return {"allowed": True, "message": ""}

    def pre_tool_use(
        self,
        tool_name: str,
        tool_input: dict,
        session: CodeSession,
        on_warning: Callable[[str], None] = _NOOP,
    ) -> dict:
        return self.fire(
            "PreToolUse",
            {
                "hook_event_name": "PreToolUse",
                "session_id": session.id,
                "cwd": session.cwd,
                "tool_name": tool_name,
                "tool_input": tool_input,
            },
            on_warning=on_warning,
        )

    def post_tool_use(
        self,
        tool_name: str,
        tool_input: dict,
        tool_response: str,
        session: CodeSession,
        on_warning: Callable[[str], None] = _NOOP,
    ):
        self.fire(
            "PostToolUse",
            {
                "hook_event_name": "PostToolUse",
                "session_id": session.id,
                "cwd": session.cwd,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_response": tool_response,
            },
            on_warning=on_warning,
        )

    def notify(self, message: str, session: CodeSession, on_warning: Callable[[str], None] = _NOOP):
        self.fire(
            "Notification",
            {"hook_event_name": "Notification", "session_id": session.id, "message": message},
            on_warning=on_warning,
        )


# ── MCP Connector ────────────────────────────────────────────────────────


class McpConnector:
    """Connect Claude to MCP servers. Supports stdio (subprocess), SSE, and
    HTTP transports. Loads .mcp.json from project root if present."""

    def __init__(self):
        self.servers: dict = {}

    @classmethod
    def from_json_file(
        cls, path: Path = MCP_JSON, on_warning: Callable[[str], None] = _NOOP
    ) -> McpConnector:
        mc = cls()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                mc.servers = data.get("mcpServers", {})
            except Exception as e:
                on_warning(f".mcp.json parse error: {e}")
        try:
            from domain.plugins import enabled_plugin_dirs, load_plugin_mcp_servers
            from infrastructure.local_storage.plugins_store import _load_registry

            mc.servers.update(
                load_plugin_mcp_servers(
                    enabled_plugin_dirs(_load_registry().get("installed", {}))
                )
            )
        except ImportError:
            pass
        return mc

    def add_stdio(self, name: str, command: str, args: list = None, env: dict = None):
        self.servers[name] = {"type": "stdio", "command": command, "args": args or [], "env": env or {}}

    def add_http(self, name: str, url: str, headers: dict = None):
        self.servers[name] = {"type": "http", "url": url, "headers": headers or {}}

    def add_sse(self, name: str, url: str, headers: dict = None):
        self.servers[name] = {"type": "sse", "url": url, "headers": headers or {}}

    def add_from_url(self, url: str):
        name = url.split("/")[-1].split("?")[0] or "mcp-server"
        if url.startswith("http"):
            self.add_http(name, url)
        else:
            self.add_stdio(name, url)

    def to_query_options(self) -> dict:
        return {"mcpServers": self.servers}

    def list_servers(self) -> list:
        return [{"name": k, **v} for k, v in self.servers.items()]

    def tool_name(self, server_name: str, tool: str) -> str:
        return f"mcp__{server_name}__{tool}"


# ── Subagent Registry ────────────────────────────────────────────────────


class SubagentRegistry:
    """Load subagent definitions from .claude/agents/*.md. YAML
    frontmatter: name, description, tools, disallowedTools, model, system_prompt."""

    def __init__(self, agents_dir: Path = AGENTS_DIR):
        self.dir = agents_dir
        self._agents: dict = {}

    def load(self, on_warning: Callable[[str], None] = _NOOP):
        if self.dir.exists():
            for f in self.dir.glob("*.md"):
                self._load_one(f, plugin=None, on_warning=on_warning)
        try:
            from domain.plugins import enabled_plugin_dirs, load_plugin_agents
            from infrastructure.local_storage.plugins_store import _load_registry

            for entry in load_plugin_agents(
                enabled_plugin_dirs(_load_registry().get("installed", {}))
            ):
                self._load_one(
                    Path(entry["path"]),
                    plugin=entry["plugin"],
                    namespace=f"{entry['plugin']}:{entry['name']}",
                    on_warning=on_warning,
                )
        except ImportError:
            pass

    def _load_one(
        self,
        f: Path,
        plugin: str | None = None,
        namespace: str | None = None,
        on_warning: Callable[[str], None] = _NOOP,
    ):
        try:
            content = f.read_text()
            meta, body = parse_frontmatter(content)
            name = namespace or meta.get("name") or f.stem
            self._agents[name] = {
                "name": name,
                "description": meta.get("description", ""),
                "tools": meta.get("tools", "all"),
                "disallowedTools": meta.get("disallowedTools", ""),
                "model": meta.get("model", ""),
                "system_prompt": body.strip(),
                "file": str(f),
                "plugin": plugin,
            }
        except Exception as e:
            on_warning(f"Could not load agent {f.name}: {e}")

    def list(self) -> list:
        return list(self._agents.values())

    def get(self, name: str) -> dict:
        return self._agents.get(name)

    def create(
        self, name: str, description: str, system_prompt: str, tools: str = "all", disallowed: str = ""
    ) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        content = (
            f"---\nname: {name}\ndescription: {description}\ntools: {tools}\n"
            + (f"disallowedTools: {disallowed}\n" if disallowed else "")
            + f"---\n\n{system_prompt}\n"
        )
        path = self.dir / f"{name}.md"
        path.write_text(content)
        return path


# ── Skills Registry ──────────────────────────────────────────────────────


class SkillsRegistry:
    """Load Agent Skills from .claude/skills/<n>/SKILL.md"""

    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self.dir = skills_dir
        self._skills: dict = {}

    def load(self):
        if self.dir.exists():
            for skill_dir in self.dir.iterdir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    content = skill_md.read_text()
                    name = skill_dir.name
                    self._skills[name] = {
                        "name": name,
                        "description": extract_skill_description(content),
                        "path": str(skill_md),
                        "source": "custom",
                    }
        for name, desc in ANTHROPIC_MANAGED_SKILLS.items():
            self._skills[name] = {"name": name, "description": desc, "path": "", "source": "anthropic"}
        try:
            from domain.plugins import enabled_plugin_dirs, load_plugin_skills
            from infrastructure.local_storage.plugins_store import _load_registry

            for entry in load_plugin_skills(
                enabled_plugin_dirs(_load_registry().get("installed", {}))
            ):
                content = Path(entry["path"]).read_text()
                key = f"{entry['plugin']}:{entry['name']}"
                self._skills[key] = {
                    "name": key,
                    "description": extract_skill_description(content),
                    "path": entry["path"],
                    "source": f"plugin:{entry['plugin']}",
                }
        except ImportError:
            pass

    def list(self) -> list:
        return list(self._skills.values())

    def get(self, name: str) -> dict:
        return self._skills.get(name)


# ── Todo List ────────────────────────────────────────────────────────────


class TodoManager:
    def __init__(self):
        self._todos: list = []
        if TODO_FILE.exists():
            try:
                self._todos = json.loads(TODO_FILE.read_text())
            except Exception:
                pass

    def _save(self):
        TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
        TODO_FILE.write_text(json.dumps(self._todos, indent=2))

    def add(self, text: str, priority: str = "medium") -> dict:
        item = {
            "id": str(uuid.uuid4())[:8],
            "text": text,
            "status": "todo",
            "priority": priority,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._todos.append(item)
        self._save()
        return item

    def complete(self, todo_id: str) -> bool:
        for t in self._todos:
            if t["id"] == todo_id:
                t["status"] = "done"
                t["done_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                self._save()
                return True
        return False

    def list(self) -> list:
        return self._todos

    def pending(self) -> list:
        return [t for t in self._todos if t["status"] != "done"]


# ── Memory (CLAUDE.md) ───────────────────────────────────────────────────


class MemoryManager:
    """Read/write CLAUDE.md project and user memory."""

    def read_project(self) -> str:
        for p in (Path(".claude/CLAUDE.md"), Path("CLAUDE.md")):
            if p.exists():
                return p.read_text()
        return ""

    def read_user(self) -> str:
        return USER_MEMORY.read_text() if USER_MEMORY.exists() else ""

    def append_project(self, content: str):
        p = Path(".claude/CLAUDE.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a") as f:
            f.write(f"\n{content}\n")

    def append_user(self, content: str):
        USER_MEMORY.parent.mkdir(parents=True, exist_ok=True)
        with open(USER_MEMORY, "a") as f:
            f.write(f"\n{content}\n")

    def combined(self) -> str:
        parts = []
        u = self.read_user()
        p = self.read_project()
        if u:
            parts.append(f"# User Memory\n{u}")
        if p:
            parts.append(f"# Project Memory\n{p}")
        return "\n\n".join(parts)
