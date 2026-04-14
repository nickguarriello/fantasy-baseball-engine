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
        if proj_winner == 'ME':
            proj_display = MY_TEAM
            proj_cls = 'win'
        elif proj_winner in ('TOSS-UP', 'UNKNOWN', ''):
            proj_display = 'Toss-Up'
            proj_cls = 'tie'
        else:
            proj_display = proj_winner
            proj_cls = 'loss'

        if leader == 'ME':
            live_display = MY_TEAM
            live_cls = 'win'
        elif leader == 'OPP':
            live_display = opp_name
            live_cls = 'loss'
        else:
            live_display = 'Tied'
            live_cls = 'tie'

        diverges = str(r.get("diverges_from_projection", "")).lower() in ("true", "1")

        # Trend arrow from Tier 3 snapshot delta
        trend = str(r.get("my_trend", "")).upper()
        if trend == "UP":
            trend_arrow, trend_cls = "↑", "trend-UP"
        elif trend == "DOWN":
            trend_arrow, trend_cls = "↓", "trend-DOWN"
        elif trend == "FLAT":
            trend_arrow, trend_cls = "→", "trend-FLAT"
        else:
            trend_arrow, trend_cls = "", "trend-FLAT"   # NEW or missing

        my_delta = r.get("my_delta")
        delta_str = ""
        if my_delta not in (None, "", "None", "nan"):
            try:
                d = float(my_delta)
                if d != 0:
                    delta_str = f"+{d}" if d > 0 else str(d)
            except (TypeError, ValueError):
                pass

        rows.append({
            "category":     cat,
            "my_score":     _fmt_stat(r.get("my_actual"),  cat),
            "opp_score":    _fmt_stat(r.get("opp_actual"), cat),
            "proj_display": proj_display,
            "live_display": live_display,
            "diverges":     diverges,
            "trend_arrow":  trend_arrow,
            "delta_str":    delta_str,
            "_row_cls":     "win" if leader == "ME" else ("loss" if leader == "OPP" else "tie"),
            "_proj_cls":    proj_cls,
            "_live_cls":    live_cls,
            "_trend_cls":   trend_cls,
            "_separator":   separator,
        })

    return {
        "available": True,
        "my_team":   MY_TEAM,
        "opp_name":  opp_name,
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
            # Z-scores all windows
            'z_season': _fmt(player.get('z_season')),
            'z_7day':   _fmt(player.get('z_7day')),
            'z_14day':  _fmt(player.get('z_14day')),
            'z_30day':  _fmt(player.get('z_30day')),
            'trend':    player.get('trend_direction', ''),
            # CSS classes
            '_cls_z_season': _z_class(player.get('z_season')),
            '_cls_z_7day':   _z_class(player.get('z_7day')),
            '_cls_z_14day':  _z_class(player.get('z_14day')),
            '_cls_z_30day':  _z_class(player.get('z_30day')),
            '_slot_sort':    _slot_sort(slot),
            '_pos_sort':     _pos_sort(pos),
        }

    all_players = [_proc(p) for p in my_players]
    all_players.sort(key=lambda p: p['_slot_sort'])

    hitters  = [p for p in all_players if not p['is_pitcher']]

    def _pitcher_sort(p):
        inactive  = 0 if p['is_active'] else 1
        pos_order = 0 if p['position'] == 'SP' else 1  # SP first, RP second
        try:
            z = -float(p['z_season'])
        except (TypeError, ValueError):
            z = 99
        return (inactive, pos_order, z)

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


def _build_matchup_calendar(research: List[Dict], matchup: Dict) -> Dict:
    """
    Build context dict for docs/matchup-calendar.html.

    Fetches the current week's MLB schedule, cross-references both
    fantasy rosters against teams playing each day, and returns JSON-
    serialisable structures for the Jinja2 template to inject into JS.
    """
    try:
        from src.fetchers import fetch_weekly_schedule
    except ImportError:
        from fetchers import fetch_weekly_schedule  # type: ignore

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

    context = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "my_team":      MY_TEAM,
        "matchup":      _build_matchup(actuals, breakdown),
        "my_roster":    _build_my_roster(research, lineup_lookup),
        "startsit":     _build_startsit(research, lineup_lookup),
        "waiver":       _build_waiver(waiver_top, two_start, research),
        "trade":        _build_trade(targets, chips),
        "rankings":     _build_rankings(research),
        "activity":     _build_activity(),
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
        cal_context  = _build_matchup_calendar(research, context.get("matchup", {}))
        cal_template = env.get_template("matchup_calendar.html")
        cal_html     = cal_template.render(**cal_context)
        cal_path     = DOCS / "matchup-calendar.html"
        cal_path.write_text(cal_html, encoding="utf-8")
        print(f"    matchup_calendar.html → docs/matchup-calendar.html ({len(cal_html)//1024}KB)")
    except Exception as e:
        print(f"    matchup-calendar.html skipped: {e}")

    return str(out_path)
