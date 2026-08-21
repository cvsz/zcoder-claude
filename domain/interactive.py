"""domain/interactive.py — Interactive chat domain layer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Pure data + pure functions for the interactive REPL. No I/O, no print(),
no input() — those belong to interfaces/.
"""

HELP_TEXT = """\
Commands:
  /help              Show this help
  /exit, /quit       End the session
  /reset             Clear conversation history (keeps system prompt)
  /system [TEXT]     Set/replace the system prompt, or clear it if empty
  /model [NAME]      Switch model for subsequent turns, or show current
  /save FILE         Write the full transcript to FILE (markdown)
  /history           Show turn count
"""


def format_transcript(history, system=None):
    lines = []
    if system:
        lines.append(f"### system\\n{system}\\n")
    for m in history:
        lines.append(f"### {m.get('role', '?')}\\n{m.get('content', '')}\\n")
    return "\\n".join(lines)
