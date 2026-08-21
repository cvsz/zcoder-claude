"""infrastructure/anthropic_api/advisor_gateway.py — Advisor tool HTTP transport
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Real HTTP calls to api.anthropic.com for the advisor tool. No print().
"""

import json
import urllib.request
from typing import Optional

from domain.advisor import ADVISOR_TOOL_BETA, ADVISOR_TOOL_TYPE, strip_advisor_blocks
from exceptions import AICoderError
from resilience import CircuitBreaker, retry, urlopen_json

ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


class AdvisorGateway:
    def __init__(self, api_key: str, executor_model: str = "claude-sonnet-5",
                 max_tokens: int = 4096):
        self.api_key = api_key
        self.executor_model = executor_model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict, beta: str) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": beta,
        }
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(payload).encode(),
            headers=headers, method="POST",
        )
        return urlopen_json(req, timeout=180)

    def _post(self, payload: dict, beta: str) -> dict:
        try:
            return self._call(payload, beta)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def run(self, prompt: str, advisor_tool: dict,
            extra_tools: Optional[list] = None,
            system: Optional[str] = None,
            max_advisor_calls: int = 10) -> tuple:
        tools = [advisor_tool] + (extra_tools or [])
        messages = [{"role": "user", "content": prompt}]
        advisor_calls = 0

        while True:
            payload = {
                "model": self.executor_model,
                "max_tokens": self.max_tokens,
                "messages": messages,
                "tools": tools,
            }
            if system:
                payload["system"] = system

            data = self._post(payload, beta=ADVISOR_TOOL_BETA)
            if "error" in data:
                return data, messages, advisor_calls

            content = data.get("content", [])
            messages.append({"role": "assistant", "content": content})

            for block in content:
                if block.get("type") == "server_tool_use" and block.get("name") == "advisor":
                    advisor_calls += 1

            if data.get("stop_reason") == "pause_turn":
                if advisor_calls >= max_advisor_calls:
                    tools = [t for t in tools if t.get("type") != ADVISOR_TOOL_TYPE]
                    messages = strip_advisor_blocks(messages)
                continue

            if data.get("stop_reason") == "tool_use":
                pending = [b for b in content if b.get("type") == "tool_use"]
                if pending:
                    return {"error": "[TOOL_USE] Executor called client tool(s) — "
                            "send tool_result blocks and resend to continue"}, messages, advisor_calls
                continue

            if data.get("stop_reason") == "end_turn":
                text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
                return {"text": text}, messages, advisor_calls

            return {"error": f"[UNEXPECTED stop_reason={data.get('stop_reason')}]"}, messages, advisor_calls
