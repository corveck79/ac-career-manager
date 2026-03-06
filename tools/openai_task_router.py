#!/usr/bin/env python3
"""Route a task to an OpenAI model using the local model router."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

from openai import AuthenticationError, OpenAI, OpenAIError, RateLimitError

import model_router


API_MODEL_MAP = {
    "GPT-5.1-Codex-Mini": "gpt-5.1-codex-mini",
    "GPT-5.2-Codex": "gpt-5.2-codex",
    "GPT-5.3-Codex": "gpt-5.3-codex",
    "GPT-5.4": "gpt-5.4",
}
DEFAULT_MAX_FILE_CHARS = 12000
DEFAULT_MAX_TOTAL_CHARS = 40000


def read_text(path: Path, max_chars: int) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[Truncated]"


def build_context(paths: Iterable[str], max_file_chars: int, max_total_chars: int) -> str:
    blocks: list[str] = []
    total_chars = 0
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Context file not found: {path}")
        text = read_text(path, max_file_chars)
        remaining = max_total_chars - total_chars
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[:remaining] + "\n\n[Truncated]"
        blocks.append(f"FILE: {path}\n```text\n{text}\n```")
        total_chars += len(text)
    return "\n\n".join(blocks)


def resolve_prompt(prompt: str | None, prompt_file: str | None) -> str:
    if prompt:
        return prompt
    if prompt_file:
        return Path(prompt_file).expanduser().resolve().read_text(encoding="utf-8")
    raise ValueError("Either --prompt or --prompt-file is required")


def resolve_advice(use_case: str | None, task: str | None) -> model_router.Advice:
    advice = model_router.choose_base_advice(use_case)
    if task:
        advice = model_router.apply_task_rules(advice, task)
    return advice


def build_instructions(advice: model_router.Advice, include_starter: bool, custom: str | None) -> str | None:
    parts: list[str] = []
    if include_starter:
        parts.append(advice.starter)
    if custom:
        parts.append(custom)
    if not parts:
        return None
    return "\n\n".join(parts)


def build_input(prompt: str, context: str) -> str:
    if not context:
        return prompt
    return f"Task:\n{prompt}\n\nWorkspace context:\n{context}"


def print_advice(advice: model_router.Advice, api_model: str) -> None:
    print(f"Model advice: {advice.model}")
    print(f"API model: {api_model}")
    print(f"Why: {advice.why}")
    print(f"Cost mode: {advice.cost_mode}")
    print(f"Switch rule: {advice.switch_rule}")


def run_request(args: argparse.Namespace) -> int:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set")

    prompt = resolve_prompt(args.prompt, args.prompt_file)
    task_hint = args.task or prompt
    advice = resolve_advice(args.use_case, task_hint)
    api_model = API_MODEL_MAP[advice.model]
    context = build_context(args.context_file or [], args.max_file_chars, args.max_total_chars)
    instructions = build_instructions(advice, args.include_starter, args.instructions)
    user_input = build_input(prompt, context)

    print_advice(advice, api_model)
    if args.dry_run:
        return 0

    client = OpenAI()
    try:
        response = client.responses.create(
            model=api_model,
            instructions=instructions,
            input=user_input,
        )
    except AuthenticationError:
        print()
        print("API error: authentication failed. Check OPENAI_API_KEY.")
        return 2
    except RateLimitError as exc:
        print()
        print(f"API error: {exc}")
        print("The router works, but this API key currently has no usable quota or hit a rate limit.")
        return 3
    except OpenAIError as exc:
        print()
        print(f"API error: {exc}")
        return 4

    text = (response.output_text or "").strip()
    if args.output_file:
        Path(args.output_file).expanduser().resolve().write_text(text, encoding="utf-8")
    print()
    print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Route a task to the cheapest viable OpenAI model")
    sub = parser.add_subparsers(dest="command", required=True)

    advise = sub.add_parser("advise", help="Return model advice without calling the API")
    advise.add_argument("--use-case", choices=sorted(model_router.USE_CASES))
    advise.add_argument("--task", required=True)

    run = sub.add_parser("run", help="Choose a model and call the OpenAI Responses API")
    prompt_group = run.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file")
    run.add_argument("--use-case", choices=sorted(model_router.USE_CASES))
    run.add_argument("--task", help="Optional classification hint if the prompt is too short")
    run.add_argument("--context-file", action="append", default=[], help="Repeat for each local text file to include")
    run.add_argument("--instructions", help="Extra instructions sent as API instructions")
    run.add_argument("--include-starter", action="store_true", help="Include the routed starter prompt as instructions")
    run.add_argument("--max-file-chars", type=int, default=DEFAULT_MAX_FILE_CHARS)
    run.add_argument("--max-total-chars", type=int, default=DEFAULT_MAX_TOTAL_CHARS)
    run.add_argument("--output-file", help="Optional file path for the model output")
    run.add_argument("--dry-run", action="store_true", help="Show the chosen model without calling the API")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "advise":
        advice = resolve_advice(args.use_case, args.task)
        api_model = API_MODEL_MAP[advice.model]
        print_advice(advice, api_model)
        return 0
    if args.command == "run":
        return run_request(args)
    parser.error("Unknown command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
