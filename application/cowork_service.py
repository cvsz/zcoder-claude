"""
application/cowork_service.py — use-case layer for the Cowork bounded
context
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

Orchestrates domain/cowork.py + infrastructure/anthropic_api/
cowork_gateway.py — no print() of its own (progress lines flow through
the on_progress callback to interfaces/). Extracted 2026-08-22 from
cowork.py.

CoworkAgent.iterate() is not surfaced here: it had no cmd_* caller in
the original module either, and §6's DoD requires every function in this
layer to be reachable from interfaces/cli/commands/*. It remains
available on the gateway class for programmatic callers.
"""

from collections.abc import Callable

from infrastructure.anthropic_api.cowork_gateway import CoworkAgent

_NOOP: Callable[[str], None] = lambda *a, **k: None  # noqa: E731


def run_cowork_task(
    api_key: str,
    model: str,
    task_type: str,
    prompt: str,
    files: list[str] | None = None,
    depth: int = 3,
    output_fmt: str = "markdown",
    on_progress: Callable[[str], None] = _NOOP,
) -> dict:
    """Execute one cowork task end-to-end and return its result dict."""
    agent = CoworkAgent(api_key=api_key, model=model)
    return agent.run(
        task_type, prompt, files=files, depth=depth, output_fmt=output_fmt, on_progress=on_progress
    )
