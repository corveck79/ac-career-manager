# AC Career GT Edition - Claude Code Guide

## Versioning Convention

| Type | When | Example |
|------|------|---------|
| `x.y.0` | New feature(s), multi-file changes | v1.8.0 — Career Wizard, Debrief, Relegation |
| `x.y.z` | Single fix, tweak, or small addition | v1.8.1 — trim README overview |

Current version: **1.17.0** (bump in `README.md` header on every release commit).

## Project Overview

AC Career GT Edition is a desktop app (pywebview + Flask) that adds a career mode to Assetto Corsa (AC). It runs a local Flask server on `http://127.0.0.1:5000` and displays the UI in a native Edge WebView2 window — no browser needed.

- **Backend:** Python / Flask (`app.py`, `career_manager.py`)
- **Frontend:** Vanilla JS + HTML/CSS (`templates/dashboard.html`, `static/app.js`, `static/style.css`)
- **Window:** pywebview 4.4.1 — `gui='edgechromium'` on Windows (Edge WebView2), `gui='gtk'` on Linux
- **Python:** 3.12 required — pythonnet (pywebview dep) has no wheel for 3.13/3.14
- **Config:** `config.json` (all tunable game settings)
- **Save data:** `career_data.json` (auto-created at runtime, next to EXE/AppImage)
- **Platform:** Windows 10/11 · Linux (AC via Steam Proton)

## Architecture

```
app.py                           # Flask server, REST API, AC launch logic, pywebview window
career_manager.py                # Game logic: tiers, teams, contracts, race generation
platform_paths.py                # OS path helpers (Windows vs Linux Proton, GUI backend)
extract_gt_cars.py               # Utility: extracts GT car data from AC content folder
templates/dashboard.html         # Single-page web UI (served by Flask)
static/style.css                 # Dark motorsport CSS theme
static/app.js                    # Frontend JS
config.json                      # Master config (tracks, teams, difficulty, format)
career_data.json                 # Live save file (auto-created; not committed)
build.bat                        # Windows: PyInstaller --onefile → dist/AC_Career_GT_Edition.exe
build.sh                         # Linux:   PyInstaller --onedir + appimagetool → AppImage
start.bat                        # Windows dev launcher (activates venv and runs app.py)
start.sh                         # Linux dev launcher (creates venv with Python 3.12)
.github/workflows/release.yml   # CI: tag push → auto-build EXE + AppImage + GitHub release
make_icon.py                     # Dev utility: generates static/logo.ico (run once, needs Pillow)
static/logo.svg                  # SVG logo — topbar + favicon in dashboard.html
static/logo.ico                  # Multi-res ICO (16–256px) — embedded in EXE via --icon
docs/screenshots/                # README screenshots (dashboard, race_modal, standings_*)
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
# ── Dev (Windows) ─────────────────────────────────────────────────────────────
start.bat                  # Create venv + run app (recommended)
python app.py              # Run directly with venv active

# ── Dev (Linux) ───────────────────────────────────────────────────────────────
bash start.sh              # Create venv + run app

# ── Install dependencies ──────────────────────────────────────────────────────
pip install -r requirements.txt
pip install pythonnet --pre   # pythonnet needs --pre flag

# ── Release (preferred — GitHub Actions) ─────────────────────────────────────
git tag v1.17.0 && git push origin v1.17.0
# → CI builds EXE (windows-latest) + AppImage (ubuntu-latest) + creates release

# ── Manual build (Windows, fallback only) ────────────────────────────────────
# Do NOT use build.bat directly in scripts (has `pause` → blocks shell)
venv\Scripts\pyinstaller --onefile --windowed --name "AC_Career_GT_Edition" ^
    --icon "static\logo.ico" --add-data "templates;templates" ^
    --add-data "static;static" --add-data "config.json;." ^
    --add-data "platform_paths.py;." --collect-all flask ^
    --collect-all flask_cors --collect-all webview app.py

# ── Manual build (Linux, fallback only) ──────────────────────────────────────
# Requires appimagetool in PATH or APPIMAGETOOL env var
bash build.sh

# ── Generate logo ICO (run once after cloning, needs Pillow) ─────────────────
venv\Scripts\python.exe make_icon.py   # Windows
venv/bin/python make_icon.py           # Linux

# ── README screenshots (headless Flask, no pywebview needed) ─────────────────
venv\Scripts\python.exe -c "import types,sys; sys.modules['webview']=types.ModuleType('webview'); from app import app; app.run(host='127.0.0.1',port=5000,debug=False,use_reloader=False)"
# Then run Playwright script (pip install playwright && playwright install chromium)
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
| GET | `/api/read-race-result` | Auto-read result from AC results JSON; returns `lap_analysis` `{lap_times, consistency, engineer_report, sector_analysis, weakest_sector, total_cuts, tyre, gap_to_leader_ms, …}` |
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

## Post-Race Debrief (v1.8.0, extended v1.17.0)

`/api/read-race-result` reads the top-level `Laps` array from the AC results JSON.
Each lap object carries `LapTime`, `Sectors` (3 sector times), `Cuts`, and `Tyre`.

```json
"lap_analysis": {
  "lap_times":        [106000, 105200, …],   // ms, valid laps only
  "lap_count":        10,
  "best_lap_ms":      105200,
  "avg_lap_ms":       106800,
  "std_ms":           420,
  "consistency":      86,                    // 0–100 (100=perfect)
  "engineer_report":  "Solid podium, P2. Good consistency …",
  "sector_analysis":  [                      // only if all laps have 3 non-zero sectors
    {"best_ms": 32100, "avg_ms": 32800, "std_ms": 210},
    {"best_ms": 38400, "avg_ms": 39200, "std_ms": 310},
    {"best_ms": 34700, "avg_ms": 35900, "std_ms": 180}
  ],
  "weakest_sector":   2,                     // 1-indexed, highest avg-best delta
  "total_cuts":       3,                     // only present when > 0
  "tyre":             "SM",                  // most-used compound; omitted if unavailable
  "gap_to_leader_ms": 4520                   // omitted for P1
}
```

**Lap filtering:** laps with `LapTime == 0` are dropped; laps > 150% of the best lap are excluded.

**Consistency score:** `max(0, min(100, 100 − std_ms / 30))` — drops ~1pt per 30ms of std dev.

**Auto-polling (v1.17.0):** `confirmStartRace()` calls `startResultPolling()` which polls
`/api/read-race-result` every 5 s (up to 30 min). When `found`/`incomplete` is returned,
`fetchRaceResult()` is called automatically — no button press required. Manual fallback
button ("Import Result Manually") stays for edge cases.

**Frontend helpers (`app.js`):**
- `fmtMs(ms)` — format milliseconds as `M:SS.mmm`
- `startResultPolling()` — auto-polls every 5 s after race launch; stops on result or navigation away
- `renderDebrief(analysis, position)` — fills `#debrief-panel` with consistency badge, report text,
  lap sparkline, sector grid (S1/S2/S3 best+avg, weakest highlighted), and meta row (gap/tyre/cuts)
- Debrief panel is reset in `confirmStartRace()` reset block

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

## platform_paths.py (v1.16.0)

Central module for OS-specific path logic — import instead of hardcoding `~/Documents` anywhere.

| Function | Returns |
|----------|---------|
| `is_linux()` | `True` on Linux |
| `is_windows()` | `True` on Windows |
| `get_ac_docs_path(subfolder)` | `~/Documents/Assetto Corsa/<sub>` on Windows; Proton compat-data path on Linux |
| `get_default_ac_install_path()` | OS-appropriate AC install hint for the setup screen |
| `get_webview_gui()` | `'edgechromium'` on Windows, `'gtk'` on Linux |

**Proton path detection order:**
1. `~/.steam/steam/steamapps/compatdata/244210/pfx/…`
2. `~/.local/share/Steam/steamapps/compatdata/244210/pfx/…`
3. Extra Steam libraries from `~/.steam/steam/steamapps/libraryfolders.vdf`
4. Fallback to `~/.steam/steam/…` (may not exist until first AC launch — `os.makedirs` creates it)

**Used by:** `app.py` (`results_dir`, `setup_status default_hint`, `webview.start gui=`) and `career_manager.py` (`_get_ac_docs_cfg`, `launch_ac_race`).

## Dependencies

- `Flask==3.0.0` + `flask-cors==4.0.0` + `Werkzeug==3.0.0`
- `Jinja2==3.1.2`
- `requests==2.31.0`
- `pywebview==4.4.1` — native window via Edge WebView2 (requires Python 3.12)
- `pyinstaller==6.19.0` (build only)
- `Pillow>=10.0.0` (build only — needed to run `make_icon.py`; not required at runtime)

## Platform Notes

### Both platforms
- AC install path must contain `acs.exe`
- `platform_paths.py` provides all OS-specific paths and the pywebview GUI backend
- **Python 3.12 required**: pythonnet has no wheel for 3.13/3.14
- Port 5000 is the default; change in `app.py` if it conflicts

### Windows
- pywebview uses Edge WebView2 (`gui='edgechromium'`) — pre-installed on Win 10/11, no browser bundled
- AC launched via `subprocess.Popen(acs.exe)` — writes `race.ini` to `~/Documents/Assetto Corsa/cfg/`
- AC results at `~/Documents/Assetto Corsa/results/YYYY_MM_DD_HH_MM_SS.json`
- Default AC path: `C:\Program Files (x86)\Steam\steamapps\common\assettocorsa`
- `start.bat` activates venv (creates with `py -3.12` if missing) and runs `app.py`
- `build.bat` produces `dist/AC_Career_GT_Edition.exe` (~13 MB) using `--onefile`

### Linux
- pywebview uses GTK (`gui='gtk'`) — requires `libwebkit2gtk-4.0` or `libwebkit2gtk-4.1` on host
- AC runs via Steam Proton; launched with `subprocess.Popen(['steam', '-applaunch', '244210'])`
- AC config/results inside Proton compat-data: `~/.steam/steam/steamapps/compatdata/244210/pfx/drive_c/users/steamuser/Documents/Assetto Corsa/`
- Also checked: `~/.local/share/Steam/` and extra libraries from `libraryfolders.vdf`
- Default AC path: `~/.steam/steam/steamapps/common/assettocorsa`
- `start.sh` creates venv with `python3.12` and runs `app.py`
- `build.sh` produces AppImage via PyInstaller `--onedir` + `appimagetool`
- `VERSION` env var overrides hardcoded version in `build.sh` (used by CI)

### CI/CD — `.github/workflows/release.yml`
- Trigger: `git tag vX.Y.Z && git push origin vX.Y.Z`
- `build-windows` (windows-latest): PyInstaller → `AC_Career_GT_Edition.exe`
- `build-linux` (ubuntu-latest): installs GTK libs + PyGObject, PyInstaller + appimagetool → `AC_Career_GT_Edition-X.Y.Z-x86_64.AppImage`
- `release`: downloads both artifacts, creates GitHub release with both files attached
- Uses `APPIMAGE_EXTRACT_AND_RUN=1` to run appimagetool without FUSE on CI runners
