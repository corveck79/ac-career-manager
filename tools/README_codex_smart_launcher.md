# Codex Smart Launcher

This is a local Windows workaround for missing per-thread model routing in Codex.

It does four things:
- classify a task with `tools/model_router.py`
- detect the currently visible model from saved label screenshots
- switch the Codex model picker only when needed
- optionally paste or submit your prompt

## Limits

- It depends on a stable Codex window layout.
- It uses screen coordinates and keyboard automation, not an official Codex API.
- Detection works only after you save one reference image per model.

## Setup

1. Make sure the Codex window is visible.
2. Run calibration:

```powershell
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\codex_smart_launcher.py calibrate
```

3. After calibration, manually select each model once in Codex and capture a reference:

```powershell
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\codex_smart_launcher.py capture-ref --model GPT-5.1-Codex-Mini
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\codex_smart_launcher.py capture-ref --model GPT-5.2-Codex
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\codex_smart_launcher.py capture-ref --model GPT-5.3-Codex
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\codex_smart_launcher.py capture-ref --model GPT-5.4
```

4. Test detection:

```powershell
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\codex_smart_launcher.py detect
```

## Usage

Advice only:

```powershell
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\codex_smart_launcher.py advise --use-case build-debug --task "debug a failing multi-file build regression"
```

Switch model and paste prompt into Codex:

```powershell
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\codex_smart_launcher.py ask --use-case build-debug --prompt "Debug the failing multi-file build regression in AC Career Manager" --paste-prompt --include-starter
```

Switch, paste, and submit:

```powershell
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\codex_smart_launcher.py ask --use-case chat --prompt "Welke config key stuurt de theme?" --paste-prompt --submit
```

## Files

- `tools/codex_smart_launcher.py`: smart launcher
- `tools/model_router.py`: model recommendation logic
- `tools/codex_launcher_config.json`: saved coordinates and references
- `tools/codex_model_refs/`: label screenshots per model
