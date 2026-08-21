"""domain/research.py — Deep Research domain layer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Pure data + pure functions for deep research planning, gathering, and
synthesis. No I/O, no print(), no `import anthropic` — those belong to
infrastructure/.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime

SYS_PLAN = "You are a research planning assistant. Output only valid JSON."
SYS_ANAL = "You are a careful research analyst. Be precise. Flag uncertainty."
SYS_SYNTH = "You are a research synthesis expert. Connect ideas, note tensions."


@dataclass
class SubQ:
    question: str
    findings: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    answered: bool = False


@dataclass
class Report:
    topic: str
    sub_questions: list[SubQ]
    synthesis: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_markdown(self) -> str:
        lines = [
            f"# Research Report: {self.topic}",
            f"_Generated: {self.created_}\\n",
            f"## Summary\\n{self.synthesis}\\n",
            "## Sub-Questions Explored",
        ]
        for i, sq in enumerate(self.sub_questions, 1):
            lines.append(f"\\n### {i}. {sq.question}")
            for f in sq.findings:
                lines.append(f"- {f}")
            if sq.sources:
                lines.append("Sources: " + ", ".join(sq.sources))
        return "\\n".join(lines)


def clean_json_response(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\\n".join(cleaned.split("\\n")[1:-1])
    return cleaned


def parse_subquestions(raw: str, depth: int) -> list[str]:
    cleaned = clean_json_response(raw)
    try:
        qs = json.loads(cleaned)
    except json.JSONDecodeError:
        qs = [line.lstrip("-· ").strip() for line in raw.splitlines() if line.strip()][:depth]
    return qs[:depth]


def parse_findings(raw: str) -> list[str]:
    return [line.lstrip("-· ").strip() for line in raw.splitlines() if line.strip()]
