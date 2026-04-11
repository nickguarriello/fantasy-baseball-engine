# Fantasy Baseball H2H Decision Engine

A Python pipeline that fetches live MLB stats, ranks every player by z-score,
and generates actionable waiver wire, matchup, and trade recommendations for
ESPN H2H category fantasy baseball leagues.

**Live report:** https://nickguarriello.github.io/fantasy-baseball-engine
(auto-updated daily via Windows Task Scheduler + GitHub Pages)

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your league info in config.py
#    LEAGUE_CONFIG = { 'league_id': ..., 'team_id': ..., 'season': 2026 }

# 3. Run the full pipeline
python -X utf8 main.py

# 4. View the report
#    docs/index.html  — open locally, or visit GitHub Pages URL above
```

> `-X utf8` required on Windows (emoji/unicode in output).
> Runtime: ~30–60 seconds (7 MLB API calls + ESPN call).

---

## How It Runs Daily

`run_daily.bat` is scheduled via Windows Task Scheduler at 7 AM each morning:
1. Runs the full pipeline (`main.py`)
2. Stages `docs/index.html`
3. Commits with today's date
4. Pushes to GitHub → GitHub Pages auto-updates

Logs written to `logs/daily_run.log`.

---

## What It Does

### Phase 1 — Player Rankings
Fetches full-season stats for every MLB player and calculates z-scores per position group.

| Column | What it means |
|--------|--------------|
| `z_season` | Full season (PRIMARY — always use this to rank) |
| `z_7day` | Last 7 days — hot/cold streak signal (noisy early season) |
| `z_14day` | Last 14 days |
| `z_30day` | Last 30 days |

All outfield sub-positions (CF, LF, RF) consolidated to **OF**.

### Phase 2 — Waiver Wire
- Ranks all unrostered players by `z_season`
- Flags two-start pitchers available on waivers
- Position-by-position sections with drop recommendations (same-pos worst + overall worst)
- Filters injured/IL players from recommendations

### Phase 3 — Matchup Analysis & Lineup
- Category-by-category live scores + pre-matchup projection in one unified table
- Start/sit with promote/bench callout box and ⬆/⬇ row indicators
- Two-col layout (hitters / pitchers)

### Phase 4 — Trade Analysis
- One suggested trade per opposing team (I Give / I Get / My Gain)
- My trade chips reference list
- Specific trade evaluation via `--trade` flag

---

## Usage

```bash
# Full pipeline (all 4 phases)
python -X utf8 main.py

# Skip phases you don't need
python -X utf8 main.py --skip-phases waiver trade

# Phase 1 only (fastest — verify pipeline)
python -X utf8 main.py --skip-phases waiver matchup trade

# Evaluate a specific trade
python -X utf8 main.py --trade "Nico Hoerner,Mason Miller" "Drake Baldwin"
```

---

## Report Sections

The HTML report at `docs/index.html` has 6 sections (phone-friendly, dark mode):

| Section | What you see |
|---------|-------------|
| **Matchup** | Live scores + pre-proj + live leader in one table · W-T-L record |
| **My Roster** | Two-col hitters/pitchers · ESPN slot badge · eligible positions · MLB team |
| **Start/Sit** | Two-col · promote/bench callout box · ⬆/⬇ row indicators |
| **Waiver Wire** | Two-start pitchers · 2-col by-position grid · drop recs |
| **Trade** | Per-team suggested trade table · my chips list |
| **Rankings** | Top 100 hitters + pitchers · JS filter buttons by position |

---

## Output Files (`outputs/`)

| File | Description |
|------|-------------|
| `all_players_ranked.csv` | All ~855 MLB players, sorted by z_season |
| `hitters_ranked.csv` / `pitchers_ranked.csv` | Split by type |
| `research_players.csv` | Full data lake — all fields, all rostered + FA players |
| `master_players.csv` | All players, all fields, no column whitelist |
| `data_dictionary.csv` | Field reference: name, source, dtype, null%, sample values |
| `waiver_wire_top.csv` | Top free agents overall |
| `waiver_[pos].csv` | Top 5 FAs by position |
| `waiver_target_[cat].csv` | Top FAs for each weak H2H category |
| `waiver_two_start.csv` | Two-start pitchers on waivers |
| `matchup_breakdown.csv` | Projected win/loss per category |
| `matchup_actuals_vs_projected.csv` | Actual week stats vs projection |
| `lineup_hitters.csv` / `lineup_pitchers.csv` | Start/sit recommendations |
| `trade_targets.csv` | Top players on other teams |
| `trade_chips.csv` | Your positive-z players (trade assets) |

---

## Configuration (`config.py`)

```python
LEAGUE_CONFIG = {
    'league_id': 1985887220,   # ESPN league ID
    'team_id': 1,              # Your team ID
    'season': 2026,
}

H2H_CATEGORIES = {
    'hitters':  [R, HR, RBI, SB, OBP],
    'pitchers': [K, QS, ERA, WHIP, SVHD],
}
```

League must be **public** (no ESPN login required).

---

## How Z-Scores Work

`z = (player_stat - position_average) / standard_deviation`

- **+2.0** = elite (top ~2% of position)
- **0.0** = exactly average
- **-2.0** = poor (bottom ~2%)

Computed within position groups. ERA/WHIP inverted so higher z is always better.
Two-start pitchers get a +0.4 effective z boost for lineup sorting (clearly labelled).

---

## Data Sources

- **MLB Stats API** (`statsapi.mlb.com`) — no key needed
- **ESPN Fantasy API** (`lm-api-reads.fantasy.espn.com`) — public league, no login needed

Free agents derived by cross-referencing MLB stats pool against all ESPN-rostered players (name matching).

---

## Roadmap

### ✅ Recently Completed
- **In-week stat accumulation**: `matchup_snapshots` DB table appends live scores each run. Trend arrows (↑↓→) appear in the matchup table after the 2nd daily run of a week.

### 📦 Backlog
- **Global CSS**: Consistent column widths across all report tables
- **Trade negotiation helper**: Multi-player offer suggestions based on surplus vs opponent needs
- **Testing suite**: Unit + integration tests for fetchers, processors, matchup, waiver, report
- **MLB player ID cross-reference**: Replace name-matching with ESPN ID ↔ MLB ID lookup

### ⏳ Blocked (needs data)
- **Phase 5 Historical Learning**: Track matchup outcomes to refine z-score weighting — revisit after 2–3 weeks of data

---

## Requirements

```
requests==2.31.0
pandas==2.1.3
numpy==1.24.3
jinja2
```

Python 3.9+ required. Run with `python -X utf8` on Windows.
