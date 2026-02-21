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


class CareerManager:
    """Main career management system"""

    # 120 globally unique driver names (covers all 106 driver slots across all tiers)
    DRIVER_NAMES = [
        # 0-9
        "Marco Rossi",       "James Hunt",        "Pierre Dupont",     "Hans Mueller",
        "Carlos Rivera",     "Tom Bradley",       "Luca Ferrari",      "Alex Chen",
        "David Williams",    "Raj Patel",
        # 10-19
        "Sven Johansson",    "Omar Hassan",       "Kenji Tanaka",      "Igor Petrov",
        "Fabio Romano",      "Ethan Clark",       "Nina Kovac",        "Lucas Petit",
        "Aiden Burke",       "Zara Osman",
        # 20-29
        "Felipe Rodrigues",  "Jan van der Berg",  "Mikael Lindqvist",  "Antoine Moreau",
        "Sebastian Richter", "Takumi Nakamura",   "Ryan O'Connor",     "Dimitri Volkov",
        "Wei Zhang",         "Emre Yilmaz",
        # 30-39
        "Stefan Baumann",    "Liam Fitzgerald",   "Pablo Sanchez",     "Yuki Hashimoto",
        "Cristian Popescu",  "Max Hartmann",      "Nico Berger",       "Andre Hoffmann",
        "Kofi Mensah",       "Ravi Sharma",
        # 40-49
        "Jake Morrison",     "Thomas Leclerc",    "Giulio Conti",      "Magnus Eriksson",
        "Aleksei Nikitin",   "Hiro Matsuda",      "Kevin Walsh",       "Leon Braun",
        "Samir Khalil",      "Dante Moraes",
        # 50-59
        "Felix Bauer",       "Connor MacLeod",    "Victor Blanc",      "Matteo Gallo",
        "Oskar Wiklund",     "Tariq Nasser",      "Samuel Obi",        "Dario Conti",
        "Erik Larsen",       "Julian Richter",
        # 60-69
        "Baptiste Renard",   "Kai Nakamura",      "Tobias Schreiber",  "Lorenzo Marini",
        "Jack Thornton",     "Vladimir Kozlov",   "Yasuhiro Ito",      "Patrick Brennan",
        "Roberto Mancini",   "Hugo Lefevre",
        # 70-79
        "Christoph Weber",   "Nils Gunnarsson",   "Mehmet Ozkan",      "Benedikt Fischer",
        "Alvaro Delgado",    "Finn Andersen",     "Artem Sokolov",     "Raul Jimenez",
        "Enzo Palermo",      "Timothy Hooper",
        # 80-89
        "Francois Girard",   "Kazuki Yamamoto",   "Benjamin Koch",     "Cian Murphy",
        "Mateus Costa",      "Tomas Novak",       "Rafael Torres",     "Pieter de Vries",
        "Duncan Fraser",     "Alexei Morozov",
        # 90-99
        "Simon Bertrand",    "Stephan Kramer",    "Mattias Svensson",  "Davide Russo",
        "Callum Stewart",    "Timur Bakirov",     "Marco Bianchi",     "Arnaud Leblanc",
        "Hiroshi Watanabe",  "Edward Collins",
        # 100-109
        "Gerhard Mayer",     "Luca Gentile",      "Frederick Larsson", "Alistair Young",
        "Marco Colombo",     "Jean-Paul Tissot",  "Adriano Ferretti",  "Sebastian Vallet",
        "Diego Morales",     "Andrei Popov",
        # 110-119
        "Josef Novotny",     "Henryk Kowalski",   "Kwame Asante",      "Taiki Oshima",
        "Brenden Walsh",     "Giacomo Vietti",    "Emilio Fernandez",  "Lars Petersen",
        "Nikolai Volkov",    "Kim Andersen",
    ]

    # How many championship drivers per team entry (MX5 is single-driver; GT3/GT4/WEC are 2)
    DRIVERS_PER_TEAM = {'mx5_cup': 1, 'gt4': 2, 'gt3': 2, 'wec': 2}

    # Global driver slot offset per tier:
    #   MX5:  14 teams × 1 = 14 drivers  → slots  0-13
    #   GT4:  16 teams × 2 = 32 drivers  → slots 14-45
    #   GT3:  20 teams × 2 = 40 drivers  → slots 46-85
    #   WEC:  10 teams × 2 = 20 drivers  → slots 86-105
    TIER_SLOT_OFFSET = {'mx5_cup': 0, 'gt4': 14, 'gt3': 46, 'wec': 86}

    def __init__(self, config):
        self.config = config
        self.tiers = ['mx5_cup', 'gt4', 'gt3', 'wec']
        self.tier_names = {
            'mx5_cup': 'MX5 Cup',
            'gt4':     'GT4 SuperCup',
            'gt3':     'British GT GT3',
            'wec':     'WEC / Elite'
        }

    def get_tier_info(self, tier_index):
        """Get tier configuration by index"""
        tier_name = self.tiers[tier_index]
        return self.config['tiers'][tier_name]

    def get_tier_races(self):
        """Get total races per tier"""
        return self.config['seasons']['races_per_tier']

    # ------------------------------------------------------------------
    # Race generation
    # ------------------------------------------------------------------

    def generate_race(self, tier_info, race_num, team_name, car):
        """Generate next race configuration"""
        tracks = tier_info['tracks']
        track = tracks[(race_num - 1) % len(tracks)]

        ai_difficulty = self._calculate_ai_difficulty(team_name, tier_info)
        opponents = self._generate_opponent_field(tier_info, race_num)

        weather = self._pick_weather(tier_info['race_format'], track)
        return {
            'race_num':         race_num,
            'track':            track,
            'car':              car,
            'team':             team_name,
            'ai_difficulty':    ai_difficulty,
            'opponents':        opponents,
            'laps':             tier_info['race_format'].get('laps', 20),
            'time_limit':       tier_info['race_format'].get('time_limit_minutes', 45),
            'practice_minutes': tier_info['race_format'].get('practice_minutes', 10),
            'quali_minutes':    tier_info['race_format'].get('quali_minutes', 10),
            'weather':          weather,
        }

    # Tracks that have wet weather support in vanilla AC
    WET_TRACKS = {
        'spa', 'monza', 'mugello', 'imola',
        'ks_silverstone', 'ks_brands_hatch',
        'ks_red_bull_ring', 'ks_vallelunga',
    }

    def _pick_weather(self, race_format, track):
        """Pick a weather preset using weighted random from weather_pool.
        Falls back to 7_heavy_clouds if wet is selected on an unsupported track.
        """
        pool = race_format.get('weather_pool', [['3_clear', 100]])
        presets  = [p[0] for p in pool]
        weights  = [p[1] for p in pool]
        chosen   = random.choices(presets, weights=weights, k=1)[0]

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

    def _generate_opponent_field(self, tier_info, race_num):
        opponents = []
        for i, team in enumerate(tier_info['teams']):
            perf = team.get('performance', 0) + random.uniform(-0.5, 0.5)
            opponents.append({
                'number':      i + 1,
                'team':        team['name'],
                'car':         team['car'],
                'tier':        team.get('tier', 'customer'),
                'performance': perf,
            })
        return opponents

    # ------------------------------------------------------------------
    # Standings — deterministic AI, real player points
    # ------------------------------------------------------------------

    def _get_driver_name(self, global_slot, season):
        """Return a globally unique driver name for the given slot and season.
        Uses a single season-seeded shuffle of the full name pool so that each
        slot index maps to a distinct name across all tiers simultaneously."""
        seed = int(hashlib.md5(
            f"global_drivers|{season}".encode()
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

    def generate_standings(self, tier_info, career_data, tier_key=None):
        """Build driver championship standings.

        MX5 Cup is a single-driver series (1 entry per team).
        GT4 / GT3 / WEC have 2 championship drivers per team.
        Names are globally unique across all 4 tiers (season-seeded global shuffle).
        """
        races_done  = career_data.get('races_completed', 0)
        player_pts  = career_data.get('points', 0)
        player_team = career_data.get('team')
        season      = career_data.get('season', 1)
        tier_index  = career_data.get('tier', 0)
        team_count  = len(tier_info['teams'])

        if tier_key is None:
            tier_key = self.tiers[tier_index]

        dpt    = self.DRIVERS_PER_TEAM.get(tier_key, 1)   # drivers per team
        offset = self.TIER_SLOT_OFFSET.get(tier_key, 0)   # global slot start

        entries = []
        for i, team in enumerate(tier_info['teams']):
            is_player_team = (team['name'] == player_team)
            slot1 = offset + i * dpt

            if is_player_team:
                pts1  = player_pts
                name1 = career_data.get('driver_name') or 'Player'
            else:
                pts1  = self._calc_ai_points(team, season, tier_index, races_done, team_count)
                name1 = self._get_driver_name(slot1, season)

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
                })
            else:
                # Two drivers per team (GT4 / GT3 / WEC)
                slot2 = slot1 + 1
                name2 = self._get_driver_name(slot2, season)

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
                })

        entries.sort(key=lambda x: x['points'], reverse=True)
        leader = entries[0]['points'] if entries else 0
        for i, s in enumerate(entries):
            s['position'] = i + 1
            s['gap']      = leader - s['points']

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
        Player appears only in their own tier; other tiers show pure AI."""
        result      = {}
        player_tier = career_data.get('tier', 0)
        for idx, tk in enumerate(self.tiers):
            tier_info = self.config['tiers'][tk]
            if idx == player_tier:
                sim = career_data
            else:
                sim = {
                    'tier':            idx,
                    'season':          career_data.get('season', 1),
                    'team':            None,
                    'races_completed': career_data.get('races_completed', 0),
                    'points':          0,
                    'driver_name':     '',
                }
            drivers = self.generate_standings(tier_info, sim, tier_key=tk)
            teams   = self.generate_team_standings_from_drivers(drivers)
            result[tk] = {'drivers': drivers, 'teams': teams}
        return result

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
        # Career complete
        if next_tier >= len(self.tiers):
            return [{'message': 'Congratulations! Career complete!', 'complete': True}]

        degradation_risk = (player_position >= team_count - 2)

        if degradation_risk:
            offers = []
            current_tier_info = config['tiers'][self.tiers[current_tier]]

            # Worst customer seat in current tier (same level)
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
                    'degradation_risk': True,
                    'description':      (
                        f"Your season results were poor. "
                        f"{team['name']} offers you a chance to stay in "
                        f"{self.tier_names[self.tiers[current_tier]]}."
                    ),
                })

            # Offer from lower tier (if not already in the bottom tier)
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
        """Return path to AC's config folder in Documents (where AC actually reads cfg)."""
        docs = os.path.join(os.path.expanduser("~"), "Documents", "Assetto Corsa", "cfg")
        return docs

    def launch_ac_race(self, race_config, config, mode='race_only'):
        """Launch Assetto Corsa with race configuration.
        mode: 'race_only' (default) or 'full_weekend' (practice + quali + race)
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
        self._write_race_config(race_cfg_path, race_config, ac_path, mode=mode)

        # 2. Patch launcher.ini in Documents so AC starts in race mode
        launcher_path = os.path.join(docs_cfg, 'launcher.ini')
        self._patch_launcher_ini(launcher_path, race_config)

        # 3. Launch acs.exe from its own directory
        ac_exe = os.path.join(ac_path, 'acs.exe')
        try:
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

    def _write_race_config(self, config_path, race_data, ac_path='', mode='race_only'):
        """Write AC race.ini in the format AC expects (Documents/Assetto Corsa/cfg/race.ini).
        mode: 'race_only' → single race session; 'full_weekend' → practice + quali + race.
        """
        driver           = race_data.get('driver_name', 'Player')
        car              = race_data['car']
        laps             = race_data['laps']
        ai_lvl           = int(race_data['ai_difficulty'])
        opponents        = race_data.get('opponents', [])
        practice_minutes = race_data.get('practice_minutes', 10)
        quali_minutes    = race_data.get('quali_minutes', 10)
        weather          = race_data.get('weather', '3_clear')

        # Limit to 19 AI cars (20 total including player)
        ai_cars = opponents[:19]
        total_cars = len(ai_cars) + 1  # +1 for player

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
            "",
        ]

        # [DRIVE] — player config
        lines += [
            "[DRIVE]",
            f"MODEL={car}",
            f"SKIN={skin}",
            f"MODEL_CONFIG=",
            f"AI_LEVEL={ai_lvl}",
            f"AI_AGGRESSION=0",
            f"SETUP=",
            f"FIXED_SETUP=0",
            f"VIRTUAL_MIRROR=0",
            f"DRIVER_NAME={driver}",
            f"NATIONALITY=",
            "",
        ]

        # Sessions — race only or full weekend (practice + qualifying + race)
        if mode == 'full_weekend':
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
                f"LAPS={laps}",
                "TYPE=3",
                "SPAWN_SET=START",
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

        # [CAR_0] — player car
        lines += [
            "[CAR_0]",
            f"MODEL={car}",
            f"SKIN={skin}",
            f"MODEL_CONFIG=",
            f"DRIVER_NAME={driver}",
            f"NATIONALITY=",
            f"AI_LEVEL=",
            f"AI_AGGRESSION=0",
            f"SETUP=",
            f"BALLAST=0",
            f"RESTRICTOR=0",
            "",
        ]

        # [CAR_N] — AI cars (use class DRIVER_NAMES for consistency with championship display)
        nations = [
            "ITA", "GBR", "FRA", "GER", "ESP", "USA", "ITA", "CHN",
            "GBR", "IND", "SWE", "MAR", "JPN", "RUS", "ITA", "USA",
            "CRO", "FRA", "IRL", "KEN", "BRA", "NLD", "SWE", "FRA",
            "GER", "JPN", "IRL", "RUS", "CHN", "TUR",
        ]

        for i, opp in enumerate(ai_cars, start=1):
            opp_car  = opp.get('car', car)
            opp_skin = self._get_car_skin(opp_car, ac_path, index=i) if ac_path else ''
            name     = self.DRIVER_NAMES[(i - 1) % len(self.DRIVER_NAMES)]
            nation   = nations[(i - 1) % len(nations)]
            lines += [
                f"[CAR_{i}]",
                f"MODEL={opp_car}",
                f"SKIN={opp_skin}",
                f"MODEL_CONFIG=",
                f"DRIVER_NAME={name}",
                f"NATION_CODE={nation}",
                f"AI_LEVEL={ai_lvl}",
                f"AI_AGGRESSION=0",
                f"SETUP=",
                f"BALLAST=0",
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
