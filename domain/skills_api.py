"""domain/skills_api.py — Agent Skills API domain layer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Pure data + pure functions for the Skills API (Messages API container.skills).
No I/O, no print(), no `import anthropic` — those belong to infrastructure/.
"""

from dataclasses import dataclass

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
CODE_EXECUTION_BETA = "code-execution-2025-08-25"
SKILLS_BETA = "skills-2025-10-02"
FILES_API_BETA = "files-api-2025-04-14"

PREBUILT_SKILLS = {
    "pptx": {"skill_id": "pptx", "description": "Create and edit PowerPoint presentations"},
    "xlsx": {"skill_id": "xlsx", "description": "Create and edit Excel spreadsheets"},
    "docx": {"skill_id": "docx", "description": "Create and edit Word documents"},
    "pdf": {"skill_id": "pdf", "description": "Create, fill, and edit PDF files"},
}


@dataclass
class SkillRef:
    type: str = "anthropic"
    skill_id: str = ""
    version: str | None = None

    def to_dict(self) -> dict:
        d = {"type": self.type, "skill_id": self.skill_id}
        if self.version:
            d["version"] = self.version
        return d

    @classmethod
    def prebuilt(cls, name: str) -> SkillRef:
        info = PREBUILT_SKILLS.get(name)
        if not info:
            raise ValueError(f"Unknown pre-built skill {name!r}. Known: {', '.join(PREBUILT_SKILLS)}")
        return cls(skill_id=info["skill_id"], type="anthropic")


def build_container_skills(skills: list) -> dict:
    if len(skills) > 8:
        raise ValueError(f"Skills API allows at most 8 skills per request; got {len(skills)}.")
    refs = [s.to_dict() if isinstance(s, SkillRef) else s for s in skills]
    return {"skills": refs}


def build_user_content(text: str, file_ids: list | None = None) -> list:
    content = [{"type": "text", "text": text}]
    for fid in file_ids or []:
        content.append({"type": "container_upload", "file_id": fid})
    return content


def extract_output_file_ids(data: dict) -> list:
    file_ids = []
    for block in data.get("content", []) or []:
        if block.get("type") not in ("code_execution_tool_result", "bash_code_execution_tool_result"):
            continue
        result = block.get("content")
        if isinstance(result, dict):
            items = result.get("content", [])
        elif isinstance(result, list):
            items = result
        else:
            items = []
        for item in items:
            fid = item.get("file_id") if isinstance(item, dict) else None
            if fid:
                file_ids.append(fid)
    return file_ids


def list_prebuilt_skills() -> list:
    return [
        {"skill_id": info["skill_id"], "type": "anthropic", "description": info["description"]}
        for info in PREBUILT_SKILLS.values()
    ]
