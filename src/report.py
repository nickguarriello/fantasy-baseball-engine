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


def _enrich_z(rows: List[Dict], z_cols: List[str]) -> List[Dict]:
    """Add _cls_{col} CSS class field for each z-score column."""
    for row in rows:
        for col in z_cols:
            row[f"_cls_{col}"] = _z_class(row.get(col))
    return rows


# ---------------------------------------------------------------------------
# Data builders — one function per section
# ---------------------------------------------------------------------------

def _build_matchup(actuals: List[Dict], breakdown: List[Dict]) -> Dict:
    if not actuals:
        return {"available": False}

    opp_name = "Opponent"
    if breakdown:
        winners = [r.get("projected_winner", "") for r in breakdown if r.get("projected_winner") not in ("ME", "TOSS-UP", "UNKNOWN", "")]
        if winners:
            opp_name = max(set(winners), key=winners.count)

    wins   = sum(1 for r in actuals if r.get("actual_leader") == "ME")
    losses = sum(1 for r in actuals if r.get("actual_leader") == "OPP")
    ties   = len(actuals) - wins - losses

    rows = []
    for r in actuals:
        cat    = r.get("category", "")
        leader = r.get("actual_leader", "")
        proj   = r.get("projected_winner", "—")
        proj_display = MY_TEAM if proj == "ME" else ("Toss-Up" if proj in ("TOSS-UP", "UNKNOWN") else proj)
        live_display = MY_TEAM if leader == "ME" else (opp_name if leader == "OPP" else "Tied")
        diverges = str(r.get("diverges_from_projection", "")).lower() in ("true", "1")
        rows.append({
            "my_score":     _fmt_stat(r.get("my_actual"),  cat),
            "category":     cat,
            "opp_score":    _fmt_stat(r.get("opp_actual"), cat),
            "leader":       leader,
            "proj_display": proj_display,
            "live_display": live_display,
            "diverges":     diverges,
            "_cls":         "win" if leader == "ME" else ("loss" if leader == "OPP" else "tie"),
            "_proj_cls":    "win" if leader == "ME" else ("loss" if leader == "OPP" else "tie"),
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


def _build_lineup(hitters: List[Dict], pitchers: List[Dict]) -> Dict:
    def _proc(rows):
        out = []
        for r in rows:
            rec = str(r.get("recommendation", "")).upper()
            inj = str(r.get("injury_status", "")).upper()
            if inj not in ("ACTIVE", "", "NAN", "NONE"):
                cls = "injured"
            elif "DO NOT START" in rec:
                cls = "sit"
            elif "START" in rec:
                cls = "start"
            else:
                cls = ""
            out.append({
                "name":           r.get("name", ""),
                "position":       r.get("position", ""),
                "z_season":       _fmt(r.get("z_season")),
                "z_7day":         _fmt(r.get("z_7day")),
                "two_start":      str(r.get("is_two_start", "")).lower() in ("true", "1"),
                "injury":         r.get("injury_status", ""),
                "rec":            r.get("recommendation", ""),
                "_cls":           cls,
                "_cls_z_season":  _z_class(r.get("z_season")),
                "_cls_z_7day":    _z_class(r.get("z_7day")),
            })
        return out
    return {"hitters": _proc(hitters), "pitchers": _proc(pitchers)}


def _build_my_roster(research: List[Dict]) -> List[Dict]:
    rows = [r for r in research if r.get("fantasy_team") == MY_TEAM]
    rows.sort(key=lambda r: float(r.get("z_season") or -99), reverse=True)
    out = []
    for r in rows:
        is_p = str(r.get("is_pitcher", "")).lower() in ("true", "1")
        out.append({
            "name":     r.get("name", ""),
            "position": r.get("position", ""),
            "z_season": _fmt(r.get("z_season")),
            "z_7day":   _fmt(r.get("z_7day")),
            "z_14day":  _fmt(r.get("z_14day")),
            "z_30day":  _fmt(r.get("z_30day")),
            "trend":    r.get("trend_direction", ""),
            "is_pitcher": is_p,
            "_cls_z_season": _z_class(r.get("z_season")),
            "_cls_z_7day":   _z_class(r.get("z_7day")),
            "_cls_z_14day":  _z_class(r.get("z_14day")),
            "_cls_z_30day":  _z_class(r.get("z_30day")),
        })
    return out


def _build_waiver(top: List[Dict], two_start: List[Dict]) -> Dict:
    z_cols = ["z_season", "z_7day", "z_14day", "z_30day"]

    def _proc(rows, limit=25):
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

    return {"top": _proc(top), "two_start": _proc(two_start, 15)}


def _build_trade(targets: List[Dict], chips: List[Dict]) -> Dict:
    def _proc(rows, limit=20):
        out = []
        for r in rows[:limit]:
            out.append({
                "name":        r.get("name", ""),
                "position":    r.get("position", ""),
                "fantasy_team": r.get("fantasy_team", ""),
                "z_season":    _fmt(r.get("z_season")),
                "z_7day":      _fmt(r.get("z_7day")),
                "_cls_z_season": _z_class(r.get("z_season")),
            })
        return out
    return {"targets": _proc(targets), "chips": _proc(chips)}


def _build_rankings(research: List[Dict]) -> Dict:
    hitters  = [r for r in research if str(r.get("is_pitcher","")).lower() not in ("true","1")]
    pitchers = [r for r in research if str(r.get("is_pitcher","")).lower() in ("true","1")]

    def _proc(rows, limit=40):
        out = []
        for r in rows[:limit]:
            out.append({
                "name":        r.get("name", ""),
                "position":    r.get("position", ""),
                "mlb_team":    r.get("mlb_team", ""),
                "fantasy_team": r.get("fantasy_team", FA_LABEL),
                "owned":       _pct(r.get("percent_owned")),
                "z_season":    _fmt(r.get("z_season")),
                "z_7day":      _fmt(r.get("z_7day")),
                "proj_z":      _fmt(r.get("proj_z_season")),
                "trend":       r.get("trend_direction", ""),
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
    """
    Load all CSVs, render templates/report.html, write docs/index.html.
    Returns path to generated file.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError:
        print("  jinja2 not installed — pip install jinja2")
        return ""

    # Load CSVs
    research  = _load("research_players.csv")
    actuals   = _load("matchup_actuals_vs_projected.csv")
    breakdown = _load("matchup_breakdown.csv")
    hitters_l = _load("lineup_hitters.csv")
    pitchers_l = _load("lineup_pitchers.csv")
    waiver_top = _load("waiver_wire_top.csv")
    two_start  = _load("waiver_two_start.csv")
    targets    = _load("trade_targets.csv")
    chips      = _load("trade_chips.csv")

    context = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "my_team":      MY_TEAM,
        "matchup":      _build_matchup(actuals, breakdown),
        "lineup":       _build_lineup(hitters_l, pitchers_l),
        "my_roster":    _build_my_roster(research),
        "waiver":       _build_waiver(waiver_top, two_start),
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
