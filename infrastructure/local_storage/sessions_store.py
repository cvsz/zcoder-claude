"""
infrastructure/local_storage/sessions_store.py — session/checkpoint
persistence and the away-summary scan
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Extracted 2026-08-18 from claude_sessions.py's storage helpers and
away_summary(). away_summary() lives here rather than in its own file:
it doesn't touch session storage, but it is local-machine state
(git log + file mtimes for a directory) — same "local disk/subprocess
adapter" role as everything else in this file, and the whole module
is small enough (227 original lines) that a fourth file for one
function would be over-splitting.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

from domain.sessions import SKIP_DIRS, Checkpoint, Session, Turn

SESSIONS_DIR = Path.home() / ".zcoder" / "sessions"
CHECKPOINTS_DIR = Path.home() / ".zcoder" / "checkpoints"


def _sess_path(sid: str) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR / f"{sid}.json"


def _cp_path(cpid: str) -> Path:
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    return CHECKPOINTS_DIR / f"{cpid}.json"


def save_session(s: Session):
    _sess_path(s.sid).write_text(json.dumps(s.to_dict(), indent=2))


def load_session(sid: str) -> Session | None:
    p = _sess_path(sid)
    if not p.exists():
        return None
    return Session.from_dict(json.loads(p.read_text()))


def latest_session(mode: str | None = None) -> Session | None:
    if not SESSIONS_DIR.exists():
        return None
    sessions = []
    for p in SESSIONS_DIR.glob("*.json"):
        try:
            s = Session.from_dict(json.loads(p.read_text()))
            if mode is None or s.mode == mode:
                sessions.append(s)
        except Exception:
            pass
    return max(sessions, key=lambda s: s.updated) if sessions else None


def list_sessions(mode: str | None = None) -> list[Session]:
    if not SESSIONS_DIR.exists():
        return []
    out = []
    for p in SESSIONS_DIR.glob("*.json"):
        try:
            s = Session.from_dict(json.loads(p.read_text()))
            if mode is None or s.mode == mode:
                out.append(s)
        except Exception:
            pass
    return sorted(out, key=lambda s: s.updated, reverse=True)


def capture_checkpoint(s: Session, label: str) -> Checkpoint:
    cp = Checkpoint(sid=s.sid, label=label, n_turns=len(s.turns), snap=[t.to_dict() for t in s.turns])
    _cp_path(cp.cpid).write_text(json.dumps(cp.to_dict(), indent=2))
    return cp


def rewind_to_checkpoint(s: Session, cpid: str) -> Session:
    p = _cp_path(cpid)
    if not p.exists():
        raise ValueError(f"Checkpoint not found: {cpid}")
    cp = Checkpoint.from_dict(json.loads(p.read_text()))
    if cp.sid != s.sid:
        raise ValueError("Checkpoint belongs to a different session")
    s.turns = [Turn.from_dict(t) for t in cp.snap]
    s.updated = datetime.now().isoformat()
    save_session(s)
    return s


def list_checkpoints(sid: str) -> list[Checkpoint]:
    if not CHECKPOINTS_DIR.exists():
        return []
    out = []
    for p in CHECKPOINTS_DIR.glob("*.json"):
        try:
            cp = Checkpoint.from_dict(json.loads(p.read_text()))
            if cp.sid == sid:
                out.append(cp)
        except Exception:
            pass
    return sorted(out, key=lambda c: c.ts)


# ── Away summary ──────────────────────────────────────────────────────────────


def away_summary(cwd: str, since_iso: str) -> str:
    from datetime import datetime

    since_dt = datetime.fromisoformat(since_iso)

    # git commits since
    commits: list[str] = []
    try:
        r = subprocess.run(
            f'git log --since="{since_iso}" --oneline',
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        commits = [line for line in r.stdout.splitlines() if line.strip()]
    except Exception:
        pass

    # files modified since
    modified: list[str] = []
    root = Path(cwd)
    ts = since_dt.timestamp()
    count = 0
    for path in root.rglob("*"):
        if count > 5000:
            break
        count += 1
        if any(p in SKIP_DIRS for p in path.parts):
            continue
        if path.is_file():
            try:
                if path.stat().st_mtime > ts:
                    modified.append(str(path.relative_to(root)))
                    if len(modified) >= 50:
                        break
            except OSError:
                pass

    if not commits and not modified:
        return "No changes detected in the project since this session was last active."
    lines = ["While you were away:"]
    if commits:
        lines.append(f"  {len(commits)} commit(s):")
        for c in commits[:8]:
            lines.append(f"    · {c}")
    if modified:
        lines.append(f"  {len(modified)} file(s) modified:")
        for f in modified[:10]:
            lines.append(f"    · {f}")
    return "\n".join(lines)
