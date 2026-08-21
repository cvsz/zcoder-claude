"""
domain/excel.py — Excel chat domain layer
AI Model Coder CLI v1.51.0 (Clean Architecture refactor, Phase C, Context #4)

Pure data for the Excel chat bounded context — the system prompt, the
code-block regex, the safety denylist, and the REPL help text. No I/O,
no print(). Extracted 2026-08-18 from claude_excel.py.

Same reasoning as domain/powerpoint.py: ExcelSession itself (the
stateful, pandas/openpyxl-backed workbook object) is NOT here — it
stays as a single class in infrastructure/local_storage/
excel_workbook_store.py, per the CodeSession/PptxSession precedent.
"""

import re

SYSTEM_PROMPT = """\
You are a spreadsheet assistant embedded in a CLI tool. The user is \
chatting with you to clean messy data, build financial models, summarize \
data, and create tables and charts — all applied directly to a live set \
of pandas DataFrames that get written back to a real .xlsx file after \
every turn.

You have access to a dict called `sheets` (sheet name -> pandas \
DataFrame) and the `pandas` module (as `pd`). To add a chart, call the \
provided `add_chart(sheet, chart_type, title, categories_col, value_cols)` \
helper, where chart_type is one of "bar", "line", or "pie", \
categories_col is a single column name, and value_cols is a list of \
column names.

Respond in ONE of two ways:

1. If the request requires changing the data (cleaning, transforming, \
computing new columns, building a model, adding a chart), respond with \
ONLY a single fenced python code block that mutates `sheets` in place \
(e.g. `sheets["Sheet1"] = sheets["Sheet1"].dropna()`) and/or calls \
`add_chart(...)`. No prose outside the code block.

2. If the request is a question that doesn't require changing the data \
(e.g. "what's the average of column X", "explain this model"), answer in \
plain text with no code block. You may compute the answer yourself from \
the sheet summary given to you, but do not guess at exact values you \
can't see — say so if you'd need a code-modifying turn to compute them.

Never write to disk, never import anything beyond pandas/numpy/datetime, \
never use `open(`, `os`, `sys`, `subprocess`, or `eval`/`exec`.
"""

_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)

# Best-effort denylist for model-generated code executed locally. This is
# not a real sandbox (see security.py's module docstring — local code
# execution sandboxing is explicitly out of scope there and left to each
# feature to handle) — it exists to catch obviously unsafe generations,
# not a malicious actor. Anything more sensitive should go through
# --code-agent-sandbox instead, which isolates filesystem/network access.
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
  /exit, /quit         End the session (workbook is already saved)
  /sheets              List current sheets and their shape
  /show SHEET [N]      Print the first N rows of SHEET (default 10)
  /undo                Revert to the state before the last applied change
"""
