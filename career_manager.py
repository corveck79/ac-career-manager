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

    def generate_standings(self, tier_info, career_data):
        """
        Build championship standings.
        AI points are deterministic per race so they are consistent
        between page loads. Player points come from actual results.
        """
        races_done   = career_data.get('races_completed', 0)
        player_pts   = career_data.get('points', 0)
        player_team  = career_data.get('team')
        season       = career_data.get('season', 1)
        tier_index   = career_data.get('tier', 0)
        team_count   = len(tier_info['teams'])

        standings = []
        for team in tier_info['teams']:
            is_player = (team['name'] == player_team)

            if is_player:
                pts = player_pts
            else:
                pts = self._calc_ai_points(
                    team, season, tier_index, races_done, team_count
                )

            standings.append({
                'team':       team['name'],
                'car':        team['car'],
                'points':     pts,
                'races':      races_done,
                'is_player':  is_player,
                'tier_level': team.get('tier', 'customer'),
            })

        # Sort descending
        standings.sort(key=lambda x: x['points'], reverse=True)

        # Add position + gap to leader
        leader = standings[0]['points'] if standings else 0
        for i, s in enumerate(standings):
            s['position'] = i + 1
            s['gap']      = leader - s['points']

        return standings

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

    def generate_contract_offers(self, player_position, next_tier, config):
        """Generate contract offers based on championship finish"""
        if next_tier >= len(self.tiers):
            return [{'message': 'Congratulations! Career complete!', 'complete': True}]

        tier_info = config['tiers'][self.tiers[next_tier]]

        if player_position == 1:
            offer_count  = config.get('contracts', {}).get('champion_offers', 4)
            tier_filter  = ['factory', 'semi']
        elif player_position <= 5:
            offer_count  = config.get('contracts', {}).get('top5_offers', 3)
            tier_filter  = ['semi', 'customer']
        elif player_position <= 10:
            offer_count  = config.get('contracts', {}).get('top10_offers', 2)
            tier_filter  = ['customer']
        else:
            offer_count  = 1
            tier_filter  = ['customer']

        available = [
            t for t in tier_info['teams']
            if t.get('tier', 'customer') in tier_filter
        ]

        selected = random.sample(available, min(offer_count, len(available)))

        offers = []
        for i, team in enumerate(selected):
            offers.append({
                'id':          f"contract_{i}_{int(datetime.now().timestamp())}",
                'team_name':   team['name'],
                'car':         team['car'],
                'tier_name':   self.tier_names[self.tiers[next_tier]],
                'tier_level':  team.get('tier', 'customer'),
                'description': (
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

    def _get_car_skin(self, car, ac_path):
        """Return first available skin for a car, or empty string."""
        skins_dir = os.path.join(ac_path, 'content', 'cars', car, 'skins')
        try:
            skins = sorted(os.listdir(skins_dir))
            return skins[0] if skins else ''
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

        # Find first skin for this car
        skin = self._get_car_skin(car, ac_path) if ac_path else ''

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

        # [CAR_N] — AI cars
        ai_names = [
            "Marco Rossi", "James Hunt", "Pierre Dupont", "Hans Mueller",
            "Carlos Rivera", "Tom Bradley", "Luca Ferrari", "Alex Chen",
            "David Williams", "Raj Patel", "Sven Johansson", "Omar Hassan",
            "Kenji Tanaka", "Igor Petrov", "Fabio Romano", "Ethan Clark",
            "Nina Kovac", "Lucas Petit", "Aiden Burke", "Zara Osman",
        ]
        nations = ["ITA", "GBR", "FRA", "GER", "ESP", "USA", "ITA", "CHN",
                   "GBR", "IND", "SWE", "MAR", "JPN", "RUS", "ITA", "USA",
                   "CRO", "FRA", "IRL", "KEN"]

        for i, opp in enumerate(ai_cars, start=1):
            opp_car  = opp.get('car', car)
            opp_skin = self._get_car_skin(opp_car, ac_path) if ac_path else ''
            name     = ai_names[i - 1] if i - 1 < len(ai_names) else f"Driver {i}"
            nation   = nations[i - 1] if i - 1 < len(nations) else "INT"
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
