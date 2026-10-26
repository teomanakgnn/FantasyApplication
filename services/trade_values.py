"""
Trade Analyzer degerleri.

Her oyuncu icin secilen veri tabanina gore mac basi istatistik ve 9
kategori z-skoru. z-skoru "draft edilen havuza" (lig boyu x 13) gore
hesaplanir; yuzdelerde hacim agirlikli etki kullanilir (%90 ama mac basi
2 serbest atis, %80 ama 8 serbest atistan daha az etkilidir). TO ters
cevrilir. Tarayici z'leri toplar, punt edilen kategorileri atar ve kadro
yeri (2'ye 1 takas) hesabini yapar.

Veri tabanlari:
  proj   - 2026-27 sezon projeksiyonu (draft siralamasi), sakatlik riski ile
  last   - gecen sezonun gerceklesen ortalamalari
  season - bu sezonun ortalamalari (sezon basladiktan sonra)
  30/15  - son 30 / 15 gunun kutu skorlari
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from services.cache import cache_data

BASES = {"proj": "2026-27 projections", "season": "This season", "30": "Last 30 days",
         "15": "Last 15 days", "last": "Last season"}
CATS = ["FG%", "FT%", "3PM", "PTS", "REB", "AST", "STL", "BLK", "TO"]
COUNTING = {"3PM": "tpm", "PTS": "pts", "REB": "reb", "AST": "ast", "STL": "stl", "BLK": "blk"}
POOL = 13 * 12           # z icin referans havuz (12 takim x 13 oyuncu)


def _norm(name):
    from services.daily_player import norm
    return norm(name)


def _num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _frame_from_board(board, prefix):
    cols = {"pts": "PTS", "reb": "REB", "ast": "AST", "stl": "STL", "blk": "BLK", "to": "TO",
            "fgm": "FGM", "fga": "FGA", "ftm": "FTM", "fta": "FTA", "tpm": "3Pts", "gp": "GP", "min": "MIN"}
    out = pd.DataFrame({"name": board["PLAYER"].values})
    for k, c in cols.items():
        actual = _num(board.get(c, 0))
        if prefix:
            proj = pd.to_numeric(board.get(prefix + c), errors="coerce") if prefix + c in board.columns else None
            out[k] = (proj.fillna(actual) if proj is not None else actual).values
        else:
            out[k] = actual.values
    return out


@cache_data(ttl=3600, show_spinner=False, copy_result=False)
def _board_info():
    """Isim -> ESPN kimligi, mevki, sakatlik, takim (fotograf ve etiketler icin)."""
    from services.draft_data import get_draft_board
    board = get_draft_board()
    info = {}
    for _, r in board.iterrows():
        pid = r.get("ESPN_ID")
        info[_norm(r["PLAYER"])] = {
            "id": str(int(pid)) if pid == pid and pid else "", "team": r.get("TEAM") or "",
            "pos": "/".join(r["POSITIONS"]) if isinstance(r.get("POSITIONS"), (list, tuple)) else (r.get("POS") or ""),
            "injury": r.get("INJURY") or "ACTIVE", "adp": float(r["ADP"]) if r["ADP"] < 999 else None}
    return board, info


def _raw(basis):
    board, _ = _board_info()
    if basis == "proj":
        df = _frame_from_board(board, "PROJ_")
        from services.strategy_engine import availability
        df["avail"] = availability(board).values
        return df
    if basis == "last":
        df = _frame_from_board(board, "")
        df = df[df["gp"] >= 15]
        df["avail"] = 1.0
        return df
    from web import stats
    if basis == "season":
        st = stats.season_table(stats.BASE_WEIGHTS, min_games=False)
        if st is None or st.empty:
            return pd.DataFrame()
        df = pd.DataFrame({"name": st["PLAYER"].values, "gp": _num(st.get("GAMES", st.get("GP", 0))).values,
                           "min": _num(st.get("MIN_INT", st.get("MIN", 0))).values})
        for k, c in (("pts", "PTS"), ("reb", "REB"), ("ast", "AST"), ("stl", "STL"), ("blk", "BLK"), ("to", "TO"),
                     ("fgm", "FGM"), ("fga", "FGA"), ("ftm", "FTM"), ("fta", "FTA"), ("tpm", "3Pts")):
            df[k] = _num(st.get(c, 0)).values
        df["avail"] = 1.0
        return df
    days = int(basis)
    end = date.today()
    rows = stats._period_games(end - timedelta(days=days), end)
    if not rows:
        return pd.DataFrame()
    daily = stats._numeric(pd.DataFrame(rows), stats.STAT_KEYS)
    daily["MIN_INT"] = daily["MIN"].apply(stats.parse_minutes) if "MIN" in daily.columns else 0
    daily = daily[daily["MIN_INT"] > 0]
    if daily.empty:
        return pd.DataFrame()
    agg = daily.groupby("PLAYER").agg(gp=("PLAYER", "size"), min=("MIN_INT", "mean"), pts=("PTS", "mean"),
                                      reb=("REB", "mean"), ast=("AST", "mean"), stl=("STL", "mean"),
                                      blk=("BLK", "mean"), to=("TO", "mean"), fgm=("FGM", "mean"),
                                      fga=("FGA", "mean"), ftm=("FTM", "mean"), fta=("FTA", "mean"),
                                      tpm=("3Pts", "mean")).reset_index().rename(columns={"PLAYER": "name"})
    agg["avail"] = 1.0
    return agg


def _zscores(df):
    """Havuza gore 9 kategori z-skoru (yuzdeler hacim agirlikli)."""
    # Gecici siralama: kaba deger, havuzu secmek icin
    rough = df["pts"] + 1.2 * df["reb"] + 1.5 * df["ast"] + 3 * df["stl"] + 3 * df["blk"] - df["to"]
    pool = df.loc[rough.sort_values(ascending=False).index[:POOL]]
    z = pd.DataFrame(index=df.index)
    for cat, k in COUNTING.items():
        mu, sd = pool[k].mean(), pool[k].std(ddof=0) or 1.0
        z[cat] = (df[k] - mu) / sd
    mu, sd = pool["to"].mean(), pool["to"].std(ddof=0) or 1.0
    z["TO"] = -(df["to"] - mu) / sd
    for cat, m, a in (("FG%", "fgm", "fga"), ("FT%", "ftm", "fta")):
        rate = pool[m].sum() / pool[a].sum() if pool[a].sum() else 0.0
        impact = (np.where(df[a] > 0, df[m] / df[a].replace(0, np.nan), rate) - rate) * df[a]
        impact = pd.Series(impact, index=df.index).fillna(0.0)
        pimpact = impact.loc[pool.index]
        z[cat] = (impact - pimpact.mean()) / (pimpact.std(ddof=0) or 1.0)
    return z


@cache_data(ttl=1800, show_spinner=False, copy_result=False)
def players(basis="proj"):
    basis = basis if basis in BASES else "proj"
    df = _raw(basis)
    if df is None or df.empty:
        return []
    df = df[(df["min"] >= 8) | (basis == "proj")].reset_index(drop=True)
    df = df[df["gp"] > 0].reset_index(drop=True) if basis != "proj" else df
    z = _zscores(df)
    _, info = _board_info()
    out = []
    for i, r in df.iterrows():
        meta = info.get(_norm(r["name"]), {})
        out.append({
            "id": meta.get("id", ""), "name": r["name"], "team": meta.get("team", ""), "pos": meta.get("pos", ""),
            "injury": meta.get("injury", "ACTIVE"), "gp": int(round(float(r["gp"] or 0))),
            "min": round(float(r["min"] or 0), 1), "avail": round(float(r.get("avail", 1.0) or 1.0), 2),
            "s": {k: round(float(r[k] or 0), 2) for k in ("pts", "reb", "ast", "stl", "blk", "to", "fgm", "fga", "ftm", "fta", "tpm")},
            "z": {c: round(float(z.at[i, c]), 2) for c in CATS},
        })
    # Kaba toplam z'ye gore sira (arama listesi sirasi)
    out.sort(key=lambda p: -sum(p["z"].values()))
    for rank, p in enumerate(out, 1):
        p["rank"] = rank
    return out
