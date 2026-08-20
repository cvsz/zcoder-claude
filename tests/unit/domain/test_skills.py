from domain.skills import parse_skill_md, validate_skill_files, validate_skill_manifest


def test_parse_manifest_with_allowed_tools():
    manifest = parse_skill_md(
        "---\nname: repo-review\ndescription: Review repositories\n"
        "allowed-tools: Read, Grep, Bash\n---\nDo the review.\n"
    )
    assert manifest.name == "repo-review"
    assert manifest.description == "Review repositories"
    assert manifest.allowed_tools == ("Read", "Grep", "Bash")
    assert validate_skill_manifest(manifest).valid


def test_manifest_rejects_invalid_name_and_missing_description():
    result = validate_skill_manifest(parse_skill_md("---\nname: Bad Name\n---\nBody\n"))
    assert not result.valid
    assert any("lowercase" in e for e in result.errors)
    assert any("description" in e for e in result.errors)


def test_package_requires_single_top_level_directory_and_skill_md():
    assert validate_skill_files(["my-skill/SKILL.md", "my-skill/scripts/run.py"]).valid
    assert not validate_skill_files(["a/SKILL.md", "b/ref.md"]).valid
    assert not validate_skill_files(["my-skill/readme.md"]).valid


def test_package_rejects_parent_traversal():
    result = validate_skill_files(["my-skill/SKILL.md", "my-skill/../secret.txt"])
    assert not result.valid
    assert any(".." in e for e in result.errors)
