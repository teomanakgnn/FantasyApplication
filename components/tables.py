import streamlit as st
from utils.helpers import parse_minutes


def render_tables(df):
    df = df.copy()

    # Dakikayı integer'a çevir
    df["MIN_INT"] = df["MIN"].apply(parse_minutes)

    # =======================
    # TOP PERFORMANCES
    # =======================
    st.markdown("## Top Performances")
    st.dataframe(
        df
        .sort_values("USER_SCORE", ascending=False)
        .head(10),
        use_container_width=True,
        height=380
    )

    # =======================
    # LOWEST PERFORMANCES
    # (SADECE BURADA FİLTRE)
    # =======================
    st.markdown("## Lowest Performances")
    st.dataframe(
        df[
            df["MIN_INT"] >= 12
        ]
        .sort_values("USER_SCORE", ascending=True)
        .head(10),
        use_container_width=True,
        height=380
    )

    # =======================
    # FULL LIST
    # =======================
    with st.expander("Full Player List"):
        st.dataframe(
            df,
            use_container_width=True
        )
