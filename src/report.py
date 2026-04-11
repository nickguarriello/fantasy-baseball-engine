"""
Report Generator — Jinja2 HTML

Loads CSVs from outputs/, renders templates/report.html, writes docs/index.html.
GitHub Pages serves docs/index.html — accessible free from any phone.

To update layout/styling: edit templates/report.html only.
To add new data:          edit this file only.
"""

import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

ROOT      = Path(__file__).parent.parent
OUTPUTS   = ROOT / "outputs"
TEMPLATES = ROOT / "templates"
DOCS      = ROOT / "docs"

MY_TEAM  = "Pitch Slap"
FA_LABEL = "FA"

# ESPN lineup slot sort order — active slots first, bench last
_SLOT_ORDER = {
    'C': 0, '1B': 1, '2B': 2, 'SS': 3, '3B': 4,
    'OF': 5, 'CF': 5, 'LF': 5, 'RF': 5,
    'DH': 6, 'UTIL': 7,
    'SP': 8, 'RP': 9, 'P': 10,
    'BE': 11, 'BN': 11,
    'IL': 12, 'IR': 12,
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
    """Category-aware stat formatting: whole numbers, OBP as .400, ERA/WHIP as 1.25."""
    if val in (None, "", "None", "nan"):
        return fallback
    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val) if val else fallback
    if cat == "OBP":
        s = f"{v:.3f}"
        return s[1:] if s.startswith("0") else s   # .400 not 0.400
    elif cat in ("ERA", "WHIP"):
        return f"{v:.2f}"
    else:
        return str(int(round(v)))


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
    """Normalize pitcher position to SP/RP — never show generic P."""
    p = str(pos).upper()
    if p == 'SP':  return 'SP'
    if p == 'RP':  return 'RP'
    if p == 'P':   return 'P'
    return pos


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
                'lineup_slot':       row.get('lineup_slot', 'BE'),
                'is_active':         str(row.get('is_active_lineup', '')).lower() in ('true', '1'),
                'rec':               row.get('recommendation', ''),
                'is_two_start':      str(row.get('is_two_start', '')).lower() in ('true', '1'),
                'injury':            row.get('injury_status', ''),
                'eligible_positions': row.get('eligible_positions', ''),
            }
    return lookup


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------

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
    for r in actuals:
        cat    = r.get("category", "")
        leader = r.get("actual_leader", "")

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
    my_players = [r for r in research if r.get("fantasy_team") == MY_TEAM]

    def _proc(player):
        name = player.get('name', '')
        key  = name.lower().strip()
        lu   = lineup_lookup.get(key, {})
        slot = lu.get('lineup_slot', 'BE')
        is_active = lu.get('is_active', False)
        is_pitcher = str(player.get('is_pitcher', '')).lower() in ('true', '1')
        pos = _pitcher_pos(player.get('position', '')) if is_pitcher else player.get('position', '')
        elig_raw = lu.get('eligible_positions', '')
        eligible = _fmt_eligible(elig_raw) if elig_raw else pos

        return {
            'name':        name,
            'position':    pos,
            'eligible':    eligible,
            'mlb_team':    player.get('mlb_team', ''),
            'slot':        slot,
            'slot_badge':  _slot_badge(slot, is_active),
            'slot_cls':    _slot_badge_cls(slot, is_active),
            'is_active':   is_active,
            'is_pitcher':  is_pitcher,
            'is_two_start': lu.get('is_two_start', False),
            'injury':      lu.get('injury', ''),
            # Hitter stats
            'games_played':   _fmt(player.get('games_played'), 0),
            'avg':            _fmt(player.get('avg'), 3),
            'obp':            _fmt_stat(player.get('obp'), 'OBP'),
            'runs':           _fmt(player.get('runs'), 0),
            'home_runs':      _fmt(player.get('home_runs'), 0),
            'rbis':           _fmt(player.get('rbis'), 0),
            'stolen_bases':   _fmt(player.get('stolen_bases'), 0),
            # Pitcher stats
            'innings_pitched': _fmt(player.get('innings_pitched'), 1),
            'era':             _fmt_stat(player.get('era'), 'ERA'),
            'whip':            _fmt_stat(player.get('whip'), 'WHIP'),
            'strikeouts_p':    _fmt(player.get('strikeouts_pitch'), 0),
            'quality_starts':  _fmt(player.get('quality_starts'), 0),
            'saves':           _fmt(player.get('saves'), 0),
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
    pitchers = [p for p in all_players if p['is_pitcher']]
    return {'hitters': hitters, 'pitchers': pitchers}


def _build_startsit(research: List[Dict], lineup_lookup: Dict) -> Dict:
    """
    Next-week lineup decisions. Pitchers first (SP/RP labels), then hitters.
    Shows active/bench badge, all z-scores + season stats.
    """
    my_players = [r for r in research if r.get("fantasy_team") == MY_TEAM]

    def _rec_cls(rec: str) -> str:
        r = rec.upper()
        if 'DO NOT START' in r: return 'sit'
        if 'START' in r:        return 'start'
        if 'CONSIDER' in r:     return 'consider'
        return 'borderline'

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
    }

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html")
    html = template.render(**context)

    DOCS.mkdir(parents=True, exist_ok=True)
    out_path = DOCS / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"    report.html → docs/index.html ({len(html)//1024}KB)")
    return str(out_path)
