"""
Screenshot script for AC Career GT Edition v1.18.x
Takes 8 screenshots for README, then updates README table.

Run with venv active:
    venv/Scripts/python.exe take_screenshots.py
"""

import json, os, shutil, sys, threading, time
import types

# ── Mock pywebview so Flask can start without a real window ─────────────────
mock_wv = types.ModuleType('webview')
mock_wv.FOLDER_DIALOG = 0
class _Win:
    def create_file_dialog(self, *a, **kw): return None
mock_wv.windows = [_Win()]
sys.modules['webview'] = mock_wv

from app import app

CAREER_DATA_PATH = os.path.join(os.path.dirname(__file__), 'career_data.json')
OUT = os.path.join(os.path.dirname(__file__), 'docs', 'screenshots')
os.makedirs(OUT, exist_ok=True)

# ── Rich demo career data ───────────────────────────────────────────────────
DEMO_CAREER = {
    "tier": 2,
    "season": 3,
    "team": "Ferrari GT3 Team",
    "car": "ferrari_488_gt3",
    "driver_name": "James Hunt",
    "races_completed": 6,
    "points": 97,
    "total_races": 14,
    "standings": [],
    "race_results": [
        {"race": 1, "track": "spa", "position": 2, "points": 18, "weather": "3_clear"},
        {"race": 2, "track": "monza", "position": 1, "points": 25, "weather": "4_mid_clear"},
        {"race": 3, "track": "ks_laguna_seca", "position": 4, "points": 12, "weather": "wet"},
        {"race": 4, "track": "mugello", "position": 3, "points": 15, "weather": "3_clear"},
        {"race": 5, "track": "imola", "position": 1, "points": 25, "weather": "4_mid_clear"},
        {"race": 6, "track": "spa", "position": 2, "points": 18, "weather": "3_clear"},
    ],
    "contracts": [
        {
            "team": "McLaren WEC Factory",
            "car": "mclaren_720s_gt3",
            "tier_name": "WEC / Elite",
            "offer_type": "factory",
            "target_tier": 3,
            "move": "promotion"
        },
        {
            "team": "Porsche WEC Semi",
            "car": "porsche_991_gt3_r",
            "tier_name": "WEC / Elite",
            "offer_type": "semi",
            "target_tier": 3,
            "move": "promotion"
        },
        {
            "team": "Aston WEC Customer",
            "car": "aston_martin_v12_vantage_gt3",
            "tier_name": "WEC / Elite",
            "offer_type": "customer",
            "target_tier": 3,
            "move": "promotion"
        }
    ],
    "final_position": 1,
    "race_started_at": None,
    "driver_history": {
        "Tom Harrison": {
            "seasons": [
                {"season": 1, "tier": "gt4",  "pos": 3,  "pts": 112},
                {"season": 2, "tier": "gt3",  "pos": 5,  "pts": 89},
                {"season": 3, "tier": "gt3",  "pos": 2,  "pts": 134}
            ]
        },
        "James Hunt": {
            "seasons": [
                {"season": 1, "tier": "mx5_cup", "pos": 1, "pts": 187},
                {"season": 2, "tier": "gt4",     "pos": 1, "pts": 201},
                {"season": 3, "tier": "gt3",     "pos": 1, "pts": 97}
            ]
        }
    },
    "career_settings": {
        "difficulty": "pro",
        "ai_offset": 0,
        "weather_mode": "realistic",
        "custom_tracks": None
    }
}

DEMO_LAP_ANALYSIS = {
    "lap_times":      [106210, 105480, 105820, 105190, 105680, 106010, 105350, 105720, 105440, 105900],
    "lap_count":      10,
    "best_lap_ms":    105190,
    "avg_lap_ms":     105680,
    "std_ms":         270,
    "consistency":    91,
    "engineer_report": "Excellent race — P2 finish. Very consistent pace throughout, lap times within 1 second of each other. Sector 2 is your strongest; work on Sector 3 braking zones next round.",
    "sector_analysis": [
        {"best_ms": 32100, "avg_ms": 32480, "std_ms": 130},
        {"best_ms": 38200, "avg_ms": 38540, "std_ms": 110},
        {"best_ms": 34890, "avg_ms": 35600, "std_ms": 280}
    ],
    "weakest_sector": 3,
    "tyre": "SM",
    "gap_to_leader_ms": 3840
}

# ── Save/restore career_data ────────────────────────────────────────────────
original_career = None
if os.path.exists(CAREER_DATA_PATH):
    with open(CAREER_DATA_PATH) as f:
        original_career = json.load(f)

def write_demo():
    with open(CAREER_DATA_PATH, 'w') as f:
        json.dump(DEMO_CAREER, f, indent=2)

def restore():
    if original_career is not None:
        with open(CAREER_DATA_PATH, 'w') as f:
            json.dump(original_career, f, indent=2)
    else:
        os.remove(CAREER_DATA_PATH)

# ── Start Flask in background ───────────────────────────────────────────────
write_demo()
t = threading.Thread(target=lambda: app.run(host='127.0.0.1', port=5000,
                                             debug=False, use_reloader=False), daemon=True)
t.start()
time.sleep(2)
print("Flask started")

# ── Playwright ──────────────────────────────────────────────────────────────
from playwright.sync_api import sync_playwright

W, H = 1440, 920

def shot(page, name, msg=''):
    path = os.path.join(OUT, name)
    page.screenshot(path=path)
    print(f"  OK {name}" + (f" - {msg}" if msg else ''))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={'width': W, 'height': H})

    # ── 1. Wizard ───────────────────────────────────────────────────────────
    print("[shot] 1/8 wizard.png")
    pg = ctx.new_page()
    pg.goto('http://127.0.0.1:5000', wait_until='networkidle')
    pg.wait_for_timeout(500)
    # Open the new-career wizard modal (correct ID: modal-new-career)
    pg.evaluate("""() => {
        if (typeof openModal === 'function') openModal('modal-new-career');
        if (typeof showWizardPage === 'function') showWizardPage(1);
        // Pre-select Pro difficulty so something is highlighted
        const di = document.querySelector('#diff-grid .wizard-preset[data-val="pro"]');
        if (di) di.classList.add('active');
        const wi = document.querySelector('#weather-grid .wizard-preset[data-val="realistic"]');
        if (wi) wi.classList.add('active');
    }""")
    pg.wait_for_timeout(500)
    shot(pg, 'wizard.png', 'career wizard')
    pg.close()

    # ── 2. career_running (main dashboard) ─────────────────────────────────
    print("[shot] 2/8 career_running.png")
    pg = ctx.new_page()
    pg.goto('http://127.0.0.1:5000', wait_until='networkidle')
    pg.wait_for_timeout(600)
    shot(pg, 'career_running.png', 'main dashboard')
    pg.close()

    # ── 3. season_end (contract offers) ─────────────────────────────────────
    print("[shot] 3/8 season_end.png")
    pg = ctx.new_page()
    pg.goto('http://127.0.0.1:5000', wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.evaluate("""() => {
        // renderContracts uses: team_name, tier_level, tier_name, car, description, id
        const contracts = [
            {id:'c1', team_name:'McLaren WEC Factory', tier_level:'Factory',
             tier_name:'WEC / Elite', car:'mclaren_720s_gt3',
             description:'Join the factory squad as first driver next season.'},
            {id:'c2', team_name:'Porsche WEC Semi',    tier_level:'Semi',
             tier_name:'WEC / Elite', car:'porsche_991_gt3_r',
             description:'Semi-works entry with factory technical support.'},
            {id:'c3', team_name:'Aston WEC Customer',  tier_level:'Customer',
             tier_name:'WEC / Elite', car:'aston_martin_v12_vantage_gt3',
             description:'Customer entry with full pit crew allocation.'}
        ];
        const posEl = document.getElementById('final-pos-text');
        if (posEl) posEl.textContent = 'You finished P1 with 97 points.';
        if (typeof renderContracts === 'function') renderContracts(contracts);
        if (typeof showView === 'function') showView('contracts');
    }""")
    pg.wait_for_timeout(400)
    shot(pg, 'season_end.png', 'contract offers')
    pg.close()

    # ── 4. settings ─────────────────────────────────────────────────────────
    print("[shot] 4/8 settings.png")
    pg = ctx.new_page()
    pg.goto('http://127.0.0.1:5000', wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.evaluate("""() => {
        if (typeof showView === 'function') showView('config');
    }""")
    pg.wait_for_timeout(400)
    shot(pg, 'settings.png', 'settings panel')
    pg.close()

    # ── 5. driver_card ──────────────────────────────────────────────────────
    print("[shot] 5/8 driver_card.png")
    pg = ctx.new_page()
    pg.goto('http://127.0.0.1:5000', wait_until='networkidle')
    pg.wait_for_timeout(600)
    # Switch to GT3 standings tier (index 2) then click a driver
    pg.evaluate("() => { if (typeof switchStandingsTier === 'function') switchStandingsTier(2); }")
    pg.wait_for_timeout(500)
    pg.evaluate("""() => {
        if (typeof showDriverProfile === 'function')
            showDriverProfile('Tom Harrison', 'ferrari_488_gt3', 1);
    }""")
    pg.wait_for_timeout(700)
    shot(pg, 'driver_card.png', 'driver profile card with 5 bars')
    pg.close()

    # ── 6. team_modal ───────────────────────────────────────────────────────
    print("[shot] 6/8 team_modal.png")
    pg = ctx.new_page()
    pg.goto('http://127.0.0.1:5000', wait_until='networkidle')
    pg.wait_for_timeout(600)
    # Switch to GT3 tier and teams mode so allStandings is populated
    pg.evaluate("() => { if (typeof switchStandingsTier === 'function') switchStandingsTier(2); }")
    pg.wait_for_timeout(500)
    pg.evaluate("() => { if (typeof switchChampMode === 'function') switchChampMode('teams'); }")
    pg.wait_for_timeout(400)
    # Read first real team from allStandings and call showTeamProfile with it
    team_info = pg.evaluate("""() => {
        const tierK = 'gt3';
        const teams = (allStandings[tierK] || {}).teams || [];
        if (teams.length > 0) return {name: teams[0].team, car: teams[0].car || ''};
        return null;
    }""")
    if team_info:
        pg.evaluate("""(t) => {
            if (typeof showTeamProfile === 'function')
                showTeamProfile(t.name, t.car);
        }""", team_info)
    pg.wait_for_timeout(700)
    shot(pg, 'team_modal.png', 'team modal with class badge')
    pg.close()

    # ── 7. player_card (NEW) ────────────────────────────────────────────────
    print("[shot] 7/8 player_card.png")
    pg = ctx.new_page()
    pg.goto('http://127.0.0.1:5000', wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.evaluate("""() => {
        if (typeof showPlayerProfile === 'function') showPlayerProfile();
    }""")
    pg.wait_for_timeout(800)
    shot(pg, 'player_card.png', 'player driver card (new)')
    pg.close()

    # ── 8. debrief ──────────────────────────────────────────────────────────
    print("[shot] 8/8 debrief.png")
    pg = ctx.new_page()
    pg.goto('http://127.0.0.1:5000', wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.evaluate("""() => {
        if (typeof showView === 'function') showView('result');
        // Show the result-found section with fake data
        const rf = document.getElementById('result-found');
        if (rf) rf.classList.remove('hidden');
        const ra = document.getElementById('result-auto');
        if (ra) ra.style.display = 'none';
        const pos = document.getElementById('rf-pos');
        if (pos) pos.textContent = 'P2';
        const pts = document.getElementById('rf-points');
        if (pts) pts.textContent = '18 pts';
        const lap = document.getElementById('rf-best-lap');
        if (lap) lap.textContent = '1:45.190';
        const lps = document.getElementById('rf-laps');
        if (lps) lps.textContent = '10 / 10';
        // Unhide debrief panel (renderDebrief fills it but never unhides it)
        const dp = document.getElementById('debrief-panel');
        if (dp) dp.classList.remove('hidden');
        const ds = document.getElementById('debrief-sectors');
        if (ds) ds.classList.remove('hidden');
        const dm = document.getElementById('debrief-meta');
        if (dm) dm.classList.remove('hidden');
    }""")
    pg.wait_for_timeout(200)
    pg.evaluate("() => { const d = %s; if (typeof renderDebrief === 'function') renderDebrief(d, 2); }"
                % json.dumps(DEMO_LAP_ANALYSIS))
    pg.wait_for_timeout(500)
    shot(pg, 'debrief.png', 'post-race debrief')
    pg.close()

    browser.close()

print("\nDone! All 8 screenshots saved to docs/screenshots/")
restore()
print("career_data.json restored")
