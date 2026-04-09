"""
Fantasy Baseball H2H Decision Engine — Streamlit Dashboard

Run:   streamlit run app.py
Prereq: pip install streamlit  (already in requirements.txt)

The dashboard reads CSV files from outputs/ and the SQLite DB.
Use the "Refresh Data" button to re-run the full pipeline.
"""

import subprocess
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT    = Path(__file__).parent
OUTPUTS = ROOT / "outputs"
DB_PATH = ROOT / "data" / "fantasy_baseball.db"
WATCHLIST_PATH = ROOT / "data" / "watchlist.json"

# ---------------------------------------------------------------------------
# Page config — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Fantasy Baseball Engine",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Watchlist persistence  (data/watchlist.json)
# ---------------------------------------------------------------------------

def load_watchlist() -> list:
    """Load player watchlist from disk. Returns list of player name strings."""
    if not WATCHLIST_PATH.exists():
        return []
    try:
        return json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_watchlist(names: list) -> None:
    """Persist watchlist to disk."""
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(sorted(set(names))), encoding="utf-8")


# ---------------------------------------------------------------------------
# Roster ownership lookup  (reads SQLite — always current after a pipeline run)
# ---------------------------------------------------------------------------

MY_TEAM_LABEL  = "⭐ My Team"
FA_LABEL       = "FA"

@st.cache_data(ttl=300)   # re-read DB at most once every 5 min
def load_roster_lookup() -> dict:
    """
    Build {player_name_lower: display_label} from the all_rosters DB table.
    Returns empty dict if DB doesn't exist yet.

    Labels:
        "⭐ My Team"   — player is on your roster
        "FA"           — not on any fantasy roster
        "<Team Name>"  — on another manager's team
    """
    if not DB_PATH.exists():
        return {}
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT player_name, fantasy_team_name, is_my_player FROM all_rosters")
        rows = cur.fetchall()
        conn.close()
    except Exception:
        return {}

    lookup = {}
    for row in rows:
        name = (row["player_name"] or "").lower().strip()
        if not name:
            continue
        if row["is_my_player"]:
            lookup[name] = MY_TEAM_LABEL
        else:
            lookup[name] = row["fantasy_team_name"] or "Unknown"
    return lookup


def add_owner_col(df: pd.DataFrame, name_col: str = "name") -> pd.DataFrame:
    """
    Insert a 'fantasy_team' column right after the name column.
    Shows: "⭐ My Team" | "<Team Name>" | "FA"
    If the column already exists (trade_targets.csv has it), just standardise it.
    """
    lookup = load_roster_lookup()
    df = df.copy()

    if "fantasy_team" in df.columns:
        # Standardise existing column
        def _fix(val):
            v = str(val).strip() if pd.notna(val) else ""
            if not v or v.lower() in ("nan", "none", "fa", ""):
                return FA_LABEL
            return v
        df["fantasy_team"] = df["fantasy_team"].apply(_fix)
    else:
        def _lookup(row_name):
            key = str(row_name).lower().strip()
            return lookup.get(key, FA_LABEL)
        df.insert(
            df.columns.get_loc(name_col) + 1 if name_col in df.columns else 0,
            "fantasy_team",
            df[name_col].apply(_lookup) if name_col in df.columns else FA_LABEL,
        )
    return df


def owner_cell_color(val):
    """Style the fantasy_team cell."""
    if val == MY_TEAM_LABEL:
        return "background-color: #1a4fa8; color: white; font-weight: bold"
    if val == FA_LABEL:
        return "color: #888888"
    return "background-color: #5d3a8e; color: white"   # purple = other team


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def load_csv(filename: str) -> pd.DataFrame:
    """Load a CSV from outputs/. Returns empty DataFrame on missing file."""
    path = OUTPUTS / filename
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def z_color(val):
    """Background color for z-score cells."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v >= 1.5:
        return "background-color: #1a7a1a; color: white"
    if v >= 0.5:
        return "background-color: #3fa63f; color: white"
    if v >= 0.0:
        return "background-color: #85c985"
    if v >= -0.5:
        return "background-color: #e88080"
    return "background-color: #c0392b; color: white"


def style_z(df: pd.DataFrame, z_cols=None) -> "pd.io.formats.style.Styler":
    """Return a styled DataFrame — z-score columns color-coded, owner column highlighted."""
    if z_cols is None:
        z_cols = [c for c in df.columns if c.startswith("z_")]
    styler = df.style
    for col in z_cols:
        if col in df.columns:
            styler = styler.map(z_color, subset=[col])
    if "fantasy_team" in df.columns:
        styler = styler.map(owner_cell_color, subset=["fantasy_team"])
    return styler


def trend_icon(direction):
    return {"UP": "⬆", "DOWN": "⬇", "FLAT": "➡"}.get(str(direction).upper(), "")


def last_run_time() -> str:
    p = OUTPUTS / "all_players_ranked.csv"
    if not p.exists():
        return "Never"
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def safe_cols(df: pd.DataFrame, want: list) -> list:
    """Return only columns from want that actually exist in df."""
    return [c for c in want if c in df.columns]


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("⚾ Fantasy Baseball")
st.sidebar.caption(f"Last run: **{last_run_time()}**")
st.sidebar.markdown("---")

if st.sidebar.button("🔄 Refresh Data (Run Engine)", use_container_width=True):
    with st.spinner("Running full pipeline (~45 s)…"):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(ROOT / "main.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    if result.returncode == 0:
        st.sidebar.success("Pipeline complete!")
        st.cache_data.clear()   # force reload of roster lookup
    else:
        st.sidebar.error("Pipeline had errors — check logs below.")
        with st.expander("Pipeline output"):
            st.code(result.stdout[-4000:] + "\n" + result.stderr[-2000:])
    st.rerun()

st.sidebar.markdown("---")

# Owner legend
st.sidebar.markdown("**Ownership colours**")
st.sidebar.markdown(
    "🔵 **⭐ My Team** &nbsp;|&nbsp; 🟣 **Other team** &nbsp;|&nbsp; ⬜ **FA**",
    unsafe_allow_html=True,
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Use the terminal with `--skip-phases waiver matchup trade` "
    "for faster partial runs. The button above always runs all phases."
)

page = st.sidebar.radio(
    "Navigate",
    ["📊 Dashboard", "🔍 Waiver Wire", "⚔️ Matchup", "🔄 Trade", "📈 Rankings"],
    label_visibility="collapsed",
)

# ---------------------------------------------------------------------------
# 📊 DASHBOARD
# ---------------------------------------------------------------------------

if page == "📊 Dashboard":
    st.title("📊 Dashboard")

    players_df   = load_csv("all_players_ranked.csv")
    waiver_df    = load_csv("waiver_wire_top.csv")
    matchup_df   = load_csv("matchup_breakdown.csv")
    two_start_df = load_csv("waiver_two_start.csv")

    # --- Metrics ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Players Ranked",
        len(players_df) if not players_df.empty else "–",
        help="Total MLB players with season stats, ranked by z_season across your 10 H2H categories.",
    )
    col2.metric(
        "Free Agents",
        len(waiver_df) if not waiver_df.empty else "–",
        help="Available players not on any fantasy roster — derived from MLB pool minus all 8 ESPN rosters.",
    )
    if not matchup_df.empty:
        wins  = (matchup_df["projected_winner"] == "ME").sum()
        total = len(matchup_df)
        col3.metric(
            "Projected Wins",
            f"{wins} / {total}",
            help="Categories where your roster's avg z_season beats your opponent's. z_7day trends may shift this.",
        )
    else:
        col3.metric("Projected Wins", "–")
    col4.metric(
        "Two-Start Pitchers (FA)",
        len(two_start_df) if not two_start_df.empty else "–",
        help="Pitchers available on waivers with 2 scheduled starts this week — roughly 2× counting-stat value.",
    )

    st.markdown("---")

    # --- Top Players ---
    if not players_df.empty:
        hitters_df  = add_owner_col(load_csv("hitters_ranked.csv"))
        pitchers_df = add_owner_col(load_csv("pitchers_ranked.csv"))

        lcol, rcol = st.columns(2)

        with lcol:
            st.subheader("🏆 Top 10 Hitters (All MLB)")
            st.caption("Click any column header to sort")
            if not hitters_df.empty:
                want = ["name", "fantasy_team", "position", "mlb_team",
                        "z_season", "z_7day", "trend_direction"]
                top10h = hitters_df.head(10)[safe_cols(hitters_df, want)].copy()
                if "trend_direction" in top10h.columns:
                    top10h["trend"] = top10h["trend_direction"].apply(trend_icon)
                    top10h = top10h.drop(columns=["trend_direction"])
                st.dataframe(style_z(top10h, ["z_season", "z_7day"]),
                             use_container_width=True, hide_index=True)

        with rcol:
            st.subheader("🎯 Top 10 Pitchers (All MLB)")
            st.caption("Click any column header to sort")
            if not pitchers_df.empty:
                want = ["name", "fantasy_team", "position", "mlb_team",
                        "z_season", "z_7day", "trend_direction", "is_two_start"]
                top10p = pitchers_df.head(10)[safe_cols(pitchers_df, want)].copy()
                if "trend_direction" in top10p.columns:
                    top10p["trend"] = top10p["trend_direction"].apply(trend_icon)
                    top10p = top10p.drop(columns=["trend_direction"])
                st.dataframe(style_z(top10p, ["z_season", "z_7day"]),
                             use_container_width=True, hide_index=True)

    st.markdown("---")

    # --- Matchup Snapshot ---
    st.subheader("⚔️ This Week's Matchup")
    if not matchup_df.empty:
        opp_series = matchup_df[matchup_df["projected_winner"] != "ME"]["projected_winner"].mode()
        opp_display = opp_series.iloc[0] if len(opp_series) else "Opponent"
        wins_me  = (matchup_df["projected_winner"] == "ME").sum()
        wins_opp = (matchup_df["projected_winner"] == opp_display).sum()
        ties     = len(matchup_df) - wins_me - wins_opp
        st.markdown(f"**Me {wins_me} — {ties} ties — {wins_opp} {opp_display}**")

        def color_winner(row):
            if row["projected_winner"] == "ME":
                return ["background-color: #3fa63f; color: white"] * len(row)
            return ["background-color: #c0392b; color: white"] * len(row)

        st.dataframe(matchup_df.style.apply(color_winner, axis=1),
                     use_container_width=True, hide_index=True)
    else:
        st.info("No matchup data yet — run the engine first.")

# ---------------------------------------------------------------------------
# 🔍 WAIVER WIRE
# ---------------------------------------------------------------------------

elif page == "🔍 Waiver Wire":
    st.title("🔍 Waiver Wire")

    # Load watchlist from disk into session state once per session
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = load_watchlist()

    tab_watch, tab_top, tab_2start, tab_bypos, tab_cats = st.tabs(
        ["⭐ Watchlist", "Top 25 Overall", "Two-Start Pitchers", "By Position", "By Weak Category"]
    )

    # ---- Watchlist tab ----
    with tab_watch:
        st.subheader("⭐ Player Watchlist")
        st.caption("Flagged players persist across sessions (saved to data/watchlist.json).")

        wl = st.session_state.watchlist

        if wl:
            # Pull stats for watchlisted players from all_players_ranked
            all_df = add_owner_col(load_csv("all_players_ranked.csv"))
            if not all_df.empty:
                wl_lower = [n.lower().strip() for n in wl]
                wl_df = all_df[all_df["name"].str.lower().str.strip().isin(wl_lower)].copy()
                want  = ["name", "fantasy_team", "position", "mlb_team",
                         "z_season", "z_7day", "z_14day", "z_30day",
                         "trend_direction", "injury_status"]
                if not wl_df.empty:
                    st.dataframe(
                        style_z(wl_df[safe_cols(wl_df, want)]),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("Watchlisted players not found in current rankings.")
        else:
            st.info("No players on your watchlist yet. Add them from the Top 25 tab.")

        st.markdown("---")
        st.markdown("**Manage Watchlist**")
        col_add, col_remove = st.columns(2)

        with col_add:
            new_player = st.text_input("Add player by name", key="wl_add",
                                       placeholder="e.g. Cam Smith")
            if st.button("➕ Add", key="wl_add_btn") and new_player.strip():
                updated = list(set(wl + [new_player.strip()]))
                st.session_state.watchlist = updated
                save_watchlist(updated)
                st.rerun()

        with col_remove:
            if wl:
                to_remove = st.selectbox("Remove player", ["—"] + sorted(wl), key="wl_remove")
                if st.button("➖ Remove", key="wl_remove_btn") and to_remove != "—":
                    updated = [p for p in wl if p != to_remove]
                    st.session_state.watchlist = updated
                    save_watchlist(updated)
                    st.rerun()

    # ---- Top 25 tab ----
    with tab_top:
        st.subheader("Top 25 Free Agents by z_season")
        df = add_owner_col(load_csv("waiver_wire_top.csv"))
        if not df.empty:
            want = ["name", "fantasy_team", "position", "mlb_team", "injury_status",
                    "z_season", "z_7day", "z_14day", "z_30day",
                    "trend_direction", "is_two_start"]
            st.dataframe(style_z(df[safe_cols(df, want)]),
                         use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("**Add to Watchlist**")
            all_names = df["name"].dropna().tolist()
            to_watch = st.multiselect(
                "Select players to add to your watchlist",
                [n for n in all_names if n not in st.session_state.watchlist],
                key="wl_multi",
            )
            if st.button("⭐ Add selected to Watchlist") and to_watch:
                updated = list(set(st.session_state.watchlist + to_watch))
                st.session_state.watchlist = updated
                save_watchlist(updated)
                st.success(f"Added {len(to_watch)} player(s) to watchlist.")
                st.rerun()
        else:
            st.info("No waiver data — run the engine.")

    # ---- Two-Start tab ----
    with tab_2start:
        st.subheader("Two-Start Pitchers Available on Waivers")
        df = add_owner_col(load_csv("waiver_two_start.csv"))
        if not df.empty:
            st.dataframe(style_z(df), use_container_width=True, hide_index=True)
        else:
            st.info("No two-start data — run the engine (or no two-starters available this week).")

    # ---- By Position tab ----
    with tab_bypos:
        st.subheader("Free Agents by Position")
        positions = {
            "OF": "waiver_of.csv",
            "1B": "waiver_1b.csv",
            "2B": "waiver_2b.csv",
            "3B": "waiver_3b.csv",
            "SS": "waiver_ss.csv",
            "C":  "waiver_c.csv",
            "SP/RP": "waiver_p.csv",
        }
        pos_sel = st.selectbox("Position", list(positions.keys()))
        df = add_owner_col(load_csv(positions[pos_sel]))
        if not df.empty:
            st.dataframe(style_z(df), use_container_width=True, hide_index=True)
        else:
            st.info(f"No data for {pos_sel}.")

    # ---- By Weak Category tab ----
    with tab_cats:
        st.subheader("Top Pickups for Your Weak Categories")
        weak_files = list(OUTPUTS.glob("waiver_target_*.csv"))
        if weak_files:
            for f in sorted(weak_files):
                cat = f.stem.replace("waiver_target_", "").upper()
                df  = add_owner_col(load_csv(f.name))
                if not df.empty:
                    with st.expander(f"Category: {cat}", expanded=True):
                        st.dataframe(style_z(df), use_container_width=True, hide_index=True)
        else:
            st.info("No weak-category data — run the engine.")

# ---------------------------------------------------------------------------
# ⚔️ MATCHUP
# ---------------------------------------------------------------------------

elif page == "⚔️ Matchup":
    st.title("⚔️ Matchup Analysis")

    tab_proj, tab_actual, tab_lineup = st.tabs(
        ["Projected Categories", "Actual vs Projected", "Start / Sit"]
    )

    with tab_proj:
        st.subheader("Category-by-Category Projection")
        df = load_csv("matchup_breakdown.csv")
        if not df.empty:
            def color_proj(row):
                if row.get("projected_winner") == "ME":
                    return ["background-color: #3fa63f; color: white"] * len(row)
                return ["background-color: #c0392b; color: white"] * len(row)

            st.dataframe(df.style.apply(color_proj, axis=1),
                         use_container_width=True, hide_index=True)
            wins_me  = (df["projected_winner"] == "ME").sum()
            wins_opp = len(df) - wins_me
            c1, c2 = st.columns(2)
            c1.metric("Projected Wins", wins_me)
            c2.metric("Projected Losses + Ties", wins_opp)
        else:
            st.info("No matchup data — run the engine.")

    with tab_actual:
        st.subheader("Actual In-Week Stats vs Projection (ESPN scoreByStat)")
        df = load_csv("matchup_actuals_vs_projected.csv")
        if not df.empty:
            st.caption(
                "⚠ Rate stats (ERA, WHIP, OBP) from ESPN are season-cumulative, "
                "not week-specific. Count stats are week-to-date."
            )

            def color_actual(row):
                match = row.get("actual_result", "")
                proj  = row.get("projected_winner", "")
                if match == "ME" and proj == "ME":
                    return ["background-color: #3fa63f; color: white"] * len(row)
                if match == "ME" and proj != "ME":
                    return ["background-color: #2980b9; color: white"] * len(row)
                if match != "ME" and proj == "ME":
                    return ["background-color: #e67e22; color: white"] * len(row)
                return ["background-color: #c0392b; color: white"] * len(row)

            st.dataframe(df.style.apply(color_actual, axis=1),
                         use_container_width=True, hide_index=True)
            st.markdown(
                "**Legend:** 🟢 Winning as expected · 🔵 Surprise win · "
                "🟠 Divergence (losing despite projection) · 🔴 Losing as expected"
            )
        else:
            st.info("No actuals data — run the engine.")

    with tab_lineup:
        st.subheader("Start / Sit Recommendations")

        def color_lineup(row):
            rec = str(row.get("recommendation", "")).upper()
            inj = str(row.get("injury_status", "")).upper()
            if inj not in ("ACTIVE", "", "NAN"):
                return ["background-color: #7f8c8d; color: white"] * len(row)
            if "DO NOT START" in rec:
                return ["background-color: #c0392b; color: white"] * len(row)
            if "START" in rec:
                return ["background-color: #3fa63f; color: white"] * len(row)
            return [""] * len(row)

        lcol, rcol = st.columns(2)
        with lcol:
            st.markdown("**Hitters**")
            df = add_owner_col(load_csv("lineup_hitters.csv"))
            if not df.empty:
                want = ["name", "fantasy_team", "position", "z_season", "z_7day",
                        "trend_direction", "recommendation", "injury_status", "is_two_start", "notes"]
                st.dataframe(df[safe_cols(df, want)].style.apply(color_lineup, axis=1),
                             use_container_width=True, hide_index=True)
            else:
                st.info("No hitter lineup data.")

        with rcol:
            st.markdown("**Pitchers**")
            df = add_owner_col(load_csv("lineup_pitchers.csv"))
            if not df.empty:
                want = ["name", "fantasy_team", "position", "z_season", "z_7day",
                        "trend_direction", "recommendation", "injury_status", "is_two_start", "notes"]
                st.dataframe(df[safe_cols(df, want)].style.apply(color_lineup, axis=1),
                             use_container_width=True, hide_index=True)
            else:
                st.info("No pitcher lineup data.")

# ---------------------------------------------------------------------------
# 🔄 TRADE
# ---------------------------------------------------------------------------

elif page == "🔄 Trade":
    st.title("🔄 Trade Analysis")

    tab_targets, tab_chips, tab_eval = st.tabs(
        ["Trade Targets", "Your Trade Chips", "Evaluate a Trade"]
    )

    with tab_targets:
        st.subheader("Best Players on Other Rosters")
        df = add_owner_col(load_csv("trade_targets.csv"))
        if not df.empty:
            teams = ["All"] + sorted(df["fantasy_team"].dropna().unique().tolist())
            team_sel = st.selectbox("Filter by Team", teams)
            filtered = df if team_sel == "All" else df[df["fantasy_team"] == team_sel]
            st.dataframe(style_z(filtered), use_container_width=True, hide_index=True)
        else:
            st.info("No trade target data — run the engine.")

    with tab_chips:
        st.subheader("Your Positive-Z Players (Trade Assets)")
        df = add_owner_col(load_csv("trade_chips.csv"))
        if not df.empty:
            st.dataframe(style_z(df), use_container_width=True, hide_index=True)
            st.caption("These are players you could realistically offer in a trade.")
        else:
            st.info("No trade chip data — run the engine.")

    with tab_eval:
        st.subheader("Evaluate a Specific Trade")
        st.caption(
            "Enter comma-separated player names exactly as they appear in rankings. "
            "This calls main.py with the --trade flag."
        )
        give_input    = st.text_input("Players you're GIVING (comma-separated)",
                                      placeholder="e.g. Nico Hoerner")
        receive_input = st.text_input("Players you're RECEIVING (comma-separated)",
                                      placeholder="e.g. Drake Baldwin")

        if st.button("Evaluate Trade", disabled=not (give_input and receive_input)):
            with st.spinner("Evaluating trade…"):
                result = subprocess.run(
                    [sys.executable, "-X", "utf8", str(ROOT / "main.py"),
                     "--skip-phases", "waiver", "matchup",
                     "--trade", give_input.strip(), receive_input.strip()],
                    cwd=str(ROOT),
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                )
            output = result.stdout + result.stderr
            marker = "Trade Evaluation"
            if marker in output:
                trade_section = output[output.index(marker):]
                end = trade_section.find("===", 20)
                if end > 0:
                    trade_section = trade_section[:end]
                st.code(trade_section)
            else:
                st.code(output[-3000:])

# ---------------------------------------------------------------------------
# 📈 RANKINGS
# ---------------------------------------------------------------------------

elif page == "📈 Rankings":
    st.title("📈 Player Rankings")

    df = add_owner_col(load_csv("all_players_ranked.csv"))
    if df.empty:
        st.info("No ranking data — run the engine first.")
        st.stop()

    # --- Filters ---
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
    with col1:
        player_type = st.selectbox("Player Type", ["All", "Hitters", "Pitchers"])
    with col2:
        positions = ["All"] + sorted(df["position"].dropna().unique().tolist())
        pos_filter = st.selectbox("Position", positions)
    with col3:
        owner_opts = ["All", MY_TEAM_LABEL, "FA"] + sorted(
            [t for t in df["fantasy_team"].dropna().unique()
             if t not in (MY_TEAM_LABEL, FA_LABEL)]
        )
        owner_filter = st.selectbox("Ownership", owner_opts)
    with col4:
        search = st.text_input("Search Name", "")

    # --- Apply filters ---
    filtered = df.copy()
    if player_type == "Hitters":
        filtered = filtered[filtered["is_pitcher"] == False]
    elif player_type == "Pitchers":
        filtered = filtered[filtered["is_pitcher"] == True]
    if pos_filter != "All":
        filtered = filtered[filtered["position"] == pos_filter]
    if owner_filter != "All":
        filtered = filtered[filtered["fantasy_team"] == owner_filter]
    if search:
        filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)]

    st.caption(
        f"Showing {len(filtered):,} of {len(df):,} players · "
        "Sorted by z_season (season is primary ranking) · "
        "Click any column header to sort"
    )

    want = ["name", "fantasy_team", "position", "mlb_team",
            "z_season", "z_7day", "z_14day", "z_30day",
            "trend_direction", "injury_status"]
    display_df = filtered[safe_cols(filtered, want)].head(300)

    st.dataframe(style_z(display_df), use_container_width=True, hide_index=True, height=600)

    if len(filtered) > 300:
        st.caption("⚠ Showing first 300 results. Use the Ownership or Position filter to narrow down.")

    st.markdown("---")
    st.subheader("Z-Score Distribution")
    if "z_season" in filtered.columns and not filtered["z_season"].dropna().empty:
        chart_df = pd.DataFrame({"z_season": filtered["z_season"].dropna().tolist()})
        st.bar_chart(chart_df["z_season"].value_counts(bins=20).sort_index())
