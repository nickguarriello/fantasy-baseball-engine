"""
Fantasy Baseball H2H Decision Engine — Streamlit Dashboard
Team: Pitch Slap

Run:   python -m streamlit run app.py
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

MY_TEAM = "Pitch Slap"
FA_LABEL = "FA"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Pitch Slap — Fantasy Baseball",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Watchlist persistence
# ---------------------------------------------------------------------------

def load_watchlist() -> list:
    if not WATCHLIST_PATH.exists():
        return []
    try:
        return json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_watchlist(names: list) -> None:
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(sorted(set(names))), encoding="utf-8")

# ---------------------------------------------------------------------------
# Roster ownership lookup
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_roster_lookup() -> dict:
    """
    {name_lower: display_label} from the LATEST all_rosters snapshot.
    Always reads the single most-recent date_snapshot so stale rows are ignored.
    """
    if not DB_PATH.exists():
        return {}
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Only use the most-recent snapshot
        cur.execute("SELECT MAX(date_snapshot) FROM all_rosters")
        latest = cur.fetchone()[0]
        if not latest:
            conn.close()
            return {}
        cur.execute(
            "SELECT player_name, fantasy_team_name, is_my_player "
            "FROM all_rosters WHERE date_snapshot = ?", (latest,)
        )
        rows = cur.fetchall()
        conn.close()
    except Exception:
        return {}

    lookup = {}
    for row in rows:
        name = (row["player_name"] or "").lower().strip()
        if not name:
            continue
        lookup[name] = MY_TEAM if row["is_my_player"] else (row["fantasy_team_name"] or "Unknown")
    return lookup

def owner_of(name: str) -> str:
    return load_roster_lookup().get(name.lower().strip(), FA_LABEL)

def add_owner_col(df: pd.DataFrame, name_col: str = "name") -> pd.DataFrame:
    df = df.copy()
    if "fantasy_team" not in df.columns:
        lookup = load_roster_lookup()
        df.insert(
            df.columns.get_loc(name_col) + 1 if name_col in df.columns else 0,
            "fantasy_team",
            df[name_col].apply(lambda n: lookup.get(str(n).lower().strip(), FA_LABEL))
            if name_col in df.columns else FA_LABEL,
        )
    else:
        # Standardise existing column — replace "Team N" stale values
        lookup = load_roster_lookup()
        def _fix(row):
            val = str(row.get("fantasy_team", "")).strip()
            # Try fresh lookup first
            key = str(row.get(name_col, "")).lower().strip()
            fresh = lookup.get(key)
            if fresh:
                return fresh
            if not val or val.lower() in ("nan", "none", ""):
                return FA_LABEL
            return val
        df["fantasy_team"] = df.apply(_fix, axis=1)
    return df

# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------

def z_color(val):
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v >= 1.5:  return "background-color: #1a7a1a; color: white"
    if v >= 0.5:  return "background-color: #3fa63f; color: white"
    if v >= 0.0:  return "background-color: #85c985"
    if v >= -0.5: return "background-color: #e88080"
    return "background-color: #c0392b; color: white"

def owner_color(val):
    if val == MY_TEAM:   return "background-color: #1a4fa8; color: white; font-weight: bold"
    if val == FA_LABEL:  return "color: #888888"
    return "background-color: #5d3a8e; color: white"

def style_df(df: pd.DataFrame, z_cols=None) -> "pd.io.formats.style.Styler":
    if z_cols is None:
        z_cols = [c for c in df.columns if c.startswith("z_")]
    s = df.style
    for col in z_cols:
        if col in df.columns:
            s = s.map(z_color, subset=[col])
    if "fantasy_team" in df.columns:
        s = s.map(owner_color, subset=["fantasy_team"])
    return s

def trend_icon(d):
    return {"UP": "⬆", "DOWN": "⬇", "FLAT": "➡"}.get(str(d).upper(), "")

def safe(df: pd.DataFrame, want: list) -> list:
    return [c for c in want if c in df.columns]

def load_csv(filename: str) -> pd.DataFrame:
    p = OUTPUTS / filename
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()

def last_run_time() -> str:
    p = OUTPUTS / "all_players_ranked.csv"
    if not p.exists():
        return "Never"
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title(f"⚾ {MY_TEAM}")
st.sidebar.caption(f"Last run: **{last_run_time()}**")
st.sidebar.markdown("---")

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    with st.spinner("Running pipeline (~45 s)…"):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(ROOT / "main.py")],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    if result.returncode == 0:
        st.sidebar.success("Done!")
        st.cache_data.clear()
    else:
        st.sidebar.error("Errors — see log below")
        with st.expander("Log"):
            st.code(result.stdout[-4000:] + "\n" + result.stderr[-2000:])
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("**Colours**")
st.sidebar.markdown("🔵 My Team &nbsp;|&nbsp; 🟣 Other team &nbsp;|&nbsp; ⬜ FA", unsafe_allow_html=True)
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "nav", ["📊 Dashboard", "🔍 Waiver Wire", "⚔️ Matchup", "🔄 Trade", "📊 Strategy"],
    label_visibility="collapsed",
)

# ---------------------------------------------------------------------------
# Helper: build the unified player table with filters
# ---------------------------------------------------------------------------

def player_filter_ui(df: pd.DataFrame, key_prefix: str, show_type_filter=True):
    """Render availability + position filters; return filtered dataframe."""
    df = add_owner_col(df)

    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        if show_type_filter:
            ptype = st.selectbox("Player type", ["All", "Hitters", "Pitchers"], key=f"{key_prefix}_type")
        else:
            ptype = "All"

    with col2:
        teams = sorted(df["fantasy_team"].dropna().unique().tolist())
        avail_opts = ["All Players", MY_TEAM, "Free Agents (FA)"] + \
                     sorted([t for t in teams if t not in (MY_TEAM, FA_LABEL)])
        avail = st.selectbox("Availability", avail_opts, key=f"{key_prefix}_avail")

    with col3:
        pos_opts = ["All"] + sorted(df["position"].dropna().unique().tolist())
        pos = st.selectbox("Position", pos_opts, key=f"{key_prefix}_pos")

    filtered = df.copy()
    if ptype == "Hitters":
        filtered = filtered[filtered["is_pitcher"] == False]
    elif ptype == "Pitchers":
        filtered = filtered[filtered["is_pitcher"] == True]

    if avail == MY_TEAM:
        filtered = filtered[filtered["fantasy_team"] == MY_TEAM]
    elif avail == "Free Agents (FA)":
        filtered = filtered[filtered["fantasy_team"] == FA_LABEL]
    elif avail != "All Players":
        filtered = filtered[filtered["fantasy_team"] == avail]

    if pos != "All":
        filtered = filtered[filtered["position"] == pos]

    return filtered

# ---------------------------------------------------------------------------
# 📊 DASHBOARD
# ---------------------------------------------------------------------------

if page == "📊 Dashboard":
    st.title("📊 Dashboard")

    players_df   = load_csv("all_players_ranked.csv")
    waiver_df    = load_csv("waiver_wire_top.csv")
    actuals_df   = load_csv("matchup_actuals_vs_projected.csv")
    two_start_df = load_csv("waiver_two_start.csv")

    # --- Metrics ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Players Ranked", len(players_df) if not players_df.empty else "–",
              help="Total MLB players with season stats. Source: all_players_ranked.csv")
    c2.metric("Free Agents Available", len(waiver_df) if not waiver_df.empty else "–",
              help="Top available FAs (not on any ESPN roster). Source: waiver_wire_top.csv")

    if not actuals_df.empty and "actual_leader" in actuals_df.columns:
        wins = (actuals_df["actual_leader"] == "ME").sum()
        total = len(actuals_df)
        c3.metric("Current Category Wins", f"{wins} / {total}",
                  help="Categories currently winning based on ESPN in-week scores. Source: matchup_actuals_vs_projected.csv")
    else:
        c3.metric("Current Category Wins", "–")

    c4.metric("Two-Start FAs", len(two_start_df) if not two_start_df.empty else "–",
              help="Pitchers on waivers with 2 starts this week (~2× counting stats). Source: waiver_two_start.csv")

    st.markdown("---")

    # --- Top Players (unified filterable table) ---
    st.subheader("🏆 Top Players")
    st.caption("Click any column header to sort · Source: hitters_ranked.csv / pitchers_ranked.csv")

    hitters_df  = load_csv("hitters_ranked.csv")
    pitchers_df = load_csv("pitchers_ranked.csv")
    combined    = pd.concat([hitters_df, pitchers_df], ignore_index=True) if not hitters_df.empty else pd.DataFrame()

    if not combined.empty:
        filtered = player_filter_ui(combined, "dash")

        is_pitchers = (
            "is_pitcher" in filtered.columns and
            filtered["is_pitcher"].astype(str).str.lower().isin(["true","1"]).all()
        )
        # Determine if filtered set is all pitchers or all hitters
        has_pitchers = not filtered.empty and filtered.get("is_pitcher", pd.Series([False])).astype(str).str.lower().isin(["true","1"]).any()
        has_hitters  = not filtered.empty and not (filtered.get("is_pitcher", pd.Series([False])).astype(str).str.lower().isin(["true","1"]).all())

        if not filtered.empty:
            # Column order per spec
            hitter_z   = ["z_r", "z_hr", "z_rbi", "z_sb", "z_obp"]
            pitcher_z  = ["z_k", "z_qs", "z_era", "z_whip", "z_svhd"]

            all_pitcher = filtered["is_pitcher"].astype(str).str.lower().isin(["true","1"]).all() if "is_pitcher" in filtered.columns else False

            if all_pitcher:
                cat_cols = pitcher_z
            else:
                cat_cols = hitter_z

            want = ["name", "mlb_team", "fantasy_team", "position"] + cat_cols + ["z_season", "trend_direction"]
            show_df = filtered[safe(filtered, want)].head(50).copy()
            if "trend_direction" in show_df.columns:
                show_df["trend"] = show_df["trend_direction"].apply(trend_icon)
                show_df = show_df.drop(columns=["trend_direction"])

            st.caption(f"Showing {len(filtered)} players · z_season = composite of all 5 category z-scores")
            st.dataframe(style_df(show_df, cat_cols + ["z_season"]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("No players match the selected filters.")
    else:
        st.info("No player data — run the engine first.")

    st.markdown("---")

    # --- Matchup: real current scores ---
    st.subheader("⚔️ This Week's Matchup — Current Scores")
    if not actuals_df.empty:
        # Determine opponent name
        opp_name = "Opponent"
        matchup_df = load_csv("matchup_breakdown.csv")
        if not matchup_df.empty and "projected_winner" in matchup_df.columns:
            opp_series = matchup_df[matchup_df["projected_winner"] != "ME"]["projected_winner"].mode()
            if len(opp_series):
                opp_name = opp_series.iloc[0]

        wins  = (actuals_df["actual_leader"] == "ME").sum()
        losses = (actuals_df["actual_leader"] == "OPP").sum()
        ties  = len(actuals_df) - wins - losses
        st.markdown(f"**{MY_TEAM} {wins} — {ties} ties — {losses} {opp_name}**")

        # Build display table: Pitch Slap | Category | Opponent
        display = pd.DataFrame({
            MY_TEAM:   actuals_df["my_actual"],
            "Category": actuals_df["category"],
            opp_name:  actuals_df["opp_actual"],
        })
        leaders = actuals_df["actual_leader"] if "actual_leader" in actuals_df.columns else pd.Series([""] * len(actuals_df))

        def color_matchup_row(row):
            idx = row.name
            leader = leaders.iloc[idx] if idx < len(leaders) else ""
            if leader == "ME":
                return ["background-color: #3fa63f; color: white"] * len(row)
            if leader == "OPP":
                return ["background-color: #c0392b; color: white"] * len(row)
            return ["background-color: #888888; color: white"] * len(row)

        st.dataframe(display.style.apply(color_matchup_row, axis=1),
                     use_container_width=True, hide_index=True)
        st.caption("🟢 Winning · 🔴 Losing · ⬜ Tied · Source: matchup_actuals_vs_projected.csv")
    else:
        st.info("No matchup data — run the engine or matchup may not have started yet.")

# ---------------------------------------------------------------------------
# 🔍 WAIVER WIRE
# ---------------------------------------------------------------------------

elif page == "🔍 Waiver Wire":
    st.title("🔍 Waiver Wire")

    if "watchlist" not in st.session_state:
        st.session_state.watchlist = load_watchlist()

    tab_watch, tab_top, tab_2start, tab_bypos, tab_cats = st.tabs(
        ["⭐ Watchlist", "Top 25 Overall", "Two-Start Pitchers", "By Position", "By Weak Category"]
    )

    with tab_watch:
        st.subheader("⭐ Player Watchlist")
        st.caption("Saved to data/watchlist.json — persists across sessions.")
        wl = st.session_state.watchlist

        if wl:
            all_df = add_owner_col(load_csv("all_players_ranked.csv"))
            if not all_df.empty:
                wl_lower = [n.lower().strip() for n in wl]
                wl_df = all_df[all_df["name"].str.lower().str.strip().isin(wl_lower)]
                want  = ["name", "fantasy_team", "position", "mlb_team",
                         "z_season", "z_7day", "z_14day", "z_30day", "trend_direction"]
                if not wl_df.empty:
                    st.dataframe(style_df(wl_df[safe(wl_df, want)]),
                                 use_container_width=True, hide_index=True)
                else:
                    st.info("Watchlisted players not in current rankings.")
        else:
            st.info("No players watchlisted yet. Add from the Top 25 tab.")

        st.markdown("---")
        ca, cr = st.columns(2)
        with ca:
            new_p = st.text_input("Add player", placeholder="e.g. Cam Smith", key="wl_add")
            if st.button("➕ Add", key="wl_add_btn") and new_p.strip():
                updated = list(set(wl + [new_p.strip()]))
                st.session_state.watchlist = updated; save_watchlist(updated); st.rerun()
        with cr:
            if wl:
                to_rm = st.selectbox("Remove", ["—"] + sorted(wl), key="wl_rm")
                if st.button("➖ Remove", key="wl_rm_btn") and to_rm != "—":
                    updated = [p for p in wl if p != to_rm]
                    st.session_state.watchlist = updated; save_watchlist(updated); st.rerun()

    with tab_top:
        st.subheader("Top 25 Free Agents")
        df = add_owner_col(load_csv("waiver_wire_top.csv"))
        if not df.empty:
            want = ["name", "fantasy_team", "position", "mlb_team", "injury_status",
                    "z_season", "z_7day", "z_14day", "z_30day", "trend_direction", "is_two_start"]
            st.dataframe(style_df(df[safe(df, want)]), use_container_width=True, hide_index=True)
            st.markdown("---")
            st.markdown("**Add to Watchlist**")
            all_names = [n for n in df["name"].dropna().tolist() if n not in st.session_state.watchlist]
            to_watch = st.multiselect("Select players", all_names, key="wl_multi")
            if st.button("⭐ Add to Watchlist") and to_watch:
                updated = list(set(st.session_state.watchlist + to_watch))
                st.session_state.watchlist = updated; save_watchlist(updated)
                st.success(f"Added {len(to_watch)} player(s)."); st.rerun()
        else:
            st.info("No waiver data — run the engine.")

    with tab_2start:
        st.subheader("Two-Start Pitchers on Waivers")
        df = add_owner_col(load_csv("waiver_two_start.csv"))
        if not df.empty:
            st.dataframe(style_df(df), use_container_width=True, hide_index=True)
        else:
            st.info("No two-start pitchers on waivers this week.")

    with tab_bypos:
        st.subheader("Free Agents by Position")
        pos_files = {
            "OF":"waiver_of.csv","1B":"waiver_1b.csv","2B":"waiver_2b.csv",
            "3B":"waiver_3b.csv","SS":"waiver_ss.csv","C":"waiver_c.csv","SP/RP":"waiver_p.csv",
        }
        pos_sel = st.selectbox("Position", list(pos_files.keys()))
        df = add_owner_col(load_csv(pos_files[pos_sel]))
        if not df.empty:
            st.dataframe(style_df(df), use_container_width=True, hide_index=True)
        else:
            st.info(f"No data for {pos_sel}.")

    with tab_cats:
        st.subheader("Top Pickups for Weak Categories")
        weak_files = sorted(OUTPUTS.glob("waiver_target_*.csv"))
        if weak_files:
            for f in weak_files:
                cat = f.stem.replace("waiver_target_", "").upper()
                df = add_owner_col(load_csv(f.name))
                if not df.empty:
                    with st.expander(f"Category: {cat}", expanded=True):
                        st.dataframe(style_df(df), use_container_width=True, hide_index=True)
        else:
            st.info("No weak-category data — run the engine.")

# ---------------------------------------------------------------------------
# ⚔️ MATCHUP
# ---------------------------------------------------------------------------

elif page == "⚔️ Matchup":
    st.title("⚔️ Matchup Analysis")

    # Determine opponent name once
    opp_name = "Opponent"
    matchup_z_df = load_csv("matchup_breakdown.csv")
    if not matchup_z_df.empty and "projected_winner" in matchup_z_df.columns:
        opp_series = matchup_z_df[matchup_z_df["projected_winner"] != "ME"]["projected_winner"].mode()
        if len(opp_series):
            opp_name = opp_series.iloc[0]

    tab_scores, tab_lineup = st.tabs(["Current Scores", "Start / Sit"])

    with tab_scores:
        st.subheader(f"Current Scores — {MY_TEAM} vs {opp_name}")
        actuals_df = load_csv("matchup_actuals_vs_projected.csv")

        if not actuals_df.empty:
            st.caption("Source: matchup_actuals_vs_projected.csv · ESPN in-week accumulated stats")

            wins  = (actuals_df["actual_leader"] == "ME").sum() if "actual_leader" in actuals_df.columns else 0
            losses = (actuals_df["actual_leader"] == "OPP").sum() if "actual_leader" in actuals_df.columns else 0
            ties  = len(actuals_df) - wins - losses
            st.markdown(f"**{MY_TEAM}: {wins}W — {ties} tied — {losses}L vs {opp_name}**")

            # Build: Pitch Slap | Category | Opponent
            display = pd.DataFrame({
                MY_TEAM:    actuals_df["my_actual"],
                "Category": actuals_df["category"],
                opp_name:   actuals_df["opp_actual"],
            })
            leaders = actuals_df["actual_leader"] if "actual_leader" in actuals_df.columns else pd.Series([""] * len(actuals_df))

            def color_score_row(row):
                idx = row.name
                leader = leaders.iloc[idx] if idx < len(leaders) else ""
                if leader == "ME":
                    return ["background-color: #3fa63f; color: white"] * len(row)
                if leader == "OPP":
                    return ["background-color: #c0392b; color: white"] * len(row)
                return ["background-color: #888888; color: white"] * len(row)

            st.dataframe(display.style.apply(color_score_row, axis=1),
                         use_container_width=True, hide_index=True)
            st.markdown("🟢 Winning · 🔴 Losing · ⬜ Tied")
            st.caption("⚠ Rate stats (ERA, WHIP, OBP) from ESPN may differ slightly from display due to rounding.")
        else:
            st.info("No current score data — run the engine. Data may not be available early in the week.")

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

        lc, rc = st.columns(2)
        with lc:
            st.markdown("**Hitters**")
            df = add_owner_col(load_csv("lineup_hitters.csv"))
            if not df.empty:
                want = ["name", "position", "z_season", "z_7day", "trend_direction",
                        "recommendation", "injury_status", "is_two_start", "notes"]
                st.dataframe(df[safe(df, want)].style.apply(color_lineup, axis=1),
                             use_container_width=True, hide_index=True)
            else:
                st.info("No hitter lineup data.")

        with rc:
            st.markdown("**Pitchers**")
            df = add_owner_col(load_csv("lineup_pitchers.csv"))
            if not df.empty:
                want = ["name", "position", "z_season", "z_7day", "trend_direction",
                        "recommendation", "injury_status", "is_two_start", "notes"]
                st.dataframe(df[safe(df, want)].style.apply(color_lineup, axis=1),
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
            st.dataframe(style_df(filtered), use_container_width=True, hide_index=True)
        else:
            st.info("No trade target data — run the engine.")

    with tab_chips:
        st.subheader(f"Your Trade Assets — {MY_TEAM}")
        df = add_owner_col(load_csv("trade_chips.csv"))
        if not df.empty:
            st.dataframe(style_df(df), use_container_width=True, hide_index=True)
            st.caption("Positive z_season players you could offer in a trade.")
        else:
            st.info("No trade chip data — run the engine.")

    with tab_eval:
        st.subheader("Evaluate a Trade")
        st.caption("Enter names exactly as they appear in rankings (comma-separated for multiple).")
        give    = st.text_input("You GIVE", placeholder="e.g. Nico Hoerner")
        receive = st.text_input("You RECEIVE", placeholder="e.g. Drake Baldwin")

        if st.button("Evaluate", disabled=not (give and receive)):
            with st.spinner("Evaluating…"):
                result = subprocess.run(
                    [sys.executable, "-X", "utf8", str(ROOT / "main.py"),
                     "--skip-phases", "waiver", "matchup",
                     "--trade", give.strip(), receive.strip()],
                    cwd=str(ROOT), capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                )
            output = result.stdout + result.stderr
            marker = "Trade Evaluation"
            if marker in output:
                section = output[output.index(marker):]
                end = section.find("===", 20)
                st.code(section[:end] if end > 0 else section)
            else:
                st.code(output[-3000:])

# ---------------------------------------------------------------------------
# 📊 STRATEGY
# ---------------------------------------------------------------------------

elif page == "📊 Strategy":
    st.title("📊 Strategy — Player Research")
    st.caption("Real stats + z-score trends for every MLB player. Source: research_players.csv")

    df = load_csv("research_players.csv")
    if df.empty:
        st.info("No research data — run the engine first.")
        st.stop()

    df = add_owner_col(df)

    # --- Filters ---
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    with c1:
        ptype = st.selectbox("Type", ["All", "Hitters", "Pitchers"])
    with c2:
        # Position groupings matching roster construction
        pos_groups = {
            "All":          None,
            "C":            ["C"],
            "1B / 3B":      ["1B", "3B"],
            "2B / SS":      ["2B", "SS"],
            "OF":           ["OF", "CF", "LF", "RF"],
            "SP":           ["SP"],
            "RP":           ["RP"],
            "DH / UTIL":    ["DH", "UTIL"],
        }
        pos_sel = st.selectbox("Position", list(pos_groups.keys()))
    with c3:
        owner_sel = st.selectbox("Ownership", ["All", "My Team", "FA", "Opponents"])
    with c4:
        search = st.text_input("Search Name", "")

    # Apply filters
    filtered = df.copy()
    if ptype == "Hitters":
        filtered = filtered[filtered["is_pitcher"].astype(str).str.lower().isin(["false","0"])]
    elif ptype == "Pitchers":
        filtered = filtered[filtered["is_pitcher"].astype(str).str.lower().isin(["true","1"])]

    if pos_groups[pos_sel]:
        filtered = filtered[filtered["position"].isin(pos_groups[pos_sel])]

    if owner_sel == "My Team":
        filtered = filtered[filtered["fantasy_team"] == MY_TEAM]
    elif owner_sel == "FA":
        filtered = filtered[filtered["fantasy_team"] == FA_LABEL]
    elif owner_sel == "Opponents":
        filtered = filtered[~filtered["fantasy_team"].isin([MY_TEAM, FA_LABEL])]

    if search:
        filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)]

    st.caption(f"Showing {len(filtered):,} of {len(df):,} players · Click column to sort")

    # Show hitter or pitcher real stats based on filter
    all_pitcher = (ptype == "Pitchers") or (
        "is_pitcher" in filtered.columns and
        filtered["is_pitcher"].astype(str).str.lower().isin(["true","1"]).all() and
        len(filtered) > 0
    )

    if all_pitcher:
        stat_cols = ["innings_pitched", "era", "whip", "strikeouts_pitch", "quality_starts", "saves", "holds"]
    else:
        stat_cols = ["games_played", "at_bats", "hits", "avg", "obp", "runs", "home_runs", "rbis", "stolen_bases", "walks"]

    want = (
        ["name", "mlb_team", "fantasy_team", "position"] +
        stat_cols +
        ["z_season", "z_7day", "z_14day", "z_30day", "trend_direction"]
    )
    # Add ESPN rating if available
    if "espn_rating" in filtered.columns and filtered["espn_rating"].notna().any():
        want.append("espn_rating")

    show = filtered[safe(filtered, want)].head(300).copy()

    st.dataframe(
        style_df(show, ["z_season", "z_7day", "z_14day", "z_30day"]),
        use_container_width=True,
        hide_index=True,
        height=600,
    )

    if len(filtered) > 300:
        st.caption("⚠ Showing first 300. Use filters to narrow down.")
