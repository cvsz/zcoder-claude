"""
claude_powerpoint.py — Conversational slide-deck assistant (compatibility shim)
AI Model Coder CLI v1.50.0 (Clean Architecture refactor, Phase C, Context #4)

This module used to contain the full implementation (459 lines: the
PptxSession class, the REPL chat loop, and the --pptx-native path). It
has been split into:

  domain/powerpoint.py                              — pure constants
                                                        (SYSTEM_PROMPT,
                                                        _CODE_BLOCK,
                                                        _DENYLIST,
                                                        HELP_TEXT)
  infrastructure/local_storage/pptx_deck_store.py    — PptxSession
                                                        (python-pptx +
                                                        disk I/O)
  application/pptx_service.py                        — use-case layer
                                                        (one turn's worth
                                                        of logic, both
                                                        the hand-rolled
                                                        and --pptx-native
                                                        paths)
  interfaces/cli/commands/pptx_commands.py           — print()/input(),
                                                        the REPL shell

This file re-exports every name the old module used to export, so
existing imports (`from claude_powerpoint import cmd_pptx_chat`, used
by main.py) keep working unmodified. See exec-planning.md §5
(migration playbook).
"""

from domain.powerpoint import _CODE_BLOCK, _DENYLIST, HELP_TEXT, SYSTEM_PROMPT
from infrastructure.local_storage.pptx_deck_store import PptxSession, Presentation
from interfaces.cli.commands.pptx_commands import _cmd_pptx_chat_native, cmd_pptx_chat

__all__ = [
    "SYSTEM_PROMPT",
    "_CODE_BLOCK",
    "_DENYLIST",
    "HELP_TEXT",
    "PptxSession",
    "Presentation",
    "cmd_pptx_chat",
    "_cmd_pptx_chat_native",
]
