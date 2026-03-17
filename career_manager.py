"""
Career Manager - Game Logic
Handles tiers, teams, contracts, race generation
"""

import json
import random
import hashlib
from datetime import datetime
import subprocess
import os

from platform_paths import get_ac_docs_path, is_linux
from driver_data import (DRIVER_NAMES, DRIVER_PROFILES, DRIVERS_PER_TEAM,
                         TIER_SLOT_OFFSET, TRACK_PREFERENCES, get_driver_style)


class CareerManager:
    """Main career management system"""

    # Data constants imported from driver_data.py (kept as class attrs for backward compat)
    DRIVER_NAMES     = DRIVER_NAMES
    DRIVER_PROFILES  = DRIVER_PROFILES
    DRIVERS_PER_TEAM = DRIVERS_PER_TEAM
    TIER_SLOT_OFFSET = TIER_SLOT_OFFSET

    # Track type classification for track affinity system.
    # 'technical' = short/twisty (< ~3.5 km), 'fast' = long/high-speed (> ~5 km).
    # Omitted tracks default to 'balanced' (no bonus/penalty for anyone).
    TRACK_TYPE = {
        # Technical tracks (short, twisty)
        'ks_brands_hatch/indy':           'technical',
        'ks_vallelunga/club_circuit':     'technical',
        'magione':                         'technical',
        'ks_silverstone/national':        'technical',
        'ks_red_bull_ring/layout_national':'technical',
        'ks_black_cat_county/layout_long':'technical',
        'ks_brands_hatch/gp':            'technical',
        # Fast tracks (long, high-speed)
        'monza':                          'fast',
        'spa':                            'fast',
        'ks_silverstone/gp':             'fast',
        'ks_nurburgring/layout_gp':      'fast',
        # Balanced tracks (medium — no advantage for anyone)
        # 'zandvoort', 'ks_barcelona/layout_gp', 'imola' → default 'balanced'
    }

    def __init__(self, config):
        self.config = config
        self.tiers = ['mx5_cup', 'gt4', 'gt3', 'wec']
        self._procedural_name_cache = {}
        self.tier_names = {
            'mx5_cup': 'MX5 Cup',
            'gt4':     'GT4 SuperCup',
            'gt3':     'British GT GT3',
            'wec':     'WEC / Elite'
        }

    def get_driver_profile(self, name, career_data=None):
        """Return profile dict for a driver name, with derived style field."""
        defaults = {"nationality": "GBR", "skill": 80, "aggression": 40,
                     "wet_skill": 65, "quali_pace": 65, "consistency": 65, "nickname": None}
        p = {**defaults, **self.DRIVER_PROFILES.get(name, {})}
        if career_data:
            progress = (career_data.get('driver_progress') or {}).get(name, {})
            current = progress.get('current') or {}
            for key in ['skill', 'aggression', 'wet_skill', 'quali_pace', 'consistency']:
                if key in current:
                    p[key] = int(round(float(current[key])))
        return {**p, "style": get_driver_style(p["skill"], p["aggression"])}

    def get_tier_info(self, tier_index):
        """Get tier configuration by index"""
        tier_name = self.tiers[tier_index]
        return self.config['tiers'][tier_name]

    def get_tier_races(self, career_data=None):
        """Get total races for the player's current tier (= length of track list)."""
        if career_data is None:
            return self.config['seasons'].get('races_per_tier', 10)
        tier_key  = self.tiers[career_data.get('tier', 0)]
        tier_info = self.config['tiers'][tier_key]
        cs        = career_data.get('career_settings') or {}
        tracks    = (cs.get('custom_tracks') or {}).get(tier_key) or tier_info['tracks']
        return len(tracks)

    # ------------------------------------------------------------------
    # Race generation
    # ------------------------------------------------------------------

    def generate_race(self, tier_info, race_num, team_name, car,
                      tier_key=None, season=1, weather_mode='realistic', night_cycle=True,
                      career_data=None):
        """Generate next race configuration.
        weather_mode: 'realistic' (default pool) | 'always_clear' | 'wet_challenge'
        night_cycle: if True and laps >= 30, enables time-of-day progression via SUN_ANGLE + TIME_OF_DAY_MULT
        """
        tracks = tier_info['tracks']
        track = tracks[(race_num - 1) % len(tracks)]

        ai_difficulty = self._calculate_ai_difficulty(team_name, tier_info)
        opponents = self._generate_opponent_field(tier_info, race_num, tier_key=tier_key,
                                                  season=season, career_data=career_data)

        weather_seed = season * 1000 + race_num
        weather = self._pick_weather(tier_info['race_format'], track, weather_mode=weather_mode,
                                     seed=weather_seed)

        laps = (tier_info['race_laps'][race_num - 1]
                if tier_info.get('race_laps') and (race_num - 1) < len(tier_info['race_laps'])
                else tier_info['race_format'].get('laps', 20))

        # Night cycle: endurance races (>= 30 laps) get 1 full 24h day-night cycle
        sun_angle        = None
        time_of_day_mult = None
        if night_cycle and laps >= 30:
            race_hours       = laps * 2 / 60
            time_of_day_mult = max(8, round(24 / race_hours))
            sun_angle        = 40  # ~14:00 start → dark at 1/3, dawn at 2/3

        return {
            'race_num':         race_num,
            'track':            track,
            'car':              car,
            'team':             team_name,
            'ai_difficulty':    ai_difficulty,
            'opponents':        opponents,
            'laps':             laps,
            'time_limit':       tier_info['race_format'].get('time_limit_minutes', 45),
            'practice_minutes': tier_info['race_format'].get('practice_minutes', 10),
            'quali_minutes':    tier_info['race_format'].get('quali_minutes', 10),
            'weather':          weather,
            'sun_angle':        sun_angle,
            'time_of_day_mult': time_of_day_mult,
        }

    # Tracks that have wet weather support in vanilla AC
    WET_TRACKS = {
        'spa', 'monza', 'mugello', 'imola',
        'ks_silverstone', 'ks_brands_hatch',
        'ks_red_bull_ring', 'ks_vallelunga',
    }

    def _pick_weather(self, race_format, track, weather_mode='realistic', seed=None):
        """Pick a weather preset.
        weather_mode:
          'always_clear'  → always 3_clear
          'wet_challenge' → mostly wet / heavy cloud
          'csp_pure'      → dramatic mix, maximises CSP Pure visual range
          'realistic'     → use the tier's weighted weather_pool (default)
        Falls back to 7_heavy_clouds if wet is picked on an unsupported track.
        seed: if provided, uses a seeded RNG so the same race always gets the same weather.
        """
        if weather_mode == 'always_clear':
            return '3_clear'

        if weather_mode == 'wet_challenge':
            pool = [['wet', 60], ['7_heavy_clouds', 30], ['4_mid_clear', 10]]
        elif weather_mode == 'csp_pure':
            # Dramatic mix — maximises Pure Weather FX visual range
            pool = [['7_heavy_clouds', 30], ['wet', 25], ['6_light_clouds', 20],
                    ['4_mid_clear', 15], ['3_clear', 10]]
        else:  # realistic
            pool = race_format.get('weather_pool', [['3_clear', 100]])

        presets = [p[0] for p in pool]
        weights = [p[1] for p in pool]
        rng     = random.Random(seed) if seed is not None else random
        chosen  = rng.choices(presets, weights=weights, k=1)[0]

        if chosen == 'wet':
            track_folder = track.split('/')[0]
            if track_folder not in self.WET_TRACKS:
                chosen = '7_heavy_clouds'  # fallback: overcast but no rain

        return chosen

    def _calculate_ai_difficulty(self, team_name, tier_info):
        base = self.config['difficulty']['base_ai_level']
        adj  = tier_info['ai_difficulty']
        var  = random.uniform(
            -self.config['difficulty']['ai_variance'],
             self.config['difficulty']['ai_variance']
        )
        return max(60, min(100, base + adj + var))

    def _generate_opponent_field(self, tier_info, race_num, tier_key=None, season=1, career_data=None):
        opponents = []
        offset = self.TIER_SLOT_OFFSET.get(tier_key, 0) if tier_key else 0
        dpt    = self.DRIVERS_PER_TEAM.get(tier_key, 1) if tier_key else 1
        career_seed = int((career_data or {}).get('driver_seed') or 0)
        name_mode = self._get_name_mode(career_data)
        for i, team in enumerate(tier_info['teams']):
            perf = team.get('performance', 0) + random.uniform(-0.5, 0.5)
            global_slot = offset + i * dpt
            driver_name = self._get_driver_name(
                global_slot, season, career_seed, name_mode,
                career_data=career_data
            ) if tier_key else None
            opponents.append({
                'number':      i + 1,
                'team':        team['name'],
                'car':         team['car'],
                'tier':        team.get('tier', 'customer'),
                'performance': perf,
                'driver_name': driver_name,
                'global_slot': global_slot,
            })
        return opponents

    # ------------------------------------------------------------------
    # Weekend simulation — practice and qualifying results
    # ------------------------------------------------------------------

    def simulate_qualifying(self, opponents, ai_lvl, career_data=None):
        """Simulate qualifying for all opponents + player.

        Each driver runs 3 hot laps (take best). Pace is driven by quali_pace
        and car performance; consistency determines lap-to-lap variance.

        Returns list sorted P1→last:
            [{'name', 'car', 'team', 'is_player', 'pace_score', 'position'}, ...]
        """
        player_team = (career_data or {}).get('team')
        results = []
        for opp in opponents[:19]:
            if player_team and opp.get('team') == player_team:
                continue  # player fills this slot — skip the AI stand-in
            name    = opp.get('driver_name') or ''
            profile = self.get_driver_profile(name, career_data=career_data)
            base    = opp.get('performance', 0) + (profile.get('quali_pace', 75) - 75) * 0.4
            spread  = (100 - profile.get('consistency', 75)) * 0.08
            best    = max(base + random.gauss(0, spread) for _ in range(3))
            results.append({
                'name': name, 'car': opp.get('car', ''),
                'team': opp.get('team', ''), 'is_player': False, 'pace_score': best,
            })

        # Player pace: relative to field average, scaled by adaptive AI level
        field_avg   = sum(r['pace_score'] for r in results) / len(results) if results else 0
        player_pace = field_avg + (ai_lvl - 80) * 0.15 + random.gauss(0, 1.5)
        results.append({
            'name': 'PLAYER', 'car': '', 'team': '', 'is_player': True, 'pace_score': player_pace,
        })

        results.sort(key=lambda x: x['pace_score'], reverse=True)
        for i, r in enumerate(results):
            r['position'] = i + 1
        return results

    # ------------------------------------------------------------------
    # Standings — deterministic AI, real player points
    # ------------------------------------------------------------------

    def _get_name_mode(self, career_data):
        cs = (career_data or {}).get('career_settings') or {}
        mode = str(cs.get('name_mode', 'curated')).strip().lower()
        return mode if mode in {'curated', 'procedural'} else 'curated'

    def _get_procedural_driver_name(self, global_slot, season, career_seed):
        cache_key = (season, career_seed)
        pool = self._procedural_name_cache.get(cache_key)
        if pool is None:
            first_names = sorted({name.split(' ', 1)[0] for name in self.DRIVER_NAMES if ' ' in name})
            last_names = sorted({name.split(' ', 1)[1] for name in self.DRIVER_NAMES if ' ' in name})
            seed = int(hashlib.md5(
                f"procedural_names|{season}|{career_seed}".encode()
            ).hexdigest()[:8], 16)
            rng = random.Random(seed)
            pairs = [f"{first} {last}" for first in first_names for last in last_names]
            rng.shuffle(pairs)
            pool = pairs
            self._procedural_name_cache[cache_key] = pool
        return pool[global_slot % len(pool)]

    def _build_season_roster(self, season, career_seed=0, retired_set=None):
        """Build slot→name mapping for entire season, skipping retired drivers."""
        cache_key = (season, career_seed, frozenset(retired_set or set()))
        if hasattr(self, '_roster_cache') and cache_key in self._roster_cache:
            return self._roster_cache[cache_key]

        seed = int(hashlib.md5(
            f"global_drivers|{season}|{career_seed}".encode()
        ).hexdigest()[:8], 16)
        rng = random.Random(seed)
        pool = list(self.DRIVER_NAMES)
        rng.shuffle(pool)

        available = [n for n in pool if n not in (retired_set or set())]
        roster = {}
        for slot in range(len(pool)):
            roster[slot] = available[slot % len(available)]

        if not hasattr(self, '_roster_cache'):
            self._roster_cache = {}
        self._roster_cache[cache_key] = roster
        return roster

    def _get_driver_name(self, global_slot, season, career_seed=0, name_mode='curated',
                         career_data=None):
        """Return a globally unique driver name for the given slot and season.
        Uses a single season-seeded shuffle of the full name pool so that each
        slot index maps to a distinct name across all tiers simultaneously.
        Checks mid-season swap overrides first, then retirement skip logic."""
        # Mid-season swap override
        swaps = (career_data or {}).get('driver_swaps', {})
        swap_name = swaps.get(str(global_slot))
        if swap_name:
            return swap_name

        if name_mode == 'procedural':
            return self._get_procedural_driver_name(global_slot, season, career_seed)

        retired_set = set((career_data or {}).get('retired_drivers', []))
        if retired_set:
            roster = self._build_season_roster(season, career_seed, retired_set)
            return roster[global_slot % len(self.DRIVER_NAMES)]

        # Original path (no retirements — identical behavior)
        seed = int(hashlib.md5(
            f"global_drivers|{season}|{career_seed}".encode()
        ).hexdigest()[:8], 16)
        rng  = random.Random(seed)
        pool = list(self.DRIVER_NAMES)
        rng.shuffle(pool)
        return pool[global_slot % len(pool)]

    def _get_driver_split(self, team_name, tier_key, season):
        """Deterministic primary-driver share of team points (0.50–0.65)."""
        seed = int(hashlib.md5(
            f"split|{team_name}|{tier_key}|{season}".encode()
        ).hexdigest()[:8], 16)
        rng = random.Random(seed)
        return 0.50 + rng.random() * 0.15

    def _is_car_usable(self, car, ac_path):
        """Return True if the car folder has data/ or data.acd (i.e. is not empty/missing)."""
        if not car or not ac_path:
            return True  # no AC path → don't filter; preflight will warn later
        car_path = os.path.join(ac_path, 'content', 'cars', car)
        return (
            os.path.isdir(os.path.join(car_path, 'data')) or
            os.path.isfile(os.path.join(car_path, 'data.acd'))
        )

    def generate_standings(self, tier_info, career_data, tier_key=None):
        """Build driver championship standings.

        MX5 Cup is a single-driver series (1 entry per team).
        GT4 / GT3 / WEC have 2 championship drivers per team.
        Names are globally unique across all 4 tiers (season-seeded global shuffle).
        Teams whose car folder is empty or missing are silently excluded.
        """
        races_done  = career_data.get('races_completed', 0)
        player_pts  = career_data.get('points', 0)
        player_team = career_data.get('team')
        season      = career_data.get('season', 1)
        tier_index  = career_data.get('tier', 0)
        career_seed = int((career_data or {}).get('driver_seed') or 0)
        name_mode   = self._get_name_mode(career_data)

        if tier_key is None:
            tier_key = self.tiers[tier_index]

        # Filter teams whose car folder is empty / missing data
        ac_path     = self.config.get('paths', {}).get('ac_install', '')
        valid_teams = [t for t in tier_info['teams']
                       if self._is_car_usable(t.get('car', ''), ac_path)]
        team_count  = len(valid_teams)

        dpt    = self.DRIVERS_PER_TEAM.get(tier_key, 1)   # drivers per team
        offset = self.TIER_SLOT_OFFSET.get(tier_key, 0)   # global slot start

        entries = []
        for i, team in enumerate(valid_teams):
            is_player_team = (team['name'] == player_team)
            slot1 = offset + i * dpt

            if is_player_team:
                pts1  = player_pts
                name1 = career_data.get('driver_name') or 'Player'
            else:
                pts1  = self._calc_ai_points(team, season, tier_index, races_done, team_count)
                name1 = self._get_driver_name(slot1, season, career_seed, name_mode,
                                              career_data=career_data)

            if dpt == 1:
                # Single-driver entry (MX5 Cup)
                entries.append({
                    'team':       team['name'],
                    'driver':     name1,
                    'driver2':    None,
                    'car':        team['car'],
                    'points':     pts1,
                    'races':      races_done,
                    'is_player':  is_player_team,
                    'is_primary': True,
                    'tier_level': team.get('tier', 'customer'),
                    'global_slot': slot1,
                })
            else:
                # Two drivers per team (GT4 / GT3 / WEC)
                slot2 = slot1 + 1
                name2 = self._get_driver_name(slot2, season, career_seed, name_mode,
                                              career_data=career_data)

                # Co-driver uses the same team performance but a slightly different seed
                codriver_team = dict(team)
                codriver_team['name'] = team['name'] + '_codriver'
                pts2 = self._calc_ai_points(
                    codriver_team, season, tier_index, races_done, team_count
                )

                # Primary driver entry
                entries.append({
                    'team':       team['name'],
                    'driver':     name1,
                    'driver2':    name2,
                    'car':        team['car'],
                    'points':     pts1,
                    'races':      races_done,
                    'is_player':  is_player_team,
                    'is_primary': True,
                    'tier_level': team.get('tier', 'customer'),
                    'global_slot': slot1,
                })
                # Co-driver entry
                entries.append({
                    'team':       team['name'],
                    'driver':     name2,
                    'driver2':    name1,
                    'car':        team['car'],
                    'points':     pts2,
                    'races':      races_done,
                    'is_player':  False,
                    'is_primary': False,
                    'tier_level': team.get('tier', 'customer'),
                    'global_slot': slot2,
                })

        entries.sort(key=lambda x: x['points'], reverse=True)
        leader = entries[0]['points'] if entries else 0
        ai_skin = 1
        for i, s in enumerate(entries):
            s['position'] = i + 1
            s['gap']      = leader - s['points']
            if s['is_player']:
                s['skin_index'] = 0
            else:
                s['skin_index'] = ai_skin
                ai_skin += 1

        return entries

    def generate_team_standings_from_drivers(self, driver_entries):
        """Aggregate driver entries into team championship (1 row per team, summed points)."""
        teams_order = []
        seen = {}
        for entry in driver_entries:
            tn = entry['team']
            if tn not in seen:
                teams_order.append(tn)
                seen[tn] = {
                    'team':       tn,
                    'car':        entry['car'],
                    'points':     0,
                    'races':      entry['races'],
                    'is_player':  False,
                    'tier_level': entry['tier_level'],
                    '_drivers':   [],
                }
            seen[tn]['points'] += entry['points']
            seen[tn]['_drivers'].append((entry.get('is_primary', True), entry['driver']))
            if entry.get('is_player'):
                seen[tn]['is_player'] = True

        team_list = []
        for tn in teams_order:
            t = seen[tn]
            # Sort so primary driver (is_primary=True) is first
            drivers = sorted(t.pop('_drivers'), key=lambda x: (0 if x[0] else 1))
            t['driver']  = drivers[0][1] if drivers else ''
            t['driver2'] = drivers[1][1] if len(drivers) > 1 else None
            team_list.append(t)

        team_list.sort(key=lambda x: x['points'], reverse=True)
        leader = team_list[0]['points'] if team_list else 0
        for i, t in enumerate(team_list):
            t['position'] = i + 1
            t['gap']      = leader - t['points']
        return team_list

    def generate_all_standings(self, career_data):
        """Return standings for all 4 tiers simultaneously.
        Each tier returns {'drivers': [...], 'teams': [...]}.
        Player appears only in their own tier; other tiers show pure AI with
        standings proportional to the player's season progress.
        Also returns tier_progress: {tier_key: {done, total}} via second return value."""
        result        = {}
        tier_progress = {}
        player_tier   = career_data.get('tier', 0)
        player_races  = career_data.get('races_completed', 0)
        player_total  = self.get_tier_races(career_data)

        for idx, tk in enumerate(self.tiers):
            tier_info = self.config['tiers'][tk]
            if idx == player_tier:
                sim = career_data
                tier_progress[tk] = {'done': player_races, 'total': player_total}
            else:
                ai_done, ai_total = self.get_ai_tier_races(tk, career_data)
                sim = {
                    'tier':            idx,
                    'season':          career_data.get('season', 1),
                    'team':            None,
                    'races_completed': ai_done,
                    'points':          0,
                    'driver_name':     '',
                    'driver_progress': career_data.get('driver_progress', {}),
                }
                tier_progress[tk] = {'done': ai_done, 'total': ai_total}
            drivers = self.generate_standings(tier_info, sim, tier_key=tk)
            teams   = self.generate_team_standings_from_drivers(drivers)
            result[tk] = {'drivers': drivers, 'teams': teams}
        return result, tier_progress

    def pick_rival(self, tier_key, season, career_data=None):
        """Pick the AI driver in tier_key whose skill is closest to 82.
        Called at new career start and on every contract acceptance (new season/tier).
        Returns a driver name string, or None if no drivers found.
        """
        tier_info = self.config['tiers'].get(tier_key)
        if not tier_info:
            return None
        offset    = self.TIER_SLOT_OFFSET.get(tier_key, 0)
        dpt       = self.DRIVERS_PER_TEAM.get(tier_key, 1)
        career_seed = int((career_data or {}).get('driver_seed') or 0)
        name_mode = self._get_name_mode(career_data)
        best_name = None
        best_diff = 999
        for i in range(len(tier_info['teams'])):
            slot    = offset + i * dpt
            name    = self._get_driver_name(slot, season, career_seed, name_mode,
                                          career_data=career_data)
            profile = self.get_driver_profile(name, career_data=career_data)
            diff    = abs(profile.get('skill', 80) - 82)
            if diff < best_diff:
                best_diff = diff
                best_name = name
        return best_name

    def check_mid_season_swaps(self, career_data, tier_info, tier_key):
        """At midpoint, bottom 2 multi-driver teams swap their worst driver."""
        dpt = self.DRIVERS_PER_TEAM.get(tier_key, 1)
        if dpt < 2:
            return []  # MX5 = single driver, no swaps

        standings = self.generate_standings(tier_info, career_data, tier_key=tier_key)
        team_standings = self.generate_team_standings_from_drivers(standings)

        # Bottom 2 teams (exclude player's team)
        bottom = [t for t in team_standings[-2:] if not t.get('is_player')]

        # Find unassigned drivers (not in any active slot, not retired)
        active_names = {s['driver'] for s in standings}
        retired = set(career_data.get('retired_drivers', []))
        available = [n for n in self.DRIVER_NAMES
                     if n not in active_names and n not in retired]

        swaps = career_data.setdefault('driver_swaps', {})
        swap_log = career_data.setdefault('swap_log', [])
        new_swaps = []

        for team_entry in bottom:
            team_name = team_entry['team']
            team_drivers = [s for s in standings
                            if s['team'] == team_name and not s.get('is_player')]
            if not team_drivers or not available:
                continue
            worst = min(team_drivers, key=lambda d: d['points'])
            replacement = available.pop(0)
            slot = worst.get('global_slot')
            if slot is None:
                continue
            swaps[str(slot)] = replacement
            entry = {
                'season': career_data.get('season', 1),
                'race': career_data.get('races_completed', 0),
                'team': team_name, 'tier': tier_key,
                'dropped': worst['driver'], 'replacement': replacement,
            }
            swap_log.append(entry)
            new_swaps.append(entry)

        return new_swaps

    def _calc_ai_points(self, team, season, tier_index, races_done, team_count):
        """
        Deterministic per-race AI points using MD5-seeded RNG.
        Same inputs → same output every time.
        """
        if races_done == 0:
            return 0

        pts_table = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
        perf      = team.get('performance', 0)   # −1.5 (slow) … +0.5 (fast)
        total     = 0

        for race_num in range(races_done):
            seed_str = f"{team['name']}|{season}|{tier_index}|{race_num}"
            seed     = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
            rng      = random.Random(seed)

            # Map performance to expected finishing position
            # perf 0.5  → position ≈ 1–3   (top)
            # perf -1.5 → position ≈ near back
            norm     = max(0.0, min(1.0, (0.5 - perf) / 2.0))
            base_pos = max(1, int(norm * team_count) + 1)

            # Add realistic race-to-race noise (±3 positions)
            pos = base_pos + rng.randint(-3, 3)
            pos = max(1, min(team_count, pos))

            total += pts_table[pos - 1] if pos <= 10 else 0

        return total

    # ------------------------------------------------------------------
    # Cross-tier race simulation
    # ------------------------------------------------------------------

    def get_ai_tier_races(self, tier_key, career_data):
        """How many races an AI tier has completed, proportional to player progress."""
        player_races = career_data.get('races_completed', 0)
        player_total = self.get_tier_races(career_data)
        fraction = player_races / player_total if player_total > 0 else 1.0
        cs = career_data.get('career_settings') or {}
        tier_info = self.config['tiers'][tier_key]
        tracks = (cs.get('custom_tracks') or {}).get(tier_key) or tier_info['tracks']
        return round(fraction * len(tracks)), len(tracks)

    def get_ai_race_grid(self, tier_key, race_num, season, career_data=None):
        """Full finishing grid for a specific AI race (0-indexed race_num).

        Uses the exact same MD5 seed pattern as _calc_ai_points so that
        cumulative points from individual grids match the standings.
        Returns {race_num, track, grid: [{position, driver, team}, ...]}.
        """
        tier_info   = self.config['tiers'][tier_key]
        tier_index  = self.tiers.index(tier_key)
        ac_path     = self.config.get('paths', {}).get('ac_install', '')
        valid_teams = [t for t in tier_info['teams']
                       if self._is_car_usable(t.get('car', ''), ac_path)]
        team_count  = len(valid_teams)
        if team_count == 0:
            return None

        dpt         = self.DRIVERS_PER_TEAM.get(tier_key, 1)
        offset      = self.TIER_SLOT_OFFSET.get(tier_key, 0)
        career_seed = int((career_data or {}).get('driver_seed') or 0)
        name_mode   = self._get_name_mode(career_data)

        cs     = (career_data or {}).get('career_settings') or {}
        tracks = (cs.get('custom_tracks') or {}).get(tier_key) or tier_info['tracks']
        track  = tracks[race_num % len(tracks)]

        # Calculate raw position score per driver (same formula as _calc_ai_points)
        entries = []
        for i, team in enumerate(valid_teams):
            for d in range(dpt):
                t_name = team['name'] if d == 0 else team['name'] + '_codriver'
                seed_str = f"{t_name}|{season}|{tier_index}|{race_num}"
                seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
                rng  = random.Random(seed)

                perf     = team.get('performance', 0)
                norm     = max(0.0, min(1.0, (0.5 - perf) / 2.0))
                base_pos = max(1, int(norm * team_count) + 1)
                raw_pos  = base_pos + rng.randint(-3, 3)
                raw_pos  = max(1, min(team_count, raw_pos))

                slot = offset + i * dpt + d
                driver = self._get_driver_name(slot, season, career_seed, name_mode,
                                               career_data=career_data)
                # Tiebreak: hash of driver name for deterministic ordering
                tie = int(hashlib.md5(f"{driver}|{race_num}".encode()).hexdigest()[:4], 16)
                entries.append({
                    'raw_pos': raw_pos,
                    'tie':     tie,
                    'driver':  driver,
                    'team':    team['name'],
                })

        # Sort by raw position, then tiebreak
        entries.sort(key=lambda e: (e['raw_pos'], e['tie']))
        grid = []
        for pos, e in enumerate(entries, 1):
            grid.append({'position': pos, 'driver': e['driver'], 'team': e['team']})

        return {
            'race_num': race_num + 1,   # 1-indexed for display
            'track':    track,
            'tier_key': tier_key,
            'grid':     grid,
        }

    # ------------------------------------------------------------------
    # Contracts
    # ------------------------------------------------------------------

    def generate_contract_offers(self, player_position, next_tier, config,
                                 current_tier=0, team_count=20):
        """Generate contract offers based on championship finish.

        Bottom 3 finishers get degradation risk: only the worst seat in the
        current tier or (if not already in the lowest tier) offers from the
        tier below.  Champion always gets promoted; top-3 get scouted by
        higher-tier teams.
        """
        degradation_risk = (player_position >= team_count - 2)

        # Career complete: only when NOT in degradation risk and already at top tier.
        # Degradation risk takes priority — even WEC last-place finishers drop to GT3.
        if not degradation_risk and next_tier >= len(self.tiers):
            return [{'message': 'Congratulations! Career complete!', 'complete': True}]

        if degradation_risk:
            offers = []
            current_tier_info = config['tiers'][self.tiers[current_tier]]

            # Worst customer seat in current tier (stay / same level)
            customers = [t for t in current_tier_info['teams']
                         if t.get('tier', 'customer') == 'customer']
            customers.sort(key=lambda t: t.get('performance', 0))
            if customers:
                team = customers[0]
                offers.append({
                    'id':               f"contract_deg_0_{int(datetime.now().timestamp())}",
                    'team_name':        team['name'],
                    'car':              team['car'],
                    'tier_name':        self.tier_names[self.tiers[current_tier]],
                    'tier_level':       'customer',
                    'target_tier':      current_tier,          # stay in same tier
                    'move':             'stay',
                    'degradation_risk': True,
                    'description':      (
                        f"Your season results were poor. "
                        f"{team['name']} offers you a chance to stay in "
                        f"{self.tier_names[self.tiers[current_tier]]}."
                    ),
                })

            # Offer(s) from lower tier (relegation — only if not already at bottom)
            if current_tier > 0:
                lower_tier_key  = self.tiers[current_tier - 1]
                lower_tier_info = config['tiers'][lower_tier_key]
                lower_teams     = [t for t in lower_tier_info['teams']
                                   if t.get('tier', 'customer') in ('factory', 'semi')]
                lower_teams.sort(key=lambda t: t.get('performance', 0), reverse=True)
                for j, team in enumerate(lower_teams[:2]):
                    offers.append({
                        'id':               f"contract_deg_{j+1}_{int(datetime.now().timestamp())}",
                        'team_name':        team['name'],
                        'car':              team['car'],
                        'tier_name':        self.tier_names[lower_tier_key],
                        'tier_level':       team.get('tier', 'semi'),
                        'target_tier':      current_tier - 1,  # drop one tier
                        'move':             'relegation',
                        'degradation_risk': True,
                        'description':      (
                            f"{team['name']} in {self.tier_names[lower_tier_key]} "
                            f"is interested in signing you."
                        ),
                    })
            return offers

        # Normal promotion path
        tier_info = config['tiers'][self.tiers[next_tier]]

        if player_position == 1:
            offer_count = config.get('contracts', {}).get('champion_offers', 4)
            tier_filter = ['factory', 'semi']
        elif player_position <= 3:
            offer_count = config.get('contracts', {}).get('top5_offers', 3)
            tier_filter = ['factory', 'semi']
        elif player_position <= 5:
            offer_count = config.get('contracts', {}).get('top5_offers', 3)
            tier_filter = ['semi', 'customer']
        elif player_position <= 10:
            offer_count = config.get('contracts', {}).get('top10_offers', 2)
            tier_filter = ['customer']
        else:
            offer_count = 1
            tier_filter = ['customer']

        available = [
            t for t in tier_info['teams']
            if t.get('tier', 'customer') in tier_filter
        ]

        selected = random.sample(available, min(offer_count, len(available)))

        offers = []
        for i, team in enumerate(selected):
            offers.append({
                'id':               f"contract_{i}_{int(datetime.now().timestamp())}",
                'team_name':        team['name'],
                'car':              team['car'],
                'tier_name':        self.tier_names[self.tiers[next_tier]],
                'tier_level':       team.get('tier', 'customer'),
                'target_tier':      next_tier,                 # promote to next tier
                'move':             'promotion',
                'degradation_risk': False,
                'description':      (
                    f"Join {team['name']} for the "
                    f"{self.tier_names[self.tiers[next_tier]]} season"
                ),
            })

        return offers

    # ------------------------------------------------------------------
    # AC launch
    # ------------------------------------------------------------------

    def _get_ac_docs_cfg(self):
        """Return path to AC's config folder where AC actually reads race.ini.
        Windows: ~/Documents/Assetto Corsa/cfg
        Linux:   Proton compat-data path/.../Documents/Assetto Corsa/cfg
        """
        return get_ac_docs_path("cfg")

    def launch_ac_race(self, race_config, config, mode='race_only', career_data=None,
                       session_type=None, grid=None):
        """Launch Assetto Corsa with race configuration.

        mode:         'race_only' (default) | 'full_weekend'
        session_type: 'practice' | 'qualifying' | 'race' — for split weekend sessions.
        grid:         Pre-sorted car list from simulate_qualifying() or AC quali results.
        """
        ac_path = config['paths']['ac_install']

        if not os.path.exists(ac_path):
            print(f"AC not found at {ac_path}")
            return False

        # AC reads config from Documents\Assetto Corsa\cfg — NOT the install folder
        docs_cfg = self._get_ac_docs_cfg()
        print(f"Writing config to: {docs_cfg}")

        # 1. Write race.ini to Documents (where AC actually reads it)
        race_cfg_path = os.path.join(docs_cfg, 'race.ini')
        self._write_race_config(race_cfg_path, race_config, ac_path, mode=mode,
                                career_data=career_data, session_type=session_type, grid=grid)

        # 2. Patch launcher.ini in Documents so AC starts in race mode
        launcher_path = os.path.join(docs_cfg, 'launcher.ini')
        self._patch_launcher_ini(launcher_path, race_config)

        # 3. Launch AC — method differs by OS
        try:
            if is_linux():
                # Linux: AC runs under Steam Proton; launch via Steam applaunch so
                # Proton environment, version pinning, and launch options are respected.
                subprocess.Popen(['steam', '-applaunch', '244210'])
            else:
                ac_exe = os.path.join(ac_path, 'acs.exe')
                subprocess.Popen(ac_exe, cwd=ac_path)
            return True
        except Exception as e:
            print(f"Failed to launch AC: {e}")
            return False

    def _patch_launcher_ini(self, launcher_path, race_config):
        """Patch DRIVE=race and TRACK in launcher.ini using raw line replacement.
        AC requires KEY=VALUE with NO spaces around = (strict format)."""
        try:
            track_folder = race_config['track'].split('/')[0]

            with open(launcher_path, 'r') as f:
                lines = f.readlines()

            patched_drive = False
            patched_track = False
            new_lines = []

            for line in lines:
                key = line.split('=')[0].strip().upper() if '=' in line else ''
                if key == 'DRIVE':
                    new_lines.append('DRIVE=race\n')
                    patched_drive = True
                elif key == 'TRACK':
                    new_lines.append(f'TRACK={track_folder}\n')
                    patched_track = True
                else:
                    new_lines.append(line)

            # If keys not found, insert after [SAVED] header
            if not patched_drive or not patched_track:
                result = []
                for line in new_lines:
                    result.append(line)
                    if line.strip().upper() == '[SAVED]':
                        if not patched_drive:
                            result.append('DRIVE=race\n')
                        if not patched_track:
                            result.append(f'TRACK={track_folder}\n')
                new_lines = result

            with open(launcher_path, 'w') as f:
                f.writelines(new_lines)

            print(f"launcher.ini patched: DRIVE=race TRACK={track_folder}")
        except Exception as e:
            print(f"Warning: could not patch launcher.ini: {e}")

    def _get_car_skin(self, car, ac_path, index=0):
        """Return skin at the given index for a car (wraps around if fewer skins).
        Use index=0 for player, index=1..N for AI cars so each gets a distinct livery."""
        skins_dir = os.path.join(ac_path, 'content', 'cars', car, 'skins')
        try:
            skins = sorted(os.listdir(skins_dir))
            return skins[index % len(skins)] if skins else ''
        except Exception:
            return ''

    def _write_race_config(self, config_path, race_data, ac_path='', mode='race_only',
                           career_data=None, session_type=None, grid=None):
        """Write AC race.ini in the format AC expects (Documents/Assetto Corsa/cfg/race.ini).

        mode:         'race_only' (default) | 'full_weekend' (practice + quali + race in one go)
        session_type: 'practice' | 'qualifying' | 'race' — single session for split weekend.
                      When set, overrides mode for session content and AI level calculation.
        grid:         Sorted list from simulate_qualifying() or actual quali results.
                      When provided, cars are written in grid order (player at correct position).
        """
        driver           = race_data.get('driver_name', 'Player')
        player_nation    = (career_data or {}).get('player_nationality', '')
        car              = race_data['car']
        laps             = race_data['laps']
        ai_lvl           = int(race_data['ai_difficulty'])
        opponents        = race_data.get('opponents', [])
        practice_minutes = race_data.get('practice_minutes', 10)
        quali_minutes    = race_data.get('quali_minutes', 10)
        weather          = race_data.get('weather', '3_clear')

        # Limit to 19 AI cars (20 total including player)
        ai_cars = opponents[:19]
        # When grid is provided its length is exact; otherwise ai_cars already contains
        # the right number of slots (player replaces their own team's AI entry, so the
        # total stays len(ai_cars), not len(ai_cars)+1).
        total_cars = len(grid) if grid else len(ai_cars)

        # Track can be "folder/layout" or just "folder"
        track_raw    = race_data['track']
        parts        = track_raw.split('/')
        track_folder = parts[0]
        config_track = parts[1] if len(parts) > 1 else ''

        # Player gets skin index 0; AI cars get 1, 2, 3… so each has a distinct livery
        skin = self._get_car_skin(car, ac_path, index=0) if ac_path else ''

        lines = []

        # [RACE] — main race block
        lines += [
            "[RACE]",
            f"TRACK={track_folder}",
            f"CONFIG_TRACK={config_track}",
            f"MODEL={car}",
            f"MODEL_CONFIG=",
            f"SKIN={skin}",
            f"PENALTIES=1",
            f"FIXED_SETUP=0",
            f"DRIFT_MODE=0",
            f"RACE_LAPS={laps}",
            f"CARS={total_cars}",
            f"AI_LEVEL={ai_lvl}",
            f"JUMP_START_PENALTY=0",
            f"WEATHER_0={weather}",
        ]
        if race_data.get('sun_angle') is not None:
            lines.append(f"SUN_ANGLE={race_data['sun_angle']}")
        if race_data.get('time_of_day_mult') is not None:
            lines.append(f"TIME_OF_DAY_MULT={race_data['time_of_day_mult']}")
        lines.append("")

        # [DRIVE] — player config
        # AI_LEVEL must be empty — a non-empty value tells AC to control this car as AI.
        lines += [
            "[DRIVE]",
            f"MODEL={car}",
            f"SKIN={skin}",
            f"MODEL_CONFIG=",
            f"AI_LEVEL=",
            f"AI_AGGRESSION=0",
            f"SETUP=",
            f"FIXED_SETUP=0",
            f"VIRTUAL_MIRROR=0",
            f"DRIVER_NAME={driver}",
            f"NATIONALITY={player_nation}",
            "",
        ]

        # [HEADER] — AC uses VERSION=2 to signal post-qualifying grid format.
        # Without this, AC may misread the file and misidentify the player car.
        lines += [
            "[HEADER]",
            "VERSION=2",
            "",
        ]

        # Sessions — single session (split weekend) or combined (full_weekend / race_only)
        if session_type == 'practice':
            lines += [
                "[SESSION_0]",
                "NAME=PRACTICE",
                "TYPE=1",
                "SPAWN_SET=PIT",
                f"DURATION_MINUTES={practice_minutes}",
                "LAPS=0",
                "",
            ]
        elif session_type == 'qualifying':
            lines += [
                "[SESSION_0]",
                "NAME=QUALIFY",
                "TYPE=2",
                "SPAWN_SET=PIT",
                f"DURATION_MINUTES={quali_minutes}",
                "LAPS=0",
                "",
            ]
        elif session_type == 'race':
            lines += [
                "[SESSION_0]",
                "NAME=RACE",
                "TYPE=3",
                "SPAWN_SET=START",
                f"LAPS={laps}",
                "DURATION_MINUTES=0",
                "",
            ]
        elif mode == 'full_weekend':
            lines += [
                "[SESSION_0]",
                "NAME=PRACTICE",
                "TYPE=1",
                "SPAWN_SET=PIT",
                f"DURATION_MINUTES={practice_minutes}",
                "LAPS=0",
                "",
                "[SESSION_1]",
                "NAME=QUALIFY",
                "TYPE=2",
                "SPAWN_SET=PIT",
                f"DURATION_MINUTES={quali_minutes}",
                "LAPS=0",
                "",
                "[SESSION_2]",
                "NAME=RACE",
                "TYPE=3",
                "SPAWN_SET=START",
                f"LAPS={laps}",
                "DURATION_MINUTES=0",
                "",
            ]
        else:
            lines += [
                "[SESSION_0]",
                "NAME=RACE",
                "TYPE=3",
                "SPAWN_SET=START",
                f"LAPS={laps}",
                "DURATION_MINUTES=0",
                "",
            ]

        # [GROOVE]
        lines += [
            "[GROOVE]",
            "VIRTUAL_LAPS=10",
            "MAX_LAPS=30",
            "STARTING_LAPS=0",
            "",
        ]

        # Wet weather detection — used for per-driver wet_skill AI adjustment
        WET_PRESETS = {'rainy', 'heavy_rain', 'wet', 'light_rain', 'drizzle', 'stormy', 'overcast_wet'}
        is_wet = weather.lower() in WET_PRESETS

        # Night/endurance detection — used for per-driver night_skill AI adjustment
        sun_angle  = race_data.get('sun_angle')
        time_mult  = race_data.get('time_of_day_mult') or 1
        if time_mult > 1:
            night_weight = 0.5   # endurance: ~half the race in darkness
        elif sun_angle is not None and sun_angle < -30:
            night_weight = 1.0   # explicit night race
        else:
            night_weight = 0.0

        # Success ballast: car model is the team differentiator; ballast only penalises recent winners.
        # Count P1 finishes in the last 3 races — each win adds 5 kg (max 15 kg).
        recent = (career_data or {}).get('race_results', [])[-3:]
        player_ballast = sum(5 for r in recent if r.get('position') == 1)

        # Base variance from config (used to scale per-driver consistency)
        base_variance = self.config.get('difficulty', {}).get('ai_level_variance', 1.5)

        # Track affinity: classify current track as fast/technical/balanced
        track_raw    = race_data['track']
        track_type   = self.TRACK_TYPE.get(track_raw, 'balanced')

        # Form scores from career_data (season momentum)
        form_scores  = (career_data or {}).get('form_scores', {})

        # Determine which skill attribute drives AI level for this session
        # qualifying → quali_pace only; full_weekend → blend; everything else → race skill
        if session_type == 'qualifying':
            ai_skill_mode = 'qualifying'
        elif mode == 'full_weekend':
            ai_skill_mode = 'blend'
        else:
            ai_skill_mode = 'race'

        def _ai_level_for(profile_, driver_name=''):
            """Compute a single AI level value for one driver."""
            if ai_skill_mode == 'qualifying':
                eff = float(profile_.get('quali_pace', 75))
            elif ai_skill_mode == 'blend':
                eff = (profile_['skill'] + profile_.get('quali_pace', 75)) / 2
            else:
                eff = float(profile_['skill'])
            s_off = int((eff - 80) * 0.2)
            w_adj = round((profile_.get('wet_skill', 60) - 50) * 0.08) if is_wet else 0
            n_adj = round((profile_.get('night_skill', 60) - 60) * 0.12 * night_weight)

            # Track affinity: +1 on preferred track type, -1 on mismatched
            driver_pref = TRACK_PREFERENCES.get(driver_name, 'balanced')
            if track_type != 'balanced' and driver_pref != 'balanced':
                t_adj = 1 if driver_pref == track_type else -1
            else:
                t_adj = 0

            # Season momentum / form: ±2 AI_LEVEL based on recent results
            form_adj = int(form_scores.get(driver_name, 0) * 2.5)

            cons  = profile_.get('consistency', 75)
            dvar  = min(base_variance * (1 + (50 - cons) / 50), 1.5)
            v_adj = random.uniform(-dvar, dvar)
            return max(50, min(100, int(ai_lvl + s_off + w_adj + n_adj + t_adj + form_adj + v_adj)))

        # Build ordered car list: grid order if provided, otherwise player P1 then AI.
        # grid entries: {'name', 'car', 'team', 'is_player', ...} sorted P1→last.
        # The player occupies one team slot, so that team must NOT also get an AI entry —
        # otherwise CARS count and actual CAR blocks diverge, producing a ghost "No name" car.
        opp_by_name  = {(opp.get('driver_name') or ''): opp for opp in ai_cars}
        player_team  = (career_data or {}).get('team')

        # Player always occupies CAR_0 — AC identifies the human player by MODEL=- in the
        # [CAR_0] block. Placing MODEL=- at any other slot causes AC to highlight the wrong
        # car as the player.  With RACE+SPAWN_SET=START (no qualifying session), CAR_N order
        # IS the grid order: CAR_0 = P1, CAR_1 = P2, etc.  The player therefore always starts
        # P1 in Race Only mode — this is a hard AC constraint that cannot be worked around
        # without the player actually driving a qualifying session.
        # AI cars follow in simulated qualifying order so they race in a realistic spread.
        if grid:
            ai_in_quali_order = [
                opp_by_name.get(g['name'], {'car': g.get('car', car), 'driver_name': g['name']})
                for g in grid if not g.get('is_player')
            ]
            car_entries = [{'type': 'player'}] + [
                {'type': 'ai', 'opp': opp} for opp in ai_in_quali_order
            ]
        else:
            # Skip the AI stand-in for the player's own team slot (ghost driver fix).
            car_entries = [{'type': 'player'}] + [
                {'type': 'ai', 'opp': opp} for opp in ai_cars
                if not (player_team and opp.get('team') == player_team)
            ]

        # Write [CAR_N] blocks in grid order
        # AI skins start at index 1 to reserve index 0 (00_official) exclusively for the player.
        # Using index=i would give CAR_0 skin index 0, colliding with the player livery and
        # causing AC to misidentify which car is the player.
        ai_skin_counter = 1
        for i, entry in enumerate(car_entries):
            if entry['type'] == 'player':
                # AC identifies the player slot via MODEL=- (a literal dash).
                # This is the format AC itself writes after a qualifying session.
                # AI_LEVEL and AI_AGGRESSION are omitted entirely for the player block.
                lines += [
                    f"[CAR_{i}]",
                    f"SETUP=",
                    f"SKIN={skin}",
                    f"MODEL=-",
                    f"MODEL_CONFIG=",
                    f"BALLAST={player_ballast}",
                    f"RESTRICTOR=0",
                    f"DRIVER_NAME={driver}",
                    f"NATIONALITY={player_nation}",
                    "",
                ]
            else:
                opp      = entry['opp']
                opp_car  = opp.get('car', car)
                opp_skin = self._get_car_skin(opp_car, ac_path, index=ai_skin_counter) if ac_path else ''
                ai_skin_counter += 1
                name     = opp.get('driver_name') or self.DRIVER_NAMES[i % len(self.DRIVER_NAMES)]
                # Prevent name collision with player: if an AI driver shares the player's
                # career name, read_race_result() would return the AI's result instead of
                # the player's actual result (the first match wins).
                if name.lower() == driver.lower():
                    name = name + ' II'
                profile  = self.get_driver_profile(name, career_data=career_data)
                nation   = profile['nationality']

                opp_ai_level  = _ai_level_for(profile, driver_name=name)
                opp_aggression = profile['aggression']
                consistency    = profile.get('consistency', 75)
                if consistency < 50:
                    opp_aggression = min(100, opp_aggression + int((50 - consistency) * 0.3))

                # Rivalry aggression boost (+5 for active rivals)
                _tk = self.tiers[(career_data or {}).get('tier', 0)]
                _tier_rivals = (career_data or {}).get('rivalries', {}).get(_tk, [])
                _rival_names = set()
                for _r in _tier_rivals:
                    if _r.get('intensity', 0) >= 3:
                        _rival_names.update(_r['drivers'])
                if name in _rival_names:
                    opp_aggression = min(100, opp_aggression + 5)

                # Team development: better-rated teams get less ballast (faster)
                opp_team_name = opp.get('team', '')
                team_dev      = (career_data or {}).get('team_development', {}).get(opp_team_name, {})
                dev_offset    = team_dev.get('rating_offset', 0)
                # +0.5 rating → -5kg ballast (faster); -0.5 → +5kg (slower)
                opp_ballast   = max(0, int(-dev_offset * 10))

                lines += [
                    f"[CAR_{i}]",
                    f"MODEL={opp_car}",
                    f"SKIN={opp_skin}",
                    f"MODEL_CONFIG=",
                    f"DRIVER_NAME={name}",
                    f"NATION_CODE={nation}",
                    f"AI_LEVEL={opp_ai_level}",
                    f"AI_AGGRESSION={opp_aggression}",
                    f"SETUP=",
                    f"BALLAST={opp_ballast}",
                    f"RESTRICTOR=0",
                    "",
                ]

        content = "\n".join(lines)

        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            f.write(content)

        print(f"race.ini written: {track_folder}/{config_track} | car={car} | laps={laps} | AI cars={len(ai_cars)}")


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    with open('config.json', 'r') as f:
        cfg = json.load(f)

    mgr      = CareerManager(cfg)
    tier_info = mgr.get_tier_info(0)
    fake_career = {
        'tier': 0, 'season': 1, 'team': 'Mazda Academy',
        'car': 'ks_mazda_mx5_cup', 'races_completed': 3,
        'points': 43, 'driver_name': 'Test Driver'
    }
    standings = mgr.generate_standings(tier_info, fake_career)
    for s in standings[:5]:
        print(s)
