"""
interfaces/cli/commands/pptx_commands.py — CLI presentation for the
PowerPoint chat REPL
AI Model Coder CLI v1.50.0 (Clean Architecture refactor, Phase C, Context #4)

Only print()/input() live here — all real work delegated to
application/pptx_service.py. Extracted 2026-08-18 from
claude_powerpoint.py's cmd_pptx_chat and _cmd_pptx_chat_native.
"""

import sys

from application import pptx_service as service
from domain.powerpoint import HELP_TEXT
from infrastructure.local_storage.pptx_deck_store import Presentation

__all__ = ["cmd_pptx_chat"]


def cmd_pptx_chat(api_key, model, input_path=None, output_path=None,
                   temperature=0.3, max_tokens=4096, native=False):
    """native=True routes each turn through claude_skills_api.py's pptx
    Skill (Anthropic's own maintained implementation, server-side in a
    code-execution container) instead of the hand-rolled python-pptx path
    below. See --pptx-native. Requires Skills access on the account; the
    hand-rolled path here remains the default and the fallback for
    accounts without it."""
    if native:
        return _cmd_pptx_chat_native(api_key, model, input_path=input_path,
                                     output_path=output_path, max_tokens=max_tokens)

    if Presentation is None:
        print("[ERROR] python-pptx is required for --pptx. Install with: "
              "pip install python-pptx", file=sys.stderr)
        sys.exit(1)

    from coder import Coder

    try:
        session = service.create_session(input_path)
    except (ImportError, ValueError, OSError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    output_path = service.resolve_output_path(input_path, output_path)

    c = Coder(api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)

    print(f"\033[94mAI Model Coder — PowerPoint chat\033[0m  (model: {c.model})")
    print(f"Deck: {output_path}  (saved after every applied change)")
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
                print(HELP_TEXT); continue
            if cmd == "/slides":
                for i, s in enumerate(session.slides):
                    print(f"  {i}: {s['title']!r} ({len(s['bullets'])} bullets)")
                continue
            if cmd == "/show":
                if len(parts) < 2 or not parts[1].isdigit() or int(parts[1]) >= len(session.slides):
                    print(f"[usage] /show N — have {len(session.slides)} slide(s)")
                    continue
                s = session.slides[int(parts[1])]
                print(f"Title: {s['title']}")
                for b in s["bullets"]:
                    print(f"  - {b}")
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
                print(f"\033[96mclaude›\033[0m Updated and saved to {output_path} "
                     f"({result['num_slides']} slides)\n")
            else:
                print(f"\033[93mclaude›\033[0m {result['message']}\n")
        else:
            print(f"\033[96mclaude›\033[0m {result['reply']}\n")

    print(f"\033[94mSession ended. Final deck: {output_path}\033[0m")
    return output_path


def _cmd_pptx_chat_native(api_key, model, input_path=None, output_path=None, max_tokens=4096):
    """--pptx-native: mirrors claude_excel.py's _cmd_excel_chat_native
    one-for-one (same reasoning applies here — see that function's
    docstring), just against the pptx Skill instead of xlsx. No local
    python-pptx dependency needed for this path.

    Slash commands from the hand-rolled path (/slides, /show, /undo)
    aren't available here — the pptx Skill owns the deck, this CLI has no
    local copy of it to inspect or revert.
    """
    from claude_skills_api import SkillsApiClient
    from claude_files import FilesAPI

    files_api = FilesAPI(api_key=api_key, model=model)
    client = SkillsApiClient(api_key=api_key, model=model, max_tokens=max_tokens)

    output_path = service.resolve_output_path(input_path, output_path)

    pending_file_ids = []
    if input_path:
        try:
            fid = service.upload_input_deck(files_api, input_path)
        except RuntimeError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        pending_file_ids = [fid]

    print(f"\033[94mAI Model Coder — PowerPoint chat (native Skills API)\033[0m  (model: {model})")
    print(f"Deck: {output_path}  (saved after every turn that produces one)")
    print("Type /exit to quit. (/slides, /show, /undo aren't available in --pptx-native.)\n")

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

        result = service.run_native_turn(client, files_api, messages, user_input,
                                          pending_file_ids, container_id, output_path)
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

    print(f"\033[94mSession ended. Final deck: {output_path}\033[0m")
    return output_path
