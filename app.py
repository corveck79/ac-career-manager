"""
AC Career Manager - Flask Backend
Main application entry point
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import os
from datetime import datetime
from pathlib import Path

from career_manager import CareerManager
from setup_wizard import check_and_run_setup

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# ---------------------------------------------------------------------------
# First-run setup
# ---------------------------------------------------------------------------
print("\nChecking configuration...")
if not check_and_run_setup('config.json'):
    print("Setup failed. Please check your AC installation path.")
    exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CONFIG_PATH = 'config.json'
DATA_PATH   = 'career_data.json'

TRACK_NAMES = {
    # MX5 Cup
    'ks_silverstone/national':        'Silverstone National',
    'ks_brands_hatch/indy':           'Brands Hatch Indy',
    'magione':                        'Magione',
    'ks_vallelunga/club_circuit':     'Vallelunga Club',
    'ks_black_cat_county/layout_long':'Black Cat County',
    # GT4
    'ks_silverstone/gp':              'Silverstone GP',
    'ks_brands_hatch/gp':             'Brands Hatch GP',
    'ks_red_bull_ring/layout_national':'Red Bull Ring',
    # GT3 / WEC
    'spa':                            'Spa-Francorchamps',
    'monza':                          'Monza',
    'ks_laguna_seca':                 'Laguna Seca',
    'mugello':                        'Mugello',
    'imola':                          'Imola',
    # Extras
    'ks_nurburgring/layout_gp_a':     'Nürburgring GP',
    'ks_barcelona/layout_gp':         'Barcelona',
    'ks_zandvoort':                   'Zandvoort',
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
# Initialise
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


@app.route('/api/career-status')
def get_career_status():
    return jsonify(load_career_data())


@app.route('/api/standings')
def get_standings():
    career_data = load_career_data()
    tier_info   = career.get_tier_info(career_data['tier'])

    standings = career.generate_standings(tier_info, career_data)

    return jsonify({
        'standings':       standings,
        'races_completed': career_data['races_completed'],
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

    race = career.generate_race(
        tier_info, race_num,
        career_data['team'], career_data['car']
    )
    return jsonify(race)


@app.route('/api/start-race', methods=['POST'])
def start_race():
    career_data = load_career_data()
    cfg         = load_config()
    tier_info   = career.get_tier_info(career_data['tier'])
    race_num    = career_data['races_completed'] + 1

    race = career.generate_race(
        tier_info, race_num,
        career_data['team'], career_data['car']
    )
    race['driver_name'] = career_data.get('driver_name', 'Player')

    success = career.launch_ac_race(race, cfg)

    if success:
        return jsonify({'status': 'success', 'message': 'AC launched!', 'race': race})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to launch AC'}), 500


@app.route('/api/finish-race', methods=['POST'])
def finish_race():
    data        = request.json
    career_data = load_career_data()

    position    = data.get('position', 1)
    fastest_lap = data.get('fastest_lap', False)
    pts_table   = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
    pts         = pts_table[min(position - 1, 9)] if position <= 10 else 0
    if fastest_lap and position <= 10:
        pts += 1

    result = {
        'race_num': career_data['races_completed'] + 1,
        'position': position,
        'points':   pts,
        'lap_time': data.get('lap_time', ''),
        'fastest_lap': fastest_lap,
    }

    career_data['races_completed'] += 1
    career_data['points']          += pts
    career_data['race_results'].append(result)
    save_career_data(career_data)

    if career_data['races_completed'] >= career.get_tier_races():
        return _do_end_season()

    return jsonify({
        'status':       'success',
        'result':       result,
        'total_points': career_data['points'],
    })


@app.route('/api/end-season', methods=['POST'])
def end_season():
    return _do_end_season()


def _do_end_season():
    career_data = load_career_data()
    cfg         = load_config()

    tier_info = career.get_tier_info(career_data['tier'])
    standings = career.generate_standings(tier_info, career_data)

    # Player position
    position = next(
        (s['position'] for s in standings if s['is_player']), 1
    )

    contracts = career.generate_contract_offers(
        position, career_data['tier'] + 1, cfg
    )

    career_data['contracts']       = contracts
    career_data['final_position']  = position
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

    selected = next(
        (c for c in career_data['contracts'] if c.get('id') == contract_id),
        None
    )
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
        'status':    'success',
        'message':   f"Welcome to {selected['team_name']}!",
        'new_tier':  career_data['tier'],
        'new_team':  career_data['team'],
        'new_car':   career_data['car'],
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

    return jsonify({
        'status':      'success',
        'message':     'New career started!',
        'career_data': initial,
    })


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


if __name__ == '__main__':
    app.run(debug=False, host='localhost', port=5000)
