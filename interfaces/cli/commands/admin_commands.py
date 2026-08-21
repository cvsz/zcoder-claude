"""
interfaces/cli/commands/admin_commands.py — CLI presentation for the Admin API
AI Model Coder CLI v1.44.0 (Clean Architecture refactor, Phase A)

Presentation layer only: every cmd_* function formats and print()s output.
All actual HTTP calls now go through application/admin_service.py (not
the gateway directly — closed in Phase A, exec-planing.md).
"""


import application.admin_service as svc
from infrastructure.anthropic_api.admin_gateway import CE_USER_MANAGEMENT_BETA


def _default_date_range() -> tuple:
    return svc._default_date_range()


def cmd_usage_report(
    admin_api_key: str, start: str | None = None, end: str | None = None, group_by: str = "model"
):
    data = svc.get_usage_report(admin_api_key, start=start, end=end, group_by=group_by)
    if "error" in data:
        print(f"\033[91m✗ Usage report failed: {data['error']}\033[0m")
        if data.get("status") in (401, 403):
            print(
                "\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
                "not a regular API key.\033[0m"
            )
        return None

    default_start, default_end = svc._default_date_range()
    start = start or default_start
    end = end or default_end
    print(f"\n\033[94mUsage report — {start} to {end} (grouped by {group_by})\033[0m\n")
    rows = data.get("data", data.get("results", []))
    if not rows:
        print("  (no usage data returned for this range)")
    for row in rows:
        label = row.get(group_by, row.get("model", "?"))
        input_tok = row.get("input_tokens", row.get("uncached_input_tokens", "?"))
        output_tok = row.get("output_tokens", "?")
        print(f"  {label:<28} in={input_tok:<12} out={output_tok}")
    print()
    return data


def cmd_cost_report(
    admin_api_key: str, start: str | None = None, end: str | None = None, group_by: str = "model"
):
    """--cost-report: actual billed spend (cost_report), distinct from
    the token-count-based --usage-report above."""
    data = svc.get_cost_report(admin_api_key, start=start, end=end, group_by=group_by)
    if "error" in data:
        print(f"\033[91m✗ Cost report failed: {data['error']}\033[0m")
        if data.get("status") in (401, 403):
            print(
                "\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
                "not a regular API key.\033[0m"
            )
        return None

    default_start, default_end = svc._default_date_range()
    start = start or default_start
    end = end or default_end
    print(f"\n\033[94mCost report — {start} to {end} (grouped by {group_by})\033[0m\n")
    rows = data.get("data", data.get("results", []))
    if not rows:
        print("  (no cost data returned for this range)")
    for row in rows:
        label = row.get(group_by, row.get("model", "?"))
        amount = row.get("amount", row.get("cost", "?"))
        currency = row.get("currency", "usd")
        print(f"  {label:<28} {amount} {currency}")
    print()
    return data


def cmd_cmek_list(admin_api_key: str, workspace_id: str | None = None):
    """--cmek-list: list registered CMEK external keys.

    ⚠️ See the "CMEK external_keys" section of AdminApiClient — the
    exact endpoint shape used here is a best-effort guess pending
    confirmation against the live API reference, not a verified client.
    """
    data = svc.list_cmek_keys(admin_api_key, workspace_id=workspace_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to list CMEK keys: {data['error']}\033[0m")
        if data.get("status") in (401, 403):
            print(
                "\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
                "not a regular API key.\033[0m"
            )
        return None

    print(
        "\n\033[94mCMEK external keys\033[0m  "
        "\033[93m(unverified endpoint shape — see docs/37_upgrade_v1.25.0_audit_and_impl.md)\033[0m\n"
    )
    for k in data.get("data", []):
        print(
            f"  {k.get('id', '?')}  workspace={k.get('workspace_id', '?')}  "
            f"provider={k.get('provider', '?')}  status={k.get('status', '?')}"
        )
    print()
    return data


def cmd_claude_code_usage_report(admin_api_key: str, starting_at: str, limit: int = 20):
    """--claude-code-usage-report: daily, per-user Claude Code productivity
    metrics (sessions, lines of code, commits/PRs, per-model cost) — a
    dedicated report distinct from the org-wide --usage-report/--cost-report
    above, though it shares the same Admin API key and client class."""
    data = svc.get_claude_code_usage_report(admin_api_key, starting_at, limit=limit)
    if "error" in data:
        print(f"\033[91m✗ Claude Code usage report failed: {data['error']}\033[0m")
        if data.get("status") in (401, 403):
            print(
                "\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
                "not a regular API key.\033[0m"
            )
        return None

    print(f"\n\033[94mClaude Code usage report — {starting_at}\033[0m\n")
    rows = data.get("data", [])
    if not rows:
        print("  (no Claude Code activity for this date)")
    for row in rows:
        actor = row.get("user_actor") or row.get("api_actor") or {}
        actor_label = actor.get("email_address") or actor.get("api_key_name") or "?"
        core = row.get("core_metrics", {})
        num_sessions = core.get("num_sessions", "?")
        loc = core.get("lines_of_code", {})
        added = loc.get("added", "?")
        removed = loc.get("removed", "?")
        commits = core.get("commits_by_claude_code", "?")
        prs = core.get("pull_requests_by_claude_code", "?")
        cost_total = sum(
            mb.get("estimated_cost", {}).get("amount", 0) for mb in row.get("model_breakdown", []) or []
        )
        print(
            f"  {actor_label:<32} sessions={num_sessions:<4} "
            f"+{added}/-{removed}  commits={commits}  prs={prs}  "
            f"cost={cost_total}"
        )
    print()
    return data


def cmd_admin_list_keys(admin_api_key: str, limit: int = 20):
    data = svc.list_api_keys(admin_api_key, limit=limit)
    if "error" in data:
        print(f"\033[91m✗ Failed to list API keys: {data['error']}\033[0m")
        if data.get("status") in (401, 403):
            print(
                "\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
                "not a regular API key.\033[0m"
            )
        return None

    print("\n\033[94mOrganization API keys\033[0m\n")
    for key in data.get("data", []):
        expires_at = key.get("expires_at") or "never"
        print(
            f"  {key.get('id', '?')}  {key.get('name', '')}  "
            f"status={key.get('status', '?')}  expires={expires_at}"
        )
    print()
    return data


def cmd_admin_revoke_key(admin_api_key: str, key_id: str):
    data = svc.revoke_api_key(admin_api_key, key_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to revoke key {key_id}: {data['error']}\033[0m")
        return None
    print(f"\033[92m✓ Key {key_id} set to inactive\033[0m")
    return data


def cmd_admin_create_key(name: str):
    """--admin-create-key deliberately does not call an API — there is no
    documented create-key endpoint. Anthropic API keys are generated
    through the Console UI, where the secret is displayed exactly once;
    creating them programmatically isn't supported, almost certainly so a
    raw secret is never returned to a script that could log or leak it.
    This prints that explanation instead of silently failing or faking
    a response. No application-layer function for this one — there's no
    HTTP call to make, so there's nothing to centralize."""
    print(
        f"\033[93mℹ Can't create API key {name!r} via the Admin API — there is no "
        "documented create-key endpoint.\033[0m"
    )
    print(
        "  API keys are generated through the Console UI (a secret is shown once, "
        "on purpose). Use --admin-list-keys / --admin-revoke-key for the parts of "
        "key management that are actually supported programmatically."
    )
    return None


def _wrong_key_hint(data: dict, extra: str = ""):
    if data.get("status") in (401, 403):
        print(
            f"\033[93m  This endpoint requires an Admin API key (sk-ant-admin...), "
            f"not a regular API key.{' ' + extra if extra else ''}\033[0m"
        )


# ── Spend Limits API (v1.23.0, Claude Enterprise only) ──────────────────


def cmd_spend_limits_list(admin_api_key: str, limit: int = 50):
    data = svc.list_effective_spend_limits(admin_api_key, limit=limit)
    if "error" in data:
        print(f"\033[91m✗ Failed to list spend limits: {data['error']}\033[0m")
        _wrong_key_hint(data, "This API also requires a Claude Enterprise organization.")
        return None

    print("\n\033[94mEffective spend limits\033[0m\n")
    for row in data.get("data", []):
        user = row.get("user_id", "?")
        amount = row.get("amount", "?")
        source = row.get("source", "?")
        spent = row.get("period_to_date_spend", "?")
        print(f"  {user:<28} limit={amount:<12} source={source:<12} spent={spent}")
    print()
    return data


def cmd_spend_limit_set(user_id: str, amount: str, admin_api_key: str, suppress_notification: bool = False):
    data = svc.set_spend_limit(admin_api_key, user_id, amount, suppress_notification=suppress_notification)
    if "error" in data:
        print(f"\033[91m✗ Failed to set spend limit: {data['error']}\033[0m")
        _wrong_key_hint(data)
        return None
    print(f"\033[92m✓ spend limit set\033[0m  user_id={user_id}  amount={amount}")
    return data


def cmd_spend_limit_get(spend_limit_id: str, admin_api_key: str):
    data = svc.get_spend_limit(admin_api_key, spend_limit_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to get spend limit {spend_limit_id}: {data['error']}\033[0m")
        return None
    print(f"  {data}")
    return data


def cmd_spend_limit_delete(spend_limit_id: str, admin_api_key: str):
    data = svc.delete_spend_limit(admin_api_key, spend_limit_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to delete spend limit {spend_limit_id}: {data['error']}\033[0m")
        return None
    print(f"\033[92m✓ spend limit {spend_limit_id} deleted\033[0m")
    return data


def cmd_spend_limit_requests_list(admin_api_key: str, status: str | None = None):
    data = svc.list_spend_limit_increase_requests(admin_api_key, status=status)
    if "error" in data:
        print(f"\033[91m✗ Failed to list spend limit increase requests: {data['error']}\033[0m")
        _wrong_key_hint(data, "This API also requires a Claude Enterprise organization.")
        return None

    print("\n\033[94mSpend limit increase requests\033[0m\n")
    for row in data.get("data", []):
        print(
            f"  {row.get('id', '?')}  user={row.get('actor', {}).get('user_id', '?')}  "
            f"status={row.get('status', '?')}  requested={row.get('requested_amount', '?')}"
        )
    print()
    return data


def cmd_spend_limit_request_approve(request_id: str, admin_api_key: str):
    data = svc.approve_spend_limit_increase_request(admin_api_key, request_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to approve request {request_id}: {data['error']}\033[0m")
        return None
    print(f"\033[92m✓ request {request_id} approved\033[0m")
    return data


def cmd_spend_limit_request_deny(request_id: str, admin_api_key: str):
    data = svc.deny_spend_limit_increase_request(admin_api_key, request_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to deny request {request_id}: {data['error']}\033[0m")
        return None
    print(f"\033[92m✓ request {request_id} denied\033[0m")
    return data


# ── Rate Limits API (v1.23.0, read-only) ─────────────────────────────────


def cmd_rate_limits(admin_api_key: str, model: str | None = None):
    data = svc.get_org_rate_limits(admin_api_key, model=model)
    if "error" in data:
        print(f"\033[91m✗ Failed to get rate limits: {data['error']}\033[0m")
        _wrong_key_hint(data)
        return None

    print("\n\033[94mOrganization rate limits\033[0m" + (f" (model={model})" if model else "") + "\n")
    for group in data.get("data", data.get("rate_limits", [])):
        label = group.get("model_group", group.get("name", "?"))
        print(f"  {label}")
        for limiter in group.get("limits", []):
            print(f"    {limiter.get('type', '?'):<24} {limiter.get('value', '?')}")
    print()
    return data


def cmd_rate_limits_workspace(workspace_id: str, admin_api_key: str):
    data = svc.get_workspace_rate_limits(admin_api_key, workspace_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to get rate limits for workspace {workspace_id}: " f"{data['error']}\033[0m")
        _wrong_key_hint(data)
        return None

    print(f"\n\033[94mWorkspace rate limit overrides — {workspace_id}\033[0m\n")
    groups = data.get("data", data.get("rate_limits", []))
    if not groups:
        print("  (no overrides — this workspace inherits every organization limit)")
    for group in groups:
        label = group.get("model_group", group.get("name", "?"))
        print(f"  {label}")
        for limiter in group.get("limits", []):
            print(
                f"    {limiter.get('type', '?'):<24} "
                f"value={limiter.get('value', '?'):<12} org_limit={limiter.get('org_limit', '?')}"
            )
    print()
    return data


# ── Claude Enterprise User Management API (v1.38.0, beta) ───────────────

_CE_HINT = "This API also requires a Claude Enterprise (claude.ai) organization."


def cmd_members_list(admin_api_key: str, limit: int = 20, email: str | None = None):
    data = svc.list_members(admin_api_key, limit=limit, email=email)
    if "error" in data:
        print(f"\033[91m✗ Failed to list members: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None

    print("\n\033[94mOrganization members\033[0m\n")
    rows = data.get("data", [])
    if not rows:
        print("  (no members found" + (f" matching {email}" if email else "") + ")")
    for m in rows:
        print(
            f"  {m.get('id', '?'):<28} {m.get('email', '?'):<32} "
            f"role={m.get('role', '?'):<16} added={m.get('added_at', '?')}"
        )
    if data.get("has_more"):
        print(f"  ... more available, last_id={data.get('last_id', '?')}")
    print()
    return data


def cmd_member_get(user_id: str, admin_api_key: str):
    data = svc.get_member(admin_api_key, user_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to get member {user_id}: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print(f"\n\033[94mMember {user_id}\033[0m")
    print(f"  email: {data.get('email', '?')}")
    print(f"  name:  {data.get('name', '?')}")
    print(f"  role:  {data.get('role', '?')}")
    print(f"  added: {data.get('added_at', '?')}\n")
    return data


def cmd_member_role_set(user_id: str, role: str, admin_api_key: str):
    """role must be "user" or "managed" — the API 400s on anything else,
    including the administrative roles, which can only be assigned in
    claude.ai organization settings."""
    data = svc.update_member_role(admin_api_key, user_id, role)
    if "error" in data:
        print(f"\033[91m✗ Failed to update role for {user_id}: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print(f"\033[92m✓ {user_id} role set to {data.get('role', role)}\033[0m")
    return data


def cmd_member_remove(user_id: str, admin_api_key: str):
    data = svc.remove_member(admin_api_key, user_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to remove member {user_id}: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print(f"\033[92m✓ Removed member {user_id}\033[0m (seat, if any, returned to the pool)")
    return data


def cmd_invite_create(email: str, role: str, admin_api_key: str, rbac_group_ids: list | None = None):
    data = svc.create_invite(admin_api_key, email, role, rbac_group_ids=rbac_group_ids)
    if "error" in data:
        print(f"\033[91m✗ Failed to invite {email}: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print(
        f"\033[92m✓ Invited {email} as {data.get('role', role)}\033[0m "
        f"(id={data.get('id', '?')}, expires={data.get('expires_at', '?')})"
    )
    return data


def cmd_invites_list(admin_api_key: str, limit: int = 20):
    data = svc.list_invites(admin_api_key, limit=limit)
    if "error" in data:
        print(f"\033[91m✗ Failed to list invites: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print("\n\033[94mOrganization invites\033[0m\n")
    rows = data.get("data", [])
    if not rows:
        print("  (no invites found)")
    for inv in rows:
        print(
            f"  {inv.get('id', '?'):<28} {inv.get('email', '?'):<32} "
            f"role={inv.get('role', '?'):<10} status={inv.get('status', '?')}"
        )
    print()
    return data


def cmd_invite_withdraw(invite_id: str, admin_api_key: str):
    """Only a pending invite can be withdrawn — accepted/expired both
    400 server-side."""
    data = svc.withdraw_invite(admin_api_key, invite_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to withdraw invite {invite_id}: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print(f"\033[92m✓ Withdrew invite {invite_id}\033[0m")
    return data


def cmd_groups_list(admin_api_key: str, limit: int = 20):
    data = svc.list_groups(admin_api_key, limit=limit)
    if "error" in data:
        print(f"\033[91m✗ Failed to list groups: {data['error']}\033[0m")
        if data.get("status") == 404:
            print(
                f"\033[93m  A 404 here usually means the {CE_USER_MANAGEMENT_BETA} beta "
                f"header wasn't accepted — confirm this is a Claude Enterprise "
                f"organization.\033[0m"
            )
        else:
            _wrong_key_hint(data, _CE_HINT)
        return None
    print("\n\033[94mEnterprise groups\033[0m\n")
    rows = data.get("data", [])
    if not rows:
        print("  (no groups found)")
    for g in rows:
        print(
            f"  {g.get('id', '?'):<32} {g.get('name', '?'):<24} "
            f"source={g.get('source_type', '?'):<8} roles={len(g.get('roles') or [])}"
        )
    print()
    return data


def cmd_group_create(name: str, admin_api_key: str):
    data = svc.create_group(admin_api_key, name)
    if "error" in data:
        print(f"\033[91m✗ Failed to create group {name!r}: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print(f"\033[92m✓ Created group {data.get('name', name)}\033[0m (id={data.get('id', '?')})")
    return data


def cmd_group_delete(group_id: str, admin_api_key: str):
    """Members keep organization membership; they just lose the
    permissions this group's attached roles granted. SCIM-provisioned
    groups can't be deleted through the API — the request returns 400."""
    data = svc.delete_group(admin_api_key, group_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to delete group {group_id}: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print(f"\033[92m✓ Deleted group {group_id}\033[0m")
    return data


def cmd_group_members_list(group_id: str, admin_api_key: str, limit: int = 100):
    data = svc.list_group_members(admin_api_key, group_id, limit=limit)
    if "error" in data:
        print(f"\033[91m✗ Failed to list members of group {group_id}: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print(f"\n\033[94mGroup {group_id} — members\033[0m\n")
    rows = data.get("data", [])
    if not rows:
        print("  (no members in this group)")
    for m in rows:
        print(f"  {m.get('user_id', '?'):<28} {m.get('email', '?')}")
    print()
    return data


def cmd_group_member_add(group_id: str, user_id: str, admin_api_key: str):
    """The user must already be an organization member (404 otherwise).
    To assign groups to someone who hasn't joined yet, invite them with
    --invite-create's rbac_group_ids instead."""
    data = svc.add_group_member(admin_api_key, group_id, user_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to add {user_id} to group {group_id}: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print(f"\033[92m✓ Added {data.get('email', user_id)} to group {group_id}\033[0m")
    return data


def cmd_group_member_remove(group_id: str, user_id: str, admin_api_key: str):
    data = svc.remove_group_member(admin_api_key, group_id, user_id)
    if "error" in data:
        print(f"\033[91m✗ Failed to remove {user_id} from group {group_id}: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print(f"\033[92m✓ Removed {user_id} from group {group_id}\033[0m")
    return data


def cmd_roles_list(admin_api_key: str, limit: int = 20):
    """Custom roles are read-only through the API — created/edited in
    claude.ai organization settings, not here."""
    data = svc.list_roles(admin_api_key, limit=limit)
    if "error" in data:
        print(f"\033[91m✗ Failed to list roles: {data['error']}\033[0m")
        if data.get("status") == 404:
            print(
                f"\033[93m  A 404 here usually means the {CE_USER_MANAGEMENT_BETA} beta "
                f"header wasn't accepted — confirm this is a Claude Enterprise "
                f"organization.\033[0m"
            )
        else:
            _wrong_key_hint(data, _CE_HINT)
        return None
    print("\n\033[94mCustom roles\033[0m\n")
    rows = data.get("data", [])
    if not rows:
        print("  (no custom roles found)")
    for r in rows:
        print(f"  {r.get('id', '?'):<32} {r.get('name', '?')}")
    print()
    return data


def cmd_role_permissions_list(role_id: str, admin_api_key: str, limit: int = 20):
    data = svc.list_role_permissions(admin_api_key, role_id, limit=limit)
    if "error" in data:
        print(f"\033[91m✗ Failed to list permissions for role {role_id}: {data['error']}\033[0m")
        _wrong_key_hint(data, _CE_HINT)
        return None
    print(f"\n\033[94mRole {role_id} — permissions\033[0m\n")
    rows = data.get("data", [])
    if not rows:
        print("  (no permissions found — role may only grant features not enabled " "for this organization)")
    for p in rows:
        resource = p.get("resource", {})
        r_type = resource.get("type", "?")
        r_detail = (
            resource.get("connector_id") or resource.get("tool_name") or resource.get("organization_id") or ""
        )
        print(f"  {r_type:<16} {r_detail:<28} action={p.get('action', '?')}")
    print()
    return data
