"""interfaces/cli/commands/skills_api_commands.py — CLI presentation for Skills API
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Only print() lives here — all real work delegated to
application/skills_api_service.py.
"""

from application import skills_api_service as service


def cmd_skills_list():
    print("\n\033[94mAgent Skills (platform API, skill_id-based)\033[0m")
    print("\033[93m⚠ Pre-built skills only — custom skills are managed in the Console,\033[0m")
    print("\033[93m  not listed by a documented API endpoint.\033[0m\n")
    for s in service.list_skills():
        print(f"  \033[1m{s['skill_id']}\033[0m  ({s['type']})")
        print(f"    {s['description']}")
    print()


def cmd_skills_info(skill_id: str):
    from domain.skills_api import CODE_EXECUTION_BETA, PREBUILT_SKILLS, SkillRef

    info = PREBUILT_SKILLS.get(skill_id)
    if not info:
        print(f"\033[91m✗ Unknown skill_id: {skill_id}\033[0m")
        print(f"  Known pre-built skills: {', '.join(PREBUILT_SKILLS)}")
        return None
    print(f"\n\033[94m{info['skill_id']}\033[0m (type: anthropic)")
    print(f"  {info['description']}")
    print(
        f"  Reference in a request as: "
        f"SkillRef.prebuilt({skill_id!r}) -> {SkillRef.prebuilt(skill_id).to_dict()}"
    )
    print(f"  Code execution requires beta header: {CODE_EXECUTION_BETA}\n")
    return info
