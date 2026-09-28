"""
Draft Strategy sekmesi.

Kullanici ligini tarif ediyor (kac takim, hangi draft sistemi, kacinci
siradan seciyor); sayfa da o kosullarda farkli stratejilerin nasil
sonuclanacagini gosteriyor: hangi turda kimin masada kalmasi bekleniyor,
her strateji hangi kadroyu veriyor ve o kadro hangi kategorilerde
onde/geride oluyor.

Uretim olcusu gelecek sezonun mac basi projeksiyonu; yaninda sakatlik
da hesaba giriyor - hem draft gunu tasinan bayrak hem projeksiyondaki
mac sayisi. Kullanici riske karsi durusunu kendisi seciyor. Sinirlari
sayfanin altinda aciklikla yaziyor.
"""
import streamlit as st

from services.draft_data import fetch_draft_rankings, get_draft_board
from services.nba_season import get_season_label
from services.strategy_engine import (AUCTION_SHAPES, CAT_LABELS,
                                     DEFAULT_RISK, FULL_SEASON_GAMES,
                                     INJURY_WORDS, NINE_CAT, RISK_LEVELS,
                                     auction_plan, availability_weighted,
                                     category_scores, draftable_depth,
                                     fragility_tier, injury_notes,
                                     league_baseline, picks_for_slots,
                                     replacement_level, slot_notes,
                                     strategy_report)

# Iraksak palet: mavi (ortalamanin ustu) <-> kirmizi (altinda), notr gri
# orta nokta. Uygulamanin kart zeminine (#171C27) karsi dogrulandi:
# CVD ayrimi 19.2, normal gorus 29.0, kontrast >= 3:1.
ABOVE = "#3987e5"
BELOW = "#e66767"
MIDLINE = "#383835"
MUTED = "#898781"


def _css():
    st.markdown("""
        <style>
        .ds-hero { margin: 0 0 6px; }
        .ds-hero h1 { font-size: 1.6rem; font-weight: 800; letter-spacing: -.6px;
                      margin: 0 0 4px; }
        .ds-hero p { color: #8C99B2; font-size: .9rem; margin: 0; line-height: 1.5; }

        .ds-picks { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 2px; }
        .ds-pick {
            border: 1px solid rgba(255,255,255,.09);
            background: rgba(255,255,255,.035);
            border-radius: 9px; padding: 5px 9px; font-size: .74rem;
            white-space: nowrap;
        }
        .ds-pick b { color: #E8ECF4; font-weight: 800; }
        .ds-pick span { color: #6B7893; }

        .ds-note {
            border-left: 2px solid rgba(255,255,255,.14);
            padding: 2px 0 2px 11px; margin: 8px 0;
            color: #A9B6CE; font-size: .86rem; line-height: 1.55;
        }

        .ds-card {
            border: 1px solid rgba(255,255,255,.09);
            background: #171C27; border-radius: 15px;
            padding: 14px 15px; margin-bottom: 10px;
        }
        .ds-card.top { border-color: rgba(57,135,229,.45); }
        .ds-head { display: flex; align-items: baseline; justify-content: space-between;
                   gap: 10px; margin-bottom: 4px; }
        .ds-name { font-size: 1.02rem; font-weight: 800; letter-spacing: -.2px; }
        .ds-metric { font-size: .78rem; color: #8C99B2; white-space: nowrap; }
        .ds-metric b { color: #E8ECF4; font-size: .95rem; }
        .ds-blurb { font-size: .86rem; color: #A9B6CE; line-height: 1.55; margin-bottom: 8px; }
        .ds-tags { display: flex; flex-wrap: wrap; gap: 5px; }
        .ds-tag { font-size: .68rem; font-weight: 800; letter-spacing: .4px;
                  padding: 3px 7px; border-radius: 6px; white-space: nowrap; }
        .ds-tag.win  { background: rgba(57,135,229,.16); color: #8fbdf2; }
        .ds-tag.lose { background: rgba(230,103,103,.14); color: #f0a3a3; }
        .ds-tag.punt { background: rgba(255,255,255,.07); color: #93A1BC; }

        .ds-meta { font-size: .78rem; color: #6B7893; line-height: 1.6; margin-top: 8px; }
        .ds-meta b { color: #A9B6CE; font-weight: 700; }

        /* Dayaniklilik cubugu: kadronun sezonun ne kadarini oynamasi
           beklendigi. Sayi her zaman yaninda yaziyor; cubuk tek basina
           anlam tasimiyor. */
        .ds-health { display: flex; align-items: center; gap: 8px; margin: 8px 0 2px;
                     font-size: .78rem; color: #8C99B2; }
        .ds-health .bar { flex: 0 0 74px; height: 5px; border-radius: 3px;
                          background: rgba(255,255,255,.1); overflow: hidden; }
        .ds-health .bar i { display: block; height: 100%; border-radius: 3px; }
        .ds-health b { color: #E8ECF4; font-weight: 700; }

        .ds-limit {
            border: 1px solid rgba(255,255,255,.07);
            border-radius: 12px; padding: 11px 13px; margin-top: 14px;
            color: #6B7893; font-size: .78rem; line-height: 1.6;
        }
        </style>
    """, unsafe_allow_html=True)


def _picks_strip(picks):
    chips = "".join(
        f'<span class="ds-pick"><b>#{pick}</b> <span>R{rnd}</span></span>'
        for rnd, pick in picks)
    st.markdown(f'<div class="ds-picks">{chips}</div>', unsafe_allow_html=True)


def _profile_chart(profile, punts, baseline_note=True):
    """
    Kategori profili: lig ortalamasi bir takima gore artı/eksi.

    Veri kutuplu oldugu icin iraksak cubuk kullaniliyor; orta cizgi
    "ortalama takim" demek. Punt edilen kategori renkle degil, ayrica
    etiketle de isaretleniyor (renk tek basina anlam tasimasin).
    """
    cats = [c for c in NINE_CAT]
    values = [profile.get(c, 0.0) for c in cats]
    span = max(0.9, max(abs(v) for v in values) * 1.15)

    row_h, label_w, gap = 26, 42, 8
    plot_w = 230
    width = label_w + plot_w + 46
    height = len(cats) * row_h + 16
    mid_x = label_w + plot_w / 2

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'style="max-width:420px;display:block" role="img" '
        f'aria-label="Category profile against an average team">'
    ]
    # Orta cizgi (ortalama takim)
    parts.append(f'<line x1="{mid_x}" y1="6" x2="{mid_x}" y2="{height - 10}" '
                 f'stroke="{MIDLINE}" stroke-width="1"/>')

    for i, cat in enumerate(cats):
        y = 8 + i * row_h
        cy = y + row_h / 2 - 4
        value = values[i]
        punted = cat in punts
        bar = (abs(value) / span) * (plot_w / 2)
        bar = max(bar, 1.5)
        colour = MUTED if punted else (ABOVE if value >= 0 else BELOW)
        x = mid_x if value >= 0 else mid_x - bar
        opacity = ".45" if punted else "1"
        tip = (f"{CAT_LABELS[cat]}: {value:+.2f} vs average team"
               + (" (punted)" if punted else ""))
        parts.append(
            f'<text x="{label_w - 8}" y="{cy + 4}" text-anchor="end" '
            f'font-size="10.5" font-weight="700" fill="#A9B6CE">'
            f'{CAT_LABELS[cat]}</text>')
        parts.append(
            f'<rect x="{x:.1f}" y="{cy - 6:.1f}" width="{bar:.1f}" height="12" '
            f'rx="3" fill="{colour}" opacity="{opacity}">'
            f'<title>{tip}</title></rect>')
        text_x = mid_x + bar + 6 if value >= 0 else mid_x - bar - 6
        anchor = "start" if value >= 0 else "end"
        label = "punted" if punted else f"{value:+.2f}"
        parts.append(
            f'<text x="{text_x:.1f}" y="{cy + 4:.1f}" text-anchor="{anchor}" '
            f'font-size="9.5" font-weight="700" fill="{MUTED}">{label}</text>')

    parts.append("</svg>")
    st.markdown("".join(parts), unsafe_allow_html=True)
    if baseline_note:
        st.caption("Each bar is this roster against an average team in your "
                   "league. Right of the line is ahead.")


# Kadro tablosunda ismin yanina konan uyari. Tek basina renk/ikon anlam
# tasimasin diye Games ve Injury cut sutunlari ayni satirda duruyor.
FRAGILE_MARKS = {0: "", 1: " ⚠", 2: " ⚠⚠"}


def _player_cell(item):
    """Oyuncu adi + kirilganlik isareti."""
    tier = fragility_tier(item.get("availability", 1.0))
    return f"{item['player']}{FRAGILE_MARKS[tier]}"


def _status_text(item):
    """Sakatlik bayragi okunur hale; sagliklı oyuncuda bos kalir."""
    status = item.get("injury")
    if not status or status == "ACTIVE":
        return ""
    return INJURY_WORDS.get(status, str(status).replace("_", " ").lower())


def _roster_table(roster, auction=False):
    rows = []
    for item in roster:
        cut = item.get("shortfall") or 0.0
        common = {
            "Games": item["games"] if item.get("games") else "-",
            "Status": _status_text(item),
            # Sakatlik hesabinin bu oyuncuya ne yaptigi acikca gorunsun:
            # degerinin yuzde kaci yedek seviyesiyle degistirildi.
            "Injury cut": f"-{cut * 100:.0f}%" if cut > 0.005 else "-",
        }
        if auction:
            rows.append({
                "Player": _player_cell(item),
                "Pos": item["pos"],
                "Team": item["team"],
                "Price": f"${item['price']}",
                **common,
            })
        else:
            rows.append({
                "Rd": item["round"],
                "Pick": f"#{item['pick']}",
                "Player": _player_cell(item),
                "Pos": item["pos"],
                "Team": item["team"],
                "ADP": item["adp"] if item["adp"] else "-",
                **common,
            })
    st.dataframe(rows, hide_index=True, width="stretch")
    marked = sum(1 for item in roster
                 if fragility_tier(item.get("availability", 1.0)))
    st.caption(
        f"⚠ is projected to miss a chunk of the season, ⚠⚠ more "
        f"than a quarter of it ({marked} of {len(roster)} here). Games is the "
        f"projected number played out of {FULL_SEASON_GAMES}; Status is the flag "
        "the player carries today. Injury cut is how much of the player's edge "
        "was handed back to a replacement for the games he is not expected to "
        "play - it is what the setting above changes.")


def _health_row(durability):
    """
    Kadronun beklenen musaitligi: cubuk + her zaman yazili sayi.

    Renk ortalama draft edilen oyuncuya gore anlam tasiyor, sabit bir esige
    gore degil; sayfanin geri kalaninda da olcut "ortalama bir takim".
    """
    share = durability["availability"]
    reference = durability.get("reference") or 0.0
    missed = durability["games_missed"]
    gap = share - reference
    colour = ABOVE if gap >= -0.01 else (MUTED if gap >= -0.05 else BELOW)
    fragile = len(durability["fragile"])
    tail = (f" &middot; {fragile} projected well under a full season"
            if fragile else "")
    against = (f" against <b>{reference * 100:.0f}%</b> for an average drafted "
               "player" if reference else "")
    st.markdown(f"""
        <div class="ds-health">
          <span class="bar"><i style="width:{share * 100:.0f}%;
                background:{colour}"></i></span>
          <span>Roster plays <b>{share * 100:.0f}%</b> of the season{against}
                &middot; <b>{missed}</b> games missed across the roster{tail}</span>
        </div>
    """, unsafe_allow_html=True)


def _strategy_card(report, index, rounds):
    punts = report["punts"]
    top = index == 0
    wins = report["expected_wins"]
    tags = "".join(
        f'<span class="ds-tag win">{CAT_LABELS[c]}</span>' for c in report["strong"])
    tags += "".join(
        f'<span class="ds-tag lose">{CAT_LABELS[c]}</span>' for c in report["weak"])
    tags += "".join(
        f'<span class="ds-tag punt">{CAT_LABELS[c]} punted</span>' for c in punts)

    st.markdown(f"""
        <div class="ds-card {'top' if top else ''}">
          <div class="ds-head">
            <span class="ds-name">{report['name']}</span>
            <span class="ds-metric"><b>{wins:.1f}</b> / 9 cats</span>
          </div>
          <div class="ds-blurb">{report['blurb']}</div>
          <div class="ds-tags">{tags}</div>
          <div class="ds-meta"><b>Works when:</b> {report['works_when']}<br>
               <b>Risk:</b> {report['risk']}</div>
        </div>
    """, unsafe_allow_html=True)

    _health_row(report["durability"])
    flagged = report["durability"]["flagged"]
    if flagged:
        listed = ", ".join(f"{name} ({INJURY_WORDS.get(status, status.lower())})"
                           for name, status in flagged[:3])
        st.caption(f"Carrying a flag today: {listed}.")

    # En iyi siradaki stratejinin detayi tiklamadan gorunsun
    with st.expander(f"Target roster and category profile - {report['name']}",
                     expanded=top):
        col1, col2 = st.columns([1.15, 1])
        with col1:
            _roster_table(report["roster"])
        with col2:
            _profile_chart(report["profile"], punts)


def _setup():
    """Lig ayarlari. Degerler oturumda tutulur ki sekme degisince kaybolmasin."""
    st.markdown(f"""
        <div class="ds-hero">
          <h1>Draft Strategy</h1>
          <p>Describe your league and see how each strategy plays out from your
             seat: who is likely there at your picks, what roster you end up
             with, and where that roster wins. Built on
             {get_season_label()} projections, with injuries priced in.</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        teams = st.number_input("Teams in your league", min_value=4, max_value=20,
                                value=st.session_state.get("ds_teams", 10), step=1,
                                key="ds_teams")
    with col2:
        rounds = st.number_input("Roster size (rounds)", min_value=5, max_value=20,
                                 value=st.session_state.get("ds_rounds", 13), step=1,
                                 key="ds_rounds")

    draft_type = st.radio(
        "Draft type", ["Snake", "Linear", "Auction"], horizontal=True,
        key="ds_type",
        help="Snake reverses the order every round. Linear keeps the same order. "
             "Auction gives every team a budget to bid with.")

    slots, budget = [], 200
    if draft_type == "Auction":
        budget = st.number_input("Budget per team ($)", min_value=50, max_value=500,
                                 value=st.session_state.get("ds_budget", 200), step=10,
                                 key="ds_budget")
    else:
        slots = st.multiselect(
            "Your draft slot", list(range(1, int(teams) + 1)),
            default=st.session_state.get("ds_slots", [min(3, int(teams))]),
            key="ds_slots",
            help="Pick more than one if you run more than one team.")
        if not slots:
            st.info("Choose the position you draft from to see your picks.")

    # Sakatliga ne kadar agirlik verilecegi kullanicinin karari: bazi ligler
    # kirilgan yildizi ucuza almayi tercih eder, bazilari hic dokunmaz.
    keys = list(RISK_LEVELS)
    risk = st.radio(
        "Injury risk", keys,
        format_func=lambda key: RISK_LEVELS[key]["name"],
        index=keys.index(st.session_state.get("ds_risk", DEFAULT_RISK)),
        horizontal=True, key="ds_risk",
        help="How much a player's expected missed games should count against "
             "him when the rosters below are built.")
    st.caption(RISK_LEVELS[risk]["note"])

    return int(teams), int(rounds), draft_type, sorted(slots), int(budget), risk


def render_draft_strategy_page():
    _css()
    teams, rounds, draft_type, slots, budget, risk = _setup()

    if fetch_draft_rankings().empty:
        st.error("The draft pool is unavailable right now - ESPN's fantasy API "
                 "drops connections from time to time.")
        if st.button("Try again", type="primary"):
            st.cache_data.clear()
            st.rerun()
        return

    board = get_draft_board()
    scores = category_scores(board, draftable_depth(teams, rounds))

    covered = int(scores["PROJECTED"].sum())
    if covered < len(scores) * 0.5:
        st.caption(f"{get_season_label()} projections were unavailable for most "
                   "of the pool, so last season's per-game production is being "
                   "used instead.")

    st.markdown("---")

    if draft_type == "Auction":
        # Acik artirmada da kadro, mac kacirma beklentisi dusuldukten sonraki
        # degere gore kuruluyor - yoksa en kirilgan yildiz her zaman en iyi
        # "para karsiligi" gorunur.
        weighted = availability_weighted(
            scores, replacement_level(scores, teams, rounds),
            risk_weight=RISK_LEVELS[risk]["weight"])
        st.subheader("Budget shapes")
        st.caption(f"${budget} for {rounds} roster spots. Every open spot needs "
                   "at least $1, so the budget below is what is actually spendable.")
        for key, shape in AUCTION_SHAPES.items():
            plan = auction_plan(weighted, budget, rounds, punts=[], shape=key)
            st.markdown(f"""
                <div class="ds-card">
                  <div class="ds-head">
                    <span class="ds-name">{shape['name']}</span>
                    <span class="ds-metric">top {shape['stars']} take
                      <b>${int(budget * shape['top_share'])}</b></span>
                  </div>
                  <div class="ds-blurb">{shape['blurb']}</div>
                  <div class="ds-meta"><b>Works when:</b> {shape['works_when']}<br>
                       <b>Risk:</b> {shape['risk']}</div>
                </div>
            """, unsafe_allow_html=True)
            _health_row(plan["durability"])
            with st.expander(f"Sample roster - {shape['name']}"):
                _roster_table(plan["roster"], auction=True)
                st.caption(f"Spends ${plan['spent']} of ${budget}.")
                _profile_chart(plan["profile"], [])
        _limits()
        return

    if not slots:
        return

    picks = picks_for_slots(teams, slots, rounds, snake=(draft_type == "Snake"))
    st.subheader("Your picks")
    _picks_strip(picks)
    notes = slot_notes(teams, slots, rounds, snake=(draft_type == "Snake"))
    notes += injury_notes(scores, picks)
    for note in notes:
        st.markdown(f'<div class="ds-note">{note}</div>', unsafe_allow_html=True)

    st.subheader("Strategies from this seat")
    st.caption("Ordered by how many of the nine categories each roster projects "
               "to take against an average team in your league, after expected "
               "missed games are taken off.")
    reports = strategy_report(scores, picks, teams=teams, rounds=rounds,
                              risk=risk)
    for index, report in enumerate(reports):
        _strategy_card(report, index, rounds)

    _limits()


def _limits():
    season = get_season_label()
    st.markdown(f"""
        <div class="ds-limit">
          <b>How this is worked out.</b> Category strength comes from ESPN's
          {season} per-game projections, turned into z-scores across the players
          your league actually drafts. Players without a projection fall back to
          last season's production. Percentages are weighted by volume, so a
          high percentage on two attempts does not outrank a good shooter on
          eight. Who is left at each pick comes from current ESPN ADP: anyone
          whose ADP is well before your pick is assumed gone.
          <br><br>
          <b>How injuries are priced.</b> Two separate signals. The projection
          carries an expected games total, which already absorbs known long-term
          absences; on top of that, a player flagged today takes a further cut,
          and the more serious the flag the larger it is. A missed game is not
          counted as zero production - the roster spot is assumed to be filled
          from the waiver wire, so the real cost of an injury is the gap between
          the player and a replacement-level one. That also means being hurt can
          never make a player look better. Your league's average team is measured
          the same way, because every team loses games.
          <br><br>
          <b>What it does not know.</b> Weekly variance, a trade or a signing
          that changes a role, waiver moves during the season, and what the other
          managers in your league actually do. Projections are one provider's
          opinion, not fact, and an injury that happens after today's flag is
          not in them. Treat the category counts as a comparison between
          strategies, not a forecast.
        </div>
    """, unsafe_allow_html=True)
