"""application/interactive_service.py — use-case layer for Interactive REPL
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Orchestrates domain/interactive.py — no print() of its own. The actual
input/output loop lives in interfaces/.
"""


from domain.interactive import HELP_TEXT, format_transcript


def get_help_text() -> str:
    return HELP_TEXT


def format_transcript_md(history, system=None) -> str:
    return format_transcript(history, system)
