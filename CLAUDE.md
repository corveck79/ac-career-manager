# AC Career Manager - Claude Code Guide

## Project Overview

AC Career Manager is a desktop app (pywebview + Flask) that adds a career mode to Assetto Corsa (AC). It runs a local Flask server on `http://127.0.0.1:5000` and displays the UI in a native Edge WebView2 window — no browser needed.

- **Backend:** Python / Flask (`app.py`, `career_manager.py`)
- **Frontend:** Vanilla JS + HTML/CSS (`templates/dashboard.html`, `static/app.js`, `static/style.css`)
- **Window:** pywebview 4.4.1 with `gui='edgechromium'` (Edge WebView2, pre-installed on Win 10/11)
- **Python:** 3.12 required — pythonnet (pywebview dep) has no wheel for 3.13/3.14
- **Config:** `config.json` (all tunable game settings)
- **Save data:** `career_data.json` (auto-created at runtime, next to EXE)
- **Platform:** Windows only (AC is a Windows game)

## Architecture

```
app.py                       # Flask server, REST API, AC launch logic, pywebview window
career_manager.py            # Game logic: tiers, teams, contracts, race generation
extract_gt_cars.py           # Utility: extracts GT car data from AC content folder
templates/dashboard.html     # Single-page web UI (served by Flask)
static/style.css             # Dark motorsport CSS theme
static/app.js                # Frontend JS
config.json                  # Master config (tracks, teams, difficulty, format)
career_data.json             # Live save file (auto-created; not committed)
build.bat                    # PyInstaller build script → dist/AC_Career_Manager.exe
start.bat                    # Dev launcher: activates venv and runs app.py
```

Note: `dashboard.html`, `style.css`, and `app.js` also exist as duplicates in the project root — not used by Flask. Flask reads from `templates/` and `static/` only.

## App Startup Flow

1. `app.py` is run (directly or as EXE)
2. Flask starts in a daemon thread on port 5000
3. pywebview creates an Edge WebView2 window pointing to `http://127.0.0.1:5000`
4. On page load, JS calls `/api/setup-status`; if AC path is invalid, setup overlay is shown
5. User sets AC path → saved to `config.json` → app is ready

### Frozen EXE path handling
- Config and save files live **next to the EXE** (not in `sys._MEIPASS`)
- `get_app_dir()` returns `os.path.dirname(sys.executable)` when frozen
- `ensure_config()` copies bundled `config.json` template to app dir on first run

### Folder picker bridge (Python ↔ JS)
JS calls `window.pywebview.api.browse_folder()`. This invokes `JsApi.browse_folder()` in
Python, which calls `webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)`.

## Common Commands

```bash
# Run the app (from project root, with venv active)
python app.py

# Install dependencies
pip install -r requirements.txt

# Note: pythonnet must be installed with --pre flag
pip install pythonnet --pre

# Create/activate venv
python -m venv venv
venv\Scripts\activate   # Windows

# Build standalone EXE
build.bat              # Runs PyInstaller, outputs dist/AC_Career_Manager.exe (~17 MB)
```

## API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/api/setup-status` | Check if AC install path is valid |
| POST | `/api/save-ac-path` | Save AC install path to config |
| GET | `/api/career-status` | Full career state |
| GET | `/api/standings` | Championship standings |
| GET | `/api/season-calendar` | Full season race calendar |
| GET | `/api/next-race` | Next race details |
| POST | `/api/start-race` | Launch AC with race config |
| POST | `/api/finish-race` | Submit result, calc points |
| POST | `/api/end-season` | Trigger season end / contract offers |
| POST | `/api/accept-contract` | Accept a contract offer |
| POST | `/api/new-career` | Reset and start fresh |
| GET/POST | `/api/config` | Read or update config |

## Career Tiers

| Index | Key | Name | AI Adj |
|-------|-----|------|--------|
| 0 | `mx5_cup` | MX5 Cup | -4 |
| 1 | `gt4` | GT4 SuperCup | -2 |
| 2 | `gt3` | British GT GT3 | 0 |
| 3 | `wec` | WEC / Elite | +1.5 |

Base AI level: 85 (0–100 scale), with ±1.5 variance per race.

## Points System

F1-standard: 25-18-15-12-10-8-6-4-2-1, +1 fastest lap (if top 10).

## Key Config Fields (`config.json`)

- `paths.ac_install` — Path to Assetto Corsa install (must contain `acs.exe`)
- `paths.content_manager` — Auto-detected if Content Manager.exe is present
- `difficulty.base_ai_level` — Base AI strength (0–100)
- `difficulty.ai_level_variance` — Per-race AI randomness (0–5)
- `seasons.races_per_tier` — Races before season ends
- `tracks.<tier>` — Track list per tier (AC track folder names)
- `teams.<tier>.teams[]` — Team/car assignments per tier
- `contracts` — How many offers based on championship finish

**Edit `config.json` only while the app is stopped.**

## Save File (`career_data.json`)

Auto-created next to the EXE. Key fields:
```json
{
  "tier": 0,
  "season": 1,
  "team": null,
  "car": null,
  "driver_name": "",
  "races_completed": 0,
  "points": 0,
  "standings": [],
  "race_results": [],
  "contracts": null
}
```
Delete to reset career. Backup before editing config.

## Dependencies

- `Flask==3.0.0` + `flask-cors==4.0.0` + `Werkzeug==3.0.0`
- `Jinja2==3.1.2`
- `requests==2.31.0`
- `pywebview==4.4.1` — native window via Edge WebView2 (requires Python 3.12)
- `pyinstaller==6.19.0` (build only)

## Windows-Specific Notes

- AC is launched via `subprocess` writing `race.ini` to `Documents\Assetto Corsa\cfg\`
- AC install path must contain `acs.exe`
- Default AC path: `C:\Program Files (x86)\Steam\steamapps\common\assettocorsa`
- Port 5000 is the default; change in `app.py` if it conflicts
- `start.bat` activates venv (creates with `py -3.12` if missing) and runs `app.py`
- `build.bat` produces a single `dist/AC_Career_Manager.exe` (~13 MB) using `--onefile`
- pywebview uses Edge WebView2 (pre-installed on Win 10/11) — no browser bundled
- **Python 3.12 required**: pythonnet has no wheel for 3.13/3.14
