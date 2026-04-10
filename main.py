"""
Fantasy Baseball H2H Category Decision Engine — All Phases

Phase 1: MLB z-scores for all ~800+ players (season + 7/14/30-day windows)
Phase 2: Waiver wire ranked by z_season; injury-filtered; two-start flagged
Phase 3: Matchup breakdown (projected + actual); start/sit with injury/2-start logic
Phase 4: Trade targets on other rosters; specific trade evaluation

Usage:
    python -X utf8 main.py                                  # all phases
    python -X utf8 main.py --skip-phases waiver trade       # skip specific phases
    python -X utf8 main.py --trade "PlayerA,PlayerB" "PlayerC"  # evaluate a trade
"""

import sys
import os
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LEAGUE_CONFIG

from src.database import (
    init_database, store_player_stats, store_z_scores,
    store_league_teams, store_all_rosters, get_players_with_stats,
)
from src.fetchers import (
    test_api_connectivity,
    fetch_espn_league_data,
    derive_free_agents,
    fetch_mlb_player_stats,
    fetch_mlb_stats_range,
    fetch_two_start_pitchers,
    fetch_espn_player_ratings,
    _n_days_ago, _today_str,
)
from src.processors import calculate_multi_period_zscores, calculate_trends
from src.waiver_wire import analyze_my_team, generate_waiver_report
from src.matchup import analyze_matchup, recommend_lineup, analyze_actuals_vs_projected
from src.trades import find_trade_targets, evaluate_trade
from src.outputs import (
    export_all_rankings, export_waiver_report,
    export_matchup_report, export_trade_targets,
    export_research_players,
    print_summary, print_waiver_summary,
    print_matchup_summary, print_trade_summary,
)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args():
    parser = argparse.ArgumentParser(description='Fantasy Baseball Decision Engine')
    parser.add_argument(
        '--trade', nargs=2, metavar=('GIVE', 'RECEIVE'),
        help='Evaluate a trade. Example: --trade "PlayerA,PlayerB" "PlayerC"',
    )
    parser.add_argument(
        '--skip-phases', nargs='*', metavar='PHASE', default=[],
        help='Phases to skip: waiver matchup trade',
    )
    return parser.parse_args()


def _header(text: str) -> None:
    print(f"\n{'='*70}\n  {text}\n{'='*70}")


def _print_trade_eval(eval_result: Dict) -> None:
    print(f"\n  Trade Evaluation")
    print(f"  {'='*50}")
    for label, key in [('Giving away', 'giving'), ('Receiving', 'receiving')]:
        print(f"  {label}:")
        for p in eval_result.get(key, []):
            z = p.get('z_season')
            z_str = f"Z={z:+.2f}" if z is not None else "Z=N/A"
            found = "" if p.get('found') else " [NOT IN STATS]"
            print(f"    {p['name']:<25s}  {z_str}{found}")
    print(f"\n  Net z-score change: {eval_result.get('net_z_change', 0):+.3f}")
    print(f"  Verdict: {eval_result.get('verdict', '?')}")
    for note in eval_result.get('notes', []):
        print(f"  * {note}")
    print("\n  Category Impact:")
    for delta in eval_result.get('category_deltas', []):
        d = delta.get('delta', 0)
        if abs(d) < 0.02:
            continue
        arrow = "UP" if delta.get('direction') == 'UP' else ("DOWN" if delta.get('direction') == 'DOWN' else "~")
        print(f"    {delta['category']:6s}  {arrow:5s}  delta={d:+.3f}")
    print()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    args = _parse_args()
    skip = set(args.skip_phases or [])

    _header("FANTASY BASEBALL H2H DECISION ENGINE")
    print(f"  League: {LEAGUE_CONFIG['league_id']}  |  Team: {LEAGUE_CONFIG['team_id']}")
    print(f"  Season: {LEAGUE_CONFIG['season']}")
    print(f"  Run:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Note:   z_season is PRIMARY ranking signal. Multi-window z-scores")
    print(f"          (7/14/30-day) add context but are noisier early in season.")

    try:
        # ============================================================ #
        # STEP 1: Connectivity
        # ============================================================ #
        print("\n[1/9] Testing API connectivity...")
        if not test_api_connectivity():
            print("Cannot connect to APIs.")
            return False
        print()

        # ============================================================ #
        # STEP 2: Database
        # ============================================================ #
        print("[2/9] Initializing database...")
        db_path = init_database()
        print(f"  Database: {db_path}\n")

        # ============================================================ #
        # STEP 3: ESPN — all rosters, injury status, matchup schedule
        # ============================================================ #
        print("[3/9] Fetching ESPN league data...")
        espn_data = fetch_espn_league_data()
        if not espn_data:
            print("Failed to fetch ESPN data.")
            return False

        my_roster           = espn_data['my_roster']
        all_rosters         = espn_data['all_rosters']
        league_teams        = espn_data['league_teams']
        opponent_team_id    = espn_data.get('current_matchup_opponent_id')
        matchup_actuals     = espn_data.get('matchup_actuals', {})
        injury_lookup       = espn_data.get('injury_lookup', {})
        print()

        # ============================================================ #
        # STEP 4: MLB season stats
        # ============================================================ #
        print("[4/9] Fetching MLB season statistics...")
        season_stats = fetch_mlb_player_stats()
        if not season_stats:
            print("Failed to fetch MLB stats.")
            return False
        print(f"  {len(season_stats)} players with season stats\n")

        # ============================================================ #
        # STEP 5: Multi-period stats (7 / 14 / 30 day)
        # ============================================================ #
        print("[5/9] Fetching recent-form stats...")
        today = _today_str()
        print("  7-day stats:")
        stats_7day  = fetch_mlb_stats_range(_n_days_ago(7),  today, '7d')
        print("  14-day stats:")
        stats_14day = fetch_mlb_stats_range(_n_days_ago(14), today, '14d')
        print("  30-day stats:")
        stats_30day = fetch_mlb_stats_range(_n_days_ago(30), today, '30d')
        print()

        # ============================================================ #
        # STEP 6: ESPN Player Rater (optional — requires auth cookies)
        # ============================================================ #
        print("[6/9] Fetching ESPN Player Rater ratings...")
        espn_ratings = fetch_espn_player_ratings()
        if not espn_ratings:
            print("  (Skipped — credentials not configured or expired)")
        print()

        # ============================================================ #
        # STEP 6b: Two-start pitchers this week
        # ============================================================ #
        print("[6b/9] Identifying two-start pitchers this week...")
        two_start_pitchers = fetch_two_start_pitchers()  # noqa: kept inline
        if two_start_pitchers:
            print(f"  Two-starters: {', '.join(k.title() for k in list(two_start_pitchers.keys())[:6])}"
                  + (f" + {len(two_start_pitchers)-6} more" if len(two_start_pitchers) > 6 else ""))
        print()

        # ============================================================ #
        # STEP 7: Derive free agents + calculate all z-scores
        # ============================================================ #
        print("[7/9] Calculating multi-period z-scores...")
        free_agents = derive_free_agents(season_stats, all_rosters)

        z_scored_players, position_stats = calculate_multi_period_zscores(
            season_stats, stats_7day, stats_14day, stats_30day
        )
        z_scored_players = calculate_trends(z_scored_players)

        # Tag two-start pitchers on z-scored list
        for player in z_scored_players:
            key = player.get('name', '').lower().strip()
            player['is_two_start'] = player.get('is_pitcher', False) and key in two_start_pitchers

        if not z_scored_players:
            print("Failed to calculate z-scores.")
            return False
        print(f"  {len(z_scored_players)} players z-scored across all windows\n")

        # ============================================================ #
        # STEP 8: Store in database
        # ============================================================ #
        print("[8/9] Storing data in database...")
        store_league_teams(league_teams)
        roster_rows = store_all_rosters(all_rosters)
        stats_stored = store_player_stats(list(season_stats.values()), season_stats)
        z_stored = store_z_scores(z_scored_players)
        print(f"  {len(league_teams)} teams | {roster_rows} roster entries | "
              f"{stats_stored} stat records | {z_stored} z-score records\n")

        # ============================================================ #
        # STEP 9: Phase outputs
        # ============================================================ #
        print("[9/9] Running decision phases...")
        all_csv_files = list(export_all_rankings(z_scored_players))
        # Research/Strategy export — real stats + z-scores + ESPN ratings
        db_stats = get_players_with_stats()
        all_csv_files.append(export_research_players(z_scored_players, db_stats, espn_ratings))
        print_summary(z_scored_players, my_roster)

        # ------------------------------------------------------------ #
        # Phase 2: Waiver Wire
        # ------------------------------------------------------------ #
        if 'waiver' not in skip:
            print("  [Phase 2] Waiver Wire Analysis...")
            team_analysis = analyze_my_team(my_roster, z_scored_players)
            waiver_report = generate_waiver_report(
                free_agents, z_scored_players, team_analysis, two_start_pitchers
            )
            print_waiver_summary(waiver_report)
            all_csv_files.extend(export_waiver_report(waiver_report))
        else:
            print("  [Phase 2] Waiver Wire — skipped")

        # ------------------------------------------------------------ #
        # Phase 3: Matchup + Lineup
        # ------------------------------------------------------------ #
        if 'matchup' not in skip:
            print("  [Phase 3] Matchup & Lineup Analysis...")

            if opponent_team_id and opponent_team_id in all_rosters:
                opponent_roster = all_rosters[opponent_team_id]['players']
                opponent_name   = all_rosters[opponent_team_id]['team_name']
            else:
                opponent_roster = []
                opponent_name   = "Unknown Opponent"
                print("    No current matchup — lineup recommendations only")

            matchup_result = analyze_matchup(
                my_roster, opponent_roster, z_scored_players, opponent_name
            )
            matchup_edges  = matchup_result.get('category_edges', [])

            # Actual vs projected (ESPN in-week stats)
            actuals = analyze_actuals_vs_projected(matchup_actuals, matchup_edges)

            lineup_result = recommend_lineup(
                my_roster, z_scored_players,
                matchup_edges=matchup_edges,
                two_start_pitchers=two_start_pitchers,
                injury_lookup=injury_lookup,
            )
            print_matchup_summary(matchup_result, lineup_result, actuals)
            all_csv_files.extend(export_matchup_report(matchup_result, lineup_result, actuals))
        else:
            print("  [Phase 3] Matchup — skipped")

        # ------------------------------------------------------------ #
        # Phase 4: Trade Analysis
        # ------------------------------------------------------------ #
        if 'trade' not in skip:
            print("  [Phase 4] Trade Analysis...")
            trade_data = find_trade_targets(
                my_roster, all_rosters, z_scored_players,
                my_team_id=LEAGUE_CONFIG['team_id'],
            )

            if args.trade:
                giving_names    = [n.strip() for n in args.trade[0].split(',')]
                receiving_names = [n.strip() for n in args.trade[1].split(',')]
                print(f"\n  Evaluating trade: Give {giving_names} | Receive {receiving_names}")
                trade_eval = evaluate_trade(
                    giving_names, receiving_names, my_roster, z_scored_players
                )
                _print_trade_eval(trade_eval)

            print_trade_summary(trade_data)
            all_csv_files.extend(export_trade_targets(trade_data))
        else:
            print("  [Phase 4] Trade — skipped")

        # ============================================================ #
        # Done
        # ============================================================ #
        _header("ALL PHASES COMPLETE")
        print(f"  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n  Database:  {db_path}")
        valid_files = [f for f in all_csv_files if f]
        print(f"  CSV files ({len(valid_files)}):")
        for f in valid_files:
            print(f"    - {Path(f).name}")
        print()
        return True

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
