"""
Phase 4: Trade Analysis

Two modes:
  1. evaluate_trade()   - Given players I give vs receive, tell me if it's good.
  2. find_trade_targets() - Scan all other rosters for players worth targeting.
"""

from typing import Dict, List, Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import H2H_CATEGORIES, TRADE_RULES


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


def _team_category_zscores(
    player_names: List[str],
    lookup: Dict[str, Dict],
) -> Dict[str, float]:
    """
    Compute average z-score per H2H category for a list of player names.
    Returns {category_name: avg_z}.
    """
    all_cats = H2H_CATEGORIES['hitters'] + H2H_CATEGORIES['pitchers']
    totals: Dict[str, List[float]] = {cat['name']: [] for cat in all_cats}

    for name in player_names:
        z_data = lookup.get(_norm(name))
        if not z_data:
            continue
        cats = H2H_CATEGORIES['pitchers'] if z_data.get('is_pitcher') else H2H_CATEGORIES['hitters']
        for cat in cats:
            z_key = f"z_{cat['name'].lower()}"
            val = z_data.get(z_key)
            if val is not None:
                totals[cat['name']].append(float(val))

    return {
        cat_name: round(sum(vals) / len(vals), 3) if vals else 0.0
        for cat_name, vals in totals.items()
    }


def _delta_summary(before: Dict[str, float], after: Dict[str, float]) -> List[Dict]:
    """Compute per-category change (after - before)."""
    all_cats = H2H_CATEGORIES['hitters'] + H2H_CATEGORIES['pitchers']
    deltas = []
    for cat in all_cats:
        name = cat['name']
        b = before.get(name, 0.0)
        a = after.get(name, 0.0)
        delta = round(a - b, 3)
        deltas.append({
            'category': name,
            'display': cat['display'],
            'type': 'hitting' if cat in H2H_CATEGORIES['hitters'] else 'pitching',
            'before': b,
            'after': a,
            'delta': delta,
            'direction': 'UP' if delta > 0.05 else ('DOWN' if delta < -0.05 else 'FLAT'),
            'higher_is_better': cat['higher_is_better'],
        })
    return deltas


def _overall_verdict(net_z_change: float, category_deltas: List[Dict]) -> str:
    """
    Return a simple verdict string based on net z-score change.
    """
    threshold = TRADE_RULES.get('value_threshold', 1.05) - 1.0  # e.g. 0.05

    # Count categories gained vs lost
    improved = sum(1 for d in category_deltas if d['direction'] == 'UP')
    hurt = sum(1 for d in category_deltas if d['direction'] == 'DOWN')

    if net_z_change > threshold and improved >= hurt:
        return 'ACCEPT'
    elif net_z_change < -threshold or hurt > improved + 2:
        return 'DECLINE'
    else:
        return 'NEUTRAL — evaluate based on your priorities'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_trade(
    giving_names: List[str],
    receiving_names: List[str],
    my_roster: List[Dict],
    z_scored_players: List[Dict],
) -> Dict:
    """
    Evaluate a trade proposal.

    Args:
        giving_names:    list of player names I'm sending away
        receiving_names: list of player names I'm receiving
        my_roster:       current roster player dicts
        z_scored_players: full z-score list

    Returns dict with:
        giving         - enriched player dicts for players I give
        receiving      - enriched player dicts for players I receive
        my_z_before    - my team avg z by category before trade
        my_z_after     - my team avg z by category after trade
        category_deltas - per-category impact list
        net_z_change   - overall z-score change (positive = I got better)
        verdict        - 'ACCEPT', 'DECLINE', or 'NEUTRAL'
        notes          - list of advisory strings
    """
    lookup = _build_zscore_lookup(z_scored_players)

    my_roster_names = [p.get('name', '') for p in my_roster]

    # Build my roster after trade
    roster_after = [n for n in my_roster_names if _norm(n) not in [_norm(g) for g in giving_names]]
    roster_after.extend(receiving_names)

    # Category averages before and after
    z_before = _team_category_zscores(my_roster_names, lookup)
    z_after = _team_category_zscores(roster_after, lookup)

    # Net overall z change (simple sum of all category changes)
    net = round(sum(z_after.values()) - sum(z_before.values()), 3)

    deltas = _delta_summary(z_before, z_after)
    verdict = _overall_verdict(net, deltas)

    # Enrich giving/receiving with z-score data
    def enrich(names):
        result = []
        for name in names:
            z = lookup.get(_norm(name))
            result.append({
                'name': name,
                'found': z is not None,
                'position': z.get('position') if z else 'UNKNOWN',
                'z_season': z.get('z_season') if z else None,
                'is_pitcher': z.get('is_pitcher', False) if z else False,
            })
        return result

    # Advisory notes
    notes = []
    giving_z = sum(
        (lookup.get(_norm(n), {}).get('z_season') or 0) for n in giving_names
    )
    receiving_z = sum(
        (lookup.get(_norm(n), {}).get('z_season') or 0) for n in receiving_names
    )

    if giving_z > receiving_z + 1.0:
        notes.append(f"WARNING: You're giving away significantly more z-score value ({giving_z:.2f} vs {receiving_z:.2f})")
    elif receiving_z > giving_z + 1.0:
        notes.append(f"BONUS: You're acquiring significantly more z-score value ({receiving_z:.2f} vs {giving_z:.2f})")

    cats_improved = [d for d in deltas if d['direction'] == 'UP']
    cats_hurt = [d for d in deltas if d['direction'] == 'DOWN']

    if cats_improved:
        notes.append(f"Improves: {', '.join(d['category'] for d in cats_improved)}")
    if cats_hurt:
        notes.append(f"Hurts: {', '.join(d['category'] for d in cats_hurt)}")

    return {
        'giving': enrich(giving_names),
        'receiving': enrich(receiving_names),
        'my_z_before': z_before,
        'my_z_after': z_after,
        'category_deltas': deltas,
        'net_z_change': net,
        'verdict': verdict,
        'notes': notes,
    }


def find_trade_targets(
    my_roster: List[Dict],
    all_rosters: Dict,
    z_scored_players: List[Dict],
    my_team_id: int,
    top_n: int = 20,
) -> Dict:
    """
    Scan other teams' rosters for high-value players worth targeting in a trade.

    Identifies:
    - Players with high z_season on other teams
    - Which of my players I could offer in return (my surplus)
    - Which of my weak categories each target helps

    Returns:
        targets         - top N players from other teams, ranked by z_season
        my_surplus      - my players with above-average z_season (trade chips)
        team_breakdown  - {team_name: [top players on that team]}
    """
    lookup = _build_zscore_lookup(z_scored_players)
    my_roster_names = {_norm(p.get('name', '')) for p in my_roster}

    # Collect all players on OTHER teams
    other_team_players: List[Dict] = []
    team_breakdown: Dict[str, List[Dict]] = {}

    for team_id, team_data in all_rosters.items():
        if team_id == my_team_id:
            continue

        team_name = team_data.get('team_name', f"Team {team_id}")
        team_targets = []

        for player in team_data.get('players', []):
            key = _norm(player.get('name', ''))
            z_data = lookup.get(key)
            if not z_data:
                continue

            z = z_data.get('z_season')
            if z is None:
                continue

            entry = {
                'name': z_data.get('name', player.get('name')),
                'position': z_data.get('position', player.get('position')),
                'is_pitcher': z_data.get('is_pitcher', False),
                'z_season': z,
                'fantasy_team': team_name,
                'fantasy_team_id': team_id,
            }
            # Add individual category z-scores
            all_cats = H2H_CATEGORIES['hitters'] + H2H_CATEGORIES['pitchers']
            for cat in all_cats:
                z_key = f"z_{cat['name'].lower()}"
                entry[z_key] = z_data.get(z_key)

            other_team_players.append(entry)
            team_targets.append(entry)

        team_targets.sort(key=lambda p: p.get('z_season', float('-inf')), reverse=True)
        team_breakdown[team_name] = team_targets[:5]

    # Sort all targets by z_season
    all_targets = sorted(
        other_team_players,
        key=lambda p: p.get('z_season', float('-inf')),
        reverse=True,
    )
    top_targets = all_targets[:top_n]

    # My trade chips: players on my team with above-average z_season
    my_surplus: List[Dict] = []
    for player in my_roster:
        key = _norm(player.get('name', ''))
        z_data = lookup.get(key)
        if z_data and (z_data.get('z_season') or 0) > 0.0:
            my_surplus.append({
                'name': z_data.get('name', player.get('name')),
                'position': z_data.get('position', player.get('position')),
                'is_pitcher': z_data.get('is_pitcher', False),
                'z_season': z_data.get('z_season', 0.0),
            })

    my_surplus.sort(key=lambda p: p.get('z_season', 0.0), reverse=True)

    return {
        'targets': top_targets,
        'my_surplus': my_surplus,
        'team_breakdown': team_breakdown,
    }
