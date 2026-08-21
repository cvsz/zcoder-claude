"""
claude_admin_api.py — COMPATIBILITY SHIM (Clean Architecture refactor, 2026-08-14)

Real content moved to two places:
  • HTTP client (AdminApiClient, AdminApiError)
    -> infrastructure/anthropic_api/admin_gateway.py
  • CLI presentation (every cmd_* / print() function, plus the small
    _default_date_range / _wrong_key_hint helpers they use)
    -> interfaces/cli/commands/admin_commands.py

This shim re-exports every public name so existing
`from claude_admin_api import X` call sites (main.py) keep working
unmodified during the migration. Tests were updated to monkeypatch
`interfaces.cli.commands.admin_commands.AdminApiClient` directly (the
module where cmd_* functions actually resolve that name at call time)
rather than this shim.
"""

from infrastructure.anthropic_api.admin_gateway import (
    CE_USER_MANAGEMENT_BETA,
    AdminApiClient,
    AdminApiError,
)
from interfaces.cli.commands.admin_commands import (
    _default_date_range,
    _wrong_key_hint,
    cmd_admin_create_key,
    cmd_admin_list_keys,
    cmd_admin_revoke_key,
    cmd_claude_code_usage_report,
    cmd_cmek_list,
    cmd_cost_report,
    cmd_group_create,
    cmd_group_delete,
    cmd_group_member_add,
    cmd_group_member_remove,
    cmd_group_members_list,
    cmd_groups_list,
    cmd_invite_create,
    cmd_invite_withdraw,
    cmd_invites_list,
    cmd_member_get,
    cmd_member_remove,
    cmd_member_role_set,
    cmd_members_list,
    cmd_rate_limits,
    cmd_rate_limits_workspace,
    cmd_role_permissions_list,
    cmd_roles_list,
    cmd_spend_limit_delete,
    cmd_spend_limit_get,
    cmd_spend_limit_request_approve,
    cmd_spend_limit_request_deny,
    cmd_spend_limit_requests_list,
    cmd_spend_limit_set,
    cmd_spend_limits_list,
    cmd_usage_report,
)

__all__ = [
    "AdminApiClient",
    "AdminApiError",
    "CE_USER_MANAGEMENT_BETA",
    "_default_date_range",
    "_wrong_key_hint",
    "cmd_admin_create_key",
    "cmd_admin_list_keys",
    "cmd_admin_revoke_key",
    "cmd_claude_code_usage_report",
    "cmd_cmek_list",
    "cmd_cost_report",
    "cmd_group_create",
    "cmd_group_delete",
    "cmd_group_member_add",
    "cmd_group_member_remove",
    "cmd_group_members_list",
    "cmd_groups_list",
    "cmd_invite_create",
    "cmd_invite_withdraw",
    "cmd_invites_list",
    "cmd_member_get",
    "cmd_member_remove",
    "cmd_member_role_set",
    "cmd_members_list",
    "cmd_rate_limits",
    "cmd_rate_limits_workspace",
    "cmd_role_permissions_list",
    "cmd_roles_list",
    "cmd_spend_limit_delete",
    "cmd_spend_limit_get",
    "cmd_spend_limit_request_approve",
    "cmd_spend_limit_request_deny",
    "cmd_spend_limit_requests_list",
    "cmd_spend_limit_set",
    "cmd_spend_limits_list",
    "cmd_usage_report",
]
