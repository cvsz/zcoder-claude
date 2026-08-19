"""
application/admin_service.py — Use-case layer for the Admin API
AI Model Coder CLI v1.44.0 (Clean Architecture refactor, Phase A)

Closes the application-layer gap flagged in exec-planing.md Phase A:
interfaces/cli/commands/admin_commands.py used to instantiate
AdminApiClient directly in every cmd_* function. Now every operation is a
plain function here — takes primitives, returns the gateway's raw dict
(including an "error" key on failure, same shape AdminApiClient already
used) — so a future Web UI can call the same 31 functions without
importing anything CLI-flavored.

Deliberately NOT moved here: the "print a hint when status is 401/403/404"
UI behavior — that's presentation, stays in admin_commands.py. What IS
here: the one piece of real logic, _default_date_range()'s usage/cost
report date defaulting, which used to live directly in cmd_usage_report /
cmd_cost_report.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from infrastructure.anthropic_api.admin_gateway import AdminApiClient


def _default_date_range() -> tuple:
    """Last 30 days, as (start_iso, end_iso). Used by get_usage_report/
    get_cost_report when the caller doesn't specify a range."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=30)
    return start.isoformat(), end.isoformat()


# ── Usage / Cost / Claude Code reports ──────────────────────────────────

def get_usage_report(admin_api_key: str, start: Optional[str] = None,
                     end: Optional[str] = None, group_by: str = "model") -> dict:
    default_start, default_end = _default_date_range()
    start = start or default_start
    end = end or default_end
    return AdminApiClient(admin_api_key).get_usage_report(start, end, group_by=group_by)


def get_cost_report(admin_api_key: str, start: Optional[str] = None,
                    end: Optional[str] = None, group_by: str = "model") -> dict:
    default_start, default_end = _default_date_range()
    start = start or default_start
    end = end or default_end
    return AdminApiClient(admin_api_key).get_cost_report(start, end, group_by=group_by)


def list_cmek_keys(admin_api_key: str, workspace_id: Optional[str] = None) -> dict:
    return AdminApiClient(admin_api_key).list_external_keys(workspace_id=workspace_id)


def get_claude_code_usage_report(admin_api_key: str, starting_at: str, limit: int = 20) -> dict:
    return AdminApiClient(admin_api_key).get_claude_code_usage_report(starting_at, limit=limit)


# ── API keys ──────────────────────────────────────────────────────────────

def list_api_keys(admin_api_key: str, limit: int = 20) -> dict:
    return AdminApiClient(admin_api_key).list_api_keys(limit=limit)


def revoke_api_key(admin_api_key: str, key_id: str) -> dict:
    return AdminApiClient(admin_api_key).revoke_api_key(key_id)


# create_api_key has no service function: there is no documented create-key
# endpoint (keys are Console-only, by design, so a raw secret is never
# returned to a script). cmd_admin_create_key stays pure presentation.


# ── Spend Limits API (Claude Enterprise only) ───────────────────────────

def list_effective_spend_limits(admin_api_key: str, limit: int = 50) -> dict:
    return AdminApiClient(admin_api_key).list_effective_spend_limits(limit=limit)


def set_spend_limit(admin_api_key: str, user_id: str, amount: str,
                    suppress_notification: bool = False) -> dict:
    return AdminApiClient(admin_api_key).set_spend_limit(
        user_id, amount, suppress_notification=suppress_notification)


def get_spend_limit(admin_api_key: str, spend_limit_id: str) -> dict:
    return AdminApiClient(admin_api_key).get_spend_limit(spend_limit_id)


def delete_spend_limit(admin_api_key: str, spend_limit_id: str) -> dict:
    return AdminApiClient(admin_api_key).delete_spend_limit(spend_limit_id)


def list_spend_limit_increase_requests(admin_api_key: str, status: Optional[str] = None) -> dict:
    status_filter = [status] if status else None
    return AdminApiClient(admin_api_key).list_spend_limit_increase_requests(status=status_filter)


def approve_spend_limit_increase_request(admin_api_key: str, request_id: str) -> dict:
    return AdminApiClient(admin_api_key).approve_spend_limit_increase_request(request_id)


def deny_spend_limit_increase_request(admin_api_key: str, request_id: str) -> dict:
    return AdminApiClient(admin_api_key).deny_spend_limit_increase_request(request_id)


# ── Rate Limits API (read-only) ─────────────────────────────────────────

def get_org_rate_limits(admin_api_key: str, model: Optional[str] = None) -> dict:
    return AdminApiClient(admin_api_key).get_org_rate_limits(model=model)


def get_workspace_rate_limits(admin_api_key: str, workspace_id: str) -> dict:
    return AdminApiClient(admin_api_key).get_workspace_rate_limits(workspace_id)


# ── Claude Enterprise User Management API (beta) ────────────────────────

def list_members(admin_api_key: str, limit: int = 20, email: Optional[str] = None) -> dict:
    return AdminApiClient(admin_api_key).list_members(limit=limit, email=email)


def get_member(admin_api_key: str, user_id: str) -> dict:
    return AdminApiClient(admin_api_key).get_member(user_id)


def update_member_role(admin_api_key: str, user_id: str, role: str) -> dict:
    """role must be "user" or "managed" — the API 400s on anything else,
    including the administrative roles, which can only be assigned in
    claude.ai organization settings."""
    return AdminApiClient(admin_api_key).update_member_role(user_id, role)


def remove_member(admin_api_key: str, user_id: str) -> dict:
    return AdminApiClient(admin_api_key).remove_member(user_id)


def create_invite(admin_api_key: str, email: str, role: str,
                  rbac_group_ids: Optional[list] = None) -> dict:
    return AdminApiClient(admin_api_key).create_invite(email, role, rbac_group_ids=rbac_group_ids)


def list_invites(admin_api_key: str, limit: int = 20) -> dict:
    return AdminApiClient(admin_api_key).list_invites(limit=limit)


def withdraw_invite(admin_api_key: str, invite_id: str) -> dict:
    """Only a pending invite can be withdrawn — accepted/expired both
    400 server-side."""
    return AdminApiClient(admin_api_key).withdraw_invite(invite_id)


def list_groups(admin_api_key: str, limit: int = 20) -> dict:
    return AdminApiClient(admin_api_key).list_groups(limit=limit)


def create_group(admin_api_key: str, name: str) -> dict:
    return AdminApiClient(admin_api_key).create_group(name)


def delete_group(admin_api_key: str, group_id: str) -> dict:
    """Members keep organization membership; they just lose the
    permissions this group's attached roles granted. SCIM-provisioned
    groups can't be deleted through the API — the request returns 400."""
    return AdminApiClient(admin_api_key).delete_group(group_id)


def list_group_members(admin_api_key: str, group_id: str, limit: int = 100) -> dict:
    return AdminApiClient(admin_api_key).list_group_members(group_id, limit=limit)


def add_group_member(admin_api_key: str, group_id: str, user_id: str) -> dict:
    """The user must already be an organization member (404 otherwise).
    To assign groups to someone who hasn't joined yet, invite them with
    create_invite()'s rbac_group_ids instead."""
    return AdminApiClient(admin_api_key).add_group_member(group_id, user_id)


def remove_group_member(admin_api_key: str, group_id: str, user_id: str) -> dict:
    return AdminApiClient(admin_api_key).remove_group_member(group_id, user_id)


def list_roles(admin_api_key: str, limit: int = 20) -> dict:
    """Custom roles are read-only through the API — created/edited in
    claude.ai organization settings, not here."""
    return AdminApiClient(admin_api_key).list_roles(limit=limit)


def list_role_permissions(admin_api_key: str, role_id: str, limit: int = 20) -> dict:
    return AdminApiClient(admin_api_key).list_role_permissions(role_id, limit=limit)
