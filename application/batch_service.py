"""
# mypy: ignore-errors
application/batch_service.py — use-case layer for the Messages Batch
API bounded context
AI Model Coder CLI v1.52.0 (Clean Architecture refactor, Phase C, Context #4)

Orchestrates infrastructure/anthropic_api/batch_gateway.py — no I/O of
its own, no print(). Extracted 2026-08-18 alongside claude_batch.py's
split. cmd_batch_generate's prompt-variant construction is the one
piece of real logic worth extracting (the rest of the original cmd_*
bodies are thin — one BatchCoder call + prints, same shape as
Context #4's files_service.py).
"""

from infrastructure.anthropic_api.batch_gateway import _NOOP, BatchCoder


def build_variant_prompts(prompt_template: str, n: int) -> list:
    return [f"{prompt_template} (variant {i+1} of {n})" for i in range(n)]


def submit_from_jsonl(
    jsonl_path: str,
    api_key: str,
    model: str,
    system: str = None,
    use_300k_output: bool = False,
    on_warning=_NOOP,
) -> str:
    bc = BatchCoder(api_key=api_key, model=model, use_300k_output=use_300k_output, on_warning=on_warning)
    return bc.submit_from_jsonl(jsonl_path, system=system)


def get_status(batch_id: str, api_key: str) -> dict:
    bc = BatchCoder(api_key=api_key)
    return bc.status(batch_id)


def get_results(batch_id: str, api_key: str, save_to: str = None) -> list:
    bc = BatchCoder(api_key=api_key)
    return bc.results(batch_id, save_to=save_to)


def list_batches(api_key: str) -> list:
    bc = BatchCoder(api_key=api_key)
    return bc.list_batches()


def cancel_batch(batch_id: str, api_key: str) -> None:
    bc = BatchCoder(api_key=api_key)
    bc.cancel(batch_id)


def generate_and_submit(prompt_template: str, n: int, api_key: str, model: str, system: str = None) -> str:
    prompts = build_variant_prompts(prompt_template, n)
    bc = BatchCoder(api_key=api_key, model=model)
    return bc.submit_prompts(prompts, system=system)


def wait_for_batch(batch_id: str, api_key: str, on_progress=_NOOP) -> dict:
    bc = BatchCoder(api_key=api_key)
    return bc.wait(batch_id, on_progress=on_progress)
