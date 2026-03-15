#!/usr/bin/env python3
"""
Recommend a Codex model for a task or use case.

This is a local workaround for the missing per-thread model setting in the UI.
It does not switch the model automatically; it tells the user which model to use
before starting or continuing a thread.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass


MODEL_MINI = "GPT-5.1-Codex-Mini"
MODEL_BALANCED = "GPT-5.2-Codex"
MODEL_STRONG = "GPT-5.3-Codex"
MODEL_MAX = "GPT-5.4"


@dataclass(frozen=True)
class Advice:
    model: str
    why: str
    cost_mode: str
    switch_rule: str
    thread_name: str
    starter: str


USE_CASES = {
    "chat": Advice(
        model=MODEL_MINI,
        why="Short questions and lightweight discussion do not need a heavier model.",
        cost_mode="economy",
        switch_rule="Move up only if the task turns into code changes, debugging, or multi-file planning.",
        thread_name="Chat + Questions",
        starter="Answer briefly in Dutch, keep app and code terms in English, and avoid doing code edits unless asked.",
    ),
    "planner": Advice(
        model=MODEL_BALANCED,
        why="Planning and triage usually need more context handling than a cheap chat model.",
        cost_mode="balanced",
        switch_rule="Move down for simple Q&A; move up if the plan depends on deep debugging or architecture changes.",
        thread_name="Plan + Triage",
        starter="First classify the task, propose the cheapest viable model, then outline the next concrete steps.",
    ),
    "small-edit": Advice(
        model=MODEL_MINI,
        why="Small edits and targeted fixes are usually cheapest on mini without losing reliability.",
        cost_mode="economy",
        switch_rule="Move up after two failed attempts or if the change expands beyond one focused area.",
        thread_name="Small Edit",
        starter="Focus on a small scoped change, keep token use low, and avoid broad refactors.",
    ),
    "feature": Advice(
        model=MODEL_BALANCED,
        why="New features often span several files and require steadier reasoning.",
        cost_mode="balanced",
        switch_rule="Move down for isolated follow-up tweaks; move up if requirements stay unclear or failures repeat.",
        thread_name="Feature Build",
        starter="Build the feature end to end, but keep scope controlled and avoid unnecessary redesign.",
    ),
    "build-debug": Advice(
        model=MODEL_STRONG,
        why="Build failures and runtime debugging usually benefit from stronger reasoning and iteration.",
        cost_mode="quality",
        switch_rule="Move down once the bug is isolated; move up only if the issue remains ambiguous after two passes.",
        thread_name="Build + Debug",
        starter="Diagnose the failing path first, verify the root cause, then make the smallest reliable fix.",
    ),
    "review": Advice(
        model=MODEL_BALANCED,
        why="Reviewing changes needs enough reasoning to spot regressions without defaulting to the most expensive model.",
        cost_mode="balanced",
        switch_rule="Move up if the diff is architectural or the bug surface is unusually broad.",
        thread_name="Code Review",
        starter="Review for bugs, regressions, and missing tests first; keep the summary short after findings.",
    ),
    "architecture": Advice(
        model=MODEL_MAX,
        why="Architecture decisions are high-leverage and expensive to get wrong.",
        cost_mode="quality",
        switch_rule="Move down for implementation follow-up once the design direction is fixed.",
        thread_name="Architecture",
        starter="Prioritize trade-offs, constraints, and failure modes before proposing structural changes.",
    ),
}


KEYWORD_RULES = [
    ("architecture", MODEL_MAX),
    ("redesign", MODEL_MAX),
    ("migration", MODEL_STRONG),
    ("refactor", MODEL_STRONG),
    ("debug", MODEL_STRONG),
    ("failing", MODEL_STRONG),
    ("broken", MODEL_STRONG),
    ("regression", MODEL_STRONG),
    ("multi-file", MODEL_BALANCED),
    ("api", MODEL_BALANCED),
    ("tests", MODEL_BALANCED),
    ("feature", MODEL_BALANCED),
    ("small", MODEL_MINI),
    ("rename", MODEL_MINI),
    ("copy", MODEL_MINI),
    ("typo", MODEL_MINI),
]


def choose_base_advice(use_case: str | None) -> Advice:
    if use_case and use_case in USE_CASES:
        return USE_CASES[use_case]
    return USE_CASES["planner"]


def escalate_model(current: str, target: str) -> str:
    order = [MODEL_MINI, MODEL_BALANCED, MODEL_STRONG, MODEL_MAX]
    return order[max(order.index(current), order.index(target))]


def apply_task_rules(base: Advice, task: str) -> Advice:
    task_lower = task.lower()
    model = base.model
    for keyword, suggested_model in KEYWORD_RULES:
        if keyword in task_lower:
            model = escalate_model(model, suggested_model)

    why = base.why
    if model != base.model:
        why = f"{base.why} The task description suggests extra complexity, so one tier higher is safer."

    cost_mode = base.cost_mode
    if model in {MODEL_STRONG, MODEL_MAX}:
        cost_mode = "quality"
    elif model == MODEL_BALANCED:
        cost_mode = "balanced"
    else:
        cost_mode = "economy"

    return Advice(
        model=model,
        why=why,
        cost_mode=cost_mode,
        switch_rule=base.switch_rule,
        thread_name=base.thread_name,
        starter=base.starter,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recommend a Codex model for a task.")
    parser.add_argument(
        "--use-case",
        choices=sorted(USE_CASES.keys()),
        help="Named workflow preset.",
    )
    parser.add_argument(
        "--task",
        help="Short task description used to adjust the recommendation.",
    )
    parser.add_argument(
        "--list-use-cases",
        action="store_true",
        help="List the available presets and exit.",
    )
    return parser


def print_use_cases() -> None:
    for name in sorted(USE_CASES):
        advice = USE_CASES[name]
        print(f"{name}: {advice.model} | {advice.thread_name}")


def print_advice(advice: Advice) -> None:
    print(f"Model advice: {advice.model}")
    print(f"Why: {advice.why}")
    print(f"Cost mode: {advice.cost_mode}")
    print(f"Switch rule: {advice.switch_rule}")
    print(f"Thread name: {advice.thread_name}")
    print(f"Starter prompt: {advice.starter}")
    print("Manual step: switch the Codex model in the UI before using this thread.")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_use_cases:
        print_use_cases()
        return 0

    advice = choose_base_advice(args.use_case)
    if args.task:
        advice = apply_task_rules(advice, args.task)

    print_advice(advice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
