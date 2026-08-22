"""
infrastructure/anthropic_api/cowork_gateway.py — Cowork HTTP adapter
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

CoworkAgent, extracted 2026-08-22 from cowork.py. The only real I/O the
class performs against Anthropic is POST https://api.anthropic.com/v1/
messages via the shared resilience primitives (same CircuitBreaker/retry
pattern as every other gateway in this package).

Fidelity notes:
- run()'s original stream_progress banner prints moved to an
  on_progress(str) callback per the established HooksEngine/batch_gateway
  convention (print() lives in interfaces/ only); cmd_cowork wires
  on_progress=print, reproducing the original output exactly.
- The attachment-file reads inside run()/iterate() are local-disk reads
  inherited from the original single-file design; they stay inside the
  class to keep it intact rather than split method-by-method (same
  reasoning as CodeSession/PptxSession), and are capped at 12k/6k chars
  exactly as before.
"""

import json
import urllib.request
from collections.abc import Callable
from pathlib import Path

from domain.cowork import COWORK_TASKS, SYSTEM_PROMPTS, build_task_prompt
from exceptions import AICoderError
from infrastructure.anthropic_api.http_client import CircuitBreaker, retry, urlopen_json

ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

_NOOP: Callable[[str], None] = lambda *a, **k: None  # noqa: E731


# ── CoworkAgent ────────────────────────────────────────────────────────────


class CoworkAgent:
    """Autonomous multi-step task executor."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5", max_tokens: int = 8192):
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
            ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict) -> dict:
        try:
            return self._call(payload)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def run(
        self,
        task_type: str,
        prompt: str,
        files: list[str] | None = None,
        depth: int = 3,
        output_fmt: str = "markdown",
        on_progress: Callable[[str], None] = _NOOP,
    ) -> dict:
        """Execute a Cowork task. Returns {"output": str, "steps": list, "usage": dict}"""
        task_type = task_type.lower()
        if task_type not in COWORK_TASKS:
            return {"output": f"[ERROR] Unknown task type: {task_type}. Use --cowork-list.", "steps": []}

        task = COWORK_TASKS[task_type]
        sys_prompt = SYSTEM_PROMPTS.get(task_type, "You are an expert assistant.")

        # Attach files
        file_content = ""
        for fp in files or []:
            try:
                text = Path(fp).read_text()[:12000]
                file_content += f"\n\n--- File: {fp} ---\n{text}\n"
            except Exception as e:
                file_content += f"\n[Could not read {fp}: {e}]"

        full_prompt = build_task_prompt(prompt, file_content, depth, output_fmt)

        on_progress(f"\n{task['icon']} \033[94m{task['name']}\033[0m")
        on_progress(f"  Depth: {depth}/5  |  Format: {output_fmt}\n")
        on_progress(f"\033[90m{'─'*50}\033[0m\n")

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": sys_prompt,
            "messages": [{"role": "user", "content": full_prompt}],
        }

        data = self._post(payload)
        if "error" in data:
            return {"output": f"[ERROR] {data['error']}", "steps": [], "usage": {}}

        output = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})

        return {
            "output": output,
            "task_type": task_type,
            "task_name": task["name"],
            "steps": [],
            "usage": usage,
        }

    # ── Multi-turn iterative cowork ────────────────────────────────────────

    def iterate(
        self,
        task_type: str,
        initial_prompt: str,
        follow_ups: list[str],
        files: list[str] | None = None,
    ) -> list[str]:
        """
        Multi-turn cowork session: initial task + follow-up refinements.
        Returns list of responses (one per turn).
        """
        sys_prompt = SYSTEM_PROMPTS.get(task_type, "You are an expert assistant.")
        messages = []
        responses = []

        # File content once
        file_content = ""
        for fp in files or []:
            try:
                file_content += f"\n\n--- {fp} ---\n{Path(fp).read_text()[:6000]}"
            except Exception:
                pass

        first = initial_prompt
        if file_content:
            first += f"\n\nATTACHED:{file_content}"

        for _i, user_msg in enumerate([first] + follow_ups):
            messages.append({"role": "user", "content": user_msg})
            payload = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": sys_prompt,
                "messages": messages,
            }
            data = self._post(payload)
            if "error" in data:
                responses.append(f"[ERROR] {data['error']}")
                break
            resp = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            responses.append(resp)
            messages.append({"role": "assistant", "content": resp})

        return responses
