import streamlit as st
import pandas as pd
from collections import Counter

def calculate_mvp_lvp_from_df(df: pd.DataFrame, weights: dict):
    """
    Calculates the frequency of players appearing in the Top 10 (MVP) 
    or Bottom 10 (LVP) for each distinct day in the dataframe.
    """
    df = df.copy()

    # ------------------
    # 1. DATE CHECK
    # ------------------
    if "DATE" not in df.columns:
        return pd.DataFrame(), pd.DataFrame()

    # ------------------
    # 2. NUMERIC CLEAN
    # ------------------
    for stat in weights.keys():
        if stat not in df.columns:
            df[stat] = 0
        df[stat] = pd.to_numeric(df[stat], errors="coerce").fillna(0)

    df["MIN"] = pd.to_numeric(df.get("MIN", 0), errors="coerce").fillna(0)

    # ------------------
    # 3. CALCULATE FANTASY SCORE
    # ------------------
    df["fantasy_score"] = 0.0
    for stat, w in weights.items():
        df["fantasy_score"] += df[stat] * w

    # ------------------
    # 4. DAY BASED ANALYSIS
    # ------------------
    top_counter = Counter()
    worst_counter = Counter()
    player_meta = {}

    # Get unique dates in the filtered dataframe
    unique_dates = df["DATE"].unique()
    
    if len(unique_dates) == 0:
        return pd.DataFrame(), pd.DataFrame()

    # Group by DATE so we find the best/worst relative to THAT specific night
    for day in unique_dates:
        day_df = df[df["DATE"] == day].copy()
        
        # Filter: Ignore players with very low minutes generally
        day_df = day_df[day_df["MIN"] >= 5]
        
        if day_df.empty:
            continue

        # Store metadata (Team)
        for _, r in day_df.iterrows():
            player_meta.setdefault(
                r["PLAYER"], 
                {"team": r.get("TEAM", "")}
            )

        # MVP — Top 10 of the day (Must play at least 20 mins)
        mvp_pool = day_df[day_df["MIN"] >= 20] \
            .sort_values("fantasy_score", ascending=False) \
            .head(10)
        
        for p in mvp_pool["PLAYER"]:
            top_counter[p] += 1

        # LVP — Worst 10 of the day (Must play at least 15 mins to qualify as 'bad')
        lvp_pool = day_df[day_df["MIN"] >= 15] \
            .sort_values("fantasy_score", ascending=True) \
            .head(10)
        
        for p in lvp_pool["PLAYER"]:
            worst_counter[p] += 1

    def build_df(counter):
        rows = []
        for player, cnt in counter.most_common(15):
            meta = player_meta.get(player, {})
            rows.append({
                "Player": player,
                "Team": meta.get("team", ""),
                "Appearances": cnt
            })
        return pd.DataFrame(rows)

    mvp_df = build_df(top_counter)
    lvp_df = build_df(worst_counter)
    
    return mvp_df, lvp_df


def render_mvp_lvp_section(date_range, weights, label):
    st.subheader(f"🏆 MVP / 💀 LVP — {label}")

    df = st.session_state.get("period_df")

    if df is None or df.empty:
        st.info("No data available for this period.")
        return

    # ---------------------------------------------------------
    # FILTER DATAFRAME BY DATE_RANGE
    # ---------------------------------------------------------
    df = df.copy()

    # Ensure DATE column exists and is datetime
    if "DATE" not in df.columns:
        st.warning("DATE column not found in data.")
        return
        
    if not pd.api.types.is_datetime64_any_dtype(df["DATE"]):
        df["DATE"] = pd.to_datetime(df["DATE"], errors='coerce')

    # Filter logic: Check if date_range is a tuple (Start, End)
    if date_range and isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
        mask = (df["DATE"].dt.date >= start_date) & (df["DATE"].dt.date <= end_date)
        df = df.loc[mask]
        
        if df.empty:
            st.warning(f"No games found between {start_date} and {end_date}.")
            return
    
    # Calculate MVP/LVP from filtered data
    top_df, worst_df = calculate_mvp_lvp_from_df(df, weights)

    if top_df.empty and worst_df.empty:
        st.info("Not enough data in this range to calculate MVP/LVP appearances.")
        return

    # Show stats info
    unique_days = df["DATE"].nunique()
    st.caption(f"📊 Analyzing {unique_days} game day(s) • Top/Bottom 10 players per day")

    col1, col2 = st.columns(2)

    # Column Configuration for cleaner UI
    max_mvp = int(top_df["Appearances"].max()) if not top_df.empty else 10
    max_lvp = int(worst_df["Appearances"].max()) if not worst_df.empty else 10
    
    col_config_mvp = {
        "Player": st.column_config.TextColumn("Player", width="medium"),
        "Team": st.column_config.TextColumn("Team", width="small"),
        "Appearances": st.column_config.ProgressColumn(
            "Top 10", 
            format="%d", 
            min_value=0, 
            max_value=max_mvp,
            help="Number of times in daily Top 10"
        ),
    }
    
    col_config_lvp = {
        "Player": st.column_config.TextColumn("Player", width="medium"),
        "Team": st.column_config.TextColumn("Team", width="small"),
        "Appearances": st.column_config.ProgressColumn(
            "Bottom 10", 
            format="%d", 
            min_value=0, 
            max_value=max_lvp,
            help="Number of times in daily Bottom 10"
        ),
    }

    with col1:
        st.markdown("### 🏆 Most MVP Appearances")
        if not top_df.empty:
            st.dataframe(
                top_df, 
                use_container_width=True, 
                hide_index=True,
                column_config=col_config_mvp
            )
        else:
            st.info("No MVP data available")

    with col2:
        st.markdown("### 💀 Most LVP Appearances")
        if not worst_df.empty:
            st.dataframe(
                worst_df, 
                use_container_width=True, 
                hide_index=True,
                column_config=col_config_lvp
            )
        else:
            st.info("No LVP data available")