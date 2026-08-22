"""infrastructure/anthropic_api/workflow_gateway.py — Workflow HTTP transport
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Real HTTP calls to api.anthropic.com for workflow step execution.
No print().
"""

import json
import time
import urllib.request

from infrastructure.anthropic_api.http_client import urlopen_json


class WorkflowGateway:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint = "https://api.anthropic.com/v1/messages"

    def run_step(self, model: str, instruction: str, max_tokens: int = 2048) -> tuple:
        t0 = time.time()
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": instruction}],
        }
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        data = urlopen_json(req, timeout=180)
        ms = int((time.time() - t0) * 1000)
        output = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return output, ms
