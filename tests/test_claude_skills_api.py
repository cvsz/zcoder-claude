"""tests/test_claude_skills_api.py

Covers claude_skills_api.py: SkillRef wire-format, the container.skills
builder, the multi-turn client used by --excel-native/--pptx-native, the
file_id extraction helper, and the two info-only CLI commands.
"""

import pytest

import infrastructure.anthropic_api.skills_api_gateway as gateway_module
from domain.skills_api import (
    CODE_EXECUTION_BETA,
    FILES_API_BETA,
    PREBUILT_SKILLS,
    SKILLS_BETA,
    SkillRef,
    build_container_skills,
    build_user_content,
    extract_output_file_ids,
)
from domain.skills_api import (
    list_prebuilt_skills as list_skills,
)
from infrastructure.anthropic_api.skills_api_gateway import SkillsApiGateway as SkillsApiClient
from interfaces.cli.commands.skills_api_commands import cmd_skills_info

# ── SkillRef / build_container_skills ────────────────────────────────────


def test_skillref_prebuilt_known_name():
    ref = SkillRef.prebuilt("xlsx")
    assert ref.to_dict() == {"type": "anthropic", "skill_id": "xlsx"}


def test_skillref_prebuilt_unknown_name_raises():
    with pytest.raises(ValueError):
        SkillRef.prebuilt("not-a-skill")


def test_skillref_custom_includes_version():
    ref = SkillRef(skill_id="my-skill", type="custom", version="3")
    assert ref.to_dict() == {"type": "custom", "skill_id": "my-skill", "version": "3"}


def test_build_container_skills_accepts_mixed_refs_and_dicts():
    out = build_container_skills([SkillRef.prebuilt("pptx"), {"type": "custom", "skill_id": "x"}])
    assert out == {"skills": [{"type": "anthropic", "skill_id": "pptx"}, {"type": "custom", "skill_id": "x"}]}


def test_build_container_skills_rejects_over_eight():
    with pytest.raises(ValueError):
        build_container_skills([SkillRef.prebuilt("pptx")] * 9)


# ── build_user_content ───────────────────────────────────────────────────


def test_build_user_content_text_only():
    assert build_user_content("hi") == [{"type": "text", "text": "hi"}]


def test_build_user_content_with_file_ids():
    out = build_user_content("hi", file_ids=["f1", "f2"])
    assert out == [
        {"type": "text", "text": "hi"},
        {"type": "container_upload", "file_id": "f1"},
        {"type": "container_upload", "file_id": "f2"},
    ]


# ── SkillsApiClient.call_with_skills / call_with_skills_turn ─────────────
#
# GA note (2026-08-22): the Skills API and Files API betas are no longer
# sent — only CODE_EXECUTION_BETA rides along.


def test_call_with_skills_sends_expected_betas_and_container(monkeypatch):
    client = SkillsApiClient(api_key="k", model="claude-sonnet-5")
    captured = {}

    def fake_post(payload, betas):
        captured["payload"] = payload
        captured["betas"] = betas
        return {"content": []}

    monkeypatch.setattr(client, "_post", fake_post)
    client.call_with_skills("do something", skills=["xlsx"])

    assert captured["betas"] == [CODE_EXECUTION_BETA]
    assert SKILLS_BETA not in captured["betas"]
    assert FILES_API_BETA not in captured["betas"]
    assert captured["payload"]["container"] == {"skills": [{"type": "anthropic", "skill_id": "xlsx"}]}
    assert captured["payload"]["tools"] == [{"type": "code_execution_20250825", "name": "code_execution"}]


def test_call_with_skills_turn_reuses_container_id(monkeypatch):
    client = SkillsApiClient(api_key="k")
    captured = {}
    monkeypatch.setattr(
        client,
        "_post",
        lambda payload, betas: (captured.update(payload=payload, betas=betas) or {"content": []}),
    )

    client.call_with_skills_turn(
        messages=[{"role": "user", "content": "hi"}],
        skills=["pptx"],
        container_id="cont_123",
    )

    assert captured["payload"]["container"]["id"] == "cont_123"
    assert FILES_API_BETA not in captured["betas"]
    assert SKILLS_BETA not in captured["betas"]
    assert captured["betas"] == [CODE_EXECUTION_BETA]


def test_call_with_skills_turn_no_files_beta_when_uploading(monkeypatch):
    """GA (2026-08-22): container_upload file references need no beta header."""
    client = SkillsApiClient(api_key="k")
    captured = {}
    monkeypatch.setattr(
        client, "_post", lambda payload, betas: (captured.update(betas=betas) or {"content": []})
    )

    client.call_with_skills_turn(
        messages=[{"role": "user", "content": build_user_content("hi", ["f1"])}],
        skills=["pptx"],
        has_file_uploads=True,
    )

    assert captured["betas"] == [CODE_EXECUTION_BETA]
    assert FILES_API_BETA not in captured["betas"]


def test_wire_request_never_sends_skills_or_files_beta(monkeypatch):
    """Wire-level: the actual outgoing anthropic-beta header carries only
    the code-execution beta — never skills/files beta strings."""
    client = SkillsApiClient(api_key="k")
    captured = {}

    def fake_urlopen_json(req, timeout):
        captured["headers"] = dict(req.header_items())
        return {"content": []}

    monkeypatch.setattr(gateway_module, "urlopen_json", fake_urlopen_json)
    client.call_with_skills("hi", skills=["xlsx"])

    header_value = (
        captured["headers"].get("Anthropic-beta") or captured["headers"].get("anthropic-beta") or ""
    )
    assert SKILLS_BETA not in header_value
    assert FILES_API_BETA not in header_value


def test_wire_request_omits_beta_header_when_no_betas(monkeypatch):
    client = SkillsApiClient(api_key="k")
    captured = {}

    def fake_urlopen_json(req, timeout):
        captured["req"] = req
        return {"content": []}

    monkeypatch.setattr(gateway_module, "urlopen_json", fake_urlopen_json)
    client._call({"model": "m"}, betas=[])

    names = {k.lower() for k in dict(captured["req"].header_items())}
    assert "anthropic-beta" not in names


# ── extract_output_file_ids ───────────────────────────────────────────────


def test_extract_output_file_ids_from_code_execution_block():
    data = {
        "content": [
            {"type": "text", "text": "done"},
            {
                "type": "code_execution_tool_result",
                "content": {"content": [{"type": "file", "file_id": "file_abc"}]},
            },
        ]
    }
    assert extract_output_file_ids(data) == ["file_abc"]


def test_extract_output_file_ids_from_bash_block_flat_list():
    data = {
        "content": [
            {
                "type": "bash_code_execution_tool_result",
                "content": [{"file_id": "file_1"}, {"file_id": "file_2"}],
            },
        ]
    }
    assert extract_output_file_ids(data) == ["file_1", "file_2"]


def test_extract_output_file_ids_ignores_unrelated_blocks():
    data = {"content": [{"type": "text", "text": "no files here"}]}
    assert extract_output_file_ids(data) == []


def test_extract_output_file_ids_tolerates_missing_content():
    assert extract_output_file_ids({}) == []
    assert extract_output_file_ids({"content": None}) == []


# ── list_skills / cmd_skills_info ────────────────────────────────────────


def test_list_skills_covers_all_prebuilt():
    skills = list_skills()
    assert {s["skill_id"] for s in skills} == set(PREBUILT_SKILLS)
    assert all(s["type"] == "anthropic" for s in skills)


def test_cmd_skills_info_known_returns_info(capsys):
    info = cmd_skills_info("docx")
    assert info == PREBUILT_SKILLS["docx"]
    out = capsys.readouterr().out
    assert "docx" in out


def test_cmd_skills_info_unknown_returns_none(capsys):
    assert cmd_skills_info("bogus") is None
    out = capsys.readouterr().out
    assert "Unknown skill_id" in out
