"""
Alt/ust tahmini: her NBA takiminin sezonluk galibiyet baremi.

Kullanici 30 takimin her biri icin "ust" mu "alt" mi der; tahminler
20 Ekim aksami kapanir, sezon baslayinca da kapali kalir.

Baremler bahis cizgisi degil, uygulamanin kendi modelinin sayilari
(bkz. services/win_totals). Ekranda da oyle yaziyor - Vegas cizgisi
gibi gosterilmiyor.

Barem yarismanin ilk acilisinda veritabaninda donduruluyor; model her
gun yeniden hesaplansa erken tahmin eden ile gec tahmin eden farkli
bareme oynamis olurdu.
"""
from datetime import datetime

import streamlit as st

from services.database import db
from services.nba_season import get_current_season_year, get_season_label
from services.win_totals import project_win_totals
from utils.text import esc

# Tahminler bu ana kadar acik. Sezon 21 Ekim'de basliyor; bir gun once
# kapaniyor ki kimse ilk maclari gordukten sonra tahmin degistirmesin.
DEADLINE = datetime(2026, 10, 20, 23, 59, 59)


def _css():
    st.markdown("""
        <style>
        .ou-hero { margin: 0 0 6px; }
        .ou-hero h1 { font-size: 1.6rem; font-weight: 800; letter-spacing: -.6px;
                      margin: 0 0 4px; }
        .ou-hero p { color: #8C99B2; font-size: .9rem; margin: 0; line-height: 1.5; }

        .ou-bar {
            display: flex; align-items: center; justify-content: space-between;
            gap: 12px; flex-wrap: wrap;
            border: 1px solid rgba(255,255,255,.09); background: #171C27;
            border-radius: 13px; padding: 11px 14px; margin: 10px 0 14px;
        }
        .ou-bar b { color: #E8ECF4; }
        .ou-bar .left { font-size: .88rem; color: #A9B6CE; }
        .ou-bar .right { font-size: .8rem; color: #6B7893; }
        .ou-bar.closed { border-color: rgba(230,103,103,.4); }

        .ou-row {
            display: flex; align-items: center; gap: 10px;
            border-bottom: 1px solid rgba(255,255,255,.055);
            padding: 7px 2px;
        }
        .ou-team { font-weight: 800; font-size: .92rem; letter-spacing: -.2px;
                   color: #E8ECF4; }
        .ou-sub { font-size: .74rem; color: #6B7893; }
        .ou-line { font-size: 1.05rem; font-weight: 800; color: #E8ECF4;
                   white-space: nowrap; }

        .ou-pill { font-size: .7rem; font-weight: 800; letter-spacing: .4px;
                   padding: 3px 8px; border-radius: 6px; white-space: nowrap; }
        .ou-pill.over  { background: rgba(57,135,229,.16); color: #8fbdf2; }
        .ou-pill.under { background: rgba(230,103,103,.14); color: #f0a3a3; }
        .ou-pill.none  { background: rgba(255,255,255,.06); color: #8C99B2; }

        .ou-note {
            border: 1px solid rgba(255,255,255,.07); border-radius: 12px;
            padding: 11px 13px; margin-top: 16px;
            color: #6B7893; font-size: .78rem; line-height: 1.6;
        }
        .ou-note b { color: #A9B6CE; }
        </style>
    """, unsafe_allow_html=True)


def _deadline_state():
    """(acik mi, kalan sure metni)"""
    now = datetime.now()
    if now > DEADLINE:
        return False, "Predictions closed on 20 October."
    remaining = DEADLINE - now
    days = remaining.days
    hours = remaining.seconds // 3600
    if days > 0:
        return True, f"{days} days {hours} hours left"
    minutes = (remaining.seconds % 3600) // 60
    return True, f"{hours} hours {minutes} minutes left"


def _lines_for_season(season):
    """
    Dondurulmus baremleri getirir; ilk acilista modelden uretip dondurur.

    Veritabani yoksa model dogrudan gosterilir ama tahmin kaydedilemez.
    """
    if db.available and db.win_lines_frozen(season):
        rows = db.get_win_lines(season)
        return [{"team": r["team"], "team_name": r["team_name"],
                 "line": float(r["line"]),
                 "projected": float(r["projected"]) if r["projected"] is not None else None}
                for r in rows], True

    table = project_win_totals()
    if table.empty:
        return [], False

    rows = [{"team": r.TEAM, "team_name": r.NAME, "line": float(r.LINE),
             "projected": float(r.PROJECTED)} for r in table.itertuples()]
    frozen = False
    if db.available:
        frozen = db.freeze_win_lines(season, rows)
        if frozen:
            # Dondurduktan sonra veritabanindaki hali tek dogru kaynak.
            return _lines_for_season(season)
    return rows, frozen


def render_over_under_page():
    _css()
    season = get_current_season_year()
    label = get_season_label(season)
    is_open, remaining = _deadline_state()

    st.markdown(f"""
        <div class="ou-hero">
          <h1>Over / Under {label}</h1>
          <p>Call every team's win total for the season. Pick over or under
             on each of the 30 lines before they lock.</p>
        </div>
    """, unsafe_allow_html=True)

    user = st.session_state.get("user")
    if not user:
        st.info("Sign in to record your predictions.")
        return

    rows, frozen = _lines_for_season(season)
    if not rows:
        st.error("Win totals are unavailable right now - ESPN's standings feed "
                 "did not answer.")
        if st.button("Try again", type="primary"):
            st.cache_data.clear()
            st.rerun()
        return

    if not db.available:
        st.warning("The database is unreachable, so predictions cannot be saved "
                   "right now. The lines below are still correct.")
        return

    user_id = user["id"]
    picks = db.get_win_picks(user_id, season)
    crowd = db.win_pick_counts(season)
    made = len(picks)

    st.markdown(f"""
        <div class="ou-bar {'' if is_open else 'closed'}">
          <span class="left"><b>{made}</b> of <b>{len(rows)}</b> teams predicted</span>
          <span class="right">{'Closes 20 October - ' + remaining if is_open
                               else remaining}</span>
        </div>
    """, unsafe_allow_html=True)

    if not is_open:
        st.caption("The window has closed. Your picks are shown as they were "
                   "submitted and can no longer be changed.")

    for row in rows:
        team = row["team"]
        current = picks.get(team)
        counts = crowd.get(team, {"over": 0, "under": 0})
        total = counts["over"] + counts["under"]
        share = (f"{round(100 * counts['over'] / total)}% over"
                 if total else "no picks yet")

        col_team, col_line, col_pick = st.columns([3.1, 1.1, 2.2])
        with col_team:
            st.markdown(
                f'<div class="ou-row" style="border:none;padding:2px">'
                f'<span><span class="ou-team">{esc(row["team_name"])}</span><br>'
                f'<span class="ou-sub">{esc(team)} &middot; {share}</span></span>'
                f'</div>', unsafe_allow_html=True)
        with col_line:
            st.markdown(f'<div class="ou-line">{row["line"]:.1f}</div>',
                        unsafe_allow_html=True)
        with col_pick:
            if is_open:
                choice = st.radio(
                    f"{team} pick", ["Over", "Under", "-"],
                    index={"over": 0, "under": 1}.get(current, 2),
                    horizontal=True, key=f"ou_{season}_{team}",
                    label_visibility="collapsed")
                wanted = {"Over": "over", "Under": "under"}.get(choice)
                if wanted != current:
                    # Yazma basarisizsa yeniden calistirma: tahmin degismemis
                    # olacagi icin ayni kosul tekrar dogru cikar ve sayfa
                    # sonsuz donguye girer.
                    if wanted is None:
                        saved = db.clear_win_pick(user_id, season, team)
                    else:
                        saved = db.save_win_pick(user_id, season, team, wanted,
                                                 row["line"])
                    if saved:
                        st.rerun()
                    else:
                        st.error(f"{team} could not be saved - the database "
                                 "refused the write.")
            else:
                css = current or "none"
                text = current.upper() if current else "NO PICK"
                st.markdown(f'<span class="ou-pill {css}">{text}</span>',
                            unsafe_allow_html=True)

    _method_note(frozen)


def _method_note(frozen):
    frozen_text = ("The lines were frozen when this page first opened, so "
                   "everyone plays the same numbers no matter when they pick."
                   if frozen else
                   "The lines shown are being generated live and will be frozen "
                   "the first time this page opens with the database reachable.")
    st.markdown(f"""
        <div class="ou-note">
          <b>These are not betting lines.</b> A sportsbook's season win-total
          market is not available from any feed this app can reach, so these
          numbers are this app's own model, not Las Vegas. Do not read them as
          odds.
          <br><br>
          <b>How each line is worked out.</b> Two signals. Last season's record,
          pulled toward .500 - NBA teams regress year to year, so a raw 60-win
          season overstates the next one. Then roster strength: each team's best
          eight players by projected production multiplied by the games they are
          expected to play, so an injured star counts for the time he is actually
          on the floor. Roster strength is converted into wins using its measured
          relationship with last season's results rather than a guessed weight,
          and the 30 projections are shifted to add up to the 1,230 wins a season
          actually contains. Every line ends in .5 so there are no ties.
          <br><br>
          <b>What it does not know.</b> Trades and signings after today, the
          schedule, coaching changes, and injuries that have not happened yet.
          {frozen_text}
        </div>
    """, unsafe_allow_html=True)
