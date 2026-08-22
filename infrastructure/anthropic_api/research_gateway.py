"""infrastructure/anthropic_api/research_gateway.py — Deep Research HTTP transport
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Real HTTP calls to api.anthropic.com + arbitrary URL fetches for research.
No print().
"""

import json
import urllib.error
import urllib.request

from infrastructure.anthropic_api.http_client import raise_for_http_error, retry, urlopen_json

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"


class DeepResearchGateway:
    def __init__(self, api_key: str, model: str = "claude-sonnet-5"):
        self.api_key = api_key
        self.model = model

    def _call(self, system: str, user: str, max_tokens: int = 2048) -> str:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        req = urllib.request.Request(
            MESSAGES_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        data = urlopen_json(req, timeout=180)
        return data["content"][0]["text"]

    @retry(max_attempts=2, base_delay=1.0, max_delay=5.0)
    def fetch_url(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "ai-coder-research/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")[:4000]
        except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
            raise_for_http_error(e)
