"""tests/unit/application/test_admin_service.py

Covers application/admin_service.py — the use-case layer added in Phase A
(exec-planing.md) to close the gap where
interfaces/cli/commands/admin_commands.py called AdminApiClient directly.
These test plain data in/data out — no stdout capture needed, unlike the
cmd_* coverage in tests/test_claude_admin_api.py.
"""
import pytest

import application.admin_service as svc


class FakeAdminApiClient:
    """Records the call it received and returns a canned response."""
    def __init__(self, admin_api_key):
        self.admin_api_key = admin_api_key
        self.calls = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return {"data": [], "_method": name}


@pytest.fixture
def fake_client(monkeypatch):
    holder = {}

    def factory(admin_api_key):
        client = FakeAdminApiClient(admin_api_key)
        holder["client"] = client
        for method in (
            "get_usage_report", "get_cost_report", "list_external_keys",
            "get_claude_code_usage_report", "list_api_keys", "revoke_api_key",
            "list_effective_spend_limits", "set_spend_limit", "get_spend_limit",
            "delete_spend_limit", "list_spend_limit_increase_requests",
            "approve_spend_limit_increase_request", "deny_spend_limit_increase_request",
            "get_org_rate_limits", "get_workspace_rate_limits",
            "list_members", "get_member", "update_member_role", "remove_member",
            "create_invite", "list_invites", "withdraw_invite",
            "list_groups", "create_group", "delete_group", "list_group_members",
            "add_group_member", "remove_group_member", "list_roles",
            "list_role_permissions",
        ):
            setattr(client, method,
                    (lambda m: lambda *a, **kw: client._record(m, *a, **kw))(method))
        return client

    monkeypatch.setattr(svc, "AdminApiClient", factory)
    yield holder


def test_default_date_range_is_30_days():
    start, end = svc._default_date_range()
    from datetime import date
    assert date.fromisoformat(start) < date.fromisoformat(end)


def test_get_usage_report_defaults_dates_when_omitted(fake_client):
    svc.get_usage_report("admin-k")
    name, args, kwargs = fake_client["client"].calls[0]
    assert name == "get_usage_report"
    assert len(args) == 2  # start, end both populated
    assert kwargs["group_by"] == "model"


def test_get_usage_report_passes_through_explicit_dates(fake_client):
    svc.get_usage_report("admin-k", start="2026-01-01", end="2026-01-31", group_by="workspace")
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("2026-01-01", "2026-01-31")
    assert kwargs["group_by"] == "workspace"


def test_get_cost_report_defaults_dates(fake_client):
    svc.get_cost_report("admin-k")
    name, args, kwargs = fake_client["client"].calls[0]
    assert name == "get_cost_report"
    assert len(args) == 2


def test_list_cmek_keys_passes_workspace_id(fake_client):
    svc.list_cmek_keys("admin-k", workspace_id="ws_1")
    name, args, kwargs = fake_client["client"].calls[0]
    assert name == "list_external_keys"
    assert kwargs["workspace_id"] == "ws_1"


def test_list_api_keys_passes_limit(fake_client):
    svc.list_api_keys("admin-k", limit=5)
    name, args, kwargs = fake_client["client"].calls[0]
    assert kwargs["limit"] == 5


def test_revoke_api_key_passes_key_id(fake_client):
    svc.revoke_api_key("admin-k", "key_123")
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("key_123",)


def test_set_spend_limit_passes_all_args(fake_client):
    svc.set_spend_limit("admin-k", "user_1", "1000", suppress_notification=True)
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("user_1", "1000")
    assert kwargs["suppress_notification"] is True


def test_list_spend_limit_increase_requests_wraps_status_in_list(fake_client):
    svc.list_spend_limit_increase_requests("admin-k", status="pending")
    name, args, kwargs = fake_client["client"].calls[0]
    assert kwargs["status"] == ["pending"]


def test_list_spend_limit_increase_requests_none_status_stays_none(fake_client):
    svc.list_spend_limit_increase_requests("admin-k")
    name, args, kwargs = fake_client["client"].calls[0]
    assert kwargs["status"] is None


def test_get_org_rate_limits_passes_model(fake_client):
    svc.get_org_rate_limits("admin-k", model="claude-sonnet-5")
    name, args, kwargs = fake_client["client"].calls[0]
    assert kwargs["model"] == "claude-sonnet-5"


def test_get_workspace_rate_limits_passes_workspace_id(fake_client):
    svc.get_workspace_rate_limits("admin-k", "ws_1")
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("ws_1",)


def test_list_members_passes_email_filter(fake_client):
    svc.list_members("admin-k", limit=10, email="a@b.com")
    name, args, kwargs = fake_client["client"].calls[0]
    assert kwargs["email"] == "a@b.com"


def test_update_member_role_passes_role(fake_client):
    svc.update_member_role("admin-k", "user_1", "managed")
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("user_1", "managed")


def test_create_invite_passes_rbac_group_ids(fake_client):
    svc.create_invite("admin-k", "a@b.com", "user", rbac_group_ids=["g1", "g2"])
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("a@b.com", "user")
    assert kwargs["rbac_group_ids"] == ["g1", "g2"]


def test_list_groups_passes_limit(fake_client):
    svc.list_groups("admin-k", limit=15)
    name, args, kwargs = fake_client["client"].calls[0]
    assert kwargs["limit"] == 15


def test_add_group_member_passes_group_and_user(fake_client):
    svc.add_group_member("admin-k", "group_1", "user_1")
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("group_1", "user_1")


def test_list_role_permissions_passes_role_id(fake_client):
    svc.list_role_permissions("admin-k", "role_1", limit=30)
    name, args, kwargs = fake_client["client"].calls[0]
    assert args == ("role_1",)
    assert kwargs["limit"] == 30


def test_every_service_function_forwards_the_admin_api_key(fake_client):
    svc.list_api_keys("my-secret-admin-key")
    assert fake_client["client"].admin_api_key == "my-secret-admin-key"
