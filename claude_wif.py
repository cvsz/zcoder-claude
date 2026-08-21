"""
claude_wif.py — Workload Identity Federation (WIF) (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

This module used to contain the full implementation (368 lines:
WIFExchangeError, WIFCredentialExchanger, resolve_wif_env, WIFAdminClient,
WIF_ENV_VARS, and 7 cmd_* CLI entry points). It has been split into:

  domain/wif.py                                         — WIFExchangeError,
                                                          WIF_ENV_VARS,
                                                          resolve_wif_env(),
                                                          OAUTH_TOKEN_ENDPOINT, etc.
  infrastructure/anthropic_api/wif_gateway.py           — WIFCredentialExchanger,
                                                          WIFAdminClient
  application/wif_service.py                            — use-case layer
  interfaces/cli/commands/wif_commands.py               — print(), cmd_wif_*

This file re-exports every name the old module used to export, so
existing imports keep working unmodified.
"""

import urllib  # noqa: F401

from domain.wif import (
    WIFExchangeError, WIF_ENV_VARS, resolve_wif_env,
    OAUTH_TOKEN_ENDPOINT, ADMIN_BASE, JWT_BEARER_GRANT,
)
from infrastructure.anthropic_api.wif_gateway import (
    WIFCredentialExchanger, WIFAdminClient,
)
from interfaces.cli.commands.wif_commands import (
    cmd_wif_status, cmd_wif_exchange_token,
    cmd_wif_create_service_account, cmd_wif_list_service_accounts,
    cmd_wif_create_issuer, cmd_wif_list_issuers,
    cmd_wif_create_rule, cmd_wif_list_rules,
)

__all__ = [
    "WIFExchangeError", "WIF_ENV_VARS", "resolve_wif_env",
    "OAUTH_TOKEN_ENDPOINT", "ADMIN_BASE", "JWT_BEARER_GRANT",
    "WIFCredentialExchanger", "WIFAdminClient",
    "cmd_wif_status", "cmd_wif_exchange_token",
    "cmd_wif_create_service_account", "cmd_wif_list_service_accounts",
    "cmd_wif_create_issuer", "cmd_wif_list_issuers",
    "cmd_wif_create_rule", "cmd_wif_list_rules",
]
