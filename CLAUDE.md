# Fantasy Baseball Engine — Claude Code Context

This file is auto-loaded by Claude Code at the start of every session.
It gives Claude full project context without needing re-explanation.

---

## Project Identity

- **Name:** Fantasy Baseball H2H Category Decision Engine
- **Owner:** Nick G
- **Stack:** Python 3, SQLite, MLB Stats API, ESPN Fantasy API, Jinja2 HTML report
- **League:** ESPN public league `1985887220`, Team ID `1`, Season `2026`
- **Format:** H2H Categories (10 cats: R, HR, RBI, SB, OBP / K, QS, ERA, WHIP, SVHD)
- **My Team Name:** `Pitch Slap`

---

## Repository Layout

```
fantasy-baseball-engine/
├── main.py                  # Pipeline entry point — python -X utf8 main.py
├── config.py                # All constants: league IDs, API URLs, stat maps
├── requirements.txt         # requests, pandas, numpy, jinja2
├── run_daily.bat            # Windows Task Scheduler script (runs pipeline + git push)
├── PLANNING.md              # ⭐ Active session plan + open questions — READ THIS NEXT
├── data/
│   └── fantasy_baseball.db  # SQLite (gitignored — regenerated each run)
├── outputs/                 # CSV exports (gitignored)
├── docs/
│   └── index.html           # HTML report — served via GitHub Pages (phone access)
├── templates/
│   └── report.html          # Jinja2 template — edit this to change layout/styling
└── src/
    ├── fetchers.py          # ESPN + MLB API calls
    ├── processors.py        # Z-score math (single + multi-period)
    ├── database.py          # SQLite schema + CRUD
    ├── report.py            # Loads CSVs, renders template → docs/index.html
    ├── waiver_wire.py       # Phase 2: free agent ranking
    ├── matchup.py           # Phase 3: matchup + lineup
    ├── trades.py            # Phase 4: trade targets + evaluation
    └── outputs.py           # CSV exports + console reports
```

---

## How to Run

```bash
# Full pipeline (all 4 phases) — also generates docs/index.html
python -X utf8 main.py

# Skip phases you don't need
python -X utf8 main.py --skip-phases waiver trade

# Evaluate a specific trade
python -X utf8 main.py --trade "Nico Hoerner,Mason Miller" "Drake Baldwin"
```

> `-X utf8` required on Windows (emoji/unicode in print statements)
> HTML report auto-generated at docs/index.html after every run
> GitHub Pages serves it at: https://nickguarriello.github.io/fantasy-baseball-engine
> Daily automation: run_daily.bat via Windows Task Scheduler (7 AM)

---

## 9-Step Pipeline

| Step | What happens |
|------|-------------|
| 1 | Connectivity check (ESPN + MLB APIs) |
| 2 | Init SQLite DB (schema + migrations) |
| 3 | Fetch all 8 ESPN rosters + injury status + matchup schedule |
| 4 | Fetch MLB season stats (~841 players) |
| 5 | Fetch 7/14/30-day stats for multi-period z-scores |
| 6 | Find two-start pitchers via MLB schedule API |
| 7 | Calculate z-scores (season = primary, 7/14/30d = context) |
| 8 | Store everything in SQLite |
| 9 | Run Phases 2/3/4 and export CSVs |

---

## Z-Score Philosophy

- **`z_season` is PRIMARY** — always the main ranking signal
- `z_7day`, `z_14day`, `z_30day` add confidence/trend context
- Early in the season (April), short windows are noisy — weight lightly
- All z-scores are computed within position groups (fair comparison)
- Two-start pitchers get a +0.4 effective z boost in lineup sorting
- **Matchup projection**: use 7-day z-scores during regular season, season z-scores during playoffs

---

## Key Config Values (config.py)

```python
LEAGUE_CONFIG = { 'league_id': 1985887220, 'team_id': 1, 'season': 2026 }
OF_POSITIONS = {'OF', 'CF', 'LF', 'RF'}   # all treated as OF
PITCHER_POSITION_IDS = {1, 9, 10}          # SP, RP, P
INJURED_STATUSES = {'INJURY_RESERVE', 'FIFTEEN_DAY_IL', ...}
ESPN_STAT_IDS = { '1': 'runs', '48': 'strikeouts', ... }  # partially confirmed

# Lineup slot mappings (added this session)
ESPN_LINEUP_SLOT_MAP = {
    0:'C', 1:'1B', 2:'2B', 3:'3B', 4:'SS', 5:'OF',
    6:'2B/SS', 7:'1B/3B', 8:'LF', 9:'CF', 10:'RF',
    11:'DH', 12:'UTIL', 13:'SP', 14:'P',
    15:'BE', 16:'IL', 17:'RP', 18:'IF', 19:'NA',
}
ESPN_PRIMARY_SLOTS = {'C','1B','2B','3B','SS','OF','DH','SP','RP'}
ESPN_INACTIVE_SLOT_IDS = {15, 16, 19}  # BE, IL, NA
```

---

## ESPN Position Data — Critical Understanding

**Two separate ESPN concepts — do not confuse them:**

| Field | ESPN Source | What it means | Example |
|-------|------------|---------------|---------|
| `lineup_slot` | `entry.lineupSlotId` | WHERE the player sits in my lineup right now | SS, BE, SP, IL |
| `eligible_positions` | `player.eligibleSlots` | ALL lineup slots this player CAN fill | ['2B','SS','2B/SS','UTIL'] |
| `position` | `player.defaultPositionId` | Player's primary/default position | SS, SP, RP |

**Rules for display:**
- Green badge in tables = `lineup_slot` (current roster spot)
- POS column = `eligible_positions` joined (e.g. `2B, SS, UTIL`)
- Pitchers: badge must show `SP` or `RP` — never show generic `P`
- `defaultPositionId` 1=SP, 9=RP, 10=P (generic) — ESPN is authoritative; MLB Stats API always returns 'P' for pitchers
- DH-only → UTIL eligible only
- DH + OF → UTIL + OF eligible
- All positional hitters → also UTIL eligible

---

## Data Sources

| Source | What we get | Auth needed? |
|--------|------------|--------------|
| `statsapi.mlb.com/api/v1/stats` | Season + date-range player stats | No |
| `statsapi.mlb.com/api/v1/schedule` | Probable pitchers by date | No |
| ESPN `mRoster` + `mMatchup` + `mTeam` | Rosters, injury status, schedule | No (public league) |
| ESPN `kona_player_info` | Free agents (ownership %) | **Yes** — not used |

Free agents are **derived**: MLB stats pool minus all ESPN-rostered players (name match).

---

## HTML Report Architecture

- **Templates:** `templates/report.html` + `templates/matchup_calendar.html` — Jinja2, edit for layout/styling only
- **Data builder:** `src/report.py` — loads CSVs, builds context dicts, renders templates
- **Outputs:** `docs/index.html` + `docs/matchup-calendar.html` — tracked in git, served via GitHub Pages
- **Rule:** Never put business logic in the template. Never put HTML in report.py.

### Report Sections (nav order)
1. ⚔️ Matchup
2. 🔵 My Roster
3. 📋 Start/Sit
4. 🔍 Waiver Wire
5. 🔄 Trade
6. 📊 Rankings
7. 📋 Activity
8. 📅 Schedule (matchup-calendar.html — separate page)

### CSS Class Reference
```css
.badge-active  /* green — player is in active lineup slot */
.badge-bench   /* gray  — player is on bench */
.badge-il      /* red   — player is on IL/IR */
.two-start-badge   /* blue — pitcher has 2 starts this week */
.start / .sit / .consider / .borderline  /* left border color on Start/Sit rows */
.z-great / .z-good / .z-ok / .z-bad / .z-terrible  /* z-score cell backgrounds */
.my-team / .other-team / .fa  /* fantasy team color coding */
.action-promote / .action-bench  /* ⬆/⬇ row indicator in Start/Sit */
.changes-callout  /* promote/bench summary box at top of Start/Sit */
.waiver-pos-grid  /* 2-col grid for by-position waiver sections */
.filter-btn / .filter-btn.active  /* Rankings JS filter buttons */
```

---

## Known Limitations / Future Work

| Item | Status |
|------|--------|
| HTML report via Jinja2 (docs/index.html → GitHub Pages) | ✅ Done |
| Daily auto-run via Windows Task Scheduler (run_daily.bat) | ✅ Done |
| ESPN projections + ownership % fetch | ✅ Done |
| Projection z-scores (our math on ESPN proj data) | ✅ Done |
| master_players.csv + data_dictionary.csv | ✅ Done |
| ESPN lineupSlotId → lineup_slot (fetchers.py) | ✅ Done |
| ESPN eligibleSlots → eligible_positions (fetchers.py) | ✅ Done |
| Matchup: "Cat"→"STAT", unified table (live scores + pre-proj + live leader) | ✅ Done |
| My Roster: slot badge, eligible positions (base only), MLB team col | ✅ Done |
| Start/Sit: two-col layout, changes callout + ⬆/⬇ row indicators | ✅ Done |
| matchup.py: ESPN position first (SP/RP), propagate slot fields to lineup CSV | ✅ Done |
| outputs.py: LINEUP_COLS add is_active_lineup/lineup_slot/eligible_positions | ✅ Done |
| Waiver: 2-col by-position grid, same-pos + worst-overall drop recs | ✅ Done |
| Trade: per-team table (I Give / I Get / My Gain) | ✅ Done |
| Rankings: JS filter buttons by position, expanded to top 100 | ✅ Done |
| Global CSS: consistent column widths throughout | 📦 Backlog |
| Tier 3: In-week cumulative stat tracking across matchups | ✅ Done |
| Transaction history + Activity section in report | ✅ Done |
| ERA/WHIP inf fix (ESPN returns JS Infinity) | ✅ Done |
| IL detection via slot IDs 17/18/19 (injuryStatus unreliable) | ✅ Done |
| Same-name MLB player disambiguation (proTeamId cross-ref) | ✅ Done |
| Pitcher G column + SV+HLD → SVHD in My Roster table | ✅ Done |
| Sortable columns + Reset button on My Roster hitter/pitcher tables | ✅ Done |
| Matchup Calendar page (matchup-calendar.html, MLB schedule + fantasy overlay) | ✅ Done |
| Matchup header → "Week N vs Opponent — W·T·L" | ✅ Done |
| Matchup columns → Pitch Slap \| STAT \| OPPONENT \| PROJECTED \| LIVE (TREND removed) | ✅ Done |
| Matchup PROJECTED/LIVE labels → "Pitch Slap" / "Opponent" / "Tied" | ✅ Done |
| My Roster rank columns (R-7d/R-14d/R-30d/R-Ssn/TOT) replace z-scores | ✅ Done |
| My Roster position-group ranks: C/1B3B/2BSS/OF/DH/SP/RP; BAD if >30 | ✅ Done |
| My Roster TOT rank vs all batters/SP/RP; BAD if >150 | ✅ Done |
| My Roster REC column removed | ✅ Done |
| My Roster "This Week" toggle (fetches Monday→today MLB stats via `_fetch_current_week_stats`) | ✅ Done |
| R2 raw 7D/14D/30D stat sub-filter (stats change per window, ranks fixed) | 📦 Backlog — needs period stats in research_players.csv |
| Matchup projection using actual 30D category totals (currently z-score based) | 📦 Backlog |
| Trade negotiation helper (multi-player, surplus vs needs) | 📦 Backlog |
| Past matchup results / history section | 📦 Backlog |
| Testing strategy + test suite | 📦 Backlog |
| MLB player ID cross-reference (replace name matching) | 📦 Backlog |
| ESPN OPP/STATUS for two-start pitcher detection | 📦 Backlog |
| Phase 5: Historical learning (trend model) | ⏳ Blocked — revisit after 2-3 weeks of data |

---

## CSV Outputs

| File | Contents |
|------|----------|
| `all_players_ranked.csv` | All ~841 MLB players, z_season primary sort |
| `hitters_ranked.csv` / `pitchers_ranked.csv` | Split by type |
| `research_players.csv` | Full data lake — all fields, all rostered + FA players |
| `master_players.csv` | All players, all fields, no column whitelist |
| `data_dictionary.csv` | Field reference: name, source, dtype, null%, sample values |
| `waiver_wire_top.csv` | Top 25 free agents |
| `waiver_[pos].csv` | Top 10 per position |
| `waiver_target_[cat].csv` | Top 10 FAs for each weak H2H category |
| `waiver_two_start.csv` | Available pitchers with 2 starts this week |
| `matchup_breakdown.csv` | Category-by-category projected edge |
| `matchup_actuals_vs_projected.csv` | Actual week stats vs projection |
| `lineup_hitters.csv` / `lineup_pitchers.csv` | Start/sit recommendations |
| `trade_targets.csv` | Top 20 players on other teams |
| `trade_chips.csv` | My positive-z players (trade assets) |

---

## Database Tables

`players`, `player_stats`, `player_z_scores`, `my_roster`, `all_rosters`,
`league_teams`, `waiver_evaluations`, `matchup_history`

Schema migrations run automatically via `_add_column_if_missing()` in `init_database()`.

---

## Commit Convention

- Run `python -X utf8 main.py --skip-phases waiver matchup trade` to verify Phase 1 before committing
- Full run before any PR
- Co-Author tag: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`

---

## ⭐ NEXT SESSION: Read PLANNING.md first

UI overhaul from Session 6 is fully complete (all 9 Q&A items shipped).
PLANNING.md should be read to understand session history, but there are no
pending open questions — the slate is clean for new feature work.

---

## Last Run Stats (auto-updated by pre-commit hook)

- **Updated:** 2026-04-18 07:01:07
- **Last data run:** 2026-04-18 11:00:47
- **Players in DB:** 913
- **Z-score records:** 52681
- **Roster entries:** 250
- **League teams:** 8
