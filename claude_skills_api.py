"""
claude_skills_api.py — Agent Skills API (platform, skill_id-based) (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

This module used to contain the full implementation (292 lines: SkillRef,
PREBUILT_SKILLS, SkillsApiClient, build_container_skills, build_user_content,
extract_output_file_ids, list_skills, cmd_skills_list, cmd_skills_info). It
has been split into:

  domain/skills_api.py                                  — SkillRef, PREBUILT_SKILLS,
                                                           build_container_skills(),
                                                           build_user_content(),
                                                           extract_output_file_ids(),
                                                           list_prebuilt_skills()
  infrastructure/anthropic_api/skills_api_gateway.py    — SkillsApiGateway
  application/skills_api_service.py                     — use-case layer
  interfaces/cli/commands/skills_api_commands.py        — print(), cmd_skills_list,
                                                           cmd_skills_info

This file re-exports every name the old module used to export, so
existing imports keep working unmodified.
"""

from domain.skills_api import (
    MESSAGES_ENDPOINT, CODE_EXECUTION_BETA, SKILLS_BETA, FILES_API_BETA,
    PREBUILT_SKILLS,
    SkillRef, build_container_skills,
    build_user_content, extract_output_file_ids, list_prebuilt_skills,
)
from infrastructure.anthropic_api.skills_api_gateway import SkillsApiGateway
from interfaces.cli.commands.skills_api_commands import (
    cmd_skills_list, cmd_skills_info,
)

__all__ = [
    "MESSAGES_ENDPOINT", "CODE_EXECUTION_BETA", "SKILLS_BETA", "FILES_API_BETA",
    "PREBUILT_SKILLS",
    "SkillRef", "build_container_skills",
    "build_user_content", "extract_output_file_ids",
    "list_skills",
    "SkillsApiGateway",
    "SkillsApiClient",
    "cmd_skills_list", "cmd_skills_info",
]

list_skills = list_prebuilt_skills
SkillsApiClient = SkillsApiGateway
