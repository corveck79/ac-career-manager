"""
Driver Progress — skill evolution system for AI drivers.

Tracks per-driver skill stats across races and seasons. Each driver has an age,
potential rating, and current skill values that drift over time based on
age curve, potential, and deterministic noise.

Extracted from app.py to keep the Flask routes focused on HTTP logic.
"""

import hashlib

from driver_data import DRIVER_PROFILES

DRIVER_SKILL_KEYS = ['skill', 'aggression', 'wet_skill', 'quali_pace', 'consistency']


def _clamp(value, low, high):
    return max(low, min(high, value))


def _seed_int(seed_text, low, high):
    raw = int(hashlib.md5(seed_text.encode('utf-8')).hexdigest()[:8], 16)
    span = max(1, (high - low + 1))
    return low + (raw % span)


def compute_progress_deltas(entry):
    """Return race/season/career deltas for a driver progress entry."""
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


def driver_trend_label(entry):
    """Return 'Rising', 'Declining', or 'Stable' based on season deltas."""
    deltas = compute_progress_deltas(entry).get('season', {})
    net = sum(float(deltas.get(k, 0)) for k in DRIVER_SKILL_KEYS)
    if net >= 1.0:
        return 'Rising'
    if net <= -1.0:
        return 'Declining'
    return 'Stable'


def ensure_driver_progress(career_data):
    """Initialise or backfill driver_progress entries for all known drivers."""
    roster = career_data.setdefault('driver_progress', {})
    changed = False
    for name, base in DRIVER_PROFILES.items():
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


WET_PRESETS = {'rainy', 'heavy_rain', 'wet', 'light_rain', 'drizzle', 'stormy', 'overcast_wet'}


def evolve_driver_progress_for_race(career_data, race_num, weather=None):
    """Apply one race tick of skill drift to every driver.

    If *weather* is a wet preset, drivers also get an extra wet_skill bump
    (diminishing returns — high wet_skill improves less).
    """
    ensure_driver_progress(career_data)
    season = career_data.get('season', 1)
    tier = career_data.get('tier', 0)
    is_wet = bool(weather and weather.lower().replace(' ', '_') in WET_PRESETS)

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

        # Wet race bonus: extra wet_skill growth with diminishing returns
        if is_wet:
            ws = float(current.get('wet_skill', 60))
            wet_room = max(0, (90 - ws) / 40)       # 0.75 at ws=60, 0.0 at ws≥90
            wet_delta = 0.15 * wet_room * (potential / 80)
            current['wet_skill'] = round(_clamp(ws + wet_delta, 40.0, 99.0), 2)


def process_retirements(career_data, season):
    """At season end, retire eligible drivers (age 38+). Returns list of newly retired.

    Probability: (age − 37) × 15%, capped at 60%.  Max 3 retirements per season.
    Decision is deterministic (seeded by name + season).
    """
    retired = set(career_data.get('retired_drivers', []))
    progress = career_data.get('driver_progress', {})
    newly_retired = []
    for name, entry in progress.items():
        if name in retired:
            continue
        age = int(entry.get('age', 25))
        if age < 38:
            continue
        threshold = min(60, (age - 37) * 15)
        roll = _seed_int(f'retire|{name}|{season}', 0, 99)
        if roll < threshold:
            retired.add(name)
            newly_retired.append({
                'name': name, 'age': age, 'season': season,
                'nickname': DRIVER_PROFILES.get(name, {}).get('nickname'),
            })
        if len(newly_retired) >= 3:
            break
    career_data['retired_drivers'] = sorted(retired)
    career_data.setdefault('retirement_log', []).extend(newly_retired)
    return newly_retired


def advance_driver_progress_season(career_data):
    """Age all drivers by 1 year and snapshot season_start for next season."""
    ensure_driver_progress(career_data)
    for _, entry in (career_data.get('driver_progress') or {}).items():
        entry['age'] = int(_clamp(int(entry.get('age', 25)) + 1, 18, 55))
        current = entry.get('current') or {}
        entry['season_start'] = {k: float(current.get(k, 70)) for k in DRIVER_SKILL_KEYS}
        entry['last_delta'] = {k: 0.0 for k in DRIVER_SKILL_KEYS}
    # Halve form scores at season boundary (carry some momentum)
    form = career_data.get('form_scores', {})
    for name in list(form):
        form[name] = round(form[name] * 0.5, 3)


def update_form_scores(career_data, ai_standings):
    """Update per-driver form_score based on latest race standings.

    ai_standings: list of {'name': ..., 'points': ...} for the current tier,
                  sorted by points descending (P1 first).

    form_score is an EMA (-1.0 to +1.0) that translates to ±2 AI_LEVEL points.
    Top 25% → delta +0.25, Bottom 25% → delta -0.25, Middle → 0.0.
    """
    form = career_data.setdefault('form_scores', {})
    if not ai_standings:
        return
    total = len(ai_standings)
    top_cutoff = max(1, total // 4)       # top 25%
    bot_cutoff = total - max(1, total // 4)  # bottom 25%

    for rank, entry in enumerate(ai_standings):
        name = entry.get('driver') or entry.get('name', '')
        if not name or entry.get('is_player'):
            continue
        if rank < top_cutoff:
            delta = 0.25
        elif rank >= bot_cutoff:
            delta = -0.25
        else:
            delta = 0.0
        old = form.get(name, 0.0)
        new_score = _clamp(old * 0.65 + delta * 0.35, -1.0, 1.0)
        form[name] = round(new_score, 3)


def update_rivalries(career_data, standings, tier_key):
    """After each race, detect/decay rivalries based on standings proximity."""
    all_rivalries = career_data.setdefault('rivalries', {})
    tier_rivals = all_rivalries.setdefault(tier_key, [])
    season = career_data.get('season', 1)

    # Build position pairs within 10 points and <= 2 positions apart
    close_pairs = set()
    sorted_standings = sorted(
        [s for s in standings if not s.get('is_player')],
        key=lambda s: s.get('points', 0), reverse=True
    )
    for i, a in enumerate(sorted_standings):
        for b in sorted_standings[i + 1:i + 3]:  # only check next 2 positions
            gap = abs(a.get('points', 0) - b.get('points', 0))
            if gap <= 10:
                pair = tuple(sorted([a['driver'], b['driver']]))
                close_pairs.add(pair)

    # Update existing rivalries
    for rival in tier_rivals:
        pair = tuple(sorted(rival['drivers']))
        if pair in close_pairs:
            rival['intensity'] = min(5, rival['intensity'] + 1)
            close_pairs.discard(pair)
        else:
            rival['intensity'] -= 1

    # Remove dead rivalries
    tier_rivals[:] = [r for r in tier_rivals if r['intensity'] > 0]

    # Create new rivalries from remaining close pairs (max 5 per tier)
    for pair in close_pairs:
        if len(tier_rivals) >= 5:
            break
        tier_rivals.append({
            'drivers': list(pair), 'intensity': 1, 'since_season': season
        })
