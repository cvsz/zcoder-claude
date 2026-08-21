"""
domain/powerpoint.py — PowerPoint chat domain layer
AI Model Coder CLI v1.50.0 (Clean Architecture refactor, Phase C, Context #4)

Pure data for the PowerPoint chat bounded context — the system prompt,
the code-block regex used to pull generated deck-edit code out of a
model reply, the safety denylist, and the REPL help text. No I/O, no
print(). Extracted 2026-08-18 from claude_powerpoint.py.

PptxSession itself (the stateful, python-pptx-backed slide-deck object)
is NOT here — like CodeSession in Context #3, it's a single class whose
methods are pervasively mixed pure-logic/disk-and-library-I/O
(summary()/undo()/apply_code() are pure; _load()/save()/_add_table()/
_add_chart() all touch the python-pptx library and disk), so per the
precedent set for CodeSession it stays as one class in
infrastructure/local_storage/pptx_deck_store.py rather than being torn
apart method-by-method.
"""

import re

SYSTEM_PROMPT = """\
You are a slide-deck assistant embedded in a CLI tool. The user is \
chatting with you to add slides, restyle text, turn bullets into tables, \
and add charts — all applied directly to a live in-memory deck \
representation that gets written back to a real .pptx file after every \
turn.

You have access to a list called `slides`, where each slide is a dict:
  {"title": str, "bullets": [str, ...], "layout": "title_content" | "title_only" | "section_header",
   "table": {"headers": [str,...], "rows": [[str,...], ...]} | None,
   "chart": {"type": "bar"|"line"|"pie", "categories": [str,...], "series": {name: [num,...]}} | None}

To change the deck, call the provided helper functions — do not build the
.pptx file yourself:
  add_slide(title, bullets=None, layout="title_content", table=None, chart=None)
  update_slide(index, title=None, bullets=None, table=None, chart=None)
  delete_slide(index)
  reorder_slides(new_order)   # new_order is a list of old indices, e.g. [0,2,1]

Respond in ONE of two ways:

1. If the request requires changing the deck (adding/editing/removing/
reordering slides), respond with ONLY a single fenced python code block
that calls the helper functions above. No prose outside the code block.

2. If the request is a question that doesn't require changing the deck
(e.g. "how many slides do I have", "what does slide 3 say"), answer in
plain text with no code block, using the deck summary given to you.

Never write to disk, never import anything, never use `open(`, `os`,
`sys`, `subprocess`, or `eval`/`exec`. Keep bullets concise (under ~12
words each) and cap slides at 5-6 bullets — this is a presentation, not a
document.
"""

_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)

# Mirrors claude_excel.py's denylist for the same reason: this is a
# best-effort catch for obviously unsafe generated code, not a real
# sandbox. Anything more sensitive should go through
# --code-agent-sandbox instead.
_DENYLIST = (
    "import os",
    "import sys",
    "import subprocess",
    "import socket",
    "__import__",
    "open(",
    "eval(",
    "exec(",
    "os.",
    "sys.",
    "subprocess.",
    "socket.",
    "shutil.",
    ".system(",
    "pathlib",
)

HELP_TEXT = """\
Commands:
  /help                Show this help
  /exit, /quit         End the session (deck is already saved)
  /slides              List current slides and their titles
  /show N              Print the text content of slide N
  /undo                Revert to the state before the last applied change
"""
