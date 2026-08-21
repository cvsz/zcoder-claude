"""
claude_workflow.py — Declarative multi-step pipelines (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

This module used to contain the full implementation (184 lines: WorkflowStep,
Workflow, StepResult, WorkflowRun, _load, _parse, _fill, run_workflow,
cmd_workflow_run, cmd_workflow_scaffold). It has been split into:

  domain/workflow.py                                    — WorkflowStep, Workflow,
                                                          StepResult, WorkflowRun,
                                                          load_workflow(),
                                                          parse_workflow(),
                                                          fill_template()
  infrastructure/anthropic_api/workflow_gateway.py      — WorkflowGateway
  application/workflow_service.py                       — use-case layer
  interfaces/cli/commands/workflow_commands.py          — print(), cmd_workflow_run,
                                                          cmd_workflow_scaffold

This file re-exports every name the old module used to export, so
existing imports keep working unmodified.
"""

from domain.workflow import (
    WorkflowStep, Workflow, StepResult, WorkflowRun,
    load_workflow, parse_workflow, fill_template,
)
from infrastructure.anthropic_api.workflow_gateway import WorkflowGateway
from interfaces.cli.commands.workflow_commands import (
    cmd_workflow_run, cmd_workflow_scaffold,
)

__all__ = [
    "WorkflowStep", "Workflow", "StepResult", "WorkflowRun",
    "load_workflow", "parse_workflow", "fill_template",
    "WorkflowGateway",
    "cmd_workflow_run", "cmd_workflow_scaffold",
]
