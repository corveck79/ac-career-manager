"""
AC Career Manager - Flask Backend
Main application entry point
"""

from flask import Flask, render_template, jsonify, request, send_file, abort
from flask_cors import CORS
import json
import os
import subprocess
import sys
import statistics
import threading
import random
from datetime import datetime
from urllib.parse import urlsplit

from career_manager import CareerManager
from driver_progress import (
    DRIVER_SKILL_KEYS,
    _seed_int,
    compute_progress_deltas,
    driver_trend_label,
    ensure_driver_progress,
    evolve_driver_progress_for_race,
    advance_driver_progress_season,
    update_form_scores,
    process_retirements,
    update_rivalries,
)
from achievements import check_achievements, ACHIEVEMENTS, ACHIEVEMENT_ORDER
from platform_paths import (
    detect_ac_install_path,
    get_ac_docs_path,
    get_default_ac_install_path,
    get_webview_gui,
)

# ---------------------------------------------------------------------------
# Path helpers — work both as script and as frozen EXE
# ---------------------------------------------------------------------------

def get_app_dir():
    """Directory where config/save files live (next to EXE, or project root)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def ensure_config():
    """Copy config template to app dir if config.json is missing."""
    if not os.path.exists(CONFIG_PATH):
        if getattr(sys, 'frozen', False):
            bundled = os.path.join(sys._MEIPASS, 'config.json')
        else:
            # Dev mode: fall back to config_example.json next to app.py
            base = os.path.dirname(os.path.abspath(__file__))
            bundled = os.path.join(base, 'config_example.json')
        if os.path.exists(bundled) and os.path.abspath(bundled) != os.path.abspath(CONFIG_PATH):
            import shutil
            shutil.copy(bundled, CONFIG_PATH)


APP_DIR     = get_app_dir()
CONFIG_PATH = os.path.join(APP_DIR, 'config.json')
DATA_PATH   = os.path.join(APP_DIR, 'career_data.json')

ensure_config()

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__, template_folder='templates', static_folder='static')
ALLOWED_WEB_ORIGINS = {'http://127.0.0.1:5000', 'http://localhost:5000'}
CORS(app, resources={r'/api/*': {'origins': list(ALLOWED_WEB_ORIGINS)}})

TRACK_NAMES = {
    'ks_silverstone/national':         'Silverstone National',
    'ks_brands_hatch/indy':            'Brands Hatch Indy',
    'magione':                         'Magione',
    'ks_vallelunga/club_circuit':      'Vallelunga Club',
    'ks_black_cat_county/layout_long': 'Black Cat County',
    'ks_silverstone/gp':               'Silverstone GP',
    'ks_brands_hatch/gp':              'Brands Hatch GP',
    'ks_red_bull_ring/layout_national':'Red Bull Ring',
    'spa':                             'Spa-Francorchamps',
    'monza':                           'Monza',
    'ks_laguna_seca':                  'Laguna Seca',
    'mugello':                         'Mugello',
    'imola':                           'Imola',
}

def _is_allowed_web_origin(value):
    """Allow only local UI origins for API write requests."""
    if not value:
        return False
    try:
        parsed = urlsplit(value)
    except Exception:
        return False
    if parsed.scheme != 'http':
        return False
    return f'http://{parsed.netloc}' in ALLOWED_WEB_ORIGINS


@app.before_request
def guard_api_write_origin():
    """Block cross-site write requests against localhost API."""
    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return None
    if not request.path.startswith('/api/'):
        return None

    origin = request.headers.get('Origin')
    referer = request.headers.get('Referer')
    if origin and not _is_allowed_web_origin(origin):
        return jsonify({'status': 'error', 'message': 'Forbidden origin'}), 403
    if not origin and referer and not _is_allowed_web_origin(referer):
        return jsonify({'status': 'error', 'message': 'Forbidden referer'}), 403
    return None

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)


def load_career_data():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return _default_career()


def save_career_data(data):
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)



def _fmt_track(track_id):
    """Convert AC track folder ID to a readable display name."""
    if not track_id:
        return 'Unknown'
    # Strip config suffix (e.g. 'ks_brands_hatch-gp' → 'ks_brands_hatch')
    base = track_id.split('-')[0] if '-' in track_id else track_id
    # Remove common prefixes
    for prefix in ('ks_', 'ac_', 'csp_'):
        if base.startswith(prefix):
            base = base[len(prefix):]
    # Title-case, replace underscores with spaces
    return base.replace('_', ' ').title()


def _add_news(career_data, event_type, text, icon, tier=None):
    """Append an event to the paddock news feed (max 100 entries).
    Deduplicates: won't add if exact same type+text already exists at same season+race."""
    news = career_data.setdefault('paddock_news', [])
    season = career_data.get('season', 1)
    race = career_data.get('races_completed', 0)
    # Deduplicate — prevent spam from per-race checks
    for existing in news[:20]:  # only check recent entries for speed
        if (existing.get('type') == event_type and existing.get('text') == text
                and existing.get('season') == season):
            return
    news.insert(0, {
        'season': season,
        'race': race,
        'type': event_type,
        'text': text,
        'icon': icon,
        'tier': tier,
    })
    if len(news) > 100:
        career_data['paddock_news'] = news[:100]


def _pick_template(templates, seed_text):
    """Deterministically pick a template string from a list, seeded by text."""
    return templates[_seed_int(seed_text, 0, len(templates) - 1)]


# ── News text templates (variety!) ──────────────────────────────────────────
_RETIREMENT_TEMPLATES = [
    "{name} ({age}) retires after a long career",
    "{name} ({age}) hangs up the helmet",
    "{name} ({age}) announces retirement from racing",
    "{name} ({age}) calls time on a distinguished career",
    "{name} ({age}) steps away from the grid",
    "{name} ({age}) closes the book on a racing career",
    "Racing farewell: {name} ({age}) announces the end of their career",
    "{name} ({age}) confirms retirement after years of competition",
    "The paddock says goodbye to {name} ({age})",
    "{name} ({age}) parks up for the last time",
]
_RETIREMENT_NICK_TEMPLATES = [
    "{name} ({age}) retires: '{nick}' hangs up the helmet",
    "'{nick}' {name} ({age}) announces retirement",
    "{name} ({age}) bows out. Farewell, '{nick}'",
    "End of an era: '{nick}' {name} ({age}) retires",
    "The paddock will miss '{nick}' — {name} ({age}) calls it a career",
    "'{nick}' is gone: {name} ({age}) steps away from racing",
    "Goodbye to '{nick}': {name} ({age}) hangs up the helmet for good",
    "A legend departs — '{nick}' {name} ({age}) retires",
]
_SWAP_TEMPLATES = [
    "{team} replaced {dropped} with {replacement} for the remainder of the season",
    "{team} drops {dropped}, signs {replacement} as mid-season replacement",
    "Driver change at {team}: {replacement} in, {dropped} out",
    "{dropped} loses seat at {team}; {replacement} called up",
    "{team} make a bold call: {dropped} stood down, {replacement} steps in",
    "Shock move at {team} — {replacement} replaces {dropped} mid-season",
    "{team} act fast: {dropped} dropped, {replacement} given the drive",
    "{replacement} gets their chance at {team} as {dropped} is shown the door",
    "Results cost {dropped} the seat — {replacement} arrives at {team}",
]
_RIVALRY_TEMPLATES = [
    "Rivalry brewing: {d1} vs {d2}",
    "Tensions rising between {d1} and {d2}",
    "{d1} and {d2} locked in a fierce battle",
    "The gloves are off: {d1} vs {d2}",
    "{d1} has {d2} in their sights",
    "Close racing turning personal: {d1} vs {d2}",
    "Neither giving an inch — {d1} and {d2} going wheel to wheel",
    "One to watch: {d1} vs {d2}, race by race",
    "A rivalry is born: {d1} and {d2} refuse to yield",
    "Personal battles on track: {d1} versus {d2} heating up",
]
_FORM_HOT_TEMPLATES = [
    "{name} is on a hot streak!",
    "{name} is in scintillating form",
    "{name} can do no wrong right now",
    "Unstoppable: {name} keeps delivering",
    "{name} is absolutely flying at the moment",
    "Nobody on the grid is matching {name} for form right now",
    "{name} has found something special — results keep coming",
    "On fire: {name} is setting the pace race after race",
    "Everything is clicking for {name} — a driver in peak form",
    "{name} is making it look effortless out there",
]
_FORM_COLD_TEMPLATES = [
    "{name} is struggling for form",
    "{name} is having a season to forget",
    "Tough times for {name}, results not coming",
    "{name} under pressure after poor run of results",
    "Questions being asked at {name}'s camp — where has the pace gone?",
    "{name} can't seem to catch a break right now",
    "A driver under pressure: {name} needs to turn things around fast",
    "The results have dried up for {name} — a concerning run continues",
    "{name} looking for answers after another disappointing weekend",
    "Something's not clicking for {name} — form is worryingly poor",
]
_CHAMPION_TEMPLATES = [
    "{tier}: {name} wins the championship!",
    "{tier}: {name} crowned champion!",
    "{tier}: Title glory for {name}!",
    "{tier}: {name} takes the drivers' title!",
    "{tier}: {name} is champion — a deserved triumph!",
    "{tier}: What a season from {name} — championship won!",
    "{tier}: {name} delivers the title in style!",
    "{tier}: {name} seals it — the championship is theirs!",
    "{tier}: Dominant. Clinical. Champion. That's {name}.",
    "{tier}: They said it was possible — {name} proves it. Champion!",
]
_TEAM_UP_TEMPLATES = [
    "{team} ({tier}): strong season results in a performance boost",
    "{team} invests in development after a solid {tier} campaign",
    "Good news at {team}: {tier} performance upgrade confirmed",
    "{team} reap the rewards of a strong {tier} season",
    "Off-season development pays off at {team} in {tier}",
    "{team} capitalise on {tier} success with technical improvements",
    "A winter of hard work: {team} emerge stronger for {tier}",
    "{team} on the up — {tier} form translating into real progress",
]
_TEAM_DOWN_TEMPLATES = [
    "{team} ({tier}): struggling after a difficult season",
    "{team} loses ground in {tier} — tough off-season ahead",
    "Budget cuts hit {team} ({tier}) hard this winter",
    "{team} facing questions after a poor {tier} campaign",
    "Hard times at {team} — {tier} results spark a rethink",
    "{team} under pressure to perform after a dismal {tier} showing",
    "The numbers don't lie: {team} fall behind in {tier} development",
    "A difficult winter for {team} after struggling in {tier}",
]
_MILESTONE_TEMPLATES = {
    'first_win':    [
        "A moment to remember: {name} takes a maiden victory!",
        "{name} breaks through with a first career win!",
        "History made! {name} wins for the first time!",
        "They've done it! {name} takes that elusive first victory!",
        "First win for {name} — a career milestone that won't be forgotten!",
        "The wait is over: {name} stands on the top step for the first time!",
    ],
    'first_podium': [
        "{name} earns a first career podium, P{pos}!",
        "First podium for {name}! A P{pos} finish to celebrate.",
        "{name} steps onto the podium for the first time — P{pos}!",
        "Career milestone: {name} takes a P{pos} podium finish!",
        "P{pos} and a first trip to the podium for {name}. Brilliant.",
        "The podium! {name} gets there for the first time — P{pos}!",
        "{name} on the rostrum — first career podium, P{pos}!",
        "They'll remember this one: {name} claims a maiden podium at P{pos}.",
    ],
    'race_10':      [
        "{name} reaches 10 career races.",
        "Ten races in — {name} is finding their feet.",
        "Double figures: {name} hits the 10-race mark.",
        "Race ten for {name}. The grid is getting familiar.",
        "Ten starts in the books for {name} — the learning curve is flattening.",
        "A milestone in the making: {name} completes race number ten.",
    ],
    'race_25':      [
        "{name} hits 25 career races. A seasoned competitor now.",
        "Twenty-five races down for {name} — experience is building.",
        "Quarter century of starts: {name} hits race 25.",
        "{name} reaches 25 races — no longer a rookie by any measure.",
        "Race 25 for {name}. Experience counts, and they're accumulating it.",
        "Twenty-five starts: {name} is a proper championship regular now.",
    ],
    'race_50':      [
        "{name} completes 50 career races! A true veteran.",
        "Fifty starts and counting — {name} has seen it all.",
        "Half a century of races for {name}. Remarkable.",
        "Race 50 for {name} — half a hundred and still going strong.",
        "{name} hits fifty starts. The paddock has a new veteran.",
        "Fifty races in: {name} has earned every grey hair on this grid.",
    ],
    'race_100':     [
        "100 races for {name}! What a career.",
        "The century! {name} reaches 100 career starts.",
        "One hundred races — {name} is a true legend of the paddock.",
        "Race 100 for {name}. An extraordinary milestone.",
        "{name} hits the century mark — 100 starts and the hunger is still there.",
        "A hundred races. {name} has given everything to this sport.",
        "Century club: {name} joins an elite group with race number 100.",
    ],
    'tier_first_win': [
        "{name} takes a first {tier} victory!",
        "First win in {tier} for {name}!",
        "{name} breaks through in {tier} — first win secured!",
        "A new tier, a new win: {name} triumphs in {tier}!",
        "{name} announces themselves in {tier} with a first victory!",
        "Winner in {tier}: {name} delivers when it counts.",
        "{name} gets {tier} off to the best possible start — first win in the bag!",
    ],
}
_ROOKIE_TEMPLATES = [
    "{name} makes their championship debut",
    "{name} joins the grid as a fresh face",
    "Rookie {name} gets the call-up to race",
    "New talent: {name} enters the championship",
    "{name} steps into the spotlight — championship debut confirmed",
    "Eyes on the newcomer: {name} is on the grid",
    "The next generation arrives: {name} makes their debut",
    "Debut time for {name} — the grid just got more interesting",
    "{name} earns their place — championship debut incoming",
]
_MOVE_TEMPLATES = {
    'promotion': [
        "{name} promoted to {tier}!",
        "{name} moves up to {tier}!",
        "Step up for {name}: joining {tier}!",
        "Onwards and upwards: {name} earns a place in {tier}!",
        "{name} graduates to {tier} — a well-earned promotion!",
        "{name} takes the next step — {tier} awaits!",
        "Big season ahead: {name} joins {tier}!",
    ],
    'relegation': [
        "{name} drops down to {tier}.",
        "{name} relegated to {tier} after a tough season.",
        "A setback for {name}: dropping to {tier}.",
        "{name} returns to {tier} — back to rebuild.",
        "Down but not out: {name} heads to {tier} for a fresh start.",
    ],
    'stay': [
        "{name} stays in {tier} for another season.",
        "{name} extends in {tier}.",
        "{name} commits to {tier} — unfinished business.",
        "Another season in {tier} for {name} — the job isn't done yet.",
        "{name} remains in {tier}: targeting better results next year.",
    ],
}
_TITLE_FIGHT_TEMPLATES = [
    "{tier}: Only {gap} points separate the top 3!",
    "{tier}: Tight at the top, {gap} points cover P1 to P3!",
    "Nail-biter in {tier}: {gap}-point gap in the title race!",
    "{tier}: It's all to play for — {gap} points between the title contenders!",
    "Championship wide open in {tier}: just {gap} points in it!",
    "{tier}: Nobody is pulling away — {gap} points covers the top 3!",
    "This is what motorsport is about: {gap}-point title gap in {tier}!",
]
_TITLE_DECIDED_TEMPLATES = [
    "{tier}: {name} clinches the title with {remaining} races to go!",
    "{tier}: {name} is champion! Sealed it with {remaining} rounds remaining.",
    "It's over in {tier}: {name} wraps up the championship early!",
    "{tier}: Mathematical. {name} is champion — {remaining} races to spare!",
    "{name} delivers in {tier}: title sewn up with {remaining} races left!",
    "{tier}: Done and dusted. {name} is champion with {remaining} to go.",
    "Early celebrations in {tier}: {name} takes the title with {remaining} rounds remaining!",
]
_WET_SPECIALIST_TEMPLATES = [
    "{name} shows wet-weather mastery after the rain",
    "Rain brings out the best in {name}",
    "{name}'s wet skills shine through in tricky conditions",
    "Wet track, no problem: {name} thrives in the rain",
    "{name} is a different driver when it's wet out there",
    "The rain is {name}'s friend — another strong wet-weather showing",
    "{name} growing stronger in the wet race by race",
    "Puddles, spray, and a fast {name} — wet conditions suit this driver",
]
_COMEBACK_TEMPLATES = [
    "{name} is staging a remarkable comeback",
    "What a turnaround from {name}!",
    "{name} fights back from a rough start to the season",
    "Don't write {name} off — they're back in the mix!",
    "The comeback is real: {name} is climbing back up the order",
    "{name} refused to give up — and it's paying off now",
    "From the back foot to fighting fit: {name}'s season is turning around",
    "Character shown: {name} bounces back after a difficult run",
]
_VETERAN_TEMPLATES = [
    "Veteran {name} ({age}) begins what could be a final season",
    "{name} ({age}) enters the twilight of a long career",
    "How long can {name} ({age}) keep going?",
    "Still going strong: {name} ({age}) lines up for another campaign",
    "{name} ({age}) refuses to walk away — another season on the grid",
    "The old guard: {name} ({age}) is still here and still competitive",
    "{name} ({age}) — experience you can't buy, still delivering on track",
    "Another year, another fight: {name} ({age}) isn't done yet",
]
_TEAMMATE_BATTLE_TEMPLATES = [
    "Internal battle at {team}: {d1} and {d2} separated by just {gap} points",
    "Tension at {team}: teammates {d1} and {d2} only {gap} points apart",
    "{team} teammates {d1} and {d2} in a tight fight ({gap}-point gap)",
    "The garage is split: {d1} and {d2} locked in a {gap}-point battle at {team}",
    "Who's the lead driver? {team}'s {d1} and {d2} are {gap} points apart",
    "Awkward atmosphere at {team}: {d1} vs {d2}, only {gap} points in it",
    "Intra-team warfare at {team} — {d1} and {d2} refuse to give ground",
]
_BIGGEST_MOVER_TEMPLATES = [
    "{name} climbs {gain} positions in the {tier} standings!",
    "Big mover: {name} up {gain} places in {tier}!",
    "{name} surges {gain} spots in the {tier} championship!",
    "Charging through the field: {name} gains {gain} positions in {tier}!",
    "{name} making waves — up {gain} in the {tier} standings!",
    "Look who's moving: {name} climbs {gain} places in {tier}!",
    "The momentum is with {name} — {gain} positions gained in {tier}!",
]
_PLAYER_RIVALRY_TEMPLATES = [
    "You and {name} are separated by just {gap} pts in {tier}",
    "{gap}-point gap: you vs {name} in {tier}",
    "Title battle heating up: {gap} pts between you and {name} in {tier}",
    "Watch out for {name} — only {gap} points between you in {tier}",
    "{name} is right on your tail in {tier} — just {gap} points back",
    "Keep an eye on {name}: {gap} points cover you both in {tier}",
    "This is personal: {gap} pts between you and {name} in {tier}",
    "The rivalry intensifies — {gap} points separate you from {name} in {tier}",
    "{name} won't let go — {gap} points behind you in {tier}",
]

_BOSS_CHAMPION_TEMPLATES = [
    "Champion! Everything we worked for, delivered. Unbelievable season.",
    "P1 in the championship — I've been in this sport a long time. This never gets old.",
    "You've done it. Title won. This whole team couldn't be prouder.",
    "Championship secured. Everything clicked this season. Outstanding.",
    "I knew it from race one. You had what it takes. Champion.",
    "We came here to win a title. Job done. Simple as that.",
    "This is why we do it. You are champion — enjoy every second of this.",
    "The title is ours. You drove the season of your life. Remarkable.",
    "I've worked with a lot of drivers. What you did this season? Special.",
    "Title. Yours. Well deserved. The whole paddock knows you earned it.",
]
_BOSS_WIN_TEMPLATES = [
    "P{pos} — but {wins_text} this season. That pace is undeniable.",
    "{wins_text} on the board. That's exactly the kind of season we were targeting.",
    "Not the title, but {wins_text}. The speed is there. We'll push for the championship next year.",
    "P{pos} in the standings, but {wins_text} tells the real story. You've got it.",
    "{wins_text} this year. That's a foundation we can build on. Good season.",
    "A race winner — multiple times. P{pos} overall, but the ceiling is higher. We'll get there.",
    "{wins_text} and a P{pos} finish. I'll take that. Next year we go for the lot.",
]
_BOSS_PODIUM_TEMPLATES = [
    "P{pos} with podiums in the bag. We're on the right track.",
    "Consistent points and podiums — that's how you build a career. Well done.",
    "Not the result we dreamed of, but those podiums show what's possible. Good foundation.",
    "P{pos} and on the podium more than once. There's something here. We develop it.",
    "Podiums mean pace. P{pos} is respectable. Now we turn 'good' into 'great'.",
    "I saw the potential. P{pos} this season with podiums — next season we push harder.",
    "Solid. That's the word. P{pos} with podiums. Exactly what we needed from year one.",
]
_BOSS_MIDFIELD_TEMPLATES = [
    "P{pos} — we showed flashes this season. Next year we aim higher.",
    "Points scored when it mattered. P{pos} isn't the ceiling — we both know that.",
    "A learning season. P{pos} is honest. We'll use it as fuel.",
    "P{pos}. Not where we want to be, but not where we'll stay. Keep working.",
    "Midfield is a start, not a destination. P{pos} this year. Higher next.",
    "We had speed at times. P{pos} is the result. We fix what held us back.",
    "P{pos} — I've seen enough to know we'll be competing for more next season.",
]
_BOSS_STRUGGLE_TEMPLATES = [
    "P{pos}. Tough year. But I've seen the work ethic — we'll come back stronger.",
    "Not what we planned for. P{pos} stings, but that's racing. We regroup and go again.",
    "It wasn't our season. P{pos} is the result, but the fight in this team hasn't changed.",
    "P{pos}. Look, it hurt. But setbacks are part of the sport. We learn and move on.",
    "I won't sugarcoat it — P{pos} is not good enough. We fix it. Together.",
    "Hard season. P{pos}. The team gave everything. Now we figure out what went wrong.",
    "P{pos} and a long winter ahead. But I've been through difficult seasons before. We come back.",
]


def _team_boss_message(position, wins, podiums, team_count, tier_key, season):
    """Generate a seeded team boss quote for the season recap."""
    seed = f"boss|{position}|{wins}|{tier_key}|{season}"
    wins_text = f"{wins} win{'s' if wins > 1 else ''}"
    fmt = {'pos': position, 'wins_text': wins_text}
    if position == 1:
        return _pick_template(_BOSS_CHAMPION_TEMPLATES, seed)
    if wins > 0:
        return _pick_template(_BOSS_WIN_TEMPLATES, seed).format(**fmt)
    if podiums > 0:
        return _pick_template(_BOSS_PODIUM_TEMPLATES, seed).format(**fmt)
    if position <= team_count // 2:
        return _pick_template(_BOSS_MIDFIELD_TEMPLATES, seed).format(**fmt)
    return _pick_template(_BOSS_STRUGGLE_TEMPLATES, seed).format(**fmt)


def _find_most_improved(career_data):
    """Return name of the AI driver with the highest positive season skill delta."""
    progress = career_data.get('driver_progress', {})
    retired = set(career_data.get('retired_drivers', []))
    best_name, best_delta = None, 0.0
    for name, entry in progress.items():
        if name in retired:
            continue
        deltas = compute_progress_deltas(entry).get('season', {})
        net = sum(float(deltas.get(k, 0)) for k in DRIVER_SKILL_KEYS)
        if net > best_delta:
            best_delta, best_name = net, name
    return best_name


def _is_ac_running():
    """Best-effort check whether Assetto Corsa is still running."""
    try:
        if os.name == 'nt':
            cp = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq acs.exe'],
                capture_output=True, text=True, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return 'acs.exe' in (cp.stdout or '').lower()
        cp = subprocess.run(['pgrep', '-f', 'acs'], capture_output=True, text=True, check=False)
        return cp.returncode == 0
    except Exception:
        return False


def _require_json_object():
    """Return parsed JSON object or a 400 response tuple."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400)
    return data, None

def _parse_optional_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _set_ac_install_path(cfg, path):
    """Store AC install path and optional Content Manager path in config dict."""
    paths = cfg.setdefault('paths', {})
    paths['ac_install'] = path
    cm = os.path.join(path, 'Content Manager.exe')
    if os.path.exists(cm):
        paths['content_manager'] = cm


def _recommended_ai_delta(position, margin_ms=None):
    """Simple adaptive AI adjustment based on result dominance."""
    if position == 1:
        if margin_ms is not None and margin_ms >= 30000:
            return 3
        if margin_ms is not None and margin_ms >= 15000:
            return 2
        if margin_ms is not None and margin_ms >= 7000:
            return 1
        return 1
    if position >= 10:
        return -2
    if position >= 7:
        return -1
    return 0


def _default_career():
    return {
        'tier':            0,
        'season':          1,
        'team':            None,
        'car':             None,
        'driver_name':     '',
        'races_completed': 0,
        'points':          0,
        'standings':       [],
        'race_results':    [],
        'contracts':       None,
        'player_history':  [],
        'driver_progress': {},
        'rival_name':      None,
    }


def _fmt_track(track_id):
    return TRACK_NAMES.get(track_id, track_id.replace('_', ' ').title())


def _get_career_tracks(tier_key, tier_info, career_data):
    """Return the effective track list for a tier.
    Uses career_settings.custom_tracks[tier_key] if set, otherwise config defaults.
    """
    cs = career_data.get('career_settings') or {}
    ct = cs.get('custom_tracks') or {}
    return ct.get(tier_key) or tier_info['tracks']


def _parse_length(raw):
    """Parse track length from ui_track.json — may be int, float, or string."""
    if not raw:
        return 0
    if isinstance(raw, (int, float)):
        return int(raw)
    s = str(raw).strip().lower().replace(',', '.').replace(' ', '')
    s = s.replace('km', '').replace('m', '')
    try:
        val = float(s)
        return int(val * 1000 if val < 100 else val)
    except ValueError:
        return 0


def _fmt_lap_ms(ms):
    """Format a lap time from milliseconds → MM:SS.mmm string."""
    if not ms or ms <= 0:
        return '–'
    mins = int(ms) // 60000
    secs = (int(ms) % 60000) / 1000
    return f'{mins}:{secs:06.3f}'


def _generate_engineer_report(position, total_drivers, valid_laps):
    """Generate a short engineer debrief text from race result + individual lap times."""
    if not valid_laps or len(valid_laps) < 2:
        return 'Not enough lap data for analysis.'

    std_ms = statistics.stdev(valid_laps)

    # Position comment
    if position == 1:
        pos_msg = 'Excellent race – P1! The team is ecstatic.'
    elif position <= 3:
        pos_msg = f'Solid podium, P{position}. Good result for the team.'
    elif position <= 5:
        pos_msg = f'P{position}, in the points. A decent afternoon.'
    elif position <= max(1, total_drivers // 2):
        pos_msg = f'P{position}, midfield finish. There\'s more pace in the car.'
    else:
        pos_msg = f'P{position}, a tough race. We\'ll debrief and come back stronger.'

    # Consistency comment
    if std_ms < 500:
        cons_msg = 'Incredibly consistent lap times – near-perfect rhythm.'
    elif std_ms < 1000:
        cons_msg = 'Good consistency throughout the stint.'
    elif std_ms < 2000:
        cons_msg = 'Some variation in lap times – tyre deg or traffic?'
    else:
        cons_msg = 'Significant lap time variation. Focus on a more consistent rhythm.'

    # Pace trend: compare first third vs last third (only if enough laps)
    n = len(valid_laps)
    trend_msg = ''
    if n >= 6:
        third     = n // 3
        early_avg = sum(valid_laps[:third]) / third
        late_avg  = sum(valid_laps[-third:]) / third
        diff_ms   = late_avg - early_avg
        if diff_ms < -300:
            trend_msg = 'You found more pace as the race progressed – great tyre management.'
        elif diff_ms > 300:
            trend_msg = 'Pace dropped in the closing laps – possible tyre wear.'
        else:
            trend_msg = 'Pace was stable throughout – solid race management.'

    parts = [pos_msg, cons_msg]
    if trend_msg:
        parts.append(trend_msg)
    return ' '.join(parts)


def _effective_tier_info(tier_key, tier_info, career_data):
    """Return a shallow copy of tier_info with tracks overridden from career_settings."""
    tracks = _get_career_tracks(tier_key, tier_info, career_data)
    if tracks is tier_info['tracks']:
        return tier_info          # nothing to override, return original
    info = dict(tier_info)
    info['tracks'] = tracks
    return info


# ---------------------------------------------------------------------------
# Initialise career manager
# ---------------------------------------------------------------------------
config = load_config()
career = CareerManager(config)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    career_data = load_career_data()
    cfg         = load_config()
    return render_template('dashboard.html', career_data=career_data, config=cfg)


@app.route('/api/setup-status')
def setup_status():
    cfg = load_config()
    ac_path = (cfg.get('paths', {}) or {}).get('ac_install', '').strip()
    valid = bool(ac_path) and os.path.exists(os.path.join(ac_path, 'acs.exe'))
    auto_detected = False

    # First-run convenience: auto-detect and persist AC install when path is missing/invalid.
    if not valid:
        detected = detect_ac_install_path()
        if detected:
            _set_ac_install_path(cfg, detected)
            save_config(cfg)
            ac_path = detected
            valid = True
            auto_detected = True

    default_hint = '' if ac_path else get_default_ac_install_path()
    return jsonify({
        'valid': valid,
        'path': ac_path,
        'default_hint': default_hint,
        'auto_detected': auto_detected,
    })


@app.route('/api/save-ac-path', methods=['POST'])
def save_ac_path():
    data, err = _require_json_object()
    if err:
        return err
    path    = data.get('path', '').strip()
    if not os.path.exists(os.path.join(path, 'acs.exe')):
        return jsonify({'status': 'error', 'message': 'acs.exe niet gevonden in die map'}), 400
    cfg = load_config()
    _set_ac_install_path(cfg, path)
    save_config(cfg)
    return jsonify({'status': 'success'})


@app.route('/api/career-status')
def get_career_status():
    career_data = load_career_data()
    career_data['total_races'] = career.get_tier_races(career_data)
    cfg = load_config()
    ac_path = cfg.get('paths', {}).get('ac_install', '')
    career_data['csp_status'] = detect_csp(ac_path)
    return jsonify(career_data)


@app.route('/api/standings')
def get_standings():
    career_data = load_career_data()
    tier_info   = career.get_tier_info(career_data['tier'])
    standings   = career.generate_standings(tier_info, career_data)
    return jsonify({
        'standings':       standings,
        'races_completed': career_data['races_completed'],
        'total_races':     career.get_tier_races(career_data),
    })


@app.route('/api/all-standings')
def get_all_standings():
    career_data = load_career_data()
    all_s, tier_progress = career.generate_all_standings(career_data)
    form_scores = career_data.get('form_scores', {})
    # Annotate each driver entry with their form score
    for tier_data in all_s.values():
        for entry in tier_data.get('drivers', []):
            dname = entry.get('driver', '')
            if dname in form_scores:
                entry['form_score'] = round(form_scores[dname], 2)
    return jsonify({
        'all_standings':   all_s,
        'tier_progress':   tier_progress,
        'current_tier':    career_data.get('tier', 0),
        'races_completed': career_data.get('races_completed', 0),
        'total_races':     career.get_tier_races(career_data),
    })


@app.route('/api/season-calendar')
def get_season_calendar():
    career_data    = load_career_data()
    cfg            = load_config()
    tier_key       = career.tiers[career_data['tier']]
    tier_info      = cfg['tiers'][tier_key]
    tracks         = _get_career_tracks(tier_key, tier_info, career_data)
    races_per_tier = len(tracks)
    races_done     = career_data['races_completed']
    race_results   = career_data.get('race_results', [])

    cal = []
    for i in range(races_per_tier):
        track_id = tracks[i]
        if i < races_done:
            status = 'completed'
        elif i == races_done:
            status = 'next'
        else:
            status = 'upcoming'
        result = race_results[i] if i < len(race_results) else None
        cal.append({
            'round':      i + 1,
            'track':      track_id,
            'track_name': _fmt_track(track_id),
            'status':     status,
            'result':     result,
        })
    return jsonify(cal)


@app.route('/api/next-race')
def get_next_race():
    career_data  = load_career_data()
    cfg          = load_config()
    tier_index   = career_data['tier']
    tier_key     = career.tiers[tier_index]
    tier_info    = _effective_tier_info(tier_key, career.get_tier_info(tier_index), career_data)
    race_num     = career_data['races_completed'] + 1
    season       = career_data.get('season', 1)
    cs           = career_data.get('career_settings') or {}
    weather_mode = cs.get('weather_mode', 'realistic')
    if not cs.get('dynamic_weather', True):
        weather_mode = 'always_clear'
    night_cycle  = cs.get('night_cycle', True)
    race = career.generate_race(tier_info, race_num, career_data['team'], career_data['car'],
                                tier_key=tier_key, season=season, weather_mode=weather_mode,
                                night_cycle=night_cycle, career_data=career_data)
    ai_offset = cs.get('ai_offset', 0)
    if ai_offset:
        race['ai_difficulty'] = max(60, min(100, race['ai_difficulty'] + ai_offset))
    return jsonify(race)


@app.route('/api/start-race', methods=['POST'])
def start_race():
    career_data  = load_career_data()
    cfg          = load_config()
    tier_index   = career_data['tier']
    tier_key     = career.tiers[tier_index]
    tier_info    = _effective_tier_info(tier_key, career.get_tier_info(tier_index), career_data)
    race_num     = career_data['races_completed'] + 1
    season       = career_data.get('season', 1)
    cs           = career_data.get('career_settings') or {}
    weather_mode = cs.get('weather_mode', 'realistic')
    if not cs.get('dynamic_weather', True):
        weather_mode = 'always_clear'
    night_cycle  = cs.get('night_cycle', True)
    race         = career.generate_race(tier_info, race_num, career_data['team'], career_data['car'],
                                        tier_key=tier_key, season=season, weather_mode=weather_mode,
                                        night_cycle=night_cycle, career_data=career_data)
    ai_offset = cs.get('ai_offset', 0)
    if ai_offset:
        race['ai_difficulty'] = max(60, min(100, race['ai_difficulty'] + ai_offset))
    race['driver_name'] = career_data.get('driver_name', 'Player')
    data, err = _require_json_object()
    if err:
        return err
    mode    = data.get('mode', 'race_only')

    # Simulate qualifying to determine AI grid order and career standings position.
    # The player always starts P1 in Race Only mode (AC constraint: player = CAR_0 = P1).
    opponents     = race.get('opponents', [])
    ai_lvl        = int(race['ai_difficulty'])
    quali_grid    = career.simulate_qualifying(opponents, ai_lvl, career_data=career_data)

    success = career.launch_ac_race(race, cfg, mode=mode, career_data=career_data,
                                    grid=quali_grid)
    if success:
        career_data['race_started_at'] = datetime.now().isoformat()
        career_data['last_race_weather'] = race.get('weather', '3_clear')
        save_career_data(career_data)
        return jsonify({'status': 'success', 'message': 'AC launched!', 'race': race})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to launch AC'}), 500


def _try_race_out_json(driver_name, start_time, race_seen):
    """Fallback: read out/race_out.json (Content Manager / newer AC format).

    Returns (data, results, player_result, player_position, race_seen) matching
    the shape expected by read_race_result().  On failure returns all-None tuple.
    """
    out_file = os.path.join(get_ac_docs_path('out'), 'race_out.json')
    if not os.path.isfile(out_file):
        return None, [], None, None, race_seen
    mtime = datetime.fromtimestamp(os.path.getmtime(out_file))
    if mtime < start_time:
        return None, [], None, None, race_seen

    try:
        with open(out_file, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return None, [], None, None, race_seen

    players  = raw.get('players', [])
    sessions = raw.get('sessions', [])
    if not players or not sessions:
        return None, [], None, None, race_seen

    # Find the RACE session (type 3) — take the last one if multiple
    race_session = None
    for s in reversed(sessions):
        if s.get('type') == 3 or (s.get('name') or '').upper() == 'RACE':
            race_session = s
            break
    if race_session is None:
        return None, [], None, None, race_seen

    race_seen = True
    race_result_indices = race_session.get('raceResult', [])
    if not race_result_indices:
        return None, [], None, None, race_seen

    # Build a results list that mirrors the classic AC format:
    #   [{DriverName, Laps, BestLap, TotalTime, ...}, ...]
    laps_raw = race_session.get('laps', [])

    # Group laps by car index
    car_laps = {}
    for lap in laps_raw:
        ci = lap.get('car')
        if ci is not None:
            car_laps.setdefault(ci, []).append(lap)

    # Best-lap lookup per car
    best_laps_raw = {bl['car']: bl['time'] for bl in race_session.get('bestLaps', [])
                     if isinstance(bl, dict)}

    results = []
    for car_idx in race_result_indices:
        if car_idx >= len(players):
            continue
        p = players[car_idx]
        p_laps = car_laps.get(car_idx, [])
        total_time = sum(l.get('time', 0) for l in p_laps)
        best_lap   = best_laps_raw.get(car_idx, 0)
        results.append({
            'DriverName': p.get('name', ''),
            'Laps':       len(p_laps),
            'BestLap':    best_lap,
            'TotalTime':  total_time,
            '_car_idx':   car_idx,
        })

    # Build a top-level 'Laps' array in classic format for debrief analysis
    classic_laps = []
    for lap in laps_raw:
        ci = lap.get('car')
        if ci is None or ci >= len(players):
            continue
        sectors = lap.get('sectors', [])
        classic_laps.append({
            'DriverName': players[ci].get('name', ''),
            'LapTime':    lap.get('time', 0),
            'Sectors':    sectors,
            'Cuts':       lap.get('cuts', 0),
            'Tyre':       lap.get('tyre', ''),
        })

    # Find player
    player_result = None
    player_position = None
    for i, r in enumerate(results):
        if r['DriverName'].lower() == driver_name.lower():
            player_result = r
            player_position = i + 1
            break

    if player_result is None:
        return None, results, None, None, race_seen

    # Package as a data dict with classic 'Laps' key for debrief compatibility
    data = {'Laps': classic_laps, '_source': 'race_out'}
    return data, results, player_result, player_position, race_seen


@app.route('/api/read-race-result')
def read_race_result():
    """Auto-read the latest AC race result from Documents/Assetto Corsa/results/ or out/race_out.json."""
    career_data = load_career_data()
    driver_name = career_data.get('driver_name', 'Player')

    race_started_at = career_data.get('race_started_at')
    if not race_started_at:
        return jsonify({'status': 'not_found', 'message': 'No race started'})

    try:
        # File mtimes may have second precision; normalize to avoid missing
        # results created in the same second as race start.
        start_time = datetime.fromisoformat(race_started_at).replace(microsecond=0)
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid race start timestamp'})

    if _is_ac_running():
        return jsonify({'status': 'waiting', 'message': 'Race in progress. Close AC to import result.'})

    tier_info     = career.get_tier_info(career_data['tier'])
    expected_laps = tier_info.get('race_format', {}).get('laps', 20)

    results_dir = get_ac_docs_path('results')
    if not os.path.exists(results_dir):
        return jsonify({'status': 'not_found', 'message': 'Results folder not found'})

    candidates = []
    for fname in os.listdir(results_dir):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(results_dir, fname)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime >= start_time:
            candidates.append((mtime, fpath))

    # ── Strategy 1: classic results/ folder (AC vanilla format) ──────────────
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)

    data = None
    results = []
    player_result = None
    player_position = None
    race_seen = False

    for _, result_file in (candidates or []):
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                candidate_data = json.load(f)
        except Exception:
            continue

        if candidate_data.get('Type', '').upper() != 'RACE':
            continue

        race_seen = True
        candidate_results = candidate_data.get('Result', [])
        for i, r in enumerate(candidate_results):
            if r.get('DriverName', '').lower() == driver_name.lower():
                data = candidate_data
                results = candidate_results
                player_result = r
                player_position = i + 1
                break
        if player_result is not None:
            break

    # ── Strategy 2: out/race_out.json (Content Manager / newer AC format) ──
    if player_result is None:
        data, results, player_result, player_position, race_seen = \
            _try_race_out_json(driver_name, start_time, race_seen)

    if player_result is None:
        msg = 'Driver not found in results' if race_seen else 'No race session result found yet'
        return jsonify({'status': 'not_found', 'message': msg})

    laps_completed = player_result.get('Laps', 0)
    total_time     = player_result.get('TotalTime', 0)
    best_lap_ms    = player_result.get('BestLap', 0)

    # race_out.json (Content Manager format) doesn't record player laps/time,
    # so skip the incomplete check when the result came from that source.
    from_race_out = isinstance(data, dict) and data.get('_source') == 'race_out'
    incomplete = (not from_race_out) and (
        (laps_completed < max(1, expected_laps // 2)) or (total_time == 0 and laps_completed == 0)
    )

    best_lap_fmt = ''
    if best_lap_ms and best_lap_ms > 0:
        mins         = best_lap_ms // 60000
        secs         = (best_lap_ms % 60000) / 1000
        best_lap_fmt = f'{mins:02d}:{secs:06.3f}'

    # ── Lap-by-lap debrief analysis ──────────────────────────────────────────
    # AC results JSON has a top-level 'Laps' array with per-lap times per driver.
    # Each lap object also carries Sectors, Cuts, and Tyre — used for rich debrief.
    raw_laps         = data.get('Laps', [])
    player_lap_objs  = [
        l for l in raw_laps
        if isinstance(l, dict)
        and l.get('DriverName', '').lower() == driver_name.lower()
        and isinstance(l.get('LapTime'), (int, float))
        and l['LapTime'] > 0
    ]
    all_player_laps = [l['LapTime'] for l in player_lap_objs]
    lap_analysis = {}
    if all_player_laps:
        lap_best_ms = min(all_player_laps)
        # Exclude in/out-lap style outliers (> 150% of the best lap)
        valid_laps     = [lt for lt in all_player_laps if lt <= lap_best_ms * 1.5]
        valid_lap_objs = [o for o in player_lap_objs if o['LapTime'] <= lap_best_ms * 1.5]
        if len(valid_laps) >= 2:
            avg_ms      = sum(valid_laps) / len(valid_laps)
            std_ms      = statistics.stdev(valid_laps)
            # consistency: 100 = perfect, drops ~1pt per 30ms of std dev
            consistency = max(0, min(100, int(100 - std_ms / 30)))
            total_d     = len(results)
            lap_analysis = {
                'lap_times':       valid_laps,
                'lap_count':       len(valid_laps),
                'best_lap_ms':     lap_best_ms,
                'avg_lap_ms':      round(avg_ms),
                'std_ms':          round(std_ms),
                'consistency':     consistency,
                'engineer_report': _generate_engineer_report(
                    player_position, total_d, valid_laps
                ),
            }

            # ── Sector analysis (S1/S2/S3) ───────────────────────────────────
            sector_rows = [o.get('Sectors', []) for o in valid_lap_objs]
            if (sector_rows and all(
                    len(s) == 3 and all(isinstance(v, (int, float)) and v > 0 for v in s)
                    for s in sector_rows)):
                sector_analysis = []
                for idx in range(3):
                    times = [row[idx] for row in sector_rows]
                    sector_analysis.append({
                        'best_ms': min(times),
                        'avg_ms':  round(sum(times) / len(times)),
                        'std_ms':  round(statistics.stdev(times)) if len(times) >= 2 else 0,
                    })
                # Weakest sector = highest (avg − best) delta → most room to improve
                worst_idx = max(range(3), key=lambda i:
                    sector_analysis[i]['avg_ms'] - sector_analysis[i]['best_ms'])
                lap_analysis['sector_analysis'] = sector_analysis
                lap_analysis['weakest_sector']  = worst_idx + 1  # 1-indexed

            # ── Track cuts ───────────────────────────────────────────────────
            total_cuts = sum(int(o.get('Cuts', 0)) for o in valid_lap_objs)
            if total_cuts:
                lap_analysis['total_cuts'] = total_cuts

            # ── Tyre compound ────────────────────────────────────────────────
            tyres = [o.get('Tyre', '') for o in player_lap_objs if o.get('Tyre')]
            if tyres:
                lap_analysis['tyre'] = max(set(tyres), key=tyres.count)

            # ── Gap to leader ────────────────────────────────────────────────
            if player_position and player_position > 1 and results:
                p1_time = results[0].get('TotalTime', 0)
                pl_time = player_result.get('TotalTime', 0)
                gap_ms  = pl_time - p1_time
                if gap_ms > 0:
                    lap_analysis['gap_to_leader_ms'] = gap_ms

    margin_to_p2_ms = None
    if player_position == 1 and len(results) > 1:
        p1_time = player_result.get('TotalTime', 0)
        p2_time = results[1].get('TotalTime', 0)
        try:
            gap_ms = int(p2_time) - int(p1_time)
            if gap_ms > 0:
                margin_to_p2_ms = gap_ms
        except (TypeError, ValueError):
            margin_to_p2_ms = None

    return jsonify({
        'status':         'incomplete' if incomplete else 'found',
        'position':       player_position,
        'best_lap':       best_lap_fmt,
        'laps_completed': laps_completed,
        'expected_laps':  expected_laps,
        'driver_name':    driver_name,
        'margin_to_p2_ms': margin_to_p2_ms,
        'lap_analysis':   lap_analysis,
    })


@app.route('/api/finish-race', methods=['POST'])
def finish_race():
    data, err = _require_json_object()
    if err:
        return err
    career_data = load_career_data()
    try:
        position = int(data.get('position', 1))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid position'}), 400
    if position < 1:
        return jsonify({'status': 'error', 'message': 'Position must be >= 1'}), 400
    pts_table   = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    pts         = pts_table[min(position - 1, 9)] if position <= 10 else 0
    margin_ms   = _parse_optional_int(data.get('margin_ms'))
    result = {
        'race_num': career_data['races_completed'] + 1,
        'position': position,
        'points':   pts,
        'lap_time': data.get('lap_time', ''),
    }
    career_data['races_completed'] += 1
    career_data['points']          += pts
    career_data['race_results'].append(result)

    cs = career_data.setdefault('career_settings', {})
    cur_ai_offset = _parse_optional_int(cs.get('ai_offset')) or 0
    ai_delta = _recommended_ai_delta(position, margin_ms=margin_ms)
    if ai_delta:
        cs['ai_offset'] = max(-20, min(20, cur_ai_offset + ai_delta))

    evolve_driver_progress_for_race(career_data, result['race_num'],
                                    weather=career_data.get('last_race_weather'))

    # Update form scores (season momentum) based on current standings
    tier_index = career_data.get('tier', 0)
    tier_key   = career.tiers[tier_index]
    tier_info  = career.get_tier_info(tier_index)
    standings  = career.generate_standings(tier_info, career_data, tier_key=tier_key)
    update_form_scores(career_data, standings)

    # Update driver rivalries
    update_rivalries(career_data, standings, tier_key)
    # Announce rivalries that just reached intensity 3 (dedup prevents repeats)
    for rival in (career_data.get('rivalries', {}).get(tier_key) or []):
        if rival.get('intensity') == 3:
            d1, d2 = rival['drivers']
            seed = f"rivalry|{d1}|{d2}|{career_data.get('season',1)}"
            text = _pick_template(_RIVALRY_TEMPLATES, seed).format(d1=d1, d2=d2)
            _add_news(career_data, 'rivalry', text, 'swords', tier=tier_key)

    # Player rivalry callout — if any AI driver is within 10 pts, announce once per season
    player_pts = career_data.get('points', 0)
    _tier_label_short = career.tier_names.get(tier_key, tier_key)
    for s in standings:
        if s.get('is_player'):
            continue
        gap = abs(player_pts - s.get('points', 0))
        if 0 < gap <= 10:
            seed = f"player_rivalry|{s['driver']}|{career_data.get('season',1)}"
            text = _pick_template(_PLAYER_RIVALRY_TEMPLATES, seed).format(
                name=s['driver'], gap=gap, tier=_tier_label_short)
            _add_news(career_data, 'player_rivalry', text, 'swords', tier=tier_key)
            break  # one callout per race

    # Form streak news — only announce once per driver per season (dedup handles it)
    for fname, fscore in (career_data.get('form_scores') or {}).items():
        if fscore >= 0.7:
            seed = f"form_hot|{fname}|{career_data.get('season',1)}"
            text = _pick_template(_FORM_HOT_TEMPLATES, seed).format(name=fname)
            _add_news(career_data, 'form_streak', text, 'form_hot', tier=tier_key)
        elif fscore <= -0.7:
            seed = f"form_cold|{fname}|{career_data.get('season',1)}"
            text = _pick_template(_FORM_COLD_TEMPLATES, seed).format(name=fname)
            _add_news(career_data, 'form_streak', text, 'form_cold', tier=tier_key)

    # Mid-season driver swaps (at midpoint)
    races_done = career_data['races_completed']
    total_races = career.get_tier_races(career_data)
    if races_done == total_races // 2:
        new_swaps = career.check_mid_season_swaps(career_data, tier_info, tier_key)
        for swap in new_swaps:
            seed = f"swap|{swap['dropped']}|{swap['replacement']}"
            text = _pick_template(_SWAP_TEMPLATES, seed).format(**swap)
            _add_news(career_data, 'swap', text, 'clipboard', tier=tier_key)

    # ── Player milestone news ─────────────────────────────────────────────
    player_name = career_data.get('driver_name', 'Player')
    player_results = career_data.get('race_results', [])
    total_player_races = len(player_results)
    player_wins = sum(1 for r in player_results if r.get('position') == 1)
    player_podiums = sum(1 for r in player_results if r.get('position', 99) <= 3)
    tier_label_here = career.tier_names.get(tier_key, tier_key)

    # First career win
    if position == 1 and player_wins == 1:
        seed = f"milestone|first_win|{player_name}"
        text = _pick_template(_MILESTONE_TEMPLATES['first_win'], seed).format(name=player_name)
        _add_news(career_data, 'milestone', text, 'trophy')
    # First career podium
    elif position <= 3 and player_podiums == 1:
        seed = f"milestone|first_podium|{player_name}"
        text = _pick_template(_MILESTONE_TEMPLATES['first_podium'], seed).format(
            name=player_name, pos=position)
        _add_news(career_data, 'milestone', text, 'trophy')
    # First win in current tier
    tier_wins = sum(1 for r in player_results if r.get('position') == 1)
    prev_season_wins = sum(1 for ph in career_data.get('player_history', [])
                           if ph.get('tier') == tier_key for _ in range(ph.get('wins', 0)))
    if position == 1 and tier_wins == 1 and prev_season_wins == 0:
        seed = f"milestone|tier_first_win|{player_name}|{tier_key}"
        text = _pick_template(_MILESTONE_TEMPLATES['tier_first_win'], seed).format(
            name=player_name, tier=tier_label_here)
        _add_news(career_data, 'milestone', text, 'trophy')
    # Race count milestones (cumulative across all seasons)
    total_career_races = total_player_races + sum(
        ph.get('races', 0) for ph in career_data.get('player_history', []))
    for milestone_key, milestone_num in [('race_10', 10), ('race_25', 25),
                                          ('race_50', 50), ('race_100', 100)]:
        if total_career_races == milestone_num:
            text = _MILESTONE_TEMPLATES[milestone_key][0].format(name=player_name)
            _add_news(career_data, 'milestone', text, 'flag')

    # ── Wet specialist shoutout ───────────────────────────────────────────
    weather = career_data.get('last_race_weather')
    is_wet = weather and weather.lower().replace(' ', '_') in {
        'rainy', 'heavy_rain', 'wet', 'light_rain', 'drizzle', 'stormy', 'overcast_wet'}
    if is_wet and position <= 3:
        seed = f"wet_spec|{player_name}|{career_data.get('season',1)}|{races_done}"
        text = _pick_template(_WET_SPECIALIST_TEMPLATES, seed).format(name=player_name)
        _add_news(career_data, 'wet_specialist', text, 'rain', tier=tier_key)

    # ── Achievement checks (race-based) ──────────────────────────────────
    newly_unlocked = check_achievements(career_data, {'is_wet': bool(is_wet), 'position': position})
    for aid in newly_unlocked:
        ach = ACHIEVEMENTS.get(aid, {})
        _add_news(career_data, 'achievement',
                  f"Achievement unlocked: {ach.get('name', aid)}! — {ach.get('desc', '')}",
                  'trophy')

    # ── Close title fight ─────────────────────────────────────────────────
    if races_done >= 3 and len(standings) >= 3:
        top3 = sorted(standings, key=lambda s: s.get('points', 0), reverse=True)[:3]
        gap = top3[0]['points'] - top3[2]['points']
        if 0 < gap <= 15:
            seed = f"title_fight|{tier_key}|{career_data.get('season',1)}"
            text = _pick_template(_TITLE_FIGHT_TEMPLATES, seed).format(
                tier=tier_label_here, gap=gap)
            _add_news(career_data, 'title_fight', text, 'swords', tier=tier_key)

    # ── Championship decided early ────────────────────────────────────────
    remaining = total_races - races_done
    if remaining > 0 and len(standings) >= 2:
        sorted_st = sorted(standings, key=lambda s: s.get('points', 0), reverse=True)
        leader_pts = sorted_st[0]['points']
        second_pts = sorted_st[1]['points']
        max_possible = remaining * 25  # max points from remaining races
        if leader_pts - second_pts > max_possible:
            seed = f"title_decided|{tier_key}|{career_data.get('season',1)}"
            text = _pick_template(_TITLE_DECIDED_TEMPLATES, seed).format(
                tier=tier_label_here, name=sorted_st[0]['driver'], remaining=remaining)
            _add_news(career_data, 'title_decided', text, 'trophy', tier=tier_key)

    # ── Teammate battles ──────────────────────────────────────────────────
    if races_done >= 3:
        dpt = career.DRIVERS_PER_TEAM.get(tier_key, 1)
        if dpt >= 2:
            teams_seen = {}
            for s in standings:
                tn = s.get('team', '')
                teams_seen.setdefault(tn, []).append(s)
            for tn, drivers in teams_seen.items():
                if len(drivers) < 2:
                    continue
                drivers_sorted = sorted(drivers, key=lambda d: d.get('points', 0), reverse=True)
                d1, d2 = drivers_sorted[0], drivers_sorted[1]
                gap = d1['points'] - d2['points']
                if 0 < gap <= 8 and not d1.get('is_player') and not d2.get('is_player'):
                    seed = f"teammate|{tn}|{career_data.get('season',1)}"
                    text = _pick_template(_TEAMMATE_BATTLE_TEMPLATES, seed).format(
                        team=tn, d1=d1['driver'], d2=d2['driver'], gap=gap)
                    _add_news(career_data, 'teammate_battle', text, 'swords', tier=tier_key)

    # ── Biggest mover (standings position change detection) ───────────────
    if races_done >= 2:
        prev_standings = career_data.get('_prev_standings_order', {}).get(tier_key, [])
        curr_order = [s['driver'] for s in sorted(
            standings, key=lambda s: s.get('points', 0), reverse=True)]
        if prev_standings:
            prev_pos = {name: i for i, name in enumerate(prev_standings)}
            best_gain = 0
            best_mover = None
            for curr_i, name in enumerate(curr_order):
                if name in prev_pos:
                    gain = prev_pos[name] - curr_i  # positive = moved up
                    if gain > best_gain:
                        best_gain = gain
                        best_mover = name
            if best_mover and best_gain >= 3:
                seed = f"mover|{best_mover}|{career_data.get('season',1)}|{races_done}"
                text = _pick_template(_BIGGEST_MOVER_TEMPLATES, seed).format(
                    name=best_mover, gain=best_gain, tier=tier_label_here)
                _add_news(career_data, 'biggest_mover', text, 'chart_up', tier=tier_key)
        # Store current order for next race comparison
        career_data.setdefault('_prev_standings_order', {})[tier_key] = curr_order

    # ── Comeback story (form swing) ───────────────────────────────────────
    for fname, fscore in (career_data.get('form_scores') or {}).items():
        progress = career_data.get('driver_progress', {}).get(fname, {})
        prev_form = progress.get('_prev_form', 0)
        # Detect swing from cold to hot (at least 1.0 swing)
        if prev_form <= -0.3 and fscore >= 0.4:
            seed = f"comeback|{fname}|{career_data.get('season',1)}"
            text = _pick_template(_COMEBACK_TEMPLATES, seed).format(name=fname)
            _add_news(career_data, 'comeback', text, 'chart_up', tier=tier_key)
        progress['_prev_form'] = fscore

    # Cross-tier championship leader updates (every 3 races, keeps feed interesting)
    if career_data['races_completed'] % 3 == 0:
        tier_labels = {'mx5_cup': 'MX5 Cup', 'gt4': 'GT4', 'gt3': 'GT3', 'wec': 'WEC'}
        all_st, _ = career.generate_all_standings(career_data)
        for tk, st_data in all_st.items():
            if tk == tier_key:
                continue  # skip player's own tier
            drivers = st_data.get('drivers', [])
            if drivers:
                leader = drivers[0]
                tl = tier_labels.get(tk, tk)
                _add_news(career_data, 'standings_update',
                          f"{tl} standings leader: {leader['driver']} ({leader['points']} pts)",
                          'standings', tier=tk)

    # ── Cross-tier race results (podium news for other tiers) ────────
    _tier_labels = {'mx5_cup': 'MX5 Cup', 'gt4': 'GT4', 'gt3': 'GT3', 'wec': 'WEC'}
    prev_ai = career_data.get('_prev_ai_races', {})
    season = career_data.get('season', 1)
    for idx, tk in enumerate(career.tiers):
        if idx == career_data['tier']:
            continue
        ai_done, ai_total = career.get_ai_tier_races(tk, career_data)
        prev_done = prev_ai.get(tk, ai_done - 1)  # first call: assume only latest race is new
        # Generate results for each newly completed race
        for rn in range(max(0, prev_done), ai_done):
            grid_data = career.get_ai_race_grid(tk, rn, season, career_data)
            if not grid_data or len(grid_data['grid']) < 3:
                continue
            tl    = _tier_labels.get(tk, tk)
            track = _fmt_track(grid_data['track'])
            p1    = grid_data['grid'][0]['driver']
            p2    = grid_data['grid'][1]['driver']
            p3    = grid_data['grid'][2]['driver']
            rd    = grid_data['race_num']
            _add_news(career_data, 'race_result',
                      f"{tl} Rd {rd} at {track}: {p1} wins, {p2} P2, {p3} P3",
                      'flag', tier=tk)
        prev_ai[tk] = ai_done
    career_data['_prev_ai_races'] = prev_ai

    save_career_data(career_data)
    if career_data['races_completed'] >= career.get_tier_races(career_data):
        return _do_end_season()
    return jsonify({
        'status': 'success',
        'result': result,
        'total_points': career_data['points'],
        'ai_change': ai_delta,
        'ai_offset': cs.get('ai_offset', 0),
    })


@app.route('/api/end-season', methods=['POST'])
def end_season():
    return _do_end_season()


def _do_end_season():
    career_data = load_career_data()
    cfg         = load_config()
    tier_index  = career_data['tier']
    tier_key    = career.tiers[tier_index]
    tier_info   = career.get_tier_info(tier_index)
    standings   = career.generate_standings(tier_info, career_data, tier_key=tier_key)
    team_count  = len(tier_info['teams'])
    position    = next((s['position'] for s in standings if s['is_player']), team_count)

    # Snapshot AI driver final positions into career history
    driver_history = career_data.get('driver_history', {})
    season         = career_data.get('season', 1)
    for entry in standings:
        if entry['is_player']:
            continue
        name = entry['driver']
        if name not in driver_history:
            driver_history[name] = {'seasons': []}
        driver_history[name]['seasons'].append({
            'season': season,
            'tier':   tier_key,
            'pos':    entry['position'],
            'pts':    entry['points'],
        })
    career_data['driver_history'] = driver_history

    # Snapshot player season stats into player_history
    player_history = career_data.setdefault('player_history', [])
    wins = sum(1 for r in career_data.get('race_results', []) if r.get('position') == 1)
    player_history.append({
        'season': season,
        'tier':   tier_key,
        'pos':    position,
        'pts':    career_data['points'],
        'races':  career_data['races_completed'],
        'wins':   wins,
    })

    # Achievement checks (season-end — player_history already updated above)
    season_unlocked = check_achievements(career_data, {'is_season_end': True})
    for aid in season_unlocked:
        ach = ACHIEVEMENTS.get(aid, {})
        _add_news(career_data, 'achievement',
                  f"Achievement unlocked: {ach.get('name', aid)}! — {ach.get('desc', '')}",
                  'trophy')

    # Evolve team development ratings based on team standings
    team_standings = career.generate_team_standings_from_drivers(standings)
    team_dev = career_data.setdefault('team_development', {})
    ts_count = len(team_standings)
    top_25 = max(1, ts_count // 4)
    for rank, ts_entry in enumerate(team_standings):
        tn = ts_entry.get('team', '')
        if not tn:
            continue
        td = team_dev.setdefault(tn, {'rating_offset': 0.0})
        # Determine tier type for volatility multiplier
        team_tier = next((t.get('tier', 'customer') for t in tier_info['teams']
                          if t['name'] == tn), 'customer')
        volatility = 0.5 if team_tier == 'factory' else (1.5 if team_tier == 'customer' else 1.0)
        if rank < top_25:
            td['rating_offset'] = min(0.5, td['rating_offset'] + 0.1 * volatility)
        elif rank >= ts_count - top_25:
            td['rating_offset'] = max(-0.5, td['rating_offset'] - 0.1 * volatility)
        td['rating_offset'] = round(td['rating_offset'], 2)

    # Process driver retirements (age 38+)
    newly_retired = process_retirements(career_data, season)
    for ret in newly_retired:
        nick = ret.get('nickname')
        seed = f"retire|{ret['name']}|{season}"
        if nick:
            text = _pick_template(_RETIREMENT_NICK_TEMPLATES, seed).format(
                name=ret['name'], age=ret['age'], nick=nick)
        else:
            text = _pick_template(_RETIREMENT_TEMPLATES, seed).format(
                name=ret['name'], age=ret['age'])
        _add_news(career_data, 'retirement', text, 'flag')

    # Championship winner news + team history snapshot (single standings call)
    tier_labels = {'mx5_cup': 'MX5 Cup', 'gt4': 'GT4', 'gt3': 'GT3', 'wec': 'WEC'}
    all_standings, _ = career.generate_all_standings(career_data)
    team_history = career_data.get('team_history', {})
    for tk, st_data in all_standings.items():
        tl = tier_labels.get(tk, tk)
        drivers = st_data.get('drivers', [])
        if drivers:
            champ = drivers[0]
            seed = f"champ|{tk}|{season}"
            text = _pick_template(_CHAMPION_TEMPLATES, seed).format(
                tier=tl, name=champ['driver'])
            _add_news(career_data, 'champion', text, 'trophy', tier=tk)
        for te in st_data.get('teams', []):
            tname = te.get('team')
            if not tname:
                continue
            if tname not in team_history:
                team_history[tname] = {'seasons': []}
            team_history[tname]['seasons'].append({
                'season':    season,
                'tier':      tk,
                'tier_name': tl,
                'pos':       te.get('position', 0),
                'pts':       te.get('points', 0),
            })
    career_data['team_history'] = team_history

    # Team development news
    tier_label = {'mx5_cup': 'MX5', 'gt4': 'GT4', 'gt3': 'GT3', 'wec': 'WEC'}.get(tier_key, tier_key.upper())
    for rank, ts_entry in enumerate(team_standings):
        tn = ts_entry.get('team', '')
        td = team_dev.get(tn, {})
        ro = td.get('rating_offset', 0)
        if ro >= 0.2:
            text = _pick_template(_TEAM_UP_TEMPLATES, f"tdev|{tn}|{season}").format(team=tn, tier=tier_label)
            _add_news(career_data, 'team_dev', text, 'chart_up', tier=tier_key)
        elif ro <= -0.2:
            text = _pick_template(_TEAM_DOWN_TEMPLATES, f"tdev|{tn}|{season}").format(team=tn, tier=tier_label)
            _add_news(career_data, 'team_dev', text, 'chart_down', tier=tier_key)

    # ── Veteran warnings (drivers age 38+ entering next season, max 3) ───
    progress = career_data.get('driver_progress', {})
    veteran_count = 0
    for dname, entry in progress.items():
        if dname in set(career_data.get('retired_drivers', [])):
            continue
        age = int(entry.get('age', 25))
        if age >= 38:
            seed = f"veteran|{dname}|{season + 1}"
            text = _pick_template(_VETERAN_TEMPLATES, seed).format(name=dname, age=age)
            _add_news(career_data, 'veteran', text, 'flag')
            veteran_count += 1
            if veteran_count >= 3:
                break

    # ── Rookie announcements (new names replacing retirees) ──────────────
    # When drivers retire, the roster shifts — new names enter the grid.
    # We announce up to len(newly_retired) rookies based on the youngest
    # non-retired drivers who haven't appeared in driver_history yet.
    if newly_retired:
        driver_history = career_data.get('driver_history', {})
        retired_set = set(career_data.get('retired_drivers', []))
        rookie_candidates = []
        for dname, entry in progress.items():
            if dname in retired_set or dname in driver_history:
                continue
            age = int(entry.get('age', 25))
            rookie_candidates.append((age, dname))
        rookie_candidates.sort()  # youngest first
        for _, dname in rookie_candidates[:len(newly_retired)]:
            seed = f"rookie|{dname}|{season}"
            text = _pick_template(_ROOKIE_TEMPLATES, seed).format(name=dname)
            _add_news(career_data, 'rookie', text, 'flag')

    # Career complete: top tier + not in degradation risk → no next tier
    degradation_risk = position >= team_count - 2
    at_top_tier      = tier_index >= len(career.tiers) - 1
    if at_top_tier and not degradation_risk:
        contracts = [{'message': 'Congratulations! Career complete!', 'complete': True}]
    else:
        contracts = career.generate_contract_offers(
            position, tier_index + 1, cfg,
            current_tier=tier_index,
            team_count=team_count,
        )
    career_data['contracts']      = contracts
    career_data['final_position'] = position
    save_career_data(career_data)

    # Build season recap (consumed by frontend recap screen before contracts)
    race_results = career_data.get('race_results', [])
    podiums = sum(1 for r in race_results if r.get('position', 99) <= 3)
    recap = {
        'player': {
            'wins':        wins,
            'podiums':     podiums,
            'best_result': min((r.get('position', 99) for r in race_results), default=None),
            'races':       career_data['races_completed'],
            'points':      career_data['points'],
            'position':    position,
            'tier':        tier_key,
        },
        'tier_champions': {
            tk: st.get('drivers', [{}])[0].get('driver')
            for tk, st in all_standings.items() if st.get('drivers')
        },
        'most_improved':  _find_most_improved(career_data),
        'boss_message':   _team_boss_message(position, wins, podiums, team_count, tier_key, season),
    }
    career_data['last_recap'] = recap
    save_career_data(career_data)

    return jsonify({
        'status':       'season_complete',
        'position':     position,
        'total_points': career_data['points'],
        'contracts':    contracts,
        'recap':        recap,
    })


@app.route('/api/season-recap')
def season_recap():
    career_data = load_career_data()
    recap = career_data.get('last_recap')
    if not recap:
        return jsonify({'error': 'no recap'}), 404
    return jsonify({
        'recap':        recap,
        'position':     career_data.get('final_position', 0),
        'total_points': career_data.get('points', 0),
    })


@app.route('/api/accept-contract', methods=['POST'])
def accept_contract():
    data, err = _require_json_object()
    if err:
        return err
    career_data = load_career_data()
    contract_id = data.get('contract_id')
    contracts = career_data.get('contracts') or []
    selected    = next((c for c in contracts if c.get('id') == contract_id), None)
    if not selected:
        return jsonify({'status': 'error', 'message': 'Contract not found'}), 400

    # Use target_tier from the contract — supports promotion, stay, AND relegation.
    # Fall back to tier+1 for contracts created before v1.8.0 (backwards compat).
    new_tier = selected.get('target_tier')
    if new_tier is None:
        new_tier = career_data['tier'] + 1
    new_tier = max(0, min(len(career.tiers) - 1, new_tier))  # clamp to valid range

    move = selected.get('move', 'promotion')

    career_data['tier']            = new_tier
    career_data['season']          += 1
    career_data['team']             = selected['team_name']
    career_data['car']              = selected['car']
    career_data['races_completed']  = 0
    career_data['points']           = 0
    career_data['race_results']     = []
    career_data['contracts']        = None
    career_data['standings']        = []
    career_data['final_position']   = None
    # Preserve career_settings (difficulty, weather, custom tracks) across seasons
    # career_settings is intentionally NOT reset here

    # Clear mid-season swap overrides and AI race tracking for the new season
    career_data['driver_swaps'] = {}
    career_data['_prev_ai_races'] = {}

    # Player move news (promotion/relegation/stay)
    new_tier_key = career.tiers[new_tier]
    new_tier_label = career.tier_names.get(new_tier_key, new_tier_key)
    player_name = career_data.get('driver_name', 'Player')
    move_templates = _MOVE_TEMPLATES.get(move, _MOVE_TEMPLATES['stay'])
    move_seed = f"move|{player_name}|{career_data['season']}"
    move_text = _pick_template(move_templates, move_seed).format(
        name=player_name, tier=new_tier_label)
    _add_news(career_data, 'player_move', move_text, 'clipboard')

    # New season announcement
    _add_news(career_data, 'new_season',
              f"Season {career_data['season']} begins!",
              'flag')

    # Pick new rival for the new tier/season
    advance_driver_progress_season(career_data)
    career_data['rival_name'] = career.pick_rival(new_tier_key, career_data.get('season', 1), career_data=career_data)

    save_career_data(career_data)

    move_labels = {
        'promotion': 'Promoted to',
        'stay':      'Staying in',
        'relegation': 'Relegated to',
    }
    tier_label = career.tier_names.get(career.tiers[new_tier], '')
    msg = f"{move_labels.get(move, 'Welcome to')} {tier_label}: {selected['team_name']}!"

    return jsonify({
        'status':   'success',
        'message':  msg,
        'move':     move,
        'new_tier': new_tier,
        'new_team': career_data['team'],
        'new_car':  career_data['car'],
    })


@app.route('/api/new-career', methods=['POST'])
def new_career():
    data          = request.json or {}
    driver_name   = data.get('driver_name', '').strip() or 'Driver'
    nationality   = data.get('nationality', '').strip().upper()
    difficulty    = data.get('difficulty', 'pro')
    weather_mode  = data.get('weather_mode', 'realistic')
    name_mode     = str(data.get('name_mode', 'curated')).strip().lower()
    if name_mode not in {'curated', 'procedural'}:
        name_mode = 'curated'
    custom_tracks = data.get('custom_tracks') or None   # None → use config defaults

    ai_offsets = {'rookie': -10, 'amateur': -5, 'pro': 0, 'legend': 5}
    ai_offset  = ai_offsets.get(difficulty, 0)

    initial = {
        'tier':            0,
        'season':          1,
        'team':            'Mazda Academy',
        'car':             'ks_mazda_mx5_cup',
        'driver_name':     driver_name,
        'player_nationality': nationality,
        'races_completed': 0,
        'points':          0,
        'standings':       [],
        'race_results':    [],
        'contracts':       None,
        'driver_history':  {},
        'team_history':    {},
        'player_history':  [],
        'form_scores':     {},
        'team_development': {},
        'rival_name':      career.pick_rival('mx5_cup', 1),
        'driver_seed':     random.randint(0, 2**31 - 1),
        'career_settings': {
            'difficulty':    difficulty,
            'ai_offset':     ai_offset,
            'weather_mode':  weather_mode,
            'name_mode':     name_mode,
            'custom_tracks': custom_tracks,
        },
    }
    ensure_driver_progress(initial)
    initial['rival_name'] = career.pick_rival('mx5_cup', 1, career_data=initial)
    save_career_data(initial)
    return jsonify({'status': 'success', 'message': 'New career started!', 'career_data': initial})


@app.route('/api/scan-content')
def scan_content():
    """Scan AC content/cars and content/tracks for valid GT3/GT4 cars and all tracks."""
    cfg     = load_config()
    ac_path = cfg.get('paths', {}).get('ac_install', '')

    if not os.path.exists(os.path.join(ac_path, 'acs.exe')):
        return jsonify({'error': 'AC installation not found. Check your AC path.'}), 400

    result = {'cars': {'gt4': [], 'gt3': []}, 'tracks': []}

    # ── Cars ────────────────────────────────────────────────────────────────
    cars_dir = os.path.join(ac_path, 'content', 'cars')
    if os.path.isdir(cars_dir):
        for car_name in sorted(os.listdir(cars_dir)):
            car_path  = os.path.join(cars_dir, car_name)
            if not os.path.isdir(car_path):
                continue
            ui_car   = os.path.join(car_path, 'ui', 'ui_car.json')
            data_dir = os.path.join(car_path, 'data')
            if not os.path.exists(ui_car) or not os.path.isdir(data_dir):
                continue
            try:
                with open(ui_car, 'r', encoding='utf-8', errors='ignore') as f:
                    car_data = json.load(f)
            except Exception:
                continue
            display  = car_data.get('name', car_name)
            tags     = [t.lower() for t in (car_data.get('tags') or [])]
            nm_lower = car_name.lower()
            if 'gt4' in tags or 'gt4' in nm_lower:
                result['cars']['gt4'].append({'id': car_name, 'name': display})
            elif 'gt3' in tags or 'gt3' in nm_lower:
                result['cars']['gt3'].append({'id': car_name, 'name': display})

    # ── Tracks ──────────────────────────────────────────────────────────────
    tracks_dir = os.path.join(ac_path, 'content', 'tracks')
    if os.path.isdir(tracks_dir):
        for track_name in sorted(os.listdir(tracks_dir)):
            track_path = os.path.join(tracks_dir, track_name)
            if not os.path.isdir(track_path):
                continue
            layouts = []
            try:
                for item in sorted(os.listdir(track_path)):
                    item_path = os.path.join(track_path, item)
                    if not os.path.isdir(item_path) or item == 'ui':
                        continue
                    layout_ui = os.path.join(item_path, 'ui', 'ui_track.json')
                    if not os.path.exists(layout_ui):
                        continue
                    try:
                        with open(layout_ui, 'r', encoding='utf-8', errors='ignore') as f:
                            td = json.load(f)
                        layouts.append({
                            'id':     f'{track_name}/{item}',
                            'name':   td.get('name') or f'{track_name} – {item}',
                            'length': _parse_length(td.get('length', 0)),
                        })
                    except Exception:
                        continue
            except PermissionError:
                continue
            # Single-layout track (no layout subdirs found)
            if not layouts:
                root_ui = os.path.join(track_path, 'ui', 'ui_track.json')
                if os.path.exists(root_ui):
                    try:
                        with open(root_ui, 'r', encoding='utf-8', errors='ignore') as f:
                            td = json.load(f)
                        layouts.append({
                            'id':     track_name,
                            'name':   td.get('name') or track_name,
                            'length': _parse_length(td.get('length', 0)),
                        })
                    except Exception:
                        pass
            result['tracks'].extend(layouts)

    result['tracks'].sort(key=lambda t: t['length'])
    return jsonify(result)


@app.route('/api/driver-profile')
def driver_profile():
    name        = request.args.get('name', '')
    career_data = load_career_data()
    changed = ensure_driver_progress(career_data)

    profile = career.get_driver_profile(name, career_data=career_data)
    progress = (career_data.get('driver_progress') or {}).get(name, {})
    profile['age'] = progress.get('age')
    profile['potential'] = progress.get('potential')
    profile['skill_deltas'] = compute_progress_deltas(progress) if progress else {
        'race': {k: 0.0 for k in DRIVER_SKILL_KEYS},
        'season': {k: 0.0 for k in DRIVER_SKILL_KEYS},
        'career': {k: 0.0 for k in DRIVER_SKILL_KEYS},
    }
    profile['trend_label'] = driver_trend_label(progress) if progress else 'Stable'

    history     = career_data.get('driver_history', {}).get(name, {'seasons': []})
    # Find current standings entry for this driver across all tiers
    all_s, _      = career.generate_all_standings(career_data)
    current_entry = None
    for tier_data in all_s.values():
        for entry in tier_data['drivers']:
            if entry.get('driver') == name:
                current_entry = entry
                break
        if current_entry:
            break

    if changed:
        save_career_data(career_data)

    return jsonify({'name': name, 'profile': profile, 'current': current_entry, 'history': history})

def _synthetic_team_history(team_name, career_data):
    """Generate plausible pre-career season history seeded by team name."""
    # Find team's tier_level (factory/semi/customer) by searching all tiers
    tier_level = 'customer'
    tier_name_map = {}
    for tk in career.tiers:
        ti = career.get_tier_info(career.tiers.index(tk))
        tl = ti.get('name', tk)
        tier_name_map[tk] = tl
        for t in ti.get('teams', []):
            if t.get('name') == team_name:
                tier_level = t.get('tier', 'customer')
                break

    # Position ranges by tier_level (min, max)
    pos_range = {'factory': (1, 5), 'semi': (3, 10), 'customer': (6, 16)}
    lo, hi = pos_range.get(tier_level, (4, 12))

    seasons = []
    current_season = career_data.get('season', 1)
    num_pre = min(3, current_season - 1)
    if num_pre <= 0:
        return seasons

    # Use current tier of team to pick tier label
    player_tier_key = career.tiers[career_data.get('tier', 0)]
    tier_label = tier_name_map.get(player_tier_key, player_tier_key)

    for i in range(num_pre, 0, -1):
        s_num = current_season - i
        seed_val = _seed_int(f"teamhist|{team_name}|{s_num}", lo, hi)
        pos = seed_val
        # Points roughly inverse to position
        pts_seed = _seed_int(f"teampts|{team_name}|{s_num}", 0, 100)
        pts = max(0, int(250 * (1 - (pos - 1) / max(hi, 1))) + pts_seed // 5 - 10)
        seasons.append({
            'season':    s_num,
            'tier':      player_tier_key,
            'tier_name': tier_label,
            'pos':       pos,
            'pts':       pts,
            'synthetic': True,
        })
    return seasons


@app.route('/api/team-profile')
def team_profile():
    name        = request.args.get('name', '')
    career_data = load_career_data()
    recorded    = career_data.get('team_history', {}).get(name, {}).get('seasons', [])

    # Synthetic pre-career seasons for seasons not yet recorded
    recorded_season_nums = {s['season'] for s in recorded}
    synthetic = [s for s in _synthetic_team_history(name, career_data)
                 if s['season'] not in recorded_season_nums]

    seasons = sorted(synthetic + recorded, key=lambda s: s['season'])
    best = min((s['pos'] for s in seasons), default=None)
    wins = sum(1 for s in seasons if s.get('pos') == 1)
    return jsonify({'name': name, 'history': {'seasons': seasons}, 'best_result': best, 'titles': wins})


@app.route('/api/paddock-news')
def paddock_news():
    career_data = load_career_data()
    news = career_data.get('paddock_news', [])
    # One-time backfill: generate news from existing race results if empty
    if not news and career_data.get('race_results'):
        tier_key = career.tiers[career_data.get('tier', 0)]
        _tier_labels = {'mx5_cup': 'MX5 Cup', 'gt4': 'GT4 SuperCup', 'gt3': 'British GT GT3', 'wec': 'WEC / Elite'}
        tier_label = _tier_labels.get(tier_key, tier_key)
        for r in career_data['race_results']:
            pos = r.get('position', 0)
            track = _fmt_track(r.get('track', ''))
            pts = r.get('points', 0)
            icon = 'trophy' if pos <= 3 else 'flag'
            text = f"{tier_label} Rd {r.get('race',0)} at {track}: You finished P{pos} (+{pts} pts)"
            news.append({'season': career_data.get('season', 1), 'race': r.get('race', 0),
                         'type': 'race_result', 'text': text, 'icon': icon, 'tier': tier_key})
        career_data['paddock_news'] = news
        save_career_data(career_data)
    return jsonify(news)


@app.route('/api/achievements')
def achievements():
    career_data = load_career_data()
    unlocked = career_data.get('achievements', [])
    return jsonify({
        'all':      ACHIEVEMENTS,
        'order':    ACHIEVEMENT_ORDER,
        'unlocked': unlocked,
    })


@app.route('/api/player-profile')
def player_profile():
    career_data = load_career_data()
    results  = career_data.get('race_results', [])
    wins     = sum(1 for r in results if r.get('position') == 1)
    podiums  = sum(1 for r in results if r.get('position', 99) <= 3)
    avg      = round(sum(r['position'] for r in results) / len(results), 1) if results else None
    return jsonify({
        'driver_name':  career_data.get('driver_name', 'Player'),
        'nationality':  career_data.get('player_nationality', ''),
        'team':         career_data.get('team'),
        'car':          career_data.get('car'),
        'season':      career_data.get('season', 1),
        'races':       len(results),
        'wins':        wins,
        'podiums':     podiums,
        'avg_finish':  avg,
        'points':      career_data.get('points', 0),
        'history':     career_data.get('player_history', []),
    })


@app.route('/api/livery-preview')
def livery_preview():
    car   = request.args.get('car', '')
    index = int(request.args.get('index', 0))
    cfg     = load_config()
    ac_path = cfg.get('paths', {}).get('ac_install', '')
    if not car or not ac_path:
        abort(404)
    skins_dir = os.path.join(ac_path, 'content', 'cars', car, 'skins')
    try:
        skins = sorted(os.listdir(skins_dir))
        if not skins:
            abort(404)
        skin = skins[index % len(skins)]
        for fname in ('preview.jpg', 'preview.png'):
            preview = os.path.join(skins_dir, skin, fname)
            if os.path.isfile(preview):
                return send_file(preview)
        abort(404)
    except Exception:
        abort(404)


@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(load_config())


@app.route('/api/config', methods=['POST'])
def update_config():
    new_cfg, err = _require_json_object()
    if err:
        return err
    save_config(new_cfg)
    return jsonify({'status': 'success', 'message': 'Configuration updated'})


@app.route('/api/preflight-check')
def preflight_check():
    """Check if the next race's track and car exist in the AC installation."""
    cfg     = load_config()
    ac_path = cfg.get('paths', {}).get('ac_install', '')
    track   = request.args.get('track', '')
    car     = request.args.get('car', '')
    result  = _check_preflight(ac_path, track, car)
    return jsonify(result)


def detect_csp(ac_path):
    """Return CSP / Pure installation status.
    CSP  detected → <AC>/extension/ folder exists
    Pure detected → <AC>/extension/weather/pure/ folder exists
    """
    ext  = os.path.join(ac_path, 'extension')
    pure = os.path.join(ac_path, 'extension', 'weather', 'pure')
    return {
        'csp':  os.path.isdir(ext),
        'pure': os.path.isdir(pure),
    }


def _check_preflight(ac_path, track, car):
    """Validate that track and car exist in the AC content folder.

    Returns {'ok': bool, 'issues': [{'type': 'error'|'warning', 'msg': str}]}
    """
    issues = []

    if not os.path.exists(os.path.join(ac_path, 'acs.exe')):
        issues.append({
            'type': 'error',
            'msg':  'AC installation not found. Check your AC path in Settings.',
        })
        return {'ok': False, 'issues': issues}

    # Track: strip layout suffix (e.g. "ks_silverstone/gp" → "ks_silverstone")
    track_folder = track.split('/')[0]
    track_path   = os.path.join(ac_path, 'content', 'tracks', track_folder)
    if not os.path.isdir(track_path):
        issues.append({
            'type': 'error',
            'msg':  f'Track not found: {track_folder}. Install this track mod before racing.',
        })

    # Car: needs the car folder + either data/ (mods) or data.acd (Kunos stock cars)
    if car:
        car_path      = os.path.join(ac_path, 'content', 'cars', car)
        car_data_path = os.path.join(car_path, 'data')
        car_data_acd  = os.path.join(car_path, 'data.acd')
        if not os.path.isdir(car_path):
            issues.append({
                'type': 'error',
                'msg':  f'Car not found: {car}. Install this car mod before racing.',
            })
        elif not os.path.isdir(car_data_path) and not os.path.isfile(car_data_acd):
            issues.append({
                'type': 'warning',
                'msg':  f'Car "{car}" may be incomplete (missing data folder).',
            })

    # CSP checks
    csp_status = detect_csp(ac_path)
    cd_check   = load_career_data()
    cs_check   = cd_check.get('career_settings', {})

    if cs_check.get('night_cycle', True) and not csp_status['csp']:
        issues.append({
            'type': 'warning',
            'msg':  'Night cycle is enabled but Custom Shader Patch (CSP) was not found. '
                    'Install CSP via Content Manager for full day/night progression. '
                    'Without CSP the race will start at a fixed sun angle.',
        })

    return {'ok': len(issues) == 0, 'issues': issues}


@app.route('/api/career-settings', methods=['POST'])
def update_career_settings():
    career_data = load_career_data()
    patch, err = _require_json_object()
    if err:
        return err
    cs          = career_data.setdefault('career_settings', {})
    cs.update(patch)
    save_career_data(career_data)
    return jsonify({'status': 'success'})


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Server error', 'detail': str(e)}), 500


# ---------------------------------------------------------------------------
# Entry point — launches pywebview window (works as script and as EXE)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import time
    import ctypes

    # Configure pythonnet to use .NET 8 Desktop Runtime (needed for WinForms/EdgeChromium)
    try:
        import pythonnet
        from clr_loader import get_coreclr
        _rc = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pythonnet.runtimeconfig.json')
        if os.path.exists(_rc):
            pythonnet.set_runtime(get_coreclr(runtime_config=_rc))
    except Exception:
        pass  # fall back to auto-detect (netfx or env var)

    import webview

    class JsApi:
        """Python functions exposed to JavaScript via window.pywebview.api"""
        def browse_folder(self):
            result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
            return result[0] if result else None

    def _set_windows_titlebar_icon(title_text, icon_path):
        """Set titlebar/taskbar icon for pywebview window when running as script on Windows."""
        if sys.platform != 'win32' or not os.path.isfile(icon_path):
            return
        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        hicon = user32.LoadImageW(None, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not hicon:
            return

        deadline = time.time() + 6.0
        hwnd = None
        while time.time() < deadline:
            hwnd = user32.FindWindowW(None, title_text)
            if hwnd:
                break
            time.sleep(0.1)
        if not hwnd:
            return

        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)

    def run_flask():
        app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(0.8)  # let Flask start up

    api    = JsApi()
    window_title = 'AC Career GT Edition'
    window = webview.create_window(
        window_title,
        'http://127.0.0.1:5000',
        width=1440, height=920,
        min_size=(1000, 700),
        js_api=api,
    )
    icon_path = os.path.join(APP_DIR, 'static', 'logo.ico')

    def on_webview_ready():
        _set_windows_titlebar_icon(window_title, icon_path)

    gui_backend = get_webview_gui()   # 'gtk' on Linux, 'edgechromium' on Windows
    try:
        webview.start(func=on_webview_ready, gui=gui_backend)
    except Exception:
        webview.start(func=on_webview_ready)  # last-resort fallback (auto-detect)
