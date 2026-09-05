"""
Fantasy NBA Mock Draft - draft öncesi pratik sekmesi.

Snake ve auction formatlarında, yapay zekâ rakiplere veya tamamen manuel
karşı draft yapılabilir. Veriler ESPN'in güncel sezon draft sıralaması ve
geçen sezonun gerçek istatistikleridir.
"""

import json
import time

import pandas as pd
import streamlit as st

from services.database import db
from services.draft_data import (fetch_draft_rankings, get_draft_board,
                                 get_headshot_url)
from services.draft_engine import (
    SLOT_ELIGIBILITY,
    available_players,
    create_draft,
    current_round,
    current_team,
    deserialize,
    draft_board_grid,
    finalize_nomination,
    grade_draft,
    is_roster_full,
    is_user_turn,
    make_pick,
    max_affordable_bid,
    nominate,
    pick_in_round,
    picks_until_user_turn,
    roster_needs,
    run_ai_until_user,
    serialize,
    step_ai_once,
    team_summary,
    total_picks,
    upcoming_picks,
    user_bid,
    user_pass,
    user_team,
)
from services.nba_season import get_season_label

POSITION_FILTERS = ["TÜMÜ", "PG", "SG", "SF", "PF", "C"]

INJURY_LABELS = {
    "ACTIVE": ("", ""),
    "DAY_TO_DAY": ("GTD", "#eab308"),
    "OUT": ("OUT", "#ef4444"),
    "INJURY_RESERVE": ("IR", "#ef4444"),
    "SUSPENSION": ("SUSP", "#f97316"),
}

POS_COLORS = {
    "PG": "#4da6ff", "SG": "#22d3ee", "SF": "#4ade80",
    "PF": "#fbbf24", "C": "#f87171",
}


# --------------------------------------------------------------------- stil

def _inject_styles():
    st.markdown("""
        <style>
        .draft-hero {
            background: linear-gradient(135deg, #1d1f33 0%, #2a1b3d 100%);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px; padding: 16px 20px; margin-bottom: 14px;
        }
        .draft-hero h1 {
            margin: 0 0 3px 0; font-size: 1.45rem; font-weight: 800;
            background: linear-gradient(135deg, #ff8c00, #ff4b4b);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .draft-hero p { margin: 0; color: rgba(255,255,255,0.55); font-size: 0.85rem; }

        /* ---- sıra çubuğu ---- */
        .clock-bar {
            display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
            background: #1c2030;
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 12px; padding: 11px 16px; margin-bottom: 10px;
        }
        .clock-bar.on-clock {
            border-color: rgba(34,197,94,0.55);
            background: linear-gradient(90deg, rgba(34,197,94,0.15), rgba(34,197,94,0.03));
        }
        .clock-pill {
            font-size: 0.7rem; font-weight: 700; letter-spacing: 1px;
            text-transform: uppercase; padding: 3px 10px; border-radius: 20px;
            background: rgba(255,255,255,0.09); color: rgba(255,255,255,0.75);
            white-space: nowrap;
        }
        .clock-pill.live {
            background: rgba(34,197,94,0.22); color: #4ade80;
            animation: pulse 1.8s ease-in-out infinite;
        }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.55} }
        .clock-main { font-size: 1.02rem; font-weight: 700; color: #fff; }
        .clock-sub { font-size: 0.8rem; color: rgba(255,255,255,0.5); }

        .progress-track {
            height: 5px; background: rgba(255,255,255,0.07);
            border-radius: 4px; overflow: hidden; margin-bottom: 14px;
        }
        .progress-fill {
            height: 100%; border-radius: 4px;
            background: linear-gradient(90deg, #ff8c00, #ff4b4b);
            transition: width .4s ease;
        }

        /* ---- canlı seçim şeridi ---- */
        .feed-wrap {
            display: flex; gap: 8px; overflow-x: auto; padding: 4px 2px 10px 2px;
            margin-bottom: 6px;
        }
        .feed-card {
            flex: 0 0 auto; min-width: 152px; max-width: 152px;
            background: #1c2030;
            border: 1px solid rgba(255,255,255,0.09);
            border-left: 3px solid rgba(255,255,255,0.18);
            border-radius: 10px; padding: 8px 10px;
        }
        .feed-card.mine {
            border-left-color: #ffd700;
            background: linear-gradient(135deg, rgba(255,215,0,0.14), rgba(255,215,0,0.02));
        }
        .feed-card.fresh { border-left-color: #4ade80; }
        .feed-no {
            font-size: 0.64rem; color: rgba(255,255,255,0.42);
            letter-spacing: .5px; text-transform: uppercase;
        }
        .feed-name {
            font-size: 0.84rem; font-weight: 700; color: #fff;
            margin: 2px 0 1px 0; line-height: 1.2;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .feed-team { font-size: 0.7rem; color: rgba(255,255,255,0.5);
                     overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

        /* ---- draft board ---- */
        .board-scroll { overflow-x: auto; padding-bottom: 8px; }
        table.draft-board { border-collapse: separate; border-spacing: 3px; font-size: 0.72rem; }
        table.draft-board th {
            font-size: 0.66rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: .4px; color: rgba(255,255,255,0.62);
            padding: 5px 7px; white-space: nowrap; text-align: left;
            background: #232840; border-radius: 6px;
        }
        table.draft-board th.mine { color: #ffd700; background: rgba(255,215,0,0.12); }
        table.draft-board td {
            padding: 5px 7px; border-radius: 6px; min-width: 118px;
            background: #1a1e2c;
            border: 1px solid rgba(255,255,255,0.06);
            vertical-align: top;
        }
        table.draft-board td.mine {
            background: linear-gradient(135deg, rgba(255,215,0,0.13), rgba(255,215,0,0.02));
            border-color: rgba(255,215,0,0.35);
        }
        table.draft-board td.empty { background: #14172250; border-style: dashed; }
        table.draft-board .rnd {
            min-width: 34px; text-align: center; font-weight: 700;
            color: rgba(255,255,255,0.55); background: #232840;
        }
        .bd-name { font-weight: 600; color: rgba(255,255,255,0.92); display:block;
                   overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .bd-meta { color: rgba(255,255,255,0.42); font-size: 0.66rem; }

        /* ---- kadro / slotlar ---- */
        .pick-row {
            display: flex; align-items: center; gap: 9px;
            padding: 6px 9px; border-radius: 8px;
            background: #1a1e2c;
            border-left: 3px solid rgba(255,255,255,0.12);
            margin-bottom: 4px; font-size: 0.83rem;
        }
        .pick-row.mine {
            border-left-color: #ffd700;
            background: linear-gradient(90deg, rgba(255,215,0,0.12), rgba(255,215,0,0.02));
        }
        .pick-no { font-size: 0.7rem; color: rgba(255,255,255,0.4); min-width: 42px; }
        .pick-name { font-weight: 600; color: rgba(255,255,255,0.9); }
        .pick-meta { font-size: 0.72rem; color: rgba(255,255,255,0.45); margin-left: auto; }

        .slot-chip {
            display: inline-block; padding: 2px 8px; border-radius: 6px;
            font-size: 0.68rem; font-weight: 700; margin: 2px 3px 2px 0;
            background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.6);
        }
        .slot-chip.open { background: rgba(255,140,0,0.18); color: #ffa64d; }
        .slot-chip.done { background: rgba(34,197,94,0.15); color: #4ade80; }

        /* ---- seçili oyuncu kartı ---- */
        .sel-card {
            display: flex; gap: 14px; align-items: center;
            background: linear-gradient(135deg, rgba(77,166,255,0.12), rgba(77,166,255,0.03));
            border: 1px solid rgba(77,166,255,0.32);
            border-radius: 14px; padding: 12px 16px; margin-bottom: 10px;
        }
        .sel-card img { width: 62px; height: 45px; object-fit: cover; border-radius: 8px; }
        .sel-name { font-size: 1.12rem; font-weight: 800; color: #fff; line-height: 1.2; }
        .sel-meta { font-size: 0.76rem; color: rgba(255,255,255,0.55); margin-top: 2px; }
        .sel-stats { font-size: 0.76rem; color: rgba(255,255,255,0.72); margin-top: 4px; }

        .nom-card {
            background: linear-gradient(135deg, rgba(255,140,0,0.13), rgba(255,75,75,0.05));
            border: 1px solid rgba(255,140,0,0.38);
            border-radius: 14px; padding: 14px 18px; margin-bottom: 12px;
        }
        .nom-player { font-size: 1.2rem; font-weight: 800; color: #fff; }
        .nom-bid { font-size: 1.7rem; font-weight: 800; color: #ffd700; }

        .empty-note {
            text-align:center; padding: 18px; border-radius: 10px;
            background: #1a1e2c; color: rgba(255,255,255,0.5);
            font-size: 0.84rem;
        }

        /* =====================================================
           MOBIL (<=768px)
           Olculen: bu sayfada 48 adet 10px civari yazi vardi ve
           hizli secim butonlari 5 kolona yayilip alt alta diziliyordu.
           ===================================================== */
        @media (max-width: 768px) {
            /* NOT: styles.py kok font-size'i 14px yapiyor; 0.72rem = 10.1px
               oluyordu. Bu blokta bilerek px kullaniliyor. */
            .draft-hero { padding: 12px 14px; border-radius: 12px; }
            .draft-hero h1 { font-size: 19px; }
            .draft-hero p { font-size: 13px; }

            .clock-bar { padding: 9px 12px; gap: 9px; }
            .clock-pill { font-size: 12px !important; letter-spacing: .6px; }
            .clock-main { font-size: 15px; }
            .clock-sub { font-size: 12.5px; }

            /* Seride daha cok kart sigsin, yazilar okunur olsun */
            .feed-card { min-width: 136px; max-width: 136px; padding: 7px 9px; }
            .feed-no   { font-size: 12px; }
            .feed-name { font-size: 14px; }
            .feed-team { font-size: 12.5px; }

            /* Draft board: hucreler daralsin ama yazi buyusun */
            table.draft-board { font-size: 13px; }
            table.draft-board th { font-size: 12px; }
            table.draft-board td { min-width: 104px; padding: 5px 6px; }
            .bd-meta { font-size: 12px; }
            .board-scroll {
                -webkit-overflow-scrolling: touch;
                overscroll-behavior-x: contain;
            }

            .pick-row  { font-size: 14px; padding: 8px 10px; }
            .pick-no   { font-size: 12.5px; min-width: 48px; }
            .pick-meta { font-size: 12.5px; }
            .slot-chip { font-size: 12.5px; padding: 3px 9px; }

            .sel-card { padding: 11px 12px; gap: 11px; }
            .sel-card img { width: 54px; height: 40px; }
            .sel-name  { font-size: 16px; }
            .sel-meta  { font-size: 12.5px; }
            .sel-stats { font-size: 12.5px; }

            .nom-player { font-size: 17px; }
            .nom-bid    { font-size: 24px; }
            .empty-note { font-size: 14px; padding: 14px; }

            /* Satir ici style ile yazilan kucuk etiketler (badge, hizli
               secim ust yazisi, sekme altligi) rem hesabindan etkilenmesin. */
            .feed-card span, .sel-meta, .bd-meta { font-size: 12.5px !important; }
            .hl-quick-cap { font-size: 12.5px !important; }
        }

        /* Hızlı seçim butonları ile havuz tablosunun araç çubuğu üst üste
           binmesin diye araya boşluk. */
        .quick-gap { height: 26px; }
        </style>
    """, unsafe_allow_html=True)


def _injury_badge(status):
    label, color = INJURY_LABELS.get(status, ("", ""))
    if not label:
        return ""
    return (f"<span style='font-size:0.8rem;font-weight:700;color:{color};"
            f"border:1px solid {color};padding:0 5px;border-radius:4px;"
            f"margin-left:6px;'>{label}</span>")


def _pos_tag(pos):
    color = POS_COLORS.get(pos, "#9ca3af")
    return (f"<span style='color:{color};font-weight:700;font-size:0.7rem;'>{pos}</span>")


# ------------------------------------------------------------------ kurulum

def _render_setup(board):
    st.markdown(f"""
        <div class="draft-hero">
            <h1>🏀 Mock Draft Simülatörü</h1>
            <p>{get_season_label()} sezonu ESPN draft sıralamasıyla — gerçek draftından
            önce istediğin kadar prova yap.</p>
        </div>
    """, unsafe_allow_html=True)

    if board.empty:
        st.error("Draft havuzu şu anda alınamadı — ESPN'in fantasy API'si "
                 "ara ara bağlantıyı kesiyor.")
        st.caption("Genelde tek denemede düzeliyor.")
        if st.button("🔄 Tekrar dene", type="primary", width='stretch',
                     key="draft_pool_retry"):
            get_draft_board.clear()
            fetch_draft_rankings.clear()
            st.rerun()
        return

    st.caption(f"Havuzda {len(board)} sıralı oyuncu · "
               f"{int(board['ROOKIE'].sum())} çaylak/istatistiksiz")

    col_a, col_b = st.columns(2)

    with col_a:
        fmt_label = st.radio(
            "Draft formatı", ["Snake", "Auction"], horizontal=True, key="draft_format",
            help="Snake: sıra 1→N, N→1 döner. Auction: her takımın bütçesi vardır, "
                 "oyuncular açık artırmayla alınır.",
        )
        fmt = "snake" if fmt_label == "Snake" else "auction"

        opp_label = st.radio(
            "Rakipler", ["Yapay zekâ rakipler", "Tüm takımları ben seçeyim"],
            key="draft_opponent_mode",
            help="Yapay zekâ modunda tek bir takımı sen yönetirsin. Manuel modda "
                 "bütün takımların seçimlerini sen yaparsın.",
        )
        opponent_mode = "ai" if opp_label.startswith("Yapay") else "manual"

        team_count = st.select_slider("Takım sayısı", options=[4, 6, 8, 10, 12, 14],
                                      value=10, key="draft_team_count")

    with col_b:
        rounds = st.slider("Kadro büyüklüğü (tur)", min_value=5, max_value=16,
                           value=13, key="draft_rounds")

        if opponent_mode == "ai":
            user_slot = st.number_input(
                "Draft pozisyonun", min_value=1, max_value=int(team_count), value=1,
                key="draft_user_slot", help="Snake draftta kaçıncı sıradan seçeceğin.",
            )
        else:
            user_slot = 1

        if fmt == "auction":
            budget = st.number_input("Takım başı bütçe ($)", min_value=50, max_value=500,
                                     value=200, step=10, key="draft_budget")
        else:
            budget = 200

        difficulty = st.select_slider(
            "Rakip öngörülebilirliği",
            options=["Çok sadık", "Dengeli", "Öngörülemez"],
            value="Dengeli", key="draft_difficulty",
            help="Sadık: rakipler sıralamaya harfiyen uyar. Öngörülemez: sürpriz "
                 "seçimler ve reach'ler artar.",
        )
        randomness = {"Çok sadık": 0.12, "Dengeli": 0.35, "Öngörülemez": 0.7}[difficulty]

    live = st.checkbox(
        "Rakip seçimlerini canlı göster", value=True, key="draft_live_mode",
        help="Açıkken rakipler sırayla, tek tek seçim yapar ve ekranda akar. "
             "Kapalıyken sıra anında sana gelir.",
    )

    if fmt == "auction" and budget < rounds:
        st.warning(f"Bütçe kadro büyüklüğünden küçük olamaz — her oyuncu en az $1. "
                   f"{rounds} tur için en az ${rounds} gerekli.")
        return

    st.markdown("")
    if st.button("🚀 Draftı Başlat", type="primary", width='stretch',
                 key="draft_start_btn"):
        state = create_draft(
            board, team_count=int(team_count), rounds=int(rounds),
            user_slot=int(user_slot), fmt=fmt, opponent_mode=opponent_mode,
            budget=int(budget), ai_randomness=randomness,
        )
        state["live_mode"] = bool(live)
        st.session_state.draft_state = state
        st.session_state.draft_messages = []
        st.session_state.draft_saved_id = None
        st.session_state.draft_pending_ai = True
        st.rerun()

    _render_saved_drafts(board)


def _render_saved_drafts(board):
    user = st.session_state.get("user")
    if not user:
        st.info("Draftlarını kaydedip sonra geri yüklemek için giriş yap.")
        return

    db.ensure_draft_table()
    saved = db.list_mock_drafts(user["id"])
    if not saved:
        return

    st.markdown("---")
    st.subheader("Kayıtlı draftların")

    for row in saved:
        c1, c2, c3, c4 = st.columns([4, 2, 1, 1])
        with c1:
            status = "✅ Tamamlandı" if row["complete"] else "⏳ Devam ediyor"
            st.markdown(f"**{row['name']}**  \n"
                        f"<span style='font-size:0.86rem;color:#888'>"
                        f"{row['format'].title()} · {row['team_count']} takım · "
                        f"{row['rounds']} tur · {status}</span>",
                        unsafe_allow_html=True)
        with c2:
            if row["grade"]:
                st.metric("Not", row["grade"], label_visibility="collapsed")
        with c3:
            if st.button("Aç", key=f"load_{row['id']}", width='stretch'):
                record = db.load_mock_draft(user["id"], row["id"])
                if record:
                    saved_state = record["state"]
                    if isinstance(saved_state, str):
                        saved_state = json.loads(saved_state)
                    st.session_state.draft_state = deserialize(saved_state, board)
                    st.session_state.draft_saved_id = row["id"]
                    st.session_state.draft_messages = []
                    st.rerun()
                else:
                    st.error("Draft yüklenemedi.")
        with c4:
            if st.button("Sil", key=f"del_{row['id']}", width='stretch'):
                db.delete_mock_draft(user["id"], row["id"])
                st.rerun()


# ------------------------------------------------------------------ üst bilgi

def _render_clock(state):
    if state["complete"]:
        st.markdown("""
            <div class="clock-bar">
                <span class="clock-pill">Bitti</span>
                <span class="clock-main">Draft tamamlandı</span>
            </div>
        """, unsafe_allow_html=True)
        return

    team = current_team(state)
    on_clock = is_user_turn(state)

    if state["format"] == "auction":
        main = f"{team['name']} aday gösteriyor" if team else "Açık artırma"
        sub = f"Seçim {state['pick_number']} / {total_picks(state)}"
    else:
        main = team["name"] if team else ""
        sub = (f"Tur {current_round(state)} · Seçim {pick_in_round(state)}"
               f" (genel {state['pick_number']}/{total_picks(state)})")
        if state["opponent_mode"] == "ai" and not on_clock:
            waiting = picks_until_user_turn(state)
            if waiting:
                sub += f" · sıran {waiting} seçim sonra"

    pill = ("<span class='clock-pill live'>Sıra sende</span>" if on_clock
            else "<span class='clock-pill'>Sırada</span>")

    st.markdown(f"""
        <div class="clock-bar {'on-clock' if on_clock else ''}">
            {pill}
            <span class="clock-main">{main}</span>
            <span class="clock-sub">{sub}</span>
        </div>
    """, unsafe_allow_html=True)


def _render_progress(state):
    total = total_picks(state)
    done = min(len(state["log"]), total)
    pct = (done / total * 100) if total else 0
    st.markdown(f"""
        <div class="progress-track"><div class="progress-fill" style="width:{pct:.1f}%"></div></div>
    """, unsafe_allow_html=True)


# ------------------------------------------------------------- canlı akış

def _feed_html(state, count=9, fresh_overalls=()):
    """Son seçimleri yatay kart şeridi olarak üretir."""
    if not state["log"]:
        return ("<div class='empty-note'>Henüz seçim yapılmadı — "
                "ilk seçimle birlikte burada akmaya başlayacak.</div>")

    cards = []
    for entry in reversed(state["log"][-count:]):
        classes = ["feed-card"]
        if entry["slot"] == state["user_slot"]:
            classes.append("mine")
        if entry["overall"] in fresh_overalls:
            classes.append("fresh")

        label = (f"${entry['price']}" if entry["price"] is not None
                 else f"#{entry['overall']}")
        cards.append(
            f"<div class='{' '.join(classes)}'>"
            f"<div class='feed-no'>{label} · {entry['team'][:14]}</div>"
            f"<div class='feed-name'>{entry['player']}</div>"
            f"<div class='feed-team'>{_pos_tag(entry['pos'])} · {entry['nba_team']} "
            f"· ADP {entry['adp']}</div>"
            f"</div>"
        )
    return f"<div class='feed-wrap'>{''.join(cards)}</div>"


def _render_feed(state, fresh_overalls=()):
    st.markdown(_feed_html(state, fresh_overalls=fresh_overalls), unsafe_allow_html=True)


def _advance_ai(state):
    """
    Yapay zekâ seçimlerini ilerletir.

    Canlı mod açıksa her seçim tek tek yapılır ve şerit anlık güncellenir,
    böylece rakiplerin ne aldığı gerçek zamanlı görünür.
    """
    if state["opponent_mode"] == "manual" or state["complete"]:
        return []

    if not state.get("live_mode"):
        return run_ai_until_user(state)

    made = []
    placeholder = st.empty()
    status = st.empty()
    guard = 0

    while not state["complete"] and not is_user_turn(state) and guard < 500:
        guard += 1
        entry = step_ai_once(state)
        if entry is None:
            break
        made.append(entry)

        fresh = {entry["overall"]}
        with placeholder.container():
            st.markdown(_feed_html(state, fresh_overalls=fresh), unsafe_allow_html=True)
        price = f" (${entry['price']})" if entry["price"] is not None else ""
        status.caption(f"🟢 {entry['team']} → **{entry['player']}**{price}")
        time.sleep(0.32)

    placeholder.empty()
    status.empty()
    state["last_ai_picks"] = made
    return made


def _render_since_last(state):
    """Kullanıcı beklerken neler olduğunu özetler."""
    made = state.get("last_ai_picks") or []
    if not made or not is_user_turn(state):
        return
    names = ", ".join(f"**{m['player']}**" for m in made[:4])
    extra = f" ve {len(made) - 4} seçim daha" if len(made) > 4 else ""
    st.caption(f"Sen beklerken {len(made)} seçim yapıldı: {names}{extra}")


# ------------------------------------------------------------- draft board

def _render_draft_board(state):
    headers, rows = draft_board_grid(state)
    if not rows:
        st.markdown("<div class='empty-note'>Draft board ilk seçimle dolmaya başlar.</div>",
                    unsafe_allow_html=True)
        return

    head_cells = "".join(
        f"<th class=\"{'mine' if h['is_user'] else ''}\">{h['name'][:16]}</th>"
        for h in headers
    )
    body = []
    for i, row in enumerate(rows, start=1):
        cells = []
        for cell in row:
            if cell is None:
                cells.append("<td class='empty'>&nbsp;</td>")
                continue
            meta = (f"${cell['price']}" if cell["price"] is not None
                    else f"#{cell['overall']}")
            cells.append(
                f"<td class=\"{'mine' if cell['is_user'] else ''}\">"
                f"<span class='bd-name'>{cell['player']}</span>"
                f"<span class='bd-meta'>{cell['pos']} · {cell['nba_team']} · {meta}</span>"
                f"</td>"
            )
        label = f"T{i}" if state["format"] != "auction" else f"{i}."
        body.append(f"<tr><td class='rnd'>{label}</td>{''.join(cells)}</tr>")

    st.markdown(
        f"<div class='board-scroll'><table class='draft-board'>"
        f"<thead><tr><th></th>{head_cells}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    st.caption("Altın sütun senin takımın. Yatay kaydırarak tüm takımları görebilirsin.")


# ------------------------------------------------------------ auction paneli

def _render_auction_panel(state):
    nom = state.get("current_nomination")
    if not nom:
        return False

    player = nom["player"]
    user = user_team(state)
    high_team = next((t for t in state["teams"] if t["slot"] == nom["high_slot"]), None)
    leading = high_team["name"] if high_team else "?"

    st.markdown(f"""
        <div class="nom-card">
            <div class="nom-player">{player['name']}
                <span style="font-size:0.86rem;color:rgba(255,255,255,0.5);font-weight:500;">
                    {'/'.join(player['positions'])} · {player['team']} · ADP {player['adp']} ·
                    ESPN değeri ${player['auction']}
                </span>
            </div>
            <div style="margin-top:5px;">
                <span class="nom-bid">${nom['high_bid']}</span>
                <span style="color:rgba(255,255,255,0.6);margin-left:8px;">
                    en yüksek teklif — <strong>{leading}</strong>
                </span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if nom.get("history"):
        trail = " → ".join(f"{h['team'][:12]} ${h['bid']}" for h in nom["history"][-4:])
        st.caption(f"Teklif akışı: {trail}")

    if not nom.get("awaiting_user"):
        if st.button("Açık artırmayı kapat", type="primary", width='stretch',
                     key="auction_close_btn"):
            ok, msg = finalize_nomination(state)
            _push_message(ok, msg)
            _advance_ai(state)
            st.rerun()
        return True

    ceiling = max_affordable_bid(state, user)
    minimum = nom["high_bid"] + 1

    st.caption(f"Kalan bütçen ${user['budget'] - user['spent']} · "
               f"bu oyuncuya en fazla ${ceiling} verebilirsin "
               f"(kalan {state['rounds'] - len(user['picks'])} kadro yeri için 1$ ayrılıyor)")

    if ceiling < minimum:
        st.warning("Bu oyuncu için teklifini artıracak bütçen yok.")
        if st.button("Pas geç", width='stretch', key="auction_pass_broke"):
            ok, msg = user_pass(state)
            _push_message(ok, msg)
            _advance_ai(state)
            st.rerun()
        return True

    # Her turda alt/üst sınır değişiyor; sabit key ile Streamlit önceki
    # değeri yeni aralığa zorlayıp hata veriyor.
    bid_key = f"auction_bid_{nom['player_id']}_{nom['high_bid']}"

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        amount = st.number_input("Teklifin ($)", min_value=minimum, max_value=int(ceiling),
                                 value=minimum, step=1, key=bid_key)
    with c2:
        if st.button("Teklif ver", type="primary", width='stretch',
                     key="auction_bid_btn"):
            ok, msg = user_bid(state, amount)
            _push_message(ok, msg)
            if ok and not state.get("current_nomination", {}).get("awaiting_user"):
                finalize_nomination(state)
                _advance_ai(state)
            st.rerun()
    with c3:
        if st.button("Pas geç", width='stretch', key="auction_pass_btn"):
            ok, msg = user_pass(state)
            _push_message(ok, msg)
            _advance_ai(state)
            st.rerun()

    return True


# ------------------------------------------------------------------ havuz

def _pool_dataframe(state, players, needs):
    rows = []
    for p in players:
        positions = set(p.get("positions") or [p["pos"]])
        fills = any(positions & SLOT_ELIGIBILITY.get(s, set())
                    for s in needs if s in ("PG", "SG", "SF", "PF", "C", "G", "F"))
        status = INJURY_LABELS.get(p["injury"], ("", ""))[0]
        rows.append({
            "_id": p["id"],
            "": get_headshot_url(p["id"]),
            "İHT": "⭐" if fills else "",
            "Oyuncu": p["name"],
            "Poz": "/".join(p["positions"]),
            "Takım": p["team"],
            "ADP": p["adp"],
            "$": p["auction"],
            "Durum": status,
            "SY": round(p["pts"], 1),
            "RIB": round(p["reb"], 1),
            "AS": round(p["ast"], 1),
            "TP": round(p["stl"], 1),
            "BLK": round(p["blk"], 1),
            "FP": round(p["fpts"], 1),
        })
    return pd.DataFrame(rows)


def _render_quick_picks(state, filtered, needs, count=5):
    """
    Sıradaki en iyi birkaç oyuncu için tek tıklık butonlar.
    Tabloya girmeden hızlı seçim yapmayı sağlar.
    """
    can_act = is_user_turn(state) and not state["complete"]
    awaiting = bool(state.get("current_nomination"))
    if not can_act or awaiting:
        return

    top = filtered[:count]
    if not top:
        return

    verb = "Aday" if state["format"] == "auction" else "Seç"
    st.caption("Hızlı seçim — sıradaki en iyiler")
    cols = st.columns(len(top))
    for col, player in zip(cols, top):
        positions = set(player.get("positions") or [player["pos"]])
        star = "⭐ " if any(positions & SLOT_ELIGIBILITY.get(s, set())
                           for s in needs
                           if s in ("PG", "SG", "SF", "PF", "C", "G", "F")) else ""
        # Uzun soyadlar butonu iki satıra bölüp yükseklikleri bozuyor.
        surname = player["name"].split(" ", 1)[-1]
        if len(surname) > 12:
            surname = surname[:11] + "…"
        with col:
            st.markdown(
                f"<div class='hl-quick-cap' style='font-size:0.78rem;color:#8b8b9a;text-align:center;"
                f"overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>"
                f"{star}{player['pos']} · ADP {player['adp']} · ${player['auction']}</div>",
                unsafe_allow_html=True,
            )
            if st.button(f"{verb}: {surname}", key=f"quick_{player['id']}",
                         width='stretch', help=f"{player['name']} — "
                         f"{player['fpts']:.0f} FP, {player['team']}"):
                _commit_player(state, player)

    # Tablonun sağ üstteki araç çubuğu butonların üstüne binmesin.
    st.markdown("<div class='quick-gap'></div>", unsafe_allow_html=True)


def _commit_player(state, player):
    """Snake'te seçer, auction'da açık artırmaya çıkarır; sonra AI'yı ilerletir."""
    if state["format"] == "auction":
        ok, msg = nominate(state, player["id"])
        _push_message(ok, msg)
        if ok and not is_user_turn(state):
            finalize_nomination(state)
            _advance_ai(state)
    else:
        ok, msg = make_pick(state, player["id"])
        _push_message(ok, msg)
        if ok:
            _advance_ai(state)
    st.rerun()


def _render_pool(state):
    pool = available_players(state)
    if not pool:
        st.markdown("<div class='empty-note'>Havuzda seçilebilecek oyuncu kalmadı.</div>",
                    unsafe_allow_html=True)
        return

    c1, c2, c3 = st.columns([2.2, 2.6, 1.4])
    with c1:
        search = st.text_input("Oyuncu ara", placeholder="isim veya takım…",
                               key="draft_search", label_visibility="collapsed")
    with c2:
        position = st.radio("Pozisyon", POSITION_FILTERS, horizontal=True,
                            key="draft_pos_filter", label_visibility="collapsed")
    with c3:
        sort_by = st.selectbox("Sırala", ["ADP", "Fantasy puanı", "Değer ($)", "Sahiplenme"],
                               key="draft_sort", label_visibility="collapsed")

    filtered = pool
    if position != "TÜMÜ":
        filtered = [p for p in filtered if position in (p.get("positions") or [p["pos"]])]
    if search:
        needle = search.lower().strip()
        filtered = [p for p in filtered
                    if needle in p["name"].lower() or needle in p["team"].lower()]

    key_fn = {
        "ADP": lambda p: p["adp"],
        "Fantasy puanı": lambda p: -p["fpts"],
        "Değer ($)": lambda p: -p["auction"],
        "Sahiplenme": lambda p: -p["owned"],
    }[sort_by]
    filtered = sorted(filtered, key=key_fn)

    if not filtered:
        st.markdown("<div class='empty-note'>Bu filtreye uyan oyuncu yok.</div>",
                    unsafe_allow_html=True)
        return

    user = user_team(state)
    needs = set(roster_needs(user, state["rounds"])) if user else set()
    shown = filtered[:120]

    # Hızlı seçim: en çok yapılan hamle "sıradaki en iyiyi al" - tek tıkla olsun.
    _render_quick_picks(state, filtered, needs)

    df = _pool_dataframe(state, shown, needs)

    # Havuz veya filtre değiştikçe key değişsin ki eski satır seçimi
    # taşınıp yanlış oyuncuyu işaret etmesin (arama metni de dahil).
    table_key = (f"pool_{len(state['drafted_ids'])}_{position}_{sort_by}"
                 f"_{len(shown)}_{hash(search) & 0xffff}")

    event = st.dataframe(
        df.drop(columns=["_id"]),
        hide_index=True,
        width='stretch',
        height=380,
        on_select="rerun",
        selection_mode="single-row",
        key=table_key,
        column_config={
            "": st.column_config.ImageColumn("", width="small"),
            "İHT": st.column_config.TextColumn("★", width="small",
                                               help="Kadrondaki açık pozisyona uyuyor"),
            "Oyuncu": st.column_config.TextColumn("Oyuncu", width="medium"),
            "ADP": st.column_config.NumberColumn("ADP", format="%d", width="small"),
            "$": st.column_config.NumberColumn("$", format="%d", width="small"),
            "FP": st.column_config.NumberColumn("FP", format="%.1f", width="small"),
        },
    )

    st.caption(f"{len(filtered)} oyuncu · ★ kadrondaki açık pozisyona uyanları gösterir · "
               f"seçmek için satıra tıkla")

    rows = (event.selection.rows if event and getattr(event, "selection", None) else [])
    # Seçim indeksi listeyle uyumsuz kalabilir (filtre değişimi); sınır kontrolü.
    if not rows or rows[0] >= len(shown):
        st.info("Listeden bir oyuncuya tıkla, sonra aşağıdan seçimini onayla.")
        return

    _render_selected_player(state, shown[rows[0]])


def _render_selected_player(state, player):
    stats = ("geçen sezon NBA istatistiği yok" if player["rookie"] or player["gp"] == 0
             else (f"{player['pts']:.1f} sy · {player['reb']:.1f} rib · "
                   f"{player['ast']:.1f} as · {player['stl']:.1f} tp · "
                   f"{player['blk']:.1f} blok · <strong>{player['fpts']:.1f} FP</strong> "
                   f"({int(player['gp'])} maç)"))

    st.markdown(f"""
        <div class="sel-card">
            <img src="{get_headshot_url(player['id'])}" alt="">
            <div>
                <div class="sel-name">{player['name']}{_injury_badge(player['injury'])}</div>
                <div class="sel-meta">{'/'.join(player['positions'])} · {player['team']} ·
                    ADP {player['adp']} · ESPN değeri ${player['auction']} ·
                    %{player['owned']:.0f} sahiplenme</div>
                <div class="sel-stats">{stats}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    can_act = is_user_turn(state) and not state["complete"]
    awaiting = bool(state.get("current_nomination"))

    if not can_act:
        st.button("Sıran değil", disabled=True, width='stretch', key="pick_disabled")
        return
    if awaiting:
        st.button("Önce açık artırmayı bitir", disabled=True, width='stretch',
                  key="pick_blocked")
        return

    if state["format"] == "auction":
        if st.button(f"🔨 {player['name']} için açık artırma başlat", type="primary",
                     width='stretch', key="confirm_nominate"):
            _commit_player(state, player)
    else:
        if st.button(f"✅ {player['name']} oyuncusunu seç", type="primary",
                     width='stretch', key="confirm_pick"):
            _commit_player(state, player)


# ------------------------------------------------------------------ takımlar

def _render_my_team(state):
    team = user_team(state)
    if not team:
        return

    summary = team_summary(state, team)
    needs = roster_needs(team, state["rounds"])

    if state["format"] == "auction":
        c1, c2, c3 = st.columns(3)
        c1.metric("Oyuncu", f"{summary['players']}/{state['rounds']}")
        c2.metric("Kalan bütçe", f"${summary['remaining']}")
        c3.metric("Fantasy", f"{summary['fpts']:.0f}")
    else:
        c1, c2 = st.columns(2)
        c1.metric("Oyuncu", f"{summary['players']}/{state['rounds']}")
        c2.metric("Fantasy", f"{summary['fpts']:.0f}")

    if needs:
        chips = "".join(f"<span class='slot-chip open'>{s}</span>" for s in needs)
        st.markdown(f"<div style='margin:6px 0 10px 0'>Açık yerler: {chips}</div>",
                    unsafe_allow_html=True)
    else:
        st.markdown("<div style='margin:6px 0 10px 0'>"
                    "<span class='slot-chip done'>Kadro tamam</span></div>",
                    unsafe_allow_html=True)

    if not team["picks"]:
        st.caption("Henüz oyuncu almadın.")
        return

    for pick in team["picks"]:
        p = pick["player"]
        price = f"${pick['price']}" if pick["price"] is not None else f"T{pick['round']}"
        st.markdown(
            f"<div class='pick-row mine'>"
            f"<span class='pick-no'>{price}</span>"
            f"<span class='pick-name'>{p['name']}</span>"
            f"<span class='pick-meta'>{_pos_tag(p['pos'])} · {p['team']} · "
            f"{p['fpts']:.0f} FP</span></div>",
            unsafe_allow_html=True,
        )


def _render_all_teams(state):
    grades = grade_draft(state) if state["complete"] else {}

    for team in state["teams"]:
        summary = team_summary(state, team)
        grade = grades.get(team["slot"], {})
        title = f"{team['name']} — {summary['players']} oyuncu · {summary['fpts']:.0f} FP"
        if grade:
            title += f" · {grade['grade']} (#{grade['rank']})"
        if state["format"] == "auction":
            title += f" · ${summary['spent']}/{team['budget']}"

        with st.expander(title, expanded=team["is_user"]):
            if not team["picks"]:
                st.caption("Henüz seçim yok.")
                continue
            open_slots = roster_needs(team, state["rounds"])
            if open_slots:
                chips = "".join(f"<span class='slot-chip open'>{s}</span>"
                                for s in open_slots)
                st.markdown(f"<div style='margin-bottom:6px'>İhtiyaç: {chips}</div>",
                            unsafe_allow_html=True)
            rows = [{
                "Tur": pick["round"],
                "Oyuncu": pick["player"]["name"],
                "Poz": "/".join(pick["player"]["positions"]),
                "Takım": pick["player"]["team"],
                "ADP": pick["player"]["adp"],
                "Fiyat": f"${pick['price']}" if pick["price"] is not None else "—",
                "FP": round(pick["player"]["fpts"], 1),
            } for pick in team["picks"]]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')


def _render_log(state):
    if not state["log"]:
        st.caption("Henüz seçim yapılmadı.")
        return
    for entry in reversed(state["log"][-80:]):
        mine = entry["slot"] == state["user_slot"]
        price = f"${entry['price']}" if entry["price"] is not None else f"#{entry['overall']}"
        st.markdown(
            f"<div class='pick-row {'mine' if mine else ''}'>"
            f"<span class='pick-no'>{price}</span>"
            f"<span class='pick-name'>{entry['player']}</span>"
            f"<span class='pick-meta'>{_pos_tag(entry['pos'])} · {entry['nba_team']} → "
            f"{entry['team']}</span></div>",
            unsafe_allow_html=True,
        )


def _render_upcoming(state):
    if state["format"] == "auction" or state["complete"]:
        return
    coming = upcoming_picks(state, 6)
    if not coming:
        return
    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
    st.caption("Sıradaki seçimler")
    for item in coming:
        mark = " **← sen**" if item["is_user"] else ""
        st.markdown(f"<span style='font-size:0.86rem;color:#8b8b9a'>"
                    f"#{item['overall']} (T{item['round']}) {item['team']}{mark}</span>",
                    unsafe_allow_html=True)


# ------------------------------------------------------------------ sonuç

def _render_results(state):
    grades = grade_draft(state)
    user = user_team(state)
    my_grade = grades.get(user["slot"], {}) if user else {}

    st.success(f"Draft tamamlandı! Takımın **{my_grade.get('grade', '-')}** aldı "
               f"— {len(state['teams'])} takım arasında **{my_grade.get('rank', '-')}.** sırada.")

    rows = []
    for team in state["teams"]:
        summary = team_summary(state, team)
        grade = grades.get(team["slot"], {})
        rows.append({
            "Sıra": grade.get("rank", 0),
            "Takım": team["name"] + (" (sen)" if team["is_user"] else ""),
            "Not": grade.get("grade", "-"),
            "Fantasy": summary["fpts"],
            "SY": summary["pts"], "RIB": summary["reb"], "AS": summary["ast"],
            "TP": summary["stl"], "BLK": summary["blk"],
            "Harcanan": f"${summary['spent']}" if state["format"] == "auction" else "—",
        })

    st.dataframe(pd.DataFrame(rows).sort_values("Sıra"), hide_index=True, width='stretch')


def _render_save(state):
    user = st.session_state.get("user")
    if not user:
        st.info("Bu draftı kaydetmek için giriş yapman gerekiyor.")
        return

    grades = grade_draft(state)
    u = user_team(state)
    my_grade = grades.get(u["slot"], {}).get("grade") if u else None
    default_name = (f"{state['format'].title()} · {state['team_count']} takım · "
                    f"{state['created_at'][:10]}")

    c1, c2 = st.columns([3, 1])
    with c1:
        name = st.text_input("Draft adı", value=default_name, key="draft_save_name",
                             label_visibility="collapsed")
    with c2:
        if st.button("💾 Kaydet", type="primary", width='stretch', key="draft_save_btn"):
            db.ensure_draft_table()
            draft_id = db.save_mock_draft(
                user["id"], name or default_name, serialize(state),
                grade=my_grade, draft_id=st.session_state.get("draft_saved_id"),
            )
            if draft_id:
                st.session_state.draft_saved_id = draft_id
                st.success("Draft kaydedildi.")
            else:
                st.error("Draft kaydedilemedi. Veritabanı bağlantısını kontrol et.")


# ------------------------------------------------------------------ yardımcılar

def _push_message(ok, msg):
    messages = st.session_state.setdefault("draft_messages", [])
    messages.append(("ok" if ok else "err", msg))
    del messages[:-4]


def _flush_messages():
    for kind, msg in st.session_state.get("draft_messages", []):
        if kind == "err":
            st.warning(msg)
    st.session_state.draft_messages = []


# ------------------------------------------------------------------ giriş noktası

def render_mock_draft_page():
    _inject_styles()

    with st.spinner("Draft havuzu hazırlanıyor…"):
        board = get_draft_board()

    state = st.session_state.get("draft_state")
    if state is None:
        _render_setup(board)
        return

    # Havuz oturum kaybında boşalmış olabilir (kayıttan yükleme vb.)
    if not state.get("pool") and not board.empty:
        state = deserialize(state, board)
        st.session_state.draft_state = state

    head_l, head_r = st.columns([4, 1])
    with head_l:
        mode = "Auction" if state["format"] == "auction" else "Snake"
        opp = "yapay zekâ" if state["opponent_mode"] == "ai" else "manuel"
        st.markdown(f"""
            <div class="draft-hero">
                <h1>🏀 Mock Draft — {mode}</h1>
                <p>{state['team_count']} takım · {state['rounds']} tur · {opp} rakipler
                   · {get_season_label()} sıralaması</p>
            </div>
        """, unsafe_allow_html=True)
    with head_r:
        st.markdown("")
        if st.button("Yeni draft", width='stretch', key="draft_new_btn"):
            for k in ("draft_state", "draft_saved_id", "draft_messages",
                      "draft_pending_ai"):
                st.session_state.pop(k, None)
            st.rerun()

    _flush_messages()

    # Sıra çubuğu ve ilerleme yer tutucuya çiziliyor: yapay zekâ turundan
    # sonra yenisi ekleneceğine mevcut olan güncelleniyor.
    clock_slot = st.empty()
    progress_slot = st.empty()

    def paint_status():
        with clock_slot.container():
            _render_clock(state)
        with progress_slot.container():
            _render_progress(state)

    paint_status()

    # Draft başlar başlamaz ilk yapay zekâ turunu canlı oynat.
    if st.session_state.pop("draft_pending_ai", False):
        _advance_ai(state)
        paint_status()

    if state["complete"]:
        _render_results(state)
        _render_save(state)
        st.markdown("---")
        tab_board, tab_teams, tab_log = st.tabs(
            ["📋 Draft Board", "Takımlar", "Akış"])
        with tab_board:
            _render_draft_board(state)
        with tab_teams:
            _render_all_teams(state)
        with tab_log:
            _render_log(state)
        return

    # --- canlı seçim şeridi (herkesin ne aldığı) ---
    _render_feed(state)
    _render_since_last(state)

    auction_open = False
    if state["format"] == "auction":
        auction_open = _render_auction_panel(state)

    main, side = st.columns([2.6, 1.4])
    with main:
        _render_pool(state)
    with side:
        tab_mine, tab_all = st.tabs(["Takımım", "Lig"])
        with tab_mine:
            _render_my_team(state)
            _render_upcoming(state)
        with tab_all:
            _render_all_teams(state)

    st.markdown("---")
    tab_board, tab_log, tab_save = st.tabs(["📋 Draft Board", "Tüm seçimler", "Kaydet"])
    with tab_board:
        _render_draft_board(state)
    with tab_log:
        _render_log(state)
    with tab_save:
        _render_save(state)
