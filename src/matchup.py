"""
Phase 3: Matchup Analysis & Lineup Recommendations

- Category-by-category projected matchup vs opponent (z-score based)
- Actual in-week stats vs projected (ESPN scoreByStat data)
- Start/sit recommendations with injury filtering and two-start pitcher boost
"""

from typing import Dict, List, Optional, Set
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import H2H_CATEGORIES, INJURED_STATUSES, QUESTIONABLE_STATUSES


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    return name.lower().strip()


def _build_zscore_lookup(z_scored_players: List[Dict]) -> Dict[str, Dict]:
    lookup: Dict[str, Dict] = {}
    for player in z_scored_players:
        key = _norm(player.get('name', ''))
        if key:
            lookup[key] = player
    return lookup


def _team_category_averages(players_with_z: List[Dict]) -> Dict[str, Optional[float]]:
    """Average z-score per H2H category for a group of players."""
    all_cats = H2H_CATEGORIES['hitters'] + H2H_CATEGORIES['pitchers']
    totals: Dict[str, List[float]] = {cat['name']: [] for cat in all_cats}

    for player in players_with_z:
        if player.get('no_stats') or player.get('z_season') is None:
            continue
        cats = H2H_CATEGORIES['pitchers'] if player.get('is_pitcher') else H2H_CATEGORIES['hitters']
        for cat in cats:
            z_key = f"z_{cat['name'].lower()}"
            val = player.get(z_key)
            if val is not None:
                totals[cat['name']].append(float(val))

    return {
        cat_name: round(sum(vals) / len(vals), 3) if vals else None
        for cat_name, vals in totals.items()
    }


def _enrich_roster(roster: List[Dict], lookup: Dict[str, Dict]) -> List[Dict]:
    """Merge z-score data onto roster player dicts by name."""
    result = []
    for player in roster:
        key = _norm(player.get('name', ''))
        z_data = lookup.get(key)
        if z_data:
            result.append({**player, **z_data, 'no_stats': False})
        else:
            result.append({**player, 'z_season': None, 'no_stats': True})
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_matchup(
    my_roster: List[Dict],
    opponent_roster: List[Dict],
    z_scored_players: List[Dict],
    opponent_team_name: str = "Opponent",
) -> Dict:
    """
    Compare my team vs opponent across all 10 H2H categories.

    Returns:
        my_avgs             {category: avg_z} for my team
        opp_avgs            {category: avg_z} for opponent
        category_edges      list of per-category dicts with projected winner
        projected_wins/losses/ties
        opponent_name
    """
    lookup = _build_zscore_lookup(z_scored_players)
    my_players = _enrich_roster(my_roster, lookup)
    opp_players = _enrich_roster(opponent_roster, lookup)

    my_avgs = _team_category_averages(my_players)
    opp_avgs = _team_category_averages(opp_players)

    all_cats = H2H_CATEGORIES['hitters'] + H2H_CATEGORIES['pitchers']
    category_edges = []
    wins = losses = ties = 0
    TIE_THRESHOLD = 0.10

    for cat in all_cats:
        name = cat['name']
        my_z = my_avgs.get(name)
        opp_z = opp_avgs.get(name)

        if my_z is None or opp_z is None:
            winner, edge = 'UNKNOWN', None
        else:
            edge = round(my_z - opp_z, 3)
            if abs(edge) <= TIE_THRESHOLD:
                winner = 'TOSS-UP'; ties += 1
            elif edge > 0:
                winner = 'ME'; wins += 1
            else:
                winner = opponent_team_name; losses += 1

        category_edges.append({
            'category': name,
            'display': cat['display'],
            'type': 'hitting' if cat in H2H_CATEGORIES['hitters'] else 'pitching',
            'my_z': my_z,
            'opp_z': opp_z,
            'edge': edge,
            'projected_winner': winner,
            'higher_is_better': cat['higher_is_better'],
        })

    return {
        'my_avgs': my_avgs,
        'opp_avgs': opp_avgs,
        'category_edges': category_edges,
        'projected_wins': wins,
        'projected_losses': losses,
        'projected_ties': ties,
        'opponent_name': opponent_team_name,
        'my_matched_players': sum(1 for p in my_players if not p.get('no_stats')),
        'opp_matched_players': sum(1 for p in opp_players if not p.get('no_stats')),
    }


def analyze_actuals_vs_projected(
    matchup_actuals: Dict,
    category_edges: List[Dict],
) -> List[Dict]:
    """
    Compare what's actually accumulated this week (ESPN scoreByStat)
    against our projected z-score advantage.

    Args:
        matchup_actuals:  {my_actuals: {cat: val}, opp_actuals: {cat: val}}
        category_edges:   from analyze_matchup()

    Returns:
        List of per-category dicts with actual + projected + divergence flag.
        Categories without actual data carry actual=None.

    Note:
        ESPN stat IDs are partially confirmed — rate stats (ERA, WHIP, OBP)
        may be approximate. Count stats (R, HR, SB, K, QS) are reliable.
    """
    if not matchup_actuals:
        return []

    my_actuals = matchup_actuals.get('my_actuals', {})
    opp_actuals = matchup_actuals.get('opp_actuals', {})

    result = []
    for edge in category_edges:
        cat = edge['category']
        # Map category name to our internal stat key
        # H2H category 'K' maps to 'strikeouts', 'HR' to 'home_runs', etc.
        stat_key_map = {
            'R':    'runs',
            'HR':   'home_runs',
            'RBI':  'rbis',
            'SB':   'stolen_bases',
            'OBP':  'obp',
            'K':    'strikeouts',
            'QS':   'quality_starts',
            'ERA':  'era',
            'WHIP': 'whip',
            'SVHD': 'sv_hd',
        }
        sk = stat_key_map.get(cat)

        my_actual = my_actuals.get(sk) if sk else None
        opp_actual = opp_actuals.get(sk) if sk else None

        # Determine actual leader
        if my_actual is not None and opp_actual is not None:
            if edge['higher_is_better']:
                actual_leader = 'ME' if my_actual > opp_actual else ('OPP' if opp_actual > my_actual else 'TIE')
            else:
                actual_leader = 'ME' if my_actual < opp_actual else ('OPP' if opp_actual < my_actual else 'TIE')
        else:
            actual_leader = None

        # Flag divergence: projected WIN but actually losing, or vice versa
        projected_winner = edge.get('projected_winner', 'UNKNOWN')
        diverges = (
            actual_leader is not None
            and projected_winner not in ('UNKNOWN', 'TOSS-UP')
            and actual_leader != 'TIE'
            and (
                (projected_winner == 'ME' and actual_leader == 'OPP')
                or (projected_winner != 'ME' and actual_leader == 'ME')
            )
        )

        result.append({
            'category': cat,
            'display': edge['display'],
            'type': edge['type'],
            'higher_is_better': edge['higher_is_better'],
            'projected_winner': projected_winner,
            'projected_edge': edge.get('edge'),
            'my_actual': my_actual,
            'opp_actual': opp_actual,
            'actual_leader': actual_leader,
            'diverges_from_projection': diverges,
        })

    return result


def recommend_lineup(
    my_roster: List[Dict],
    z_scored_players: List[Dict],
    matchup_edges: Optional[List[Dict]] = None,
    two_start_pitchers: Optional[Dict[str, int]] = None,
    injury_lookup: Optional[Dict[str, str]] = None,
) -> Dict:
    """
    Start/sit recommendations for your roster.

    Rules (in priority order):
      1. Injured / IL players → 'INJURED — DO NOT START'
      2. Questionable players → flagged with warning
      3. Two-start pitchers get a +0.4 z-score boost for lineup sorting
      4. Z-score thresholds:
            >= 1.0  → START
            >= 0.0  → CONSIDER
            >= -0.5 → BORDERLINE
            < -0.5  → BENCH
      5. Borderline/Consider players who help in matchup weak spots → START (matchup need)

    Args:
        my_roster:           list of your ESPN player dicts
        z_scored_players:    full z-score list
        matchup_edges:       from analyze_matchup() — used for matchup-need boost
        two_start_pitchers:  {name_lower: start_count} from fetch_two_start_pitchers()
        injury_lookup:       {name_lower: status} from fetch_espn_league_data()
    """
    lookup = _build_zscore_lookup(z_scored_players)
    two_starters: Set[str] = set(two_start_pitchers.keys()) if two_start_pitchers else set()
    inj_lookup = injury_lookup or {}

    # Categories where we're projected behind — used for matchup-need boost
    weak_cats: List[str] = []
    if matchup_edges:
        weak_cats = [
            e['category'] for e in matchup_edges
            if e.get('projected_winner') not in ('ME', 'UNKNOWN', 'TOSS-UP')
        ]

    hitters: List[Dict] = []
    pitchers: List[Dict] = []

    for player in my_roster:
        name = player.get('name', 'Unknown')
        key = _norm(name)
        z_data = lookup.get(key)

        # ---- Injury check (ESPN roster data takes priority) ----
        # Use ESPN injury status from roster data (more current than MLB API)
        espn_status = inj_lookup.get(key, player.get('injury_status', 'ACTIVE'))
        is_injured = espn_status in INJURED_STATUSES
        is_questionable = espn_status in QUESTIONABLE_STATUSES

        if is_injured:
            entry = {
                'name': name,
                'position': player.get('position', '?'),
                'eligible_positions': player.get('eligible_positions', [player.get('position', '?')]),
                'lineup_slot':        player.get('lineup_slot', 'BE'),
                'is_active_lineup':   player.get('is_active_lineup', False),
                'z_season': None,
                'z_7day': None,
                'z_14day': None,
                'z_30day': None,
                'recommendation': 'INJURED — DO NOT START',
                'injury_status': espn_status,
                'is_two_start': False,
                'notes': f'Status: {espn_status}',
            }
            (pitchers if player.get('is_pitcher') else hitters).append(entry)
            continue

        if not z_data:
            entry = {
                'name': name,
                'position': player.get('position', '?'),
                'eligible_positions': player.get('eligible_positions', [player.get('position', '?')]),
                'lineup_slot':        player.get('lineup_slot', 'BE'),
                'is_active_lineup':   player.get('is_active_lineup', False),
                'z_season': None,
                'z_7day': None,
                'z_14day': None,
                'z_30day': None,
                'recommendation': 'NO DATA',
                'injury_status': espn_status,
                'is_two_start': False,
                'notes': 'No MLB stats found — may not have played yet',
            }
            (pitchers if player.get('is_pitcher') else hitters).append(entry)
            continue

        z_season = z_data.get('z_season', 0.0) or 0.0
        is_pitcher = z_data.get('is_pitcher', False)
        is_two_start = is_pitcher and key in two_starters

        # Two-start pitchers get a sort boost — labelled clearly in output
        effective_z = z_season + (0.4 if is_two_start else 0.0)

        # Base recommendation
        if effective_z >= 1.0:
            rec = 'START'
        elif effective_z >= 0.0:
            rec = 'CONSIDER'
        elif effective_z >= -0.5:
            rec = 'BORDERLINE'
        else:
            rec = 'BENCH'

        # Matchup-need boost for borderline/consider players
        if rec in ('CONSIDER', 'BORDERLINE') and weak_cats:
            for cat in weak_cats:
                z_cat = z_data.get(f"z_{cat.lower()}")
                if z_cat is not None and z_cat > 0.5:
                    rec = 'START (matchup need)'
                    break

        notes_parts = []
        if is_two_start:
            count = two_start_pitchers.get(key, 2)
            notes_parts.append(f'2-start week ({count} starts)')
        if is_questionable:
            notes_parts.append(f'QUESTIONABLE ({espn_status})')

        entry = {
            'name': z_data.get('name', name),
            'position': player.get('position', z_data.get('position', '?')),  # ESPN first
            'eligible_positions': player.get('eligible_positions', []),
            'lineup_slot':        player.get('lineup_slot', 'BE'),
            'is_active_lineup':   player.get('is_active_lineup', False),
            'z_season': z_season,
            'z_7day': z_data.get('z_7day'),
            'z_14day': z_data.get('z_14day'),
            'z_30day': z_data.get('z_30day'),
            'trend_direction': z_data.get('trend_direction', 'FLAT'),
            'recommendation': rec,
            'injury_status': espn_status,
            'is_two_start': is_two_start,
            'notes': ' | '.join(notes_parts),
        }
        (pitchers if is_pitcher else hitters).append(entry)

    # Sort: START first, then by effective z (two-starters already boosted)
    REC_ORDER = {
        'START': 0,
        'START (matchup need)': 1,
        'CONSIDER': 2,
        'BORDERLINE': 3,
        'BENCH': 4,
        'NO DATA': 5,
        'INJURED — DO NOT START': 6,
    }

    def _sort_key(p):
        z = p.get('z_season') or float('-inf')
        two_boost = 0.4 if p.get('is_two_start') else 0.0
        return (REC_ORDER.get(p['recommendation'], 9), -(z + two_boost))

    hitters.sort(key=_sort_key)
    pitchers.sort(key=_sort_key)

    return {
        'hitters': hitters,
        'pitchers': pitchers,
        'start_hitters': [p for p in hitters if 'START' in p['recommendation']],
        'start_pitchers': [p for p in pitchers if 'START' in p['recommendation']],
    }
