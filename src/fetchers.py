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
    ESPN_LINEUP_SLOT_MAP, ESPN_PRIMARY_SLOTS, ESPN_INACTIVE_SLOT_IDS,
    ESPN_S2, ESPN_SWID,
    ESPN_PRO_TEAM_MAP,
)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _safe_float(val, default=0.0) -> float:
    """Convert a value to float, returning default if empty or non-numeric (e.g. '-.--')."""
    try:
        return float(val) if val else default
    except (TypeError, ValueError):
        return default


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
    Extracts:
      - defaultPositionId  → position (SP/RP/C/1B/etc.)
      - lineupSlotId       → lineup_slot (current roster slot: SS, BE, SP, etc.)
      - eligibleSlots      → eligible_positions (all real positions player can fill)
      - injuryStatus       → injury_status
    """
    player_pool = entry.get('playerPoolEntry', {})
    player = player_pool.get('player', {})

    espn_id = player.get('id')
    if not espn_id:
        return None

    # Default position (SP/RP/C/1B/etc.) — correct source for pitcher SP vs RP
    pos_id = player.get('defaultPositionId', 0)
    raw_position = ESPN_POSITION_MAP.get(pos_id, 'UNKNOWN')
    position = _normalize_position(raw_position)
    is_pitcher = pos_id in PITCHER_POSITION_IDS

    # Current lineup slot (where this player is sitting in the lineup right now)
    lineup_slot_id = entry.get('lineupSlotId', 15)  # default 15 = BE
    lineup_slot = ESPN_LINEUP_SLOT_MAP.get(lineup_slot_id, f'SLOT{lineup_slot_id}')
    is_active_lineup = lineup_slot_id not in ESPN_INACTIVE_SLOT_IDS

    # Eligible positions — all real positions this player can fill
    # (excludes utility/flex/bench slots; used for display in roster tables)
    eligible_slot_ids = player.get('eligibleSlots', [])
    seen: set = set()
    eligible_positions: List[str] = []
    for sid in eligible_slot_ids:
        name = ESPN_LINEUP_SLOT_MAP.get(sid, '')
        if name in ESPN_PRIMARY_SLOTS and name not in seen:
            eligible_positions.append(name)
            seen.add(name)
    # Fallback: if none found, use the default position
    if not eligible_positions:
        eligible_positions = [position] if position not in ('UNKNOWN', 'UTIL') else []

    # Injury status from ESPN
    # NOTE: ESPN frequently returns 'N/A' for injuryStatus even for IL players.
    # Fall back to lineup slot detection: slots 17/18/19 are IL slots.
    IL_SLOT_IDS = {17, 18, 19}
    injury_status = player_pool.get('injuryStatus', 'ACTIVE') or 'ACTIVE'
    is_injured = injury_status in INJURED_STATUSES or lineup_slot_id in IL_SLOT_IDS
    is_questionable = injury_status in QUESTIONABLE_STATUSES

    return {
        'espn_id':           espn_id,
        'id':                espn_id,
        'name':              player.get('fullName', 'Unknown'),
        'position':          position,           # default position (SP/RP/C/1B…)
        'position_id':       pos_id,
        'eligible_positions': eligible_positions, # all fillable positions
        'lineup_slot':       lineup_slot,         # current roster slot
        'lineup_slot_id':    lineup_slot_id,
        'is_active_lineup':  is_active_lineup,    # True if not BE/IL
        'is_pitcher':        is_pitcher,
        'team_id':           team_id,
        'team_name':         team_name,
        'is_my_player':      team_id == my_team_id,
        'ownership_pct':     player_pool.get('percentOwned', 0.0),
        'pro_team_id':       player.get('proTeamId'),
        'pro_team_abbrev':   ESPN_PRO_TEAM_MAP.get(player.get('proTeamId'), ''),
        'injury_status':     injury_status,
        'is_injured':        is_injured,
        'is_questionable':   is_questionable,
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
        import math
        result = {}
        for stat_id, stat_data in score_by_stat.items():
            cat = ESPN_STAT_IDS.get(str(stat_id))
            if cat:
                val = stat_data.get('score')
                if val is not None:
                    float_val = float(val)
                    # ESPN returns Infinity for ERA/WHIP when no innings pitched yet — skip
                    if math.isinf(float_val) or math.isnan(float_val):
                        continue
                    result[cat] = round(float_val, 4)
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
        'games_played': stats.get('gamesPlayed', 0) or 0,   # appearances / games pitched
        'innings_pitched': float(stats['inningsPitched']) if stats.get('inningsPitched') else 0.0,
        'earned_runs': stats.get('earnedRuns', 0) or 0,
        'era': _safe_float(stats.get('era')),
        'whip': _safe_float(stats.get('whip')),
        'strikeouts': ks,
        'strikeouts_pitch': ks,
        'wins': stats.get('wins', 0) or 0,
        'losses': stats.get('losses', 0) or 0,
        'saves': saves,
        'holds': holds,
        'sv_hd': saves + holds,
        'quality_starts': stats.get('qualityStarts', 0) or 0,
        'hits': stats.get('hits', 0) or 0,           # hits allowed
        'walks': stats.get('baseOnBalls', 0) or 0,   # walks issued (BB)
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
# ESPN Transaction History
# ---------------------------------------------------------------------------

# Module-level cache so repeated calls in one run don't re-hit the API
_player_name_cache: Dict[int, str] = {}


def _resolve_player_name(player_id: int) -> str:
    """Look up a player's full name from ESPN by espn_player_id."""
    if player_id in _player_name_cache:
        return _player_name_cache[player_id]
    season = LEAGUE_CONFIG['season']
    url = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb"
           f"/seasons/{season}/players/{player_id}")
    try:
        r = requests.get(url, params={'view': 'players_wl'},
                         headers={'Accept': 'application/json'}, timeout=8)
        name = r.json().get('fullName', str(player_id)) if r.status_code == 200 else str(player_id)
    except Exception:
        name = str(player_id)
    _player_name_cache[player_id] = name
    return name


def fetch_all_transactions(scoring_period_id: int, all_rosters: Dict) -> List[Dict]:
    """
    Fetch all FREEAGENT / WAIVER / TRADE transactions across all scoring periods.

    Loops scoring period 1 → scoring_period_id, deduplicating by ESPN UUID.
    Returns list of decoded transaction dicts with resolved player names.
    """
    from datetime import datetime as _dt

    league_id = LEAGUE_CONFIG['league_id']
    season    = LEAGUE_CONFIG['season']
    url       = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb"
                 f"/seasons/{season}/segments/0/leagues/{league_id}")
    headers   = {'Accept': 'application/json'}

    # Build name cache from current roster data (covers most players)
    for tid, tdata in all_rosters.items():
        for p in tdata.get('players', []):
            pid = p.get('espn_id')
            if pid and p.get('name'):
                _player_name_cache[pid] = p['name']

    # Build team name lookup
    team_map: Dict[int, str] = {td: tdata.get('team_name', f'Team {td}')
                                 for td, tdata in all_rosters.items()}
    team_map[0] = 'FA Pool'

    seen_ids: set = set()
    transactions: List[Dict] = []

    for period in range(1, scoring_period_id + 1):
        try:
            r = requests.get(url, params={'view': 'mTransactions2', 'scoringPeriodId': period},
                             headers=headers, timeout=12)
            if r.status_code != 200:
                continue
            raw_txns = r.json().get('transactions', [])
        except Exception:
            continue

        for t in raw_txns:
            txn_id = t.get('id')
            if not txn_id or txn_id in seen_ids:
                continue
            if t.get('isPending', False):
                continue
            txn_type = t.get('type', '')
            if txn_type not in ('FREEAGENT', 'WAIVER', 'TRADE'):
                continue

            seen_ids.add(txn_id)

            # Resolve items
            items = []
            for item in t.get('items', []):
                action    = item.get('type', '')  # ADD or DROP
                player_id = item.get('playerId')
                if action not in ('ADD', 'DROP') or not player_id:
                    continue
                items.append({
                    'action':      action,
                    'player_id':   player_id,
                    'player_name': _player_name_cache.get(player_id)
                                   or _resolve_player_name(player_id),
                })

            team_id = t.get('teamId', 0)
            ms      = t.get('proposedDate', 0)
            date_str = _dt.fromtimestamp(ms / 1000).strftime('%Y-%m-%d') if ms else ''

            transactions.append({
                'id':                txn_id,
                'txn_type':          txn_type,
                'status':            t.get('status', 'EXECUTED'),
                'team_id':           team_id,
                'team_name':         team_map.get(team_id, f'Team {team_id}'),
                'scoring_period_id': t.get('scoringPeriodId', period),
                'proposed_date':     date_str,
                'items':             items,
            })

        time.sleep(0.15)  # polite rate limiting

    return sorted(transactions, key=lambda x: x.get('proposed_date', ''))


def apply_transaction_flags(
    all_rosters: Dict,
    transactions: List[Dict],
    lag_days: int = 2,
) -> None:
    """
    Cross-reference ESPN roster data with recent transactions to flag
    API-lag cases: player shows on roster but has a recent DROP transaction.

    Mutates player dicts in all_rosters in place.
    """
    from datetime import datetime as _dt, timedelta

    cutoff = (_dt.now() - timedelta(days=lag_days)).strftime('%Y-%m-%d')
    recent = [t for t in transactions if t.get('proposed_date', '') >= cutoff]

    # Build: player_id → {action, team_id, date}
    recent_moves: Dict[int, Dict] = {}
    for t in sorted(recent, key=lambda x: x.get('proposed_date', '')):
        for item in t.get('items', []):
            pid = item.get('player_id')
            if pid:
                recent_moves[pid] = {
                    'action':    item['action'],
                    'team_id':   t['team_id'],
                    'team_name': t['team_name'],
                    'date':      t['proposed_date'],
                }

    for tid, tdata in all_rosters.items():
        for player in tdata.get('players', []):
            pid = player.get('espn_id')
            if not pid:
                continue
            move = recent_moves.get(pid)
            if move and move['action'] == 'DROP' and move['team_id'] == tid:
                player['pending_drop'] = True
            elif move and move['action'] == 'ADD' and move['team_id'] == tid:
                player['pending_add'] = True


def get_recently_dropped_ids(transactions: List[Dict], days: int = 3) -> set:
    """
    Return set of ESPN player_ids that have a DROP transaction in the last N days.
    Used to tag FA players as 'recently available' in waiver analysis.
    """
    from datetime import datetime as _dt, timedelta
    cutoff = (_dt.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    dropped: set = set()
    for t in transactions:
        if t.get('proposed_date', '') >= cutoff:
            for item in t.get('items', []):
                if item.get('action') == 'DROP':
                    dropped.add(item['player_id'])
    return dropped


# ---------------------------------------------------------------------------
# MLB Schedule API — two-start pitchers
# ---------------------------------------------------------------------------

def _format_game_time_et(game_date_utc: str) -> str:
    """Convert UTC ISO game time to Eastern Time display string, e.g. '7:05 PM'."""
    if not game_date_utc:
        return 'TBD'
    try:
        from datetime import datetime, timedelta
        dt = datetime.fromisoformat(game_date_utc.replace('Z', '+00:00'))
        et = dt - timedelta(hours=4)          # Baseball season = EDT = UTC-4
        hour = et.hour % 12 or 12
        ampm = 'AM' if et.hour < 12 else 'PM'
        return f'{hour}:{et.minute:02d} {ampm}'
    except Exception:
        return 'TBD'


def fetch_weekly_schedule() -> Dict[str, List[Dict]]:
    """
    Fetch the MLB game schedule for the current fantasy week (Mon-Sun).

    Returns:
        {'Mon Apr 21': [game_dicts], 'Tue Apr 22': [...], ...}
        Each game_dict: away, home, awayR, homeR, time, status, awaySP, homeSP
    """
    week_start, week_end = _get_week_dates()
    print(f"  Fetching weekly MLB schedule ({week_start} to {week_end})...", end=" ", flush=True)

    response = _make_request(
        'https://statsapi.mlb.com/api/v1/schedule',
        params={
            'sportId': 1,
            'startDate': week_start,
            'endDate': week_end,
            'gameType': 'R',
            'hydrate': 'probablePitcher,linescore,team',
        }
    )

    if not response:
        print("(failed)")
        return {}

    result: Dict[str, List] = {}
    total_games = 0

    for date_entry in response.get('dates', []):
        date_str = date_entry.get('date', '')
        try:
            from datetime import datetime as _dt
            d = _dt.strptime(date_str, '%Y-%m-%d')
            day_label = f"{d.strftime('%a')} {d.strftime('%b')} {d.day}"
        except ValueError:
            continue

        games = []
        for game in date_entry.get('games', []):
            teams    = game.get('teams', {})
            away_d   = teams.get('away', {})
            home_d   = teams.get('home', {})

            away_abbr = away_d.get('team', {}).get('abbreviation', '???')
            home_abbr = home_d.get('team', {}).get('abbreviation', '???')
            # Normalise OAK → ATH (ESPN uses ATH)
            away_abbr = 'ATH' if away_abbr == 'OAK' else away_abbr
            home_abbr = 'ATH' if home_abbr == 'OAK' else home_abbr

            state = game.get('status', {}).get('abstractGameState', 'Preview')
            status = 'live' if state == 'Live' else ('final' if state == 'Final' else 'preview')

            away_score = away_d.get('score')
            home_score = home_d.get('score')

            away_sp = (away_d.get('probablePitcher') or {}).get('fullName') or 'TBD'
            home_sp = (home_d.get('probablePitcher') or {}).get('fullName') or 'TBD'

            games.append({
                'away':   away_abbr,
                'home':   home_abbr,
                'awayR':  away_score,
                'homeR':  home_score,
                'time':   _format_game_time_et(game.get('gameDate', '')),
                'status': status,
                'awaySP': away_sp,
                'homeSP': home_sp,
            })
            total_games += 1

        if games:
            result[day_label] = games

    print(f"({total_games} games across {len(result)} days)")
    return result


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

def fetch_espn_projections_and_ownership() -> Dict[str, Dict]:
    """
    Fetch ESPN rest-of-season projections + ownership % for all players.
    Requires espn_s2 / SWID cookies (espn_credentials.py).

    ESPN allows up to 500 players per call, so 2 calls covers all ~850 players.

    Projection stat IDs (confirmed against live API):
      Hitters:  R=20, HR=23, RBI=21, SB=5,  OBP=17
      Pitchers: K=48, QS=63, ERA=47, WHIP=41, SVHD=83

    Returns {name_lower: {
        percent_owned, percent_started,
        proj_runs, proj_home_runs, proj_rbis, proj_stolen_bases, proj_obp,
        proj_strikeouts, proj_quality_starts, proj_era, proj_whip, proj_sv_hd,
        is_pitcher (bool), position (str)
    }}
    """
    if not ESPN_S2 or not ESPN_SWID:
        return {}

    league_id = LEAGUE_CONFIG['league_id']
    season    = LEAGUE_CONFIG['season']
    url       = f"{API_CONFIG['espn_base_url']}/seasons/{season}/segments/0/leagues/{league_id}"
    headers   = {
        'Cookie':          f'espn_s2={ESPN_S2}; SWID={ESPN_SWID}',
        'User-Agent':      'Mozilla/5.0 (Fantasy Baseball Engine)',
        'Accept':          'application/json',
        'X-Fantasy-Source': 'kona',
    }

    # Stat ID → our internal key mapping (confirmed via live API)
    PROJ_STAT_MAP = {
        '20': 'proj_runs',
        '23': 'proj_home_runs',
        '21': 'proj_rbis',
        '5':  'proj_stolen_bases',
        '17': 'proj_obp',
        '48': 'proj_strikeouts',
        '63': 'proj_quality_starts',
        '47': 'proj_era',
        '41': 'proj_whip',
        '83': 'proj_sv_hd',
    }

    results: Dict[str, Dict] = {}

    for offset in range(0, 1500, 500):
        import json as _json
        fantasy_filter = _json.dumps({
            'players': {
                'filterStatus':  {'value': ['FREEAGENT', 'WAIVERS', 'ONTEAM']},
                'filterStatsForTopScoringPeriodIds': {
                    'value': 2,
                    'additionalValue': ['002026', '102026'],   # actual + projected
                },
                'sortAppliedStatTotal': {
                    'sortAsc': False, 'sortPriority': 1, 'value': '102026',
                },
                'limit':  500,
                'offset': offset,
            }
        })

        r = None
        try:
            import requests as _req
            resp = _req.get(
                url,
                params={'view': 'kona_player_info'},
                headers={**headers, 'X-Fantasy-Filter': fantasy_filter},
                timeout=API_CONFIG['request_timeout'],
            )
            resp.raise_for_status()
            r = resp.json()
        except Exception as e:
            print(f"  [ESPN Projections] Request failed at offset {offset}: {e}")
            break

        players_raw = r.get('players', []) if r else []
        if not players_raw:
            break

        for entry in players_raw:
            player_info = entry.get('player', {})
            name = player_info.get('fullName', '').lower().strip()
            if not name:
                continue

            default_pos_id  = player_info.get('defaultPositionId', 0)
            pos_str         = ESPN_POSITION_MAP.get(default_pos_id, 'UTIL')
            is_pitcher      = default_pos_id in PITCHER_POSITION_IDS

            ownership       = player_info.get('ownership', {})
            pct_owned       = ownership.get('percentOwned', 0.0)
            pct_started     = ownership.get('percentStarted', 0.0)

            # Find the projection stats entry (id='102026', statSourceId=1)
            proj_stats: Dict[str, float] = {}
            for stat_entry in player_info.get('stats', []):
                if stat_entry.get('id') == '102026':
                    raw = stat_entry.get('stats', {})
                    for sid, key in PROJ_STAT_MAP.items():
                        val = raw.get(sid)
                        if val is not None:
                            proj_stats[key] = round(float(val), 4)
                    break

            results[name] = {
                'percent_owned':   pct_owned,
                'percent_started': pct_started,
                'position':        pos_str,
                'is_pitcher':      is_pitcher,
                **proj_stats,
            }

        if len(players_raw) < 500:
            break

    if results:
        print(f"  [ESPN] Projections + ownership loaded for {len(results)} players")
    else:
        print("  [ESPN] No projection data — credentials may be expired")
    return results


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
