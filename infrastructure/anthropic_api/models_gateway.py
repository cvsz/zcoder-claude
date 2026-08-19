"""
infrastructure/anthropic_api/models_gateway.py — Live Anthropic API adapters for models
AI Model Coder CLI v1.41.0 (Clean Architecture refactor)

Infrastructure layer: everything here makes real HTTP calls to
api.anthropic.com. Extracted 2026-08-14 from claude_models.py, which
previously mixed this transport code with domain data (now in
domain/models/catalog.py) and CLI presentation (now in
interfaces/cli/commands/model_commands.py) in one file.

Depends on domain/models/catalog.py for model IDs where relevant, but
domain/models/catalog.py does NOT depend back on this module — the
Dependency Rule points inward only.
"""

import json
import urllib.request
import urllib.error
from typing import Optional

from exceptions import AICoderError
from resilience import CircuitBreaker, retry, urlopen_json

MODELS_ENDPOINT   = "https://api.anthropic.com/v1/models"
MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

# Computer Use — moved here 2026-08-14 (found via pyflakes during the
# Clean Architecture refactor): these landed in the CLI commands file by
# line-adjacency during the original mechanical extraction even though
# only ComputerUseCoder (this file) uses them, leaving both this file and
# the CLI file broken (NameError at call time — nothing caught it because
# neither had test coverage that exercised these code paths).
COMPUTER_USE_TOOLS = [
    {
        "type":               "computer_20250124",
        "name":               "computer",
        "display_width_px":   1024,
        "display_height_px":  768,
        "display_number":     1,
    },
    {
        "type": "bash_20250124",
        "name": "bash",
    },
    {
        "type": "text_editor_20250124",
        "name": "str_replace_based_edit_tool",
    },
]
COMPUTER_USE_BETA = "computer-use-2025-01-24"

# Adaptive + Interleaved Thinking — same relocation, same reason (only
# AdaptiveThinkingCoder, this file, uses it).
EFFORT_BUDGETS = {"low": 2000, "medium": 8000, "high": 16000, "max": 32000}


# ── Models API ─────────────────────────────────────────────────────────────

class ModelsAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, req: "urllib.request.Request") -> dict:
        return urlopen_json(req, timeout=30)

    def _get(self, url: str) -> dict:
        headers = {
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            return self._call(req)
        except AICoderError as e:
            raise RuntimeError(f"Models API error: {e.message}") from e

    def list_models(self) -> list:
        data = self._get(MODELS_ENDPOINT)
        return data.get("data", [])

    def get_model(self, model_id: str) -> dict:
        return self._get(f"{MODELS_ENDPOINT}/{model_id}")


class ComputerUseCoder:
    """Claude with computer use tools."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5",
                 max_tokens: int = 4096,
                 width: int = 1024, height: int = 768):
        self.api_key    = api_key
        self.model      = model
        self.max_tokens = max_tokens
        self.width      = width
        self.height     = height

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict) -> dict:
        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta":    COMPUTER_USE_BETA,
        }
        req = urllib.request.Request(
            MESSAGES_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=120)

    def _post(self, payload: dict) -> dict:
        try:
            return self._call(payload)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def run_task(self, task: str, system: str = None) -> dict:
        """Submit a computer use task. Returns tool calls for execution."""
        tools = [dict(t) for t in COMPUTER_USE_TOOLS]
        tools[0]["display_width_px"]  = self.width
        tools[0]["display_height_px"] = self.height

        system_prompt = system or (
            "You have access to a computer with a display. "
            "Use the computer and bash tools to complete the task. "
            "Describe each action you take."
        )

        payload = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "system":     system_prompt,
            "tools":      tools,
            "messages":   [{"role": "user", "content": task}],
        }
        data = self._post(payload)
        if "error" in data:
            return {"text": f"[ERROR] {data['error']}", "tool_calls": []}

        text       = ""
        tool_calls = []
        for block in data.get("content", []):
            bt = block.get("type", "")
            if bt == "text":
                text += block.get("text", "")
            elif bt == "tool_use":
                tool_calls.append({
                    "name":  block.get("name"),
                    "input": block.get("input", {}),
                    "id":    block.get("id"),
                })

        return {"text": text, "tool_calls": tool_calls, "stop_reason": data.get("stop_reason")}


class AdaptiveThinkingCoder:
    """Extended thinking with adaptive / interleaved modes."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5",
                 max_tokens: int = 8000):
        self.api_key    = api_key
        self.model      = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict, betas: list[str] = None) -> dict:
        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
        }
        if betas:
            headers["anthropic-beta"] = ",".join(betas)
        req = urllib.request.Request(
            MESSAGES_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict, betas: list[str] = None) -> dict:
        try:
            return self._call(payload, betas)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def adaptive(self, prompt: str, budget: int = 8000,
                 effort: str = None, system: str = None) -> str:
        """Adaptive thinking — model decides depth."""
        if effort:
            budget = EFFORT_BUDGETS.get(effort, budget)
        payload = {
            "model":      self.model,
            "max_tokens": max(self.max_tokens, budget + 1000),
            "thinking":   {"type": "adaptive", "budget_tokens": budget},
            "messages":   [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        data  = self._post(payload)
        if "error" in data:
            return f"[ERROR] {data['error']}"
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    def interleaved(self, prompt: str, tools: list[dict],
                    budget: int = 8000, system: str = None) -> str:
        """Interleaved thinking — think between tool calls."""
        payload = {
            "model":      self.model,
            "max_tokens": max(self.max_tokens, budget + 1000),
            "thinking":   {"type": "enabled", "budget_tokens": budget},
            "tools":      tools,
            "messages":   [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        data  = self._post(payload, betas=["interleaved-thinking-2025-05-14"])
        if "error" in data:
            return f"[ERROR] {data['error']}"
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
