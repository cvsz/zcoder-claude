"""
application/compliance_service.py — Use-case layer for the Compliance API
AI Model Coder CLI v1.44.0 (Clean Architecture refactor, Phase A)

Same pattern as application/admin_service.py: every operation is a plain
function taking primitives and returning/yielding the gateway's raw data
(or raising ComplianceApiError / ValueError, same as the gateway does) —
no print(), so a future Web UI can reuse these directly.

cmd_compliance_activities is the one function with real orchestration
logic worth centralizing: it chooses between a single list_activities()
page and iterate_activities() across all pages depending on `all_pages`.
That choice now lives here as list_activities_page() / iterate_all_activities()
rather than duplicated if a second interface needs the same behavior.
"""

from typing import Iterator, Optional

from infrastructure.anthropic_api.compliance_gateway import ComplianceApiClient


# ── Activity Feed ────────────────────────────────────────────────────────

def list_activities_page(api_key: str, since: Optional[str] = None,
                         until: Optional[str] = None,
                         activity_types: Optional[list] = None,
                         limit: int = 100) -> dict:
    return ComplianceApiClient(api_key).list_activities(
        limit=limit, activity_types=activity_types,
        created_at_gte=since, created_at_lte=until,
    )


def iterate_all_activities(api_key: str, since: Optional[str] = None,
                           until: Optional[str] = None,
                           activity_types: Optional[list] = None,
                           limit: int = 100) -> Iterator[dict]:
    client = ComplianceApiClient(api_key)
    yield from client.iterate_activities(
        activity_types=activity_types, created_at_gte=since, created_at_lte=until,
        page_size=min(limit, 5000) or 100,
    )


# ── Chats ────────────────────────────────────────────────────────────────

def list_chats(api_key: str, user_ids: list, limit: int = 100) -> dict:
    return ComplianceApiClient(api_key).list_chats(user_ids, limit=limit)


def get_chat_messages(api_key: str, chat_id: str) -> dict:
    return ComplianceApiClient(api_key).get_chat_messages(chat_id)


def delete_chat(api_key: str, chat_id: str) -> dict:
    return ComplianceApiClient(api_key).delete_chat(chat_id)


# ── Files ────────────────────────────────────────────────────────────────

def download_file(api_key: str, file_id: str) -> tuple:
    """(content_bytes, filename, mime_type). Writing to disk stays in the
    CLI layer — this just fetches."""
    return ComplianceApiClient(api_key).download_file_content(file_id)


def delete_file(api_key: str, file_id: str) -> dict:
    return ComplianceApiClient(api_key).delete_file(file_id)


# ── Projects ─────────────────────────────────────────────────────────────

def list_projects(api_key: str, limit: int = 100) -> dict:
    return ComplianceApiClient(api_key).list_projects(limit=limit)


def get_project(api_key: str, project_id: str) -> dict:
    return ComplianceApiClient(api_key).get_project(project_id)


def list_project_attachments(api_key: str, project_id: str) -> dict:
    return ComplianceApiClient(api_key).list_project_attachments(project_id)


def delete_project(api_key: str, project_id: str) -> dict:
    """Fails (409) if chats are still attached — caller must detach/delete
    them first. See ComplianceApiError.status on failure."""
    return ComplianceApiClient(api_key).delete_project(project_id)


# ── Organizations / roles / settings ────────────────────────────────────

def list_organizations(api_key: str) -> dict:
    return ComplianceApiClient(api_key).list_organizations()


def list_organization_users(api_key: str, org_uuid: str, limit: int = 500) -> dict:
    return ComplianceApiClient(api_key).list_organization_users(org_uuid, limit=limit)


def list_roles(api_key: str, org_uuid: str) -> dict:
    return ComplianceApiClient(api_key).list_roles(org_uuid)


def get_effective_settings(api_key: str, org_uuid: str) -> dict:
    return ComplianceApiClient(api_key).get_effective_settings(org_uuid)


# ── Groups ───────────────────────────────────────────────────────────────

def list_groups(api_key: str) -> dict:
    return ComplianceApiClient(api_key).list_groups()


def list_group_members(api_key: str, group_id: str) -> dict:
    return ComplianceApiClient(api_key).list_group_members(group_id)


# ── Session transcripts (local: Cowork/Claude Code on-device; remote: Cowork cloud) ──

def list_local_sessions(api_key: str, since: Optional[str] = None,
                        until: Optional[str] = None, limit: int = 100) -> dict:
    return ComplianceApiClient(api_key).list_local_sessions(
        created_at_gte=since, created_at_lt=until, limit=limit)


def get_local_session(api_key: str, session_id: str) -> dict:
    return ComplianceApiClient(api_key).get_local_session(session_id)


def get_local_session_messages(api_key: str, session_id: str) -> dict:
    return ComplianceApiClient(api_key).get_local_session_messages(session_id)


def list_remote_sessions(api_key: str, since: Optional[str] = None,
                         until: Optional[str] = None,
                         user_ids: Optional[list] = None,
                         organization_ids: Optional[list] = None,
                         limit: int = 100) -> dict:
    return ComplianceApiClient(api_key).list_remote_sessions(
        organization_ids=organization_ids, user_ids=user_ids,
        created_at_gte=since, created_at_lt=until, limit=limit,
    )


def get_remote_session_messages(api_key: str, session_id: str) -> dict:
    return ComplianceApiClient(api_key).get_remote_session_messages(session_id)