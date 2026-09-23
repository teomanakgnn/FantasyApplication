"""
Analiz kenar cubugu: tarih, punt build secimi ve puanlama katsayilari.

Onceki surumde "Other Punt Builds (Pro)" diye bir secenek vardi; secince
hicbir sey yapmiyor, yalnizca var olmayan ozellikleri ("9-CAT optimized
models", "Custom punt combinations") vaat eden bir kutu gosteriyordu.
Yerine gercekten calisan punt build'ler kondu ve Pro kapisi bunlarin
uzerine kuruldu.
"""
from datetime import datetime, timedelta

import streamlit as st

from components.pro import is_pro

# Punt build = bir kategoriden vazgecip digerlerinde one gecmek.
# Vazgecilen kategorinin katsayilari sifirlanir.
PUNT_BUILDS = {
    "Default": (),
    "Punt FT%": ("FTM", "FTA"),
    "Punt FG%": ("FGM", "FGA"),
    "Punt turnovers": ("TO",),
}

# Pro'ya acik ek build'ler
PRO_PUNT_BUILDS = {
    "Punt points": ("PTS",),
    "Punt assists": ("AST",),
    "Punt rebounds": ("REB",),
    "Punt threes": ("3Pts",),
}

BASE_WEIGHTS = {
    "PTS": 0.75,
    "REB": 0.5,
    "AST": 0.8,
    "STL": 1.7,
    "BLK": 1.6,
    "TO": -1.5,
    "FGA": -0.9,
    "FGM": 1.2,
    "FTA": -0.55,
    "FTM": 1.1,
    "3Pts": 0.6,
}


def render_sidebar():
    st.sidebar.markdown("### Analysis")

    date = st.sidebar.date_input("Game date", datetime.now() - timedelta(days=1))

    pro = is_pro()
    options = list(PUNT_BUILDS) + list(PRO_PUNT_BUILDS)

    def label(name):
        if name in PRO_PUNT_BUILDS and not pro:
            return f"{name} (Pro)"
        return name

    build = st.sidebar.selectbox("Build", options, format_func=label)

    weights = BASE_WEIGHTS.copy()
    locked = build in PRO_PUNT_BUILDS and not pro
    if locked:
        st.sidebar.caption("This build is part of Pro. Showing the default "
                           "weights until then.")
    else:
        for stat in PUNT_BUILDS.get(build, ()) or PRO_PUNT_BUILDS.get(build, ()):
            weights[stat] = 0.0

    with st.sidebar.expander("Scoring weights"):
        for key in list(weights):
            weights[key] = st.number_input(key, value=weights[key], key=f"w_{key}")

    run = st.sidebar.button("Run analysis", width="stretch", type="primary")
    st.sidebar.markdown("---")

    return date, weights, run
