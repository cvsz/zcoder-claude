"""
interfaces/cli/commands/excel_commands.py — CLI presentation for the
Excel chat REPL
AI Model Coder CLI v1.51.0 (Clean Architecture refactor, Phase C, Context #4)

Only print()/input() live here — all real work delegated to
application/excel_service.py. Extracted 2026-08-18 from claude_excel.py's
cmd_excel_chat and _cmd_excel_chat_native.
"""

import sys

from application import excel_service as service
from domain.excel import HELP_TEXT
from infrastructure.local_storage.excel_workbook_store import pd

__all__ = ["cmd_excel_chat"]


def cmd_excel_chat(
    api_key,
    model,
    input_path=None,
    output_path=None,
    sheet_name=None,
    temperature=0.3,
    max_tokens=4096,
    native=False,
):
    """native=True routes each turn through claude_skills_api.py's xlsx
    Skill (Anthropic's own maintained implementation, server-side in a
    code-execution container) instead of the hand-rolled pandas/openpyxl
    path below. See --excel-native. Requires Skills access on the
    account; the hand-rolled path here remains the default and the
    fallback for accounts without it."""
    if native:
        return _cmd_excel_chat_native(
            api_key, model, input_path=input_path, output_path=output_path, max_tokens=max_tokens
        )

    if pd is None:
        print(
            "[ERROR] pandas is required for --excel. Install with: " "pip install pandas openpyxl",
            file=sys.stderr,
        )
        sys.exit(1)

    from infrastructure.anthropic_api.core_gateway import Coder

    try:
        session = service.create_session(input_path, sheet_name)
    except (ImportError, ValueError, OSError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    output_path = service.resolve_output_path(input_path, output_path)

    c = Coder(api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)

    print(f"\033[94mAI Model Coder — Excel chat\033[0m  (model: {c.model})")
    print(f"Workbook: {output_path}  (saved after every applied change)")
    print("Type /help for commands, /exit to quit.\n")

    history = []
    while True:
        try:
            user_input = input("\033[92myou›\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.split()
            cmd = parts[0].lower()
            if cmd in ("/exit", "/quit"):
                break
            if cmd == "/help":
                print(HELP_TEXT)
                continue
            if cmd == "/sheets":
                for name, df in session.sheets.items():
                    print(f"  {name}: {df.shape[0]} rows x {df.shape[1]} cols")
                continue
            if cmd == "/show":
                if len(parts) < 2 or parts[1] not in session.sheets:
                    print(f"[usage] /show SHEET [N] — sheets: {list(session.sheets)}")
                    continue
                n = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 10
                print(session.sheets[parts[1]].head(n).to_string())
                continue
            if cmd == "/undo":
                print("[reverted]" if session.undo() else "[nothing to undo]")
                session.save(output_path)
                continue
            print(f"[unknown command {cmd!r}; try /help]")
            continue

        result = service.run_turn(c, session, user_input, history, output_path)
        if result["code_block_found"]:
            if result["applied"]:
                print(f"\033[96mclaude›\033[0m Updated and saved to {output_path} " f"({result['shapes']})\n")
            else:
                print(f"\033[93mclaude›\033[0m {result['message']}\n")
        else:
            print(f"\033[96mclaude›\033[0m {result['reply']}\n")

    print(f"\033[94mSession ended. Final workbook: {output_path}\033[0m")
    return output_path


def _cmd_excel_chat_native(api_key, model, input_path=None, output_path=None, max_tokens=4096):
    """--excel-native: same chat shape as cmd_excel_chat above, but every
    turn is a Messages API call carrying the xlsx Skill in a
    code-execution container (see claude_skills_api.py) — the workbook is
    built and edited entirely server-side. No local pandas/openpyxl
    dependency needed for this path; this CLI only uploads the starting
    file (if any, once) and downloads the resulting workbook after each
    turn that produces one.

    Slash commands from the hand-rolled path (/sheets, /show, /undo)
    aren't available here — the xlsx Skill owns the workbook, this CLI
    has no local copy of it to inspect or revert.
    """
    from infrastructure.anthropic_api.files_gateway import FilesAPI
    from infrastructure.anthropic_api.skills_api_gateway import SkillsApiGateway as SkillsApiClient

    files_api = FilesAPI(api_key=api_key, model=model)
    client = SkillsApiClient(api_key=api_key, model=model, max_tokens=max_tokens)

    output_path = service.resolve_output_path(input_path, output_path)

    pending_file_ids = []
    if input_path:
        try:
            fid = service.upload_input_workbook(files_api, input_path)
        except RuntimeError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        pending_file_ids = [fid]

    print(f"\033[94mAI Model Coder — Excel chat (native Skills API)\033[0m  (model: {model})")
    print(f"Workbook: {output_path}  (saved after every turn that produces one)")
    print("Type /exit to quit. (/sheets, /show, /undo aren't available in --excel-native.)\n")

    messages = []
    container_id = None
    while True:
        try:
            user_input = input("\033[92myou›\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in ("/exit", "/quit"):
            break

        result = service.run_native_turn(
            client, files_api, messages, user_input, pending_file_ids, container_id, output_path
        )
        pending_file_ids = []  # only attach on the turn that actually introduces the file
        container_id = result["container_id"]

        if result["error"]:
            print(f"\033[91m✗ {result['error']}\033[0m\n")
            continue

        if result["text"]:
            print(f"\033[96mclaude›\033[0m {result['text']}\n")

        if result["downloaded"]:
            print(f"\033[90m  (saved to {output_path})\033[0m\n")
        elif result["download_error"]:
            print(f"\033[93m  Couldn't download generated file: {result['download_error']}\033[0m\n")

    print(f"\033[94mSession ended. Final workbook: {output_path}\033[0m")
    return output_path
