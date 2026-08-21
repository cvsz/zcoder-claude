"""application/prompt_optimizer_service.py — use-case layer for Prompt Optimizer
# mypy: ignore-errors
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Orchestrates domain/prompt_optimizer.py + infrastructure/local_storage/
prompt_library_store.py — no print() of its own.
"""

from collections.abc import Callable

from domain.prompt_optimizer import (
    ab_test_prompts,
    lib_add_entry,
    lib_get_entry,
    lib_list_entries,
    optimize_prompt,
    parse_judgment,
    parse_score,
    score_prompt,
)
from infrastructure.local_storage.prompt_library_store import read_prompt_lib, write_prompt_lib


def optimize(prompt: str) -> tuple[str, str]:
    system, user = optimize_prompt(prompt)
    return system, user


def score(prompt: str) -> tuple[str, str, int, Callable[[str], dict]]:
    system, user, max_tokens = score_prompt(prompt)
    return system, user, max_tokens, parse_score


def ab_test(prompt_a: str, prompt_b: str, task: str) -> tuple:
    judge_prompt, max_tokens = ab_test_prompts(prompt_a, prompt_b, task)
    return judge_prompt, max_tokens, parse_judgment


def add_to_lib(prompt: str, tag: str) -> dict:
    lib = read_prompt_lib()
    lib = lib_add_entry(lib, prompt, tag)
    write_prompt_lib(lib)
    return lib


def list_lib() -> list:
    return lib_list_entries(read_prompt_lib())


def get_from_lib(tag: str) -> str | None:
    return lib_get_entry(read_prompt_lib(), tag)
