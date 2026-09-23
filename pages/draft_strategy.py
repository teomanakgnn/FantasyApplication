"""
Draft Strategy sekmesi.

Kullanici ligini tarif ediyor (kac takim, hangi draft sistemi, kacinci
siradan seciyor); sayfa da o kosullarda farkli stratejilerin nasil
sonuclanacagini gosteriyor: hangi turda kimin masada kalmasi bekleniyor,
her strateji hangi kadroyu veriyor ve o kadro hangi kategorilerde
onde/geride oluyor.

Sayilar tahmin degil; gecen sezonun mac basi uretimi ve bugunku ADP
uzerinden hesaplaniyor. Sinirlari sayfanin altinda aciklikla yaziyor.
"""
import streamlit as st

from services.draft_data import fetch_draft_rankings, get_draft_board
from services.strategy_engine import (AUCTION_SHAPES, CAT_LABELS, NINE_CAT,
                                     auction_plan, category_scores,
                                     draftable_depth, league_baseline,
                                     picks_for_slots, slot_notes,
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


def _roster_table(roster, auction=False):
    rows = []
    for item in roster:
        if auction:
            rows.append({
                "Player": item["player"],
                "Pos": item["pos"],
                "Team": item["team"],
                "Price": f"${item['price']}",
            })
        else:
            rows.append({
                "Rd": item["round"],
                "Pick": f"#{item['pick']}",
                "Player": item["player"],
                "Pos": item["pos"],
                "Team": item["team"],
                "ADP": item["adp"] if item["adp"] else "-",
            })
    st.dataframe(rows, hide_index=True, width="stretch")


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
    st.markdown("""
        <div class="ds-hero">
          <h1>Draft Strategy</h1>
          <p>Describe your league and see how each strategy plays out from your
             seat: who is likely there at your picks, what roster you end up
             with, and where that roster wins.</p>
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
    return int(teams), int(rounds), draft_type, sorted(slots), int(budget)


def render_draft_strategy_page():
    _css()
    teams, rounds, draft_type, slots, budget = _setup()

    if fetch_draft_rankings().empty:
        st.error("The draft pool is unavailable right now - ESPN's fantasy API "
                 "drops connections from time to time.")
        if st.button("Try again", type="primary"):
            st.cache_data.clear()
            st.rerun()
        return

    board = get_draft_board()
    scores = category_scores(board, draftable_depth(teams, rounds))

    st.markdown("---")

    if draft_type == "Auction":
        st.subheader("Budget shapes")
        st.caption(f"${budget} for {rounds} roster spots. Every open spot needs "
                   "at least $1, so the budget below is what is actually spendable.")
        for key, shape in AUCTION_SHAPES.items():
            plan = auction_plan(scores, budget, rounds, punts=[], shape=key)
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
    for note in slot_notes(teams, slots, rounds, snake=(draft_type == "Snake")):
        st.markdown(f'<div class="ds-note">{note}</div>', unsafe_allow_html=True)

    st.subheader("Strategies from this seat")
    st.caption("Ordered by how many of the nine categories each roster projects "
               "to take against an average team in your league.")
    reports = strategy_report(scores, picks, teams=teams, rounds=rounds)
    for index, report in enumerate(reports):
        _strategy_card(report, index, rounds)

    _limits()


def _limits():
    st.markdown("""
        <div class="ds-limit">
          <b>How this is worked out.</b> Category strength comes from last
          season's per-game production, turned into z-scores across the players
          your league actually drafts. Percentages are weighted by volume, so a
          high percentage on two attempts does not outrank a good shooter on
          eight. Availability at each pick comes from current ESPN ADP: anyone
          whose ADP is well before your pick is assumed gone.
          <br><br>
          <b>What it does not know.</b> Weekly variance, injuries, waiver moves
          and what the other managers in your league actually do. Treat the
          category counts as a comparison between strategies, not a forecast.
        </div>
    """, unsafe_allow_html=True)
