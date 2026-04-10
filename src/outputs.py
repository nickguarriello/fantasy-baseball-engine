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

    two_start_fas = waiver_report.get('two_start_free_agents', [])
    if two_start_fas:
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
    'name', 'position', 'z_season', 'z_7day', 'z_14day', 'z_30day',
    'trend_direction', 'recommendation', 'injury_status', 'is_two_start', 'notes',
]

MATCHUP_COLS = [
    'category', 'display', 'type', 'my_z', 'opp_z', 'edge', 'projected_winner',
]

ACTUALS_COLS = [
    'category', 'display', 'type',
    'my_actual', 'opp_actual', 'actual_leader',
    'projected_winner', 'projected_edge', 'diverges_from_projection',
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
        inj = [p for p in your_roster if p.get('injury_status', 'ACTIVE') in {'INJURY_RESERVE','FIFTEEN_DAY_IL','SIXTY_DAY_IL','OUT'}]
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
    # Identity
    'name', 'mlb_team', 'position', 'is_pitcher', 'fantasy_team',
    # Real stats — hitters
    'games_played', 'at_bats', 'hits', 'avg', 'obp',
    'runs', 'home_runs', 'rbis', 'stolen_bases', 'walks',
    # Real stats — pitchers
    'innings_pitched', 'era', 'whip', 'strikeouts_pitch',
    'quality_starts', 'saves', 'holds',
    # Z-scores (key only)
    'z_season', 'z_7day', 'z_14day', 'z_30day', 'trend_direction',
    'espn_rating', 'percent_owned',
]


def export_research_players(z_scored_players: List[Dict], db_stats: List[Dict], espn_ratings: Dict = None) -> str:
    """
    Export combined real-stats + z-scores for the Strategy/Research tab.
    Joins z_scored_players with DB stats by name, adds ESPN ratings if available.
    """
    espn_ratings = espn_ratings or {}

    # Build lookup: name_lower → real stats row
    stats_lookup: Dict[str, Dict] = {}
    for row in db_stats:
        key = (row.get('name') or '').lower().strip()
        if key:
            stats_lookup[key] = row

    rows = []
    for player in z_scored_players:
        name = player.get('name', '')
        key  = name.lower().strip()
        stat_row = stats_lookup.get(key, {})
        espn     = espn_ratings.get(key, {})

        # fantasy_team from DB stats row (joined via all_rosters)
        fantasy_team = stat_row.get('fantasy_team_name') or ''
        if stat_row.get('is_my_player'):
            fantasy_team = 'Pitch Slap'
        elif not fantasy_team:
            fantasy_team = 'FA'

        row = {
            'name':         name,
            'mlb_team':     player.get('mlb_team', ''),
            'position':     player.get('position', ''),
            'is_pitcher':   player.get('is_pitcher', False),
            'fantasy_team': fantasy_team,
            # Hitting real stats
            'games_played':    stat_row.get('games_played'),
            'at_bats':         stat_row.get('at_bats'),
            'hits':            stat_row.get('hits'),
            'avg':             stat_row.get('avg'),
            'obp':             stat_row.get('obp'),
            'runs':            stat_row.get('runs'),
            'home_runs':       stat_row.get('home_runs'),
            'rbis':            stat_row.get('rbis'),
            'stolen_bases':    stat_row.get('stolen_bases'),
            'walks':           stat_row.get('walks'),
            # Pitching real stats
            'innings_pitched': stat_row.get('innings_pitched'),
            'era':             stat_row.get('era'),
            'whip':            stat_row.get('whip'),
            'strikeouts_pitch': stat_row.get('strikeouts_pitch'),
            'quality_starts':  stat_row.get('quality_starts'),
            'saves':           stat_row.get('saves'),
            'holds':           stat_row.get('holds'),
            # Z-scores
            'z_season':        player.get('z_season'),
            'z_7day':          player.get('z_7day'),
            'z_14day':         player.get('z_14day'),
            'z_30day':         player.get('z_30day'),
            'trend_direction': player.get('trend_direction'),
            # ESPN
            'espn_rating':     espn.get('espn_rating'),
            'percent_owned':   espn.get('percent_owned'),
        }
        rows.append(row)

    rows.sort(key=lambda r: r.get('z_season') or -99, reverse=True)
    print("\n  Exporting research CSV...")
    return export_csv('research_players.csv', rows, RESEARCH_COLS)


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
