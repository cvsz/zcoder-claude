"""Anthropic Skills Management API transport adapter.

Wraps the official SDK beta.skills and beta.skills.versions surfaces.  This
module contains network I/O only; local SKILL.md parsing/validation belongs in
domain.skills.
"""

# mypy: ignore-errors

from collections.abc import Iterable
from pathlib import Path

SKILLS_BETA = "skills-2025-10-02"


class SkillsManagementGateway:
    def __init__(self, api_key: str):
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)

    @staticmethod
    def _open_files(paths: Iterable[str]):
        handles = []
        try:
            for path in paths:
                handles.append(open(Path(path), "rb"))
            return handles
        except Exception:
            for handle in handles:
                handle.close()
            raise

    def create_skill(self, file_paths: Iterable[str], display_title: str | None = None):
        handles = self._open_files(file_paths)
        try:
            kwargs = {"files": handles, "betas": [SKILLS_BETA]}
            if display_title is not None:
                kwargs["display_title"] = display_title
            return self.client.beta.skills.create(**kwargs)
        finally:
            for handle in handles:
                handle.close()

    def list_skills(self, *, limit: int = 20, page: str | None = None, source: str | None = None):
        kwargs = {"limit": limit, "betas": [SKILLS_BETA]}
        if page is not None:
            kwargs["page"] = page
        if source is not None:
            kwargs["source"] = source
        return self.client.beta.skills.list(**kwargs)

    def get_skill(self, skill_id: str):
        return self.client.beta.skills.retrieve(skill_id, betas=[SKILLS_BETA])

    def delete_skill(self, skill_id: str):
        return self.client.beta.skills.delete(skill_id, betas=[SKILLS_BETA])

    def create_version(self, skill_id: str, file_paths: Iterable[str]):
        handles = self._open_files(file_paths)
        try:
            return self.client.beta.skills.versions.create(skill_id, files=handles, betas=[SKILLS_BETA])
        finally:
            for handle in handles:
                handle.close()

    def list_versions(self, skill_id: str, *, limit: int = 20, page: str | None = None):
        kwargs = {"limit": limit, "betas": [SKILLS_BETA]}
        if page is not None:
            kwargs["page"] = page
        return self.client.beta.skills.versions.list(skill_id, **kwargs)

    def get_version(self, skill_id: str, version: str):
        return self.client.beta.skills.versions.retrieve(version, skill_id=skill_id, betas=[SKILLS_BETA])

    def download_version(self, skill_id: str, version: str):
        return self.client.beta.skills.versions.download(version, skill_id=skill_id, betas=[SKILLS_BETA])

    def delete_version(self, skill_id: str, version: str):
        return self.client.beta.skills.versions.delete(version, skill_id=skill_id, betas=[SKILLS_BETA])
