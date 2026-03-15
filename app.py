"""
AC Career Manager - Flask Backend
Main application entry point
"""

from flask import Flask, render_template, jsonify, request, send_file, abort
from flask_cors import CORS
import json
import os
import sys
import statistics
import threading
import hashlib
import random
from datetime import datetime
from urllib.parse import urlsplit

from career_manager import CareerManager
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
    """On first EXE run, copy bundled config template to app dir."""
    if not os.path.exists(CONFIG_PATH):
        if getattr(sys, 'frozen', False):
            bundled = os.path.join(sys._MEIPASS, 'config.json')
        else:
            bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
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


DRIVER_SKILL_KEYS = ['skill', 'aggression', 'wet_skill', 'quali_pace', 'consistency']

def _clamp(value, low, high):
    return max(low, min(high, value))

def _seed_int(seed_text, low, high):
    raw = int(hashlib.md5(seed_text.encode('utf-8')).hexdigest()[:8], 16)
    span = max(1, (high - low + 1))
    return low + (raw % span)

def _compute_progress_deltas(entry):
    current = entry.get('current') or {}
    season_start = entry.get('season_start') or {}
    career_start = entry.get('career_start') or {}
    last_delta = entry.get('last_delta') or {}
    season_delta = {}
    career_delta = {}
    race_delta = {}
    for key in DRIVER_SKILL_KEYS:
        cur = float(current.get(key, 0))
        s0 = float(season_start.get(key, cur))
        c0 = float(career_start.get(key, cur))
        ld = float(last_delta.get(key, 0))
        season_delta[key] = round(cur - s0, 1)
        career_delta[key] = round(cur - c0, 1)
        race_delta[key] = round(ld, 1)
    return {'race': race_delta, 'season': season_delta, 'career': career_delta}

def _driver_trend_label(entry):
    deltas = _compute_progress_deltas(entry).get('season', {})
    net = sum(float(deltas.get(k, 0)) for k in DRIVER_SKILL_KEYS)
    if net >= 1.0:
        return 'Rising'
    if net <= -1.0:
        return 'Declining'
    return 'Stable'

def _ensure_driver_progress(career_data):
    roster = career_data.setdefault('driver_progress', {})
    changed = False
    for name, base in career.DRIVER_PROFILES.items():
        entry = roster.get(name)
        if not isinstance(entry, dict):
            age = _seed_int(f'age|{name}', 19, 37)
            potential = _seed_int(f'pot|{name}', 62, 96)
            current = {k: float(base.get(k, 70)) for k in DRIVER_SKILL_KEYS}
            roster[name] = {
                'age': age,
                'potential': potential,
                'current': current,
                'season_start': dict(current),
                'career_start': dict(current),
                'last_delta': {k: 0.0 for k in DRIVER_SKILL_KEYS},
            }
            changed = True
            continue

        current = entry.setdefault('current', {})
        season_start = entry.setdefault('season_start', {})
        career_start = entry.setdefault('career_start', {})
        entry.setdefault('last_delta', {})
        if 'age' not in entry:
            entry['age'] = _seed_int(f'age|{name}', 19, 37)
            changed = True
        if 'potential' not in entry:
            entry['potential'] = _seed_int(f'pot|{name}', 62, 96)
            changed = True
        for key in DRIVER_SKILL_KEYS:
            base_val = float(base.get(key, 70))
            if key not in current:
                current[key] = base_val
                changed = True
            if key not in season_start:
                season_start[key] = float(current[key])
                changed = True
            if key not in career_start:
                career_start[key] = float(current[key])
                changed = True
            if key not in entry['last_delta']:
                entry['last_delta'][key] = 0.0
                changed = True
    return changed

def _evolve_driver_progress_for_race(career_data, race_num):
    _ensure_driver_progress(career_data)
    season = career_data.get('season', 1)
    tier = career_data.get('tier', 0)
    for name, entry in (career_data.get('driver_progress') or {}).items():
        age = int(entry.get('age', 26))
        potential = int(entry.get('potential', 75))
        current = entry.get('current') or {}
        last_delta = {}

        if age <= 26:
            age_factor = 0.8
        elif age <= 31:
            age_factor = 0.2
        elif age <= 35:
            age_factor = -0.25
        else:
            age_factor = -0.6
        pot_factor = (potential - 75) / 25.0

        for key in DRIVER_SKILL_KEYS:
            noise_raw = _seed_int(f'{name}|{season}|{tier}|{race_num}|{key}', 0, 2000) / 1000.0 - 1.0
            key_mult = 0.9 if key == 'skill' else 0.75
            delta = key_mult * (0.028 * age_factor + 0.033 * pot_factor + 0.055 * noise_raw)
            delta = _clamp(delta, -0.35, 0.35)
            cur = float(current.get(key, 70))
            cur = _clamp(cur + delta, 40.0, 99.0)
            current[key] = round(cur, 2)
            last_delta[key] = round(delta, 2)
        entry['last_delta'] = last_delta

def _advance_driver_progress_season(career_data):
    _ensure_driver_progress(career_data)
    for _, entry in (career_data.get('driver_progress') or {}).items():
        entry['age'] = int(_clamp(int(entry.get('age', 25)) + 1, 18, 55))
        current = entry.get('current') or {}
        entry['season_start'] = {k: float(current.get(k, 70)) for k in DRIVER_SKILL_KEYS}
        entry['last_delta'] = {k: 0.0 for k in DRIVER_SKILL_KEYS}

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
    all_s = career.generate_all_standings(career_data)
    return jsonify({
        'all_standings':   all_s,
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
    success = career.launch_ac_race(race, cfg, mode=mode, career_data=career_data)
    if success:
        career_data['race_started_at'] = datetime.now().isoformat()
        save_career_data(career_data)
        return jsonify({'status': 'success', 'message': 'AC launched!', 'race': race})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to launch AC'}), 500


@app.route('/api/read-race-result')
def read_race_result():
    """Auto-read the latest AC race result from Documents/Assetto Corsa/results/."""
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

    if not candidates:
        return jsonify({'status': 'not_found', 'message': 'No result file found yet'})

    candidates.sort(key=lambda x: x[0], reverse=True)
    data = None
    results = []
    player_result = None
    player_position = None
    race_seen = False

    # Walk recent files newest -> oldest and pick the first race result
    # that actually contains the active player.
    for _, result_file in candidates:
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

    if player_result is None:
        msg = 'Driver not found in results' if race_seen else 'No race session result found yet'
        return jsonify({'status': 'not_found', 'message': msg})

    laps_completed = player_result.get('Laps', 0)
    total_time     = player_result.get('TotalTime', 0)
    best_lap_ms    = player_result.get('BestLap', 0)

    incomplete = (laps_completed < max(1, expected_laps // 2)) or (total_time == 0 and laps_completed == 0)

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

    _evolve_driver_progress_for_race(career_data, result['race_num'])
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
    position    = next((s['position'] for s in standings if s['is_player']), 1)
    team_count  = len(tier_info['teams'])

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

    contracts   = career.generate_contract_offers(
        position, tier_index + 1, cfg,
        current_tier=tier_index,
        team_count=team_count,
    )
    career_data['contracts']      = contracts
    career_data['final_position'] = position
    save_career_data(career_data)
    return jsonify({
        'status':       'season_complete',
        'position':     position,
        'total_points': career_data['points'],
        'contracts':    contracts,
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

    # Pick new rival for the new tier/season
    new_tier_key              = career.tiers[new_tier]
    _advance_driver_progress_season(career_data)
    career_data['rival_name'] = career.pick_rival(new_tier_key, career_data.get('season', 1), career_data=career_data)

    save_career_data(career_data)

    move_labels = {
        'promotion': 'Promoted to',
        'stay':      'Staying in',
        'relegation': 'Relegated to',
    }
    tier_label = career.tier_names.get(career.tiers[new_tier], '')
    msg = f"{move_labels.get(move, 'Welcome to')} {tier_label} — {selected['team_name']}!"

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
        'races_completed': 0,
        'points':          0,
        'standings':       [],
        'race_results':    [],
        'contracts':       None,
        'driver_history':  {},
        'player_history':  [],
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
    _ensure_driver_progress(initial)
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
    changed = _ensure_driver_progress(career_data)

    profile = career.get_driver_profile(name, career_data=career_data)
    progress = (career_data.get('driver_progress') or {}).get(name, {})
    profile['age'] = progress.get('age')
    profile['potential'] = progress.get('potential')
    profile['skill_deltas'] = _compute_progress_deltas(progress) if progress else {
        'race': {k: 0.0 for k in DRIVER_SKILL_KEYS},
        'season': {k: 0.0 for k in DRIVER_SKILL_KEYS},
        'career': {k: 0.0 for k in DRIVER_SKILL_KEYS},
    }
    profile['trend_label'] = _driver_trend_label(progress) if progress else 'Stable'

    history     = career_data.get('driver_history', {}).get(name, {'seasons': []})
    # Find current standings entry for this driver across all tiers
    all_s         = career.generate_all_standings(career_data)
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

@app.route('/api/player-profile')
def player_profile():
    career_data = load_career_data()
    results  = career_data.get('race_results', [])
    wins     = sum(1 for r in results if r.get('position') == 1)
    podiums  = sum(1 for r in results if r.get('position', 99) <= 3)
    avg      = round(sum(r['position'] for r in results) / len(results), 1) if results else None
    return jsonify({
        'driver_name': career_data.get('driver_name', 'Player'),
        'team':        career_data.get('team'),
        'car':         career_data.get('car'),
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
    import webview
    import ctypes

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
