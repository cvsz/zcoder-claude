"""
claude_admin_api.py — Admin API: Usage & Cost, API keys, Spend Limits, Rate Limits, Claude Code Analytics, User Management
AI Model Coder CLI v1.38.0

Thin Admin API wrappers, combined into one module since all require the
same auth (an Admin API key, prefix sk-ant-admin..., created in the
Console — this is a different key type than the regular API key used
everywhere else in this CLI, and these calls will 401 with a normal key).

  1. Usage and Cost API — org-level historical spend/usage reporting.
     `claude_cost_optimizer.py` only ever *estimates* cost locally from
     token counts it's told about after the fact; it never calls a real
     usage/cost endpoint. This module is that missing live-data path —
     see claude_cost_optimizer.py's docstring for the cross-link the other
     direction.

  2. API key management — list/update organization API keys. Anthropic
     does not document a create-key endpoint: keys are created through
     the Console UI, where the secret is displayed exactly once, and
     that's intentional (creating a raw secret programmatically would be
     an exfiltration/security risk). So this module implements list,
     get, and update (e.g. changing status to revoke a key) — not create.
     `--admin-create-key` is deliberately not implemented; see
     cmd_admin_create_key() below for why, rather than silently no-op-ing.

  3. Spend Limits API (v1.23.0) — per-member spend governance. Claude
     Enterprise only; a Claude Console/API-only org gets a 403 from
     these endpoints. Eight endpoints across two resources: spend limits
     (list effective limits org-wide, set/get/delete a per-user
     override) and spend limit increase requests (list the queue,
     approve/deny a pending request). Requires an Admin API key with the
     read:spend_limits / write:spend_limits scopes.

  4. Rate Limits API (v1.23.0) — read-only. Two endpoints: the org's
     configured limits (grouped by model family, batches, files, skills,
     web search), and a workspace's overrides (each paired with the
     inherited org_limit). This is a different concern from
     resilience.py's client-side 429 backoff: that module *reacts* to
     being rate-limited; this one *reads what the configured limits
     are* before you ever hit them.

  5. Claude Enterprise User Management API (v1.38.0, beta) — Members,
     Invites, Groups, and read-only Custom Roles for a Claude Enterprise
     (claude.ai) organization. Member/invite endpoints are the same
     /organizations/{users,invites} paths section 2's API-key-management
     already uses for Claude Console orgs — no beta header needed there.
     Groups (/rbac_groups) and Custom Roles (/rbac_roles) are Enterprise-
     only and require the ce-user-management-2026-07-13 beta header;
     omitting it 404s rather than degrading. The API can only assign the
     "user"/"managed" roles — owner/membership_admin/primary_owner stay
     Console-managed, same as key creation in section 2 being N/A by
     design. Requires an Admin API key with read:members / write:members
     (members, invites) or read:rbac_groups / write:rbac_groups (groups);
     custom-role reads use read:members too.

CLI flags:
  --usage-report                 Print a usage report table (token counts)
  --usage-report-start DATE       Start date (YYYY-MM-DD), default: 30 days ago
  --usage-report-end DATE         End date (YYYY-MM-DD), default: today
  --usage-report-group-by FIELD   Group by field, e.g. model, api_key_id (default: model)
  --cost-report                   Print a cost report table (billed spend, not token counts)
  --cost-report-start DATE        Start date (YYYY-MM-DD), default: 30 days ago
  --cost-report-end DATE          End date (YYYY-MM-DD), default: today
  --cost-report-group-by FIELD    Group by field, e.g. model, api_key_id (default: model)
  --admin-list-keys               List organization API keys
  --admin-revoke-key ID           Revoke (set status=inactive) an API key by ID
  --admin-create-key NAME         Explains why this isn't supported (Console-only)
  --spend-limits-list             List every member's resolved effective spend limit
  --spend-limit-set USER_ID AMOUNT  Set a per-user spend limit override (decimal string, minor units)
  --spend-limit-get ID            Get one spend limit override by id
  --spend-limit-delete ID         Delete a per-user spend limit override
  --spend-limit-requests-list     List spend limit increase requests
  --spend-limit-status STATUS     Filter --spend-limit-requests-list by status (pending/approved/denied)
  --spend-limit-request-approve ID  Approve a pending increase request
  --spend-limit-request-deny ID   Deny a pending increase request
  --rate-limits                   Print the organization's configured rate limits
  --rate-limits-model MODEL       Filter --rate-limits to one model's group
  --rate-limits-workspace ID      Print one workspace's rate limit overrides (with inherited org_limit)
  --claude-code-usage-report      Print daily per-user Claude Code productivity metrics (v1.24.0)
  --claude-code-usage-report-start DATE  Date (YYYY-MM-DD) for --claude-code-usage-report, default: yesterday
  --members-list [--members-email E]     List/lookup organization members (Claude Enterprise)
  --member-get USER_ID                   Get one member by ID
  --member-role-set USER_ID ROLE         Set a member's role (user/managed)
  --member-remove USER_ID                Remove a member
  --invite-create EMAIL ROLE [--invite-rbac-groups G1,G2]  Invite someone (role: user/managed)
  --invites-list                         List organization invites
  --invite-withdraw INVITE_ID            Withdraw a pending invite
  --groups-list                          List the enterprise's groups (beta header)
  --group-create NAME                    Create a group
  --group-delete GROUP_ID                Delete a group
  --group-members-list GROUP_ID          List a group's members
  --group-member-add GROUP_ID USER_ID    Add an org member to a group
  --group-member-remove GROUP_ID USER_ID Remove a member from a group
  --roles-list                           List custom roles (read-only)
  --role-permissions-list ROLE_ID        List one custom role's permissions
"""

import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional

ADMIN_BASE = "https://api.anthropic.com/v1/organizations"

# Claude Enterprise (claude.ai) User Management API (v1.38.0) — beta for all
# Claude Enterprise organizations. Per platform.claude.com/docs/en/manage-claude/
# user-management (checked 2026-07-27): member and invite endpoints are the
# *same* /v1/organizations/{users,invites} endpoints Claude Console orgs use
# (no beta header needed there — this file's existing API-key-management
# section above is exactly this for Console orgs). Group and custom-role
# endpoints (/rbac_groups, /rbac_roles) are Claude-Enterprise-only and require
# this beta header; omitting it on those returns 404, not a degraded response.
# Confirmed genuinely absent from this codebase before this cycle: grepped for
# "ce-user-management|rbac_group|rbac_role|list_members" — zero matches.
CE_USER_MANAGEMENT_BETA = "ce-user-management-2026-07-13"


class AdminApiError(Exception):
    pass


class AdminApiClient:
    """Thin client for the Admin API, following the same _post()/_get()
    pattern used throughout this project's claude_*.py modules.

    admin_api_key must be an Admin API key (sk-ant-admin...), not a
    regular API key — regular keys don't have access to this endpoint
    family and will get a 401/403.
    """

    def __init__(self, admin_api_key: str):
        self.admin_api_key = admin_api_key

    def _headers(self, beta: Optional[str] = None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.admin_api_key,
            "anthropic-version": "2023-06-01",
        }
        if beta:
            headers["anthropic-beta"] = beta
        return headers

    def _get(self, path: str, params: Optional[dict] = None, beta: Optional[str] = None) -> dict:
        url = f"{ADMIN_BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}, doseq=True,
            )
        req = urllib.request.Request(url, headers=self._headers(beta=beta), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": e.read().decode(), "status": e.code}
        except Exception as e:
            return {"error": str(e)}

    def _post(self, path: str, payload: dict, beta: Optional[str] = None) -> dict:
        req = urllib.request.Request(
            f"{ADMIN_BASE}{path}", data=json.dumps(payload).encode(),
            headers=self._headers(beta=beta), method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": e.read().decode(), "status": e.code}
        except Exception as e:
            return {"error": str(e)}

    def _delete(self, path: str, beta: Optional[str] = None) -> dict:
        req = urllib.request.Request(f"{ADMIN_BASE}{path}", headers=self._headers(beta=beta), method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode()
                return json.loads(body) if body else {"deleted": True}
        except urllib.error.HTTPError as e:
            return {"error": e.read().decode(), "status": e.code}
        except Exception as e:
            return {"error": str(e)}

    # ── Usage and Cost API ──────────────────────────────────────────────

    def get_usage_report(self, start: str, end: str, group_by: str = "model") -> dict:
        """Wraps the usage_report endpoint. start/end are YYYY-MM-DD."""
        return self._get("/usage_report", params={
            "starting_at": start, "ending_at": end, "group_by": group_by,
        })

    def get_cost_report(self, start: str, end: str, group_by: str = "model") -> dict:
        """Wraps the cost_report endpoint — actual billed spend, distinct
        from the token-count usage_report above."""
        return self._get("/cost_report", params={
            "starting_at": start, "ending_at": end, "group_by": group_by,
        })

    # ── CMEK external_keys (v1.25.0 — see note below) ─────────────────────
    #
    # ⚠️ Confirmation needed: the docs confirm "external_keys API
    # endpoints" exist and are Admin-API-scoped on Claude Platform
    # (explicitly called out as *unavailable* on Claude Platform on AWS),
    # but this session could not find or safely fetch the endpoint's
    # exact path, request body, or response schema. The path segment
    # below (/organizations/external_keys) is a best-effort guess by
    # analogy with every other resource in this file living under
    # /organizations/..., NOT a confirmed one. Verify against the live
    # API reference before using this against a production organization
    # — CMEK misconfiguration risk is asymmetric (see the "Revoking or
    # disabling the key makes all CMEK-protected data in that workspace
    # permanently inaccessible, with no backout path" warning in the
    # product docs), so treat these methods as a starting point to
    # correct, not a verified client.
    def create_external_key(self, workspace_id: str, provider: str, key_arn_or_id: str) -> dict:
        """Register a customer-managed encryption key (CMEK) for a
        workspace. `provider` is one of "aws_kms", "gcp_kms", or
        "azure_key_vault" per the product docs (Google Cloud KMS and
        Azure Key Vault are not available on Claude Platform on AWS —
        AWS KMS only there). Attaching a key to a workspace is
        irreversible: it cannot later be detached or swapped, and the
        workspace's data-retention setting locks in place."""
        return self._post("/external_keys", {
            "workspace_id": workspace_id, "provider": provider,
            "key_arn_or_id": key_arn_or_id,
        })

    def validate_external_key(self, key_id: str) -> dict:
        """Validate a registered key's permissions/purpose/algorithm
        before attaching it — mirrors the Console's "validate" step."""
        return self._post(f"/external_keys/{key_id}/validate", {})

    def attach_external_key(self, key_id: str, workspace_id: str) -> dict:
        """Attach a validated key to a workspace. Irreversible per the
        product docs: once attached, a key cannot be detached or
        swapped, and returning to zero data retention requires creating
        a new workspace and moving traffic to it."""
        return self._post(f"/external_keys/{key_id}/attach", {"workspace_id": workspace_id})

    def list_external_keys(self, workspace_id: Optional[str] = None) -> dict:
        """List registered CMEK keys, optionally filtered to one
        workspace."""
        params = {"workspace_id": workspace_id} if workspace_id else None
        return self._get("/external_keys", params=params)

    # ── Claude Code Analytics API (v1.24.0) ──────────────────────────────

    def get_claude_code_usage_report(self, starting_at: str, limit: int = 20,
                                     page: Optional[str] = None) -> dict:
        """GET /organizations/usage_report/claude_code — one record per
        user per day: session counts, lines of code added/removed,
        commits/PRs created through Claude Code, per-editing-tool
        accept/reject counts, and a per-model token/cost breakdown. Same
        Admin API key as the org-wide Usage & Cost API above, but this is
        Claude-Code-specific and free to call regardless of plan.
        starting_at is required (YYYY-MM-DD); page is the cursor from a
        previous response's next_page for pagination."""
        return self._get("/usage_report/claude_code", params={
            "starting_at": starting_at, "limit": limit, "page": page,
        })

    # ── API key management ──────────────────────────────────────────────

    def list_api_keys(self, limit: int = 20) -> dict:
        return self._get("/api_keys", params={"limit": limit})

    def get_api_key(self, key_id: str) -> dict:
        return self._get(f"/api_keys/{key_id}")

    def update_api_key(self, key_id: str, status: Optional[str] = None,
                       name: Optional[str] = None) -> dict:
        """status: 'active' or 'inactive'. There is no documented delete
        endpoint either — revocation is done via status, not deletion."""
        payload = {}
        if status:
            payload["status"] = status
        if name:
            payload["name"] = name
        return self._post(f"/api_keys/{key_id}", payload)

    def revoke_api_key(self, key_id: str) -> dict:
        return self.update_api_key(key_id, status="inactive")

    # ── Spend Limits API (v1.23.0, Claude Enterprise only) ───────────────

    def list_effective_spend_limits(self, limit: int = 50, page: Optional[str] = None) -> dict:
        """Every current member with their resolved effective spend limit,
        where it's inherited from (source), and their period-to-date
        spend. GET /spend_limits/effective."""
        return self._get("/spend_limits/effective", params={"limit": limit, "page": page})

    def set_spend_limit(self, user_id: str, amount: str,
                        suppress_notification: bool = False) -> dict:
        """Set a per-user spend limit override. `amount` is a decimal
        string in minor units (cents), per the API's convention.
        `suppress_notification` is only sent when True (omitted
        otherwise) — by default Anthropic emails the member."""
        payload = {"user_id": user_id, "amount": amount}
        if suppress_notification:
            payload["suppress_notification"] = True
        return self._post("/spend_limits", payload)

    def get_spend_limit(self, spend_limit_id: str) -> dict:
        return self._get(f"/spend_limits/{spend_limit_id}")

    def delete_spend_limit(self, spend_limit_id: str) -> dict:
        """Deletes a per-user override. Seat-tier, group, and
        organization-level rows cannot be deleted through this
        endpoint — only per-user overrides."""
        return self._delete(f"/spend_limits/{spend_limit_id}")

    def list_spend_limit_increase_requests(self, status: Optional[list] = None,
                                           actor_ids: Optional[list] = None,
                                           limit: int = 50,
                                           page: Optional[str] = None) -> dict:
        """List spend limit increase requests, most recent first. `status`
        filters by one or more of pending/approved/denied; `actor_ids`
        filters to specific requesters."""
        params = {"limit": limit, "page": page}
        if status:
            params["status[]"] = status
        if actor_ids:
            params["actor_ids[]"] = actor_ids
        return self._get("/spend_limit_increase_requests", params=params)

    def get_spend_limit_increase_request(self, request_id: str) -> dict:
        return self._get(f"/spend_limit_increase_requests/{request_id}")

    def approve_spend_limit_increase_request(self, request_id: str,
                                             suppress_notification: bool = False) -> dict:
        """Approving writes the same per-user spend limit row that
        set_spend_limit() writes — this resolves the pending request AND
        sets the override in one call."""
        payload = {}
        if suppress_notification:
            payload["suppress_notification"] = True
        return self._post(f"/spend_limit_increase_requests/{request_id}/approve", payload)

    def deny_spend_limit_increase_request(self, request_id: str,
                                          suppress_notification: bool = False) -> dict:
        payload = {}
        if suppress_notification:
            payload["suppress_notification"] = True
        return self._post(f"/spend_limit_increase_requests/{request_id}/deny", payload)

    # ── Rate Limits API (v1.23.0, read-only) ─────────────────────────────

    def get_org_rate_limits(self, model: Optional[str] = None) -> dict:
        """The organization's configured rate limits, grouped by model
        family/batches/files/skills/web-search. `model`, when given,
        filters to the single group that model string belongs to (404 if
        it doesn't match any group) — omitted by default, returning every
        group."""
        params = {"model": model} if model else None
        return self._get("/rate_limits", params=params)

    def get_workspace_rate_limits(self, workspace_id: str) -> dict:
        """A single workspace's rate limit *overrides* only — anything
        missing is inherited from the organization, not unlimited. Each
        present limiter is paired with the organization's value
        (org_limit) for the same limiter."""
        return self._get(f"/workspaces/{workspace_id}/rate_limits")

    # ── Claude Enterprise User Management API (v1.38.0, beta) ────────────
    #
    # Members and invites take no beta header (same endpoints Console orgs
    # already use above). Groups and custom roles require
    # CE_USER_MANAGEMENT_BETA and exist only for Claude Enterprise. The API
    # can only assign the "user"/"managed" roles — owner/membership_admin/
    # primary_owner are Console-managed and out of scope by design, same as
    # --admin-create-key above being N/A by design.

    def list_members(self, limit: int = 20, email: Optional[str] = None,
                     before_id: Optional[str] = None, after_id: Optional[str] = None) -> dict:
        """GET /organizations/users. `email` filters to one member
        (case-insensitive, tolerates common address variants per the
        docs) instead of paging the whole roster."""
        return self._get("/users", params={
            "limit": limit, "email": email, "before_id": before_id, "after_id": after_id,
        })

    def get_member(self, user_id: str) -> dict:
        return self._get(f"/users/{user_id}")

    def update_member_role(self, user_id: str, role: str) -> dict:
        """role must be "user" or "managed" — administrative roles
        (owner/membership_admin/primary_owner) 400 here by design, same
        restriction the docs describe for invite creation below."""
        return self._post(f"/users/{user_id}", {"role": role})

    def remove_member(self, user_id: str) -> dict:
        return self._delete(f"/users/{user_id}")

    def create_invite(self, email: str, role: str,
                      rbac_group_ids: Optional[list] = None) -> dict:
        """role must be "user" or "managed". `rbac_group_ids`, when
        given, additionally requires the caller's key to carry
        write:rbac_groups (group assignment can grant that group's
        role permissions) — the API enforces this, not this client."""
        payload = {"email": email, "role": role}
        if rbac_group_ids:
            payload["rbac_group_ids"] = rbac_group_ids
        return self._post("/invites", payload)

    def list_invites(self, limit: int = 20, before_id: Optional[str] = None,
                     after_id: Optional[str] = None) -> dict:
        """No status filter — the response mixes pending/accepted/expired;
        filter client-side on `status` if you only want one state."""
        return self._get("/invites", params={
            "limit": limit, "before_id": before_id, "after_id": after_id,
        })

    def get_invite(self, invite_id: str) -> dict:
        return self._get(f"/invites/{invite_id}")

    def withdraw_invite(self, invite_id: str) -> dict:
        """Only a pending invite can be withdrawn — accepted/expired
        both 400 per the docs; this client doesn't pre-check status,
        the API is the source of truth."""
        return self._delete(f"/invites/{invite_id}")

    def list_groups(self, limit: int = 20, page: Optional[str] = None) -> dict:
        return self._get("/rbac_groups", params={"limit": limit, "page": page},
                         beta=CE_USER_MANAGEMENT_BETA)

    def get_group(self, group_id: str) -> dict:
        return self._get(f"/rbac_groups/{group_id}", beta=CE_USER_MANAGEMENT_BETA)

    def create_group(self, name: str) -> dict:
        return self._post("/rbac_groups", {"name": name}, beta=CE_USER_MANAGEMENT_BETA)

    def rename_group(self, group_id: str, name: str) -> dict:
        """`name` is the only field this endpoint can change."""
        return self._post(f"/rbac_groups/{group_id}", {"name": name}, beta=CE_USER_MANAGEMENT_BETA)

    def delete_group(self, group_id: str) -> dict:
        """Members keep their organization membership; they just lose
        the permissions the group's attached roles granted."""
        return self._delete(f"/rbac_groups/{group_id}", beta=CE_USER_MANAGEMENT_BETA)

    def list_group_members(self, group_id: str, limit: int = 100,
                           page: Optional[str] = None) -> dict:
        return self._get(f"/rbac_groups/{group_id}/members", params={"limit": limit, "page": page},
                         beta=CE_USER_MANAGEMENT_BETA)

    def add_group_member(self, group_id: str, user_id: str) -> dict:
        """The user must already be an organization member (404
        otherwise). To assign groups to someone who hasn't joined yet,
        use rbac_group_ids on create_invite() instead."""
        return self._post(f"/rbac_groups/{group_id}/members", {"user_id": user_id},
                          beta=CE_USER_MANAGEMENT_BETA)

    def remove_group_member(self, group_id: str, user_id: str) -> dict:
        return self._delete(f"/rbac_groups/{group_id}/members/{user_id}", beta=CE_USER_MANAGEMENT_BETA)

    def list_roles(self, limit: int = 20, page: Optional[str] = None) -> dict:
        """Custom roles are read-only through the API — defined in
        claude.ai organization settings, not writable here."""
        return self._get("/rbac_roles", params={"limit": limit, "page": page},
                         beta=CE_USER_MANAGEMENT_BETA)

    def get_role(self, role_id: str) -> dict:
        return self._get(f"/rbac_roles/{role_id}", beta=CE_USER_MANAGEMENT_BETA)

    def list_role_permissions(self, role_id: str, limit: int = 20,
                              page: Optional[str] = None) -> dict:
        return self._get(f"/rbac_roles/{role_id}/permissions", params={"limit": limit, "page": page},
                         beta=CE_USER_MANAGEMENT_BETA)


# ── Clean Architecture refactor note (2026-08-14) ───────────────────────────
# This file used to also contain every cmd_* CLI/print() function. Those
# moved to interfaces/cli/commands/admin_commands.py so this module stays a
# pure infrastructure adapter and can be imported/tested without capturing
# stdout. claude_admin_api.py is now a compatibility shim re-exporting both.
