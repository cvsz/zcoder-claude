"""
application/pptx_service.py — use-case layer for the PowerPoint chat
bounded context
AI Model Coder CLI v1.50.0 (Clean Architecture refactor, Phase C, Context #4)

Orchestrates infrastructure/local_storage/pptx_deck_store.py (the
hand-rolled path) and claude_skills_api.py + infrastructure/
anthropic_api/files_gateway.py (the --pptx-native path) — one turn's
worth of logic each, no print(). Extracted 2026-08-18 from
claude_powerpoint.py's cmd_pptx_chat/_cmd_pptx_chat_native loop bodies,
mirroring application/code_agent_loop_service.py's run_agent_query
shape (one function per "what happens when the user sends one message",
callers own the print()/input() REPL shell around it).
"""

import re

from domain.powerpoint import _CODE_BLOCK, SYSTEM_PROMPT
from infrastructure.local_storage.pptx_deck_store import PptxSession


def resolve_output_path(input_path, output_path):
    return output_path or (re.sub(r"\.\w+$", "", input_path) + ".pptx" if input_path else "pptx_session.pptx")


def create_session(input_path):
    """Raises ImportError (python-pptx missing), ValueError, or OSError —
    same exception types the original cmd_pptx_chat caught."""
    return PptxSession(input_path)


# ── hand-rolled path ─────────────────────────────────────────────────────


def run_turn(coder, session, user_input, history, output_path):
    """Run one hand-rolled-path turn: prompt Claude with the current deck
    summary + the user's request, apply any generated deck-edit code, and
    save if it applied cleanly. Appends to `history` in place (matching
    the original's behavior of always recording the turn, whether or not
    a code block was found or applied). Returns a result dict rather than
    printing directly."""
    prompt = f"Current deck:\n{session.summary()}\n\nRequest: {user_input}"
    reply = coder.generate(prompt, system=SYSTEM_PROMPT, history=history)

    match = _CODE_BLOCK.search(reply)

    result = {
        "reply": reply,
        "code_block_found": False,
        "applied": None,
        "message": None,
        "num_slides": len(session.slides),
    }
    if match:
        result["code_block_found"] = True
        ok, message = session.apply_code(match.group(1))
        result["applied"] = ok
        result["message"] = message
        if ok:
            session.save(output_path)
            result["num_slides"] = len(session.slides)

    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": reply})
    return result


# ── --pptx-native path ────────────────────────────────────────────────────


def upload_input_deck(files_api, input_path):
    """Upload the starting deck for --pptx-native. Raises RuntimeError on
    any failure — both the original's "upload() itself raised
    RuntimeError/OSError" path and its "upload succeeded but returned no
    file id" path were print-then-exit(1) in the original with different
    message text; both collapse to RuntimeError here (with that same
    message text preserved inside it), so the caller needs only one
    except clause."""
    try:
        uploaded = files_api.upload(input_path)
    except (RuntimeError, OSError) as e:
        raise RuntimeError(f"Could not upload {input_path}: {e}") from e
    fid = uploaded.get("id")
    if not fid:
        raise RuntimeError(f"Upload succeeded but returned no file id: {uploaded}")
    return fid


def run_native_turn(client, files_api, messages, user_input, pending_file_ids, container_id, output_path):
    """Run one --pptx-native turn against the pptx Skill. `messages` is
    mutated in place (appended to on success, popped back on error,
    matching the original). Returns a result dict; does not print."""
    from claude_skills_api import build_user_content, extract_output_file_ids

    messages.append({"role": "user", "content": build_user_content(user_input, pending_file_ids)})
    has_uploads = bool(pending_file_ids)

    data = client.call_with_skills_turn(
        messages,
        skills=["pptx"],
        container_id=container_id,
        has_file_uploads=has_uploads,
    )

    result = {
        "error": None,
        "text": "",
        "downloaded": False,
        "download_error": None,
        "container_id": container_id,
    }
    if "error" in data:
        result["error"] = data["error"]
        messages.pop()
        return result

    result["container_id"] = (data.get("container") or {}).get("id", container_id)
    messages.append({"role": "assistant", "content": data.get("content", [])})

    result["text"] = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    new_file_ids = extract_output_file_ids(data)
    if new_file_ids:
        try:
            files_api.download(new_file_ids[-1], output_path)
            result["downloaded"] = True
        except RuntimeError as e:
            result["download_error"] = str(e)

    return result
