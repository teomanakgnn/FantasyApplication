import streamlit as st
from utils.helpers import parse_minutes


def render_tables(df):
    df = df.copy()

    # Dakikayı integer'a çevir
    df["MIN_INT"] = df["MIN"].apply(parse_minutes)

    # Görüntülenecek sütun sırası
    column_order = [
        "PLAYER", "TEAM", "USER_SCORE", "MIN", "PTS", 
        "FG", "3PT", "FT", 
        "REB", "AST", "STL", "BLK", "TO", "+/-"
    ]
    
    # Mevcut olmayan sütunları filtrele
    available_columns = [col for col in column_order if col in df.columns]
    
    # Sütun konfigürasyonu
    column_config = {
        "PLAYER": st.column_config.TextColumn("Player", width="medium"),
        "TEAM": st.column_config.TextColumn("Team", width="small"),
        "USER_SCORE": st.column_config.NumberColumn("Score", format="%.2f", width="small"),
        "MIN": st.column_config.TextColumn("Min", width="small"),
        "PTS": st.column_config.TextColumn("Pts", width="small"),
        "FG": st.column_config.TextColumn("FG", width="small"),
        "3PT": st.column_config.TextColumn("3PT", width="small"),
        "FT": st.column_config.TextColumn("FT", width="small"),
        "REB": st.column_config.NumberColumn("REB", format="%d", width="small"),
        "AST": st.column_config.NumberColumn("AST", format="%d", width="small"),
        "STL": st.column_config.NumberColumn("STL", format="%d", width="small"),
        "BLK": st.column_config.NumberColumn("BLK", format="%d", width="small"),
        "TO": st.column_config.NumberColumn("TO", format="%d", width="small"),
        "+/-": st.column_config.NumberColumn("+/-", format="%d", width="small"),
    }

    # =======================
    # TOP PERFORMANCES
    # =======================
    st.markdown("## Top Performances")
    top_df = df.sort_values("USER_SCORE", ascending=False).head(10)
    st.dataframe(
        top_df[available_columns],
        use_container_width=True,
        height=380,
        hide_index=True,
        column_config=column_config
    )

    # =======================
    # LOWEST PERFORMANCES
    # (SADECE BURADA FİLTRE)
    # =======================
    st.markdown("## Lowest Performances")
    low_df = df[df["MIN_INT"] >= 15].sort_values("USER_SCORE", ascending=True).head(10)
    st.dataframe(
        low_df[available_columns],
        use_container_width=True,
        height=380,
        hide_index=True,
        column_config=column_config
    )

    # =======================
    # FULL LIST
    # =======================
    with st.expander("Full Player List"):
        full_df = df.sort_values("USER_SCORE", ascending=False)
        st.dataframe(
            full_df[available_columns],
            use_container_width=True,
            hide_index=True,
            column_config=column_config
        )