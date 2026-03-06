# OpenAI Task Router

This CLI uses the local `model_router.py` rules to choose the cheapest viable model and then sends the task to the official OpenAI Responses API.

It is the supported alternative to UI model switching in the Codex desktop app.

## Requirements

- `OPENAI_API_KEY` must be set in the environment.
- The `openai` Python package must be installed.

## What it does

- chooses a model per task or use case
- optionally includes local workspace files as plain-text context
- sends the request through the official OpenAI API
- avoids fragile Codex UI automation

## Limits

- This does not control the Codex desktop app.
- The API call does not get Codex tool access by itself.
- API billing/quota is separate from the Codex desktop app; a valid key can still fail if the API project has no quota.
- Only files you explicitly pass with `--context-file` are included.

## Usage

Advice only:

```powershell
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\openai_task_router.py advise --use-case build-debug --task "debug a failing multi-file build regression"
```

Dry run for a real request:

```powershell
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\openai_task_router.py run --use-case small-edit --prompt "Rename the function make_offer to create_offer" --dry-run
```

Run a request with workspace context:

```powershell
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\openai_task_router.py run --use-case review --prompt "Review this file for likely bugs" --context-file C:\Users\Sjack\Documents\Codex\AC_Career_Manager\app.py
```

Run with multiple files and save the answer:

```powershell
python C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tools\openai_task_router.py run --use-case feature --prompt-file C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tmp\task.txt --context-file C:\Users\Sjack\Documents\Codex\AC_Career_Manager\README.md --context-file C:\Users\Sjack\Documents\Codex\AC_Career_Manager\app.py --include-starter --output-file C:\Users\Sjack\Documents\Codex\AC_Career_Manager\tmp\router-output.txt
```
