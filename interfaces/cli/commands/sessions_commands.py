"""
interfaces/cli/commands/sessions_commands.py — CLI presentation for the
Sessions bounded context
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Only print() lives here — all real work delegated to
application/sessions_service.py. Extracted 2026-08-18 from
claude_sessions.py's cmd_sessions_list, cmd_session_show,
cmd_checkpoint_list, cmd_away_summary.
"""

from application import sessions_service as service

__all__ = [
    "cmd_sessions_list", "cmd_session_show", "cmd_checkpoint_list",
    "cmd_away_summary",
]


def cmd_sessions_list():
    ss = service.list_all_sessions()
    if not ss: print("No saved sessions."); return
    print(f"{'ID':<14} {'Mode':<14} {'Turns':<7} {'Title / Updated'}")
    print("─" * 60)
    for s in ss[:20]:
        title = (s.title or "")[:24]
        upd   = s.updated[:16]
        print(f"{s.sid:<14} {s.mode:<14} {len(s.turns):<7} {title or upd}")


def cmd_session_show(sid: str):
    s = service.get_session(sid)
    if not s: print(f"Session not found: {sid}"); return
    print(s.recap(n=10))


def cmd_checkpoint_list(sid: str):
    cps = service.get_checkpoints(sid)
    if not cps: print(f"No checkpoints for session {sid}"); return
    for cp in cps:
        print(f"  [{cp.cpid}] '{cp.label}' — {cp.n_turns} turns, {cp.ts[:16]}")


def cmd_away_summary(sid: str, cwd: str = "."):
    summary = service.get_away_summary(sid, cwd)
    if summary is None: print(f"Session not found: {sid}"); return
    print(summary)
