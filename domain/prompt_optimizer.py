"""domain/prompt_optimizer.py — Prompt Optimizer domain layer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Pure data + pure functions for prompt optimization, scoring, A/B testing,
and prompt library management. No I/O, no print(), no `import anthropic` —
those belong to infrastructure/.
"""

import json
import time
from pathlib import Path


def optimize_prompt(prompt: str) -> str:
    system = (
        "You are an expert prompt engineer. Rewrite the user's prompt to be "
        "clearer, more specific, and more likely to get a great response from an AI. "
        "Return ONLY the improved prompt — no commentary, no explanation."
    )
    return system, f"Prompt to improve:\n{prompt}"


def score_prompt(prompt: str) -> tuple:
    system = (
        "You are a prompt quality evaluator. Score this prompt on three dimensions "
        "(each 0-100): clarity, specificity, completeness. "
        'Return ONLY a JSON object: {"clarity": N, "specificity": N, "completeness": N, '
        '"total": N, "feedback": "one sentence of the most impactful improvement"}. '
        "Total = average of the three scores."
    )
    return system, f"Prompt to score:\n{prompt}", 512


def ab_test_prompts(prompt_a: str, prompt_b: str, task: str) -> tuple:
    judge_prompt = (
        f"Task: {task}\n\n"
        f"Response A:\n{{response_a}}\\n\\n"
        f"Response B:\n{{response_b}}\\n\\n"
        "Which response better completes the task? Reply ONLY with a JSON object: "
        '{"winner": "A" or "B" or "tie", "reason": "one sentence", '
        '"score_a": 0-100, "score_b": 0-100}'
    )
    return judge_prompt, 512


def parse_score(raw: str) -> dict:
    try:
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "Could not parse score", "raw": raw}


def parse_judgment(raw: str) -> dict:
    try:
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"winner": "unknown", "reason": raw}


PROMPT_LIB_PATH = Path("~/.ai-coder/prompt_library.json").expanduser()


def load_lib() -> dict:
    if PROMPT_LIB_PATH.exists():
        try:
            with open(PROMPT_LIB_PATH) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_lib(lib: dict):
    PROMPT_LIB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROMPT_LIB_PATH, "w") as f:
        json.dump(lib, f, indent=2)


def lib_add_entry(lib: dict, prompt: str, tag: str) -> dict:
    lib[tag] = {"prompt": prompt, "added": time.strftime("%Y-%m-%dT%H:%M:%S")}
    save_lib(lib)
    return lib


def lib_list_entries(lib: dict) -> list:
    return [{"tag": k, "added": v.get("added", ""), "preview": v["prompt"][:80]} for k, v in lib.items()]


def lib_get_entry(lib: dict, tag: str) -> str | None:
    return lib.get(tag, {}).get("prompt")
