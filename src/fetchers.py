"""
Fetchers Module - API Communication

Handles:
- ESPN Fantasy API: all rosters, injury status, matchup schedule, in-week actuals
- MLB Stats API: season stats, date-range stats (7/14/30 day), two-start pitchers
- Error handling with retry logic
"""

import requests
import json
import time
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    LEAGUE_CONFIG, API_CONFIG, DEBUG_CONFIG,
    ESPN_POSITION_MAP, PITCHER_POSITION_IDS,
    OF_POSITIONS, ESPN_STAT_IDS, ESPN_RATE_STAT_IDS,
    INJURED_STATUSES, QUESTIONABLE_STATUSES,
    ESPN_S2, ESPN_SWID,
)


# ---------------------------------------------------------------------------
# Low-level HTTP helper
# ---------------------------------------------------------------------------

def _make_request(
    url: str,
    params: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    max_retries: int = 3,
) -> Optional[Dict]:
    """GET with retry logic. Returns parsed JSON or None on failure."""
    base_headers = {'User-Agent': 'Mozilla/5.0 (Fantasy Baseball Engine)'}
    if headers:
        base_headers.update(headers)

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                url, params=params, timeout=API_CONFIG['request_timeout'],
                headers=base_headers,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(API_CONFIG['retry_delay'])
            else:
                print(f"  Timeout after {max_retries} attempts: {url}")
                return None

        except requests.exceptions.ConnectionError:
            if attempt < max_retries:
                time.sleep(API_CONFIG['retry_delay'])
            else:
                print(f"  Connection failed: {url}")
                return None

        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 429:
                time.sleep(10)
            elif attempt < max_retries:
                time.sleep(API_CONFIG['retry_delay'])
            else:
                print(f"  HTTP {code}: {url}")
                return None

        except ValueError:
            print(f"  Invalid JSON: {url}")
            return None

    return None


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _today_str() -> str:
    return date.today().strftime('%Y-%m-%d')


def _n_days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).strftime('%Y-%m-%d')


def _get_week_dates() -> Tuple[str, str]:
    """Returns (monday, sunday) of the current week as YYYY-MM-DD strings."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')


# ---------------------------------------------------------------------------
# ESPN parsing helpers
# ---------------------------------------------------------------------------

def _normalize_position(pos: str) -> str:
    """Map CF/LF/RF to OF. All other positions pass through."""
    if pos in OF_POSITIONS:
        return 'OF'
    return pos


def _parse_espn_player(
    entry: Dict, team_id: int, team_name: str, my_team_id: int
) -> Optional[Dict]:
    """
    Parse a single ESPN roster entry into a normalised player dict.
    Extracts injury status and maps position IDs correctly.
    """
    player_pool = entry.get('playerPoolEntry', {})
    player = player_pool.get('player', {})

    espn_id = player.get('id')
    if not espn_id:
        return None

    pos_id = player.get('defaultPositionId', 0)
    raw_position = ESPN_POSITION_MAP.get(pos_id, 'UNKNOWN')
    position = _normalize_position(raw_position)
    is_pitcher = pos_id in PITCHER_POSITION_IDS

    # Injury status from ESPN
    injury_status = player_pool.get('injuryStatus', 'ACTIVE') or 'ACTIVE'
    is_injured = injury_status in INJURED_STATUSES
    is_questionable = injury_status in QUESTIONABLE_STATUSES

    return {
        'espn_id': espn_id,
        'id': espn_id,
        'name': player.get('fullName', 'Unknown'),
        'position': position,
        'position_id': pos_id,
        'is_pitcher': is_pitcher,
        'team_id': team_id,
        'team_name': team_name,
        'is_my_player': team_id == my_team_id,
        'ownership_pct': player_pool.get('percentOwned', 0.0),
        'pro_team_id': player.get('proTeamId'),
        'injury_status': injury_status,
        'is_injured': is_injured,
        'is_questionable': is_questionable,
    }


def _parse_matchup_actuals(schedule: List[Dict], my_team_id: int) -> Dict:
    """
    Extract in-week accumulated stats for my team and opponent
    from the ESPN matchup schedule's cumulativeScore.scoreByStat.

    Returns {
        'my_actuals': {category: value},
        'opp_actuals': {category: value},
        'matchup_period': int,
        'opponent_team_id': int or None,
    }
    """
    my_undecided = [
        m for m in schedule
        if m.get('winner', '') in ('UNDECIDED', '', None)
        and (
            m.get('home', {}).get('teamId') == my_team_id
            or m.get('away', {}).get('teamId') == my_team_id
        )
    ]
    if not my_undecided:
        return {}

    current = min(my_undecided, key=lambda m: m.get('matchupPeriodId', 9999))
    period = current.get('matchupPeriodId')
    home_id = current.get('home', {}).get('teamId')
    away_id = current.get('away', {}).get('teamId')
    opp_id = away_id if home_id == my_team_id else home_id

    def parse_score_by_stat(side_data: Dict) -> Dict:
        score_by_stat = side_data.get('cumulativeScore', {}).get('scoreByStat', {}) or {}
        result = {}
        for stat_id, stat_data in score_by_stat.items():
            cat = ESPN_STAT_IDS.get(str(stat_id))
            if cat:
                val = stat_data.get('score')
                if val is not None:
                    result[cat] = round(float(val), 4)
        return result

    my_side = current.get('home') if home_id == my_team_id else current.get('away')
    opp_side = current.get('away') if home_id == my_team_id else current.get('home')

    return {
        'my_actuals': parse_score_by_stat(my_side or {}),
        'opp_actuals': parse_score_by_stat(opp_side or {}),
        'matchup_period': period,
        'opponent_team_id': opp_id,
    }


# ---------------------------------------------------------------------------
# ESPN public API — league data
# ---------------------------------------------------------------------------

def fetch_espn_league_data() -> Optional[Dict]:
    """
    Fetch all team rosters + matchup schedule from ESPN.

    Returns dict with:
        my_roster                   list of your players (with injury status)
        all_rosters                 {team_id: {team_name, players}}
        owned_espn_ids              set of all rostered ESPN player IDs
        league_teams                [{team_id, team_name}]
        league_info                 {season, league_id, num_teams}
        scoring_period_id           int
        current_matchup_opponent_id int or None
        current_matchup_period      int or None
        matchup_actuals             {my_actuals, opp_actuals} — in-week stats
        injury_lookup               {lower_name: injury_status}
    """
    print("  Fetching ESPN league data (all rosters + matchup)...")

    league_id = LEAGUE_CONFIG['league_id']
    season = LEAGUE_CONFIG['season']
    my_team_id = LEAGUE_CONFIG['team_id']

    url = (
        f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb"
        f"/seasons/{season}/segments/0/leagues/{league_id}"
    )

    response = _make_request(url, params={'view': ['mRoster', 'mMatchup', 'mTeam']})
    if not response:
        return None

    try:
        teams_raw = response.get('teams', [])
        if not teams_raw:
            print("  No teams in ESPN response")
            return None

        scoring_period_id = response.get('scoringPeriodId', 1)

        # Build team name map from mTeam view
        team_name_map: Dict[int, str] = {}
        for t in teams_raw:
            tid = t.get('id')
            name = (
                t.get('name', '').strip()
                or f"{t.get('location', '')} {t.get('nickname', '')}".strip()
                or f"Team {tid}"
            )
            team_name_map[tid] = name

        # Parse all rosters + build injury lookup
        all_rosters: Dict[int, Dict] = {}
        my_roster: List[Dict] = []
        owned_espn_ids: Set[int] = set()
        injury_lookup: Dict[str, str] = {}

        for team in teams_raw:
            team_id = team.get('id')
            team_name = team_name_map.get(team_id, f"Team {team_id}")
            players = []

            for entry in team.get('roster', {}).get('entries', []):
                player = _parse_espn_player(entry, team_id, team_name, my_team_id)
                if player:
                    players.append(player)
                    owned_espn_ids.add(player['espn_id'])
                    # Build name-keyed injury lookup for all rostered players
                    key = player['name'].lower().strip()
                    injury_lookup[key] = player['injury_status']
                    if team_id == my_team_id:
                        my_roster.append(player)

            all_rosters[team_id] = {
                'team_id': team_id,
                'team_name': team_name,
                'players': players,
            }

        # Current week opponent (first undecided matchup involving my team)
        schedule = response.get('schedule', [])
        current_opponent_id = None
        current_matchup_period = None

        my_undecided = [
            m for m in schedule
            if m.get('winner', '') in ('UNDECIDED', '', None)
            and (
                m.get('home', {}).get('teamId') == my_team_id
                or m.get('away', {}).get('teamId') == my_team_id
            )
        ]
        if my_undecided:
            current = min(my_undecided, key=lambda m: m.get('matchupPeriodId', 9999))
            current_matchup_period = current.get('matchupPeriodId')
            h = current.get('home', {}).get('teamId')
            a = current.get('away', {}).get('teamId')
            current_opponent_id = a if h == my_team_id else h

        # In-week actual stats
        matchup_actuals = _parse_matchup_actuals(schedule, my_team_id)

        h_count = sum(1 for p in my_roster if not p['is_pitcher'])
        p_count = sum(1 for p in my_roster if p['is_pitcher'])
        inj_count = sum(1 for p in my_roster if p.get('is_injured'))
        print(f"    Your roster: {len(my_roster)} players "
              f"({h_count} hitters, {p_count} pitchers, {inj_count} injured/IL)")
        print(f"    League: {len(teams_raw)} teams | Scoring period: {scoring_period_id}")

        if current_opponent_id:
            opp_name = team_name_map.get(current_opponent_id, f"Team {current_opponent_id}")
            print(f"    Matchup period {current_matchup_period}: vs {opp_name}")
        else:
            print(f"    No current matchup found")

        league_teams = [
            {'team_id': tid, 'team_name': name}
            for tid, name in team_name_map.items()
        ]

        return {
            'my_roster': my_roster,
            'all_rosters': all_rosters,
            'owned_espn_ids': owned_espn_ids,
            'league_teams': league_teams,
            'league_info': {
                'name': 'League',
                'season': season,
                'league_id': league_id,
                'num_teams': len(teams_raw),
            },
            'scoring_period_id': scoring_period_id,
            'current_matchup_opponent_id': current_opponent_id,
            'current_matchup_period': current_matchup_period,
            'matchup_actuals': matchup_actuals,
            'injury_lookup': injury_lookup,
        }

    except (KeyError, IndexError, TypeError) as e:
        print(f"  Error parsing ESPN response: {e}")
        import traceback; traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Free agent derivation
# ---------------------------------------------------------------------------

def derive_free_agents(mlb_stats: Dict, all_rosters: Dict) -> List[Dict]:
    """
    Compute free agents = MLB stats players NOT on any ESPN roster.

    ESPN's free agent API requires authentication even on public leagues,
    so we derive availability by name-matching against all rostered players.
    """
    print("  Deriving free agent pool from MLB stats minus rostered players...")

    owned_names: Set[str] = set()
    for team_data in all_rosters.values():
        for player in team_data.get('players', []):
            name = player.get('name', '').lower().strip()
            if name:
                owned_names.add(name)

    free_agents = []
    for player in mlb_stats.values():
        name = player.get('name', '').lower().strip()
        if name and name not in owned_names:
            fa = {**player, 'ownership_pct': 0.0, 'acquisition_type': 'FREEAGENT'}
            free_agents.append(fa)

    print(f"    {len(free_agents)} free agents (MLB players not on any roster)")
    return free_agents


# ---------------------------------------------------------------------------
# MLB Stats API — internal helpers
# ---------------------------------------------------------------------------

def _parse_hitting_split(split: Dict) -> Optional[Dict]:
    """Parse one MLB API hitting split into our stat dict."""
    player_info = split.get('player', {})
    player_id = player_info.get('id')
    if not player_id:
        return None

    stats = split.get('stat', {})
    pos_abbr = split.get('position', {}).get('abbreviation', '')
    position = _normalize_position(pos_abbr)

    return {
        'player_id': player_id,
        'mlb_id': player_id,
        'name': player_info.get('fullName', 'Unknown'),
        'position': position,
        'mlb_team': split.get('team', {}).get('name', ''),
        'is_pitcher': False,
        'games_played': stats.get('gamesPlayed', 0) or 0,
        'at_bats': stats.get('atBats', 0) or 0,
        'hits': stats.get('hits', 0) or 0,
        'home_runs': stats.get('homeRuns', 0) or 0,
        'rbis': stats.get('rbi', 0) or 0,
        'runs': stats.get('runs', 0) or 0,
        'stolen_bases': stats.get('stolenBases', 0) or 0,
        'walks': stats.get('baseOnBalls', 0) or 0,
        'strikeouts': stats.get('strikeOuts', 0) or 0,
        'avg': float(stats['avg']) if stats.get('avg') else 0.0,
        'obp': float(stats['obp']) if stats.get('obp') else 0.0,
        # Pitching fields default to 0 for hitters
        'innings_pitched': 0.0,
        'earned_runs': 0,
        'era': 0.0,
        'whip': 0.0,
        'strikeouts_pitch': 0,
        'wins': 0,
        'losses': 0,
        'saves': 0,
        'holds': 0,
        'sv_hd': 0,
        'quality_starts': 0,
    }


def _parse_pitching_split(split: Dict) -> Tuple[Optional[int], Dict]:
    """
    Parse one MLB API pitching split into a partial stats dict.
    Returns (player_id, stats_update).
    """
    player_info = split.get('player', {})
    player_id = player_info.get('id')
    if not player_id:
        return None, {}

    stats = split.get('stat', {})
    saves = stats.get('saves', 0) or 0
    holds = stats.get('holds', 0) or 0
    ks = stats.get('strikeOuts', 0) or 0
    pos_abbr = split.get('position', {}).get('abbreviation', '')
    position = _normalize_position(pos_abbr)

    base = {
        'player_id': player_id,
        'mlb_id': player_id,
        'name': player_info.get('fullName', 'Unknown'),
        'position': position,
        'mlb_team': split.get('team', {}).get('name', ''),
        'is_pitcher': True,
    }
    pitching_stats = {
        'innings_pitched': float(stats['inningsPitched']) if stats.get('inningsPitched') else 0.0,
        'earned_runs': stats.get('earnedRuns', 0) or 0,
        'era': float(stats['era']) if stats.get('era') else 0.0,
        'whip': float(stats['whip']) if stats.get('whip') else 0.0,
        'strikeouts': ks,
        'strikeouts_pitch': ks,
        'wins': stats.get('wins', 0) or 0,
        'losses': stats.get('losses', 0) or 0,
        'saves': saves,
        'holds': holds,
        'sv_hd': saves + holds,
        'quality_starts': stats.get('qualityStarts', 0) or 0,
    }
    return player_id, {**base, **pitching_stats}


def _fetch_mlb_group(group: str, extra_params: Dict) -> Dict:
    """
    Fetch one stat group (hitting or pitching) from MLB Stats API.
    Returns {player_id: stats_dict}.
    """
    params = {
        'group': group,
        'sportId': 1,
        'playerPool': 'All',
        'limit': 2000,
        **extra_params,
    }
    response = _make_request('https://statsapi.mlb.com/api/v1/stats', params)
    if not response or not response.get('stats'):
        return {}
    splits = response['stats'][0].get('splits', [])
    result: Dict = {}

    if group == 'hitting':
        for split in splits:
            parsed = _parse_hitting_split(split)
            if parsed:
                result[parsed['player_id']] = parsed
    else:  # pitching
        for split in splits:
            pid, update = _parse_pitching_split(split)
            if pid is None:
                continue
            if pid in result:
                result[pid].update(update)
            else:
                # Pitcher not yet in dict — add with default hitter fields
                base_hitter_fields = {
                    'games_played': 0, 'at_bats': 0, 'hits': 0,
                    'home_runs': 0, 'rbis': 0, 'runs': 0,
                    'stolen_bases': 0, 'walks': 0, 'avg': 0.0, 'obp': 0.0,
                }
                result[pid] = {**base_hitter_fields, **update}

    return result


# ---------------------------------------------------------------------------
# MLB Stats API — season stats
# ---------------------------------------------------------------------------

def fetch_mlb_player_stats() -> Dict:
    """
    Fetch full-season MLB stats for all players.
    Returns {player_id: stats_dict}.
    """
    print("  Fetching MLB player statistics...")
    season = LEAGUE_CONFIG['season']
    season_params = {'stats': 'season', 'season': season}

    print("    Hitting...", end=" ", flush=True)
    hitting = _fetch_mlb_group('hitting', season_params)
    print(f"({len(hitting)})")

    print("    Pitching...", end=" ", flush=True)
    pitching = _fetch_mlb_group('pitching', season_params)
    print(f"({len(pitching)})")

    # Merge: pitchers not already in hitting dict get added
    all_stats = dict(hitting)
    for pid, pdata in pitching.items():
        if pid in all_stats:
            all_stats[pid].update({
                k: v for k, v in pdata.items()
                if k not in ('player_id', 'mlb_id', 'name')
            })
        else:
            all_stats[pid] = pdata

    print(f"    Total: {len(all_stats)} players")
    return all_stats


# ---------------------------------------------------------------------------
# MLB Stats API — date-range stats (7/14/30 day)
# ---------------------------------------------------------------------------

def fetch_mlb_stats_range(start_date: str, end_date: str, label: str = '') -> Dict:
    """
    Fetch MLB stats for a specific date range.
    Returns {player_id: stats_dict} — same shape as fetch_mlb_player_stats().
    Returns {} if the API call fails or returns no data.
    """
    tag = f"[{label}] " if label else ''
    print(f"    {tag}Hitting...", end=" ", flush=True)

    range_params = {
        'stats': 'byDateRange',
        'startDate': start_date,
        'endDate': end_date,
    }

    hitting = _fetch_mlb_group('hitting', range_params)
    print(f"({len(hitting)})")

    print(f"    {tag}Pitching...", end=" ", flush=True)
    pitching = _fetch_mlb_group('pitching', range_params)
    print(f"({len(pitching)})")

    all_stats = dict(hitting)
    for pid, pdata in pitching.items():
        if pid in all_stats:
            all_stats[pid].update({
                k: v for k, v in pdata.items()
                if k not in ('player_id', 'mlb_id', 'name')
            })
        else:
            all_stats[pid] = pdata

    return all_stats


# ---------------------------------------------------------------------------
# MLB Schedule API — two-start pitchers
# ---------------------------------------------------------------------------

def fetch_two_start_pitchers() -> Dict[str, int]:
    """
    Find starting pitchers with 2+ probable starts this week (Mon-Sun).

    Queries the MLB schedule API for probable pitchers for all games
    in the current fantasy week.

    Returns:
        {pitcher_name_lower: start_count}
        Only includes pitchers with 2+ starts. Empty dict on failure.
    """
    week_start, week_end = _get_week_dates()
    print(f"  Fetching probable starters ({week_start} to {week_end})...", end=" ", flush=True)

    response = _make_request(
        'https://statsapi.mlb.com/api/v1/schedule',
        params={
            'sportId': 1,
            'startDate': week_start,
            'endDate': week_end,
            'gameType': 'R',
            'hydrate': 'probablePitcher',
        }
    )

    if not response:
        print("(failed)")
        return {}

    start_counts: Dict[str, int] = {}  # {name_lower: count}

    for date_entry in response.get('dates', []):
        for game in date_entry.get('games', []):
            for side in ('home', 'away'):
                pitcher = game.get('teams', {}).get(side, {}).get('probablePitcher')
                if pitcher and pitcher.get('fullName'):
                    key = pitcher['fullName'].lower().strip()
                    start_counts[key] = start_counts.get(key, 0) + 1

    two_starters = {name: count for name, count in start_counts.items() if count >= 2}
    all_starters = len(start_counts)
    print(f"({all_starters} probable starters, {len(two_starters)} with 2 starts this week)")

    return two_starters


# ---------------------------------------------------------------------------
# Connectivity check
# ---------------------------------------------------------------------------

def fetch_espn_player_ratings() -> Dict[str, Dict]:
    """
    Fetch ESPN player ownership % and draft ranks via kona_player_info (requires auth).
    Returns {player_name_lower: {percent_owned, percent_started, espn_draft_rank}}
    or empty dict if credentials not configured or request fails.

    Note: ESPN's composite Player Rater score is not available in this endpoint.
    We use ownership % and raw stats as supplemental data.
    The endpoint returns ~50 players per call (ESPN pagination).
    """
    if not ESPN_S2 or not ESPN_SWID:
        return {}

    league_id = LEAGUE_CONFIG['league_id']
    season    = LEAGUE_CONFIG['season']
    url       = f"{API_CONFIG['espn_base_url']}/seasons/{season}/segments/0/leagues/{league_id}"
    headers   = {'Cookie': f'espn_s2={ESPN_S2}; SWID={ESPN_SWID}'}

    ratings: Dict[str, Dict] = {}

    # Fetch multiple pages (50 players per page)
    for offset in range(0, 1000, 50):
        params = {
            'view': 'kona_player_info',
            'scoringPeriodId': 0,
            'offset': offset,
        }
        data = _make_request(url, params=params, headers=headers)
        if not data:
            break

        players_raw = data.get('players', [])
        if not players_raw:
            break

        for entry in players_raw:
            player_info = entry.get('player', {})
            name = player_info.get('fullName', '').lower().strip()
            if not name:
                continue

            ownership = player_info.get('ownership', {})
            draft_ranks = entry.get('draftRanksByRankType', {})
            roto_rank = draft_ranks.get('ROTO', {}).get('rank')

            ratings[name] = {
                'percent_owned':   ownership.get('percentOwned', 0.0),
                'percent_started': ownership.get('percentStarted', 0.0),
                'espn_draft_rank': roto_rank,
            }

        # If fewer than 50 returned, we've hit the end
        if len(players_raw) < 50:
            break

    if ratings:
        print(f"  [ESPN] Loaded ownership data for {len(ratings)} players")
    else:
        print("  [ESPN] No player data returned — credentials may be expired")
    return ratings


def test_api_connectivity() -> bool:
    """Returns True if both ESPN and MLB Stats APIs respond successfully."""
    print("Testing API connectivity...")

    league_id = LEAGUE_CONFIG['league_id']
    season = LEAGUE_CONFIG['season']

    print("  ESPN Fantasy API...", end=" ")
    espn_url = (
        f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb"
        f"/seasons/{season}/segments/0/leagues/{league_id}"
    )
    espn_ok = _make_request(espn_url, {'view': 'mRoster'}) is not None
    print("OK" if espn_ok else "FAILED")
    if not espn_ok:
        return False

    print("  MLB Stats API...", end=" ")
    mlb_ok = _make_request(
        'https://statsapi.mlb.com/api/v1/stats',
        {'group': 'hitting', 'season': season, 'stats': 'season'},
    ) is not None
    print("OK" if mlb_ok else "FAILED")
    return mlb_ok
