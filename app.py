"""
AC Career Manager - Flask Backend
Main application entry point
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import os
import sys
import threading
from datetime import datetime

from career_manager import CareerManager

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
CORS(app)

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

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def load_career_data():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r') as f:
            return json.load(f)
    return _default_career()


def save_career_data(data):
    with open(DATA_PATH, 'w') as f:
        json.dump(data, f, indent=2)


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
    }


def _fmt_track(track_id):
    return TRACK_NAMES.get(track_id, track_id.replace('_', ' ').title())


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
    cfg     = load_config()
    ac_path = cfg.get('paths', {}).get('ac_install', '')
    valid   = os.path.exists(os.path.join(ac_path, 'acs.exe'))
    return jsonify({'valid': valid, 'path': ac_path})


@app.route('/api/save-ac-path', methods=['POST'])
def save_ac_path():
    data    = request.json
    path    = data.get('path', '').strip()
    if not os.path.exists(os.path.join(path, 'acs.exe')):
        return jsonify({'status': 'error', 'message': 'acs.exe niet gevonden in die map'}), 400
    cfg = load_config()
    cfg['paths']['ac_install'] = path
    cm = os.path.join(path, 'Content Manager.exe')
    if os.path.exists(cm):
        cfg['paths']['content_manager'] = cm
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)
    return jsonify({'status': 'success'})


@app.route('/api/career-status')
def get_career_status():
    return jsonify(load_career_data())


@app.route('/api/standings')
def get_standings():
    career_data = load_career_data()
    tier_info   = career.get_tier_info(career_data['tier'])
    standings   = career.generate_standings(tier_info, career_data)
    return jsonify({
        'standings':       standings,
        'races_completed': career_data['races_completed'],
        'total_races':     career.get_tier_races(),
    })


@app.route('/api/all-standings')
def get_all_standings():
    career_data = load_career_data()
    all_s = career.generate_all_standings(career_data)
    return jsonify({
        'all_standings':   all_s,
        'current_tier':    career_data.get('tier', 0),
        'races_completed': career_data.get('races_completed', 0),
        'total_races':     career.get_tier_races(),
    })


@app.route('/api/season-calendar')
def get_season_calendar():
    career_data    = load_career_data()
    cfg            = load_config()
    tier_key       = career.tiers[career_data['tier']]
    tier_info      = cfg['tiers'][tier_key]
    tracks         = tier_info['tracks']
    races_per_tier = cfg['seasons']['races_per_tier']
    races_done     = career_data['races_completed']
    race_results   = career_data.get('race_results', [])

    cal = []
    for i in range(races_per_tier):
        track_id = tracks[i % len(tracks)]
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
    career_data = load_career_data()
    cfg         = load_config()
    tier_info   = career.get_tier_info(career_data['tier'])
    race_num    = career_data['races_completed'] + 1
    race = career.generate_race(tier_info, race_num, career_data['team'], career_data['car'])
    return jsonify(race)


@app.route('/api/start-race', methods=['POST'])
def start_race():
    career_data = load_career_data()
    cfg         = load_config()
    tier_info   = career.get_tier_info(career_data['tier'])
    race_num    = career_data['races_completed'] + 1
    race        = career.generate_race(tier_info, race_num, career_data['team'], career_data['car'])
    race['driver_name'] = career_data.get('driver_name', 'Player')
    mode    = (request.json or {}).get('mode', 'race_only')
    success = career.launch_ac_race(race, cfg, mode=mode)
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

    start_time = datetime.fromisoformat(race_started_at)

    tier_info     = career.get_tier_info(career_data['tier'])
    expected_laps = tier_info.get('race_format', {}).get('laps', 20)

    results_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'Assetto Corsa', 'results')
    if not os.path.exists(results_dir):
        return jsonify({'status': 'not_found', 'message': 'Results folder not found'})

    candidates = []
    for fname in os.listdir(results_dir):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(results_dir, fname)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime > start_time:
            candidates.append((mtime, fpath))

    if not candidates:
        return jsonify({'status': 'not_found', 'message': 'No result file found yet'})

    candidates.sort(key=lambda x: x[0], reverse=True)
    result_file = candidates[0][1]

    try:
        with open(result_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

    if data.get('Type', '').upper() != 'RACE':
        return jsonify({'status': 'not_found', 'message': 'Latest result is not a race session'})

    results = data.get('Result', [])

    player_result   = None
    player_position = None
    for i, r in enumerate(results):
        if r.get('DriverName', '').lower() == driver_name.lower():
            player_result   = r
            player_position = i + 1
            break

    if player_result is None:
        return jsonify({'status': 'not_found', 'message': 'Driver not found in results'})

    laps_completed = player_result.get('Laps', 0)
    total_time     = player_result.get('TotalTime', 0)
    best_lap_ms    = player_result.get('BestLap', 0)

    incomplete = (laps_completed < max(1, expected_laps // 2)) or (total_time == 0 and laps_completed == 0)

    best_lap_fmt = ''
    if best_lap_ms and best_lap_ms > 0:
        mins         = best_lap_ms // 60000
        secs         = (best_lap_ms % 60000) / 1000
        best_lap_fmt = f'{mins:02d}:{secs:06.3f}'

    return jsonify({
        'status':         'incomplete' if incomplete else 'found',
        'position':       player_position,
        'best_lap':       best_lap_fmt,
        'laps_completed': laps_completed,
        'expected_laps':  expected_laps,
        'driver_name':    driver_name,
    })


@app.route('/api/finish-race', methods=['POST'])
def finish_race():
    data        = request.json
    career_data = load_career_data()
    position    = data.get('position', 1)
    pts_table   = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    pts         = pts_table[min(position - 1, 9)] if position <= 10 else 0
    result = {
        'race_num': career_data['races_completed'] + 1,
        'position': position,
        'points':   pts,
        'lap_time': data.get('lap_time', ''),
    }
    career_data['races_completed'] += 1
    career_data['points']          += pts
    career_data['race_results'].append(result)
    save_career_data(career_data)
    if career_data['races_completed'] >= career.get_tier_races():
        return _do_end_season()
    return jsonify({'status': 'success', 'result': result, 'total_points': career_data['points']})


@app.route('/api/end-season', methods=['POST'])
def end_season():
    return _do_end_season()


def _do_end_season():
    career_data = load_career_data()
    cfg         = load_config()
    tier_info   = career.get_tier_info(career_data['tier'])
    standings   = career.generate_standings(tier_info, career_data)
    position    = next((s['position'] for s in standings if s['is_player']), 1)
    team_count  = len(tier_info['teams'])
    contracts   = career.generate_contract_offers(
        position, career_data['tier'] + 1, cfg,
        current_tier=career_data['tier'],
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
    data        = request.json
    career_data = load_career_data()
    contract_id = data.get('contract_id')
    selected    = next((c for c in career_data['contracts'] if c.get('id') == contract_id), None)
    if not selected:
        return jsonify({'status': 'error', 'message': 'Contract not found'}), 400
    career_data['tier']            += 1
    career_data['season']          += 1
    career_data['team']             = selected['team_name']
    career_data['car']              = selected['car']
    career_data['races_completed']  = 0
    career_data['points']           = 0
    career_data['race_results']     = []
    career_data['contracts']        = None
    career_data['standings']        = []
    save_career_data(career_data)
    return jsonify({
        'status':   'success',
        'message':  f"Welcome to {selected['team_name']}!",
        'new_tier': career_data['tier'],
        'new_team': career_data['team'],
        'new_car':  career_data['car'],
    })


@app.route('/api/new-career', methods=['POST'])
def new_career():
    data        = request.json or {}
    driver_name = data.get('driver_name', '').strip() or 'Driver'
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
    }
    save_career_data(initial)
    return jsonify({'status': 'success', 'message': 'New career started!', 'career_data': initial})


@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(load_config())


@app.route('/api/config', methods=['POST'])
def update_config():
    new_cfg = request.json
    with open(CONFIG_PATH, 'w') as f:
        json.dump(new_cfg, f, indent=2)
    return jsonify({'status': 'success', 'message': 'Configuration updated'})


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

    class JsApi:
        """Python functions exposed to JavaScript via window.pywebview.api"""
        def browse_folder(self):
            result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
            return result[0] if result else None

    def run_flask():
        app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(0.8)  # let Flask start up

    api    = JsApi()
    window = webview.create_window(
        'AC Career Manager',
        'http://127.0.0.1:5000',
        width=1440, height=920,
        min_size=(1000, 700),
        js_api=api,
    )
    try:
        webview.start(gui='edgechromium')
    except Exception:
        webview.start()
