# UI Overhaul — Active Plan & Open Questions

> **READ THIS FIRST** at the start of any new session before writing code.
> This file tracks the full UI overhaul plan. As of Session 6, all 9 Q&A items
> are fully implemented and shipped. No open questions remain.

---

## Session History Summary

- **Session 1–2:** Built full pipeline (fetchers, processors, database, outputs, matchup, waiver, trade)
- **Session 3:** Dropped Streamlit → Jinja2 HTML report (`docs/index.html`) via GitHub Pages. Set up Windows Task Scheduler (`run_daily.bat`). Added master_players.csv + data_dictionary.csv.
- **Session 4 (bad):** A rogue Claude session made unauthorized changes. Reverted with `git reset --hard 005c7bd` + force push.
- **Session 5:** Re-applied all good changes. Rewrote report.py + report.html. Added ESPN slot/position data extraction to fetchers.py. Ended context before executing the full UI overhaul plan.
- **Session 6:** Answered all 9 open questions. Executed full UI overhaul in one pass across 4 files (outputs.py, matchup.py, report.py, report.html). Built Tier 3 in-week trend tracking (matchup_snapshots table, trend arrows). All items shipped, committed, pushed. Ready for UAT.

---

## What Was Already Completed This Session

### ✅ config.py
Added three new constants:
```python
ESPN_LINEUP_SLOT_MAP = {
    0:'C', 1:'1B', 2:'2B', 3:'3B', 4:'SS', 5:'OF',
    6:'2B/SS', 7:'1B/3B', 8:'LF', 9:'CF', 10:'RF',
    11:'DH', 12:'UTIL', 13:'SP', 14:'P',
    15:'BE', 16:'IL', 17:'RP', 18:'IF', 19:'NA',
}
ESPN_PRIMARY_SLOTS = {'C','1B','2B','3B','SS','OF','DH','SP','RP'}
ESPN_INACTIVE_SLOT_IDS = {15, 16, 19}  # BE, IL, NA
```

### ✅ src/fetchers.py — `_parse_espn_player()`
Fully rewritten to extract:
- `lineup_slot` (readable name from lineupSlotId)
- `lineup_slot_id` (raw int)
- `is_active_lineup` (bool — True if not BE/IL/NA)
- `eligible_positions` (list of positions the player can fill, filtered to PRIMARY slots)

### ✅ src/report.py
Fully rewritten with:
- `_slot_badge()`, `_slot_badge_cls()`, `_pitcher_pos()` helpers
- `_build_lineup_lookup()` — reads lineup CSVs, returns name → {slot, is_active, rec, two_start, injury}
- `_build_my_roster()` — merges research_players + lineup lookup, sorts by slot order
- `_build_startsit()` — pitchers first, sorted by slot then z_season
- `_build_matchup()` — category-aware `_fmt_stat()`, live_rows + proj_rows

### ✅ templates/report.html
Fully rewritten with:
- Nav: Matchup → My Roster → Start/Sit → Waiver → Trade → Rankings
- Matchup: side-by-side grid (live scores + projection table)
- My Roster: two-col (hitters left, pitchers right), badges, all 4 z-score windows
- Start/Sit: full-width tables, pitchers first, left-border color coding
- All CSS classes in place

---

## Session 6 — Completed ✅

All items below were executed and shipped in Session 6.

---

## 9 Questions — Answered Session 6

### Q1 — Matchup projection table column order
Two instructions gave slightly different orders. Confirm which:
- **Option A** (earlier): `Pre-Proj | Pitch Slap (My Z) | STAT | Opp Z | Live Leader`
- **Option B** (latest): `Pre-Proj | Live Leader | Pitch Slap | STAT | Opponent`

### Q2 — What do "Pitch Slap" and "Opponent" show in the projection table?
Is it their **z-score** (the advantage signal), their **actual live score**, or should both be shown?
Current data available: `my_z`, `opp_z`, `proj_display` (projected winner text), `live_display` (live leader text).

### Q3 — 7-day z-score for matchup projection: how to detect playoffs?
Use 7-day z during regular season, season z during playoffs.
- Does user know what week number playoffs start? (ESPN typically last 3 weeks)
- Or: auto-detect by checking if z_7day has enough sample (fallback to season if <5 games)?

### Q4 — Eligible positions display in Pos column
User specified: player with 2B, 1B, DH, OF shows as `2B, 2B/SS, 1B, 1B/3B, OF, UTIL`
- Should flex slots (2B/SS, 1B/3B) be shown in the Pos column?
- Or just base positions (2B, 1B, OF, UTIL) to keep column shorter?
- Currently `ESPN_PRIMARY_SLOTS` excludes flex slots. If we want flex, update the set.

### Q5 — Start/Sit changes summary format
User wants to see: "players I should bench that are currently active" and "players I should start that are currently benched."
- **Option A**: Callout box at the **top** of Start/Sit with two lists: "Move to Bench ⬇" and "Promote to Active ⬆"
- **Option B**: Column in each table row showing `⬆ Promote` / `⬇ Bench` indicator
- **Option C**: Both — callout summary + row indicators

### Q6 — Waiver drop recommendation logic
For each waiver pickup suggestion, the recommended DROP should be:
- **Option A**: Lowest-z player at the **same position** on my roster
- **Option B**: My overall **worst player** (lowest z_season) regardless of position
- **Option C**: Show both — positional drop + my absolute worst

### Q7 — Waiver wire: show all positions or only weak spots?
- Show 3–5 FA suggestions for **every** lineup slot (C, 1B, 2B, SS, 3B, OF, SP, RP)?
- Or only for positions where my roster is **below league average** z-score?

### Q8 — Trade per-team format
User wants one recommended trade per opposing team (7 teams total).
- **Option A**: Card per team — Team name, What I give, What I get, Mutual benefit text
- **Option B**: Table row per team — columns: Team | Give | Get | Their Gain | My Gain
Algorithm: find highest-z player on their roster at my weakest position, offer my best surplus.

### Q9 — Rankings count
- Keep at top 40 per type (current)?
- Expand to top 100?
- Show all (800+) with filtering?

---

## Full Change Plan (Execute After Answers)

### File 1: `config.py`
- Update `ESPN_PRIMARY_SLOTS` to include flex slots if Q4 answer = yes
  ```python
  ESPN_PRIMARY_SLOTS = {'C','1B','2B','3B','SS','OF','DH','SP','RP','2B/SS','1B/3B','UTIL','IF'}
  ```

### File 2: `src/matchup.py` — `recommend_lineup()`
This edit FAILED last session ("file not read"). Read the file fresh, then edit.

**Injured entry dict** — add 3 fields:
```python
'eligible_positions': player.get('eligible_positions', [player.get('position','?')]),
'lineup_slot':        player.get('lineup_slot', 'BE'),
'is_active_lineup':   player.get('is_active_lineup', False),
```

**No-data entry dict** — same 3 fields added.

**Main entry dict** — fix position + add 3 fields:
```python
# CHANGE this line (MLB API returns 'P' for all pitchers, ESPN is authoritative):
'position': player.get('position', z_data.get('position', '?')),  # ESPN first
# ADD these:
'eligible_positions': player.get('eligible_positions', []),
'lineup_slot':        player.get('lineup_slot', 'BE'),
'is_active_lineup':   player.get('is_active_lineup', False),
```

### File 3: `src/outputs.py` — `LINEUP_COLS`
```python
LINEUP_COLS = [
    'name', 'position', 'eligible_positions', 'is_active_lineup', 'lineup_slot',
    'z_season', 'z_7day', 'z_14day', 'z_30day',
    'trend_direction', 'recommendation', 'injury_status', 'is_two_start', 'notes',
]
```

### File 4: `src/report.py`
Changes needed:

**`_build_lineup_lookup()`** — add `eligible_positions` to the lookup dict:
```python
'eligible_positions': row.get('eligible_positions', ''),
```

**`_build_my_roster()` — `_proc()` function:**
- Use `eligible_positions` from lineup lookup for Pos column display
- Add `mlb_team` field from research player data
- Format eligible_positions list from CSV string: `"['2B','SS']"` → `"2B, SS"`

**`_build_startsit()` — `_proc()` function:**
- Same eligible_positions fix
- Add `was_active` flag (was the player active last week = is_active currently)
- Add `changes_suggested` list built before returning: cross-reference rec vs is_active

**`_build_waiver()`** — replace current flat list with:
- `by_position`: dict of {position: [top 3-5 FAs + drop recommendation]}
- `two_start`: keep as-is (separate section)
- `starters`: top SP free agents (separate from RP)
- `relievers`: top RP free agents

**`_build_trade()`** — add `per_team` list: one recommended trade per opponent team.

**`_build_rankings()`** — pass full list (filtered in JS), add `eligible_positions`.

### File 5: `templates/report.html`
**Global:**
- All `Cat` → `STAT`
- `<colgroup>` on all tables for consistent widths: Name=160px, Pos=90px, Team=50px, stat=45px, z=55px
- Tighter font: 12px data, 11px headers

**Matchup:**
- Reorder projection table columns per Q1/Q2 answer
- Use 7-day z label when showing 7-day data

**My Roster:**
- Add `Team` column (MLB team abbrev) between Name and Pos
- Pos column = `eligible_positions` (formatted string)
- Badge = lineup_slot (SP/RP for pitchers, position slot for hitters)

**Start/Sit:**
- Switch to two-col layout (hitters left, pitchers right) matching My Roster
- Add changes callout box at top per Q5 answer
- Row order: sorted by lineup slot order (same as My Roster), not rec order

**Waiver Wire:**
- Replace Top 25 flat table with position-by-position sections
- Each position: small table (3-5 rows) + "Drop:" recommendation
- SP section + RP section + Two-start section remain separate
- Apply same badge/position fixes

**Trade:**
- Replace current layout with per-team recommendations per Q8 answer

**Rankings:**
- Add filter button bar above each table (JS-powered)
- Hitter filters: All | C | 1B | 2B | SS | 3B | OF | DH | UTIL
- Pitcher filters: All | SP | RP
- Simple JS: toggle `.hidden` class on rows based on position field

---

## Position Data Quick Reference

```
ESPN defaultPositionId → position:
  1  = SP (starting pitcher)
  2  = C
  3  = 1B
  4  = 2B
  5  = 3B
  6  = SS
  7  = LF → OF
  8  = CF → OF
  9  = RF → OF
  10 = DH
  11 = SP (also)
  12 = RP
  13 = P (utility pitcher — map to RP if unknown)

ESPN lineupSlotId → slot name:
  0=C, 1=1B, 2=2B, 3=3B, 4=SS, 5=OF
  6=2B/SS, 7=1B/3B, 8=LF, 9=CF, 10=RF
  11=DH, 12=UTIL, 13=SP, 14=P
  15=BE (bench), 16=IL, 17=RP, 18=IF, 19=NA
```

---

## Confirmed User Decisions (from session)

- "STAT" not "Cat" everywhere in the report ✅
- Pitchers always show SP or RP — never generic P ✅
- Green badge = ESPN lineup slot (current roster position) ✅
- Position column = eligible positions from ESPN eligibleSlots ✅
- DH-only = UTIL eligible only; DH+OF = UTIL+OF eligible ✅
- All positional players = also UTIL eligible ✅
- 7-day z-scores for matchup projection (regular season); season z for playoffs ✅
- Waiver: separate section for two-start pitchers, SP, and RP ✅
- Trade: one recommended trade per opposing team ✅
- Rankings: filter buttons by position (JS, phone-friendly) ✅
- Layout: two-col (hitters left, pitchers right) for My Roster AND Start/Sit ✅
- MLB team abbreviation column added to My Roster ✅
- Start/Sit: callout box showing suggested lineup changes (promote/bench) ✅

---

## Status: All Done ✅

All 9 questions answered, all code shipped, all 19 template checks passing.
