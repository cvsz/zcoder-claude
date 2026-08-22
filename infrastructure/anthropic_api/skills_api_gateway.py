"""infrastructure/anthropic_api/skills_api_gateway.py — Skills API HTTP transport
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Real HTTP calls to api.anthropic.com for the Skills API (Messages API with
container.skills). No print().

GA note (2026-08-22): the Agent Skills API went GA on Aug 19–20, 2026 —
Messages container skill loading no longer requires the
`skills-2025-10-02` beta header, and file-reference/container_upload
calls no longer require the `files-api-2025-04-14` beta header. Neither
is sent anymore (see domain/skills_api.py's module docstring). The only
beta still attached is CODE_EXECUTION_BETA for the code-execution tool,
which has not gone GA.
"""

import json
import urllib.request

from core.exceptions import ZCoderError
from domain.skills_api import (
    CODE_EXECUTION_BETA,
    MESSAGES_ENDPOINT,
    SkillRef,
    build_container_skills,
)
from infrastructure.anthropic_api.http_client import CircuitBreaker, retry, urlopen_json

_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


class SkillsApiGateway:
    def __init__(self, api_key: str, model: str = "claude-sonnet-5", max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict, betas: list) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        if betas:
            # GA Skills API calls need no skills/files beta; today this is
            # CODE_EXECUTION_BETA only. Never send an empty header value.
            headers["anthropic-beta"] = ",".join(betas)
        req = urllib.request.Request(
            MESSAGES_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict, betas: list) -> dict:
        try:
            return self._call(payload, betas)
        except ZCoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def call_with_skills(self, prompt: str, skills: list, system: str | None = None) -> dict:
        refs = [s if isinstance(s, SkillRef) else SkillRef.prebuilt(s) for s in skills]
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [{"type": "code_execution_20250825", "name": "code_execution"}],
            "container": build_container_skills(refs),
        }
        if system:
            payload["system"] = system
        return self._post(payload, betas=[CODE_EXECUTION_BETA])

    def call_with_skills_turn(
        self,
        messages: list,
        skills: list,
        container_id: str | None = None,
        has_file_uploads: bool = False,
        system: str | None = None,
    ) -> dict:
        """has_file_uploads is accepted for call-shape compatibility but no
        longer toggles any beta header — Files API went GA (2026-08-22), so
        container_upload references ride the same GA endpoint."""
        refs = [s if isinstance(s, SkillRef) else SkillRef.prebuilt(s) for s in skills]
        container = build_container_skills(refs)
        if container_id:
            container["id"] = container_id
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
            "tools": [{"type": "code_execution_20250825", "name": "code_execution"}],
            "container": container,
        }
        if system:
            payload["system"] = system
        return self._post(payload, betas=[CODE_EXECUTION_BETA])
