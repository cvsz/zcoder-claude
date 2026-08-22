"""interfaces/cli/commands/prompt_optimizer_commands.py — CLI presentation for Prompt Optimizer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Only print() lives here — all real work delegated to
application/prompt_optimizer_service.py.
"""

# mypy: ignore-errors

from application import prompt_optimizer_service as service


def cmd_optimize(prompt: str, api_key: str, model: str):
    import anthropic

    sys_msg, user_msg = service.optimize(prompt)
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=2048,
        system=sys_msg,
        messages=[{"role": "user", "content": user_msg}],
    )
    improved = resp.content[0].text.strip()
    print("\n\033[94mOriginal:\033[0m")
    print(prompt)
    print("\n\033[92mOptimized:\033[0m")
    print(improved)
    return improved


def cmd_score(prompt: str, api_key: str, model: str):
    import anthropic

    sys_msg, user_msg, max_tokens, parse = service.score(prompt)
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=sys_msg,
        messages=[{"role": "user", "content": user_msg}],
    )
    result = parse(resp.content[0].text.strip())
    if "error" in result:
        print(f"\033[91mError: {result['error']}\033[0m")
        return
    print("\n\033[94mPrompt Score\033[0m")
    print(f"  Clarity:       {result.get('clarity', '?')}/100")
    print(f"  Specificity:   {result.get('specificity', '?')}/100")
    print(f"  Completeness:  {result.get('completeness', '?')}/100")
    print(f"  \033[1mTotal:         {result.get('total', '?')}/100\033[0m")
    print(f"  Feedback:      {result.get('feedback', '')}\n")


def cmd_ab_test(prompt_a: str, prompt_b: str, task: str, api_key: str, model: str):
    import anthropic

    from utils import sampling_kwargs

    judge_prompt, max_tokens, parse = service.ab_test(prompt_a, prompt_b, task)

    def run(prompt):
        t0 = __import__("time").time()
        resp = anthropic.Anthropic(api_key=api_key).messages.create(
            model=model,
            max_tokens=2048,
            **sampling_kwargs(model, temperature=0.5),
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip(), round(__import__("time").time() - t0, 2)

    resp_a, time_a = run(prompt_a)
    resp_b, time_b = run(prompt_b)

    filled = judge_prompt.replace("{response_a}", resp_a).replace("{response_b}", resp_b)
    client = anthropic.Anthropic(api_key=api_key)
    judge_resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system="You are an objective evaluator of AI responses.",
        messages=[{"role": "user", "content": filled}],
    )
    j = parse(judge_resp.content[0].text.strip())
    print("\n\033[94mA/B Test Results\033[0m")
    print(f"  Winner:  \033[1m{j.get('winner', '?')}\033[0m  — {j.get('reason', '')}")
    print(f"  Score A: {j.get('score_a', '?')}/100  (response in {time_a}s)")
    print(f"  Score B: {j.get('score_b', '?')}/100  (response in {time_b}s)")
    print(f"\n\033[90m--- Response A ---\033[0m\n{resp_a[:400]}...")
    print(f"\n\033[90m--- Response B ---\033[0m\n{resp_b[:400]}...")


def cmd_prompt_lib_list():
    entries = service.list_lib()
    if not entries:
        print("Prompt library is empty. Use --prompt-lib-add with --tag to save prompts.")
        return
    print(f"\n\033[94mPrompt Library ({len(entries)} entries)\033[0m")
    for e in entries:
        print(f"  \033[1m{e['tag']:<20}\033[0m {e['preview']}")
    print()
