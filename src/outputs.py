"""
Outputs Module - CSV and Console Reports

All four phases produce CSV exports and console summaries.
Z-score column note: z_season is PRIMARY. z_7day/z_14day/z_30day add context
but are noisier early in the season — weight them lightly in April.
"""

import csv
from pathlib import Path
from typing import Dict, List, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_CONFIG, H2H_CATEGORIES


# ---------------------------------------------------------------------------
# Low-level CSV helper
# ---------------------------------------------------------------------------

def export_csv(filename: str, rows: List[Dict], columns: List[str]) -> str:
    output_dir = Path(DATA_CONFIG['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col, '') for col in columns})
        print(f"    {filename} ({len(rows)} rows)")
        return str(filepath)
    except Exception as e:
        print(f"    Error writing {filename}: {e}")
        return ""


# ---------------------------------------------------------------------------
# Phase 1: Player rankings
# ---------------------------------------------------------------------------

RANKING_COLS = [
    'name', 'position', 'mlb_team', 'is_pitcher',
    'z_season',                       # PRIMARY ranking signal
    'z_7day', 'z_14day', 'z_30day',  # Recent form context (noisier early season)
    'trend_direction', 'momentum',
    'z_r', 'z_hr', 'z_rbi', 'z_sb', 'z_obp',
    'z_k', 'z_qs', 'z_era', 'z_whip', 'z_svhd',
]


def export_all_rankings(all_players: List[Dict]) -> List[str]:
    """Export season z-score rankings (all players, hitters, pitchers)."""
    print("\n  Exporting ranking CSVs...")
    ranked = sorted(all_players, key=lambda p: p.get('z_season') or 0, reverse=True)
    hitters = [p for p in ranked if not p.get('is_pitcher')]
    pitchers = [p for p in ranked if p.get('is_pitcher')]
    return [
        export_csv('all_players_ranked.csv', ranked, RANKING_COLS),
        export_csv('hitters_ranked.csv', hitters, RANKING_COLS),
        export_csv('pitchers_ranked.csv', pitchers, RANKING_COLS),
    ]


# ---------------------------------------------------------------------------
# Phase 2: Waiver wire
# ---------------------------------------------------------------------------

WAIVER_COLS = [
    'name', 'position', 'mlb_team', 'ownership_pct',
    'injury_status', 'is_two_start',
    'z_season', 'z_7day', 'z_14day', 'z_30day',
    'trend_direction',
    'z_r', 'z_hr', 'z_rbi', 'z_sb', 'z_obp',
    'z_k', 'z_qs', 'z_era', 'z_whip', 'z_svhd',
]


def export_waiver_report(waiver_report: Dict) -> List[str]:
    """Export waiver wire CSVs — top overall, by position, weak-category targets."""
    print("\n  Exporting waiver wire CSVs...")
    files = []

    files.append(export_csv('waiver_wire_top.csv', waiver_report.get('top_overall', []), WAIVER_COLS))

    # Always write — even if empty — so stale data from a previous run is cleared
    two_start_fas = waiver_report.get('two_start_free_agents', [])
    files.append(export_csv('waiver_two_start.csv', two_start_fas, WAIVER_COLS))

    by_pos = waiver_report.get('by_position', {})
    for pos, players in by_pos.items():
        if players:
            files.append(export_csv(f'waiver_{pos.lower()}.csv', players, WAIVER_COLS))

    for cat, players in waiver_report.get('weak_category_targets', {}).items():
        if players:
            files.append(export_csv(f'waiver_target_{cat.lower()}.csv', players, WAIVER_COLS))

    return [f for f in files if f]


# ---------------------------------------------------------------------------
# Phase 3: Matchup + lineup
# ---------------------------------------------------------------------------

LINEUP_COLS = [
    'name', 'position', 'eligible_positions', 'is_active_lineup', 'lineup_slot',
    'z_season', 'z_7day', 'z_14day', 'z_30day',
    'trend_direction', 'recommendation', 'injury_status', 'is_two_start', 'notes',
]

MATCHUP_COLS = [
    'category', 'display', 'type', 'my_z', 'opp_z', 'edge', 'projected_winner',
]

ACTUALS_COLS = [
    'category', 'display', 'type',
    'my_actual', 'opp_actual', 'actual_leader',
    'projected_winner', 'projected_edge', 'diverges_from_projection',
    'my_delta', 'my_trend',   # Tier 3: in-week trend (delta since last run, UP/DOWN/FLAT/NEW)
]


def export_matchup_report(matchup: Dict, lineup: Dict, actuals: List[Dict] = None) -> List[str]:
    """Export matchup breakdown + lineup recommendations + actual vs projected."""
    print("\n  Exporting matchup CSVs...")
    files = [
        export_csv('matchup_breakdown.csv', matchup.get('category_edges', []), MATCHUP_COLS),
        export_csv('lineup_hitters.csv', lineup.get('hitters', []), LINEUP_COLS),
        export_csv('lineup_pitchers.csv', lineup.get('pitchers', []), LINEUP_COLS),
    ]
    if actuals:
        files.append(export_csv('matchup_actuals_vs_projected.csv', actuals, ACTUALS_COLS))
    return [f for f in files if f]


# ---------------------------------------------------------------------------
# Phase 4: Trade analysis
# ---------------------------------------------------------------------------

TRADE_TARGET_COLS = [
    'name', 'position', 'fantasy_team', 'z_season', 'z_7day', 'z_14day',
    'trend_direction',
    'z_r', 'z_hr', 'z_rbi', 'z_sb', 'z_obp',
    'z_k', 'z_qs', 'z_era', 'z_whip', 'z_svhd',
]

TRADE_CHIP_COLS = ['name', 'position', 'z_season', 'z_7day', 'is_pitcher', 'trend_direction']


def export_trade_targets(trade_data: Dict) -> List[str]:
    """Export trade targets and my trade chips to CSV."""
    print("\n  Exporting trade CSVs...")
    return [f for f in [
        export_csv('trade_targets.csv', trade_data.get('targets', []), TRADE_TARGET_COLS),
        export_csv('trade_chips.csv', trade_data.get('my_surplus', []), TRADE_CHIP_COLS),
    ] if f]


# ---------------------------------------------------------------------------
# Console summaries
# ---------------------------------------------------------------------------

def print_summary(all_players: List[Dict], your_roster: List[Dict] = None) -> None:
    print("\n" + "=" * 70)
    print("  PHASE 1 — PLAYER RANKINGS")
    print("=" * 70)
    print("  NOTE: z_season is the primary ranking. z_7day/z_14day/z_30day add")
    print("        context but are noisier early in the season.")

    hitters = [p for p in all_players if not p.get('is_pitcher')]
    pitchers = [p for p in all_players if p.get('is_pitcher')]
    print(f"\n  Total: {len(all_players)} players  ({len(hitters)} hitters, {len(pitchers)} pitchers)")

    if your_roster:
        h = [p for p in your_roster if not p.get('is_pitcher')]
        p_c = [p for p in your_roster if p.get('is_pitcher')]
        inj = [p for p in your_roster if p.get('is_injured')]
        print(f"  Your roster: {len(your_roster)} ({len(h)} hitters, {len(p_c)} pitchers, {len(inj)} injured/IL)")

    top5 = sorted(all_players, key=lambda p: p.get('z_season') or 0, reverse=True)[:5]
    print(f"\n  Top 5 Players (by z_season):")
    for i, p in enumerate(top5, 1):
        z = p.get('z_season') or 0
        z7 = p.get('z_7day')
        z7_str = f"  7d={z7:+.2f}" if z7 is not None else ""
        print(f"    {i}. {p.get('name'):<25s} ({p.get('position')})  season={z:+.2f}{z7_str}")
    print("=" * 70 + "\n")


def print_waiver_summary(waiver_report: Dict) -> None:
    print("\n" + "=" * 70)
    print("  PHASE 2 — WAIVER WIRE")
    print("=" * 70)

    team_analysis = waiver_report.get('team_analysis', {})
    if team_analysis:
        print("\n  Your Team by Category:")
        for cat_name, data in sorted(team_analysis.items(), key=lambda x: x[1].get('rank', 99)):
            strength = data.get('strength', '?')
            avg = data.get('my_avg', 0.0)
            print(f"    {cat_name:6s} [{strength:8s}]  avg z={avg:+.3f}  {data.get('display', '')}")

    weak = waiver_report.get('weak_categories', [])
    if weak:
        print(f"\n  Target categories: {', '.join(weak)}")

    two_start_fas = waiver_report.get('two_start_free_agents', [])
    if two_start_fas:
        print(f"\n  Two-start pitchers available on waivers:")
        for p in two_start_fas[:5]:
            z = p.get('z_season') or 0
            n = p.get('two_start_count', 2)
            print(f"    {p.get('name', '?'):<25s} {p.get('position','?'):4s}  Z={z:+.2f}  ({n} starts)")

    top = waiver_report.get('top_overall', [])[:10]
    print(f"\n  Top 10 Free Agents (z_season primary | z_7day for recent form):")
    print(f"  {'Name':<25s} {'Pos':4s}  {'Season':>7}  {'7-day':>7}  {'14-day':>7}  {'Trend':5s}")
    print(f"  {'-'*65}")
    for i, p in enumerate(top, 1):
        z_s  = p.get('z_season') or 0
        z_7  = p.get('z_7day')
        z_14 = p.get('z_14day')
        z7_str  = f"{z_7:+.2f}"  if z_7  is not None else "  N/A"
        z14_str = f"{z_14:+.2f}" if z_14 is not None else "  N/A"
        trend = p.get('trend_direction', 'FLAT')
        two_s = " [2-start]" if p.get('is_two_start') else ""
        print(f"  {i:2d}. {p.get('name','?'):<23s} {p.get('position','?'):4s}  "
              f"{z_s:+.2f}     {z7_str:>7}  {z14_str:>7}  {trend:5s}{two_s}")

    total = waiver_report.get('total_free_agents', 0)
    with_stats = waiver_report.get('free_agents_with_stats', 0)
    print(f"\n  ({total} total free agents, {with_stats} with MLB stats)")
    print("=" * 70 + "\n")


def print_matchup_summary(matchup: Dict, lineup: Dict, actuals: List[Dict] = None) -> None:
    opp = matchup.get('opponent_name', 'Opponent')
    print("\n" + "=" * 70)
    print(f"  PHASE 3 — MATCHUP vs {opp}")
    print("=" * 70)

    wins   = matchup.get('projected_wins', 0)
    losses = matchup.get('projected_losses', 0)
    ties   = matchup.get('projected_ties', 0)
    print(f"\n  Projected: {wins}W - {losses}L - {ties} toss-ups")

    # Show projected vs actual side by side if actuals available
    if actuals:
        print(f"\n  {'Cat':6s} {'Proj':>8} {'My Act':>8} {'Opp Act':>8}  {'Actual':10s} {'Diverges?':9s}")
        print(f"  {'-'*60}")
        for a in actuals:
            cat = a['category']
            proj = a.get('projected_winner', '?')
            proj_short = 'WIN' if proj == 'ME' else ('LOSS' if proj not in ('ME','TOSS-UP','UNKNOWN') else proj[:4])
            my_a = a.get('my_actual')
            opp_a = a.get('opp_actual')
            ldr = a.get('actual_leader', '')
            div = ' ** DIVERGES' if a.get('diverges_from_projection') else ''
            my_str  = f"{my_a:.2f}"  if my_a  is not None else "  N/A"
            opp_str = f"{opp_a:.2f}" if opp_a is not None else "  N/A"
            print(f"  {cat:6s} {proj_short:>8} {my_str:>8} {opp_str:>8}  {ldr or '?':10s}{div}")
    else:
        print(f"\n  {'Category':<8} {'My Z':>7} {'Opp Z':>7} {'Edge':>7}  Outlook")
        print(f"  {'-'*55}")
        for edge in matchup.get('category_edges', []):
            cat = edge['category']
            my_z  = edge.get('my_z')
            opp_z = edge.get('opp_z')
            e     = edge.get('edge')
            winner = edge.get('projected_winner', '?')
            flag = 'WIN' if winner == 'ME' else ('LOSS' if winner not in ('ME','TOSS-UP','UNKNOWN') else winner)
            print(f"  {cat:<6}  {(f'{my_z:+.3f}' if my_z is not None else '  N/A'):>7}"
                  f"  {(f'{opp_z:+.3f}' if opp_z is not None else '  N/A'):>7}"
                  f"  {(f'{e:+.3f}' if e is not None else '  N/A'):>7}  {flag}")

    print(f"\n  Start/Sit — Hitters (z_season primary):")
    for p in lineup.get('hitters', [])[:10]:
        z = p.get('z_season')
        z7 = p.get('z_7day')
        z_str = f"season={z:+.2f}" if z is not None else "season= N/A"
        z7_str = f"  7d={z7:+.2f}" if z7 is not None else ""
        two = " [2-start]" if p.get('is_two_start') else ""
        inj = f" [{p.get('injury_status')}]" if p.get('injury_status') not in ('ACTIVE', None, '') else ""
        print(f"    {p.get('name','?'):<25s} {p.get('position','?'):4s}  {z_str}{z7_str}  -> {p.get('recommendation','?')}{two}{inj}")

    print(f"\n  Start/Sit — Pitchers (z_season primary):")
    for p in lineup.get('pitchers', [])[:10]:
        z = p.get('z_season')
        z7 = p.get('z_7day')
        z_str = f"season={z:+.2f}" if z is not None else "season= N/A"
        z7_str = f"  7d={z7:+.2f}" if z7 is not None else ""
        two = " [2-start]" if p.get('is_two_start') else ""
        inj = f" [{p.get('injury_status')}]" if p.get('injury_status') not in ('ACTIVE', None, '') else ""
        print(f"    {p.get('name','?'):<25s} {p.get('position','?'):4s}  {z_str}{z7_str}  -> {p.get('recommendation','?')}{two}{inj}")

    print("=" * 70 + "\n")


def print_trade_summary(trade_data: Dict) -> None:
    print("\n" + "=" * 70)
    print("  PHASE 4 — TRADE ANALYSIS")
    print("=" * 70)

    targets = trade_data.get('targets', [])[:10]
    print(f"\n  Top 10 Trade Targets (other teams):")
    print(f"  {'Name':<25s} {'Pos':4s}  {'Season':>7}  {'7-day':>7}  {'Trend':5s}  Team")
    print(f"  {'-'*70}")
    for i, p in enumerate(targets, 1):
        z  = p.get('z_season') or 0
        z7 = p.get('z_7day')
        z7_str = f"{z7:+.2f}" if z7 is not None else "  N/A"
        trend = p.get('trend_direction', 'FLAT')
        team = p.get('fantasy_team', '?')
        print(f"  {i:2d}. {p.get('name','?'):<23s} {p.get('position','?'):4s}  "
              f"{z:+.2f}     {z7_str:>7}  {trend:5s}  {team}")

    surplus = trade_data.get('my_surplus', [])
    print(f"\n  Your Trade Chips (positive z_season):")
    for p in surplus[:8]:
        z  = p.get('z_season') or 0
        z7 = p.get('z_7day')
        z7_str = f"  7d={z7:+.2f}" if z7 is not None else ""
        print(f"    {p.get('name','?'):<25s} {p.get('position','?'):4s}  season={z:+.2f}{z7_str}")

    team_bd = trade_data.get('team_breakdown', {})
    if team_bd:
        print(f"\n  Best Available Per Opponent Team:")
        for team_name, players in team_bd.items():
            if players:
                best = players[0]
                z = best.get('z_season') or 0
                print(f"    {team_name:<35s}  {best.get('name','?'):<22s} Z={z:+.2f}")

    print("=" * 70 + "\n")


RESEARCH_COLS = [
    # Identity + ownership
    'name', 'mlb_team', 'position', 'is_pitcher', 'fantasy_team',
    'percent_owned', 'percent_started',
    # --- ACTUAL STATS ---
    'games_played', 'at_bats', 'hits', 'avg', 'obp', 'walks',
    'runs', 'home_runs', 'rbis', 'stolen_bases',
    'innings_pitched', 'era', 'whip', 'strikeouts_pitch',
    'quality_starts', 'saves', 'holds',
    # --- ACTUAL Z-SCORES ---
    'z_r', 'z_hr', 'z_rbi', 'z_sb', 'z_obp',
    'z_k', 'z_qs', 'z_era', 'z_whip', 'z_svhd',
    'z_season', 'z_7day', 'z_14day', 'z_30day', 'trend_direction',
    # --- ESPN PROJECTIONS (rest of season) ---
    'proj_runs', 'proj_home_runs', 'proj_rbis', 'proj_stolen_bases', 'proj_obp',
    'proj_strikeouts', 'proj_quality_starts', 'proj_era', 'proj_whip', 'proj_sv_hd',
    # --- PROJECTION Z-SCORES ---
    'proj_z_r', 'proj_z_hr', 'proj_z_rbi', 'proj_z_sb', 'proj_z_obp',
    'proj_z_k', 'proj_z_qs', 'proj_z_era', 'proj_z_whip', 'proj_z_svhd',
    'proj_z_season',
]


def export_research_players(
    z_scored_players: List[Dict],
    db_stats: List[Dict],
    espn_projections: Dict = None,
    proj_zscores: Dict = None,
) -> str:
    """
    Export the Strategy tab dataset — four clearly separated layers:
      1. Identity + ownership
      2. Actual MLB stats (season to date)
      3. Actual z-scores (season / 7d / 14d / 30d)
      4. ESPN rest-of-season projections + projection z-scores
    """
    espn_projections = espn_projections or {}
    proj_zscores     = proj_zscores     or {}

    # Build lookup keyed by (name_lower, team_lower) for precise matching,
    # plus a fallback by name_lower for players without name collisions.
    stats_lookup: Dict = {}          # (name, team) → row
    stats_lookup_name: Dict = {}     # name → row  (fallback; prefers roster players)
    for row in db_stats:
        name_key = (row.get('name') or '').lower().strip()
        team_key = (row.get('mlb_team') or '').lower().strip()
        if name_key:
            stats_lookup[(name_key, team_key)] = row
            # Fallback: prefer roster players when multiple share a name
            if name_key not in stats_lookup_name or row.get('is_my_player'):
                stats_lookup_name[name_key] = row

    rows = []
    for player in z_scored_players:
        name = player.get('name', '')
        key  = name.lower().strip()
        team = (player.get('mlb_team') or '').lower().strip()
        # Use (name, team) lookup first — handles same-name players correctly
        stat = stats_lookup.get((key, team)) or stats_lookup_name.get(key, {})
        proj = espn_projections.get(key, {})
        pz   = proj_zscores.get(key, {})

        # Determine fantasy team label from the per-player stat row
        fantasy_team = stat.get('fantasy_team_name') or ''
        if stat.get('is_my_player'):
            fantasy_team = 'Pitch Slap'
        elif not fantasy_team:
            fantasy_team = 'FA'

        row = {
            # Identity
            'name':          name,
            'mlb_team':      player.get('mlb_team', ''),
            'position':      player.get('position', ''),
            'is_pitcher':    player.get('is_pitcher', False),
            'fantasy_team':  fantasy_team,
            'percent_owned':   proj.get('percent_owned'),
            'percent_started': proj.get('percent_started'),
            # Actual stats
            'games_played':    stat.get('games_played'),
            'at_bats':         stat.get('at_bats'),
            'hits':            stat.get('hits'),
            'avg':             stat.get('avg'),
            'obp':             stat.get('obp'),
            'walks':           stat.get('walks'),
            'runs':            stat.get('runs'),
            'home_runs':       stat.get('home_runs'),
            'rbis':            stat.get('rbis'),
            'stolen_bases':    stat.get('stolen_bases'),
            'innings_pitched': stat.get('innings_pitched'),
            'era':             stat.get('era'),
            'whip':            stat.get('whip'),
            'strikeouts_pitch': stat.get('strikeouts_pitch'),
            'quality_starts':  stat.get('quality_starts'),
            'saves':           stat.get('saves'),
            'holds':           stat.get('holds'),
            # Actual z-scores
            'z_r':    player.get('z_r'),
            'z_hr':   player.get('z_hr'),
            'z_rbi':  player.get('z_rbi'),
            'z_sb':   player.get('z_sb'),
            'z_obp':  player.get('z_obp'),
            'z_k':    player.get('z_k'),
            'z_qs':   player.get('z_qs'),
            'z_era':  player.get('z_era'),
            'z_whip': player.get('z_whip'),
            'z_svhd': player.get('z_svhd'),
            'z_season':        player.get('z_season'),
            'z_7day':          player.get('z_7day'),
            'z_14day':         player.get('z_14day'),
            'z_30day':         player.get('z_30day'),
            'trend_direction': player.get('trend_direction'),
            # ESPN projections
            'proj_runs':           proj.get('proj_runs'),
            'proj_home_runs':      proj.get('proj_home_runs'),
            'proj_rbis':           proj.get('proj_rbis'),
            'proj_stolen_bases':   proj.get('proj_stolen_bases'),
            'proj_obp':            proj.get('proj_obp'),
            'proj_strikeouts':     proj.get('proj_strikeouts'),
            'proj_quality_starts': proj.get('proj_quality_starts'),
            'proj_era':            proj.get('proj_era'),
            'proj_whip':           proj.get('proj_whip'),
            'proj_sv_hd':          proj.get('proj_sv_hd'),
            # Projection z-scores
            'proj_z_r':       pz.get('proj_z_r'),
            'proj_z_hr':      pz.get('proj_z_hr'),
            'proj_z_rbi':     pz.get('proj_z_rbi'),
            'proj_z_sb':      pz.get('proj_z_sb'),
            'proj_z_obp':     pz.get('proj_z_obp'),
            'proj_z_k':       pz.get('proj_z_k'),
            'proj_z_qs':      pz.get('proj_z_qs'),
            'proj_z_era':     pz.get('proj_z_era'),
            'proj_z_whip':    pz.get('proj_z_whip'),
            'proj_z_svhd':    pz.get('proj_z_svhd'),
            'proj_z_season':  pz.get('proj_z_season'),
        }
        rows.append(row)

    rows.sort(key=lambda r: r.get('z_season') or -99, reverse=True)
    print("\n  Exporting research CSV...")
    return export_csv('research_players.csv', rows, RESEARCH_COLS)


# ---------------------------------------------------------------------------
# Master export — every field, no column whitelist
# ---------------------------------------------------------------------------

# Static metadata for known fields: layer, source, description
_FIELD_META = {
    # Identity
    'name':             ('identity',   'mlb_api',    'Player full name'),
    'mlb_team':         ('identity',   'mlb_api',    'MLB team abbreviation'),
    'position':         ('identity',   'mlb_api',    'Primary position (C/1B/2B/3B/SS/OF/SP/RP)'),
    'is_pitcher':       ('identity',   'mlb_api',    'True if SP/RP/P, False for hitters'),
    'fantasy_team':     ('identity',   'espn_api',   'ESPN fantasy team name or FA'),
    'percent_owned':    ('identity',   'espn_auth',  'ESPN ownership % (requires auth)'),
    'percent_started':  ('identity',   'espn_auth',  'ESPN start % (requires auth)'),
    # Actual hitter stats
    'games_played':     ('actual_stats', 'mlb_api',  'Games played (season to date)'),
    'at_bats':          ('actual_stats', 'mlb_api',  'At-bats (season to date)'),
    'hits':             ('actual_stats', 'mlb_api',  'Hits (season to date)'),
    'avg':              ('actual_stats', 'mlb_api',  'Batting average (season to date)'),
    'obp':              ('actual_stats', 'mlb_api',  'On-base percentage (H2H scoring cat)'),
    'walks':            ('actual_stats', 'mlb_api',  'Walks (season to date)'),
    'runs':             ('actual_stats', 'mlb_api',  'Runs scored (H2H scoring cat)'),
    'home_runs':        ('actual_stats', 'mlb_api',  'Home runs (H2H scoring cat)'),
    'rbis':             ('actual_stats', 'mlb_api',  'Runs batted in (H2H scoring cat)'),
    'stolen_bases':     ('actual_stats', 'mlb_api',  'Stolen bases (H2H scoring cat)'),
    # Actual pitcher stats
    'innings_pitched':  ('actual_stats', 'mlb_api',  'Innings pitched (season to date)'),
    'era':              ('actual_stats', 'mlb_api',  'Earned run average (H2H scoring cat, lower=better)'),
    'whip':             ('actual_stats', 'mlb_api',  'WHIP (H2H scoring cat, lower=better)'),
    'strikeouts_pitch': ('actual_stats', 'mlb_api',  'Pitcher strikeouts (H2H scoring cat)'),
    'quality_starts':   ('actual_stats', 'mlb_api',  'Quality starts (H2H scoring cat)'),
    'saves':            ('actual_stats', 'mlb_api',  'Saves (counts toward SVHD)'),
    'holds':            ('actual_stats', 'mlb_api',  'Holds (counts toward SVHD)'),
    # Actual z-scores (hitter)
    'z_r':              ('actual_z', 'our_math', 'Z-score: runs vs position peers'),
    'z_hr':             ('actual_z', 'our_math', 'Z-score: home runs vs position peers'),
    'z_rbi':            ('actual_z', 'our_math', 'Z-score: RBI vs position peers'),
    'z_sb':             ('actual_z', 'our_math', 'Z-score: stolen bases vs position peers'),
    'z_obp':            ('actual_z', 'our_math', 'Z-score: OBP vs position peers'),
    # Actual z-scores (pitcher)
    'z_k':              ('actual_z', 'our_math', 'Z-score: strikeouts vs position peers'),
    'z_qs':             ('actual_z', 'our_math', 'Z-score: quality starts vs position peers'),
    'z_era':            ('actual_z', 'our_math', 'Z-score: ERA vs peers (inverted, higher=better)'),
    'z_whip':           ('actual_z', 'our_math', 'Z-score: WHIP vs peers (inverted, higher=better)'),
    'z_svhd':           ('actual_z', 'our_math', 'Z-score: saves+holds vs position peers'),
    # Composite / multi-window z-scores
    'z_season':         ('actual_z', 'our_math', 'PRIMARY: composite z-score across all 5 H2H cats (season stats)'),
    'z_7day':           ('actual_z', 'our_math', 'Composite z-score using last 7 days of stats (noisy early season)'),
    'z_14day':          ('actual_z', 'our_math', 'Composite z-score using last 14 days of stats'),
    'z_30day':          ('actual_z', 'our_math', 'Composite z-score using last 30 days of stats'),
    'trend_direction':  ('actual_z', 'our_math', 'UP/DOWN/FLAT based on z_7day vs z_30day delta'),
    'momentum':         ('actual_z', 'our_math', 'Numeric trend score (z_7day - z_30day)'),
    'is_two_start':     ('actual_z', 'mlb_api',  'True if pitcher has 2 starts this week (schedule-derived)'),
    # ESPN projections
    'proj_runs':           ('espn_proj', 'espn_auth', 'ESPN rest-of-season projected runs'),
    'proj_home_runs':      ('espn_proj', 'espn_auth', 'ESPN rest-of-season projected home runs'),
    'proj_rbis':           ('espn_proj', 'espn_auth', 'ESPN rest-of-season projected RBI'),
    'proj_stolen_bases':   ('espn_proj', 'espn_auth', 'ESPN rest-of-season projected stolen bases'),
    'proj_obp':            ('espn_proj', 'espn_auth', 'ESPN rest-of-season projected OBP'),
    'proj_strikeouts':     ('espn_proj', 'espn_auth', 'ESPN rest-of-season projected strikeouts'),
    'proj_quality_starts': ('espn_proj', 'espn_auth', 'ESPN rest-of-season projected quality starts'),
    'proj_era':            ('espn_proj', 'espn_auth', 'ESPN rest-of-season projected ERA'),
    'proj_whip':           ('espn_proj', 'espn_auth', 'ESPN rest-of-season projected WHIP'),
    'proj_sv_hd':          ('espn_proj', 'espn_auth', 'ESPN rest-of-season projected saves+holds'),
    # Projection z-scores
    'proj_z_r':       ('proj_z', 'our_math', 'Z-score applied to ESPN projected runs'),
    'proj_z_hr':      ('proj_z', 'our_math', 'Z-score applied to ESPN projected home runs'),
    'proj_z_rbi':     ('proj_z', 'our_math', 'Z-score applied to ESPN projected RBI'),
    'proj_z_sb':      ('proj_z', 'our_math', 'Z-score applied to ESPN projected stolen bases'),
    'proj_z_obp':     ('proj_z', 'our_math', 'Z-score applied to ESPN projected OBP'),
    'proj_z_k':       ('proj_z', 'our_math', 'Z-score applied to ESPN projected strikeouts'),
    'proj_z_qs':      ('proj_z', 'our_math', 'Z-score applied to ESPN projected quality starts'),
    'proj_z_era':     ('proj_z', 'our_math', 'Z-score applied to ESPN projected ERA (inverted)'),
    'proj_z_whip':    ('proj_z', 'our_math', 'Z-score applied to ESPN projected WHIP (inverted)'),
    'proj_z_svhd':    ('proj_z', 'our_math', 'Z-score applied to ESPN projected saves+holds'),
    'proj_z_season':  ('proj_z', 'our_math', 'Composite projection z-score across all 5 H2H cats'),
}

# Layer sort order for data dictionary
_LAYER_ORDER = ['identity', 'actual_stats', 'actual_z', 'espn_proj', 'proj_z', 'other']


def export_master_players(
    z_scored_players: List[Dict],
    db_stats: List[Dict],
    espn_projections: Dict = None,
    proj_zscores: Dict = None,
) -> str:
    """
    Export every field we have on every player — no column whitelist.
    This is the full data lake: use it to discover available fields,
    build new views, or answer 'do we have X?'
    """
    espn_projections = espn_projections or {}
    proj_zscores     = proj_zscores     or {}

    stats_lookup_m: Dict = {}
    stats_lookup_m_name: Dict = {}
    for row in db_stats:
        name_key = (row.get('name') or '').lower().strip()
        team_key = (row.get('mlb_team') or '').lower().strip()
        if name_key:
            stats_lookup_m[(name_key, team_key)] = row
            if name_key not in stats_lookup_m_name or row.get('is_my_player'):
                stats_lookup_m_name[name_key] = row

    rows = []
    all_keys: set = set()

    for player in z_scored_players:
        name = player.get('name', '')
        key  = name.lower().strip()
        team = (player.get('mlb_team') or '').lower().strip()
        stat = stats_lookup_m.get((key, team)) or stats_lookup_m_name.get(key, {})
        proj = espn_projections.get(key, {})
        pz   = proj_zscores.get(key, {})

        fantasy_team = stat.get('fantasy_team_name') or ''
        if stat.get('is_my_player'):
            fantasy_team = 'Pitch Slap'
        elif not fantasy_team:
            fantasy_team = 'FA'

        row = {}
        # Layer 1: identity (always present)
        row['name']             = name
        row['mlb_team']         = player.get('mlb_team', '')
        row['position']         = player.get('position', '')
        row['is_pitcher']       = player.get('is_pitcher', False)
        row['fantasy_team']     = fantasy_team
        row['percent_owned']    = proj.get('percent_owned')
        row['percent_started']  = proj.get('percent_started')
        # Layer 2: all z-score player fields
        for k, v in player.items():
            if k not in row:
                row[k] = v
        # Layer 3: all DB stat fields
        for k, v in stat.items():
            if k not in row:
                row[k] = v
        # Layer 4: all ESPN projection fields
        for k, v in proj.items():
            if k not in row:
                row[k] = v
        # Layer 5: all projection z-score fields
        for k, v in pz.items():
            if k not in row:
                row[k] = v

        rows.append(row)
        all_keys.update(row.keys())

    # Sort columns: known fields by layer order first, then unknown alphabetically
    def _col_sort(col):
        meta = _FIELD_META.get(col)
        layer_idx = _LAYER_ORDER.index(meta[0]) if meta and meta[0] in _LAYER_ORDER else len(_LAYER_ORDER)
        return (layer_idx, col)

    columns = sorted(all_keys, key=_col_sort)
    rows.sort(key=lambda r: r.get('z_season') or -99, reverse=True)

    print("\n  Exporting master players CSV (all fields)...")
    return export_csv('master_players.csv', rows, columns)


def export_data_dictionary(master_csv_path: str) -> str:
    """
    Auto-generate a field-by-field reference from master_players.csv.
    Outputs data_dictionary.csv — one row per column with:
      field, layer, source, description, dtype, null_pct, sample_values
    """
    import csv as _csv

    master_path = Path(master_csv_path)
    if not master_path.exists():
        print("    data_dictionary.csv skipped — master_players.csv not found")
        return ""

    # Read master CSV
    with open(master_path, encoding='utf-8') as f:
        reader = _csv.DictReader(f)
        master_rows = list(reader)
        columns     = reader.fieldnames or []

    if not master_rows:
        return ""

    dict_rows = []
    for col in columns:
        values    = [r.get(col, '') for r in master_rows]
        non_null  = [v for v in values if v not in ('', 'None', None)]
        null_pct  = round((len(values) - len(non_null)) / len(values) * 100, 1) if values else 100.0

        # Infer dtype
        numeric_count = 0
        for v in non_null[:50]:
            try:
                float(v)
                numeric_count += 1
            except (ValueError, TypeError):
                pass
        if non_null and numeric_count / max(len(non_null[:50]), 1) > 0.8:
            dtype = 'float'
        elif col in ('is_pitcher', 'is_two_start', 'is_my_player'):
            dtype = 'bool'
        else:
            dtype = 'str'

        # Sample values — up to 3 distinct non-null, skip booleans
        seen = set()
        samples = []
        for v in non_null:
            sv = str(v).strip()
            if sv not in seen and sv not in ('True', 'False'):
                seen.add(sv)
                samples.append(sv)
            if len(samples) >= 3:
                break

        meta = _FIELD_META.get(col, ('other', 'unknown', ''))
        dict_rows.append({
            'field':         col,
            'layer':         meta[0],
            'source':        meta[1],
            'description':   meta[2] or '',
            'dtype':         dtype,
            'null_pct':      f"{null_pct}%",
            'total_players': len(master_rows),
            'non_null':      len(non_null),
            'sample_values': ' | '.join(samples),
        })

    # Sort by layer order, then field name
    def _sort(r):
        layer_idx = _LAYER_ORDER.index(r['layer']) if r['layer'] in _LAYER_ORDER else len(_LAYER_ORDER)
        return (layer_idx, r['field'])

    dict_rows.sort(key=_sort)

    dd_cols = ['field', 'layer', 'source', 'description', 'dtype', 'null_pct', 'total_players', 'non_null', 'sample_values']
    print("  Exporting data dictionary CSV...")
    return export_csv('data_dictionary.csv', dict_rows, dd_cols)


def print_status() -> None:
    """Quick DB record count check."""
    import sqlite3
    db_path = DATA_CONFIG['db_path']
    if not Path(db_path).exists():
        print("Database not yet created.")
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        for table in ('players', 'player_stats', 'player_z_scores', 'all_rosters', 'league_teams'):
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table:<22s}: {count}")
            except Exception:
                print(f"  {table:<22s}: (not found)")
    finally:
        conn.close()
