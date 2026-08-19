"""
claude_excel.py — Conversational spreadsheet / data-analysis assistant (compatibility shim)
AI Model Coder CLI v1.51.0 (Clean Architecture refactor, Phase C, Context #4)

This module used to contain the full implementation (397 lines: the
ExcelSession class, the REPL chat loop, and the --excel-native path). It
has been split into:

  domain/excel.py                                    — pure constants
                                                        (SYSTEM_PROMPT,
                                                        _CODE_BLOCK,
                                                        _DENYLIST,
                                                        HELP_TEXT)
  infrastructure/local_storage/excel_workbook_store.py — ExcelSession
                                                        (pandas/openpyxl +
                                                        disk I/O)
  application/excel_service.py                       — use-case layer
                                                        (one turn's worth
                                                        of logic, both
                                                        the hand-rolled
                                                        and --excel-native
                                                        paths)
  interfaces/cli/commands/excel_commands.py          — print()/input(),
                                                        the REPL shell

This file re-exports every name the old module used to export, so
existing imports (`from claude_excel import cmd_excel_chat`, used by
main.py) keep working unmodified. See exec-planning.md §5 (migration
playbook).
"""

from domain.excel import SYSTEM_PROMPT, _CODE_BLOCK, _DENYLIST, HELP_TEXT
from infrastructure.local_storage.excel_workbook_store import ExcelSession, pd
from interfaces.cli.commands.excel_commands import cmd_excel_chat, _cmd_excel_chat_native

__all__ = [
    "SYSTEM_PROMPT", "_CODE_BLOCK", "_DENYLIST", "HELP_TEXT",
    "ExcelSession", "pd",
    "cmd_excel_chat", "_cmd_excel_chat_native",
]
