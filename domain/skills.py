"""Pure Agent Skills manifest parsing and validation.

No network, disk writes, or presentation logic lives here.  This supports
both local Claude Code-style SKILL.md packages and custom Skills uploaded to
the Anthropic Skills Management API.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class SkillManifest:
    name: str
    description: str
    allowed_tools: tuple[str, ...] = field(default_factory=tuple)
    body: str = ""


@dataclass(frozen=True)
class SkillValidationResult:
    valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values, body


def parse_skill_md(text: str) -> SkillManifest:
    frontmatter, body = _parse_frontmatter(text)
    raw_tools = frontmatter.get("allowed-tools", "")
    allowed_tools = tuple(item.strip() for item in raw_tools.split(",") if item.strip())
    return SkillManifest(
        name=frontmatter.get("name", ""),
        description=frontmatter.get("description", ""),
        allowed_tools=allowed_tools,
        body=body,
    )


def validate_skill_manifest(manifest: SkillManifest) -> SkillValidationResult:
    errors: list[str] = []
    if not manifest.name:
        errors.append("SKILL.md frontmatter requires name")
    elif len(manifest.name) > 64:
        errors.append("skill name must be at most 64 characters")
    elif not _NAME_RE.fullmatch(manifest.name):
        errors.append("skill name must use lowercase letters, digits, and single hyphens")
    if not manifest.description:
        errors.append("SKILL.md frontmatter requires description")
    elif len(manifest.description) > 1024:
        errors.append("skill description must be at most 1024 characters")
    if len(set(manifest.allowed_tools)) != len(manifest.allowed_tools):
        errors.append("allowed-tools must not contain duplicates")
    return SkillValidationResult(valid=not errors, errors=tuple(errors))


def validate_skill_files(paths: Iterable[str]) -> SkillValidationResult:
    """Validate package layout without reading files.

    The Anthropic API requires all uploaded files to share one top-level
    directory and requires SKILL.md at that directory root.
    """
    normalized = [p.replace("\\", "/").strip("/") for p in paths]
    errors: list[str] = []
    if not normalized:
        return SkillValidationResult(False, ("skill package has no files",))
    if any(".." in p.split("/") for p in normalized):
        errors.append("skill package paths must not contain '..'")
    roots = {p.split("/", 1)[0] for p in normalized if p}
    if len(roots) != 1:
        errors.append("all skill files must share one top-level directory")
    root = next(iter(roots), "")
    if f"{root}/SKILL.md" not in normalized:
        errors.append("skill package must include top-level SKILL.md")
    return SkillValidationResult(valid=not errors, errors=tuple(errors))
