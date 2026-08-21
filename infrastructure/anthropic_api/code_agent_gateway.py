"""
# mypy: ignore-errors
infrastructure/anthropic_api/code_agent_gateway.py — live Anthropic API
adapters for Code Execution tool, Plan Mode, and Multi-Agent Router
AI Model Coder CLI v1.48.0 (Clean Architecture refactor, Phase C)

Extracted 2026-08-16 from claude_code_exec.py, claude_hooks_perms_plan.py
(the Plan Mode third), and claude_router.py — the HTTP-calling pieces of
those three modules, grouped here since they're all straightforward
Messages API callers with no local-disk state of their own (unlike the
hooks/permissions halves of claude_hooks_perms_plan.py, which are in
infrastructure/local_storage/hooks_permissions_store.py).
"""

import base64
import json
import urllib.request
from collections.abc import Callable
from pathlib import Path

import anthropic

from domain.agent_execution import Plan, PlanStep
from exceptions import AICoderError
from resilience import CircuitBreaker, retry, urlopen_json
from utils import sampling_kwargs

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)
_NOOP = lambda *a, **k: None  # noqa: E731


# ── Code Execution tool (claude_code_exec.py) ───────────────────────────────

LEGACY_BETA_HEADER = "code-execution-2025-05-22"
LEGACY_CODE_EXEC_VERSION = "code_execution_20250522"
DEFAULT_CODE_EXEC_VERSION = "code_execution_20260521"

CODE_EXEC_TOOL = {"type": DEFAULT_CODE_EXEC_VERSION, "name": "code_execution"}


class CodeExecutionCoder:
    """Claude client with server-side code execution."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-5",
        max_tokens: int = 8192,
        code_exec_version: str = DEFAULT_CODE_EXEC_VERSION,
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.code_exec_version = code_exec_version

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        if self.code_exec_version == LEGACY_CODE_EXEC_VERSION:
            headers["anthropic-beta"] = LEGACY_BETA_HEADER
        req = urllib.request.Request(
            MESSAGES_ENDPOINT, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict) -> dict:
        try:
            return self._call(payload)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def execute(
        self,
        prompt: str,
        system: str | None = None,
        file_ids: list | None = None,
        output_dir: str | None = None,
        on_file_saved: Callable[[str], None] = _NOOP,
    ) -> dict:
        """Ask Claude to write and run code. Returns {"text", "outputs",
        "files", "usage"}."""
        content = [{"type": "text", "text": prompt}]
        for fid in file_ids or []:
            content.append({"type": "container_upload", "file_id": fid})

        messages = [{"role": "user", "content": content}]
        code_exec_tool = {"type": self.code_exec_version, "name": "code_execution"}
        payload: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "tools": [code_exec_tool],
            "messages": messages,
        }
        if system:
            payload["system"] = system

        data = self._post(payload)
        if "error" in data:
            return {"text": f"[ERROR] {data['error']}", "outputs": [], "files": []}

        text, outputs, files = "", [], []

        for block in data.get("content", []):
            btype = block.get("type", "")
            if btype == "text":
                text += block.get("text", "")
            elif btype == "tool_use" and block.get("name") == "code_execution":
                outputs.append({"type": "code", "input": block.get("input", {}).get("code", "")})
            elif btype == "tool_result":
                for sub in block.get("content", []):
                    st = sub.get("type", "")
                    if st == "text":
                        outputs.append({"type": "stdout", "text": sub.get("text", "")})
                    elif st == "image":
                        img_data = sub.get("source", {}).get("data", "")
                        img_type = sub.get("source", {}).get("media_type", "image/png")
                        files.append({"type": "image", "data": img_data, "media_type": img_type})
                        outputs.append({"type": "image_output", "media_type": img_type})
            elif btype == "server_tool_use":
                code = block.get("input", {}).get("code", "")
                if code:
                    outputs.append({"type": "executed_code", "code": code})
            elif btype == "server_tool_result":
                for sub in block.get("content", []):
                    st = sub.get("type", "")
                    if st == "text":
                        outputs.append({"type": "stdout", "text": sub.get("text", "")})
                    elif st == "image":
                        img_data = sub.get("source", {}).get("data", "")
                        img_mt = sub.get("source", {}).get("media_type", "image/png")
                        files.append({"type": "image", "data": img_data, "media_type": img_mt})
                        if output_dir:
                            ext = img_mt.split("/")[-1]
                            p = Path(output_dir) / f"output_{len(files)}.{ext}"
                            p.parent.mkdir(parents=True, exist_ok=True)
                            p.write_bytes(base64.b64decode(img_data))
                            on_file_saved(str(p))

        return {"text": text, "outputs": outputs, "files": files, "usage": data.get("usage", {})}

    def debug_code(self, code: str, language: str = "python") -> dict:
        prompt = (
            f"Debug this {language} code. Run it, find errors, fix them, "
            f"and show the working version:\n\n```{language}\n{code}\n```"
        )
        return self.execute(prompt, system="You are an expert debugger. Run the code and fix all errors.")

    def analyse_data(self, csv_path: str, question: str) -> dict:
        code = Path(csv_path).read_text()
        prompt = (
            f"Analyse this CSV data and answer: {question}\n\n"
            f"CSV content:\n```\n{code[:10000]}\n```\n\n"
            "Write Python code to load and analyse the data, then answer the question."
        )
        return self.execute(prompt)


# ── Plan Mode (claude_hooks_perms_plan.py) ──────────────────────────────────


class PlanModeAgent:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def _call(self, system: str, user: str, max_tokens: int = 2048) -> str:
        r = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0.3,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return r.content[0].text

    def propose(self, task: str, context: str = "") -> Plan:
        raw = self._call(
            "Output only valid JSON.",
            f"Break this task into 3–8 concrete, numbered steps. Return ONLY a JSON array of strings.\n"
            f"Task: {task}\n" + (f"Context:\n{context}" if context else ""),
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:-1])
        try:
            descs = json.loads(cleaned)
        except Exception:
            descs = [ln.lstrip("-· ").strip() for ln in raw.splitlines() if ln.strip()]
        return Plan(task=task, steps=[PlanStep(number=i + 1, description=d) for i, d in enumerate(descs)])

    def execute_step(self, plan: Plan, number: int) -> PlanStep:
        if not plan.approved:
            raise PermissionError("Plan not approved")
        step = next((s for s in plan.steps if s.number == number), None)
        if not step:
            raise ValueError(f"Step {number} not found")
        prior = "\n".join(f"Step {s.number}: {s.result}" for s in plan.steps if s.completed and s.result)
        step.result = self._call(
            "Execute the task step precisely.",
            f"Task: {plan.task}\nStep {step.number}: {step.description}\n"
            + (f"\nCompleted prior steps:\n{prior}" if prior else ""),
        )
        step.completed = True
        return step

    def execute_all(self, plan: Plan, on_step: Callable[[PlanStep], None] = _NOOP) -> Plan:
        for s in plan.steps:
            if not s.completed:
                self.execute_step(plan, s.number)
                on_step(s)
        return plan

    @staticmethod
    def approve(plan: Plan) -> Plan:
        plan.approved = True
        return plan


# ── Multi-Agent Router (claude_router.py) ───────────────────────────────────


@retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
def _call(api_key: str, payload: dict) -> dict:
    headers = {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
    req = urllib.request.Request(
        MESSAGES_ENDPOINT, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    return urlopen_json(req, timeout=60)


def _post(api_key: str, payload: dict) -> dict:
    try:
        return _call(api_key, payload)
    except AICoderError as e:
        return {"error": e.message}
    except Exception as e:
        return {"error": str(e)}


def _text(data: dict) -> str:
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def classify(prompt: str, table: dict, api_key: str, model: str) -> tuple[str, str]:
    """Return (agent_name, reason) for the best-fit agent."""
    options = "\n".join(f"  {k}: {v}" for k, v in table.items())
    classifier_prompt = (
        f"You are a routing classifier. Given a user request, choose the single best "
        f"specialist agent from the list below. Reply with ONLY a JSON object: "
        f'{{"agent": "<agent_name>", "reason": "<one sentence>"}}\n\n'
        f"Agents:\n{options}\n\nUser request: {prompt}"
    )
    data = _post(
        api_key,
        {
            "model": model,
            "max_tokens": 200,
            **sampling_kwargs(model, temperature=0.0),
            "messages": [{"role": "user", "content": classifier_prompt}],
        },
    )
    raw = _text(data).strip()
    try:
        parsed = json.loads(raw)
        agent = parsed.get("agent", "code")
        reason = parsed.get("reason", "")
        if agent not in table:
            agent = "code"
        return agent, reason
    except (json.JSONDecodeError, KeyError):
        return "code", "classifier output not parseable; defaulting to code agent"


def route_and_call(
    prompt: str,
    api_key: str,
    model: str,
    table: dict,
    explain: bool = False,
    parallel: bool = False,
    on_route: Callable[[str, str], None] = _NOOP,
) -> str:
    if parallel:
        results = {}
        for agent_name, description in table.items():
            system = f"You are a specialist in: {description}. Answer as that expert."
            data = _post(
                api_key,
                {
                    "model": model,
                    "max_tokens": 2048,
                    **sampling_kwargs(model, temperature=0.5),
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            results[agent_name] = _text(data)
        synthesis_prompt = (
            "Multiple specialist agents answered this question. "
            "Synthesise the best, most complete answer, crediting unique insights "
            "from each agent where relevant.\n\n"
            + "\n\n".join(f"[{k.upper()}]\n{v}" for k, v in results.items())
            + f"\n\nOriginal question: {prompt}"
        )
        data = _post(
            api_key,
            {
                "model": model,
                "max_tokens": 4096,
                **sampling_kwargs(model, temperature=0.3),
                "messages": [{"role": "user", "content": synthesis_prompt}],
            },
        )
        return _text(data)

    agent_name, reason = classify(prompt, table, api_key, model)
    if explain:
        on_route(agent_name, reason)

    system = f"You are a specialist in: {table[agent_name]}. Answer as that expert."
    data = _post(
        api_key,
        {
            "model": model,
            "max_tokens": 4096,
            **sampling_kwargs(model, temperature=0.6),
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    return _text(data)
