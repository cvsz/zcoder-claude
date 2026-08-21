"""application/workflow_service.py — use-case layer for Workflow engine
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Orchestrates domain/workflow.py + infrastructure/anthropic_api/
workflow_gateway.py — no print() of its own.
"""

import time

from domain.workflow import (
    StepResult,
    Workflow,
    WorkflowRun,
    fill_template,
)
from infrastructure.anthropic_api.workflow_gateway import WorkflowGateway


def run_workflow(
    gateway: WorkflowGateway,
    wf: Workflow,
    initial_vars: dict[str, str] | None = None,
    verbose: bool = False,
) -> WorkflowRun:
    variables = dict(initial_vars or {})
    results: list[StepResult] = []
    completed = set()
    t_start = time.time()

    pending = list(wf.steps)
    max_iters = len(pending) ** 2 + 10
    iters = 0
    while pending and iters < max_iters:
        iters += 1
        ready = [s for s in pending if all(d in completed for d in s.depends_on)]
        if not ready:
            remaining_ids = [s.step_id for s in pending]
            for s in pending:
                results.append(
                    StepResult(
                        step_id=s.step_id,
                        output="",
                        latency_ms=0,
                        status="error",
                        error=f"Dependency deadlock — remaining: {remaining_ids}",
                    )
                )
            break
        for step in ready:
            pending.remove(step)
            instruction = fill_template(step.instruction, variables)
            t0 = time.time()
            try:
                output, ms = gateway.run_step(
                    step.model or wf.model,
                    instruction,
                    step.max_tokens,
                )
                variables[step.step_id] = output
                completed.add(step.step_id)
                results.append(StepResult(step_id=step.step_id, output=output, latency_ms=ms))
            except Exception as e:
                ms = int((time.time() - t0) * 1000)
                results.append(
                    StepResult(
                        step_id=step.step_id,
                        output="",
                        latency_ms=ms,
                        status="error",
                        error=str(e),
                    )
                )
                completed.add(step.step_id)

    return WorkflowRun(
        workflow=wf.name,
        results=results,
        variables=variables,
        elapsed_s=round(time.time() - t_start, 2),
    )


def scaffold_workflow() -> str:
    import json

    sample = {
        "name": "Example Workflow",
        "model": "claude-sonnet-5",
        "steps": [
            {"id": "draft", "instruction": "Write a short essay about: {{input}}"},
            {"id": "improve", "instruction": "Improve this essay:\\n{{draft}}", "depends_on": ["draft"]},
        ],
    }
    return json.dumps(sample, indent=2)
