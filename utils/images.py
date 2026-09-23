"""
Oyuncu fotograflari.

Uygulamanin elinde ESPN oyuncu kimligi zaten vardi ama fotograf yalnizca
tek bir yerde, oyuncu detay panelinde kullaniliyordu. Tablolar ve ozet
bolumleri bastan asagi sayiydi. Bu yardimci, ayni kimlikten fotograf
adresini uretip her yerde kullanilabilir hale getiriyor.
"""
import pandas as pd

# ESPN'in boyutlandirilabilir fotograf adresi. w/h istenen olcuyu verir;
# kucuk isteyip buyutmek yerine dogru olcuyu istemek daha net gorunuyor.
_ESPN = ("https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/"
         "{player_id}.png&w={w}&h={h}")

# Fotografi olmayan oyuncular icin NBA'in kendi yedek gorseli
FALLBACK = "https://cdn.nba.com/headshots/nba/latest/1040x760/logoman.png"


def headshot(player_id, width=104, height=76):
    """Bir oyuncunun fotograf adresi. Kimlik yoksa yedek gorsel doner."""
    if player_id is None:
        return FALLBACK
    text = str(player_id).strip()
    if not text or text.lower() in ("nan", "none", "0"):
        return FALLBACK
    if text.endswith(".0"):          # pandas sayiyi float'a cevirmis olabilir
        text = text[:-2]
    return _ESPN.format(player_id=text, w=width, h=height)


def add_headshot_column(df, id_column="PLAYER_ID", target="PHOTO",
                        width=104, height=76):
    """
    DataFrame'e fotograf sutunu ekler.

    Kimlik sutunu yoksa tabloyu oldugu gibi birakir; boylece cagiran
    tarafin kontrol etmesi gerekmiyor.
    """
    if df is None or not hasattr(df, "columns") or id_column not in df.columns:
        return df
    out = df.copy()
    out[target] = out[id_column].apply(lambda v: headshot(v, width, height))
    return out


def _normalise(name):
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def name_to_id_map():
    """
    Oyuncu adi -> ESPN kimligi.

    Bazi bolumlerin elinde yalnizca ad var (MVP/LVP sayaci, izleme
    listesi). Sezon istatistigi tablosu hem adi hem kimligi tasidigi
    icin harita oradan kuruluyor. Streamlit onbellegi varsa kullanilir;
    yoksa (test/konsol) her cagrida yeniden kurulur.
    """
    try:
        import streamlit as st
        cached = st.cache_data(ttl=6 * 3600, show_spinner=False)(_build_name_map)
        return cached()
    except Exception:
        return _build_name_map()


def _build_name_map():
    try:
        from services.espn_api import get_nba_season_stats_official
        df = get_nba_season_stats_official()
    except Exception:
        return {}
    if df is None or getattr(df, "empty", True):
        return {}
    if "PLAYER" not in df.columns or "PLAYER_ID" not in df.columns:
        return {}
    return {_normalise(row["PLAYER"]): row["PLAYER_ID"]
            for _, row in df[["PLAYER", "PLAYER_ID"]].dropna().iterrows()}


def headshot_for_name(name, width=104, height=76):
    """Adi bilinen ama kimligi bilinmeyen oyuncunun fotografi."""
    if not name:
        return FALLBACK
    return headshot(name_to_id_map().get(_normalise(name)), width, height)


def add_headshot_by_name(df, name_column="PLAYER", target="PHOTO",
                         width=104, height=76):
    """Ad sutunundan fotograf sutunu uretir."""
    if df is None or not hasattr(df, "columns") or name_column not in df.columns:
        return df
    lookup = name_to_id_map()
    out = df.copy()
    out[target] = out[name_column].apply(
        lambda n: headshot(lookup.get(_normalise(n)), width, height))
    return out
