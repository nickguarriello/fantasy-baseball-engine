"""
Report Generator — Jinja2 HTML

Loads CSVs from outputs/, renders templates/report.html, writes docs/index.html.
GitHub Pages serves docs/index.html — accessible free from any phone.

To update layout/styling: edit templates/report.html only.
To add new data:          edit this file only.
"""

import csv
import json
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional

ROOT      = Path(__file__).parent.parent
OUTPUTS   = ROOT / "outputs"
TEMPLATES = ROOT / "templates"
DOCS      = ROOT / "docs"

MY_TEAM  = "Pitch Slap"
FA_LABEL = "FA"

_MLB_TEAM_ABBREV = {
    'Arizona Diamondbacks': 'ARI', 'Atlanta Braves': 'ATL',
    'Baltimore Orioles': 'BAL', 'Boston Red Sox': 'BOS',
    'Chicago Cubs': 'CHC', 'Chicago White Sox': 'CWS',
    'Cincinnati Reds': 'CIN', 'Cleveland Guardians': 'CLE',
    'Colorado Rockies': 'COL', 'Detroit Tigers': 'DET',
    'Houston Astros': 'HOU', 'Kansas City Royals': 'KC',
    'Los Angeles Angels': 'LAA', 'Los Angeles Dodgers': 'LAD',
    'Miami Marlins': 'MIA', 'Milwaukee Brewers': 'MIL',
    'Minnesota Twins': 'MIN', 'New York Mets': 'NYM',
    'New York Yankees': 'NYY', 'Oakland Athletics': 'OAK',
    'Philadelphia Phillies': 'PHI', 'Pittsburgh Pirates': 'PIT',
    'San Diego Padres': 'SD', 'San Francisco Giants': 'SF',
    'Seattle Mariners': 'SEA', 'St. Louis Cardinals': 'STL',
    'Tampa Bay Rays': 'TB', 'Texas Rangers': 'TEX',
    'Toronto Blue Jays': 'TOR', 'Washington Nationals': 'WSH',
    'Athletics': 'OAK',
}

# Valid display positions by player type
_HITTER_ELIGIBLE_SLOTS = {'C', '1B', '2B', '3B', 'SS', 'OF', 'DH', '2B/SS', '1B/3B', 'UTIL', 'IF'}
_PITCHER_ELIGIBLE_SLOTS = {'SP', 'RP'}
_PITCHER_LINEUP_SLOTS   = {'SP', 'RP', 'P'}

# ESPN lineup slot sort order — matches user's preferred roster display order
_SLOT_ORDER = {
    # Hitters (user spec: C, C, 1B, 3B, 1B/3B, 2B, SS, 2B/SS, OF×5, DH, UTIL×2)
    'C':     0,
    '1B':    1,
    '3B':    2,
    '1B/3B': 3,
    '2B':    4,
    'SS':    5,
    '2B/SS': 6,
    'OF':    7, 'LF': 7, 'CF': 7, 'RF': 7,
    'DH':    8,
    'UTIL':  9,
    # Pitchers (SP first, then RP/P, then bench)
    'SP':    10,
    'P':     11,
    'RP':    12,
    'BE':    13, 'BN': 13, 'BENCH': 13,
    'IL':    14, 'IR': 14, 'NA': 14,
}

# ESPN roster position display order (for My Roster table)
_POS_ORDER = {
    'C': 0, '1B': 1, '2B': 2, 'SS': 3, '3B': 4,
    'OF': 5, 'CF': 5, 'LF': 5, 'RF': 5,
    'DH': 6, 'UTIL': 7,
    'SP': 8, 'RP': 9, 'P': 10,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(filename: str) -> List[Dict]:
    p = OUTPUTS / filename
    if not p.exists():
        return []
    try:
        with open(p, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def _z_class(val) -> str:
    """CSS class name for a z-score value."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return "z-na"
    if v >= 1.5:  return "z-great"
    if v >= 0.5:  return "z-good"
    if v >= 0.0:  return "z-ok"
    if v >= -0.5: return "z-bad"
    return "z-terrible"


def _fmt(val, decimals=2, fallback="—") -> str:
    """Format a numeric value; return fallback if empty/null."""
    if val in (None, "", "None", "nan"):
        return fallback
    try:
        return f"{float(val):.{decimals}f}"
    except (TypeError, ValueError):
        return str(val) if val else fallback


def _fmt_stat(val, cat: str, fallback="—") -> str:
    """Category-aware stat formatting: whole numbers, OBP as .333, ERA/WHIP as 1.25."""
    if val in (None, "", "None", "nan"):
        return fallback
    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val) if val else fallback
    if cat == "OBP":
        s = f"{v:.3f}"
        return s[1:] if s.startswith("0") else s   # .333 not 0.333
    elif cat in ("ERA", "WHIP"):
        return f"{v:.2f}"
    else:
        return str(int(round(v)))


def _team_abbrev(name: str) -> str:
    return _MLB_TEAM_ABBREV.get(name, name[:3].upper() if name else '')


def _fmt_avg(val, fallback="—") -> str:
    """Format batting average as .311 (no leading zero, 3 decimals)."""
    if val in (None, "", "None", "nan"):
        return fallback
    try:
        s = f"{float(val):.3f}"
        return s[1:] if s.startswith("0") else s
    except (TypeError, ValueError):
        return fallback


def _rec_cls(rec: str) -> str:
    r = rec.upper()
    if 'DO NOT START' in r: return 'sit'
    if 'START' in r:        return 'start'
    if 'CONSIDER' in r:     return 'consider'
    return 'borderline'


def _pct(val, fallback="—") -> str:
    if val in (None, "", "None", "nan"):
        return fallback
    try:
        return f"{float(val):.1f}%"
    except (TypeError, ValueError):
        return fallback


def _fmt_eligible(raw: str) -> str:
    """Parse eligible_positions like "['2B', 'SS']" → "2B, SS"."""
    if not raw or str(raw) in ('', 'None', 'nan', '[]'):
        return ''
    s = str(raw).strip("[] ").replace("'", "").replace('"', '')
    return ', '.join(p.strip() for p in s.split(',') if p.strip())


def _slot_sort(slot: str) -> int:
    return _SLOT_ORDER.get(str(slot).upper(), 99)


def _pos_sort(pos: str) -> int:
    return _POS_ORDER.get(str(pos).upper(), 50)


def _slot_badge(slot: str, is_active: bool) -> str:
    """Badge label for a lineup slot."""
    s = str(slot).upper()
    if s in ('BE', 'BN'):
        return 'BENCH'
    if s in ('IL', 'IR'):
        return 'IL'
    return slot.upper() if slot else ('ACTIVE' if is_active else 'BENCH')


def _slot_badge_cls(slot: str, is_active: bool) -> str:
    """CSS class for the slot badge."""
    s = str(slot).upper()
    if s in ('IL', 'IR'):
        return 'badge-il'
    if s in ('BE', 'BN') or not is_active:
        return 'badge-bench'
    return 'badge-active'


def _pitcher_pos(pos: str) -> str:
    """Normalize pitcher position to SP/RP — generic P falls back to RP."""
    p = str(pos).upper()
    if p == 'SP':  return 'SP'
    if p == 'RP':  return 'RP'
    return 'RP'   # P or unknown → RP (generic relievers default to RP)


# ---------------------------------------------------------------------------
# Rank computation helpers (R3-R5)
# ---------------------------------------------------------------------------

def _pos_group(p: Dict) -> str:
    """Map a player's position to their ranking group."""
    pos = str(p.get('position', '')).upper()
    is_pitcher = str(p.get('is_pitcher', '')).lower() in ('true', '1')
    if is_pitcher:
        return 'SP' if pos == 'SP' else 'RP'
    if pos == 'C':                       return 'C'
    if pos in ('1B', '3B'):              return '1B3B'
    if pos in ('2B', 'SS'):              return '2BSS'
    if pos in ('OF', 'LF', 'CF', 'RF'): return 'OF'
    if pos == 'DH':                      return 'DH'
    return 'OTHER'


def _compute_rank_maps(research: List[Dict]) -> Dict[str, Dict]:
    """
    Compute position-group ranks (for 4 z-score windows) and total-pool ranks.
    Returns {name_lower: {pos_7: N, pos_14: N, pos_30: N, pos_ssn: N, tot: N}}
    """
    def _z(p, field):
        try:
            v = p.get(field)
            return float(v) if v not in (None, '', 'None', 'nan') else -99.0
        except (TypeError, ValueError):
            return -99.0

    windows = [
        ('pos_7',   'z_7day'),
        ('pos_14',  'z_14day'),
        ('pos_30',  'z_30day'),
        ('pos_ssn', 'z_season'),
    ]

    rank_map: Dict[str, Dict] = {}

    # Position-group ranks per window
    for rank_key, z_field in windows:
        groups: Dict[str, List] = {}
        for p in research:
            g = _pos_group(p)
            groups.setdefault(g, []).append(p)
        for g, players in groups.items():
            for rank, p in enumerate(sorted(players, key=lambda x: _z(x, z_field), reverse=True), 1):
                key = p.get('name', '').lower().strip()
                if key:
                    rank_map.setdefault(key, {})[rank_key] = rank

    # Total-pool ranks (by z_season)
    batters   = sorted([p for p in research
                        if str(p.get('is_pitcher', '')).lower() not in ('true', '1')],
                       key=lambda x: _z(x, 'z_season'), reverse=True)
    starters  = sorted([p for p in research
                        if str(p.get('is_pitcher', '')).lower() in ('true', '1')
                        and str(p.get('position', '')).upper() == 'SP'],
                       key=lambda x: _z(x, 'z_season'), reverse=True)
    relievers = sorted([p for p in research
                        if str(p.get('is_pitcher', '')).lower() in ('true', '1')
                        and str(p.get('position', '')).upper() != 'SP'],
                       key=lambda x: _z(x, 'z_season'), reverse=True)

    for pool in (batters, starters, relievers):
        for rank, p in enumerate(pool, 1):
            key = p.get('name', '').lower().strip()
            if key:
                rank_map.setdefault(key, {})['tot'] = rank

    # Per-group season ranks (for Option B multi-position best-rank lookup)
    group_ssn_groups: Dict[str, List] = {}
    for p in research:
        g = _pos_group(p)
        group_ssn_groups.setdefault(g, []).append(p)
    for g, players in group_ssn_groups.items():
        for rank, p in enumerate(sorted(players, key=lambda x: _z(x, 'z_season'), reverse=True), 1):
            key = p.get('name', '').lower().strip()
            if key:
                rank_map.setdefault(key, {}).setdefault('group_ranks', {})[g] = rank

    return rank_map


def _rank_fmt(rank: int, bad_threshold: int = 30) -> str:
    """Format a rank number; show 'BAD' if above threshold."""
    if rank is None or rank >= 999:
        return '—'
    if rank > bad_threshold:
        return 'BAD'
    return str(rank)


def _rank_cls(rank: int, bad_threshold: int = 30) -> str:
    """CSS class for a rank number (lower = better)."""
    if rank is None or rank >= 999:
        return 'z-na'
    if bad_threshold == 150:
        # Total pool (bigger pool)
        if rank <= 10:  return 'z-great'
        if rank <= 30:  return 'z-good'
        if rank <= 60:  return 'z-ok'
        if rank <= 100: return 'z-bad'
        return 'z-terrible'
    else:
        # Position group
        if rank <= 3:   return 'z-great'
        if rank <= 8:   return 'z-good'
        if rank <= 15:  return 'z-ok'
        if rank <= 30:  return 'z-bad'
        return 'z-terrible'


# ---------------------------------------------------------------------------
# Build lineup lookup from lineup CSVs
# ---------------------------------------------------------------------------

def _build_lineup_lookup() -> Dict[str, Dict]:
    """
    Returns {name_lower: {lineup_slot, is_active, rec, is_two_start, injury}}
    from both lineup_hitters.csv and lineup_pitchers.csv.
    """
    lookup = {}
    for fname in ('lineup_hitters.csv', 'lineup_pitchers.csv'):
        for row in _load(fname):
            key = row.get('name', '').lower().strip()
            if not key:
                continue
            lookup[key] = {
                'lineup_slot':        row.get('lineup_slot', 'BE'),
                'is_active':          str(row.get('is_active_lineup', '')).lower() in ('true', '1'),
                'rec':                row.get('recommendation', ''),
                'is_two_start':       str(row.get('is_two_start', '')).lower() in ('true', '1'),
                'injury':             row.get('injury_status', ''),
                'eligible_positions': row.get('eligible_positions', ''),
                'espn_position':      row.get('position', ''),  # ESPN-authoritative SP/RP
            }
    return lookup


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------

_PITCHER_CATS = {'K', 'QS', 'ERA', 'WHIP', 'SVHD'}


def _build_matchup(actuals: List[Dict], breakdown: List[Dict]) -> Dict:
    if not actuals:
        return {"available": False}

    opp_name = "Opponent"
    if breakdown:
        winners = [r.get("projected_winner", "") for r in breakdown
                   if r.get("projected_winner") not in ("ME", "TOSS-UP", "UNKNOWN", "")]
        if winners:
            opp_name = max(set(winners), key=winners.count)

    wins   = sum(1 for r in actuals if r.get("actual_leader") == "ME")
    losses = sum(1 for r in actuals if r.get("actual_leader") == "OPP")
    ties   = len(actuals) - wins - losses

    # Week number: season started 2026-03-31 (Week 1 = Mar 31–Apr 5)
    today = date.today()
    season_start = date(2026, 3, 31)
    week_num = max(1, (today - season_start).days // 7 + 1)

    # Build a lookup of breakdown data keyed by category
    breakdown_map = {r.get('category', ''): r for r in breakdown}

    rows = []
    prev_was_pitcher = False
    for r in actuals:
        cat    = r.get("category", "")
        leader = r.get("actual_leader", "")
        is_pitcher_cat = cat in _PITCHER_CATS
        separator = is_pitcher_cat and not prev_was_pitcher and bool(rows)
        prev_was_pitcher = is_pitcher_cat

        bd = breakdown_map.get(cat, {})
        proj_winner = bd.get('projected_winner', '—')
        # Simple booleans: who was projected to win? (⚡ icon left of their score)
        proj_me  = proj_winner == 'ME'
        proj_opp = proj_winner not in ('ME', 'TOSS-UP', 'UNKNOWN', '', '—')

        rows.append({
            "category":  cat,
            "my_score":  _fmt_stat(r.get("my_actual"),  cat),
            "opp_score": _fmt_stat(r.get("opp_actual"), cat),
            "proj_me":   proj_me,
            "proj_opp":  proj_opp,
            "_row_cls":  "win" if leader == "ME" else ("loss" if leader == "OPP" else "tie"),
            "_separator": separator,
        })

    return {
        "available": True,
        "my_team":   MY_TEAM,
        "opp_name":  opp_name,
        "week_num":  week_num,
        "wins":      wins,
        "losses":    losses,
        "ties":      ties,
        "rows":      rows,
    }


def _build_my_roster(research: List[Dict], lineup_lookup: Dict) -> Dict:
    """
    Current-week roster view. Uses research_players for real position/stats,
    lineup lookup for active/bench slot. Sorted by ESPN slot order.
    """
    # Compute ranks across ALL tracked players (R3-R5)
    rank_maps = _compute_rank_maps(research)

    my_players_raw = [r for r in research if r.get("fantasy_team") == MY_TEAM]
    # Deduplicate by name: two MLB players can share a name (e.g., two "Max Muncy"s).
    # Keep the one that matches the lineup_lookup (has slot data), or highest games_played.
    seen_names: Dict[str, Dict] = {}
    for p in my_players_raw:
        n = p.get('name', '').lower().strip()
        if n not in seen_names:
            seen_names[n] = p
        else:
            # Prefer the one that has a lineup_lookup entry
            existing_has_lu = n in lineup_lookup
            if existing_has_lu:
                pass  # keep existing
            else:
                # Prefer higher games played as tiebreaker
                try:
                    if int(p.get('games_played') or 0) > int(seen_names[n].get('games_played') or 0):
                        seen_names[n] = p
                except (ValueError, TypeError):
                    pass
    my_players = list(seen_names.values())

    def _proc(player):
        name = player.get('name', '')
        key  = name.lower().strip()
        lu   = lineup_lookup.get(key, {})
        slot = lu.get('lineup_slot', 'BE')
        is_active  = lu.get('is_active', False)
        is_pitcher = str(player.get('is_pitcher', '')).lower() in ('true', '1')
        # For pitchers: prefer ESPN position (SP/RP) from lineup CSV over MLB Stats API (which returns generic 'P')
        if is_pitcher:
            espn_pos = lu.get('espn_position', '')
            pos = _pitcher_pos(espn_pos) if espn_pos else _pitcher_pos(player.get('position', ''))
        else:
            pos = player.get('position', '')

        # Sanitize slot: hitters cannot occupy pitcher slots and vice versa
        if not is_pitcher and slot in _PITCHER_LINEUP_SLOTS:
            slot = 'BE'
            is_active = False

        # Eligible positions: pitchers just show SP or RP; hitters show filtered eligible slots
        if is_pitcher:
            eligible = pos  # SP or RP from defaultPositionId — clean and unambiguous
        else:
            elig_raw = lu.get('eligible_positions', '')
            if elig_raw:
                parsed = [p.strip() for p in _fmt_eligible(elig_raw).split(',') if p.strip()]
                filtered = [p for p in parsed if p in _HITTER_ELIGIBLE_SLOTS]
                eligible = ', '.join(filtered) if filtered else pos
            else:
                eligible = pos

        # Rec + action (merging Start/Sit logic)
        rec = lu.get('rec', '')
        inj = lu.get('injury', '')
        if inj and inj.upper() not in ('ACTIVE', '', 'NONE', 'NAN'):
            row_cls = 'injured'
        else:
            row_cls = _rec_cls(rec)

        if not is_active and rec in ('START', 'START (matchup need)'):
            action = 'PROMOTE'
        elif is_active and rec == 'BENCH':
            action = 'BENCH'
        else:
            action = ''

        # Ranks (R3-R5)
        rk = rank_maps.get(name.lower().strip(), {})
        r7   = rk.get('pos_7',   999)
        r14  = rk.get('pos_14',  999)
        r30  = rk.get('pos_30',  999)
        rssn = rk.get('pos_ssn', 999)
        rtot = rk.get('tot',     999)

        # Option B: use best rank across all eligible position groups (hitters only)
        if not is_pitcher:
            group_ranks = rk.get('group_ranks', {})
            if group_ranks:
                elig_raw = lu.get('eligible_positions', '')
                elig_groups = set()
                if elig_raw:
                    for ep in _fmt_eligible(elig_raw).split(','):
                        ep = ep.strip()
                        if ep:
                            g = _pos_group({'position': ep, 'is_pitcher': False})
                            if g != 'OTHER':
                                elig_groups.add(g)
                # Always include primary group
                elig_groups.add(_pos_group({'position': pos, 'is_pitcher': False}))
                best = min((group_ranks.get(g, 999) for g in elig_groups), default=rssn)
                if best < rssn:
                    rssn = best

        return {
            'name':        name,
            'position':    pos,
            'eligible':    eligible,
            'mlb_team':    _team_abbrev(player.get('mlb_team', '')),
            'slot':        slot,
            'slot_badge':  pos if is_pitcher else _slot_badge(slot, is_active),
            'slot_cls':    _slot_badge_cls(slot, is_active),
            'is_active':   is_active,
            'is_pitcher':  is_pitcher,
            'is_two_start': lu.get('is_two_start', False),
            'injury':      inj,
            'rec':         rec,
            'action':      action,
            'row_cls':     row_cls,
            # Hitter stats
            'games_played':   _fmt(player.get('games_played'), 0),
            'avg':            _fmt_avg(player.get('avg')),
            'obp':            _fmt_stat(player.get('obp'), 'OBP'),
            'runs':           _fmt(player.get('runs'), 0),
            'home_runs':      _fmt(player.get('home_runs'), 0),
            'rbis':           _fmt(player.get('rbis'), 0),
            'stolen_bases':   _fmt(player.get('stolen_bases'), 0),
            # Pitcher stats
            'games_pitched':   _fmt(player.get('games_played'), 0),
            'innings_pitched': _fmt(player.get('innings_pitched'), 1),
            'hits_allowed':    _fmt(player.get('hits'), 0),
            'walks':           _fmt(player.get('walks'), 0),
            'era':             _fmt_stat(player.get('era'), 'ERA'),
            'whip':            _fmt_stat(player.get('whip'), 'WHIP'),
            'strikeouts_p':    _fmt(player.get('strikeouts_pitch'), 0),
            'quality_starts':  _fmt(player.get('quality_starts'), 0),
            'saves':           _fmt(player.get('saves'), 0),
            'svhd':            _fmt((player.get('saves') or 0) + (player.get('holds') or 0), 0),
            'holds':           _fmt(player.get('holds'), 0),
            # Rank columns (replace z-score display — R3/R4/R5)
            'rank_7':    _rank_fmt(r7),
            'rank_14':   _rank_fmt(r14),
            'rank_30':   _rank_fmt(r30),
            'rank_ssn':  _rank_fmt(rssn),
            'rank_tot':  _rank_fmt(rtot, bad_threshold=150),
            '_cls_rank_7':   _rank_cls(r7),
            '_cls_rank_14':  _rank_cls(r14),
            '_cls_rank_30':  _rank_cls(r30),
            '_cls_rank_ssn': _rank_cls(rssn),
            '_cls_rank_tot': _rank_cls(rtot, bad_threshold=150),
            '_slot_sort':    _slot_sort(slot),
            '_pos_sort':     _pos_sort(pos),
        }

    all_players = [_proc(p) for p in my_players]
    all_players.sort(key=lambda p: p['_slot_sort'])

    hitters  = [p for p in all_players if not p['is_pitcher']]

    def _pitcher_sort(p):
        inactive  = 0 if p['is_active'] else 1
        pos_order = 0 if p['position'] == 'SP' else 1  # SP first, RP second
        # Use season rank (lower = better) — z_season no longer in player dict
        rk = p.get('rank_ssn', '999')
        try:
            r = int(rk) if rk not in ('BAD', '—', '') else 999
        except (TypeError, ValueError):
            r = 999
        return (inactive, pos_order, r)

    pitchers = sorted([p for p in all_players if p['is_pitcher']], key=_pitcher_sort)

    promote = [{'name': p['name'], 'pos': p['position']} for p in all_players if p.get('action') == 'PROMOTE']
    bench   = [{'name': p['name'], 'pos': p['position']} for p in all_players if p.get('action') == 'BENCH']
    changes_summary = {'promote': promote, 'bench': bench, 'has_changes': bool(promote or bench)}

    return {'hitters': hitters, 'pitchers': pitchers, 'changes_summary': changes_summary}


def _build_startsit(research: List[Dict], lineup_lookup: Dict) -> Dict:
    """
    Next-week lineup decisions. Pitchers first (SP/RP labels), then hitters.
    Shows active/bench badge, all z-scores + season stats.
    """
    my_players_raw = [r for r in research if r.get("fantasy_team") == MY_TEAM]
    # Deduplicate by name (handles same-name MLB players)
    seen_names_2: Dict[str, Dict] = {}
    for p in my_players_raw:
        n = p.get('name', '').lower().strip()
        if n not in seen_names_2:
            seen_names_2[n] = p
        else:
            try:
                if int(p.get('games_played') or 0) > int(seen_names_2[n].get('games_played') or 0):
                    seen_names_2[n] = p
            except (ValueError, TypeError):
                pass
    my_players = list(seen_names_2.values())

    def _proc(player):
        name = player.get('name', '')
        key  = name.lower().strip()
        lu   = lineup_lookup.get(key, {})
        slot = lu.get('lineup_slot', 'BE')
        is_active  = lu.get('is_active', False)
        is_pitcher = str(player.get('is_pitcher', '')).lower() in ('true', '1')
        pos = _pitcher_pos(player.get('position', '')) if is_pitcher else player.get('position', '')
        rec = lu.get('rec', '')
        inj = lu.get('injury', '')
        if inj and inj.upper() not in ('ACTIVE', '', 'NONE', 'NAN'):
            row_cls = 'injured'
        else:
            row_cls = _rec_cls(rec)

        # Action indicator: flag players whose bench/active status disagrees with rec
        if not is_active and rec in ('START', 'START (matchup need)'):
            action = 'PROMOTE'
        elif is_active and rec == 'BENCH':
            action = 'BENCH'
        else:
            action = ''

        return {
            'name':        name,
            'position':    pos,
            'slot':        slot,
            'slot_badge':  _slot_badge(slot, is_active),
            'slot_cls':    _slot_badge_cls(slot, is_active),
            'is_active':   is_active,
            'is_pitcher':  is_pitcher,
            'is_two_start': lu.get('is_two_start', False),
            'injury':      inj,
            'rec':         rec,
            'row_cls':     row_cls,
            'action':      action,
            # Hitter stats (season)
            'games_played':   _fmt(player.get('games_played'), 0),
            'avg':            _fmt(player.get('avg'), 3),
            'obp':            _fmt_stat(player.get('obp'), 'OBP'),
            'runs':           _fmt(player.get('runs'), 0),
            'home_runs':      _fmt(player.get('home_runs'), 0),
            'rbis':           _fmt(player.get('rbis'), 0),
            'stolen_bases':   _fmt(player.get('stolen_bases'), 0),
            # Pitcher stats (season)
            'innings_pitched': _fmt(player.get('innings_pitched'), 1),
            'era':             _fmt_stat(player.get('era'), 'ERA'),
            'whip':            _fmt_stat(player.get('whip'), 'WHIP'),
            'strikeouts_p':    _fmt(player.get('strikeouts_pitch'), 0),
            'quality_starts':  _fmt(player.get('quality_starts'), 0),
            'saves':           _fmt(player.get('saves'), 0),
            'holds':           _fmt(player.get('holds'), 0),
            # Z-scores
            'z_season': _fmt(player.get('z_season')),
            'z_7day':   _fmt(player.get('z_7day')),
            'z_14day':  _fmt(player.get('z_14day')),
            'z_30day':  _fmt(player.get('z_30day')),
            'trend':    player.get('trend_direction', ''),
            '_cls_z_season': _z_class(player.get('z_season')),
            '_cls_z_7day':   _z_class(player.get('z_7day')),
            '_cls_z_14day':  _z_class(player.get('z_14day')),
            '_cls_z_30day':  _z_class(player.get('z_30day')),
            '_slot_sort':    _slot_sort(slot),
        }

    all_players = [_proc(p) for p in my_players]
    pitchers = sorted([p for p in all_players if p['is_pitcher']],
                      key=lambda p: (p['_slot_sort'], -float(p['z_season']) if p['z_season'] != '—' else 99))
    hitters  = sorted([p for p in all_players if not p['is_pitcher']],
                      key=lambda p: (p['_slot_sort'], -float(p['z_season']) if p['z_season'] != '—' else 99))

    promote = [{'name': p['name'], 'pos': p['position']} for p in all_players if p.get('action') == 'PROMOTE']
    bench   = [{'name': p['name'], 'pos': p['position']} for p in all_players if p.get('action') == 'BENCH']
    changes_summary = {'promote': promote, 'bench': bench, 'has_changes': bool(promote or bench)}

    return {'pitchers': pitchers, 'hitters': hitters, 'changes_summary': changes_summary}


def _build_waiver(top: List[Dict], two_start: List[Dict], research: List[Dict]) -> Dict:
    def _proc(rows, limit=5):
        out = []
        for r in rows[:limit]:
            out.append({
                "name":       r.get("name", ""),
                "position":   r.get("position", ""),
                "mlb_team":   r.get("mlb_team", ""),
                "owned":      _pct(r.get("percent_owned")),
                "z_season":   _fmt(r.get("z_season")),
                "z_7day":     _fmt(r.get("z_7day")),
                "z_14day":    _fmt(r.get("z_14day")),
                "z_30day":    _fmt(r.get("z_30day")),
                "two_start":  str(r.get("is_two_start", "")).lower() in ("true", "1"),
                "injury":     r.get("injury_status", ""),
                "_cls_z_season": _z_class(r.get("z_season")),
                "_cls_z_7day":   _z_class(r.get("z_7day")),
            })
        return out

    # My roster for drop recommendations
    my_players = [r for r in research if r.get("fantasy_team") == MY_TEAM]
    my_with_z = [p for p in my_players
                 if p.get('z_season') not in (None, '', 'None', 'nan')]
    my_with_z.sort(key=lambda p: float(p.get('z_season', 0)))
    worst_overall = my_with_z[0] if my_with_z else None

    def _drop_info(player_or_none):
        if not player_or_none:
            return None
        return {
            'name':     player_or_none.get('name', '—'),
            'z_season': _fmt(player_or_none.get('z_season')),
        }

    # Build per-position sections for all 8 positions
    by_position = []
    for pos in ['C', '1B', '2B', 'SS', '3B', 'OF', 'SP', 'RP']:
        pos_players = _load(f'waiver_{pos.lower()}.csv')
        if not pos_players:
            continue

        # Worst at same position on my roster
        if pos == 'OF':
            pos_roster = [p for p in my_players if p.get('position', '') in ('OF', 'LF', 'CF', 'RF')]
        elif pos == 'RP':
            pos_roster = [p for p in my_players if p.get('position', '') in ('RP', 'P')]
        else:
            pos_roster = [p for p in my_players if p.get('position', '') == pos]
        pos_with_z = [p for p in pos_roster if p.get('z_season') not in (None, '', 'None', 'nan')]
        pos_with_z.sort(key=lambda p: float(p.get('z_season', 0)))

        by_position.append({
            'pos':        pos,
            'players':    _proc(pos_players, 5),
            'drop_pos':   _drop_info(pos_with_z[0] if pos_with_z else None),
            'drop_worst': _drop_info(worst_overall),
        })

    return {
        "top":         _proc(top, 10),
        "two_start":   _proc(two_start, 15),
        "by_position": by_position,
    }


def _build_trade(targets: List[Dict], chips: List[Dict]) -> Dict:
    # Per-team recommendations: one suggested trade per opposing team
    team_targets: Dict[str, list] = {}
    for t in targets:
        team = t.get('fantasy_team', '')
        if team and team != MY_TEAM:
            team_targets.setdefault(team, []).append(t)

    chips_sorted = sorted(chips, key=lambda p: float(p.get('z_season') or 0), reverse=True)
    best_chip = chips_sorted[0] if chips_sorted else None

    per_team = []
    for team in sorted(team_targets):
        best_target = max(team_targets[team],
                          key=lambda p: float(p.get('z_season') or 0),
                          default=None)
        if not best_target:
            continue
        chip_z = float(best_chip.get('z_season') or 0) if best_chip else 0.0
        tgt_z  = float(best_target.get('z_season') or 0)
        diff   = tgt_z - chip_z
        per_team.append({
            'team':      team,
            'give_name': best_chip.get('name', '—') if best_chip else '—',
            'give_pos':  best_chip.get('position', '') if best_chip else '',
            'give_z':    _fmt(best_chip.get('z_season')) if best_chip else '—',
            'get_name':  best_target.get('name', '—'),
            'get_pos':   best_target.get('position', ''),
            'get_z':     _fmt(best_target.get('z_season')),
            'my_gain':   f"+{diff:.2f}" if diff >= 0 else f"{diff:.2f}",
            '_give_cls': _z_class(best_chip.get('z_season') if best_chip else None),
            '_get_cls':  _z_class(best_target.get('z_season')),
        })

    # My chips reference list
    all_chips = []
    for c in chips_sorted[:10]:
        all_chips.append({
            'name':     c.get('name', ''),
            'position': c.get('position', ''),
            'z_season': _fmt(c.get('z_season')),
            '_cls':     _z_class(c.get('z_season')),
        })

    return {"per_team": per_team, "all_chips": all_chips}


def _build_rankings(research: List[Dict]) -> Dict:
    hitters  = [r for r in research if str(r.get("is_pitcher","")).lower() not in ("true","1")]
    pitchers = [r for r in research if str(r.get("is_pitcher","")).lower() in ("true","1")]

    def _proc(rows, limit=100):
        out = []
        for r in rows[:limit]:
            out.append({
                "name":         r.get("name", ""),
                "position":     r.get("position", ""),
                "mlb_team":     r.get("mlb_team", ""),
                "fantasy_team": r.get("fantasy_team", FA_LABEL),
                "owned":        _pct(r.get("percent_owned")),
                "z_season":     _fmt(r.get("z_season")),
                "z_7day":       _fmt(r.get("z_7day")),
                "proj_z":       _fmt(r.get("proj_z_season")),
                "trend":        r.get("trend_direction", ""),
                "_cls_z_season":  _z_class(r.get("z_season")),
                "_cls_z_7day":    _z_class(r.get("z_7day")),
                "_cls_proj_z":    _z_class(r.get("proj_z_season")),
                "_team_cls": "my-team" if r.get("fantasy_team") == MY_TEAM else (
                             "fa" if r.get("fantasy_team") in (FA_LABEL, "", None) else "other-team"),
            })
        return out
    return {"hitters": _proc(hitters), "pitchers": _proc(pitchers)}


# ---------------------------------------------------------------------------
# Activity feed builder
# ---------------------------------------------------------------------------

MY_TEAM_ID = 1   # ESPN team_id for Pitch Slap

def _fmt_date(date_str: str) -> str:
    """'2026-04-13' → 'Apr 13'"""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        return d.strftime('%b ') + str(d.day)
    except Exception:
        return date_str


def _build_activity(days: int = 21) -> Dict:
    """
    Pull recent league transactions from the DB and format for the report.
    Shows all FA/waiver/trade moves, newest first, grouped by date.
    My team's moves are flagged for highlight.
    """
    try:
        from src.database import get_transactions as _get_txns
    except ImportError:
        return {'available': False}

    txns = _get_txns(days=days)
    if not txns:
        return {'available': False, 'by_date': [], 'my_recent_summary': [], 'days': days}

    # My recent moves summary (last 7 actions by my team)
    my_txns = [t for t in txns if t.get('team_id') == MY_TEAM_ID]
    my_recent_summary = []
    for t in my_txns[:10]:
        for item in t.get('items', []):
            my_recent_summary.append({
                'date':        _fmt_date(t.get('proposed_date', '')),
                'action':      item.get('action', ''),
                'player_name': item.get('player_name', ''),
            })
            if len(my_recent_summary) >= 8:
                break
        if len(my_recent_summary) >= 8:
            break

    # Group all transactions by date (newest first)
    from collections import OrderedDict
    by_date_dict: Dict[str, List] = OrderedDict()
    for t in txns:
        d = t.get('proposed_date', '')
        if d not in by_date_dict:
            by_date_dict[d] = []
        adds  = [i['player_name'] for i in t.get('items', []) if i.get('action') == 'ADD']
        drops = [i['player_name'] for i in t.get('items', []) if i.get('action') == 'DROP']
        by_date_dict[d].append({
            'team_name':  t.get('team_name', '?'),
            'is_my_team': t.get('team_id') == MY_TEAM_ID,
            'adds':       adds,
            'drops':      drops,
            'txn_type':   t.get('txn_type', ''),
        })

    by_date = [
        {'date_label': _fmt_date(d), 'rows': rows}
        for d, rows in by_date_dict.items()
    ]

    return {
        'available':         True,
        'by_date':           by_date,
        'my_recent_summary': my_recent_summary,
        'days':              days,
    }


# ---------------------------------------------------------------------------
# Matchup Calendar builder
# ---------------------------------------------------------------------------

# Full 2026 season week skeleton — opponents updated live for current week
_SEASON_SCHEDULE = {
    1:  {'opp': '—', 'dates': 'Mar 31 – Apr 6',   'result': None, 'score': None},
    2:  {'opp': '—', 'dates': 'Apr 7 – Apr 13',   'result': None, 'score': None},
    3:  {'opp': '—', 'dates': 'Apr 14 – Apr 20',  'result': None, 'score': None},
    4:  {'opp': '—', 'dates': 'Apr 21 – Apr 27',  'result': None, 'score': None},
    5:  {'opp': '—', 'dates': 'Apr 28 – May 4',   'result': None, 'score': None},
    6:  {'opp': '—', 'dates': 'May 5 – May 11',   'result': None, 'score': None},
    7:  {'opp': '—', 'dates': 'May 12 – May 18',  'result': None, 'score': None},
    8:  {'opp': '—', 'dates': 'May 19 – May 25',  'result': None, 'score': None},
    9:  {'opp': '—', 'dates': 'May 26 – Jun 1',   'result': None, 'score': None},
    10: {'opp': '—', 'dates': 'Jun 2 – Jun 8',    'result': None, 'score': None},
    11: {'opp': '—', 'dates': 'Jun 9 – Jun 15',   'result': None, 'score': None},
    12: {'opp': '—', 'dates': 'Jun 16 – Jun 22',  'result': None, 'score': None},
    13: {'opp': '—', 'dates': 'Jun 23 – Jun 29',  'result': None, 'score': None},
    14: {'opp': '—', 'dates': 'Jun 30 – Jul 6',   'result': None, 'score': None},
    15: {'opp': '—', 'dates': 'Jul 7 – Jul 13',   'result': None, 'score': None},
    16: {'opp': '—', 'dates': 'Jul 14 – Jul 20',  'result': None, 'score': None},
    17: {'opp': '—', 'dates': 'Jul 21 – Jul 27',  'result': None, 'score': None},
    18: {'opp': '—', 'dates': 'Jul 28 – Aug 3',   'result': None, 'score': None},
    19: {'opp': '—', 'dates': 'Aug 4 – Aug 10',   'result': None, 'score': None},
    20: {'opp': '—', 'dates': 'Aug 11 – Aug 17',  'result': None, 'score': None},
    21: {'opp': 'TBD (Semifinal)',    'dates': 'Aug 18 – Aug 24', 'result': None, 'score': None, 'playoff': True},
    22: {'opp': 'TBD (Semifinal)',    'dates': 'Aug 25 – Aug 31', 'result': None, 'score': None, 'playoff': True},
    23: {'opp': 'TBD (Championship)', 'dates': 'Sep 1 – Sep 7',  'result': None, 'score': None, 'playoff': True},
}


def _build_games_today(research: List[Dict], lineup_lookup: Dict, opp_name: str, schedule: Dict) -> List[Dict]:
    """Today's MLB games with my/opponent player highlights."""
    today = date.today()
    today_key = f"{today.strftime('%a')} {today.strftime('%b')} {today.day}"
    games_raw = schedule.get(today_key, [])
    if not games_raw:
        return []

    # Build team → player list lookups (abbreviations)
    my_by_team: Dict[str, List] = {}
    opp_by_team: Dict[str, List] = {}
    for p in research:
        team = _team_abbrev(p.get('mlb_team', ''))
        name = p.get('name', '')
        lu   = lineup_lookup.get(name.lower().strip(), {})
        slot = lu.get('lineup_slot', 'BE')
        is_active = lu.get('is_active', False)
        entry = {'name': name, 'slot': slot, 'slot_cls': _slot_badge_cls(slot, is_active)}
        if p.get('fantasy_team') == MY_TEAM:
            my_by_team.setdefault(team, []).append(entry)
        elif opp_name and p.get('fantasy_team') == opp_name:
            opp_by_team.setdefault(team, []).append(entry)

    games = []
    for g in games_raw:
        away, home = g.get('away', ''), g.get('home', '')
        my_p   = my_by_team.get(away, []) + my_by_team.get(home, [])
        opp_p  = opp_by_team.get(away, []) + opp_by_team.get(home, [])
        away_s = g.get('awayR')
        home_s = g.get('homeR')
        games.append({
            'away':        away,
            'home':        home,
            'time':        g.get('time', ''),
            'status':      g.get('status', 'preview'),
            'away_sp':     g.get('awaySP', 'TBD'),
            'home_sp':     g.get('homeSP', 'TBD'),
            'score':       f"{away_s}\u2013{home_s}" if away_s is not None and home_s is not None else '',
            'my_players':  my_p,
            'opp_players': opp_p,
            'has_interest': bool(my_p or opp_p),
        })
    games.sort(key=lambda g: (not g['has_interest'], g['time'] or '99:99'))
    return games


def _build_matchup_calendar(research: List[Dict], matchup: Dict, schedule: Optional[Dict] = None) -> Dict:
    """
    Build context dict for docs/matchup-calendar.html.

    Fetches the current week's MLB schedule, cross-references both
    fantasy rosters against teams playing each day, and returns JSON-
    serialisable structures for the Jinja2 template to inject into JS.
    """
    # ── Rosters ──────────────────────────────────────────────────────────────
    ll        = _build_lineup_lookup()
    opp_name  = (matchup or {}).get('opp_name', '') if isinstance(matchup, dict) else ''

    def _to_cal(p: Dict, on_il: bool = False) -> Dict:
        return {
            'name': p.get('name', ''),
            'pos':  p.get('position', ''),
            'team': _team_abbrev(p.get('mlb_team', '')),
            'il':   on_il,
        }

    my_players = []
    for p in research:
        if p.get('fantasy_team') != MY_TEAM:
            continue
        key   = p.get('name', '').lower().strip()
        on_il = ll.get(key, {}).get('lineup_slot', '') == 'IL'
        my_players.append(_to_cal(p, on_il))

    opp_players = [_to_cal(p) for p in research if opp_name and p.get('fantasy_team') == opp_name]

    # ── Schedule ─────────────────────────────────────────────────────────────
    if schedule is None:
        try:
            from src.fetchers import fetch_weekly_schedule
        except ImportError:
            from fetchers import fetch_weekly_schedule  # type: ignore
        schedule = fetch_weekly_schedule()

    # Determine week number from current Monday relative to season start
    today      = date.today()
    monday     = today - timedelta(days=today.weekday())
    season_start = date(2026, 3, 31)          # Week 1 starts Mar 31
    week_num   = max(1, min(23, ((monday - season_start).days // 7) + 1))

    # ── MATCHUPS structure (all 23 weeks for dropdown) ────────────────────────
    import copy
    matchups_data = copy.deepcopy(_SEASON_SCHEDULE)
    if week_num in matchups_data:
        matchups_data[week_num]['opp'] = opp_name or '—'
        # Compute date label from live schedule
        if schedule:
            days = list(schedule.keys())
            if len(days) >= 2:
                first_parts = days[0].split()   # ['Mon', 'Apr', '21']
                last_parts  = days[-1].split()
                if len(first_parts) >= 3 and len(last_parts) >= 3:
                    matchups_data[week_num]['dates'] = (
                        f"{first_parts[1]} {first_parts[2]} – {last_parts[2]}"
                    )

    weeks_data = {week_num: {'days': schedule}} if schedule else {}

    return {
        'my_team':          MY_TEAM,
        'opp_name':         opp_name or 'Opponent',
        'current_week':     week_num,
        'matchups_json':    json.dumps(matchups_data),
        'weeks_json':       json.dumps(weeks_data),
        'my_players_json':  json.dumps(my_players),
        'opp_players_json': json.dumps(opp_players),
        'generated_at':     datetime.now().strftime('%Y-%m-%d %H:%M'),
    }


# ---------------------------------------------------------------------------
# Date-range stats helpers (R1 / Feature 3)
# ---------------------------------------------------------------------------

def _fetch_range_stats(start: str, end: str, label: str = '') -> Dict[str, Dict]:
    """Fetch MLB stats for a date range. Returns {name_lower: {formatted stats}}."""
    try:
        try:
            from src.fetchers import fetch_mlb_stats_range
        except ImportError:
            from fetchers import fetch_mlb_stats_range  # type: ignore
        raw = fetch_mlb_stats_range(start, end, label=label)
        result: Dict[str, Dict] = {}
        for stats in raw.values():
            name = stats.get('name', '')
            if not name:
                continue
            key = name.lower().strip()
            saves = stats.get('saves', 0) or 0
            holds = stats.get('holds', 0) or 0
            result[key] = {
                'g':    str(int(stats.get('games_played', 0) or 0)),
                'avg':  _fmt_avg(stats.get('avg')),
                'obp':  _fmt_stat(stats.get('obp'), 'OBP'),
                'r':    str(int(stats.get('runs', 0) or 0)),
                'hr':   str(int(stats.get('home_runs', 0) or 0)),
                'rbi':  str(int(stats.get('rbis', 0) or 0)),
                'sb':   str(int(stats.get('stolen_bases', 0) or 0)),
                'gp':   str(int(stats.get('games_played', 0) or 0)),
                'ip':   _fmt(stats.get('innings_pitched'), 1),
                'h':    str(int(stats.get('hits', 0) or 0)),
                'bb':   str(int(stats.get('walks', 0) or 0)),
                'era':  _fmt_stat(stats.get('era'), 'ERA'),
                'whip': _fmt_stat(stats.get('whip'), 'WHIP'),
                'k':    str(int(stats.get('strikeouts_pitch', 0) or 0)),
                'qs':   str(int(stats.get('quality_starts', 0) or 0)),
                'svhd': str(int(saves + holds)),
            }
        return result
    except Exception as e:
        print(f"  Stats [{label}] skipped: {e}")
        return {}


def _fetch_all_stat_windows() -> Dict[str, Dict]:
    """
    Fetch stats for all roster toggle windows at report time.
    Returns {'curr_week': {...}, 'last_week': {...}, '14d': {...}, '30d': {...}}
    """
    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    last_monday = monday - timedelta(days=7)
    last_sunday = monday - timedelta(days=1)
    d14 = today - timedelta(days=14)
    d30 = today - timedelta(days=30)

    windows: Dict[str, Dict] = {}
    if monday < today:
        windows['curr_week'] = _fetch_range_stats(
            monday.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'), 'curr_wk')
    else:
        windows['curr_week'] = {}

    windows['last_week'] = _fetch_range_stats(
        last_monday.strftime('%Y-%m-%d'), last_sunday.strftime('%Y-%m-%d'), 'last_wk')
    windows['14d'] = _fetch_range_stats(
        d14.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'), '14d')
    windows['30d'] = _fetch_range_stats(
        d30.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'), '30d')
    return windows


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

# Category display order and short labels for the standings table
_STANDINGS_CATS = [
    ('runs',          'R'),
    ('home_runs',     'HR'),
    ('rbis',          'RBI'),
    ('stolen_bases',  'SB'),
    ('obp',           'OBP'),
    ('strikeouts',    'K'),
    ('quality_starts','QS'),
    ('era',           'ERA'),
    ('whip',          'WHIP'),
    ('sv_hd',         'SVHD'),
]
_RATE_CATS = {'obp', 'era', 'whip'}


def _build_standings() -> Dict:
    """
    Fetch and format league standings for the template.

    Returns:
        {
            'teams': [{'team_name', 'wins', 'ties', 'losses', 'is_my_team',
                       'weeks_played', 'cats': [str, ...]}],
            'cat_headers': ['R','HR', ...],   # 10 headers
        }
    """
    try:
        try:
            from src.fetchers import fetch_espn_standings as _fes
        except ImportError:
            from fetchers import fetch_espn_standings as _fes  # type: ignore
        raw = _fes()
    except Exception:
        return {'teams': [], 'cat_headers': [c[1] for c in _STANDINGS_CATS]}

    teams = []
    for t in raw:
        cats = []
        ct = t.get('cat_totals', {})
        for cat_key, _ in _STANDINGS_CATS:
            val = ct.get(cat_key)
            if val is None:
                cats.append('—')
            elif cat_key == 'obp':
                cats.append(f"{val:.3f}")
            elif cat_key in ('era', 'whip'):
                cats.append(f"{val:.2f}")
            else:
                cats.append(str(val))
        teams.append({
            'team_name':    t['team_name'],
            'wins':         t['wins'],
            'ties':         t['ties'],
            'losses':       t['losses'],
            'is_my_team':   t['is_my_team'],
            'weeks_played': t['weeks_played'],
            'cats':         cats,
        })

    return {
        'teams':       teams,
        'cat_headers': [c[1] for c in _STANDINGS_CATS],
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_report() -> str:
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError:
        print("  jinja2 not installed — pip install jinja2")
        return ""

    research   = _load("research_players.csv")
    actuals    = _load("matchup_actuals_vs_projected.csv")
    breakdown  = _load("matchup_breakdown.csv")
    waiver_top = _load("waiver_wire_top.csv")
    two_start  = _load("waiver_two_start.csv")
    targets    = _load("trade_targets.csv")
    chips      = _load("trade_chips.csv")

    lineup_lookup = _build_lineup_lookup()

    # Build matchup first (to get opp_name for games_today)
    matchup_data = _build_matchup(actuals, breakdown)
    opp_name = matchup_data.get('opp_name', '')

    # Fetch schedule once — used by both games_today and matchup calendar
    try:
        try:
            from src.fetchers import fetch_weekly_schedule as _fws
        except ImportError:
            from fetchers import fetch_weekly_schedule as _fws  # type: ignore
        _schedule = _fws()
    except Exception:
        _schedule = {}

    games_today = _build_games_today(research, lineup_lookup, opp_name, _schedule)

    # Stat windows for roster toggle (Feature 3)
    stat_windows = _fetch_all_stat_windows()
    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    curr_week_label = f"{monday.strftime('%b')} {monday.day}–{today.day}"
    last_week_label = (
        f"{(monday - timedelta(7)).strftime('%b')} "
        f"{(monday - timedelta(7)).day}–{(monday - timedelta(1)).day}"
    )

    context = {
        "generated_at":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "my_team":           MY_TEAM,
        "matchup":           matchup_data,
        "games_today":       games_today,
        "standings":         _build_standings(),
        "my_roster":         _build_my_roster(research, lineup_lookup),
        "startsit":          _build_startsit(research, lineup_lookup),
        "waiver":            _build_waiver(waiver_top, two_start, research),
        "trade":             _build_trade(targets, chips),
        "rankings":          _build_rankings(research),
        "activity":          _build_activity(),
        "stat_windows_json": json.dumps(stat_windows),
        "curr_week_label":   curr_week_label,
        "last_week_label":   last_week_label,
    }

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )

    # ── Main dashboard ────────────────────────────────────────────────────────
    template = env.get_template("report.html")
    html = template.render(**context)
    DOCS.mkdir(parents=True, exist_ok=True)
    out_path = DOCS / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"    report.html → docs/index.html ({len(html)//1024}KB)")

    # ── Matchup calendar ─────────────────────────────────────────────────────
    try:
        cal_context  = _build_matchup_calendar(research, context.get("matchup", {}), schedule=_schedule)
        cal_template = env.get_template("matchup_calendar.html")
        cal_html     = cal_template.render(**cal_context)
        cal_path     = DOCS / "matchup-calendar.html"
        cal_path.write_text(cal_html, encoding="utf-8")
        print(f"    matchup_calendar.html → docs/matchup-calendar.html ({len(cal_html)//1024}KB)")
    except Exception as e:
        print(f"    matchup-calendar.html skipped: {e}")

    return str(out_path)
