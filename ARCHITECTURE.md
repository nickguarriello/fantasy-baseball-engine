# Architecture Overview

## Data Flow

```
ESPN Fantasy API              MLB Stats API
(mRoster + mMatchup + mTeam)  (season + byDateRange + schedule)
         |                              |
         v                              v
   fetchers.py ──────────────────► fetchers.py
   - all 8 rosters                - season stats (~841 players)
   - injury status                - 7/14/30-day stats
   - matchup schedule             - two-start probable pitchers
   - in-week actuals (scoreByStat)
         |                              |
         └──────────────┬───────────────┘
                        v
                 processors.py
            calculate_multi_period_zscores()
            - z_season  ← PRIMARY sort key
            - z_7day    ← hot/cold context
            - z_14day
            - z_30day
            calculate_trends()
            - uses z_7day vs z_season for momentum
                        |
         ┌──────────────┼──────────────┬──────────────┐
         v              v              v              v
   database.py    waiver_wire.py  matchup.py     trades.py
   (SQLite)       Phase 2         Phase 3        Phase 4
         |              |              |              |
         └──────────────┴──────────────┴──────────────┘
                        |
                   outputs.py
                - CSV exports
                - Console reports
```

---

## Module Responsibilities

### `config.py`
Single source of truth for all constants. Nothing is hardcoded in other modules.
Key sections: `LEAGUE_CONFIG`, `H2H_CATEGORIES`, `ESPN_POSITION_MAP`,
`OF_POSITIONS`, `INJURED_STATUSES`, `ESPN_STAT_IDS`.

### `fetchers.py`
All network I/O. Two API families:

**ESPN Fantasy API** (public, no auth):
- `fetch_espn_league_data()` — one call with `mRoster + mMatchup + mTeam` views
  Returns: all rosters, injury status, current week opponent, in-week scores
- `derive_free_agents()` — computed from MLB pool minus ESPN rosters (no API call needed)

**MLB Stats API** (no auth):
- `fetch_mlb_player_stats()` — season stats, all players
- `fetch_mlb_stats_range(start, end)` — date-range stats (same structure)
- `fetch_two_start_pitchers()` — MLB schedule API with `hydrate=probablePitcher`

Internal helpers:
- `_fetch_mlb_group(group, params)` — DRY core for all MLB stat fetches
- `_parse_hitting_split()` / `_parse_pitching_split()` — split→dict parsers
- `_parse_matchup_actuals()` — ESPN scoreByStat → our category keys

### `processors.py`
Pure math. No I/O.

- `calculate_z_scores(players)` — single period, grouped by position
- `calculate_multi_period_zscores(season, 7d, 14d, 30d)` — calls calculate_z_scores
  4 times, merges z_7day/z_14day/z_30day onto season player list by name
- `calculate_trends()` — uses z_7day vs z_season for direction signal

### `database.py`
SQLite via Python's `sqlite3`. 8 tables:

| Table | Purpose |
|-------|---------|
| `players` | Master player info (includes injury_status) |
| `player_stats` | Time-series stats (one row per refresh) |
| `player_z_scores` | Calculated z-scores (z_season, z_7day, z_14day, z_30day, is_two_start) |
| `my_roster` | Your team snapshot |
| `all_rosters` | All teams' rosters (enables trade/matchup analysis) |
| `league_teams` | Team name ↔ ID lookup |
| `waiver_evaluations` | Phase 2 waiver decisions (future) |
| `matchup_history` | Phase 5 learning data (future) |

Schema migration: `_add_column_if_missing()` handles adding new columns to existing DBs
without breaking existing installs.

### `waiver_wire.py`
Phase 2 logic. No I/O.

Key functions:
- `analyze_my_team()` — avg z per H2H category → STRONG/AVERAGE/WEAK
- `generate_waiver_report()` — top overall, by position, by weak category,
  two-start FAs. Normalises OF sub-positions to OF.
- `link_players_to_zscores()` — name-match free agents to z-score data

### `matchup.py`
Phase 3 logic. No I/O.

Key functions:
- `analyze_matchup()` — category-by-category avg z comparison, TIE_THRESHOLD=0.10
- `analyze_actuals_vs_projected()` — maps ESPN scoreByStat to our categories,
  flags divergence (projected WIN but actually losing)
- `recommend_lineup()` — priority: injury filter → two-start boost →
  z-score thresholds → matchup-need boost

### `trades.py`
Phase 4 logic. No I/O.

Key functions:
- `find_trade_targets()` — scans other teams' rosters, ranks by z_season
- `evaluate_trade()` — simulates roster before/after, computes per-category delta

### `outputs.py`
All print and CSV logic. Two categories per phase: `export_*()` and `print_*()`.
Column definitions at top of file (`RANKING_COLS`, `WAIVER_COLS`, etc.)

---

## Z-Score Design Decisions

**Why position-grouped z-scores?**
A catcher and an outfielder can't be compared directly — pool sizes and stat
distributions differ. Each player is ranked within their positional peer group.

**Why z_season as primary?**
7-day z-scores are extremely noisy early in the season (small samples). A player
going 8-for-15 in one week looks elite on z_7day but may regress to league average.
Season z-score is the stable signal; recent windows add "is this trending?"

**Why +0.4 two-start boost?**
A pitcher with 2 starts contributes ~2x the counting stats (K, QS) and ~2x the
ERA/WHIP innings. A +0.4 z-score bump approximates this without double-counting.
Clearly labelled in output — not hidden.

**Why OF consolidation?**
ESPN fantasy baseball treats CF/LF/RF as the same OF position. The MLB Stats API
returns specific outfield positions. We normalise to OF everywhere to match fantasy
roster eligibility.

---

## Name Matching Strategy

The critical join across systems is **player name → player data**. We use
case-insensitive, whitespace-stripped name matching throughout:

```python
def _norm(name: str) -> str:
    return name.lower().strip()
```

Limitations:
- Players with accented names (e.g., "Ramón Laureano") must match exactly
- No fuzzy matching — a single API inconsistency breaks the link
- MLB API and ESPN API names have been consistent in practice

Future improvement: use MLB player ID cross-reference if ESPN provides it in
their roster data (currently not extracted).

---

## ESPN Stat ID Mapping

ESPN's in-week accumulated stats use numeric IDs. Mapping in `config.ESPN_STAT_IDS`:

| ID | Category | Confidence |
|----|----------|-----------|
| `1` | R (Runs) | Confirmed |
| `5` | SB | Confirmed |
| `48` | K (pitching) | Confirmed |
| `63` | QS | Confirmed |
| `41` | ERA | Confirmed (rate stat) |
| `17` | WHIP | Confirmed (rate stat) |
| `83` | SV+HD | Confirmed |
| `23` | HR | Estimated |
| `37` | RBI | Estimated |
| `20` | OBP | Estimated |

Rate stats (ERA, WHIP, OBP) from ESPN are season-cumulative, not week-specific.
Count stats are week-to-date for the current matchup.
