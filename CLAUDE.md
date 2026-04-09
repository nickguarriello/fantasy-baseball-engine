# Fantasy Baseball Engine — Claude Code Context

This file is auto-loaded by Claude Code at the start of every session.
It gives Claude full project context without needing re-explanation.

---

## Project Identity

- **Name:** Fantasy Baseball H2H Category Decision Engine
- **Owner:** Nick G
- **Stack:** Python 3, SQLite, MLB Stats API, ESPN Fantasy API (public, no auth)
- **League:** ESPN public league `1985887220`, Team ID `1`, Season `2026`
- **Format:** H2H Categories (10 cats: R, HR, RBI, SB, OBP / K, QS, ERA, WHIP, SVHD)

---

## Repository Layout

```
fantasy-baseball-engine/
├── app.py                   # Streamlit UI — run with: streamlit run app.py
├── main.py                  # Pipeline entry point — run this
├── config.py                # All constants: league IDs, API URLs, stat maps
├── requirements.txt         # requests, pandas, numpy, streamlit
├── data/
│   └── fantasy_baseball.db  # SQLite (gitignored — regenerated each run)
├── outputs/                 # CSV exports (gitignored)
└── src/
    ├── fetchers.py          # ESPN + MLB API calls
    ├── processors.py        # Z-score math (single + multi-period)
    ├── database.py          # SQLite schema + CRUD
    ├── waiver_wire.py       # Phase 2: free agent ranking
    ├── matchup.py           # Phase 3: matchup + lineup
    ├── trades.py            # Phase 4: trade targets + evaluation
    └── outputs.py           # CSV exports + console reports
```

---

## How to Run

```bash
# Full pipeline (all 4 phases)
python -X utf8 main.py

# Skip phases you don't need
python -X utf8 main.py --skip-phases waiver trade

# Evaluate a specific trade
python -X utf8 main.py --trade "Nico Hoerner,Mason Miller" "Drake Baldwin"

# Launch the Streamlit UI (reads from outputs/ CSVs)
streamlit run app.py
```

> `-X utf8` required on Windows (emoji/unicode in print statements)
> Streamlit UI has a built-in "Refresh Data" button that re-runs the full pipeline

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

## Key Config Values (config.py)

```python
LEAGUE_CONFIG = { 'league_id': 1985887220, 'team_id': 1, 'season': 2026 }
OF_POSITIONS = {'OF', 'CF', 'LF', 'RF'}   # all treated as OF
PITCHER_POSITION_IDS = {1, 9, 10}          # SP, RP, P
INJURED_STATUSES = {'INJURY_RESERVE', 'FIFTEEN_DAY_IL', ...}
ESPN_STAT_IDS = { '1': 'runs', '48': 'strikeouts', ... }  # partially confirmed
```

---

## Known Limitations / Future Work

| Item | Status |
|------|--------|
| Streamlit UI (app.py) | ✅ Done — 5 tabs: Dashboard, Waiver, Matchup, Trade, Rankings |
| Tier 3: Daily auto-run via Windows Task Scheduler | Planned |
| Tier 3: In-week cumulative stat tracking across matchups | Planned |
| Tier 3: Trade negotiation — suggest what to offer | Planned |
| ESPN `kona_player_info` free agent fetch | Requires auth — currently derived |
| ESPN stat ID map validation | Partially confirmed; rate stats (OBP, ERA, WHIP) IDs estimated |
| Phase 5: Historical learning (trend model) | Placeholder — needs 2-3 weeks data |

---

## CSV Outputs

| File | Contents |
|------|----------|
| `all_players_ranked.csv` | All ~841 MLB players, z_season primary sort |
| `hitters_ranked.csv` / `pitchers_ranked.csv` | Split by type |
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

## Last Run Stats (auto-updated by pre-commit hook)

- **Updated:** 2026-04-09 16:56:47
- **Last data run:** 2026-04-09 20:53:42
- **Players in DB:** 842
- **Z-score records:** 11779
- **Roster entries:** 2739
- **League teams:** 8
