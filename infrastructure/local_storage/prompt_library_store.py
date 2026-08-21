"""infrastructure/local_storage/prompt_library_store.py — Prompt Library persistence
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Local-disk I/O for the prompt library. No network calls, no print().
"""


from domain.prompt_optimizer import load_lib, save_lib


def read_prompt_lib() -> dict:
    return load_lib()


def write_prompt_lib(lib: dict):
    save_lib(lib)
