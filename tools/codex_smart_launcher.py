#!/usr/bin/env python3
"""
Smart Codex launcher for model-aware prompting on Windows.

Workflow:
1. Calibrate clickable coordinates in the Codex UI.
2. Capture a label reference image for each model once.
3. Ask this launcher to choose a model, switch if needed, and paste a prompt.

This is a UI-automation workaround. It depends on stable window layout.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import subprocess
import sys
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageGrab, ImageOps

import model_router


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "codex_launcher_config.json"
REF_DIR = ROOT / "codex_model_refs"
WINDOW_TITLE = "Codex"
DEFAULT_DELAY = 0.25
MODEL_SEARCH_TEXT = {
    "GPT-5.1-Codex-Mini": "GPT-5.1-Codex-Mini",
    "GPT-5.2-Codex": "GPT-5.2-Codex",
    "GPT-5.3-Codex": "GPT-5.3-Codex",
    "GPT-5.4": "GPT-5.4",
}


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


user32 = ctypes.windll.user32


def powershell(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
    )


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"refs": {}, "item_pos": {}, "last_model": None}


def save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def get_cursor_pos() -> tuple[int, int]:
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def set_cursor_pos(x: int, y: int) -> None:
    user32.SetCursorPos(x, y)


def mouse_click(x: int, y: int) -> None:
    set_cursor_pos(x, y)
    time.sleep(0.05)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.03)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def app_activate(window_title: str = WINDOW_TITLE) -> bool:
    result = powershell(
        "$wshell = New-Object -ComObject WScript.Shell;"
        f"if ($wshell.AppActivate('{window_title}')) {{ 'ok' }} else {{ 'fail' }}"
    )
    return result.stdout.strip() == "ok"


def set_clipboard(text: str) -> None:
    escaped = text.replace("'", "''")
    result = powershell(f"Set-Clipboard -Value @'\n{escaped}\n'@")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to set clipboard")


def send_keys(keys: str) -> None:
    escaped = keys.replace("'", "''")
    result = powershell(
        "$wshell = New-Object -ComObject WScript.Shell;"
        f"$wshell.SendKeys('{escaped}')"
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Failed to send keys: {keys}")


def screenshot_region(region: dict[str, int]) -> Image.Image:
    left = region["x"]
    top = region["y"]
    right = left + region["width"]
    bottom = top + region["height"]
    return ImageGrab.grab(bbox=(left, top, right, bottom))


def average_hash(image: Image.Image, size: int = 8) -> int:
    gray = ImageOps.grayscale(image).resize((size, size))
    # Pillow 14 deprecates getdata() in favor of get_flattened_data().
    get_flattened_data = getattr(gray, 'get_flattened_data', None)
    if callable(get_flattened_data):
        pixels = list(get_flattened_data())
    else:
        pixels = list(gray.getdata())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for value in pixels:
        bits = (bits << 1) | int(value >= avg)
    return bits


def hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def prompt_cursor(label: str, delay_seconds: int = 0) -> tuple[int, int]:
    if delay_seconds and delay_seconds > 0:
        print(f"Place the mouse over {label}. Capturing in {delay_seconds}s...")
        time.sleep(delay_seconds)
    else:
        input(f"Place the mouse over {label}, then press Enter here...")
    pos = get_cursor_pos()
    print(f"Captured {label} at {pos[0]}, {pos[1]}")
    return pos


def calibrate(config: dict[str, Any], delay_seconds: int = 0) -> None:
    print("Calibrating Codex launcher.")
    print("Make sure the Codex window is visible and the composer area is on screen.")
    picker_x, picker_y = prompt_cursor("the model picker", delay_seconds=delay_seconds)
    prompt_x, prompt_y = prompt_cursor("the prompt input box", delay_seconds=delay_seconds)
    print("Now capture the visible model label region.")
    left_x, left_y = prompt_cursor("the TOP-LEFT corner of the visible model label", delay_seconds=delay_seconds)
    right_x, right_y = prompt_cursor("the BOTTOM-RIGHT corner of the visible model label", delay_seconds=delay_seconds)
    config["picker_pos"] = {"x": picker_x, "y": picker_y}
    config["prompt_pos"] = {"x": prompt_x, "y": prompt_y}
    config["label_region"] = {
        "x": min(left_x, right_x),
        "y": min(left_y, right_y),
        "width": abs(right_x - left_x),
        "height": abs(right_y - left_y),
    }
    save_config(config)
    print(f"Saved calibration to {CONFIG_PATH}")


def ensure_ready(config: dict[str, Any]) -> None:
    required = ["picker_pos", "prompt_pos", "label_region"]
    missing = [name for name in required if name not in config]
    if missing:
        raise SystemExit(f"Missing config fields: {', '.join(missing)}. Run --calibrate first.")


def ref_path(model: str) -> Path:
    safe = model.lower().replace(".", "_").replace("-", "_")
    return REF_DIR / f"{safe}.png"


def capture_model_item(config: dict[str, Any], model: str, delay_seconds: int = 5) -> None:
    """Capture the click position for a model entry in the open picker menu."""
    ensure_ready(config)
    config.setdefault("item_pos", {})
    x, y = prompt_cursor(f"the menu item for {model} (make sure the model list is open)", delay_seconds=delay_seconds)
    config["item_pos"][model] = {"x": x, "y": y}
    save_config(config)
    print(f"Saved menu item position for {model} at {x}, {y}")


def capture_model_ref(config: dict[str, Any], model: str) -> None:
    ensure_ready(config)
    REF_DIR.mkdir(parents=True, exist_ok=True)
    image = screenshot_region(config["label_region"])
    path = ref_path(model)
    image.save(path)
    config.setdefault("refs", {})[model] = str(path)
    config["last_model"] = model
    save_config(config)
    print(f"Saved reference for {model} to {path}")


def detect_current_model(config: dict[str, Any]) -> tuple[str | None, int | None]:
    ensure_ready(config)
    refs = config.get("refs", {})
    if not refs:
        return None, None
    current = screenshot_region(config["label_region"])
    current_hash = average_hash(current)
    best_model = None
    best_distance = None
    for model, path_str in refs.items():
        path = Path(path_str)
        if not path.exists():
            continue
        ref_hash = average_hash(Image.open(path))
        distance = hamming_distance(current_hash, ref_hash)
        if best_distance is None or distance < best_distance:
            best_model = model
            best_distance = distance
    if best_distance is not None and best_distance <= 10:
        return best_model, best_distance
    return None, best_distance


def paste_text(text: str) -> None:
    set_clipboard(text)
    send_keys("^v")


def choose_advice(use_case: str | None, task: str | None) -> model_router.Advice:
    advice = model_router.choose_base_advice(use_case)
    if task:
        advice = model_router.apply_task_rules(advice, task)
    return advice


def switch_model(
    config: dict[str, Any],
    target_model: str,
    verify: bool = True,
) -> tuple[str | None, bool, str | None, int | None]:
    ensure_ready(config)
    current_model, distance = detect_current_model(config)
    if current_model == target_model:
        return current_model, True, current_model, distance

    if not app_activate():
        raise RuntimeError("Could not focus the Codex window.")
    time.sleep(DEFAULT_DELAY)

    after_model: str | None = None
    after_distance: int | None = None

    for _attempt in range(2):
        mouse_click(config["picker_pos"]["x"], config["picker_pos"]["y"]) 
        time.sleep(0.4)

        # Prefer clicking the menu item if calibrated; fall back to typing search text.
        item = config.get("item_pos", {}).get(target_model)
        if item:
            mouse_click(item["x"], item["y"])
        else:
            # Best-effort: if a search box is focused, select-all before paste.
            send_keys("^a")
            time.sleep(0.05)
            paste_text(MODEL_SEARCH_TEXT[target_model])
            time.sleep(0.15)
            send_keys("{ENTER}")


        if verify:
            # Poll a few times; UI updates can lag.
            for _ in range(6):
                time.sleep(0.35)
                after_model, after_distance = detect_current_model(config)
                if after_model == target_model:
                    break
        else:
            time.sleep(0.8)

        if (not verify) or after_model == target_model:
            config["last_model"] = target_model
            save_config(config)
            return current_model, True, after_model, after_distance

        # Retry once: close any open dropdown and try again.
        send_keys("{ESC}")
        time.sleep(0.2)

    # Failed verification after retry.
    if verify:
        after_model, after_distance = detect_current_model(config)
    return current_model, False, after_model, after_distance



def fill_prompt(config: dict[str, Any], prompt: str, submit: bool) -> None:
    if not app_activate():
        raise RuntimeError("Could not focus the Codex window.")
    time.sleep(DEFAULT_DELAY)
    mouse_click(config["prompt_pos"]["x"], config["prompt_pos"]["y"])
    time.sleep(0.2)
    paste_text(prompt)
    time.sleep(0.1)
    if submit:
        send_keys("{ENTER}")
def command_advise(args: argparse.Namespace, config: dict[str, Any]) -> int:
    advice = choose_advice(args.use_case, args.task)
    print_advice(advice)
    return 0


def print_advice(advice: model_router.Advice) -> None:
    print(f"Model advice: {advice.model}")
    print(f"Why: {advice.why}")
    print(f"Cost mode: {advice.cost_mode}")
    print(f"Switch rule: {advice.switch_rule}")
    print(f"Thread name: {advice.thread_name}")
    print(f"Starter prompt: {advice.starter}")


def command_ask(args: argparse.Namespace, config: dict[str, Any]) -> int:
    ensure_ready(config)
    advice = choose_advice(args.use_case, args.task or args.prompt)
    print_advice(advice)
    current_model, switched, after_model, after_distance = switch_model(
        config, advice.model, verify=not args.no_verify
    )
    print(f"Current model before switch: {current_model or 'unknown'}")
    print(f"Switch result: {'ok' if switched else 'unverified'}")
    if not args.no_verify:
        print(f"Detected model after switch: {after_model or 'unknown'}")
        print(f"Distance after switch: {after_distance}")
    final_prompt = args.prompt
    if args.include_starter:
        final_prompt = f"{advice.starter}\n\nTask: {args.prompt}"
    if args.paste_prompt or args.submit:
        fill_prompt(config, final_prompt, submit=args.submit)
        print("Prompt pasted into Codex.")
    return 0 if switched else 2


def command_detect(args: argparse.Namespace, config: dict[str, Any]) -> int:
    model, distance = detect_current_model(config)
    print(f"Detected model: {model or 'unknown'}")
    print(f"Distance: {distance}")
    return 0 if model else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smart Codex model launcher")
    sub = parser.add_subparsers(dest="command", required=True)

    cal = sub.add_parser("calibrate", help="Capture screen coordinates for Codex UI controls")
    cal.add_argument("--delay-seconds", type=int, default=0)

    ref = sub.add_parser("capture-ref", help="Capture the current visible model label as a reference")
    ref.add_argument("--model", required=True, choices=sorted(MODEL_SEARCH_TEXT))

    item = sub.add_parser("capture-item", help="Capture click position for a model entry in the picker menu")
    item.add_argument("--model", required=True, choices=sorted(MODEL_SEARCH_TEXT))
    item.add_argument("--delay-seconds", type=int, default=5)

    sub.add_parser("detect", help="Detect the currently visible model from saved references")

    advise = sub.add_parser("advise", help="Return model advice only")
    advise.add_argument("--use-case", choices=sorted(model_router.USE_CASES))
    advise.add_argument("--task")

    ask = sub.add_parser("ask", help="Choose model, switch if needed, and paste a prompt")
    ask.add_argument("--prompt", required=True)
    ask.add_argument("--use-case", choices=sorted(model_router.USE_CASES))
    ask.add_argument("--task")
    ask.add_argument("--paste-prompt", action="store_true")
    ask.add_argument("--submit", action="store_true")
    ask.add_argument("--include-starter", action="store_true")
    ask.add_argument("--no-verify", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config()

    if args.command == "calibrate":
        calibrate(config, delay_seconds=getattr(args, "delay_seconds", 0))
        return 0
    if args.command == "capture-ref":
        capture_model_ref(config, args.model)
        return 0

    if args.command == "capture-item":
        capture_model_item(config, args.model, delay_seconds=getattr(args, "delay_seconds", 5))
        return 0
    if args.command == "detect":
        return command_detect(args, config)
    if args.command == "advise":
        return command_advise(args, config)
    if args.command == "ask":
        return command_ask(args, config)
    parser.error("Unknown command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
