"""
Processors Module - Statistical Calculations

Handles:
- Z-score calculation per position group
- Multi-period z-scores (7-day, 14-day, 30-day, season)
  NOTE: Season z-score is the primary ranking signal.
        Short-window z-scores add context but are noisier early in the season.
- Trend detection (placeholder for Phase 5 when historical data accumulates)
- Data validation and normalization
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import H2H_CATEGORIES


# ---------------------------------------------------------------------------
# Core z-score math
# ---------------------------------------------------------------------------

def _calculate_z_score(
    value: float, mean: float, std_dev: float, invert: bool = False
) -> float:
    """
    Z-score = (value - mean) / std_dev.
    Inverted for lower-is-better stats (ERA, WHIP).
    Returns 0.0 if std_dev == 0 or value is None.
    """
    if std_dev == 0 or value is None:
        return 0.0
    z = (value - mean) / std_dev
    return round(-z if invert else z, 2)


# ---------------------------------------------------------------------------
# Single-period z-score calculation
# ---------------------------------------------------------------------------

def calculate_z_scores(players_data: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    Calculate z-scores for all players across all H2H categories.

    Groups players by position, computes mean/std per stat within each group,
    then scores each player relative to their positional peers.

    Args:
        players_data: List of player stat dicts (from MLB Stats API)

    Returns:
        (z_scored_players, position_stats)
        Each player dict has z_<cat> keys and a z_season composite.
        z_7day / z_14day / z_30day are set to None here — filled later
        by calculate_multi_period_zscores().
    """
    z_scored_players: List[Dict] = []
    position_stats: Dict = {}

    # Group by position
    position_groups: Dict[str, List[Dict]] = {}
    for player in players_data:
        pos = player.get('position', 'UNKNOWN')
        position_groups.setdefault(pos, []).append(player)

    for position, pos_players in position_groups.items():
        is_pitcher = position.upper() in ('P', 'SP', 'RP')
        categories = H2H_CATEGORIES['pitchers'] if is_pitcher else H2H_CATEGORIES['hitters']

        # Compute mean + std per category within this position group
        pos_means: Dict[str, float] = {}
        pos_stds: Dict[str, float] = {}

        for cat in categories:
            stat_key = cat['stat_key']
            values = [
                float(p[stat_key])
                for p in pos_players
                if p.get(stat_key) is not None and p[stat_key] > 0
            ]
            if values:
                pos_means[stat_key] = np.mean(values)
                pos_stds[stat_key] = np.std(values)
            else:
                pos_means[stat_key] = 0.0
                pos_stds[stat_key] = 1.0

        # Score each player
        for player in pos_players:
            z_data: Dict = {
                'player_id': player.get('player_id'),
                'name': player.get('name'),
                'position': position,
                'mlb_team': player.get('mlb_team'),
                'is_pitcher': is_pitcher,
            }

            z_scores: List[float] = []
            for cat in categories:
                stat_key = cat['stat_key']
                stat_name = cat['name']
                val = player.get(stat_key)
                z = _calculate_z_score(
                    val,
                    pos_means[stat_key],
                    pos_stds[stat_key],
                    invert=not cat['higher_is_better'],
                )
                z_data[f"z_{stat_name.lower()}"] = z
                z_scores.append(z)

            z_data['z_season'] = round(np.mean(z_scores), 2) if z_scores else 0.0

            # Multi-period fields — set to None, filled by calculate_multi_period_zscores
            z_data['z_7day'] = None
            z_data['z_14day'] = None
            z_data['z_30day'] = None

            z_scored_players.append(z_data)

        position_stats[position] = {
            'count': len(pos_players),
            'means': pos_means,
            'stds': pos_stds,
        }

    return z_scored_players, position_stats


# ---------------------------------------------------------------------------
# Multi-period z-scores
# ---------------------------------------------------------------------------

def calculate_multi_period_zscores(
    season_stats: Dict,
    stats_7day: Dict,
    stats_14day: Dict,
    stats_30day: Dict,
) -> Tuple[List[Dict], Dict]:
    """
    Calculate z-scores for all four time windows and merge onto season players.

    NOTE: Season z-score (z_season) is the PRIMARY ranking signal.
    Short-window z-scores (z_7day, z_14day, z_30day) add confidence context:
      - Early in the season, they are noisy and should be weighted lightly.
      - As the season progresses, recent-window z-scores become more meaningful.

    For each period:
      - Z-scores are computed within that period's player pool (fair comparison).
      - Players who didn't play in a window get None for that window's z-score.

    Args:
        season_stats:  {player_id: stats} from fetch_mlb_player_stats()
        stats_7day:    {player_id: stats} from fetch_mlb_stats_range(7 days)
        stats_14day:   {player_id: stats} from fetch_mlb_stats_range(14 days)
        stats_30day:   {player_id: stats} from fetch_mlb_stats_range(30 days)

    Returns:
        (z_scored_players, position_stats) — same shape as calculate_z_scores()
        Each player has z_season, z_7day, z_14day, z_30day.
    """
    def _to_valid_list(stats_dict: Dict) -> List[Dict]:
        return [p for p in stats_dict.values() if p.get('name') and p.get('position')]

    def _name_z_lookup(z_list: List[Dict]) -> Dict[str, float]:
        """Map normalised name → z_season composite for a period's z-score list."""
        return {
            p.get('name', '').lower().strip(): p.get('z_season')
            for p in z_list
        }

    print("  Season z-scores...")
    season_players = _to_valid_list(season_stats)
    z_season_list, position_stats = calculate_z_scores(season_players)

    print("  7-day z-scores...", end=" ", flush=True)
    if stats_7day:
        z7_list, _ = calculate_z_scores(_to_valid_list(stats_7day))
        print(f"({len(z7_list)} players)")
    else:
        z7_list = []
        print("(no data)")

    print("  14-day z-scores...", end=" ", flush=True)
    if stats_14day:
        z14_list, _ = calculate_z_scores(_to_valid_list(stats_14day))
        print(f"({len(z14_list)} players)")
    else:
        z14_list = []
        print("(no data)")

    print("  30-day z-scores...", end=" ", flush=True)
    if stats_30day:
        z30_list, _ = calculate_z_scores(_to_valid_list(stats_30day))
        print(f"({len(z30_list)} players)")
    else:
        z30_list = []
        print("(no data)")

    z7_lookup = _name_z_lookup(z7_list)
    z14_lookup = _name_z_lookup(z14_list)
    z30_lookup = _name_z_lookup(z30_list)

    # Merge period composites onto each season player
    for player in z_season_list:
        key = player.get('name', '').lower().strip()
        player['z_7day'] = z7_lookup.get(key)    # None if not in 7-day pool
        player['z_14day'] = z14_lookup.get(key)
        player['z_30day'] = z30_lookup.get(key)

    return z_season_list, position_stats


# ---------------------------------------------------------------------------
# Trend detection (placeholder — meaningful after Phase 5 data accumulates)
# ---------------------------------------------------------------------------

def calculate_trends(players: List[Dict]) -> List[Dict]:
    """
    Detect whether a player is trending up, down, or flat.

    Uses z_7day vs z_season as a momentum signal when both are available.
    Otherwise marks as FLAT until more historical data accumulates.

    Args:
        players: List of players with z_season, z_7day

    Returns:
        Same list with 'trend_direction' and 'momentum' added.
    """
    for player in players:
        z_s = player.get('z_season')
        z_7 = player.get('z_7day')

        if z_s is not None and z_7 is not None:
            momentum = round(z_7 - z_s, 3)
            if momentum > 0.3:
                direction = 'UP'
            elif momentum < -0.3:
                direction = 'DOWN'
            else:
                direction = 'FLAT'
        else:
            momentum = 0.0
            direction = 'FLAT'

        player['trend_direction'] = direction
        player['momentum'] = momentum

    return players


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_player_data(player: Dict) -> bool:
    """Return True if player dict has required fields and sane stat values."""
    if not player.get('name') or not player.get('position'):
        return False

    stat_fields = [
        'games_played', 'at_bats', 'hits', 'home_runs', 'rbis',
        'runs', 'stolen_bases', 'walks', 'strikeouts',
        'innings_pitched', 'earned_runs', 'wins', 'losses',
        'saves', 'holds', 'quality_starts',
    ]
    for field in stat_fields:
        val = player.get(field)
        if val is not None and (not isinstance(val, (int, float)) or val < 0):
            return False

    return True


def normalize_stats(stats_dict: Dict) -> Dict:
    """Convert None to 0 and enforce correct numeric types for DB storage."""
    int_fields = [
        'games_played', 'at_bats', 'hits', 'home_runs', 'rbis',
        'runs', 'stolen_bases', 'walks', 'strikeouts', 'earned_runs',
        'wins', 'losses', 'saves', 'holds', 'quality_starts',
    ]
    float_fields = ['avg', 'obp', 'slg', 'ops', 'innings_pitched', 'era', 'whip']
    normalized: Dict = {}
    for f in int_fields:
        v = stats_dict.get(f)
        normalized[f] = int(v) if v is not None else 0
    for f in float_fields:
        v = stats_dict.get(f)
        normalized[f] = float(v) if v is not None else 0.0
    return normalized
