"""
Alt/ust tahmini: her NBA takiminin sezonluk galibiyet baremi.

Kullanici 30 takimin her biri icin "ust" mu "alt" mi der; tahminler
20 Ekim aksami kapanir, sezon baslayinca da kapali kalir.

Baremler Las Vegas'in sezonluk galibiyet cizgileri (bkz.
services/win_totals.VEGAS_LINES). Uygulamanin kendi modeli cizgi degil,
kartta Vegas'in yaninda "model" olarak duruyor.

Baremler veritabaninda donduruluyor ki herkes ayni sayiya oynasin. Ilk
surum modelin cizgilerini dondurmustu; Vegas cizgileri gelince bir kez
degistirildi (bkz. _switch_to_vegas).

Akicilik notu: Streamlit her tiklamada butun betigi bastan calistirir.
Ilk surumde her tiklama Neon'a dort sorgu birden atiyordu (baremler,
tahminler, kalabalik, donmus mu) ve ustune bir de st.rerun() cagriliyordu
- yani her secim iki tam tur. Simdi veri oturumda tutuluyor, yazma
on_change geri cagrisinda yapiliyor ve elle rerun yok: bir tiklama = bir
tur, bir sorgu.
"""
import csv
import io
from datetime import datetime

import streamlit as st

from services.database import db
from services.nba_season import get_current_season_year, get_season_label
from services.win_totals import (get_team_identity, implied_over,
                                 project_win_totals, vegas_lines)
from utils.share_card import over_under_card
from utils.text import esc

# Tahminler bu ana kadar acik. Sezon 21 Ekim'de basliyor; bir gun once
# kapaniyor ki kimse ilk maclari gordukten sonra tahmin degistirmesin.
DEADLINE = datetime(2026, 10, 20, 23, 59, 59)

OVER, UNDER = "over", "under"
LABELS = {OVER: "Over", UNDER: "Under"}
FROM_LABEL = {"Over": OVER, "Under": UNDER}

ACCENT = "#3987e5"
DANGER = "#e66767"
MUTED = "#8C99B2"


def _css():
    st.markdown("""
        <style>
        .ou-hero { margin: 0 0 10px; }
        .ou-hero h1 { font-size: 1.65rem; font-weight: 800; letter-spacing: -.6px;
                      margin: 0 0 4px; }
        .ou-hero p { color: #8C99B2; font-size: .9rem; margin: 0; line-height: 1.5; }

        /* Ust serit: ilerleme her zaman sayiyla birlikte, cubuk tek basina
           anlam tasimasin. */
        .ou-top {
            border: 1px solid rgba(255,255,255,.09); background: #171C27;
            border-radius: 15px; padding: 13px 15px; margin: 4px 0 14px;
        }
        .ou-top .line1 {
            display: flex; align-items: baseline; justify-content: space-between;
            gap: 12px; flex-wrap: wrap; margin-bottom: 9px;
        }
        .ou-count { font-size: 1.02rem; font-weight: 800; color: #E8ECF4; }
        .ou-count span { color: #6B7893; font-weight: 700; font-size: .84rem; }
        .ou-clock { font-size: .8rem; font-weight: 700; color: #8fbdf2;
                    white-space: nowrap; }
        .ou-clock.closed { color: #f0a3a3; }
        .ou-track { height: 6px; border-radius: 4px; background: rgba(255,255,255,.08);
                    overflow: hidden; }
        .ou-track i { display: block; height: 100%; border-radius: 4px;
                      background: linear-gradient(90deg, #3987e5, #6fb0ff); }

        .ou-stats { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 10px;
                    font-size: .78rem; color: #6B7893; }
        .ou-stats b { color: #A9B6CE; font-weight: 800; }

        /* Takim karti */
        .ou-card {
            border: 1px solid rgba(255,255,255,.09);
            border-left: 3px solid var(--team, #3987e5);
            background: #171C27; border-radius: 13px;
            padding: 10px 12px; margin-bottom: 6px;
        }
        .ou-card.picked { border-color: rgba(57,135,229,.5);
                          border-left-color: var(--team, #3987e5); }
        .ou-head { display: flex; align-items: center; gap: 9px; }
        .ou-logo { width: 34px; height: 34px; object-fit: contain; flex: 0 0 auto; }
        .ou-name { font-size: .9rem; font-weight: 800; color: #E8ECF4;
                   letter-spacing: -.2px; line-height: 1.2; }
        .ou-city { font-size: .7rem; color: #6B7893; }
        .ou-num { margin-left: auto; text-align: right; }
        .ou-line { font-size: 1.25rem; font-weight: 800; color: #E8ECF4;
                   line-height: 1; }
        .ou-lastwins { font-size: .67rem; color: #6B7893; }
        .ou-odds { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 7px;
                   font-size: .7rem; color: #6B7893; }
        .ou-odds b { color: #A9B6CE; font-weight: 800; }
        .ou-odds .lean { margin-left: auto; font-weight: 700; }

        /* Kalabalik: cubuk + yazi birlikte */
        .ou-crowd { margin-top: 8px; font-size: .68rem; color: #6B7893; }
        .ou-crowdbar { height: 4px; border-radius: 3px; overflow: hidden;
                       background: rgba(230,103,103,.35); margin-bottom: 3px; }
        .ou-crowdbar i { display: block; height: 100%; background: #3987e5; }

        .ou-note {
            border: 1px solid rgba(255,255,255,.07); border-radius: 12px;
            padding: 11px 13px; margin-top: 18px;
            color: #6B7893; font-size: .78rem; line-height: 1.6;
        }
        .ou-note b { color: #A9B6CE; }

        .ou-pill { font-size: .68rem; font-weight: 800; letter-spacing: .4px;
                   padding: 3px 9px; border-radius: 6px; }
        .ou-pill.over  { background: rgba(57,135,229,.18); color: #8fbdf2; }
        .ou-pill.under { background: rgba(230,103,103,.16); color: #f0a3a3; }
        .ou-pill.none  { background: rgba(255,255,255,.06); color: #8C99B2; }
        </style>
    """, unsafe_allow_html=True)


# ==================== DURUM ====================

def _deadline_state():
    """(acik mi, kisa sure metni)"""
    now = datetime.now()
    if now > DEADLINE:
        return False, "Closed 20 October"
    left = DEADLINE - now
    if left.days > 0:
        return True, f"{left.days}d {left.seconds // 3600}h left"
    return True, f"{left.seconds // 3600}h {(left.seconds % 3600) // 60}m left"


def _load_lines(season):
    """
    Dondurulmus baremleri getirir; ilk acilista modelden uretip dondurur.

    Sonuc oturumda tutuluyor: barem donmus bir veri, her tiklamada
    veritabanina tekrar sormanin anlami yok.
    """
    key = f"ou_lines_{season}"
    if key in st.session_state:
        return st.session_state[key]

    rows, frozen = [], False
    if db.available and db.win_lines_frozen(season):
        rows = [{"team": r["team"], "team_name": r["team_name"],
                 "line": float(r["line"]),
                 "projected": float(r["projected"]) if r["projected"] is not None else None,
                 "conf": r["conf"] or "",
                 "last_wins": None if r["last_wins"] is None else float(r["last_wins"]),
                 "over_odds": r.get("over_odds"), "under_odds": r.get("under_odds")}
                for r in db.get_win_lines(season)]
        frozen = True
        _switch_to_vegas(season, rows)

    # Model yalnizca gerektiginde calisir. Cagrisi pahali: butun draft
    # tablosunu (16MB) cekiyor. Baremler donmus ve gosterim alanlari da
    # doluysa buraya hic girilmiyor, sayfa veritabanindan aciliyor.
    needs_backfill = frozen and any(not row["conf"] for row in rows)
    if not rows or needs_backfill:
        table = project_win_totals()
        if not table.empty:
            fresh = [{"team": r.TEAM, "team_name": r.NAME, "line": float(r.LINE),
                      "projected": float(r.PROJECTED), "conf": r.CONF,
                      "last_wins": float(r.LAST_WINS),
                      "over_odds": _odds_or_none(r.OVER_ODDS),
                      "under_odds": _odds_or_none(r.UNDER_ODDS)}
                     for r in table.itertuples()]
            if needs_backfill:
                detail = {row["team"]: row for row in fresh}
                for row in rows:
                    match = detail.get(row["team"])
                    if match:
                        row["conf"] = match["conf"]
                        row["last_wins"] = match["last_wins"]
                db.backfill_win_line_details(season, fresh)
            else:
                rows = fresh
                if db.available:
                    frozen = db.freeze_win_lines(season, rows)

    st.session_state[key] = (rows, frozen)
    return rows, frozen


def _odds_or_none(value):
    try:
        return None if value is None or value != value else int(value)
    except (TypeError, ValueError):
        return None


def _switch_to_vegas(season, rows):
    """
    Donmus cizgiler Vegas'inkiyle ayni degilse bir kez degistirir.

    Karsilastirma bellekte yapiliyor; cizgiler zaten Vegas'sa veritabanina
    hic gidilmiyor. Tahminler korunabildigi kadar korunuyor (bkz.
    db.replace_win_lines) ve kac tahminin sifirlandigi ekrana yaziliyor.
    """
    vegas = vegas_lines(season)
    if not vegas:
        return
    stale = [row for row in rows
             if row["team"] in vegas and (
                 row["line"] != vegas[row["team"]][0]
                 or row.get("over_odds") != vegas[row["team"]][1]
                 or row.get("under_odds") != vegas[row["team"]][2])]
    if not stale:
        return
    cleared = db.replace_win_lines(season, {row["team"]: vegas[row["team"]]
                                            for row in stale})
    if cleared is None:
        return
    for row in stale:
        row["line"], row["over_odds"], row["under_odds"] = vegas[row["team"]]
    # Tahminler degisti; oturumdaki kopyalar bayat.
    st.session_state.pop(f"ou_picks_{season}", None)
    st.session_state.pop(f"ou_crowd_{season}", None)
    for row in stale:
        st.session_state.pop(f"ou_pick_{season}_{row['team']}", None)
    st.session_state["ou_switched"] = cleared


def _load_picks(season, user_id):
    key = f"ou_picks_{season}"
    if key not in st.session_state:
        st.session_state[key] = db.get_win_picks(user_id, season) if db.available else {}
    return st.session_state[key]


def _load_crowd(season, force=False):
    """Kalabalik dagilimi. Her tiklamada degil, istenince tazeleniyor."""
    key = f"ou_crowd_{season}"
    if force or key not in st.session_state:
        st.session_state[key] = db.win_pick_counts(season) if db.available else {}
    return st.session_state[key]


def _on_pick(season, user_id, team, line, widget_key):
    """
    Secim degisince calisir.

    Streamlit geri cagridan sonra zaten bir tur donuyor; buradan elle
    st.rerun() cagirmak turu ikiye katlar ve sayfayi agirlastirir.
    """
    label = st.session_state.get(widget_key)
    wanted = FROM_LABEL.get(label)
    picks = st.session_state.setdefault(f"ou_picks_{season}", {})

    if wanted is None:
        if db.clear_win_pick(user_id, season, team):
            picks.pop(team, None)
        else:
            st.session_state["ou_error"] = f"{team} could not be cleared."
        return

    if db.save_win_pick(user_id, season, team, wanted, line):
        picks[team] = wanted
    else:
        # Yazma tutmadiysa ekranda dogruyu goster: widget'i eski degerine al.
        st.session_state[widget_key] = LABELS.get(picks.get(team))
        st.session_state["ou_error"] = f"{team} could not be saved."


# ==================== EKRAN ====================

def render_over_under_page():
    _css()
    season = get_current_season_year()
    is_open, clock = _deadline_state()

    st.markdown(f"""
        <div class="ou-hero">
          <h1>Over / Under {get_season_label(season)}</h1>
          <p>Call all 30 Las Vegas win totals before they lock. Pick over or under
             on each line - tap a pick again to clear it - then share your card.</p>
        </div>
    """, unsafe_allow_html=True)

    user = st.session_state.get("user")
    if not user:
        st.info("Sign in to record your predictions.")
        return
    if not db.available:
        st.warning("The database is unreachable, so predictions cannot be saved "
                   "right now.")
        return

    rows, frozen = _load_lines(season)
    if not rows:
        st.error("Win totals are unavailable - ESPN's standings feed did not answer.")
        if st.button("Try again", type="primary"):
            st.session_state.pop(f"ou_lines_{season}", None)
            st.cache_data.clear()
            st.rerun()
        return

    user_id = user["id"]
    picks = _load_picks(season, user_id)
    crowd = _load_crowd(season)
    identity = get_team_identity()

    switched = st.session_state.pop("ou_switched", None)
    if switched is not None:
        st.info("The lines are now the Las Vegas win totals. Picks the new line "
                "still covers were kept (over 45.5 is also over 43.5)"
                + (f"; {switched} that it did not were cleared - please call "
                   "those again." if switched else "."))
    if st.session_state.pop("ou_error", None):
        st.error("That pick could not be saved - the database refused the write.")

    _summary(rows, picks, crowd, is_open, clock)
    visible = _controls(season, rows, picks)
    _grid(season, user_id, visible, picks, crowd, identity, is_open)
    _export(season, rows, picks, crowd, identity, user)
    _method_note(frozen)


def _summary(rows, picks, crowd, is_open, clock):
    done, total = len(picks), len(rows)
    pct = round(100 * done / total) if total else 0
    overs = sum(1 for v in picks.values() if v == OVER)
    unders = done - overs

    # Kalabalige karsi gidilen tahmin sayisi: sayfayi "liste doldurma"
    # olmaktan cikaran sey bu - nerede ayristigini gosteriyor.
    against = 0
    for row in rows:
        mine = picks.get(row["team"])
        counts = crowd.get(row["team"])
        if not mine or not counts:
            continue
        total_votes = counts.get(OVER, 0) + counts.get(UNDER, 0)
        if total_votes >= 3 and counts.get(mine, 0) / total_votes < 0.4:
            against += 1

    avg = (sum(r["line"] for r in rows if r["team"] in picks) / done) if done else 0

    st.markdown(f"""
        <div class="ou-top">
          <div class="line1">
            <span class="ou-count">{done}<span> / {total} teams called</span></span>
            <span class="ou-clock {'' if is_open else 'closed'}">{clock}</span>
          </div>
          <div class="ou-track"><i style="width:{pct}%"></i></div>
          <div class="ou-stats">
            <span><b>{overs}</b> over</span>
            <span><b>{unders}</b> under</span>
            <span><b>{avg:.1f}</b> average line picked</span>
            <span><b>{against}</b> against the crowd</span>
          </div>
        </div>
    """, unsafe_allow_html=True)


def _controls(season, rows, picks):
    """Filtre ve siralama. Hepsi yerel - veritabanina gitmiyor."""
    left, middle, right = st.columns([1.5, 1.2, 1.3])
    with left:
        shown = st.segmented_control(
            "Show", ["All", "To do", "Done"], default="All",
            key=f"ou_filter_{season}")
    with middle:
        conf = st.segmented_control(
            "Conference", ["All", "East", "West"], default="All",
            key=f"ou_conf_{season}")
    with right:
        order = st.selectbox("Sort", ["Highest line", "Lowest line", "Team name"],
                             key=f"ou_sort_{season}", label_visibility="visible")

    out = list(rows)
    if shown == "To do":
        out = [r for r in out if r["team"] not in picks]
    elif shown == "Done":
        out = [r for r in out if r["team"] in picks]
    if conf in ("East", "West"):
        out = [r for r in out if (r.get("conf") or "").startswith(conf)]

    if order == "Lowest line":
        out.sort(key=lambda r: r["line"])
    elif order == "Team name":
        out.sort(key=lambda r: r["team_name"])
    else:
        out.sort(key=lambda r: -r["line"])

    if not out:
        st.caption("Nothing matches that filter.")
    return out


def _grid(season, user_id, rows, picks, crowd, identity, is_open):
    """Takim kartlari: ucer sutunluk izgara."""
    per_row = 3
    for start in range(0, len(rows), per_row):
        columns = st.columns(per_row, gap="small")
        for column, row in zip(columns, rows[start:start + per_row]):
            with column:
                _card(season, user_id, row, picks, crowd, identity, is_open)


def _card(season, user_id, row, picks, crowd, identity, is_open):
    team = row["team"]
    look = identity.get(team, {})
    current = picks.get(team)
    counts = crowd.get(team, {})
    votes = counts.get(OVER, 0) + counts.get(UNDER, 0)
    over_share = round(100 * counts.get(OVER, 0) / votes) if votes else None

    last = (f'last season {row["last_wins"]:.0f}-{82 - row["last_wins"]:.0f}'
            if row.get("last_wins") is not None else "")
    crowd_html = ""
    if over_share is not None:
        crowd_html = (f'<div class="ou-crowd">'
                      f'<div class="ou-crowdbar"><i style="width:{over_share}%"></i></div>'
                      f'{over_share}% of players took over</div>')
    else:
        crowd_html = '<div class="ou-crowd">no picks yet</div>'

    odds_html = ""
    if row.get("over_odds") is not None and row.get("under_odds") is not None:
        lean = implied_over(row["over_odds"], row["under_odds"])
        lean_html = ""
        if lean is not None and abs(lean - 0.5) >= 0.015:
            side, share = ("over", lean) if lean > 0.5 else ("under", 1 - lean)
            colour = "#8fbdf2" if side == "over" else "#f0a3a3"
            lean_html = (f'<span class="lean" style="color:{colour}">Vegas leans '
                         f'{side} {share * 100:.0f}%</span>')
        odds_html = (f'<div class="ou-odds"><span>O <b>{_american(row["over_odds"])}</b></span>'
                     f'<span>U <b>{_american(row["under_odds"])}</b></span>'
                     f'{lean_html}</div>')
    model_html = ""
    if row.get("projected") is not None:
        model_html = f' &middot; model {row["projected"]:.0f}'

    logo = look.get("logo") or ""
    logo_html = (f'<img class="ou-logo" src="{esc(logo)}" alt="">' if logo else "")

    st.markdown(f"""
        <div class="ou-card {'picked' if current else ''}"
             style="--team:{esc(look.get('color') or ACCENT)}">
          <div class="ou-head">
            {logo_html}
            <span>
              <div class="ou-name">{esc(look.get('short') or row['team_name'])}</div>
              <div class="ou-city">{esc(team)}</div>
            </span>
            <span class="ou-num">
              <div class="ou-line">{row['line']:.1f}</div>
              <div class="ou-lastwins">{esc(last)}{model_html}</div>
            </span>
          </div>
          {odds_html}
          {crowd_html}
        </div>
    """, unsafe_allow_html=True)

    if is_open:
        widget_key = f"ou_pick_{season}_{team}"
        st.segmented_control(
            f"{team} pick", ["Over", "Under"],
            default=LABELS.get(current),
            key=widget_key, label_visibility="collapsed",
            on_change=_on_pick,
            args=(season, user_id, team, row["line"], widget_key))
    else:
        css = current or "none"
        st.markdown(
            f'<span class="ou-pill {css}">'
            f'{LABELS.get(current, "NO PICK").upper()}</span>',
            unsafe_allow_html=True)


def _american(odds):
    odds = int(odds)
    return f"+{odds}" if odds > 0 else str(odds)


def _share(season, rows, picks, identity, user):
    """
    Paylasim karti (PNG). WhatsApp'a atilacak sey bu.

    Kart her turda cizilmiyor: logolari cekip resmi cizmek bir-iki saniye
    suruyor ve sayfanin tiklama hizini geri goturur. Istenince ciziliyor,
    tahminler degisince eskisi atiliyor.
    """
    key = f"ou_card_{season}"
    signature = tuple(sorted(picks.items()))
    cached = st.session_state.get(key)
    if cached and cached[0] != signature:
        st.session_state.pop(key, None)
        cached = None

    if not cached:
        if st.button("Create share image", type="primary", width="stretch",
                     disabled=not picks,
                     help="A picture of all your picks to post on WhatsApp, "
                          "Instagram or anywhere else."):
            with st.spinner("Drawing your card..."):
                png = over_under_card(get_season_label(season), rows, picks,
                                      identity, owner=user.get("username"))
            st.session_state[key] = (signature, png)
            cached = st.session_state[key]
    if cached:
        st.image(cached[1], width=480)
        st.download_button(
            "Download image (PNG)", cached[1],
            file_name=f"over-under-{get_season_label(season)}.png",
            mime="image/png", type="primary", width="stretch")


def _export(season, rows, picks, crowd, identity, user):
    """
    Paylasim karti (PNG) ve tahminlerin CSV hali.

    CSV tarayici indirmesi; dosya burada bellekte uretilip dogrudan
    veriliyor, yani buton her turda hazir.
    """
    st.subheader("Share your picks")
    _share(season, rows, picks, identity, user)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["team", "team_name", "conference", "line", "over_odds",
                     "under_odds", "last_season_wins", "my_pick", "crowd_over_pct"])
    for row in sorted(rows, key=lambda r: -r["line"]):
        counts = crowd.get(row["team"], {})
        votes = counts.get(OVER, 0) + counts.get(UNDER, 0)
        writer.writerow([
            row["team"], row["team_name"], row.get("conf") or "",
            f'{row["line"]:.1f}',
            "" if row.get("over_odds") is None else _american(row["over_odds"]),
            "" if row.get("under_odds") is None else _american(row["under_odds"]),
            "" if row.get("last_wins") is None else f'{row["last_wins"]:.0f}',
            picks.get(row["team"], ""),
            "" if not votes else round(100 * counts.get(OVER, 0) / votes),
        ])

    left, right = st.columns([1, 2.4])
    with left:
        st.download_button(
            "Export CSV", buffer.getvalue(),
            file_name=f"over-under-{get_season_label(season)}.csv",
            mime="text/csv", width="stretch")
    with right:
        if st.button("Refresh crowd numbers", width="stretch"):
            _load_crowd(season, force=True)
            st.rerun()


def _method_note(frozen):
    frozen_text = ("The lines are frozen, so everyone plays the same numbers no "
                   "matter when they pick."
                   if frozen else
                   "The lines will be frozen the first time this page opens with "
                   "the database reachable.")
    st.markdown(f"""
        <div class="ou-note">
          <b>Where the lines come from.</b> These are the Las Vegas season win
          totals, with the price on each side (American odds: -115 means risking
          115 to win 100). When the two prices differ, the book expects one side
          more than the other; "Vegas leans" is that expectation with the
          bookmaker's margin taken out. Every line ends in .5, so there are no
          ties.
          <br><br>
          <b>The model number.</b> Next to last season's record is this app's own
          projection: last season's wins pulled toward .500, plus roster strength
          from each team's best eight players by projected production and
          expected games. Where it disagrees with Vegas is where a pick is worth
          a second look - it is not a betting tip.
          <br><br>
          {frozen_text}
        </div>
    """, unsafe_allow_html=True)
