"""
domain/files.py — Files API (beta) domain layer
AI Model Coder CLI v1.50.0 (Clean Architecture refactor, Phase C, Context #4)

Pure data and pure logic for the Files API bounded context — no I/O,
no print(). Extracted 2026-08-18 from claude_files.py.

BETA_HEADER follows the same convention as domain/messaging.py's
FINE_GRAINED_TOOL_STREAMING_BETA and domain/tools.py's
CONTEXT_MANAGEMENT_BETA: a feature-flag string is domain-meaningful
(it's part of what a "Files API call" *is*), so it lives here even
though only the infrastructure/anthropic_api/ gateway ever puts it on
the wire. Endpoint URLs (FILES_BASE, MESSAGES_BASE) are not
domain-meaningful the same way — those stay in
infrastructure/anthropic_api/files_gateway.py, per the pattern
established for infrastructure/anthropic_api/messaging_gateway.py's
MESSAGES_ENDPOINT.
"""

from typing import Optional

BETA_HEADER = "files-api-2025-04-14"

# platform.claude.com/docs/en/build-with-claude/files — File storage and limits
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB per file
_FORBIDDEN_FILENAME_CHARS = set('<>:"|?*\\/') | {chr(c) for c in range(32)}


def _validate_filename(name: str) -> Optional[str]:
    """Mirror the API's documented Invalid filename (400) rule client-side.
    Returns an error message, or None if the filename is fine."""
    if not (1 <= len(name) <= 255):
        return f"Invalid filename: must be 1-255 characters (got {len(name)})"
    bad = _FORBIDDEN_FILENAME_CHARS & set(name)
    if bad:
        shown = ", ".join(repr(c) for c in sorted(bad, key=str))
        return f"Invalid filename: contains forbidden character(s) {shown}"
    return None
