# AC Career Manager - Claude Code Guide

## Project Overview

AC Career Manager is a Flask-based web app that adds a career mode to Assetto Corsa (AC). It runs a local server (`http://localhost:5000`) and launches AC races through the OS via subprocess calls.

- **Backend:** Python / Flask (`app.py`, `career_manager.py`)
- **Frontend:** Vanilla JS + HTML/CSS (`dashboard.html`, `app.js`, `style.css`)
- **Config:** `config.json` (all tunable game settings)
- **Save data:** `career_data.json` (auto-created at runtime)
- **Platform:** Windows only (AC is a Windows game)

## Architecture

```
app.py                       # Flask server, REST API endpoints, AC launch logic
career_manager.py            # Game logic: tiers, teams, contracts, race generation
setup_wizard.py              # First-run setup: detects AC install path
extract_gt_cars.py           # Utility: extracts GT car data from AC content folder
templates/dashboard.html     # Single-page web UI (served by Flask)
static/style.css             # Dark motorsport CSS theme
static/app.js                # Frontend JS
config.json                  # Master config (tracks, teams, difficulty, format)
career_data.json             # Live save file (auto-created; not committed)
```

Note: `dashboard.html`, `style.css`, and `app.js` also exist as duplicates in the project root — these are the originals but are **not used by Flask**. Flask reads from `templates/` and `static/` only.

## Common Commands

```bash
# Run the app (from project root, with venv active)
python app.py

# Install dependencies
pip install -r requirements.txt

# Create/activate venv
python -m venv venv
venv\Scripts\activate   # Windows

# Build standalone EXE
build.bat              # Runs PyInstaller, outputs dist/AC_Career_Manager.exe
```

## API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/api/career-status` | Full career state |
| GET | `/api/standings` | Championship standings |
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

- `paths.ac_install` — Path to Assetto Corsa install (must be correct)
- `difficulty.base_ai_level` — Base AI strength (0–100)
- `seasons.races_per_tier` — Races before season ends
- `tracks.<tier>` — Track list per tier (AC track folder names)
- `teams.<tier>.teams[]` — Team/car assignments per tier
- `contracts` — How many offers based on championship finish

**Edit `config.json` only while the app is stopped.**

## Save File (`career_data.json`)

Auto-created. Key fields:
```json
{
  "tier": 0,
  "season": 1,
  "team": null,
  "car": null,
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
- `pyinstaller==6.19.0` (build only)

## Windows-Specific Notes

- AC is launched via `subprocess` pointing to AC's `.exe`
- Default AC path: `C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa`
- Port 5000 is the default; change in `app.py` if it conflicts
- `start.bat` handles venv activation + auto-opens browser
- `build.bat` produces a self-contained EXE (~150 MB) in `dist/`
