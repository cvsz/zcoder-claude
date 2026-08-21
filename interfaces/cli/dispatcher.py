import os
import sys
from pathlib import Path

VERSION = "1.41.0"

BANNER = f"\033[94mAI Model Coder CLI v{VERSION}\033[0m"

AGENT_SYSTEM_PROMPTS = {
    "code_generator": "You are a full-project code generation agent. Produce complete, "
    "runnable code for the request, not a partial sketch.",
    "code_reviewer": "You are a code review agent. Focus on correctness, readability, "
    "and maintainability; call out concrete issues with line-level detail.",
    "testing_agent": "You are a testing agent. Produce comprehensive test suites, "
    "covering edge cases and failure modes, not just the happy path.",
    "documentation_agent": "You are a documentation agent. Write clear docs, READMEs, and API "
    "references aimed at a reader new to this codebase.",
    "optimizer": "You are a performance optimization agent. Identify concrete "
    "bottlenecks and propose measurable improvements.",
    "security_auditor": "You are a security audit agent. Review for vulnerabilities "
    "(injection, auth, secrets handling, unsafe deserialization, etc.) "
    "and rate severity for each finding.",
    "full_stack": "You are a full-stack engineering agent. Consider frontend, backend, "
    "and data-layer concerns together when responding.",
}


def _api_key(args):
    k = getattr(args, "api_key", None) or os.environ.get("ANTHROPIC_API_KEY", "")
    if not k:
        print("[ERROR] ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    return k


def _model(args):
    return getattr(args, "model", "claude-sonnet-5") or "claude-sonnet-5"


def _read_file(path):
    try:
        return open(path).read()
    except Exception as e:
        print(f"[ERROR] Cannot read {path}: {e}", file=sys.stderr)
        sys.exit(1)


def dispatch(args):
    from logging_config import new_correlation_id, setup_logging

    setup_logging()
    new_correlation_id()

    from logging_config import new_correlation_id, setup_logging

    setup_logging()
    new_correlation_id()

    if args.version:
        print(BANNER)
        return

    if getattr(args, "health_check", False):
        import json as _json

        from health import run_health_check

        report = run_health_check(deep=getattr(args, "health_check_deep", False))
        print(_json.dumps(report.to_dict(), indent=2))
        sys.exit(0 if report.healthy else 1)

    # ── No-key listing ──
    if args.list_skills:
        from skills import SkillManager

        for s in SkillManager().list_skills():
            print(f"  {s['name']:<25} — {s['description']}")
        return
    if args.list_agents:
        # Was a second, independent hardcoded list of the same seven names
        # with no data behind them; now sourced from AGENT_SYSTEM_PROMPTS,
        # the same table --agent actually uses, so the two can't drift.
        for n, sys_prompt in sorted(AGENT_SYSTEM_PROMPTS.items()):
            print(f"  {n:<25} — {sys_prompt}")
        return
    if args.list_personalities:
        from personalities import PersonalityManager

        for p_ in PersonalityManager().list_personalities():
            print(f"  {p_['name']:<12} — {p_['description']}")
        return

    # ── Plugins & Marketplaces (no API key required) ──
    if args.plugin_marketplace_add:
        from claude_plugins import cmd_plugin_marketplace_add

        cmd_plugin_marketplace_add(args.plugin_marketplace_add, args.plugin_marketplace_name)
        return
    if args.plugin_marketplace_list:
        from claude_plugins import cmd_plugin_marketplace_list

        cmd_plugin_marketplace_list()
        return
    if args.plugin_marketplace_remove:
        from claude_plugins import cmd_plugin_marketplace_remove

        cmd_plugin_marketplace_remove(args.plugin_marketplace_remove)
        return
    if args.plugin_install:
        from claude_plugins import cmd_plugin_install

        cmd_plugin_install(args.plugin_install)
        return
    if args.plugin_dir:
        from claude_plugins import cmd_plugin_install_dir

        cmd_plugin_install_dir(args.plugin_dir)
        return
    if args.plugin_uninstall:
        from claude_plugins import cmd_plugin_uninstall

        cmd_plugin_uninstall(args.plugin_uninstall)
        return
    if args.plugin_list:
        from claude_plugins import cmd_plugin_list

        cmd_plugin_list()
        return
    if args.plugin_info:
        from claude_plugins import cmd_plugin_info

        cmd_plugin_info(args.plugin_info)
        return
    if args.plugin_enable:
        from claude_plugins import cmd_plugin_enable

        cmd_plugin_enable(args.plugin_enable)
        return
    if args.plugin_disable:
        from claude_plugins import cmd_plugin_disable

        cmd_plugin_disable(args.plugin_disable)
        return
    if args.plugin_validate:
        from claude_plugins import cmd_plugin_validate

        cmd_plugin_validate(args.plugin_validate)
        return

    # ── Settings (no API key required) ──
    if args.settings_show:
        from claude_settings import cmd_settings_show

        cmd_settings_show()
        return
    if args.status_line:
        from claude_settings import cmd_status_line

        cmd_status_line(model=args.model or "claude-sonnet-5", cwd=args.code_agent_cwd)
        return
    if args.list_output_styles:
        from claude_output_styles import cmd_list_output_styles

        cmd_list_output_styles()
        return

    if args.fable5_info:
        from claude_fable5 import cmd_fable5_info

        cmd_fable5_info()
        return

    if args.mythos5_info:
        from claude_mythos5 import cmd_mythos5_info

        cmd_mythos5_info()
        return

    if args.opus5_info:
        from claude_opus5 import cmd_opus5_info

        cmd_opus5_info()
        return

    if args.sonnet5_info:
        from claude_sonnet5 import cmd_sonnet5_info

        cmd_sonnet5_info()
        return

    if args.sonnet5_cost:
        from claude_sonnet5 import cmd_sonnet5_cost

        cmd_sonnet5_cost(args.sonnet5_cost)
        return

    if args.haiku45_info:
        from claude_haiku45 import cmd_haiku45_info

        cmd_haiku45_info()
        return

    if args.skills_list:
        from claude_skills_api import cmd_skills_list

        cmd_skills_list()
        return
    if args.skills_info:
        from claude_skills_api import cmd_skills_info

        cmd_skills_info(args.skills_info)
        return

    if (
        args.usage_report
        or args.cost_report
        or args.admin_list_keys
        or args.admin_revoke_key
        or args.admin_create_key
        or args.spend_limits_list
        or args.spend_limit_set
        or args.spend_limit_get
        or args.spend_limit_delete
        or args.spend_limit_requests_list
        or args.spend_limit_request_approve
        or args.spend_limit_request_deny
        or args.rate_limits
        or args.rate_limits_workspace
        or args.claude_code_usage_report
        or args.cmek_list
    ):
        admin_key = args.admin_api_key or os.environ.get("ANTHROPIC_ADMIN_API_KEY")
        if args.admin_create_key:
            from claude_admin_api import cmd_admin_create_key

            cmd_admin_create_key(args.admin_create_key)
            return
        if not admin_key:
            print(
                "[ERROR] This requires an Admin API key: pass --admin-api-key or set "
                "ANTHROPIC_ADMIN_API_KEY",
                file=sys.stderr,
            )
            sys.exit(1)
        if args.usage_report:
            from claude_admin_api import cmd_usage_report

            cmd_usage_report(
                admin_key,
                start=args.usage_report_start,
                end=args.usage_report_end,
                group_by=args.usage_report_group_by,
            )
            return
        if args.cost_report:
            from claude_admin_api import cmd_cost_report

            cmd_cost_report(
                admin_key,
                start=args.cost_report_start,
                end=args.cost_report_end,
                group_by=args.cost_report_group_by,
            )
            return
        if args.admin_list_keys:
            from claude_admin_api import cmd_admin_list_keys

            cmd_admin_list_keys(admin_key)
            return
        if args.admin_revoke_key:
            from claude_admin_api import cmd_admin_revoke_key

            cmd_admin_revoke_key(admin_key, args.admin_revoke_key)
            return
        if args.spend_limits_list:
            from claude_admin_api import cmd_spend_limits_list

            cmd_spend_limits_list(admin_key)
            return
        if args.spend_limit_set:
            from claude_admin_api import cmd_spend_limit_set

            user_id, amount = args.spend_limit_set
            cmd_spend_limit_set(user_id, amount, admin_key)
            return
        if args.spend_limit_get:
            from claude_admin_api import cmd_spend_limit_get

            cmd_spend_limit_get(args.spend_limit_get, admin_key)
            return
        if args.spend_limit_delete:
            from claude_admin_api import cmd_spend_limit_delete

            cmd_spend_limit_delete(args.spend_limit_delete, admin_key)
            return
        if args.spend_limit_requests_list:
            from claude_admin_api import cmd_spend_limit_requests_list

            cmd_spend_limit_requests_list(admin_key, status=args.spend_limit_status or None)
            return
        if args.spend_limit_request_approve:
            from claude_admin_api import cmd_spend_limit_request_approve

            cmd_spend_limit_request_approve(args.spend_limit_request_approve, admin_key)
            return
        if args.spend_limit_request_deny:
            from claude_admin_api import cmd_spend_limit_request_deny

            cmd_spend_limit_request_deny(args.spend_limit_request_deny, admin_key)
            return
        if args.rate_limits_workspace:
            from claude_admin_api import cmd_rate_limits_workspace

            cmd_rate_limits_workspace(args.rate_limits_workspace, admin_key)
            return
        if args.rate_limits:
            from claude_admin_api import cmd_rate_limits

            cmd_rate_limits(admin_key, model=args.rate_limits_model or None)
            return
        if args.claude_code_usage_report:
            from claude_admin_api import cmd_claude_code_usage_report

            starting_at = args.claude_code_usage_report_start
            if not starting_at:
                import datetime as _dt

                starting_at = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
            cmd_claude_code_usage_report(admin_key, starting_at)
            return
        if args.cmek_list:
            from claude_admin_api import cmd_cmek_list

            cmd_cmek_list(admin_key, workspace_id=args.cmek_workspace or None)
            return

    if (
        args.members_list
        or args.member_get
        or args.member_role_set
        or args.member_remove
        or args.invite_create
        or args.invites_list
        or args.invite_withdraw
        or args.groups_list
        or args.group_create
        or args.group_delete
        or args.group_members_list
        or args.group_member_add
        or args.group_member_remove
        or args.roles_list
        or args.role_permissions
    ):
        admin_key = args.admin_api_key or os.environ.get("ANTHROPIC_ADMIN_API_KEY")
        if not admin_key:
            print(
                "[ERROR] This requires an Admin API key: pass --admin-api-key or set "
                "ANTHROPIC_ADMIN_API_KEY",
                file=sys.stderr,
            )
            sys.exit(1)
        if args.members_list:
            from claude_admin_api import cmd_members_list

            cmd_members_list(admin_key, email=args.members_email or None)
            return
        if args.member_get:
            from claude_admin_api import cmd_member_get

            cmd_member_get(args.member_get, admin_key)
            return
        if args.member_role_set:
            from claude_admin_api import cmd_member_role_set

            user_id, role = args.member_role_set
            cmd_member_role_set(user_id, role, admin_key)
            return
        if args.member_remove:
            from claude_admin_api import cmd_member_remove

            cmd_member_remove(args.member_remove, admin_key)
            return
        if args.invite_create:
            from claude_admin_api import cmd_invite_create

            email, role = args.invite_create
            rbac_group_ids = (
                [g.strip() for g in args.invite_rbac_groups.split(",") if g.strip()]
                if args.invite_rbac_groups
                else None
            )
            cmd_invite_create(email, role, admin_key, rbac_group_ids=rbac_group_ids)
            return
        if args.invites_list:
            from claude_admin_api import cmd_invites_list

            cmd_invites_list(admin_key)
            return
        if args.invite_withdraw:
            from claude_admin_api import cmd_invite_withdraw

            cmd_invite_withdraw(args.invite_withdraw, admin_key)
            return
        if args.groups_list:
            from claude_admin_api import cmd_groups_list

            cmd_groups_list(admin_key)
            return
        if args.group_create:
            from claude_admin_api import cmd_group_create

            cmd_group_create(args.group_create, admin_key)
            return
        if args.group_delete:
            from claude_admin_api import cmd_group_delete

            cmd_group_delete(args.group_delete, admin_key)
            return
        if args.group_members_list:
            from claude_admin_api import cmd_group_members_list

            cmd_group_members_list(args.group_members_list, admin_key)
            return
        if args.group_member_add:
            from claude_admin_api import cmd_group_member_add

            group_id, user_id = args.group_member_add
            cmd_group_member_add(group_id, user_id, admin_key)
            return
        if args.group_member_remove:
            from claude_admin_api import cmd_group_member_remove

            group_id, user_id = args.group_member_remove
            cmd_group_member_remove(group_id, user_id, admin_key)
            return
        if args.roles_list:
            from claude_admin_api import cmd_roles_list

            cmd_roles_list(admin_key)
            return
        if args.role_permissions:
            from claude_admin_api import cmd_role_permissions_list

            cmd_role_permissions_list(args.role_permissions, admin_key)
            return

    if (
        args.wif_exchange_token
        or args.wif_status
        or args.wif_create_service_account
        or args.wif_list_service_accounts
        or args.wif_create_issuer
        or args.wif_list_issuers
        or args.wif_create_rule
        or args.wif_list_rules
    ):
        if args.wif_status:
            from claude_wif import cmd_wif_status

            cmd_wif_status()
            return
        if args.wif_exchange_token:
            from claude_wif import cmd_wif_exchange_token

            cmd_wif_exchange_token()
            return
        org_admin_token = args.org_admin_token or os.environ.get("ANTHROPIC_ORG_ADMIN_TOKEN")
        if not org_admin_token:
            print(
                "[ERROR] This requires an org:admin OAuth token: pass --org-admin-token or "
                "set ANTHROPIC_ORG_ADMIN_TOKEN",
                file=sys.stderr,
            )
            sys.exit(1)
        if args.wif_create_service_account:
            from claude_wif import cmd_wif_create_service_account

            cmd_wif_create_service_account(args.wif_create_service_account, org_admin_token)
            return
        if args.wif_list_service_accounts:
            from claude_wif import cmd_wif_list_service_accounts

            cmd_wif_list_service_accounts(org_admin_token)
            return
        if args.wif_create_issuer:
            from claude_wif import cmd_wif_create_issuer

            if not args.wif_issuer_url:
                print("[ERROR] --wif-create-issuer requires --wif-issuer-url")
                sys.exit(1)
            cmd_wif_create_issuer(args.wif_create_issuer, args.wif_issuer_url, org_admin_token)
            return
        if args.wif_list_issuers:
            from claude_wif import cmd_wif_list_issuers

            cmd_wif_list_issuers(org_admin_token)
            return
        if args.wif_create_rule:
            from claude_wif import cmd_wif_create_rule

            if not (args.wif_rule_issuer and args.wif_rule_service_account and args.wif_rule_subject_prefix):
                print(
                    "[ERROR] --wif-create-rule requires --wif-rule-issuer, "
                    "--wif-rule-service-account, and --wif-rule-subject-prefix"
                )
                sys.exit(1)
            cmd_wif_create_rule(
                args.wif_create_rule,
                args.wif_rule_issuer,
                args.wif_rule_service_account,
                args.wif_rule_subject_prefix,
                org_admin_token,
            )
            return
        if args.wif_list_rules:
            from claude_wif import cmd_wif_list_rules

            cmd_wif_list_rules(org_admin_token)
            return

    _compliance_flags = (
        args.compliance_activities,
        args.compliance_chats_list,
        args.compliance_chat_messages,
        args.compliance_chat_delete,
        args.compliance_file_download,
        args.compliance_file_delete,
        args.compliance_projects_list,
        args.compliance_project_info,
        args.compliance_project_attachments,
        args.compliance_project_delete,
        args.compliance_orgs_list,
        args.compliance_org_users,
        args.compliance_org_roles,
        args.compliance_org_settings,
        args.compliance_groups_list,
        args.compliance_group_members,
        args.compliance_local_sessions_list,
        args.compliance_local_session_get,
        args.compliance_local_session_messages,
        args.compliance_remote_sessions_list,
        args.compliance_remote_session_messages,
    )
    if any(_compliance_flags):
        compliance_key = (
            args.compliance_api_key
            or os.environ.get("ANTHROPIC_COMPLIANCE_API_KEY")
            or args.admin_api_key
            or os.environ.get("ANTHROPIC_ADMIN_API_KEY")
        )
        if not compliance_key:
            print(
                "[ERROR] This requires a Compliance Access Key or Admin API key: pass "
                "--compliance-api-key or set ANTHROPIC_COMPLIANCE_API_KEY (or "
                "--admin-api-key / ANTHROPIC_ADMIN_API_KEY for Activity-Feed-only access)",
                file=sys.stderr,
            )
            sys.exit(1)
        activity_types = args.compliance_activity_types.split(",") if args.compliance_activity_types else None
        user_ids = args.compliance_user_ids.split(",") if args.compliance_user_ids else None

        if args.compliance_activities:
            from claude_compliance_api import cmd_compliance_activities

            cmd_compliance_activities(
                compliance_key,
                since=args.compliance_activities_since,
                until=args.compliance_activities_until,
                activity_types=activity_types,
                limit=args.compliance_activities_limit,
                all_pages=args.compliance_activities_all,
            )
            return
        if args.compliance_chats_list:
            from claude_compliance_api import cmd_compliance_chats_list

            if not user_ids:
                print("[ERROR] --compliance-chats-list requires --compliance-user-ids", file=sys.stderr)
                sys.exit(1)
            cmd_compliance_chats_list(compliance_key, user_ids)
            return
        if args.compliance_chat_messages:
            from claude_compliance_api import cmd_compliance_chat_messages

            cmd_compliance_chat_messages(compliance_key, args.compliance_chat_messages)
            return
        if args.compliance_chat_delete:
            from claude_compliance_api import cmd_compliance_chat_delete

            cmd_compliance_chat_delete(compliance_key, args.compliance_chat_delete, yes=args.compliance_yes)
            return
        if args.compliance_file_download:
            from claude_compliance_api import cmd_compliance_file_download

            cmd_compliance_file_download(
                compliance_key, args.compliance_file_download, output_path=args.compliance_output
            )
            return
        if args.compliance_file_delete:
            from claude_compliance_api import cmd_compliance_file_delete

            cmd_compliance_file_delete(compliance_key, args.compliance_file_delete, yes=args.compliance_yes)
            return
        if args.compliance_projects_list:
            from claude_compliance_api import cmd_compliance_projects_list

            cmd_compliance_projects_list(compliance_key)
            return
        if args.compliance_project_info:
            from claude_compliance_api import cmd_compliance_project_info

            cmd_compliance_project_info(compliance_key, args.compliance_project_info)
            return
        if args.compliance_project_attachments:
            from claude_compliance_api import cmd_compliance_project_attachments

            cmd_compliance_project_attachments(compliance_key, args.compliance_project_attachments)
            return
        if args.compliance_project_delete:
            from claude_compliance_api import cmd_compliance_project_delete

            cmd_compliance_project_delete(
                compliance_key, args.compliance_project_delete, yes=args.compliance_yes
            )
            return
        if args.compliance_orgs_list:
            from claude_compliance_api import cmd_compliance_orgs_list

            cmd_compliance_orgs_list(compliance_key)
            return
        if args.compliance_org_users:
            from claude_compliance_api import cmd_compliance_org_users

            cmd_compliance_org_users(compliance_key, args.compliance_org_users)
            return
        if args.compliance_org_roles:
            from claude_compliance_api import cmd_compliance_org_roles

            cmd_compliance_org_roles(compliance_key, args.compliance_org_roles)
            return
        if args.compliance_org_settings:
            from claude_compliance_api import cmd_compliance_org_settings

            cmd_compliance_org_settings(compliance_key, args.compliance_org_settings)
            return
        if args.compliance_groups_list:
            from claude_compliance_api import cmd_compliance_groups_list

            cmd_compliance_groups_list(compliance_key)
            return
        if args.compliance_group_members:
            from claude_compliance_api import cmd_compliance_group_members

            cmd_compliance_group_members(compliance_key, args.compliance_group_members)
            return
        if args.compliance_local_sessions_list:
            from claude_compliance_api import cmd_compliance_local_sessions_list

            cmd_compliance_local_sessions_list(
                compliance_key,
                since=args.compliance_sessions_since,
                until=args.compliance_sessions_until,
                limit=args.compliance_sessions_limit,
            )
            return
        if args.compliance_local_session_get:
            from claude_compliance_api import cmd_compliance_local_session_get

            cmd_compliance_local_session_get(compliance_key, args.compliance_local_session_get)
            return
        if args.compliance_local_session_messages:
            from claude_compliance_api import cmd_compliance_local_session_messages

            cmd_compliance_local_session_messages(compliance_key, args.compliance_local_session_messages)
            return
        if args.compliance_remote_sessions_list:
            from claude_compliance_api import cmd_compliance_remote_sessions_list

            cmd_compliance_remote_sessions_list(
                compliance_key,
                since=args.compliance_sessions_since,
                until=args.compliance_sessions_until,
                user_ids=user_ids,
                limit=args.compliance_sessions_limit,
            )
            return
        if args.compliance_remote_session_messages:
            from claude_compliance_api import cmd_compliance_remote_session_messages

            cmd_compliance_remote_session_messages(compliance_key, args.compliance_remote_session_messages)
            return

    if args.whoami:
        from claude_response_metadata import cmd_whoami

        key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            print("[ERROR] --whoami requires --api-key or ANTHROPIC_API_KEY", file=sys.stderr)
            return
        cmd_whoami(key)
        return

    if args.check_deprecated:
        from claude_models import cmd_check_deprecated

        cmd_check_deprecated(args.check_deprecated)
        return
    if args.upgrade_all:
        from claude_models import cmd_upgrade_all

        cmd_upgrade_all(
            args.upgrade_all,
            target=args.upgrade_target,
            apply=args.upgrade_yes,
            no_backup=args.upgrade_no_backup,
        )
        return

    if args.project_list:
        from projects import cmd_project_list

        cmd_project_list()
        return
    if args.project_templates:
        from projects import cmd_project_templates

        cmd_project_templates()
        return
    if args.project_show:
        from projects import cmd_project_show

        cmd_project_show(args.project_show)
        return
    if args.project_delete:
        from projects import ProjectManager

        ProjectManager().delete_project(args.project_delete)
        print("✓ Deleted.")
        return
    if args.project_archive:
        from projects import ProjectManager

        ProjectManager().archive_project(args.project_archive)
        print("✓ Archived.")
        return
    if args.project_create:
        from projects import cmd_project_create

        cmd_project_create(args.project_create, args.project_desc, args.project_template)
        return
    if args.project_add_task:
        from projects import cmd_project_add_task

        cmd_project_add_task(
            args.project_add_task,
            args.task_title or args.prompt or "",
            args.task_desc,
            args.task_agent,
            args.task_priority,
        )
        return
    if args.artifact_types:
        from artifacts import cmd_artifact_types

        cmd_artifact_types()
        return
    if args.artifact_list:
        from artifacts import cmd_artifact_list

        cmd_artifact_list(
            query=args.artifact_query,
            artifact_type=args.artifact_type if args.artifact_type != "code" else "",
            project_id=args.artifact_project,
            tag=args.tag,
        )
        return
    if args.artifact_show:
        from artifacts import cmd_artifact_show

        cmd_artifact_show(args.artifact_show, args.artifact_version)
        return
    if args.artifact_export:
        from artifacts import cmd_artifact_export

        cmd_artifact_export(args.artifact_export, args.output or "", args.artifact_version)
        return
    if args.artifact_export_all:
        from artifacts import cmd_artifact_export_all

        cmd_artifact_export_all(args.artifact_export_all, args.artifact_output_dir)
        return
    if args.artifact_diff:
        from artifacts import cmd_artifact_diff

        cmd_artifact_diff(args.artifact_diff, args.v1, args.v2)
        return
    if args.artifact_delete:
        from artifacts import cmd_artifact_delete

        cmd_artifact_delete(args.artifact_delete)
        return
    if args.artifact_tag:
        from artifacts import cmd_artifact_tag

        cmd_artifact_tag(args.artifact_tag, args.tag)
        return
    if args.artifact_attach:
        from artifacts import cmd_artifact_attach

        cmd_artifact_attach(args.artifact_attach, args.to_project)
        return
    if args.list_server_tools:
        from claude_tools import cmd_list_server_tools

        cmd_list_server_tools()
        return

    if args.mid_conv_tool_check:
        from claude_tools import (
            MID_CONVERSATION_TOOL_CHANGES_SUPPORTED,
            validate_mid_conversation_tool_change,
        )

        model_id = args.mid_conv_tool_check
        warning = validate_mid_conversation_tool_change(model_id)
        if warning is None:
            print(
                f"\033[92m✓ {model_id} supports mid-conversation tool changes\033[0m "
                f"(mid-conversation-tool-changes-2026-07-01 beta)"
            )
        else:
            print(f"\033[93m⚠ {warning}\033[0m")
            print(f"  Supported models: {', '.join(sorted(MID_CONVERSATION_TOOL_CHANGES_SUPPORTED))}")
        return
    if args.cowork_list:
        from cowork import cmd_cowork_list

        cmd_cowork_list()
        return
    if args.agent_list_sessions:
        from claude_agents_sdk import cmd_agent_list_sessions

        cmd_agent_list_sessions()
        return
    if args.list_tool_presets:
        from claude_agents_sdk import cmd_list_tool_presets

        cmd_list_tool_presets()
        return
    if args.code_agent_list_sessions:
        from claude_code import cmd_code_list_sessions

        cmd_code_list_sessions()
        return
    if args.code_agent_list_tools:
        from claude_code import cmd_code_list_tools

        cmd_code_list_tools()
        return

    # ── New in v1.10.0 — no API key required ──
    if args.memory_add:
        from claude_memory import cmd_memory_add

        cmd_memory_add(
            args.memory_add, args.memory_type, args.memory_tags, args.memory_importance, args.memory_ns
        )
        return
    if args.memory_recall:
        from claude_memory import cmd_memory_recall

        cmd_memory_recall(args.memory_recall, args.memory_ns)
        return
    if args.memory_forget:
        from claude_memory import cmd_memory_forget

        cmd_memory_forget(args.memory_forget, args.memory_ns)
        return
    if args.memory_stats:
        from claude_memory import cmd_memory_stats

        cmd_memory_stats(args.memory_ns)
        return
    if args.memory_retention:
        from claude_memory import cmd_memory_retention

        cmd_memory_retention(args.memory_ns)
        return
    if args.sessions_list:
        from claude_sessions import cmd_sessions_list

        cmd_sessions_list()
        return
    if args.session_show:
        from claude_sessions import cmd_session_show

        cmd_session_show(args.session_show)
        return
    if args.checkpoint_list:
        from claude_sessions import cmd_checkpoint_list

        cmd_checkpoint_list(args.checkpoint_list)
        return
    if args.away_summary:
        from claude_sessions import cmd_away_summary

        cmd_away_summary(args.away_summary)
        return
    if args.rag_index and args.rag_folder:
        from claude_rag import cmd_rag_index

        cmd_rag_index(args.rag_index, args.rag_folder)
        return
    if args.rag_list:
        from claude_rag import cmd_rag_list

        cmd_rag_list()
        return
    if args.eval_list:
        from claude_eval import cmd_eval_list

        cmd_eval_list()
        return
    if args.eval_scaffold:
        from claude_eval import cmd_eval_scaffold

        cmd_eval_scaffold(args.eval_scaffold)
        return
    if args.cost_summary:
        from claude_cost_optimizer import cmd_cost_summary

        cmd_cost_summary()
        return
    if args.cost_reset:
        from claude_cost_optimizer import cmd_cost_reset

        cmd_cost_reset()
        return
    if args.metrics_show:
        from claude_metrics import cmd_metrics_show

        cmd_metrics_show(today_only=args.metrics_today, model_filter=args.metrics_model or None)
        return
    if args.metrics_clear:
        from claude_metrics import cmd_metrics_clear

        cmd_metrics_clear()
        return
    if args.metrics_export:
        from claude_metrics import cmd_metrics_export

        cmd_metrics_export(args.metrics_export, today_only=args.metrics_today)
        return
    if args.obs_latency:
        from claude_observability import cmd_obs_latency

        cmd_obs_latency(args.obs_hours)
        return
    if args.obs_tail is not None:
        from claude_observability import cmd_obs_tail

        cmd_obs_tail(args.obs_tail)
        return
    if args.obs_clear:
        from claude_observability import cmd_obs_clear

        cmd_obs_clear()
        return
    if args.workflow_scaffold:
        from claude_workflow import cmd_workflow_scaffold

        cmd_workflow_scaffold(args.workflow_scaffold)
        return
    if args.hooks_add:
        from claude_hooks_perms_plan import cmd_hooks_add

        cmd_hooks_add(args.hooks_add[0], args.hooks_add[1], args.hook_tool_match)
        return
    if args.hooks_list:
        from claude_hooks_perms_plan import cmd_hooks_list

        cmd_hooks_list()
        return
    if args.hooks_remove is not None:
        from claude_hooks_perms_plan import cmd_hooks_remove

        cmd_hooks_remove(args.hooks_remove)
        return
    if args.perms_list:
        from claude_hooks_perms_plan import cmd_perms_list

        cmd_perms_list()
        return
    if args.perms_add:
        from claude_hooks_perms_plan import cmd_perms_add

        cmd_perms_add(args.perms_add[0], args.perms_add[1], args.perms_reason)
        return

    if args.tui:
        from tui import run_tui

        run_tui(api_key=getattr(args, "api_key", None) or os.getenv("ANTHROPIC_API_KEY", ""))
        return

    # ── API key required ──
    key = _api_key(args)
    model = _model(args)

    if args.interactive:
        from claude_interactive import cmd_interactive

        cmd_interactive(
            key,
            model,
            system=args.interactive_system,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            personality_style=args.personality,
        )
        return

    if args.excel is not None:
        from claude_excel import cmd_excel_chat

        cmd_excel_chat(
            key,
            model,
            input_path=args.excel or None,
            output_path=args.excel_output,
            sheet_name=args.excel_sheet,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            native=args.excel_native,
        )
        return

    if args.pptx is not None:
        from claude_powerpoint import cmd_pptx_chat

        cmd_pptx_chat(
            key,
            model,
            input_path=args.pptx or None,
            output_path=args.pptx_output,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            native=args.pptx_native,
        )
        return

    if args.browse:
        if not args.browse_task:
            print("[ERROR] --browse requires --browse-task", file=sys.stderr)
            sys.exit(1)
        from claude_chrome import cmd_browse

        cmd_browse(
            key,
            model,
            args.browse,
            args.browse_task,
            max_steps=args.browse_max_steps,
            allowed_domains=args.browse_allow_domains,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        return

    if args.list_models:
        from claude_models import cmd_list_models

        cmd_list_models(key, include_legacy=getattr(args, "list_models_legacy", False))
        return
    if args.model_info:
        from claude_models import cmd_model_info

        cmd_model_info(args.model_info, key)
        return
    if args.fable5:
        from claude_fable5 import cmd_fable5_call, parse_fallback_chain

        try:
            chain = parse_fallback_chain(getattr(args, "fable5_fallback_chain", None))
        except ValueError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        cmd_fable5_call(
            args.fable5,
            key,
            fallback_model=args.fallback_model,
            allow_fallback=not args.fable5_no_fallback,
            fallback_chain=chain,
        )
        return
    if args.mythos5:
        from claude_mythos5 import cmd_mythos5_call

        cmd_mythos5_call(args.mythos5, key)
        return
    if args.opus5:
        from claude_opus5 import cmd_opus5_call

        cmd_opus5_call(
            args.opus5,
            key,
            effort=args.opus5_effort,
            disable_thinking=args.opus5_disable_thinking,
            fast=args.opus5_fast,
            use_geo=args.opus5_geo,
        )
        return
    if args.sonnet5:
        from claude_sonnet5 import cmd_sonnet5_call

        cmd_sonnet5_call(args.sonnet5, key, use_geo=args.sonnet5_geo)
        return
    if args.haiku45:
        from claude_haiku45 import cmd_haiku45_call

        cmd_haiku45_call(args.haiku45, key, thinking_budget=args.haiku45_thinking_budget)
        return

    # ── zai-live ──
    if args.live:
        from claude_live import cmd_live

        # --temperature was accepted by the parser but never reached cmd_live,
        # so live mode always used LiveSession's 0.7 default regardless of the
        # flag. Now threaded through (still safely dropped by sampling_kwargs()
        # for claude-sonnet-5 and later, which reject it).
        cmd_live(key, model=model, temperature=args.temperature)
        return

    # ── Deep Research ──
    if args.research:
        from claude_research import cmd_research

        cmd_research(
            args.research,
            key,
            model,
            depth=args.research_depth,
            source_urls=args.research_urls,
            output=args.output,
        )
        return

    # ── RAG (query needs the key for generation; index/list handled above) ──
    if args.rag_query:
        from claude_rag import cmd_rag_query

        cmd_rag_query(args.rag_index_name, args.rag_query, key, model, k=args.rag_k)
        return

    # ── Evaluation (run/compare call the model; list/scaffold handled above) ──
    if args.eval_run:
        from claude_eval import cmd_eval_run

        cmd_eval_run(args.eval_run, key, model, threshold=args.eval_threshold, output=args.output)
        return
    if args.eval_compare:
        from claude_eval import cmd_eval_compare

        cmd_eval_compare(
            args.eval_run or args.eval_scaffold or "", args.eval_compare[0], args.eval_compare[1], key
        )
        return

    # ── Git Integration ──
    if args.git_commit:
        from claude_git import cmd_git_commit

        cmd_git_commit(key, model, style=args.git_commit_style, write=args.git_commit_write)
        return
    if args.git_pr:
        from claude_git import cmd_git_pr

        cmd_git_pr(args.git_pr[0], args.git_pr[1], key, model)
        return
    if args.git_changelog:
        from claude_git import cmd_git_changelog

        cmd_git_changelog(args.git_changelog, key, model, output=args.output)
        return
    if args.git_review:
        from claude_git import cmd_git_review

        cmd_git_review(key, model)
        return
    if args.git_blame_explain:
        from claude_git import cmd_git_blame_explain

        f, s, e = args.git_blame_explain  # type: ignore[misc]
        cmd_git_blame_explain(f, int(s), int(e), key, model)
        return

    # ── GitHub Integration ──
    if args.gh_review_pr:
        from claude_github import cmd_gh_review_pr

        cmd_gh_review_pr(args.gh_review_pr, args.gh_token or None, key, model)
        return
    if args.gh_triage_issues:
        from claude_github import cmd_gh_triage

        cmd_gh_triage(args.gh_triage_issues, args.gh_max_items, args.gh_token or None, key, model)
        return
    if args.gh_summarise_commits:
        from claude_github import cmd_gh_commits

        cmd_gh_commits(args.gh_summarise_commits, args.gh_max_items, args.gh_token or None, key, model)
        return
    if args.gh_pr_description:
        from claude_github import cmd_gh_pr_description

        cmd_gh_pr_description(args.gh_pr_description, args.gh_token or None, key, model)
        return

    # ── Multi-Agent Router ──
    if args.route_list:
        from claude_router import cmd_route_list

        cmd_route_list()
        return
    if args.route:
        from claude_router import cmd_route

        cmd_route(args.route, key, model, explain=args.route_explain, parallel=args.route_parallel)
        return

    # ── Prompt Optimizer ──
    if args.prompt_lib_list:
        from claude_prompt_optimizer import cmd_prompt_lib_list

        cmd_prompt_lib_list()
        return
    if args.prompt_lib_get:
        from claude_prompt_optimizer import lib_get

        found = lib_get(args.prompt_lib_get)
        print(found if found is not None else f"No prompt saved under tag '{args.prompt_lib_get}'")
        return
    if args.prompt_lib_add:
        from claude_prompt_optimizer import lib_add

        if not args.prompt:
            print("\033[91m--prompt-lib-add requires --prompt\033[0m")
            return
        import time as _time

        tag = lib_add(args.prompt, args.tag or _time.strftime("%Y%m%d-%H%M%S"))
        print(f"Saved to prompt library under tag '{tag}'")
        return
    if args.ab_test:
        from claude_prompt_optimizer import cmd_ab_test

        if not (args.prompt and args.ab_prompt_b):
            print("\033[91m--ab-test requires --prompt (variant A) and --ab-prompt-b " "(variant B)\033[0m")
            return
        cmd_ab_test(args.prompt, args.ab_prompt_b, args.ab_task, key, model)
        return
    if args.score_prompt:
        from claude_prompt_optimizer import cmd_score

        cmd_score(args.score_prompt, key, model)
        return
    if args.prompt_optimize:
        from claude_prompt_optimizer import cmd_optimize

        cmd_optimize(args.prompt_optimize, key, model)
        return

    # ── Cost Optimizer (optimized calls the model; summary/reset handled above) ──
    if args.optimized:
        from claude_cost_optimizer import cmd_optimized

        cmd_optimized(args.optimized, key, verbose=True, force_model=args.force_model)
        return

    # ── Observability (errors needs the model for analysis; rest handled above) ──
    if args.obs_errors:
        from claude_observability import cmd_obs_errors

        cmd_obs_errors(key, model, args.obs_hours)
        return

    # ── Workflows (run calls the model; scaffold handled above) ──
    if args.workflow_run:
        from claude_workflow import cmd_workflow_run

        cmd_workflow_run(args.workflow_run, key, input_text=args.workflow_input, output=args.output)
        return

    # ── Plan Mode ──
    if args.plan:
        from claude_hooks_perms_plan import cmd_plan

        cmd_plan(
            args.plan, key, model, context=args.plan_context, execute=args.plan_execute, output=args.output
        )
        return

    if args.thinking or args.adaptive or args.effort_legacy_budget:
        from claude_thinking import ThinkingModeError, cmd_thinking

        prompt = args.prompt or (args.file and _read_file(args.file)) or ""
        try:
            cmd_thinking(
                prompt=prompt,
                api_key=key,
                model=model,
                budget=args.thinking_budget,
                effort=args.effort or None,
                adaptive=(True if args.adaptive else None),
                legacy_budget=args.effort_legacy_budget,
                show_thinking=args.show_thinking,
                stream=args.stream,
                display_omitted=args.thinking_display_omitted,
            )
        except ThinkingModeError as e:
            print(f"\033[91m✗ {e}\033[0m", file=sys.stderr)
            sys.exit(1)
        return
    if args.stream:
        from claude_stream import cmd_stream

        cmd_stream(
            args.prompt or "",
            key,
            model,
            file_content=_read_file(args.file) if args.file else None,
            show_thinking=args.show_thinking,
        )
        return
    if args.web_search or args.web_fetch:
        from claude_search import cmd_web_search

        cmd_web_search(
            args.prompt or "",
            key,
            model,
            max_searches=args.max_searches,
            show_citations=not args.no_citations,
            web_fetch=args.web_fetch,
            response_inclusion=args.response_inclusion or None,
        )
        return
    if args.fetch_url:
        from claude_search import cmd_fetch_url

        cmd_fetch_url(args.fetch_url, args.prompt or "", key, model)
        return
    if args.vision:
        from claude_vision import cmd_vision

        cmd_vision(
            args.vision, args.prompt or "", key, model, is_code=args.vision_code, language=args.vision_lang
        )
        return
    if args.vision_pdf:
        from claude_vision import cmd_vision_pdf

        cmd_vision_pdf(args.vision_pdf, args.prompt or "", key, model)
        return
    if args.vision_url:
        from claude_vision import cmd_vision_url

        cmd_vision_url(args.vision_url, args.prompt or "", key, model)
        return
    if args.vision_compare:
        from claude_vision import cmd_vision_compare

        cmd_vision_compare(args.vision_compare, args.prompt or "", key, model)
        return
    if args.vision_ocr:
        from claude_vision import cmd_vision_ocr

        cmd_vision_ocr(args.vision_ocr, key, model)
        return
    if args.batch_submit:
        from claude_batch import cmd_batch_submit

        cmd_batch_submit(args.batch_submit, key, model, use_300k_output=args.batch_300k_output)
        return
    if args.batch_status:
        from claude_batch import cmd_batch_status

        cmd_batch_status(args.batch_status, key)
        return
    if args.batch_results:
        from claude_batch import cmd_batch_results

        cmd_batch_results(args.batch_results, key, save_to=args.output or None)
        return
    if args.batch_cancel:
        from claude_batch import cmd_batch_cancel

        cmd_batch_cancel(args.batch_cancel, key)
        return
    if args.batch_list:
        from claude_batch import cmd_batch_list

        cmd_batch_list(key)
        return
    if args.batch_generate > 0:
        from claude_batch import cmd_batch_generate

        cmd_batch_generate(args.prompt or "", args.batch_generate, key, model, wait=args.batch_wait)
        return
    if args.cache_warm:
        from claude_cache import cmd_cache_warm

        cmd_cache_warm(
            key, model, system=args.cache_system or None, doc_files=args.cache_docs or [], ttl=args.cache_ttl
        )
        return
    if args.cache_multi_turn:
        from claude_cache import cmd_cache_multi_turn

        cmd_cache_multi_turn(
            args.cache_multi_turn,
            key,
            model,
            system=args.cache_system or None,
            ttl=args.cache_ttl,
            mid_system=args.cache_mid_system or None,
            mid_system_after=args.cache_mid_system_after,
            show_stats=args.cache_stats,
        )
        return
    if args.cache:
        from claude_cache import cmd_cache_generate

        docs = [open(f).read() for f in (args.cache_docs or [])]
        cmd_cache_generate(
            args.prompt or "",
            key,
            model,
            system=args.cache_system or None,
            docs=docs,
            ttl=args.cache_ttl,
            show_stats=args.cache_stats,
            diagnose=args.cache_diagnose,
        )
        return
    if args.tool_agent:
        from claude_tools import cmd_tool_agent

        cmd_tool_agent(args.prompt or "", key, model, max_turns=args.max_turns)
        return
    if args.server_tool:
        from claude_tools import cmd_server_tool

        extra_tool_defs = None
        if args.file:
            import json as _json

            extra_tool_defs = _json.loads(_read_file(args.file))
            if isinstance(extra_tool_defs, dict):
                extra_tool_defs = [extra_tool_defs]
        cmd_server_tool(
            args.prompt or "",
            [t.strip() for t in args.server_tool.split(",")],
            key,
            model,
            use_context_management=args.context_management,
            use_compaction=args.compaction,
            task_budget_tokens=args.task_budget or None,
            use_ptc=args.ptc,
            extra_tool_defs=extra_tool_defs,
        )
        return
    if args.memory_agent:
        from claude_tools import cmd_memory_agent

        cmd_memory_agent(args.memory_agent, key, model, memory_dir=args.memory_dir, max_turns=args.max_turns)
        return
    if args.advisor:
        from claude_advisor import cmd_advisor

        cmd_advisor(
            args.advisor,
            key,
            model,
            advisor_model=args.advisor_model,
            max_uses=args.advisor_max_uses or None,
            advisor_max_tokens=args.advisor_max_tokens or None,
        )
        return
    if args.embed:
        from claude_embeddings import cmd_embed

        cmd_embed(args.embed, model=args.embed_model, input_type=args.embed_input_type)
        return
    if args.embed_file:
        from claude_embeddings import cmd_embed_file

        cmd_embed_file(args.embed_file, model=args.embed_model, input_type=args.embed_input_type)
        return
    if args.embed_similarity:
        from claude_embeddings import cmd_embed_similarity

        cmd_embed_similarity(args.embed_similarity[0], args.embed_similarity[1], model=args.embed_model)
        return
    if args.stream_tools:
        import json as _json

        from claude_stream import cmd_stream_tools

        tool_defs = _json.loads(_read_file(args.file)) if args.file else []
        if isinstance(tool_defs, dict):
            tool_defs = [tool_defs]
        cmd_stream_tools(args.stream_tools, tool_defs, key, model)
        return
    if args.structured:
        from claude_structured import cmd_structured

        cmd_structured(
            args.prompt or "", key, model, schema_path=args.schema, schema_inline=args.schema_inline
        )
        return
    if args.structured_analyse:
        from claude_structured import cmd_structured_analyse

        cmd_structured_analyse(args.structured_analyse, key, model)
        return
    if args.structured_extract:
        from claude_structured import cmd_structured_extract

        cmd_structured_extract(args.structured_extract, args.schema, key, model)
        return
    if args.file_upload:
        from claude_files import cmd_file_upload

        cmd_file_upload(args.file_upload, key, model)
        return
    if args.file_list:
        from claude_files import cmd_file_list

        cmd_file_list(key, model)
        return
    if args.file_delete:
        from claude_files import cmd_file_delete

        cmd_file_delete(args.file_delete, key)
        return
    if args.file_ask:
        from claude_files import cmd_file_ask

        cmd_file_ask(args.file_ask, args.prompt or "Summarise.", key, model, media_type=args.file_media_type)
        return
    if args.file_download:
        from claude_files import cmd_file_download

        cmd_file_download(
            args.file_download, args.file_output or args.output or f"{args.file_download}.bin", key
        )
        return
    if args.code_exec:
        from claude_code_exec import cmd_code_exec

        cmd_code_exec(
            args.prompt or "",
            key,
            model,
            output_dir=args.code_exec_output or None,
            code_exec_version=args.code_exec_version,
        )
        return
    if args.code_debug:
        from claude_code_exec import cmd_code_debug

        cmd_code_debug(args.code_debug, key, model, code_exec_version=args.code_exec_version)
        return
    if args.count_tokens:
        from claude_tokens import cmd_count_tokens

        cmd_count_tokens(args.prompt or "", key, model, file_path=args.file, budget=args.count_budget or None)
        return
    if args.cite:
        from claude_citations import cmd_cite

        cmd_cite(args.prompt or "", args.cite, key, model)
        return
    if args.rag:
        from claude_citations import cmd_rag

        cmd_rag(args.prompt or "", args.rag, key, model, pattern=args.rag_pattern)
        return
    if args.computer_use:
        from claude_models import cmd_computer_use

        cmd_computer_use(args.computer_use, key, model)
        return
    if args.interleaved_thinking:
        from claude_models import cmd_adaptive_thinking

        cmd_adaptive_thinking(args.prompt or "", key, model, effort=args.effort or "medium")
        return
    if args.agent_session or args.agent_orchestrate:
        from claude_agents_sdk import cmd_agent_chat, cmd_agent_orchestrate

        if args.agent_orchestrate:
            cmd_agent_orchestrate(args.prompt or "", key, model, session_id=args.agent_session)
        else:
            cmd_agent_chat(args.prompt or "", key, model, session_id=args.agent_session)
        return
    if args.agent_dream:
        from claude_agents_sdk import cmd_agent_dream

        sess_ids = [s.strip() for s in args.agent_dream_sessions.split(",") if s.strip()] or None
        cmd_agent_dream(
            args.agent_dream,
            key,
            model=model,
            session_ids=sess_ids,
            instructions=args.agent_dream_instructions or None,
        )
        return
    if args.agent_dream_get:
        from claude_agents_sdk import cmd_agent_dream_get

        cmd_agent_dream_get(args.agent_dream_get, key)
        return
    if args.agent_dream_cancel:
        from claude_agents_sdk import cmd_agent_dream_cancel

        cmd_agent_dream_cancel(args.agent_dream_cancel, key)
        return
    if args.agent_dream_archive:
        from claude_agents_sdk import cmd_agent_dream_archive

        cmd_agent_dream_archive(args.agent_dream_archive, key)
        return
    if args.agent_dream_list:
        from claude_agents_sdk import cmd_agent_dream_list

        cmd_agent_dream_list(
            key,
            include_archived=args.agent_dream_list_include_archived,
            limit=args.agent_dream_list_limit,
            page=args.agent_dream_list_page or None,
        )
        return
    if args.agent_webhook_register:
        from claude_agents_sdk import cmd_agent_webhook_register

        events = [e.strip() for e in args.agent_webhook_events.split(",") if e.strip()] or None
        cmd_agent_webhook_register(args.agent_webhook_register, key, events=events)
        return
    if args.agent_vault_create:
        from claude_agents_sdk import cmd_agent_vault_create

        cmd_agent_vault_create(
            args.agent_vault_create, key, external_user_id=args.agent_vault_external_user or None
        )
        return
    if args.agent_vault_add_credential:
        from claude_agents_sdk import cmd_agent_vault_add_credential

        if not args.agent_vault_cred_type:
            print("[ERROR] --agent-vault-add-credential requires --agent-vault-cred-type")
            sys.exit(1)
        domains = [d.strip() for d in args.agent_vault_allowed_domains.split(",") if d.strip()] or None
        cmd_agent_vault_add_credential(
            args.agent_vault_add_credential,
            args.agent_vault_cred_type,
            key,
            mcp_server_url=args.agent_vault_mcp_url or None,
            secret_name=args.agent_vault_secret_name or None,
            secret_value=args.agent_vault_secret,
            allowed_domains=domains,
            injection_location=args.agent_vault_injection_location or None,
        )
        return
    if args.agent_vault_list:
        from claude_agents_sdk import cmd_agent_vault_list

        cmd_agent_vault_list(key)
        return
    if args.agent_schedule_create:
        from claude_agents_sdk import cmd_agent_schedule_create

        if not args.agent_schedule_env or not args.agent_schedule_cron:
            print(
                "[ERROR] --agent-schedule-create requires --agent-schedule-env " "and --agent-schedule-cron"
            )
            sys.exit(1)
        cmd_agent_schedule_create(
            args.agent_schedule_create,
            args.agent_schedule_env,
            args.agent_schedule_cron,
            key,
            timezone=args.agent_schedule_tz,
            task=args.agent_schedule_task,
        )
        return
    if args.agent_schedule_list:
        from claude_agents_sdk import cmd_agent_schedule_list

        cmd_agent_schedule_list(key)
        return
    if args.agent_schedule_cancel:
        from claude_agents_sdk import cmd_agent_schedule_cancel

        cmd_agent_schedule_cancel(args.agent_schedule_cancel, key)
        return
    if args.agent_review_multiagent:
        from claude_agents_sdk import cmd_agent_review_multiagent

        specialists = [s.strip() for s in args.agent_review_specialists.split(",") if s.strip()]
        cmd_agent_review_multiagent(args.agent_review_multiagent, specialists, key, model=model)
        return
    if args.agent_outcome_rubric_upload:
        from claude_agents_sdk import cmd_agent_outcome_rubric_upload

        cmd_agent_outcome_rubric_upload(args.agent_outcome_rubric_upload, key, model)
        return
    if args.agent_env_self_hosted:
        from claude_agents_sdk import cmd_agent_env_self_hosted_create

        cmd_agent_env_self_hosted_create(args.agent_env_self_hosted, key)
        return
    if args.agent_env_work_stats:
        from claude_agents_sdk import cmd_agent_env_work_stats

        cmd_agent_env_work_stats(args.agent_env_work_stats, key)
        return
    if args.agent_managed_run:
        # Real hosted Claude Managed Agents API (/v1/agents, /v1/environments,
        # /v1/sessions) — distinct from --agent-session above, which runs a
        # local agent loop over the plain Messages API. See
        # claude_agents_sdk.ManagedAgentsClient.
        from claude_agents_sdk import cmd_managed_agent_run

        outcome_rubric_text = None
        if args.agent_outcome_rubric:
            outcome_rubric_text = Path(args.agent_outcome_rubric).read_text(encoding="utf-8")
        if args.agent_outcome and not outcome_rubric_text and not args.agent_outcome_rubric_file:
            print(
                "[ERROR] --agent-outcome requires --agent-outcome-rubric FILE "
                "or --agent-outcome-rubric-file FILE_ID"
            )
            sys.exit(1)
        agent_overrides = None
        if args.agent_override_json:
            import json as _json

            agent_overrides = _json.loads(Path(args.agent_override_json).read_text(encoding="utf-8"))
        if args.agent_override_model or args.agent_override_system:
            agent_overrides = agent_overrides or {}
            if args.agent_override_model:
                agent_overrides["model"] = args.agent_override_model
            if args.agent_override_system:
                agent_overrides["system"] = args.agent_override_system
        cmd_managed_agent_run(
            args.agent_managed_run,
            key,
            model=model,
            memory_store=args.agent_memory_store or None,
            outcome_description=args.agent_outcome or None,
            outcome_rubric=outcome_rubric_text,
            outcome_rubric_file_id=args.agent_outcome_rubric_file or None,
            outcome_max_iterations=args.agent_outcome_max_iter,
            vault_id=args.agent_vault or None,
            agent_overrides=agent_overrides,
            stream_deltas=args.agent_stream_deltas,
            budget_usd_cents=(
                round(args.agent_session_budget_usd * 100) if args.agent_session_budget_usd else None
            ),
        )
        return
    if args.agent_create:
        from claude_agents_sdk import cmd_agent_create

        cmd_agent_create(
            args.agent_create,
            key,
            model=model,
            system=args.agent_system,
            effort=args.agent_effort or None,
            inference_geo=args.agent_inference_geo or None,
        )
        return
    if args.agent_get:
        from claude_agents_sdk import cmd_agent_get

        cmd_agent_get(args.agent_get, key, version=args.agent_get_version)
        return
    if args.agent_list:
        from claude_agents_sdk import cmd_agent_list

        cmd_agent_list(key, limit=args.agent_list_limit)
        return
    if args.agent_update:
        from claude_agents_sdk import cmd_agent_update

        cmd_agent_update(
            args.agent_update,
            key,
            model=model if model else None,
            effort=args.agent_effort or None,
            system=args.agent_system or None,
            inference_geo=args.agent_inference_geo or None,
        )
        return
    if args.agent_session_get:
        from claude_agents_sdk import cmd_agent_session_get

        cmd_agent_session_get(args.agent_session_get, key)
        return
    if args.agent_session_budget_set:
        from claude_agents_sdk import cmd_agent_session_budget_set

        if not args.agent_session_budget_usd:
            print("[ERROR] --agent-session-budget-set requires " "--agent-session-budget-usd DOLLARS")
            sys.exit(1)
        cmd_agent_session_budget_set(
            args.agent_session_budget_set, key, round(args.agent_session_budget_usd * 100)
        )
        return
    if args.agent_session_budget_remove:
        from claude_agents_sdk import cmd_agent_session_budget_remove

        cmd_agent_session_budget_remove(args.agent_session_budget_remove, key)
        return
    if args.agent_memory_store_create:
        from claude_agents_sdk import cmd_agent_memory_store_create

        if not args.agent_memory_store:
            print("[ERROR] --agent-memory-store-create requires --agent-memory-store NAME")
            sys.exit(1)
        cmd_agent_memory_store_create(args.agent_memory_store, key)
        return
    if args.agent_memory_list:
        from claude_agents_sdk import cmd_agent_memory_list

        depth = int(args.agent_memory_depth) if args.agent_memory_depth else None
        cmd_agent_memory_list(
            args.agent_memory_list, key, path_prefix=args.agent_memory_path_prefix or None, depth=depth
        )
        return
    if args.agent_memory_stores_list:
        from claude_agents_sdk import cmd_agent_memory_stores_list

        cmd_agent_memory_stores_list(key, include_archived=args.agent_memory_stores_include_archived)
        return
    if args.agent_memory_store_archive:
        from claude_agents_sdk import cmd_agent_memory_store_archive

        cmd_agent_memory_store_archive(args.agent_memory_store_archive, key)
        return
    if args.agent_memory_store_delete:
        from claude_agents_sdk import cmd_agent_memory_store_delete

        cmd_agent_memory_store_delete(
            args.agent_memory_store_delete, key, confirm=args.agent_memory_store_delete_yes
        )
        return
    if args.agent_memory_get:
        from claude_agents_sdk import cmd_agent_memory_get

        if not args.agent_memory_id:
            print("[ERROR] --agent-memory-get requires --agent-memory-id")
            sys.exit(1)
        cmd_agent_memory_get(args.agent_memory_get, args.agent_memory_id, key)
        return
    if args.agent_memory_create:
        from claude_agents_sdk import cmd_agent_memory_create

        if not args.agent_memory_path or not args.agent_memory_content:
            print("[ERROR] --agent-memory-create requires --agent-memory-path " "and --agent-memory-content")
            sys.exit(1)
        cmd_agent_memory_create(
            args.agent_memory_create, args.agent_memory_path, args.agent_memory_content, key
        )
        return
    if args.agent_memory_update:
        from claude_agents_sdk import cmd_agent_memory_update

        if not args.agent_memory_id:
            print("[ERROR] --agent-memory-update requires --agent-memory-id")
            sys.exit(1)
        cmd_agent_memory_update(
            args.agent_memory_update,
            args.agent_memory_id,
            key,
            content=args.agent_memory_content or None,
            path=args.agent_memory_path or None,
        )
        return
    if args.agent_memory_delete:
        from claude_agents_sdk import cmd_agent_memory_delete

        if not args.agent_memory_id:
            print("[ERROR] --agent-memory-delete requires --agent-memory-id")
            sys.exit(1)
        cmd_agent_memory_delete(
            args.agent_memory_delete, args.agent_memory_id, key, confirm=args.agent_memory_delete_yes
        )
        return
    if args.cowork:
        from cowork import cmd_cowork

        prompt = args.cowork_prompt or args.prompt or ""
        if not prompt:
            print("[ERROR] --cowork requires -p or --cowork-prompt")
            sys.exit(1)
        cmd_cowork(
            args.cowork,
            prompt,
            key,
            model,
            files=args.cowork_files,
            depth=args.cowork_depth,
            output_fmt=args.cowork_format,
            output_file=args.output,
        )
        return

    # Claude Code commands
    if args.code_agent_mcp_tunnel:
        from claude_agents_sdk import cmd_mcp_tunnel_open

        cmd_mcp_tunnel_open(key, args.code_agent_mcp_tunnel)
        return
    if args.code_agent or args.code_agent_session or args.code_agent_resume:
        from claude_code import cmd_code_agent

        prompt = args.prompt or ""
        if not prompt:
            print("[ERROR] --code-agent requires -p PROMPT")
            sys.exit(1)
        cmd_code_agent(
            prompt=prompt,
            api_key=key,
            model=model,
            cwd=args.code_agent_cwd,
            tools=args.code_agent_tools,
            permission=args.code_agent_permission,
            session_id=args.code_agent_session or args.code_agent_resume,
            system=args.code_agent_system,
            mcp_urls=args.code_agent_mcp or [],
            output_mode=args.code_agent_output,
            hooks_file=args.code_agent_hooks,
            checkpoint=args.code_agent_checkpoint,
            output_file=args.output,
            output_style=args.code_agent_output_style,
            sandbox=args.code_agent_sandbox,
            sandbox_allow_net=args.code_agent_sandbox_allow_net,
            sandbox_roots=args.code_agent_sandbox_roots or [],
            headless=args.code_agent_headless,
            agent_context_editing=args.agent_context_editing,
        )
        return
    if args.code_agent_subagent:
        from claude_code import cmd_code_subagent

        cmd_code_subagent(args.code_agent_subagent, key, model, cwd=args.code_agent_cwd)
        return
    if args.code_agent_todo:
        from claude_code import cmd_code_todo

        cmd_code_todo(args.code_agent_todo, key, model)
        return
    if args.code_agent_slash:
        from claude_code import cmd_code_slash

        cmd_code_slash(args.code_agent_slash, key, model, cwd=args.code_agent_cwd, prompt=args.prompt or "")
        return
    if args.code_agent_cost:
        from claude_code import cmd_code_cost

        cmd_code_cost(key)
        return

    if args.project_plan:
        from coder import Coder
        from projects import cmd_project_plan

        cmd_project_plan(args.project_plan, Coder(api_key=key, model=model))
        return
    if args.project_run:
        from coder import Coder
        from projects import cmd_project_run

        cmd_project_run(args.project_run, args.task or "all", Coder(api_key=key, model=model))
        return
    if args.artifact_create:
        from artifacts import cmd_artifact_create
        from coder import Coder

        if not args.prompt:
            print("[ERROR] --artifact-create requires -p")
            sys.exit(1)
        tags = [t.strip() for t in args.artifact_tags.split(",") if t.strip()]
        cmd_artifact_create(
            args.artifact_create,
            args.prompt,
            artifact_type=args.artifact_type,
            language=args.artifact_lang,
            tags=tags,
            project_id=args.artifact_project,
            coder=Coder(api_key=key, model=model),
        )
        return
    if args.artifact_iterate:
        from artifacts import cmd_artifact_iterate
        from coder import Coder

        cmd_artifact_iterate(args.artifact_iterate, args.prompt or "", Coder(api_key=key, model=model))
        return

    if args.prompt or args.file:
        from coder import Coder

        c = Coder(
            api_key=key,
            model=model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            service_tier=args.service_tier,
            inference_geo=args.inference_geo,
            fast_mode=args.fast_mode,
            # Previously never sourced from a CLI flag at all — see
            # the Skills & Agents arg group comment above.
            personality_style=args.personality,
        )
        # --skill and --agent now actually affect the request: each
        # contributes a system-prompt fragment instead of being accepted
        # and discarded.
        system_parts = []
        if args.skill:
            from skills import SkillManager

            skill = SkillManager().get_skill(args.skill)
            if skill:
                system_parts.append(f"Skill focus — {skill['name']}: {skill['description']}")
            else:
                print(
                    f"\033[93m⚠ Unknown --skill '{args.skill}' (see --list-skills); ignoring.\033[0m",
                    file=sys.stderr,
                )
        if args.agent:
            system_parts.append(AGENT_SYSTEM_PROMPTS[args.agent])
        system = "\n\n".join(system_parts) or None

        result = c.generate(
            args.prompt or "", system=system, file_content=_read_file(args.file) if args.file else None
        )
        print(result)
        if args.output:
            open(args.output, "w").write(result)
        return
