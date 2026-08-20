"""tests/unit/application/test_compliance_service.py

Covers application/compliance_service.py — the use-case layer added in
Phase A (exec-planing.md) to close the gap where
interfaces/cli/commands/compliance_commands.py called ComplianceApiClient
directly. Plain data in/data out, no stdout capture needed.
"""
import pytest

import application.compliance_service as svc
from infrastructure.anthropic_api.compliance_gateway import ComplianceApiError


class FakeComplianceApiClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.calls = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return {"data": [], "_method": name}


@pytest.fixture
def fake_client(monkeypatch):
    holder = {}

    def factory(api_key):
        client = FakeComplianceApiClient(api_key)
        holder["client"] = client
        for method in (
            "list_activities", "list_chats", "get_chat_messages", "delete_chat",
            "download_file_content", "delete_file", "list_projects", "get_project",
            "list_project_attachments", "delete_project", "list_organizations",
            "list_organization_users", "list_roles", "get_effective_settings",
            "list_groups", "list_group_members", "list_local_sessions",
            "get_local_session", "get_local_session_messages", "list_remote_sessions",
            "get_remote_session_messages",
        ):
            setattr(client, method,
                    (lambda m: lambda *a, **kw: client._record(m, *a, **kw))(method))
        client.download_file_content = lambda *a, **kw: (b"bytes", "f.txt", "text/plain")
        client.iterate_activities = lambda **kw: iter([{"id": "a1"}, {"id": "a2"}])
        return client

    monkeypatch.setattr(svc, "ComplianceApiClient", factory)
    yield holder


def test_list_activities_page_passes_filters(fake_client):
    svc.list_activities_page("k", since="2026-01-01", until="2026-02-01",
                             activity_types=["chat_created"], limit=50)
    name, args, kwargs = fake_client["client"].calls[0]
    assert name == "list_activities"
    assert kwargs["created_at_gte"] == "2026-01-01"
    assert kwargs["created_at_lte"] == "2026-02-01"
    assert kwargs["activity_types"] == ["chat_created"]
    assert kwargs["limit"] == 50


def test_iterate_all_activities_yields_from_gateway_iterator(fake_client):
    results = list(svc.iterate_all_activities("k"))
    assert [a["id"] for a in results] == ["a1", "a2"]


def test_iterate_all_activities_caps_page_size_at_5000(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, api_key): pass
        def iterate_activities(self, **kw):
            captured.update(kw)
            return iter([])

    monkeypatch.setattr(svc, "ComplianceApiClient", FakeClient)
    list(svc.iterate_all_activities("k", limit=10_000))
    assert captured["page_size"] == 5000


def test_list_chats_passes_user_ids_and_limit(fake_client):
    svc.list_chats("k", ["u1", "u2"], limit=25)
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == (["u1", "u2"],)
    assert kwargs["limit"] == 25


def test_download_file_returns_tuple(fake_client):
    content, filename, mime = svc.download_file("k", "file_1")
    assert content == b"bytes"
    assert filename == "f.txt"
    assert mime == "text/plain"


def test_delete_project_forwards_project_id(fake_client):
    svc.delete_project("k", "proj_1")
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("proj_1",)


def test_list_organization_users_passes_limit(fake_client):
    svc.list_organization_users("k", "org_1", limit=200)
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("org_1",)
    assert kwargs["limit"] == 200


def test_get_effective_settings_forwards_org_uuid(fake_client):
    svc.get_effective_settings("k", "org_1")
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("org_1",)


def test_list_group_members_forwards_group_id(fake_client):
    svc.list_group_members("k", "group_1")
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("group_1",)


def test_list_local_sessions_passes_date_range(fake_client):
    svc.list_local_sessions("k", since="2026-01-01", until="2026-02-01", limit=10)
    name, args, kwargs = fake_client["client"].calls[0]
    assert kwargs["created_at_gte"] == "2026-01-01"
    assert kwargs["created_at_lt"] == "2026-02-01"
    assert kwargs["limit"] == 10


def test_list_remote_sessions_passes_all_filters(fake_client):
    svc.list_remote_sessions("k", since="2026-01-01", user_ids=["u1"],
                             organization_ids=["o1"], limit=10)
    name, args, kwargs = fake_client["client"].calls[0]
    assert kwargs["user_ids"] == ["u1"]
    assert kwargs["organization_ids"] == ["o1"]


def test_get_remote_session_messages_forwards_session_id(fake_client):
    svc.get_remote_session_messages("k", "cse_abc")
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("cse_abc",)


def test_every_service_function_forwards_the_api_key(fake_client):
    svc.list_projects("my-secret-key")
    assert fake_client["client"].api_key == "my-secret-key"


def test_list_chats_propagates_value_error(monkeypatch):
    class BoomClient:
        def __init__(self, api_key): pass
        def list_chats(self, user_ids, limit=100):
            raise ValueError("too many user_ids")

    monkeypatch.setattr(svc, "ComplianceApiClient", BoomClient)
    with pytest.raises(ValueError):
        svc.list_chats("k", ["u"] * 999)


def test_get_project_propagates_compliance_api_error(monkeypatch):
    class BoomClient:
        def __init__(self, api_key): pass
        def get_project(self, project_id):
            raise ComplianceApiError(status=404, error_type="not_found",
                                     message="no such project", request_id=None)

    monkeypatch.setattr(svc, "ComplianceApiClient", BoomClient)
    with pytest.raises(ComplianceApiError):
        svc.get_project("k", "proj_missing")
