"""
claude_compliance_api.py — COMPATIBILITY SHIM (Clean Architecture refactor, 2026-08-14)

Real content moved to two places:
  • HTTP client (ComplianceApiClient, ComplianceApiError)
    -> infrastructure/anthropic_api/compliance_gateway.py
  • CLI presentation (every cmd_compliance_* / print() function)
    -> interfaces/cli/commands/compliance_commands.py

This shim re-exports every public name so existing
`from claude_compliance_api import X` call sites (main.py) keep working
unmodified during the migration. Tests were updated to monkeypatch
`interfaces.cli.commands.compliance_commands.ComplianceApiClient` directly
(the module where cmd_* functions actually resolve that name at call time)
rather than this shim, since patching a re-exported name here would not
affect the name lookup inside the CLI module's own functions.
"""

from infrastructure.anthropic_api.compliance_gateway import (
    ComplianceApiClient, ComplianceApiError,
    _is_retryable, _parse_content_disposition_filename,
)
from interfaces.cli.commands.compliance_commands import (
    cmd_compliance_activities,
    cmd_compliance_chats_list,
    cmd_compliance_chat_messages,
    cmd_compliance_chat_delete,
    cmd_compliance_file_download,
    cmd_compliance_file_delete,
    cmd_compliance_projects_list,
    cmd_compliance_project_info,
    cmd_compliance_project_attachments,
    cmd_compliance_project_delete,
    cmd_compliance_orgs_list,
    cmd_compliance_org_users,
    cmd_compliance_org_roles,
    cmd_compliance_org_settings,
    cmd_compliance_groups_list,
    cmd_compliance_group_members,
    cmd_compliance_local_sessions_list,
    cmd_compliance_local_session_get,
    cmd_compliance_local_session_messages,
    cmd_compliance_remote_sessions_list,
    cmd_compliance_remote_session_messages,
)

__all__ = [
    "ComplianceApiClient", "ComplianceApiError",
    "cmd_compliance_activities", "cmd_compliance_chats_list",
    "cmd_compliance_chat_messages", "cmd_compliance_chat_delete",
    "cmd_compliance_file_download", "cmd_compliance_file_delete",
    "cmd_compliance_projects_list", "cmd_compliance_project_info",
    "cmd_compliance_project_attachments", "cmd_compliance_project_delete",
    "cmd_compliance_orgs_list", "cmd_compliance_org_users",
    "cmd_compliance_org_roles", "cmd_compliance_org_settings",
    "cmd_compliance_groups_list", "cmd_compliance_group_members",
    "cmd_compliance_local_sessions_list", "cmd_compliance_local_session_get",
    "cmd_compliance_local_session_messages", "cmd_compliance_remote_sessions_list",
    "cmd_compliance_remote_session_messages",
]
