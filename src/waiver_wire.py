"""
Phase 2: Waiver Wire Analysis

- Links ESPN free agents to MLB z-score data
- Ranks by z_season (primary) with z_7day/z_14day/z_30day as context
- Flags injured players and two-start pitchers
- Identifies your team's weak H2H categories
- All outfield positions (CF/LF/RF) treated as OF
"""

from typing import Dict, List, Optional, Set
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import H2H_CATEGORIES, INJURED_STATUSES, OF_POSITIONS


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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def link_players_to_zscores(
    players: List[Dict],
    z_scored_players: List[Dict],
) -> List[Dict]:
    """
    Enrich a player list with z-score data by name matching.
    Players with no match get no_stats=True and z_season=None.
    """
    lookup = _build_zscore_lookup(z_scored_players)
    enriched = []
    for player in players:
        key = _norm(player.get('name', ''))
        z_data = lookup.get(key)
        if z_data:
            enriched.append({**player, **z_data, 'no_stats': False})
        else:
            enriched.append({**player, 'z_season': None, 'no_stats': True})
    return enriched


def analyze_my_team(
    my_roster: List[Dict],
    z_scored_players: List[Dict],
) -> Dict[str, Dict]:
    """
    Calculate my team's average z-score per H2H category.

    Returns dict keyed by category name, each with:
        display, type, my_avg, strength (STRONG/AVERAGE/WEAK), rank
    """
    lookup = _build_zscore_lookup(z_scored_players)
    all_cats = H2H_CATEGORIES['hitters'] + H2H_CATEGORIES['pitchers']
    cat_values: Dict[str, List[float]] = {cat['name']: [] for cat in all_cats}

    for player in my_roster:
        key = _norm(player.get('name', ''))
        z_data = lookup.get(key)
        if not z_data:
            continue
        cats = H2H_CATEGORIES['pitchers'] if z_data.get('is_pitcher') else H2H_CATEGORIES['hitters']
        for cat in cats:
            val = z_data.get(f"z_{cat['name'].lower()}")
            if val is not None:
                cat_values[cat['name']].append(float(val))

    analysis: Dict[str, Dict] = {}
    for cat in all_cats:
        name = cat['name']
        vals = cat_values[name]
        avg = round(sum(vals) / len(vals), 3) if vals else 0.0
        analysis[name] = {
            'display': cat['display'],
            'type': 'hitting' if cat in H2H_CATEGORIES['hitters'] else 'pitching',
            'my_avg': avg,
            'higher_is_better': cat['higher_is_better'],
        }

    # Rank by effective strength (simple sort on avg z)
    sorted_cats = sorted(analysis.items(), key=lambda x: x[1]['my_avg'])
    for rank, (cat_name, data) in enumerate(sorted_cats, start=1):
        data['rank'] = rank
        n = len(sorted_cats)
        if rank <= 2:
            data['strength'] = 'WEAK'
        elif rank >= n - 1:
            data['strength'] = 'STRONG'
        else:
            data['strength'] = 'AVERAGE'

    return analysis


def rank_free_agents(
    free_agents: List[Dict],
    z_scored_players: List[Dict],
    position_filter: Optional[str] = None,
    exclude_injured: bool = True,
) -> List[Dict]:
    """Rank free agents by z_season, optionally filtered by position."""
    enriched = link_players_to_zscores(free_agents, z_scored_players)

    if position_filter:
        pos = position_filter.upper()
        # Treat all OF sub-positions as OF
        if pos == 'OF':
            enriched = [p for p in enriched if p.get('position', '').upper() in OF_POSITIONS]
        else:
            enriched = [p for p in enriched if p.get('position', '').upper() == pos]

    if exclude_injured:
        enriched = [p for p in enriched if p.get('injury_status', 'ACTIVE') not in INJURED_STATUSES]

    def sort_key(p):
        z = p.get('z_season')
        return z if z is not None else float('-inf')

    return sorted(enriched, key=sort_key, reverse=True)


def generate_waiver_report(
    free_agents: List[Dict],
    z_scored_players: List[Dict],
    team_analysis: Dict[str, Dict],
    two_start_pitchers: Optional[Dict[str, int]] = None,
    top_n: int = 25,
) -> Dict:
    """
    Generate the full waiver wire report.

    Args:
        free_agents:         from derive_free_agents()
        z_scored_players:    from calculate_multi_period_zscores()
        team_analysis:       from analyze_my_team()
        two_start_pitchers:  {name_lower: start_count} — pitchers with 2 starts this week
        top_n:               how many top overall to return

    Returns:
        top_overall           top N FAs ranked by z_season
        by_position           top 10 per position (OF consolidates CF/LF/RF)
        weak_category_targets top 10 FAs per weak category
        team_analysis         category strength summary
        weak_categories       list of weak category names
        two_start_free_agents available pitchers with 2 starts this week
    """
    two_starters: Set[str] = set(two_start_pitchers.keys()) if two_start_pitchers else set()

    enriched = link_players_to_zscores(free_agents, z_scored_players)

    # Flag two-starters and normalise position
    for p in enriched:
        key = _norm(p.get('name', ''))
        p['is_two_start'] = key in two_starters
        if p.get('is_two_start') and two_start_pitchers:
            p['two_start_count'] = two_start_pitchers.get(key, 2)
        # Normalise OF sub-positions
        if p.get('position', '') in OF_POSITIONS:
            p['position'] = 'OF'

    with_stats = [
        p for p in enriched
        if not p.get('no_stats') and p.get('z_season') is not None
    ]

    # Top overall (healthy only for default view)
    healthy = [p for p in with_stats if p.get('injury_status', 'ACTIVE') not in INJURED_STATUSES]
    top_overall = sorted(healthy, key=lambda p: p.get('z_season', float('-inf')), reverse=True)[:top_n]

    # By position (all OF positions → 'OF')
    positions = ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP', 'RP', 'P', 'DH']
    by_position: Dict[str, List[Dict]] = {}
    for pos in positions:
        if pos == 'OF':
            pool = [p for p in healthy if p.get('position', '').upper() in OF_POSITIONS or p.get('position') == 'OF']
        else:
            pool = [p for p in healthy if p.get('position', '').upper() == pos]
        by_position[pos] = sorted(pool, key=lambda p: p.get('z_season', float('-inf')), reverse=True)[:10]

    # Two-start free agent pitchers (big priority for waiver adds)
    two_start_fas = sorted(
        [p for p in with_stats if p.get('is_two_start')],
        key=lambda p: p.get('z_season', float('-inf')),
        reverse=True,
    )

    # Top FAs per weak category
    weak_cats = [name for name, data in team_analysis.items() if data.get('strength') == 'WEAK']
    weak_cat_targets: Dict[str, List[Dict]] = {}
    for cat in weak_cats:
        z_key = f"z_{cat.lower()}"
        pool = [p for p in healthy if p.get(z_key) is not None]
        weak_cat_targets[cat] = sorted(
            pool, key=lambda p: p.get(z_key, float('-inf')), reverse=True
        )[:10]

    return {
        'top_overall': top_overall,
        'by_position': by_position,
        'weak_category_targets': weak_cat_targets,
        'team_analysis': team_analysis,
        'weak_categories': weak_cats,
        'two_start_free_agents': two_start_fas,
        'total_free_agents': len(free_agents),
        'free_agents_with_stats': len(with_stats),
    }
