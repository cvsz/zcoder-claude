"""infrastructure/anthropic_api/skills_api_gateway.py — Skills API HTTP transport
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Real HTTP calls to api.anthropic.com for the Skills API (Messages API with
container.skills). No print().
"""

import json
import urllib.request

from domain.skills_api import (
    CODE_EXECUTION_BETA,
    FILES_API_BETA,
    MESSAGES_ENDPOINT,
    SKILLS_BETA,
    SkillRef,
    build_container_skills,
)
from exceptions import ZCoderError
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
            "anthropic-beta": ",".join(betas),
        }
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
        return self._post(payload, betas=[CODE_EXECUTION_BETA, SKILLS_BETA])

    def call_with_skills_turn(
        self,
        messages: list,
        skills: list,
        container_id: str | None = None,
        has_file_uploads: bool = False,
        system: str | None = None,
    ) -> dict:
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
        betas = [CODE_EXECUTION_BETA, SKILLS_BETA]
        if has_file_uploads:
            betas.append(FILES_API_BETA)
        return self._post(payload, betas=betas)
