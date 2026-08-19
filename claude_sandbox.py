"""
claude_sandbox.py — Sandboxed Bash execution (compatibility shim)
AI Model Coder CLI v1.48.0 (Clean Architecture refactor, Phase C)

Real implementation moved 2026-08-16 — this module was entirely pure
logic (zero I/O), so it moved in full to domain/agent_execution.py:
  SandboxViolation, NETWORK_BINARIES, NETWORK_PIP_NPM_FLAGS,
  tokenize_command (was _tokenize), check_network, check_filesystem, enforce

New code should import from domain.agent_execution directly rather than
through this shim.
"""

from domain.agent_execution import (
    SandboxViolation, NETWORK_BINARIES, NETWORK_PIP_NPM_FLAGS,
    tokenize_command, check_network, check_filesystem, enforce,
)

__all__ = [
    "SandboxViolation", "NETWORK_BINARIES", "NETWORK_PIP_NPM_FLAGS",
    "tokenize_command", "check_network", "check_filesystem", "enforce",
]
