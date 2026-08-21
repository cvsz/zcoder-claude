"""
claude_chrome.py — CLI browsing-agent loop (compatibility shim)
AI Model Coder CLI v1.54.0 (Clean Architecture refactor, Phase D, Context #8)

IMPORTANT — what this module is, and isn't (preserved from the original):
Claude in Chrome is a browser extension with a side panel, click/type/tab
control, logged-in-session context, and its own prompt-injection defenses
— none of which a CLI process can replicate, because a terminal has no
browser to sit inside. This module is a same-*shape* analog for headless
use: Claude reads a page's text, decides one action, this module performs
it (fetch a URL, or stop and report), and the loop repeats with the new
page as context. There's no clicking, no form-filling, no logged-in
cookies, and no Chrome-specific attack surface — just fetch-observe-decide,
in a loop.

If you actually want Claude in Chrome, install the extension from the
Chrome Web Store and sign in with your Claude account; there's no API
that lets a script drive it. This module exists for headless/CI use
cases where a real browser isn't available or wanted.

Safety note: browsing agents are exposed to prompt injection. This module
has none of the classifier-based defenses Claude in Chrome ships with.
Don't run it unattended against sites you don't control.

This module used to contain the full implementation (218 lines: an HTML
text extractor, page fetching with retry, the full step-by-step loop with
print() at every step, and one cmd_* CLI entry point). It has been split
into:

  domain/devtools.py                                    — MAX_PAGE_CHARS,
                                                           BROWSE_SYSTEM_PROMPT
                                                           (was SYSTEM_PROMPT),
                                                           TextExtractor
                                                           (was _TextExtractor),
                                                           domain_allowed()
                                                           (was _domain_allowed()),
                                                           parse_json_action()
                                                           (was
                                                           _parse_json_action()),
                                                           BrowseStep (new —
                                                           the pure "what
                                                           happened" record
                                                           replacing inline
                                                           print())
  infrastructure/anthropic_api/devtools_gateway.py       — fetch_page()
                                                           (unchanged
                                                           signature),
                                                           _fetch_retrying(),
                                                           make_coder()/
                                                           browse_decide()
                                                           (the Coder-driven
                                                           decide step)
  application/devtools_service.py                        — browse_session():
                                                           the full loop,
                                                           print() calls
                                                           converted to an
                                                           on_step(BrowseStep)
                                                           callback — same
                                                           convention as
                                                           agents_gateway.py's
                                                           on_step/on_delta
  interfaces/cli/commands/devtools_commands.py           — print(), the one
                                                           cmd_browse entry
                                                           point (its on_step
                                                           handler reproduces
                                                           every original
                                                           print exactly)

This file re-exports every name the old module used to export, so
existing imports (`from claude_chrome import cmd_browse`, etc., used by
main.py) keep working unmodified. See exec-planning.md §5 (migration
playbook).
"""

from domain.devtools import (
    BROWSE_SYSTEM_PROMPT as SYSTEM_PROMPT,
)
from domain.devtools import (
    MAX_PAGE_CHARS,
)
from domain.devtools import (
    TextExtractor as _TextExtractor,
)
from domain.devtools import (
    domain_allowed as _domain_allowed,
)
from domain.devtools import (
    parse_json_action as _parse_json_action,
)
from infrastructure.anthropic_api.devtools_gateway import (
    _fetch_retrying,
    fetch_page,
)
from interfaces.cli.commands.devtools_commands import cmd_browse

__all__ = [
    "MAX_PAGE_CHARS",
    "SYSTEM_PROMPT",
    "_TextExtractor",
    "fetch_page",
    "_fetch_retrying",
    "_domain_allowed",
    "_parse_json_action",
    "cmd_browse",
]
