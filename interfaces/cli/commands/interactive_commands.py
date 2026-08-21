"""interfaces/cli/commands/interactive_commands.py — CLI presentation for Interactive REPL
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Only print() and input() live here — all real work delegated to
application/interactive_service.py and coder.py.
"""

from application import interactive_service as service


def cmd_interactive(api_key, model, system=None, temperature=0.3, max_tokens=4096, personality_style=None):
    from coder import Coder

    history = []
    c = Coder(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        personality_style=personality_style,
    )

    print(f"\\033[94mAI Model Coder — interactive chat\\033[0m  (model: {c.model})")
    print("Type /help for commands, /exit (or Ctrl-D) to quit.\\n")

    while True:
        try:
            user_input = input("\\033[92myou›\\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            rest = parts[1].strip() if len(parts) > 1 else ""

            if cmd in ("/exit", "/quit"):
                break
            if cmd == "/help":
                print(service.get_help_text())
                continue
            if cmd == "/reset":
                history = []
                print("[history cleared]")
                continue
            if cmd == "/system":
                system = rest or None
                print("[system prompt set]" if system else "[system prompt cleared]")
                continue
            if cmd == "/model":
                if rest:
                    c.model = rest
                    print(f"[model switched to {c.model}]")
                else:
                    print(f"[current model: {c.model}]")
                continue
            if cmd == "/save":
                path = rest or "transcript.md"
                try:
                    with open(path, "w") as f:
                        f.write(service.format_transcript_md(history, system))
                    print(f"[saved transcript to {path}]")
                except OSError as e:
                    print(f"[ERROR] could not save: {e}")
                continue
            if cmd == "/history":
                print(f"[{len(history)} messages in history]")
                continue
            print(f"[unknown command {cmd!r}; try /help]")
            continue

        reply = c.generate(user_input, system=system, history=history)
        print(f"\\033[96mclaude›\\033[0m {reply}\\n")
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})

    print("\\033[94mSession ended.\\033[0m")
    return history
