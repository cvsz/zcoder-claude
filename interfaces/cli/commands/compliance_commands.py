"""
interfaces/cli/commands/compliance_commands.py — CLI presentation for the Compliance API
AI Model Coder CLI v1.44.0 (Clean Architecture refactor, Phase A)

Presentation layer only: every cmd_* function formats and print()s output.
All actual HTTP calls now go through application/compliance_service.py
(not the gateway directly — closed in Phase A, exec-planing.md).
ComplianceApiError is still imported here since cmd_* functions catch it
directly (the service layer lets it propagate rather than swallowing it).
"""

from pathlib import Path

import application.compliance_service as svc
from infrastructure.anthropic_api.compliance_gateway import ComplianceApiError


def _print_error(prefix: str, e: ComplianceApiError):
    print(f"\033[91m✗ {prefix}: [{e.status}] {e.error_type}: {e.message}\033[0m")
    if e.status == 403:
        print(
            "\033[93m  Compliance Access Keys (sk-ant-api01-...) carry different scopes "
            "than Admin API keys (sk-ant-admin01-...); an Admin API key can only call "
            "the Activity Feed. See the message above for the scopes this call needed "
            "vs. what your key carries.\033[0m"
        )
    elif e.status == 401:
        print(
            "\033[93m  Confirm the key value and that it hasn't been revoked in "
            "claude.ai (Compliance Access Keys) or Claude Console (Admin API keys).\033[0m"
        )
    elif e.status == 429:
        print(
            "\033[93m  Rate limited even after automatic backoff — this org is doing "
            "600+ requests/min against the Compliance API. Slow down the polling "
            "interval.\033[0m"
        )
    if e.request_id:
        print(
            f"\033[90m  request-id: {e.request_id} (include this if escalating to Anthropic support)\033[0m"
        )


def cmd_compliance_activities(
    api_key: str,
    since: str | None = None,
    until: str | None = None,
    activity_types: list | None = None,
    limit: int = 100,
    all_pages: bool = False,
):
    print(
        "\n\033[94mActivity Feed\033[0m"
        + (" (all matching pages)" if all_pages else f" (up to {limit})")
        + "\n"
    )
    try:
        count = 0
        if all_pages:
            for activity in svc.iterate_all_activities(
                api_key,
                since=since,
                until=until,
                activity_types=activity_types,
                limit=limit,
            ):
                _print_activity(activity)
                count += 1
        else:
            page = svc.list_activities_page(
                api_key,
                since=since,
                until=until,
                activity_types=activity_types,
                limit=limit,
            )
            for activity in page.get("data", []):
                _print_activity(activity)
                count += 1
            if page.get("has_more"):
                print(
                    f"\033[90m  ... more available (pass --compliance-activities-all "
                    f"to page through everything, last_id={page.get('last_id')})\033[0m"
                )
    except ComplianceApiError as e:
        _print_error("Activity Feed request failed", e)
        return None
    print(f"\n\033[90m{count} activit{'y' if count == 1 else 'ies'} shown\033[0m\n")
    return count


def _print_activity(a: dict):
    actor = a.get("actor", {})
    who = (
        actor.get("email_address")
        or actor.get("api_key_id")
        or actor.get("admin_api_key_id")
        or actor.get("unauthenticated_email_address")
        or actor.get("type", "?")
    )
    print(f"  {a.get('created_at', '?'):<25} {a.get('type', '?'):<30} {who}")


def cmd_compliance_chats_list(api_key: str, user_ids: list, limit: int = 100):
    print(f"\n\033[94mChats for {len(user_ids)} user(s)\033[0m\n")
    try:
        page = svc.list_chats(api_key, user_ids, limit=limit)
    except (ComplianceApiError, ValueError) as e:
        if isinstance(e, ValueError):
            print(f"\033[91m✗ {e}\033[0m")
        else:
            _print_error("Chat list request failed", e)
        return None
    for chat in page.get("data", []):
        deleted = " (soft-deleted)" if chat.get("deleted_at") else ""
        print(f"  {chat.get('id')}  {chat.get('name', '(untitled)')}{deleted}")
    if page.get("has_more"):
        print(f"\033[90m  ... more available (last_id={page.get('last_id')})\033[0m")
    print()
    return page


def cmd_compliance_chat_messages(api_key: str, chat_id: str):
    try:
        data = svc.get_chat_messages(api_key, chat_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to fetch messages for chat {chat_id}", e)
        return None
    print(f"\n\033[94m{data.get('name', '(untitled)')}\033[0m  ({chat_id})\n")
    for msg in data.get("chat_messages", []) or []:
        text = "".join(b.get("text", "") for b in msg.get("content", []) if b.get("type") == "text")
        print(f"  [{msg.get('role', '?'):<9}] {text[:200]}")
        for f in msg.get("files") or []:
            print(f"      \033[90m📎 {f.get('filename')} ({f.get('id')})\033[0m")
        for f in msg.get("generated_files") or []:
            print(f"      \033[90m📄 generated: {f.get('filename')} ({f.get('id')})\033[0m")
        for a in msg.get("artifacts") or []:
            print(f"      \033[90m🧩 artifact: {a.get('title')} ({a.get('version_id')})\033[0m")
    print()
    return data


def cmd_compliance_chat_delete(api_key: str, chat_id: str, yes: bool = False):
    if not yes:
        print(
            f"\033[93m⚠ DRY RUN: would permanently delete chat {chat_id} and all its "
            f"messages/attached files. This cannot be undone. Re-run with "
            f"--compliance-yes to actually delete.\033[0m"
        )
        return None
    try:
        result = svc.delete_chat(api_key, chat_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to delete chat {chat_id}", e)
        return None
    print(f"\033[92m✓ Deleted chat {chat_id} ({result.get('type', '?')})\033[0m")
    return result


def cmd_compliance_file_download(api_key: str, file_id: str, output_path: str | None = None):
    try:
        content, filename, mime_type = svc.download_file(api_key, file_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to download file {file_id}", e)
        return None
    dest = Path(output_path or filename or file_id)
    dest.write_bytes(content)
    print(f"\033[92m✓ Saved {len(content)} bytes to {dest} ({mime_type or 'unknown MIME type'})\033[0m")
    return str(dest)


def cmd_compliance_file_delete(api_key: str, file_id: str, yes: bool = False):
    if not yes:
        print(
            f"\033[93m⚠ DRY RUN: would permanently delete file {file_id}. This cannot be "
            f"undone. Re-run with --compliance-yes to actually delete.\033[0m"
        )
        return None
    try:
        result = svc.delete_file(api_key, file_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to delete file {file_id}", e)
        return None
    print(f"\033[92m✓ Deleted file {file_id}\033[0m")
    return result


def cmd_compliance_projects_list(api_key: str, limit: int = 100):
    try:
        page = svc.list_projects(api_key, limit=limit)
    except ComplianceApiError as e:
        _print_error("Project list request failed", e)
        return None
    print("\n\033[94mProjects\033[0m\n")
    for p in page.get("data", []):
        print(f"  {p.get('id')}  {p.get('name', '(untitled)')}")
    if page.get("has_more"):
        print(f"\033[90m  ... more available (next_page={page.get('next_page')})\033[0m")
    print()
    return page


def cmd_compliance_project_info(api_key: str, project_id: str):
    try:
        data = svc.get_project(api_key, project_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to fetch project {project_id}", e)
        return None
    print(f"\n\033[94m{data.get('name', '(untitled)')}\033[0m  ({project_id})")
    for k, v in data.items():
        if k not in ("id", "name"):
            print(f"  {k}: {v}")
    print()
    return data


def cmd_compliance_project_attachments(api_key: str, project_id: str):
    try:
        page = svc.list_project_attachments(api_key, project_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to list attachments for project {project_id}", e)
        return None
    print(f"\n\033[94mAttachments for project {project_id}\033[0m\n")
    for a in page.get("data", []):
        kind = "📄 doc" if a.get("type") == "project_doc" else "📎 file"
        print(f"  {kind}  {a.get('id')}  {a.get('filename')}")
    if page.get("has_more"):
        print(f"\033[90m  ... more available (next_page={page.get('next_page')})\033[0m")
    print()
    return page


def cmd_compliance_project_delete(api_key: str, project_id: str, yes: bool = False):
    if not yes:
        print(
            f"\033[93m⚠ DRY RUN: would permanently delete project {project_id}. Fails if "
            f"chats are still attached (detach/delete them first). Re-run with "
            f"--compliance-yes to actually delete.\033[0m"
        )
        return None
    try:
        result = svc.delete_project(api_key, project_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to delete project {project_id}", e)
        if e.status == 409:
            print(
                "\033[93m  This project still has chats attached. List them with "
                "list_chats(user_ids=[...], project_ids=[project_id]) and delete or "
                "detach each one first, then retry.\033[0m"
            )
        return None
    print(f"\033[92m✓ Deleted project {project_id}\033[0m")
    return result


def cmd_compliance_orgs_list(api_key: str):
    try:
        data = svc.list_organizations(api_key)
    except ComplianceApiError as e:
        _print_error("Organization list request failed", e)
        return None
    print("\n\033[94mLinked organizations\033[0m\n")
    for org in data.get("data", []):
        print(f"  {org.get('uuid')}  {org.get('name')}")
    print()
    return data


def cmd_compliance_org_users(api_key: str, org_uuid: str, limit: int = 500):
    try:
        page = svc.list_organization_users(api_key, org_uuid, limit=limit)
    except ComplianceApiError as e:
        _print_error(f"Failed to list users for organization {org_uuid}", e)
        return None
    print(f"\n\033[94mUsers in {org_uuid}\033[0m\n")
    for u in page.get("data", []):
        print(f"  {u.get('id')}  {u.get('email', '?'):<32} role={u.get('organization_role', '?')}")
    if page.get("has_more"):
        print(f"\033[90m  ... more available (next_page={page.get('next_page')})\033[0m")
    print()
    return page


def cmd_compliance_org_roles(api_key: str, org_uuid: str):
    try:
        data = svc.list_roles(api_key, org_uuid)
    except ComplianceApiError as e:
        _print_error(f"Failed to list roles for organization {org_uuid}", e)
        return None
    print(f"\n\033[94mRoles in {org_uuid}\033[0m\n")
    for r in data.get("data", []):
        print(f"  {r.get('id')}  {r.get('name')} — {r.get('description', '')}")
    print()
    return data


def cmd_compliance_org_settings(api_key: str, org_uuid: str):
    try:
        data = svc.get_effective_settings(api_key, org_uuid)
    except ComplianceApiError as e:
        _print_error(f"Failed to fetch settings for organization {org_uuid}", e)
        return None
    print(f"\n\033[94mEffective settings for {org_uuid}\033[0m\n")
    for s in data.get("settings", []):
        print(f"  {s.get('name')} ({s.get('type')}): {s.get('value')}")
    print()
    return data


def cmd_compliance_groups_list(api_key: str):
    try:
        data = svc.list_groups(api_key)
    except ComplianceApiError as e:
        _print_error("Group list request failed", e)
        return None
    print("\n\033[94mGroups\033[0m\n")
    for g in data.get("data", []):
        print(f"  {g.get('id')}  {g.get('name')} (source: {g.get('source_type', '?')})")
    print()
    return data


def cmd_compliance_group_members(api_key: str, group_id: str):
    try:
        data = svc.list_group_members(api_key, group_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to list members for group {group_id}", e)
        return None
    print(f"\n\033[94mMembers of {group_id}\033[0m\n")
    for m in data.get("data", []):
        print(f"  {m.get('user_id')}  {m.get('email', '?')}")
    print()


def _print_session_row(s: dict, local: bool):
    who = (
        (s.get("user") or {}).get("email_address")
        or (s.get("user") or {}).get("id")
        or s.get("agent_id")
        or "?"
    )
    surface = s.get("product_surface", "?")
    if local:
        print(f"  {s.get('id')}  {s.get('created_at', '?'):<25} {surface:<12} {who}")
    else:
        status = s.get("status", "?")
        print(f"  {s.get('id')}  {s.get('created_at', '?'):<25} {surface:<14} {status:<10} {who}")


def cmd_compliance_local_sessions_list(
    api_key: str, since: str | None = None, until: str | None = None, limit: int = 100
):
    try:
        page = svc.list_local_sessions(api_key, since=since, until=until, limit=limit)
    except ComplianceApiError as e:
        _print_error("Local session list request failed", e)
        return None
    print("\n\033[94mLocal sessions (Cowork on Claude Desktop, Claude Code)\033[0m\n")
    for s in page.get("data", []):
        _print_session_row(s, local=True)
    if page.get("next_page"):
        print(f"\033[90m  ... more available (next_page={page.get('next_page')})\033[0m")
    print()
    return page


def cmd_compliance_local_session_get(api_key: str, session_id: str):
    try:
        data = svc.get_local_session(api_key, session_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to fetch local session {session_id}", e)
        return None
    print(f"\n\033[94mLocal session {session_id}\033[0m")
    for k, v in data.items():
        print(f"  {k}: {v}")
    print()
    return data


def cmd_compliance_local_session_messages(api_key: str, session_id: str):
    try:
        data = svc.get_local_session_messages(api_key, session_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to fetch transcript for local session {session_id}", e)
        return None
    _print_session_transcript(data)
    return data


def cmd_compliance_remote_sessions_list(
    api_key: str,
    since: str | None = None,
    until: str | None = None,
    user_ids: list | None = None,
    organization_ids: list | None = None,
    limit: int = 100,
):
    try:
        page = svc.list_remote_sessions(
            api_key,
            since=since,
            until=until,
            user_ids=user_ids,
            organization_ids=organization_ids,
            limit=limit,
        )
    except (ComplianceApiError, ValueError) as e:
        if isinstance(e, ValueError):
            print(f"\033[91m✗ {e}\033[0m")
        else:
            _print_error("Remote session list request failed", e)
        return None
    print("\n\033[94mRemote sessions (Cowork on claude.ai web/mobile)\033[0m\n")
    for s in page.get("data", []):
        _print_session_row(s, local=False)
    if page.get("next_page"):
        print(f"\033[90m  ... more available (next_page={page.get('next_page')})\033[0m")
    print()
    return page


def cmd_compliance_remote_session_messages(api_key: str, session_id: str):
    try:
        data = svc.get_remote_session_messages(api_key, session_id)
    except ComplianceApiError as e:
        _print_error(f"Failed to fetch transcript for remote session {session_id}", e)
        return None
    _print_session_transcript(data)
    return data


def _print_session_transcript(data: dict):
    session = data.get("session", {})
    print(
        f"\n\033[94mSession {session.get('id')}\033[0m  "
        f"(product_surface={session.get('product_surface', '?')})\n"
    )
    for msg in data.get("data", []):
        role = msg.get("role", "?")
        parts = []
        for block in msg.get("content", []) or []:
            btype = block.get("type")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_use":
                parts.append(f"[tool_use {block.get('name')}: {block.get('input')}]")
            elif btype == "tool_result":
                inner = "".join(
                    b.get("text", "") for b in (block.get("content") or []) if b.get("type") == "text"
                )
                parts.append(f"[tool_result {block.get('name')}: {inner[:200]}]")
        text = " ".join(parts)
        provenance = msg.get("provenance")
        marker = f" \033[90m(provenance: {provenance.get('type')})\033[0m" if provenance else ""
        print(f"  [{role:<9}]{marker} {text[:300]}")
    if data.get("next_page"):
        print(f"\033[90m  ... more available (next_page={data.get('next_page')})\033[0m")
    print()
    return data
