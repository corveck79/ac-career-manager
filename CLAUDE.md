# AC Career Manager - Claude Code Guide

## Versioning Convention

| Type | When | Example |
|------|------|---------|
| `x.y.0` | New feature(s), multi-file changes | v1.8.0 — Career Wizard, Debrief, Relegation |
| `x.y.z` | Single fix, tweak, or small addition | v1.8.1 — trim README overview |

Current version: **1.12.0** (bump in `README.md` header on every release commit).

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
make_icon.py                 # Dev utility: generates static/logo.ico (run once, needs Pillow)
static/logo.svg              # SVG logo — topbar + favicon in dashboard.html
static/logo.ico              # Multi-res ICO (16–256px) — embedded in EXE via --icon
docs/screenshots/            # README screenshots (dashboard, race_modal, standings_*)
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
build.bat              # Runs PyInstaller, outputs dist/AC_Career_Manager.exe (~13 MB)

# Generate logo ICO (run once after cloning, needs Pillow)
venv\Scripts\python.exe make_icon.py

# Take/update README screenshots (headless — no pywebview window needed)
# 1. Start Flask without webview:
venv\Scripts\python.exe -c "import types,sys; sys.modules['webview']=types.ModuleType('webview'); from app import app; app.run(host='127.0.0.1',port=5000,debug=False,use_reloader=False)"
# 2. In another terminal, run Playwright screenshot script (pip install playwright + playwright install chromium)
```

## API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/api/setup-status` | Check if AC install path is valid |
| POST | `/api/save-ac-path` | Save AC install path to config |
| GET | `/api/career-status` | Full career state |
| GET | `/api/standings` | Championship standings (player tier only, legacy) |
| GET | `/api/all-standings` | All 4 tiers: `{tier_key: {drivers:[...], teams:[...]}}` |
| GET | `/api/season-calendar` | Full season race calendar |
| GET | `/api/next-race` | Next race details |
| POST | `/api/start-race` | Launch AC with race config; body `{mode}` = `race_only` or `full_weekend`; saves `race_started_at` |
| GET | `/api/read-race-result` | Auto-read result from AC results JSON; returns `lap_analysis` `{lap_times, consistency, engineer_report, …}` |
| POST | `/api/finish-race` | Submit result, calc points |
| POST | `/api/end-season` | Trigger season end / contract offers; snapshots AI driver history |
| POST | `/api/accept-contract` | Accept a contract offer; reads `target_tier` + `move` from contract → real promotion/stay/relegation |
| POST | `/api/new-career` | Reset and start fresh; body `{driver_name, difficulty, weather_mode, custom_tracks}` |
| GET/POST | `/api/config` | Read or update config |
| GET | `/api/driver-profile` | Driver profile: `?name=<driver>` → `{name, profile, current, history}` |
| GET | `/api/preflight-check` | Validate track & car exist: `?track=<id>&car=<id>` → `{ok, issues:[{type,msg}]}` |
| GET | `/api/scan-content` | Scan AC content folder → `{cars:{gt4:[],gt3:[]}, tracks:[{id,name,length}]}` |
| POST | `/api/career-settings` | Patch career_settings in career_data.json; body `{dynamic_weather: bool, night_cycle: bool}` |

## Career Tiers

| Index | Key | Name | AI Adj |
|-------|-----|------|--------|
| 0 | `mx5_cup` | MX5 Cup | -4 |
| 1 | `gt4` | GT4 SuperCup | -2 |
| 2 | `gt3` | British GT GT3 | 0 |
| 3 | `wec` | WEC / Elite | +1.5 |

Base AI level: 95 (0–100 scale), with ±1.5 variance per race.

**Difficulty presets** (applied as `ai_offset` to `base_ai_level`, stored in `career_settings`):
| Preset | Offset | Effective base at GT3 |
|--------|--------|-----------------------|
| Rookie | −10    | 85                    |
| Amateur| −5     | 90                    |
| Pro    | 0      | 95                    |
| Legend | +5     | 100                   |

## Points System

F1-standard: 25-18-15-12-10-8-6-4-2-1. Fastest lap bonus removed.

## Driver Name Architecture (career_manager.py)

- `DRIVER_NAMES`: 120-name pool — enough for all 106 championship driver slots
- `DRIVERS_PER_TEAM`: `{mx5_cup:1, gt4:2, gt3:2, wec:2}` — MX5 is single-driver
- `TIER_SLOT_OFFSET`: `{mx5_cup:0, gt4:14, gt3=46, wec:86}` — global slot start per tier
- `_get_driver_name(global_slot, season)`: season-seeded global shuffle → each slot → unique name
- `generate_standings()`: returns driver championship (1 or 2 entries per team)
- `generate_team_standings_from_drivers()`: aggregates driver entries to team championship
- `generate_all_standings()`: returns `{tier_key: {drivers:[...], teams:[...]}}` for all 4 tiers
- `_get_car_skin(car, ac_path, index=0)`: index-based skin picker; player gets 0, AI cars get 1,2,3…

## Driver Profiles & Personalities (v1.7.0, career_manager.py)

- `DRIVER_PROFILES`: class-level dict — 120 entries matching `DRIVER_NAMES` exactly
  - Each entry: `{"nationality": "GBR", "skill": 80, "aggression": 50}`
  - `skill` range: 70–95 → maps to `AI_LEVEL` offset in race.ini (`skill_offset = int((skill-80)*0.2)`)
  - `aggression` range: 0–100 → maps directly to `AI_AGGRESSION` in race.ini
- `_get_style(skill, aggression)` → archetype string:
  - skill≥85 + aggr≥60 = **"The Charger"**
  - skill≥85 + aggr<60 = **"The Tactician"**
  - skill<85 + aggr≥60 = **"The Wildcard"**
  - else = **"The Journeyman"**
- `get_driver_profile(name)` → `{nationality, skill, aggression, style}` (fallback: GBR/80/40)
- `_generate_opponent_field()` stores `driver_name` + `global_slot` per opponent
- `_write_race_config()` uses per-driver `AI_LEVEL` + `AI_AGGRESSION` (no longer global/hardcoded 0)
- standings↔race name sync: both use `_get_driver_name(global_slot, season)` — names now match

## Contracts & Promotion/Relegation (v1.8.0)

Every contract object in `career_data.json['contracts']` carries two new fields:

| Field | Values | Meaning |
|-------|--------|---------|
| `target_tier` | int 0–3 | Tier index the player moves to on acceptance |
| `move` | `'promotion'` / `'stay'` / `'relegation'` | How to label the transition |

**`generate_contract_offers()` logic (career_manager.py):**
- `player_position >= team_count − 2` → **degradation risk path**:
  - Worst customer seat in current tier (`move='stay'`, `target_tier=current_tier`)
  - Up to 2 best semi/factory seats from the tier below (`move='relegation'`, `target_tier=current_tier−1`)
  - No offers if already in tier 0 (MX5 Cup, can't go lower)
- Otherwise → **normal promotion path**: all offers have `move='promotion'`, `target_tier=current_tier+1`

**`accept_contract()` fix (app.py):**
- Reads `target_tier` from the selected contract (falls back to `tier+1` for pre-v1.8 saves)
- Clamps to `[0, len(tiers)−1]`
- Sets `career_data['tier'] = new_tier` — NOT `+= 1`
- **`career_settings` (difficulty, weather, custom tracks) is preserved** — not reset
- Returns `{status, message, move, new_tier, new_team, new_car}`
- Move message examples: "Promoted to British GT GT3 — Ferrari GT3 Team!", "Relegated to GT4 SuperCup — GT4 Privateer!"

**Backwards compatibility:** Old contracts without `target_tier` fall back to `tier+1` (promotion assumed).

## Post-Race Debrief (v1.8.0)

`/api/read-race-result` now reads the top-level `Laps` array from the AC results JSON and returns:

```json
"lap_analysis": {
  "lap_times":       [106000, 105200, …],   // ms, valid laps only
  "lap_count":       10,
  "best_lap_ms":     105200,
  "avg_lap_ms":      106800,
  "std_ms":          420,
  "consistency":     86,                    // 0–100 (100=perfect)
  "engineer_report": "Solid podium, P2. Good consistency …"
}
```

**Lap filtering:** laps with `LapTime == 0` are dropped; laps > 150% of the best lap (in/out laps) are excluded from statistics.

**Consistency score:** `max(0, min(100, 100 − std_ms / 30))` — drops ~1pt per 30ms of std deviation.

**Engineer report** has three parts:
1. **Position feedback** — ecstatic (P1), podium (P2-3), points (P4-5), midfield, tough race
2. **Consistency feedback** — based on std dev thresholds: <500ms/1000ms/2000ms
3. **Pace trend** — compares first vs last third of laps (only when ≥6 valid laps)

**Frontend helpers (`app.js`):**
- `fmtMs(ms)` — format milliseconds as `M:SS.mmm`
- `renderDebrief(analysis, position)` — fills `#debrief-panel` with consistency badge, report text, and lap sparkline bar chart; called from `fetchRaceResult()` when status is `'found'`
- Debrief panel is hidden on race start (reset in `confirmStartRace()`)

## Career History (v1.7.0)

- `career_data.json` field: `"driver_history": {name: {seasons: [{season, tier, pos, pts}]}}`
- Populated by `/api/end-season` before contract generation
- `/api/driver-profile` returns `history` for the requested driver
- Frontend: profile card shows history rows newest-first with tier label and trophy for P1

## Key Config Fields (`config.json`)

- `paths.ac_install` — Path to Assetto Corsa install (must contain `acs.exe`)
- `paths.content_manager` — Auto-detected if Content Manager.exe is present
- `difficulty.base_ai_level` — Base AI strength (0–100)
- `difficulty.ai_level_variance` — Per-race AI randomness (0–5)
- `seasons.races_per_tier` — Races before season ends
- `tracks.<tier>` — Track list per tier (AC track folder names)
- `teams.<tier>.teams[]` — Team/car assignments per tier
- `contracts` — How many offers based on championship finish
- `tiers.<tier>.race_format.weather_pool` — `[[preset, weight], ...]` pairs for weighted random weather
- `tiers.<tier>.race_format.practice_minutes` / `quali_minutes` — session lengths for Full Weekend mode

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
  "contracts": null,
  "final_position": null,
  "race_started_at": "2025-01-01T12:00:00",
  "driver_history": {},
  "career_settings": {
    "difficulty": "pro",
    "ai_offset": 0,
    "weather_mode": "realistic",
    "custom_tracks": null
  }
}
```
- `final_position` — set by `_do_end_season()`, cleared to `null` on contract acceptance
- `career_settings` — persists across seasons; stores difficulty, weather mode, and optional custom track lists
- `driver_history` format: `{name: {seasons: [{season:1, tier:"gt4", pos:3, pts:45}]}}`

Delete to reset career. Backup before editing config.

## Logo & Icon

Design: dark navy `#07091A` rounded square, orange `#E84A0A` top-right triangle, gold `#F7B801`
bottom-left triangle, white "AC" bold text, gold underline.

- `static/logo.svg` — 40×40 SVG, used in `dashboard.html` topbar (`<img class="topbar-logo">`) and as favicon (`<link rel="icon" type="image/svg+xml">`)
- `static/logo.ico` — multi-resolution ICO (16/32/48/64/128/256px), embedded in EXE via `--icon`
- `make_icon.py` — regenerate ICO if design changes: `venv\Scripts\python.exe make_icon.py`
- `.topbar-logo { width:28px; height:28px }` in `static/style.css`

## Screenshots (docs/screenshots/)

Taken headlessly with Playwright (chromium). Flask runs without pywebview, Playwright renders at 1440×920.

```python
# Pattern used to take screenshots:
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={'width':1440,'height':920}).new_page()
    page.goto('http://127.0.0.1:5000', wait_until='networkidle')
    page.screenshot(path='docs/screenshots/dashboard.png')
    page.evaluate("switchStandingsTier(1)")   # GT4 tab
    page.screenshot(path='docs/screenshots/standings_gt4.png')
    browser.close()
```

Current screenshots: `dashboard.png`, `race_modal.png`, `standings_gt4.png`, `standings_wec.png`, `standings_teams.png`

**To update screenshots:** start Flask headless (see Common Commands), run the Playwright script, then commit `docs/screenshots/`.

## Dependencies

- `Flask==3.0.0` + `flask-cors==4.0.0` + `Werkzeug==3.0.0`
- `Jinja2==3.1.2`
- `requests==2.31.0`
- `pywebview==4.4.1` — native window via Edge WebView2 (requires Python 3.12)
- `pyinstaller==6.19.0` (build only)
- `Pillow>=10.0.0` (build only — needed to run `make_icon.py`; not required at runtime)

## Windows-Specific Notes

- AC is launched via `subprocess` writing `race.ini` to `Documents\Assetto Corsa\cfg\`
- AC writes race results to `Documents\Assetto Corsa\results\YYYY_MM_DD_HH_MM_SS.json`; `/api/read-race-result` scans for the newest file after `race_started_at`
- AC install path must contain `acs.exe`
- Default AC path: `C:\Program Files (x86)\Steam\steamapps\common\assettocorsa`
- Port 5000 is the default; change in `app.py` if it conflicts
- `start.bat` activates venv (creates with `py -3.12` if missing) and runs `app.py`
- `build.bat` produces a single `dist/AC_Career_Manager.exe` (~13 MB) using `--onefile`
- pywebview uses Edge WebView2 (pre-installed on Win 10/11) — no browser bundled
- **Python 3.12 required**: pythonnet has no wheel for 3.13/3.14
