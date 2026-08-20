"""
claude_eval.py — Evaluation harness for prompts, agents, and skills
(compatibility shim)
AI Model Coder CLI v1.53.1 (Clean Architecture refactor, Phase D, Context #7)

This module used to contain the full implementation (198 lines: the
EvalCase/EvalResult/EvalRun dataclasses, LLMJudge, EvalRunner, a
_save_run() disk writer, and 4 cmd_* CLI entry points). It has been
split into:

  domain/observability.py                              — EvalCase,
                                                          EvalResult,
                                                          EvalRun,
                                                          build_eval_run()
                                                          (the pure
                                                          aggregation half
                                                          of the old
                                                          EvalRunner.run())
  infrastructure/anthropic_api/observability_gateway.py — LLMJudge,
                                                          EvalRunner (real
                                                          anthropic SDK
                                                          calls; .run()'s
                                                          print() calls
                                                          converted to an
                                                          on_case callback)
  infrastructure/local_storage/observability_store.py  — EVALS_DIR,
                                                          save_eval_run()
                                                          (was _save_run()),
                                                          load_eval_run_summaries(),
                                                          load_eval_suite(),
                                                          write_eval_suite_scaffold(),
                                                          write_eval_first_result_json()
  application/observability_service.py                 — use-case layer
  interfaces/cli/commands/observability_commands.py     — print(), the 4
                                                          cmd_* entry points

This file re-exports every name the old module used to export, so
existing imports (`from claude_eval import EvalCase`, etc., used by
main.py) keep working unmodified. See exec-planning.md §5 (migration
playbook).
"""

from domain.observability import EvalCase, EvalResult, EvalRun
from infrastructure.anthropic_api.observability_gateway import LLMJudge, EvalRunner
from infrastructure.local_storage.observability_store import (
    EVALS_DIR, save_eval_run as _save_run,
)
from interfaces.cli.commands.observability_commands import (
    cmd_eval_run, cmd_eval_compare, cmd_eval_list, cmd_eval_scaffold,
)

__all__ = [
    "EVALS_DIR", "EvalCase", "EvalResult", "EvalRun", "LLMJudge",
    "EvalRunner", "_save_run",
    "cmd_eval_run", "cmd_eval_compare", "cmd_eval_list", "cmd_eval_scaffold",
]
