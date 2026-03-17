"""
Achievement definitions and unlock logic for AC Career GT Edition.

Achievements are checked after each race (race-based) and after season end
(season-based). Unlocked achievements are stored in career_data['achievements']
as a list of {id, season, race} dicts.
"""

from driver_progress import DRIVER_SKILL_KEYS, compute_progress_deltas

ACHIEVEMENTS = {
    'first_win':      {'name': 'First Blood',     'icon': '🏆', 'desc': 'Win your first race'},
    'hat_trick':      {'name': 'Hat Trick',        'icon': '🎩', 'desc': 'Win 3 races in one season'},
    'rain_king':      {'name': 'Rain King',        'icon': '🌧️', 'desc': 'Win a race in wet conditions'},
    'podium_hat':     {'name': 'Podium Regular',   'icon': '🥉', 'desc': 'Earn 5 podiums in one season'},
    'centurion':      {'name': 'Centurion',        'icon': '💯', 'desc': 'Score 100+ points in a season'},
    'champion':       {'name': 'Champion',         'icon': '🏅', 'desc': 'Win any championship'},
    'double_champ':   {'name': 'Double Champion',  'icon': '✌️', 'desc': 'Win 2 championships'},
    'triple_crown':   {'name': 'Triple Crown',     'icon': '👑', 'desc': 'Win 3 championships'},
    'full_career':    {'name': 'Old Timer',        'icon': '🧓', 'desc': 'Complete 5 seasons'},
    'clean_sweep':    {'name': 'Dominant',         'icon': '⚡', 'desc': 'Win every race in a season'},
}

# Ordered for the achievements grid (roughly hardest to easiest to unlock)
ACHIEVEMENT_ORDER = [
    'first_win', 'rain_king', 'hat_trick', 'podium_hat',
    'centurion', 'champion', 'clean_sweep',
    'double_champ', 'triple_crown', 'full_career',
]


def check_achievements(career_data, context=None):
    """Check all achievements and unlock new ones.

    Returns a list of newly unlocked achievement ids.

    context keys (all optional):
        is_wet (bool):       was the last race in wet conditions?
        position (int):      player finishing position in last race (finish_race only)
        is_season_end (bool): True when called from _do_end_season
    """
    if context is None:
        context = {}

    unlocked_ids = {a['id'] for a in career_data.get('achievements', [])}
    newly_unlocked = []
    season = career_data.get('season', 1)
    race_num = career_data.get('races_completed', 0)

    race_results = career_data.get('race_results', [])
    player_history = career_data.get('player_history', [])

    wins_this_season = sum(1 for r in race_results if r.get('position') == 1)
    podiums_this_season = sum(1 for r in race_results if r.get('position', 99) <= 3)
    championship_wins = sum(1 for ph in player_history if ph.get('pos') == 1)
    seasons_completed = len(player_history)

    def _unlock(aid):
        if aid not in unlocked_ids:
            unlocked_ids.add(aid)
            newly_unlocked.append(aid)
            career_data.setdefault('achievements', []).append(
                {'id': aid, 'season': season, 'race': race_num}
            )

    # ── Race-based achievements ─────────────────────────────────────────────
    position = context.get('position')

    if wins_this_season >= 1:
        _unlock('first_win')

    if wins_this_season >= 3:
        _unlock('hat_trick')

    if podiums_this_season >= 5:
        _unlock('podium_hat')

    if context.get('is_wet') and position == 1:
        _unlock('rain_king')

    # ── Season-end achievements ─────────────────────────────────────────────
    if context.get('is_season_end'):
        season_points = career_data.get('points', 0)
        if season_points >= 100:
            _unlock('centurion')

        if championship_wins >= 1:
            _unlock('champion')
        if championship_wins >= 2:
            _unlock('double_champ')
        if championship_wins >= 3:
            _unlock('triple_crown')

        if seasons_completed >= 5:
            _unlock('full_career')

        # Clean sweep: won every race this season
        races_this_season = len(race_results)
        if races_this_season > 0 and wins_this_season == races_this_season:
            _unlock('clean_sweep')

    return newly_unlocked
