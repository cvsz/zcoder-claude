"""tests/test_cli_wiring.py — CLI-to-API wiring coverage

Two invariants:

1. Every `cmd_*` function defined in interfaces/cli/commands/
   *_commands.py is dispatched by interfaces/cli/dispatcher.py.
2. The retired repo-root compatibility shims (claude_*.py, coder.py)
   never come back.

This doesn't verify the *behavior* of each wired command (that's each
module's own test file's job) — only that nothing gets left behind the
way claude_github.py, claude_metrics.py, claude_prompt_optimizer.py,
and claude_router.py once were: fully written, fully tested at the
function level, and never given a CLI flag.
"""

import ast
import glob
import os
import re

import pytest

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

def _cmd_functions(path):
    """Top-level `def cmd_*` function names in a Python source file."""
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    return [
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("cmd_")
    ]


@pytest.fixture(scope="module")
def main_source():
    sources = []
    for name in ("main.py", "interfaces/cli/dispatcher.py"):
        path = os.path.join(REPO_ROOT, name)
        with open(path, encoding="utf-8") as f:
            sources.append(f.read())
    return "\n".join(sources)


def _interfaces_cmd_functions():
    """cmd_* functions defined across every migrated command module."""
    fns = []
    for path in sorted(glob.glob(os.path.join(REPO_ROOT, "interfaces/cli/commands/*_commands.py"))):
        fns.extend((os.path.basename(path), name) for name in _cmd_functions(path))
    return fns


def test_every_commands_function_is_dispatched(main_source):
    """Every cmd_* defined in interfaces/cli/commands/*_commands.py must
    be dispatched by interfaces/cli/dispatcher.py — the no-orphaned-command
    guarantee, generalized from wrapper_commands.py to all command modules."""
    dispatcher_path = os.path.join(REPO_ROOT, "interfaces/cli/dispatcher.py")
    with open(dispatcher_path, encoding="utf-8") as f:
        dispatcher_source = f.read()
    for module, fn in _interfaces_cmd_functions():
        pattern = r"\b" + re.escape(fn) + r"\b"
        assert re.search(pattern, dispatcher_source), (
            f"{module}.{fn}() is defined but never dispatched by "
            f"interfaces/cli/dispatcher.py — add a CLI flag and dispatch "
            f"line, or remove the dead function."
        )


def test_no_claude_shim_files_remain():
    """The Clean Architecture migration retired every repo-root
    compatibility shim (claude_*.py plus coder.py) — guard against
    reintroduction."""
    assert glob.glob(os.path.join(REPO_ROOT, "claude_*.py")) == []
    assert not os.path.exists(os.path.join(REPO_ROOT, "coder.py"))


# ── Targeted dispatch tests for the four newly-wired modules ────────────


@pytest.fixture
def parsed_args():
    import main as main_mod

    parser = main_mod.build_parser()

    def _parse(argv):
        return parser.parse_args(argv)

    return _parse


def test_gh_review_pr_flag_parses(parsed_args):
    args = parsed_args(["--gh-review-pr", "acme/widgets/42", "--gh-token", "ghp_x"])
    assert args.gh_review_pr == "acme/widgets/42"
    assert args.gh_token == "ghp_x"


def test_gh_max_items_defaults_to_20(parsed_args):
    args = parsed_args(["--gh-triage-issues", "acme/widgets"])
    assert args.gh_max_items == 20


def test_route_flags_parse(parsed_args):
    args = parsed_args(["--route", "fix this bug", "--route-explain", "--route-parallel"])
    assert args.route == "fix this bug"
    assert args.route_explain is True
    assert args.route_parallel is True


def test_route_list_is_independent_flag(parsed_args):
    args = parsed_args(["--route-list"])
    assert args.route_list is True
    assert args.route is None


def test_optimize_flag_parses(parsed_args):
    args = parsed_args(["--optimize", "write me a poem"])
    assert args.prompt_optimize == "write me a poem"


def test_ab_test_flags_parse(parsed_args):
    args = parsed_args(
        ["--ab-test", "--prompt", "variant A", "--ab-prompt-b", "variant B", "--ab-task", "summarize a doc"]
    )
    assert args.ab_test is True
    assert args.prompt == "variant A"
    assert args.ab_prompt_b == "variant B"
    assert args.ab_task == "summarize a doc"


def test_metrics_show_and_modifiers_parse(parsed_args):
    args = parsed_args(["--metrics-show", "--metrics-today", "--metrics-model", "claude-sonnet-5"])
    assert args.metrics_show is True
    assert args.metrics_today is True
    assert args.metrics_model == "claude-sonnet-5"


def test_metrics_export_flag_parses(parsed_args):
    args = parsed_args(["--metrics-export", "out.json"])
    assert args.metrics_export == "out.json"


# ── Dispatch-level tests (monkeypatch the imported cmd_* function) ──────


def _run_main_with(monkeypatch, argv, api_key="sk-ant-test"):
    import main as main_mod

    monkeypatch.setattr("sys.argv", ["main.py"] + argv)
    monkeypatch.setenv("ANTHROPIC_API_KEY", api_key)
    main_mod.main()


def test_route_list_dispatches_to_cmd_route_list(monkeypatch):
    from interfaces.cli.commands import code_agent_commands as claude_router

    called = {}
    monkeypatch.setattr(claude_router, "cmd_route_list", lambda *a, **k: called.setdefault("hit", True))
    _run_main_with(monkeypatch, ["--route-list"])
    assert called.get("hit") is True


def test_prompt_lib_list_dispatches(monkeypatch):
    from interfaces.cli.commands import prompt_optimizer_commands as claude_prompt_optimizer

    called = {}
    monkeypatch.setattr(
        claude_prompt_optimizer, "cmd_prompt_lib_list", lambda *a, **k: called.setdefault("hit", True)
    )
    _run_main_with(monkeypatch, ["--prompt-lib-list"])
    assert called.get("hit") is True


def test_metrics_clear_dispatches(monkeypatch):
    from interfaces.cli.commands import observability_commands as claude_metrics

    called = {}
    monkeypatch.setattr(claude_metrics, "cmd_metrics_clear", lambda *a, **k: called.setdefault("hit", True))
    _run_main_with(monkeypatch, ["--metrics-clear"])
    assert called.get("hit") is True


def test_gh_triage_dispatches_with_positional_order(monkeypatch):
    from interfaces.cli.commands import devtools_commands as claude_github

    seen = {}

    def fake_triage(repo, max_items, token, api_key, model):
        seen.update(repo=repo, max_items=max_items, token=token)

    monkeypatch.setattr(claude_github, "cmd_gh_triage", fake_triage)
    _run_main_with(
        monkeypatch, ["--gh-triage-issues", "acme/widgets", "--gh-max-items", "5", "--gh-token", "ghp_x"]
    )
    assert seen == {"repo": "acme/widgets", "max_items": 5, "token": "ghp_x"}


def test_prompt_lib_add_requires_prompt(monkeypatch, capsys):
    _run_main_with(monkeypatch, ["--prompt-lib-add", "--tag", "my-tag"])
    out = capsys.readouterr().out
    assert "requires --prompt" in out


def test_ab_test_requires_both_variants(monkeypatch, capsys):
    _run_main_with(monkeypatch, ["--ab-test", "--prompt", "only A"])
    out = capsys.readouterr().out
    assert "requires --prompt" in out and "--ab-prompt-b" in out


# ── Targeted parse tests for v1.38.0's CE User Management flags ─────────


def test_members_list_and_email_filter_parse(parsed_args):
    args = parsed_args(["--members-list", "--members-email", "jane@example.com"])
    assert args.members_list is True
    assert args.members_email == "jane@example.com"


def test_member_role_set_flag_parses(parsed_args):
    args = parsed_args(["--member-role-set", "user_01Ab", "managed"])
    assert args.member_role_set == ["user_01Ab", "managed"]


def test_invite_create_with_rbac_groups_parses(parsed_args):
    args = parsed_args(
        [
            "--invite-create",
            "jane@example.com",
            "managed",
            "--invite-rbac-groups",
            "rbac_group_01Ab,rbac_group_02Cd",
        ]
    )
    assert args.invite_create == ["jane@example.com", "managed"]
    assert args.invite_rbac_groups == "rbac_group_01Ab,rbac_group_02Cd"


def test_group_member_add_flag_parses(parsed_args):
    args = parsed_args(["--group-member-add", "rbac_group_01Ab", "user_01Cd"])
    assert args.group_member_add == ["rbac_group_01Ab", "user_01Cd"]


def test_roles_list_and_role_permissions_flags_parse(parsed_args):
    args = parsed_args(["--roles-list"])
    assert args.roles_list is True
    args2 = parsed_args(["--role-permissions", "rbac_role_01Ab"])
    assert args2.role_permissions == "rbac_role_01Ab"


def test_ce_user_management_dispatch_requires_admin_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_ADMIN_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        _run_main_with(monkeypatch, ["--members-list"])
    err = capsys.readouterr().err
    assert "Admin API key" in err


def test_members_list_dispatches_to_cmd(monkeypatch):
    from interfaces.cli.commands import admin_commands as claude_admin_api

    seen = {}

    def fake_members_list(admin_key, limit=20, email=None):
        seen.update(admin_key=admin_key, email=email)

    monkeypatch.setattr(claude_admin_api, "cmd_members_list", fake_members_list)
    monkeypatch.setenv("ANTHROPIC_ADMIN_API_KEY", "sk-ant-admin-test")
    _run_main_with(monkeypatch, ["--members-list", "--members-email", "jane@example.com"])
    assert seen == {"admin_key": "sk-ant-admin-test", "email": "jane@example.com"}
