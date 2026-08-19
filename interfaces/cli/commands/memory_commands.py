"""
interfaces/cli/commands/memory_commands.py — CLI presentation for the
Memory bounded context
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Only print() lives here — all real work delegated to
application/memory_service.py. Extracted 2026-08-18 from
claude_memory.py's cmd_memory_add, cmd_memory_recall, cmd_memory_forget,
cmd_memory_stats, cmd_memory_retention.
"""

from application import memory_service as service

__all__ = [
    "cmd_memory_add", "cmd_memory_recall", "cmd_memory_forget",
    "cmd_memory_stats", "cmd_memory_retention",
]


def cmd_memory_add(content: str, mtype: str = "fact", tags: str = "", importance: int = 5,
                   ns: str = "default"):
    entry = service.add_memory(
        content, mtype=mtype,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        importance=importance, ns=ns,
    )
    print(f"✓ Stored [{entry.mid}] {entry.content}")


def cmd_memory_recall(query: str, ns: str = "default", limit: int = 6):
    hits = service.recall_memories(query, ns=ns, limit=limit)
    if not hits:
        print("No matching memories."); return
    print(f"Memories matching '{query}':\n")
    for h in hits:
        print(f"  [{h.mid}] ({h.mtype.value}, importance={h.importance}) {h.content}")
        if h.tags: print(f"         tags: {', '.join(h.tags)}")


def cmd_memory_forget(mid: str, ns: str = "default"):
    if service.forget_memory(mid, ns=ns): print(f"✓ Forgot {mid}")
    else: print(f"Not found: {mid}")


def cmd_memory_stats(ns: str = "default"):
    s = service.get_stats(ns=ns)
    print(f"Namespace: {s['namespace']}  |  Total: {s['total']}")
    for t, c in s["by_type"].items():
        print(f"  {t:<15} {c}")


def cmd_memory_retention(ns: str = "default", max_age: int = 365, max_entries: int = 2000):
    r, remaining = service.apply_retention(ns=ns, max_age_days=max_age, max_entries=max_entries)
    print(f"✓ Retention applied — removed {r['removed_age']} by age, "
          f"{r['removed_cap']} by cap. {remaining} remain.")
