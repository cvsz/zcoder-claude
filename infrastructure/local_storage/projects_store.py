"""
infrastructure/local_storage/projects_store.py — Feature Projects
subsystem local-disk persistence
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

ProjectManager and its manifest helpers, extracted 2026-08-22 from
projects.py. Everything here is local-disk I/O under ~/.zcoder/
projects/ — same bucket as the other *_store.py modules (see
infrastructure/local_storage/devtools_store.py's docstring for the
precedent). The class is kept intact rather than split method-by-method,
matching the CodeSession/PptxSession/ExcelSession precedent:
generate_plan()/run_task()/run_all_pending() call a caller-supplied
`coder` object (duck-typed generate()), while CRUD methods are pure
manifest manipulation over disk.

The only behavioral change from projects.py: run_all_pending()'s inline
print(f"  → Running: {t['title']}") moved to an on_progress(str)
callback per the established HooksEngine/batch_gateway convention —
cmd_project_run wires on_progress=print, reproducing the original output.
"""

import json
import os
import shutil
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from domain.projects import ProjectStatus, Task

PROJECTS_DIR = os.path.expanduser("~/.zcoder/projects")


# ── helpers ────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _projects_dir() -> Path:
    p = Path(PROJECTS_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _project_path(project_id: str) -> Path:
    return _projects_dir() / project_id


def _manifest_path(project_id: str) -> Path:
    return _project_path(project_id) / "project.json"


def _load_manifest(project_id: str) -> dict:
    mp = _manifest_path(project_id)
    if not mp.exists():
        raise FileNotFoundError(f"Project '{project_id}' not found.")
    with open(mp) as f:
        return json.load(f)


def _save_manifest(project_id: str, data: dict):
    mp = _manifest_path(project_id)
    mp.parent.mkdir(parents=True, exist_ok=True)
    with open(mp, "w") as f:
        json.dump(data, f, indent=2)


_NOOP: Callable[..., None] = lambda *a, **k: None  # noqa: E731


# ── ProjectManager ─────────────────────────────────────────────────────────


class ProjectManager:
    """Create, manage, and run Feature Projects."""

    # ── CRUD ───────────────────────────────────────────────────────────────

    def create_project(self, name: str, description: str = "", template: str = "blank") -> dict:
        """Create a new project and return its manifest."""
        pid = str(uuid.uuid4())[:12]
        templates = self._builtin_templates()
        tpl = templates.get(template, templates["blank"])

        manifest = {
            "id": pid,
            "name": name,
            "description": description,
            "template": template,
            "status": ProjectStatus.PLANNING,
            "created_at": _now(),
            "updated_at": _now(),
            "tasks": [t.to_dict() for t in tpl["tasks"]],
            "context": tpl.get("context", ""),
            "files": [],
            "tags": [],
            "agents_used": [],
            "run_log": [],
        }
        _save_manifest(pid, manifest)

        # Create project workspace directory
        ws = _project_path(pid) / "workspace"
        ws.mkdir(parents=True, exist_ok=True)

        return manifest

    def list_projects(self) -> list:
        projects = []
        base = _projects_dir()
        for d in sorted(base.iterdir()):
            mp = d / "project.json"
            if mp.exists():
                try:
                    with open(mp) as f:
                        m = json.load(f)
                    projects.append(
                        {
                            "id": m["id"],
                            "name": m["name"],
                            "status": m["status"],
                            "tasks_total": len(m.get("tasks", [])),
                            "tasks_done": sum(1 for t in m.get("tasks", []) if t.get("status") == "done"),
                            "created_at": m.get("created_at", ""),
                            "updated_at": m.get("updated_at", ""),
                        }
                    )
                except Exception:
                    pass
        return projects

    def get_project(self, project_id: str) -> dict:
        return _load_manifest(project_id)

    def update_project(self, project_id: str, **kwargs) -> dict:
        m = _load_manifest(project_id)
        for k, v in kwargs.items():
            if k in m:
                m[k] = v
        m["updated_at"] = _now()
        _save_manifest(project_id, m)
        return m

    def delete_project(self, project_id: str) -> bool:
        pp = _project_path(project_id)
        if pp.exists():
            shutil.rmtree(pp)
            return True
        return False

    def archive_project(self, project_id: str) -> dict:
        return self.update_project(project_id, status=ProjectStatus.ARCHIVED)

    # ── Tasks ──────────────────────────────────────────────────────────────

    def add_task(
        self, project_id: str, title: str, description: str = "", agent: str = "", priority: str = "medium"
    ) -> dict:
        m = _load_manifest(project_id)
        task = Task(title, description, agent, priority)
        m["tasks"].append(task.to_dict())
        m["updated_at"] = _now()
        _save_manifest(project_id, m)
        return task.to_dict()

    def update_task(self, project_id: str, task_id: str, **kwargs) -> dict:
        m = _load_manifest(project_id)
        for t in m["tasks"]:
            if t["id"] == task_id:
                t.update(kwargs)
                t["updated_at"] = _now()
                break
        m["updated_at"] = _now()
        _save_manifest(project_id, m)
        return m

    def complete_task(self, project_id: str, task_id: str, result: str = "") -> dict:
        return self.update_task(project_id, task_id, status="done", result=result)

    # ── AI-powered actions ─────────────────────────────────────────────────

    def generate_plan(self, project_id: str, coder) -> str:
        """Use AI to generate a task plan for the project."""
        m = _load_manifest(project_id)
        prompt = (
            f"Project: {m['name']}\n"
            f"Description: {m['description']}\n"
            f"Template: {m['template']}\n\n"
            "Generate a detailed task plan with 5-10 concrete tasks. "
            "For each task include: title, description, suggested agent "
            "(code_generator/testing_agent/security_auditor/documentation_agent/"
            "optimizer/full_stack), and priority (low/medium/high/critical). "
            "Respond as a JSON array of task objects."
        )
        system = (
            "You are a senior software architect. Output ONLY a JSON array — "
            "no markdown fences, no prose. Each object must have keys: "
            "title, description, agent, priority."
        )
        result = coder.generate(prompt, system=system)

        # Parse and insert tasks
        try:
            # Strip possible markdown fences
            clean = result.strip()
            if clean.startswith("```"):
                clean = "\n".join(clean.split("\n")[1:])
            if clean.endswith("```"):
                clean = "\n".join(clean.split("\n")[:-1])
            tasks_data = json.loads(clean)
            m = _load_manifest(project_id)
            for td in tasks_data:
                task = Task(
                    title=td.get("title", "Task"),
                    description=td.get("description", ""),
                    agent=td.get("agent", ""),
                    priority=td.get("priority", "medium"),
                )
                m["tasks"].append(task.to_dict())
            m["status"] = ProjectStatus.ACTIVE
            m["updated_at"] = _now()
            _save_manifest(project_id, m)
            return f"Generated {len(tasks_data)} tasks for project '{m['name']}'."
        except json.JSONDecodeError:
            # AI returned prose plan — store as context
            m = _load_manifest(project_id)
            m["context"] = result
            m["updated_at"] = _now()
            _save_manifest(project_id, m)
            return result

    def run_task(self, project_id: str, task_id: str, coder) -> str:
        """Run a single task using its assigned agent."""
        m = _load_manifest(project_id)
        task_data = next((t for t in m["tasks"] if t["id"] == task_id), None)
        if not task_data:
            return f"[ERROR] Task {task_id} not found."

        self.update_task(project_id, task_id, status="in_progress")

        prompt = (
            f"Project: {m['name']}\nContext: {m.get('context', '')}\n\n"
            f"Task: {task_data['title']}\n{task_data['description']}"
        )
        system = (
            "You are an expert software developer. Complete the task thoroughly. "
            "Provide complete, runnable code or documentation as appropriate."
        )
        result = coder.generate(prompt, system=system)

        self.complete_task(project_id, task_id, result=result[:500])

        # Log to run_log
        mn = _load_manifest(project_id)
        mn["run_log"].append(
            {
                "timestamp": _now(),
                "task_id": task_id,
                "task": task_data["title"],
                "agent": task_data.get("agent", "ai"),
                "status": "done",
            }
        )
        _save_manifest(project_id, mn)

        # Save result to workspace
        ws = _project_path(project_id) / "workspace"
        ws.mkdir(exist_ok=True)
        out_file = ws / f"task_{task_id}.md"
        out_file.write_text(f"# {task_data['title']}\n\n{result}")

        return result

    def run_all_pending(self, project_id: str, coder, on_progress: Callable[[str], None] = _NOOP) -> dict:
        """Run all todo tasks in sequence."""
        m = _load_manifest(project_id)
        results = {}
        pending = [t for t in m["tasks"] if t.get("status") == "todo"]
        for t in pending:
            on_progress(f"  → Running: {t['title']}")
            results[t["id"]] = self.run_task(project_id, t["id"], coder)
        return results

    # ── Display ────────────────────────────────────────────────────────────

    def show_project(self, project_id: str) -> str:
        m = _load_manifest(project_id)
        tasks = m.get("tasks", [])
        done = sum(1 for t in tasks if t.get("status") == "done")
        pct = int(done / len(tasks) * 100) if tasks else 0
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)

        lines = [
            f"\n{'═'*60}",
            f"  PROJECT: {m['name']}",
            f"  ID:      {m['id']}",
            f"  Status:  {m['status']}",
            f"  Created: {m['created_at'][:10]}",
            f"  Progress: [{bar}] {pct}% ({done}/{len(tasks)} tasks)",
            f"{'═'*60}",
        ]
        if m.get("description"):
            lines.append(f"\n  {m['description']}")
        if tasks:
            lines.append("\n  TASKS:")
            icons = {"todo": "○", "in_progress": "◐", "done": "●", "blocked": "✗"}
            pri_colors = {"critical": "31", "high": "33", "medium": "36", "low": "37"}
            for t in tasks:
                icon = icons.get(t.get("status", "todo"), "○")
                color = pri_colors.get(t.get("priority", "medium"), "37")
                lines.append(
                    f"  {icon} [{t['id']}] \033[{color}m{t['title']}\033[0m"
                    f" ({t.get('priority','medium')}) — {t.get('status','todo')}"
                )
        return "\n".join(lines)

    # ── Templates ──────────────────────────────────────────────────────────

    def _builtin_templates(self) -> dict:
        def tasks(*specs):
            return [Task(title=s[0], description=s[1], agent=s[2], priority=s[3]) for s in specs]

        return {
            "blank": {"tasks": [], "context": ""},
            "web_app": {
                "context": "Full-stack web application project.",
                "tasks": tasks(
                    (
                        "Architecture Design",
                        "Define system architecture and tech stack.",
                        "code_generator",
                        "high",
                    ),
                    ("Backend API", "Implement REST API with authentication.", "code_generator", "high"),
                    ("Frontend UI", "Build responsive frontend interface.", "code_generator", "medium"),
                    ("Database Schema", "Design and implement database schema.", "code_generator", "high"),
                    ("Unit Tests", "Write comprehensive test suite.", "testing_agent", "medium"),
                    ("Security Audit", "Review for common vulnerabilities.", "security_auditor", "high"),
                    ("Documentation", "API docs and README.", "documentation_agent", "low"),
                ),
            },
            "api": {
                "context": "REST API project.",
                "tasks": tasks(
                    ("API Design", "Design endpoints and data models.", "code_generator", "high"),
                    ("Implementation", "Implement all endpoints.", "code_generator", "high"),
                    ("Auth Layer", "Add JWT/OAuth authentication.", "code_generator", "high"),
                    ("Tests", "Integration and unit tests.", "testing_agent", "medium"),
                    ("Security", "Rate limiting, input validation.", "security_auditor", "high"),
                    ("Docs", "OpenAPI/Swagger documentation.", "documentation_agent", "medium"),
                ),
            },
            "cli_tool": {
                "context": "Command-line tool project.",
                "tasks": tasks(
                    ("CLI Design", "Define commands and flags.", "code_generator", "high"),
                    ("Core Logic", "Implement main functionality.", "code_generator", "high"),
                    ("Config", "Config file and env var support.", "code_generator", "medium"),
                    ("Tests", "Unit tests for all commands.", "testing_agent", "medium"),
                    ("Packaging", "setup.py and distribution.", "code_generator", "low"),
                    ("README", "Usage guide with examples.", "documentation_agent", "medium"),
                ),
            },
            "data_pipeline": {
                "context": "Data pipeline / ETL project.",
                "tasks": tasks(
                    ("Schema Design", "Define input/output schemas.", "code_generator", "high"),
                    ("Ingestion", "Data ingestion from sources.", "code_generator", "high"),
                    ("Transform", "Transformation and cleaning.", "code_generator", "high"),
                    ("Validation", "Data quality checks.", "testing_agent", "medium"),
                    ("Optimization", "Performance tuning.", "optimizer", "medium"),
                    ("Monitoring", "Logging and alerting.", "code_generator", "low"),
                    ("Docs", "Pipeline documentation.", "documentation_agent", "low"),
                ),
            },
            "ml_model": {
                "context": "Machine learning model project.",
                "tasks": tasks(
                    ("Data Prep", "Data loading and preprocessing.", "code_generator", "high"),
                    ("EDA", "Exploratory data analysis.", "code_generator", "medium"),
                    ("Model Design", "Architecture selection.", "code_generator", "high"),
                    ("Training", "Training loop implementation.", "code_generator", "high"),
                    ("Evaluation", "Metrics and validation.", "testing_agent", "high"),
                    ("Serving", "Inference API or export.", "code_generator", "medium"),
                    ("Docs", "Model card and usage guide.", "documentation_agent", "low"),
                ),
            },
        }

    def list_templates(self) -> list:
        return list(self._builtin_templates().keys())


def workspace_dir(project_id: str) -> Path:
    """Public accessor for a project's workspace directory — used by
    interfaces/ for cmd_project_create's display line (was the private
    module helper _project_path(...) / 'workspace' pre-split)."""
    return _project_path(project_id) / "workspace"
