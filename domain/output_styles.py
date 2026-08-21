"""domain/output_styles.py — Output Styles domain layer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Pure data + pure functions for output styles. No I/O, no print(), no
`import anthropic`, no `urllib.request` here — those belong to infrastructure/.
"""

import os
import re
from pathlib import Path
from typing import Optional

PROJECT_STYLES_DIR = Path(".claude/output-styles")
USER_STYLES_DIR = Path(os.path.expanduser("~/.claude/output-styles"))

BUILTIN_STYLES = {
    "default": {
        "description": "Standard Claude Code behaviour — concise, tool-using, no extra narration.",
        "prompt": "",
    },
    "explanatory": {
        "description": "Adds educational insights about implementation choices and codebase patterns.",
        "prompt": (
            "After completing each significant step, briefly explain the *why* behind "
            "the implementation choice you made — patterns used, trade-offs considered, "
            "and anything notable about the surrounding codebase. Keep these insights to "
            "1-3 sentences; do not let them overwhelm the actual work."
        ),
    },
    "concise": {
        "description": "Minimal narration. Output is mostly tool calls and final results.",
        "prompt": (
            "Be extremely concise. Skip preamble and restating the task. Narrate only "
            "what is necessary to track progress. Prefer terse confirmations over "
            "explanations unless the user asks why."
        ),
    },
    "learning": {
        "description": "Interactive mode that pauses at decision points for the user to write a small piece of code themselves.",
        "prompt": (
            "Work collaboratively rather than autonomously. At natural decision points "
            "(e.g. before writing a non-trivial function or fixing a bug), pause and ask "
            "the user to write a small (5-10 line) piece of the implementation themselves, "
            "giving them just enough context to do so, then continue from what they wrote. "
            "Use this as a teaching opportunity — explain the concept briefly before they write."
        ),
    },
}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_style_file(path: Path) -> Optional[dict]:
    try:
        text = path.read_text()
    except Exception:
        return None
    m = FRONTMATTER_RE.match(text)
    meta, body = {}, text
    if m:
        front, body = m.group(1), m.group(2)
        for line in front.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"').strip("'")
    name = meta.get("name", path.stem)
    return {
        "name": name,
        "description": meta.get("description", ""),
        "keep_coding_instructions": meta.get("keep-coding-instructions", "false").lower() == "true",
        "prompt": body.strip(),
        "source": str(path),
    }


def list_styles(plugin_styles: Optional[list] = None) -> list:
    out = [{"name": n, "description": s["description"], "builtin": True}
           for n, s in BUILTIN_STYLES.items()]
    custom = plugin_styles or []
    for s in custom:
        out.append({
            "name": s["name"], "description": s["description"], "builtin": False,
            "plugin": s.get("plugin"),
        })
    return out


def get_style(name: str, custom_styles: Optional[dict] = None) -> Optional[dict]:
    if name in BUILTIN_STYLES:
        return {"name": name, **BUILTIN_STYLES[name], "keep_coding_instructions": True}
    return (custom_styles or {}).get(name)


def system_prompt_fragment(name: str, custom_styles: Optional[dict] = None) -> str:
    style = get_style(name, custom_styles)
    if not style or not style.get("prompt"):
        return ""
    return f"[Output style: {name}]\n{style['prompt']}"
