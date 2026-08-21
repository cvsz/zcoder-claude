"""domain/workflow.py — Workflow engine domain layer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Pure data + pure functions for declarative multi-step pipelines. No I/O,
no print(), no `import anthropic` — those belong to infrastructure/.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WorkflowStep:
    step_id: str
    instruction: str
    depends_on: list[str] = field(default_factory=list)
    model: str | None = None
    max_tokens: int = 2048


@dataclass
class Workflow:
    name: str
    steps: list[WorkflowStep]
    model: str = "claude-sonnet-5"


@dataclass
class StepResult:
    step_id: str
    output: str
    latency_ms: int
    status: str = "ok"
    error: str | None = None


@dataclass
class WorkflowRun:
    workflow: str
    results: list[StepResult]
    variables: dict[str, str]
    elapsed_s: float
    ts: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_markdown(self) -> str:
        lines = [f"# Workflow Run: {self.workflow}", f"_Completed: {self.ts_}\\n"]
        for r in self.results:
            icon = "✓" if r.status == "ok" else "✗"
            lines.append(f"## {icon} {r.step_id}  ({r.latency_ms}ms)\\n{r.output}\\n")
        return "\\n".join(lines)


def load_workflow(path: str, has_yaml: bool = True) -> dict:
    from pathlib import Path

    text = Path(path).read_text()
    if path.endswith((".yml", ".yaml")):
        if not has_yaml:
            raise RuntimeError("PyYAML not installed — run: pip install pyyaml")
        import yaml

        return yaml.safe_load(text)
    import json

    return json.loads(text)


def parse_workflow(d: dict) -> Workflow:
    steps = [
        WorkflowStep(
            step_id=s["id"],
            instruction=s["instruction"],
            depends_on=s.get("depends_on", []),
            model=s.get("model"),
            max_tokens=s.get("max_tokens", 2048),
        )
        for s in d.get("steps", [])
    ]
    return Workflow(
        name=d.get("name", "Untitled"),
        steps=steps,
        model=d.get("model", "claude-sonnet-5"),
    )


def fill_template(template: str, variables: dict[str, str]) -> str:
    def replace(m):
        key = m.group(1).strip()
        return variables.get(key, f"{{{{ {key} }}}}")

    return re.sub(r"\\{\\{\\s*(\\w+)\\s*\\}\\}", replace, template)
