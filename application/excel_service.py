"""
application/excel_service.py — use-case layer for the Excel chat
bounded context
AI Model Coder CLI v1.51.0 (Clean Architecture refactor, Phase C, Context #4)

Orchestrates infrastructure/local_storage/excel_workbook_store.py (the
hand-rolled path) and claude_skills_api.py + infrastructure/
anthropic_api/files_gateway.py (the --excel-native path) — one turn's
worth of logic each, no print(). Extracted 2026-08-18 from
claude_excel.py's cmd_excel_chat/_cmd_excel_chat_native loop bodies,
mirroring application/pptx_service.py's shape one-for-one (same
product, same session/history/undo/native design as claude_powerpoint.py
per that module's own docstring).
"""

import re

from domain.excel import SYSTEM_PROMPT, _CODE_BLOCK
from infrastructure.local_storage.excel_workbook_store import ExcelSession


def resolve_output_path(input_path, output_path):
    return output_path or (
        re.sub(r"\.\w+$", "", input_path) + ".xlsx" if input_path else "excel_session.xlsx"
    )


def create_session(input_path, sheet_name):
    """Raises ImportError (pandas missing), ValueError, or OSError —
    same exception types the original cmd_excel_chat caught."""
    return ExcelSession(input_path, sheet_name)


# ── hand-rolled path ─────────────────────────────────────────────────────

def run_turn(coder, session, user_input, history, output_path):
    """Run one hand-rolled-path turn: prompt Claude with the current data
    summary + the user's request, apply any generated code, and save if
    it applied cleanly. Appends to `history` in place (matching the
    original's behavior of always recording the turn). Returns a result
    dict rather than printing directly."""
    prompt = f"Current data:\n{session.summary()}\n\nRequest: {user_input}"
    reply = coder.generate(prompt, system=SYSTEM_PROMPT, history=history)

    match = _CODE_BLOCK.search(reply)

    result = {
        "reply": reply, "code_block_found": False, "applied": None,
        "message": None, "shapes": None,
    }
    if match:
        result["code_block_found"] = True
        ok, message = session.apply_code(match.group(1))
        result["applied"] = ok
        result["message"] = message
        if ok:
            session.save(output_path)
            result["shapes"] = ", ".join(
                f"{n}: {d.shape[0]}x{d.shape[1]}" for n, d in session.sheets.items())

    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": reply})
    return result


# ── --excel-native path ───────────────────────────────────────────────────

def upload_input_workbook(files_api, input_path):
    """Upload the starting workbook for --excel-native. Raises
    RuntimeError on any failure — mirrors application/pptx_service.py's
    upload_input_deck one-for-one, same original two-print-then-exit(1)
    paths collapsed into one exception with the same message text."""
    try:
        uploaded = files_api.upload(input_path)
    except (RuntimeError, OSError) as e:
        raise RuntimeError(f"Could not upload {input_path}: {e}") from e
    fid = uploaded.get("id")
    if not fid:
        raise RuntimeError(f"Upload succeeded but returned no file id: {uploaded}")
    return fid


def run_native_turn(client, files_api, messages, user_input, pending_file_ids,
                     container_id, output_path):
    """Run one --excel-native turn against the xlsx Skill. `messages` is
    mutated in place (appended to on success, popped back on error,
    matching the original). Returns a result dict; does not print."""
    from claude_skills_api import build_user_content, extract_output_file_ids

    messages.append({"role": "user", "content": build_user_content(user_input, pending_file_ids)})
    has_uploads = bool(pending_file_ids)

    data = client.call_with_skills_turn(
        messages, skills=["xlsx"], container_id=container_id, has_file_uploads=has_uploads,
    )

    result = {
        "error": None, "text": "", "downloaded": False, "download_error": None,
        "container_id": container_id,
    }
    if "error" in data:
        result["error"] = data["error"]
        messages.pop()
        return result

    result["container_id"] = (data.get("container") or {}).get("id", container_id)
    messages.append({"role": "assistant", "content": data.get("content", [])})

    result["text"] = "".join(
        b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
    )

    new_file_ids = extract_output_file_ids(data)
    if new_file_ids:
        try:
            files_api.download(new_file_ids[-1], output_path)
            result["downloaded"] = True
        except RuntimeError as e:
            result["download_error"] = str(e)

    return result
