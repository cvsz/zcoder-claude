"""application/skills_api_service.py — use-case layer for Skills API
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Orchestrates domain/skills_api.py + infrastructure/anthropic_api/
skills_api_gateway.py — no print() of its own.
"""

from typing import Optional

from domain.skills_api import (
    list_prebuilt_skills,
)
from infrastructure.anthropic_api.skills_api_gateway import SkillsApiGateway


def call_with_skills(gateway: SkillsApiGateway, prompt: str, skills: list,
                     system: Optional[str] = None) -> dict:
    return gateway.call_with_skills(prompt, skills, system)


def call_with_skills_turn(gateway: SkillsApiGateway, messages: list, skills: list,
                          container_id: Optional[str] = None,
                          has_file_uploads: bool = False,
                          system: Optional[str] = None) -> dict:
    return gateway.call_with_skills_turn(messages, skills, container_id, has_file_uploads, system)


def list_skills() -> list:
    return list_prebuilt_skills()
