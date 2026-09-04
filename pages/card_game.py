"""
Card Connections - NBA Card Game UI
Premium game-card design with network layout.
"""
import streamlit as st
import streamlit.components.v1 as components
from services.card_game_engine import GameState, ConnectionChecker
from services.nba_players_data import CONNECTION_TYPES


# ── Team colour palette ────────────────────────────────────────────
TEAM_COLORS = {
    "Los Angeles Lakers":       ("#552583", "#FDB927"),
    "Boston Celtics":           ("#007A33", "#BA9653"),
    "Golden State Warriors":    ("#1D428A", "#FFC72C"),
    "Milwaukee Bucks":          ("#00471B", "#EEE1C6"),
    "Denver Nuggets":           ("#0E2240", "#FEC524"),
    "Phoenix Suns":             ("#1D1160", "#E56020"),
    "Dallas Mavericks":         ("#00538C", "#B8C4CA"),
    "Philadelphia 76ers":       ("#006BB6", "#ED174C"),
    "Miami Heat":               ("#98002E", "#F9A01B"),
    "Oklahoma City Thunder":    ("#007AC1", "#EF6100"),
    "Minnesota Timberwolves":   ("#0C2340", "#236192"),
    "New York Knicks":          ("#006BB6", "#F58426"),
    "Cleveland Cavaliers":      ("#860038", "#FDBB30"),
    "Sacramento Kings":         ("#5A2D81", "#63727A"),
    "Indiana Pacers":           ("#002D62", "#FDBB30"),
    "Los Angeles Clippers":     ("#C8102E", "#1D428A"),
    "Toronto Raptors":          ("#CE1141", "#000000"),
    "Chicago Bulls":            ("#CE1141", "#000000"),
    "Atlanta Hawks":            ("#E03A3E", "#C1D32F"),
    "Memphis Grizzlies":        ("#5D76A9", "#12173F"),
    "New Orleans Pelicans":     ("#0C2340", "#C8102E"),
    "San Antonio Spurs":        ("#C4CED4", "#000000"),
    "Houston Rockets":          ("#CE1141", "#000000"),
    "Brooklyn Nets":            ("#000000", "#FFFFFF"),
    "Charlotte Hornets":        ("#1D1160", "#00788C"),
    "Portland Trail Blazers":   ("#E03A3E", "#000000"),
    "Utah Jazz":                ("#002B5C", "#F9A01B"),
    "Washington Wizards":       ("#002B5C", "#E31837"),
    "Detroit Pistons":          ("#C8102E", "#1D42BA"),
    "Orlando Magic":            ("#0077C0", "#000000"),
}


def _team_clr(team, idx=0):
    return TEAM_COLORS.get(team, ("#6366f1", "#a78bfa"))[idx]


# ════════════════════════════════════════════════════════════════════
#  CSS INJECTION
# ════════════════════════════════════════════════════════════════════
def _inject_card_game_css():
    st.markdown("""
    <style>
        /* ───── ROOT TOKENS ───── */
        :root {
            --cg-green: #10b981;
            --cg-blue: #3b82f6;
            --cg-amber: #f59e0b;
            --cg-orange: #f97316;
            --cg-dark: #0a0e1a;
            --cg-dark2: #141829;
            --cg-border: #232840;
            --cg-text: #e2e8f0;
            --cg-text-dim: #8892b0;
            --cg-red: #ef4444;
            --cg-purple: #8b5cf6;
            --cg-gold: #fbbf24;
            --cg-surface: rgba(20,24,41,0.85);
        }

        /* ─── KEYFRAMES ─── */
        @keyframes cg-float {
            0%,100% { transform:translateY(0); }
            50% { transform:translateY(-8px); }
        }
        @keyframes cg-pulse-glow {
            0%,100% { box-shadow:0 0 15px rgba(251,191,36,0.15); }
            50% { box-shadow:0 0 30px rgba(251,191,36,0.3); }
        }
        @keyframes cg-shimmer-move {
            0% { background-position:-200% center; }
            100% { background-position:200% center; }
        }
        @keyframes cg-card-deal {
            0% { opacity:0; transform:translateY(40px) rotateX(15deg) scale(0.85); }
            60% { opacity:1; transform:translateY(-5px) rotateX(-2deg) scale(1.02); }
            100% { opacity:1; transform:translateY(0) rotateX(0) scale(1); }
        }
        @keyframes cg-score-pop {
            0% { transform:scale(1); }
            50% { transform:scale(1.15); }
            100% { transform:scale(1); }
        }
        @keyframes cg-slide-up {
            0% { opacity:0; transform:translateY(20px); }
            100% { opacity:1; transform:translateY(0); }
        }
        @keyframes cg-gradient-shift {
            0% { background-position:0% 50%; }
            50% { background-position:100% 50%; }
            100% { background-position:0% 50%; }
        }
        @keyframes cg-bot-pattern {
            0% { transform:rotate(0deg); }
            100% { transform:rotate(360deg); }
        }
        @keyframes cg-confetti-fall {
            0% { transform:translateY(-100vh) rotate(0deg); opacity:1; }
            100% { transform:translateY(100vh) rotate(720deg); opacity:0; }
        }
        @keyframes cg-ring-spin {
            0% { transform:rotate(0deg); }
            100% { transform:rotate(360deg); }
        }
        @keyframes cg-badge-pulse {
            0%,100% { transform:scale(1); }
            50% { transform:scale(1.08); }
        }

        /* ───── LOBBY ───── */
        .cg-lobby-container {
            text-align:center; padding:2.5rem 0.5rem 1.5rem;
            position:relative;
        }
        .cg-lobby-container::before {
            content:'';
            position:absolute; inset:-50px;
            background:radial-gradient(ellipse at 30% 20%, rgba(139,92,246,0.08) 0%, transparent 50%),
                        radial-gradient(ellipse at 70% 80%, rgba(251,191,36,0.06) 0%, transparent 50%);
            pointer-events:none; z-index:0;
        }
        .cg-lobby-title {
            font-size:3.5rem!important; font-weight:950!important;
            background:linear-gradient(135deg,#fbbf24 0%,#ef4444 35%,#8b5cf6 70%,#3b82f6 100%);
            background-size:200% 200%;
            animation:cg-gradient-shift 4s ease infinite;
            -webkit-background-clip:text; -webkit-text-fill-color:transparent;
            background-clip:text; letter-spacing:-2px;
            filter:drop-shadow(0 0 40px rgba(251,191,36,0.2));
            position:relative; z-index:1;
            line-height:1.1!important;
        }
        .cg-lobby-subtitle {
            color:var(--cg-text-dim)!important; font-size:1.08rem!important;
            margin-top:6px!important; position:relative; z-index:1;
            letter-spacing:0.5px;
        }

        /* ─── Lobby Cards ─── */
        .cg-rules-card {
            background:linear-gradient(160deg, rgba(20,24,41,0.95), rgba(10,14,26,0.98));
            border:1px solid rgba(255,255,255,0.06);
            border-radius:20px;
            padding:1.5rem 1.6rem; margin:1rem auto; max-width:620px; text-align:left;
            box-shadow:0 12px 40px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04);
            backdrop-filter:blur(20px);
            animation:cg-slide-up 0.6s ease both;
        }
        .cg-rules-card:nth-child(2) { animation-delay:0.15s; }
        .cg-rules-title {
            font-size:1.15rem!important; font-weight:700!important;
            color:var(--cg-text)!important; margin-bottom:0.8rem!important;
            display:flex; align-items:center; gap:8px;
            padding-bottom:10px;
            border-bottom:1px solid rgba(255,255,255,0.05);
        }
        .cg-connection-row {
            display:flex; align-items:center; gap:12px;
            padding:10px 14px; margin:5px 0; border-radius:12px;
            transition:all .22s cubic-bezier(.4,0,.2,1);
        }
        .cg-connection-row:hover {
            transform:translateX(6px);
            box-shadow:0 4px 15px rgba(0,0,0,0.2);
        }
        .cg-conn-badge {
            min-width:54px; padding:6px 12px; border-radius:10px;
            font-weight:800; font-size:0.9rem; text-align:center; color:#fff;
            letter-spacing:0.3px;
            box-shadow:0 2px 8px rgba(0,0,0,0.3);
        }
        .cg-conn-label { font-weight:700; color:var(--cg-text)!important; font-size:0.93rem; }
        .cg-conn-desc  { color:var(--cg-text-dim)!important; font-size:0.78rem; margin-top:1px; }

        /* ───── SCOREBOARD ───── */
        .cg-scoreboard {
            display:flex; justify-content:space-between; align-items:center;
            background:linear-gradient(140deg, rgba(20,24,41,0.97), rgba(10,14,26,0.97));
            border:1px solid rgba(255,255,255,0.06);
            border-radius:20px;
            padding:1.1rem 1.8rem; margin-bottom:1rem;
            box-shadow:0 8px 35px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04);
            position:relative; overflow:hidden;
        }
        /* Subtle animated accent line on top */
        .cg-scoreboard::before {
            content:'';
            position:absolute; top:0; left:0; right:0; height:3px;
            background:linear-gradient(90deg, var(--cg-green), var(--cg-blue), var(--cg-purple), var(--cg-gold));
            background-size:300% 100%;
            animation:cg-gradient-shift 3s linear infinite;
        }
        .cg-score-side { text-align:center; min-width:110px; }
        .cg-score-label {
            font-size:0.7rem!important; color:var(--cg-text-dim)!important;
            text-transform:uppercase; letter-spacing:2px; font-weight:800;
        }
        .cg-score-value {
            font-size:2.6rem!important; font-weight:950!important;
            color:var(--cg-text)!important; line-height:1.1;
            font-family:'Inter','Segoe UI',sans-serif;
        }
        .cg-score-vs {
            font-size:1.1rem!important; font-weight:900!important;
            color:var(--cg-text-dim)!important; opacity:.3;
            letter-spacing:3px;
        }
        .cg-info-bar {
            display:flex; justify-content:space-between; align-items:center;
            margin-bottom:.8rem; gap:8px; flex-wrap:wrap;
        }
        .cg-info-chip {
            padding:6px 16px; border-radius:24px; font-size:0.8rem;
            font-weight:700; display:inline-flex; align-items:center; gap:6px;
            backdrop-filter:blur(8px);
            transition:all .2s ease;
        }
        .cg-info-chip:hover { transform:translateY(-1px); }
        .cg-discard-chip {
            background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.2); color:#a78bfa;
        }
        .cg-preview-chip {
            background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.2); color:#34d399;
        }

        /* ───────────────────────────────────────
           PREMIUM GAME CARD
           ─────────────────────────────────────── */
        .gc-card {
            position:relative;
            border-radius:18px;
            overflow:hidden;
            cursor:pointer;
            transition:transform .25s cubic-bezier(.4,0,.2,1),
                        box-shadow .25s ease,
                        filter .25s ease;
            min-height:250px;
            animation:cg-card-deal 0.5s cubic-bezier(.34,1.56,.64,1) both;
        }
        .gc-card:nth-child(1) { animation-delay:0.05s; }
        .gc-card:nth-child(2) { animation-delay:0.1s; }
        .gc-card:nth-child(3) { animation-delay:0.15s; }
        .gc-card:nth-child(4) { animation-delay:0.2s; }
        .gc-card:nth-child(5) { animation-delay:0.25s; }
        .gc-card:hover {
            transform:translateY(-8px) scale(1.03);
            z-index:10;
            filter:brightness(1.05);
        }

        /* Holographic shimmer overlay */
        .gc-card::after {
            content:'';
            position:absolute; inset:0;
            background:linear-gradient(
                105deg,
                transparent 25%,
                rgba(255,255,255,0.04) 35%,
                rgba(255,255,255,0.12) 45%,
                rgba(255,255,255,0.04) 55%,
                transparent 65%
            );
            background-size:200% 100%;
            pointer-events:none;
            opacity:0;
            transition:opacity .3s ease;
        }
        .gc-card:hover::after {
            opacity:1;
            animation:cg-shimmer-move 1.5s ease infinite;
        }

        /* Inner foil border */
        .gc-card-inner {
            position:relative;
            border-radius:16px;
            padding:2px;
            height:100%;
        }
        .gc-card-body {
            position:relative;
            background:linear-gradient(170deg,#14182d 0%,#0c0f1d 100%);
            border-radius:14px;
            padding:16px 14px 14px;
            height:100%;
            overflow:hidden;
        }

        /* Jersey number watermark */
        .gc-jersey-watermark {
            position:absolute;
            top:-10px; right:-4px;
            font-size:6rem;
            font-weight:950;
            opacity:0.05;
            line-height:1;
            pointer-events:none;
            font-family:'Inter','Segoe UI',sans-serif;
            user-select:none;
        }

        /* Team colour stripe at top */
        .gc-team-stripe {
            position:absolute; top:0; left:0; right:0;
            height:4px;
            box-shadow:0 2px 10px rgba(0,0,0,0.3);
        }

        /* Avatar */
        .gc-avatar-ring {
            width:66px; height:66px;
            border-radius:50%;
            padding:2.5px;
            display:inline-flex;
            align-items:center; justify-content:center;
            flex-shrink:0;
            box-shadow:0 4px 14px rgba(0,0,0,0.3);
            transition:transform .3s ease;
        }
        .gc-card:hover .gc-avatar-ring { transform:scale(1.05); }
        .gc-avatar {
            width:58px; height:58px;
            border-radius:50%;
            object-fit:cover;
            background:#0a0e1a;
            border:2px solid rgba(255,255,255,0.06);
        }

        /* Header row */
        .gc-header {
            display:flex; align-items:center; gap:11px;
            margin-bottom:12px; position:relative; z-index:1;
        }
        .gc-name {
            font-weight:800; font-size:0.9rem;
            color:#f1f5f9; line-height:1.2;
            letter-spacing:-0.3px;
        }
        .gc-team-name {
            font-size:0.7rem; font-weight:600;
            margin-top:2px; opacity:.85;
            letter-spacing:0.2px;
        }

        /* Attribute badges */
        .gc-attrs {
            display:flex; flex-wrap:wrap; gap:5px;
            position:relative; z-index:1;
        }
        .gc-attr {
            padding:4px 9px; border-radius:8px;
            font-size:0.68rem; font-weight:700;
            background:rgba(255,255,255,0.04);
            border:1px solid rgba(255,255,255,0.07);
            color:var(--cg-text-dim);
            letter-spacing:0.3px;
            transition:all .2s ease;
        }
        .gc-card:hover .gc-attr { border-color:rgba(255,255,255,0.12); }
        .gc-attr.pos {
            background:rgba(99,102,241,0.15);
            border-color:rgba(99,102,241,0.3);
            color:#a5b4fc;
        }
        .gc-attr.country {
            background:rgba(59,130,246,0.12);
            border-color:rgba(59,130,246,0.25);
            color:#93c5fd;
        }
        .gc-attr.draft {
            background:rgba(249,115,22,0.12);
            border-color:rgba(249,115,22,0.25);
            color:#fdba74;
        }
        .gc-attr.former {
            background:rgba(245,158,11,0.08);
            border-color:rgba(245,158,11,0.18);
            color:#fcd34d;
            font-size:0.63rem;
        }

        /* Contribution badge */
        .gc-contrib {
            position:absolute; bottom:12px; right:12px;
            font-size:0.75rem; font-weight:800;
            padding:4px 10px; border-radius:10px;
            z-index:1;
            backdrop-filter:blur(8px);
            transition:all .2s ease;
        }
        .gc-contrib.high {
            background:rgba(16,185,129,0.2);
            color:#34d399;
            border:1px solid rgba(16,185,129,0.35);
            animation:cg-badge-pulse 2s ease infinite;
        }
        .gc-contrib.mid {
            background:rgba(251,191,36,0.15);
            color:#fbbf24;
            border:1px solid rgba(251,191,36,0.25);
        }
        .gc-contrib.low {
            background:rgba(239,68,68,0.12);
            color:#f87171;
            border:1px solid rgba(239,68,68,0.2);
        }

        /* Select indicator */
        .gc-select-ind {
            position:absolute; top:10px; right:10px;
            width:26px; height:26px; border-radius:50%;
            border:2px solid rgba(255,255,255,0.12);
            display:flex; align-items:center; justify-content:center;
            font-size:11px; background:rgba(0,0,0,0.5);
            z-index:3; transition:all .22s cubic-bezier(.4,0,.2,1);
            backdrop-filter:blur(6px);
        }
        .gc-select-ind.on {
            background:var(--cg-red);
            border-color:var(--cg-red);
            color:#fff;
            box-shadow:0 0 16px rgba(239,68,68,0.4);
            transform:scale(1.1);
        }

        /* Selected card glow */
        .gc-card.sel {
            box-shadow:0 0 0 2px var(--cg-red),
                        0 0 30px rgba(239,68,68,0.2)!important;
        }
        .gc-card.sel .gc-team-stripe {
            background:linear-gradient(90deg,var(--cg-red),var(--cg-orange))!important;
            height:5px!important;
        }
        .gc-card.sel .gc-select-ind { animation:cg-badge-pulse 1s ease infinite; }

        /* ───── NETWORK GRID ───── */
        .cg-network-grid {
            display:grid;
            grid-template-columns:repeat(5,1fr);
            gap:14px 12px;
            margin-bottom:6px;
        }
        .cg-network-grid.staggered {
            margin-left:5%;
            margin-right:-2%;
        }
        .cg-network-grid .gc-card-wrapper {
            position:relative;
        }

        /* ───── BOT CARDS (Animated Back) ───── */
        .gc-bot-card {
            border-radius:16px;
            min-height:75px;
            display:flex; align-items:center; justify-content:center;
            position:relative; overflow:hidden;
            transition:transform .2s ease;
        }
        .gc-bot-card:hover { transform:scale(1.04) translateY(-3px); }
        .gc-bot-card-inner {
            position:absolute; inset:2.5px;
            border-radius:13px;
            background:linear-gradient(170deg,#151930,#0c0f1d);
            display:flex; align-items:center; justify-content:center;
            overflow:hidden;
        }
        /* Animated pattern on bot card back */
        .gc-bot-card-inner::before {
            content:'';
            position:absolute; inset:-30px;
            background:repeating-conic-gradient(
                rgba(99,102,241,0.04) 0deg 10deg,
                transparent 10deg 20deg
            );
            animation:cg-bot-pattern 20s linear infinite;
        }
        .gc-bot-card-inner::after {
            content:'';
            position:absolute;
            width:40px; height:40px;
            border-radius:50%;
            border:2px solid rgba(99,102,241,0.12);
            border-top-color:rgba(139,92,246,0.25);
            animation:cg-ring-spin 3s linear infinite;
        }
        .gc-bot-card-icon {
            font-size:1.3rem; opacity:.25;
            position:relative; z-index:1;
            filter:grayscale(0.5);
        }

        /* ───── SECTION HEADERS ───── */
        .cg-section-header {
            display:flex; align-items:center; gap:10px;
            margin:1.2rem 0 0.7rem 0;
            padding-bottom:8px;
            border-bottom:1px solid rgba(255,255,255,0.04);
        }
        .cg-section-title {
            font-size:1rem!important; font-weight:700!important;
            color:var(--cg-text)!important;
            letter-spacing:0.2px;
        }
        .cg-section-count {
            padding:3px 12px; border-radius:12px;
            font-size:0.73rem; font-weight:700;
            background:rgba(255,255,255,0.04);
            color:var(--cg-text-dim);
            border:1px solid rgba(255,255,255,0.04);
        }

        /* ───── CONNECTION LINES ───── */
        .cg-conn-item {
            display:flex; align-items:center; gap:10px;
            padding:8px 14px; border-radius:12px;
            margin:4px 0; font-size:0.83rem;
            transition:all .2s cubic-bezier(.4,0,.2,1);
            border:1px solid transparent;
        }
        .cg-conn-item:hover {
            transform:translateX(6px);
            border-color:rgba(255,255,255,0.04);
            box-shadow:0 4px 12px rgba(0,0,0,0.15);
        }
        .cg-conn-dot {
            width:10px; height:10px; border-radius:50%; flex-shrink:0;
            box-shadow:0 0 8px currentColor;
        }
        .cg-conn-players {
            font-weight:700; color:var(--cg-text)!important; font-size:0.82rem;
        }
        .cg-conn-detail {
            color:var(--cg-text-dim)!important; font-size:0.75rem;
        }
        .cg-conn-points {
            margin-left:auto; font-weight:800; font-size:0.82rem;
            padding:3px 10px; border-radius:8px; min-width:32px; text-align:center;
        }

        /* ───── RESULT BANNER ───── */
        .cg-result-banner {
            text-align:center; padding:2rem; border-radius:22px;
            margin-bottom:1.4rem; position:relative; overflow:hidden;
            box-shadow:0 12px 45px rgba(0,0,0,0.35);
        }
        .cg-result-banner::before {
            content:'';
            position:absolute; inset:0;
            opacity:0.5;
            pointer-events:none;
        }
        .cg-result-banner.win {
            background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(5,150,105,0.06));
            border:1px solid rgba(16,185,129,0.25);
        }
        .cg-result-banner.win::before {
            background:radial-gradient(circle at 50% 0%, rgba(16,185,129,0.12) 0%, transparent 60%);
        }
        .cg-result-banner.lose {
            background:linear-gradient(135deg,rgba(239,68,68,0.15),rgba(185,28,28,0.06));
            border:1px solid rgba(239,68,68,0.25);
        }
        .cg-result-banner.lose::before {
            background:radial-gradient(circle at 50% 0%, rgba(239,68,68,0.1) 0%, transparent 60%);
        }
        .cg-result-banner.tie {
            background:linear-gradient(135deg,rgba(139,92,246,0.15),rgba(109,40,217,0.06));
            border:1px solid rgba(139,92,246,0.25);
        }
        .cg-result-banner.tie::before {
            background:radial-gradient(circle at 50% 0%, rgba(139,92,246,0.1) 0%, transparent 60%);
        }
        .cg-result-title {
            font-size:2.5rem!important; font-weight:950!important;
            margin-bottom:0.3rem!important; position:relative; z-index:1;
            letter-spacing:-1px;
        }
        .cg-result-title.win  { color:var(--cg-green)!important; }
        .cg-result-title.lose { color:var(--cg-red)!important; }
        .cg-result-title.tie  { color:var(--cg-purple)!important; }
        .cg-result-subtitle {
            color:var(--cg-text-dim); font-size:0.92rem;
            position:relative; z-index:1;
        }
        .cg-result-scores {
            display:flex; justify-content:center; align-items:center;
            gap:1.8rem; margin-top:0.8rem;
            position:relative; z-index:1;
        }
        .cg-result-score-box {
            padding:0.7rem 2rem; border-radius:16px; text-align:center;
            backdrop-filter:blur(8px);
            transition:transform .2s ease;
        }
        .cg-result-score-box:hover { transform:scale(1.05); }
        .cg-result-score-box.player {
            background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.2);
        }
        .cg-result-score-box.bot {
            background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.2);
        }
        .cg-result-score-number {
            font-size:2rem; font-weight:950; line-height:1;
        }
        .cg-result-score-label {
            font-size:.7rem; color:var(--cg-text-dim); font-weight:700;
            text-transform:uppercase; letter-spacing:1.5px; margin-bottom:2px;
        }

        /* ─── Win Confetti ─── */
        .cg-confetti-container {
            position:fixed; inset:0; pointer-events:none; z-index:9999; overflow:hidden;
        }
        .cg-confetti-piece {
            position:absolute;
            width:10px; height:10px;
            top:-20px;
            animation:cg-confetti-fall linear forwards;
        }

        /* ─── Score Breakdown Card ─── */
        .cg-breakdown-card {
            text-align:center; padding:14px 8px;
            border-radius:16px;
            transition:all .2s ease;
            position:relative; overflow:hidden;
        }
        .cg-breakdown-card:hover {
            transform:translateY(-3px);
            box-shadow:0 6px 20px rgba(0,0,0,0.2);
        }
        .cg-breakdown-icon { font-size:1.5rem; margin-bottom:4px; }
        .cg-breakdown-label {
            font-size:.7rem; color:var(--cg-text-dim); font-weight:700;
            margin-top:4px; letter-spacing:0.3px;
        }
        .cg-breakdown-scores { margin-top:8px; }
        .cg-breakdown-vs {
            color:var(--cg-text-dim); font-size:.75rem; margin:0 4px;
        }
        .cg-breakdown-links {
            font-size:.65rem; color:var(--cg-text-dim); margin-top:3px;
        }

        /* ───── MOBILE ───── */
        @media (max-width:768px) {
            .cg-lobby-title { font-size:2.4rem!important; letter-spacing:-1px; }
            .cg-network-grid { grid-template-columns:repeat(2,1fr); gap:10px; }
            .cg-network-grid.staggered { margin-left:12%; margin-right:-2%; }
            .gc-card { min-height:215px; }
            .gc-avatar-ring { width:54px; height:54px; }
            .gc-avatar { width:48px; height:48px; }
            .gc-name { font-size:0.82rem; }
            .gc-jersey-watermark { font-size:4.5rem; }
            .cg-scoreboard { padding:.8rem 1rem; border-radius:16px; }
            .cg-score-value { font-size:1.8rem!important; }
            .cg-result-title { font-size:1.8rem!important; }
            .gc-bot-card { min-height:58px; }
            .cg-result-scores { gap:1rem; }
            .cg-result-score-box { padding:0.5rem 1.2rem; }
            .cg-result-score-number { font-size:1.5rem; }
        }
    </style>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  CARD HTML BUILDER
# ════════════════════════════════════════════════════════════════════
def _build_card_html(card, index, is_selected=False, show_contrib=False, contrib=0):
    """Build premium game-card HTML."""
    team = card["current_team"]
    c1 = _team_clr(team, 0)
    c2 = _team_clr(team, 1)

    sel_cls = "sel" if is_selected else ""
    ind_cls = "on" if is_selected else ""
    ind_icon = "✕" if is_selected else ""

    # Former teams (max 3)
    former_html = ""
    for ft in card.get("former_teams", [])[:3]:
        ft_short = ft.replace("Los Angeles ", "LA ").replace("Golden State ", "GS ").replace("Oklahoma City ", "OKC ").replace("New Orleans ", "NO ").replace("San Antonio ", "SA ").replace("Portland Trail ", "POR ").replace("Minnesota ", "MIN ")
        former_html += f'<span class="gc-attr former">{ft_short}</span>'

    # Contrib badge with colour tier
    contrib_html = ""
    if show_contrib:
        if contrib >= 8:
            tier = "high"
        elif contrib >= 3:
            tier = "mid"
        else:
            tier = "low"
        contrib_html = f'<div class="gc-contrib {tier}">+{contrib}</div>'

    # Determine team name short
    team_short = team  # could shorten for mobile

    return f"""
    <div class="gc-card {sel_cls}" id="gc-{index}">
        <div class="gc-card-inner"
             style="background:linear-gradient(135deg,{c1}40 0%,{c2}22 50%,{c1}12 100%);">
            <div class="gc-card-body">
                <div class="gc-team-stripe"
                     style="background:linear-gradient(90deg,{c1},{c2});"></div>
                <div class="gc-jersey-watermark" style="color:{c2};">
                    {card['jersey']}
                </div>
                <div class="gc-select-ind {ind_cls}">{ind_icon}</div>
                <div class="gc-header">
                    <div class="gc-avatar-ring"
                         style="background:linear-gradient(135deg,{c1},{c2});">
                        <img class="gc-avatar"
                             src="{card['headshot_url']}"
                             onerror="this.src='https://cdn.nba.com/headshots/nba/latest/1040x760/logoman.png'"
                             alt="{card['name']}">
                    </div>
                    <div>
                        <div class="gc-name">{card['name']}</div>
                        <div class="gc-team-name" style="color:{c2};">{team_short}</div>
                    </div>
                </div>
                <div class="gc-attrs">
                    <span class="gc-attr pos">{card['position']}</span>
                    <span class="gc-attr country">{card['country']}</span>
                    <span class="gc-attr draft">'{str(card['draft_year'])[2:]}</span>
                    {former_html}
                </div>
                {contrib_html}
            </div>
        </div>
    </div>
    """


def _build_bot_card_html(index):
    c1 = "#6366f1"
    c2 = "#8b5cf6"
    icons = ["🏀", "🃏", "⭐", "🏀", "🃏", "⭐", "🏀", "🃏", "⭐", "🏀"]
    icon = icons[index % len(icons)]
    return f"""
    <div class="gc-bot-card"
         style="background:linear-gradient(135deg,{c1}25,{c2}12);
                border:1px solid {c1}20;">
        <div class="gc-bot-card-inner">
            <div class="gc-bot-card-icon">{icon}</div>
        </div>
    </div>
    """


# ════════════════════════════════════════════════════════════════════
#  LOBBY SCREEN
# ════════════════════════════════════════════════════════════════════
def _render_lobby():
    st.markdown("""
    <div class="cg-lobby-container">
        <div class="cg-lobby-title">Card Connections</div>
        <div class="cg-lobby-subtitle">Find the strongest links between NBA players</div>
    </div>
    """, unsafe_allow_html=True)

    # Connection types
    st.markdown('<div class="cg-rules-card">', unsafe_allow_html=True)
    st.markdown('<div class="cg-rules-title">Connection Types & Points</div>',
                unsafe_allow_html=True)
    for key, ct in CONNECTION_TYPES.items():
        st.markdown(f"""
        <div class="cg-connection-row" style="background:{ct['bg_color']}">
            <div class="cg-conn-badge" style="background:{ct['color']}">{ct['points']}pt</div>
            <div>
                <div class="cg-conn-label">{ct['icon']} {ct['label']}</div>
                <div class="cg-conn-desc">{ct['description']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # How to play
    st.markdown("""
    <div class="cg-rules-card" style="margin-top:1rem;">
        <div class="cg-rules-title">How to Play</div>
        <div style="color:#8892b0;font-size:0.88rem;line-height:1.9;">
            <strong style="color:#e2e8f0;">1.</strong> Each player gets <strong style="color:#e2e8f0;">10 cards</strong> from the NBA deck<br>
            <strong style="color:#e2e8f0;">2.</strong> You have <strong style="color:#e2e8f0;">3 chances</strong> to discard weak cards and draw new ones<br>
            <strong style="color:#e2e8f0;">3.</strong> Every pair of cards with a connection scores points<br>
            <strong style="color:#e2e8f0;">4.</strong> The player with the <strong style="color:#fbbf24;">highest total score</strong> wins!
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        difficulty = st.select_slider(
            "Bot Difficulty",
            options=["easy", "normal", "hard"],
            value="normal",
            format_func=lambda x: {"easy": "Easy", "normal": "Normal", "hard": "Hard"}[x],
            key="cg_difficulty"
        )
        if st.button("Play vs Bot", width='stretch', type="primary",
                      key="cg_start_btn"):
            game = GameState(bot_difficulty=difficulty)
            game.start_game()
            st.session_state.card_game = game.to_dict()
            st.session_state.cg_selected_cards = set()
            st.rerun()


# ════════════════════════════════════════════════════════════════════
#  GAME SCREEN
# ════════════════════════════════════════════════════════════════════
def _render_game_screen(game):
    preview_score, preview_connections = game.get_current_player_score_preview()

    # Scoreboard
    st.markdown(f"""
    <div class="cg-scoreboard">
        <div class="cg-score-side">
            <div class="cg-score-label">You</div>
            <div class="cg-score-value" style="color:var(--cg-green)!important;">{preview_score}</div>
        </div>
        <div class="cg-score-vs">VS</div>
        <div class="cg-score-side">
            <div class="cg-score-label">Bot</div>
            <div class="cg-score-value" style="color:var(--cg-text-dim)!important;">?</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Info bar
    selected = st.session_state.get("cg_selected_cards", set())
    discard_pct = game.player_discards_left / GameState.MAX_DISCARDS * 100
    st.markdown(f"""
    <div class="cg-info-bar">
        <div class="cg-info-chip cg-discard-chip">
            Discards Left: {game.player_discards_left}/{GameState.MAX_DISCARDS}
        </div>
        <div class="cg-info-chip cg-preview-chip">
            Score: {preview_score} pts &middot; {len(preview_connections)} connections
        </div>
    </div>
    """, unsafe_allow_html=True)

    if game.message:
        st.info(game.message)

    # ── Bot hand (face-down, compact) ──
    st.markdown("""
    <div class="cg-section-header">
        <div class="cg-section-title">Opponent's Hand</div>
        <div class="cg-section-count">10 cards</div>
    </div>
    """, unsafe_allow_html=True)

    bot_html = '<div class="cg-network-grid">'
    for i in range(min(10, len(game.bot_hand))):
        bot_html += f'<div class="gc-card-wrapper">{_build_bot_card_html(i)}</div>'
    bot_html += '</div>'
    st.markdown(bot_html, unsafe_allow_html=True)

    # ── Player hand (staggered network grid) ──
    st.markdown(f"""
    <div class="cg-section-header">
        <div class="cg-section-title">Your Hand</div>
        <div class="cg-section-count">{len(game.player_hand)} cards</div>
    </div>
    """, unsafe_allow_html=True)

    if selected:
        st.caption(f"{len(selected)} card(s) selected for discard")

    hand = game.player_hand

    # Row 1 (first 5 cards)
    row1 = hand[:5]
    row1_html = '<div class="cg-network-grid">'
    for i, card in enumerate(row1):
        is_sel = i in selected
        contrib = ConnectionChecker.calculate_card_contribution(hand, i)
        row1_html += f'<div class="gc-card-wrapper">{_build_card_html(card, i, is_sel, True, contrib)}</div>'
    row1_html += '</div>'
    st.markdown(row1_html, unsafe_allow_html=True)

    # Row 1 checkboxes
    cols1 = st.columns(len(row1))
    for i in range(len(row1)):
        with cols1[i]:
            if st.checkbox("Sel", key=f"cg_sel_{i}", value=(i in selected),
                           label_visibility="collapsed"):
                selected.add(i)
            else:
                selected.discard(i)

    # Row 2 (cards 5–9, staggered)
    row2 = hand[5:10]
    if row2:
        row2_html = '<div class="cg-network-grid staggered">'
        for j, card in enumerate(row2):
            card_idx = 5 + j
            is_sel = card_idx in selected
            contrib = ConnectionChecker.calculate_card_contribution(hand, card_idx)
            row2_html += f'<div class="gc-card-wrapper">{_build_card_html(card, card_idx, is_sel, True, contrib)}</div>'
        row2_html += '</div>'
        st.markdown(row2_html, unsafe_allow_html=True)

        # Row 2 checkboxes (offset to match stagger)
        c_spacer, *cols2 = st.columns([0.5] + [1] * len(row2))
        for j in range(len(row2)):
            card_idx = 5 + j
            with cols2[j]:
                if st.checkbox("Sel", key=f"cg_sel_{card_idx}",
                               value=(card_idx in selected),
                               label_visibility="collapsed"):
                    selected.add(card_idx)
                else:
                    selected.discard(card_idx)

    st.session_state.cg_selected_cards = selected

    # ── Action buttons ──
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        dis = (game.player_discards_left <= 0) or (len(selected) == 0)
        if st.button(f"Discard & Draw ({len(selected)})", disabled=dis,
                     width='stretch', key="cg_discard_btn", type="secondary"):
            if selected:
                game.player_discard(list(selected))
                st.session_state.card_game = game.to_dict()
                st.session_state.cg_selected_cards = set()
                st.rerun()
    with col2:
        if st.button("Lock In Hand", width='stretch', key="cg_lock_btn",
                      type="primary"):
            game.player_lock_in()
            st.session_state.card_game = game.to_dict()
            st.session_state.cg_selected_cards = set()
            st.rerun()
    with col3:
        if st.button("Back to Lobby", width='stretch', key="cg_back_game",
                      type="secondary"):
            st.session_state.pop("card_game", None)
            st.session_state.pop("cg_selected_cards", None)
            st.rerun()

    # ── Connections preview ──
    if preview_connections:
        with st.expander(
            f"Your Connections Preview ({len(preview_connections)} pairs)",
            expanded=False
        ):
            _render_connections_list(preview_connections, "preview")


# ════════════════════════════════════════════════════════════════════
#  CONNECTION LIST
# ════════════════════════════════════════════════════════════════════
def _render_connections_list(connections, prefix=""):
    for pair in connections:
        for conn in pair["connections"]:
            bg = conn["bg_color"]
            color = conn["color"]
            st.markdown(f"""
            <div class="cg-conn-item" style="background:{bg}">
                <div class="cg-conn-dot" style="background:{color};"></div>
                <div>
                    <div class="cg-conn-players">{pair['card_a']['name']} &harr; {pair['card_b']['name']}</div>
                    <div class="cg-conn-detail">{conn['icon']} {conn['label']}: {conn['detail']}</div>
                </div>
                <div class="cg-conn-points" style="background:{bg};color:{color};">+{conn['points']}</div>
            </div>
            """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  CONFETTI EFFECT (WIN ONLY)
# ════════════════════════════════════════════════════════════════════
def _render_confetti():
    """Render CSS-only confetti animation for victory screen."""
    import random
    colors = ["#10b981", "#fbbf24", "#3b82f6", "#8b5cf6", "#ef4444", "#f97316", "#ec4899"]
    pieces = ""
    for i in range(40):
        color = random.choice(colors)
        left = random.randint(0, 100)
        delay = round(random.uniform(0, 3), 2)
        duration = round(random.uniform(2.5, 5), 2)
        size = random.randint(6, 14)
        rotation = random.randint(0, 360)
        shape = "border-radius:50%;" if random.random() > 0.5 else f"border-radius:2px; transform:rotate({rotation}deg);"
        pieces += f'<div class="cg-confetti-piece" style="left:{left}%;background:{color};width:{size}px;height:{size}px;{shape}animation-delay:{delay}s;animation-duration:{duration}s;"></div>'

    st.markdown(f'<div class="cg-confetti-container">{pieces}</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  REVEAL / RESULTS SCREEN
# ════════════════════════════════════════════════════════════════════
def _render_reveal_screen(game):
    winner = game.get_winner()

    if winner == "player":
        bc, tc = "win", "win"
        title, sub = "Victory!", "Your connections were stronger!"
        _render_confetti()
    elif winner == "bot":
        bc, tc = "lose", "lose"
        title, sub = "Defeat", "The bot had better connections."
    else:
        bc, tc = "tie", "tie"
        title, sub = "It's a Tie!", "Equally matched!"

    st.markdown(f"""
    <div class="cg-result-banner {bc}">
        <div class="cg-result-title {tc}">{title}</div>
        <div class="cg-result-subtitle">{sub}</div>
        <div class="cg-result-scores">
            <div class="cg-result-score-box player">
                <div class="cg-result-score-label">YOU</div>
                <div class="cg-result-score-number" style="color:var(--cg-green);">{game.player_score}</div>
            </div>
            <div style="font-size:1.1rem;color:var(--cg-text-dim);font-weight:900;opacity:.3;">vs</div>
            <div class="cg-result-score-box bot">
                <div class="cg-result-score-label">BOT</div>
                <div class="cg-result-score-number" style="color:var(--cg-red);">{game.bot_score}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    _render_score_breakdown(game)

    tab1, tab2 = st.tabs(["Your Hand & Connections", "Bot's Hand & Connections"])
    with tab1:
        _render_reveal_hand(game.player_hand, game.player_connections, "player")
    with tab2:
        _render_reveal_hand(game.bot_hand, game.bot_connections, "bot")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Play Again", width='stretch', type="primary",
                      key="cg_play_again"):
            new = GameState(bot_difficulty=game.bot_difficulty)
            new.start_game()
            st.session_state.card_game = new.to_dict()
            st.session_state.cg_selected_cards = set()
            st.rerun()
    with col2:
        if st.button("Back to Lobby", width='stretch', key="cg_back_reveal"):
            st.session_state.pop("card_game", None)
            st.session_state.pop("cg_selected_cards", None)
            st.rerun()


def _render_score_breakdown(game):
    def calc_bd(conns):
        bd = {k: {"count": 0, "points": 0} for k in CONNECTION_TYPES}
        for pair in conns:
            for c in pair["connections"]:
                bd[c["type"]]["count"] += 1
                bd[c["type"]]["points"] += c["points"]
        return bd

    pbd = calc_bd(game.player_connections)
    bbd = calc_bd(game.bot_connections)

    st.markdown("""
    <div class="cg-section-header">
        <div class="cg-section-title">Score Breakdown</div>
    </div>
    """, unsafe_allow_html=True)

    cols = st.columns(len(CONNECTION_TYPES))
    for i, (key, ct) in enumerate(CONNECTION_TYPES.items()):
        with cols[i]:
            pp, bp = pbd[key]["points"], bbd[key]["points"]
            pc, bcc = pbd[key]["count"], bbd[key]["count"]
            # Determine who leads this category
            p_color = "var(--cg-green)" if pp >= bp else "var(--cg-text-dim)"
            b_color = "var(--cg-red)" if bp >= pp else "var(--cg-text-dim)"
            st.markdown(f"""
            <div class="cg-breakdown-card"
                 style="background:{ct['bg_color']};
                        border:1px solid {ct['color']}22;">
                <div class="cg-breakdown-icon">{ct['icon']}</div>
                <div class="cg-breakdown-label">{ct['label']}</div>
                <div class="cg-breakdown-scores">
                    <span style="color:{p_color};font-weight:800;font-size:1.1rem;">{pp}</span>
                    <span class="cg-breakdown-vs">vs</span>
                    <span style="color:{b_color};font-weight:800;font-size:1.1rem;">{bp}</span>
                </div>
                <div class="cg-breakdown-links">({pc} vs {bcc} links)</div>
            </div>
            """, unsafe_allow_html=True)


def _render_reveal_hand(hand, connections, side):
    label = "Your" if side == "player" else "Bot's"
    st.markdown(f"""
    <div class="cg-section-header">
        <div class="cg-section-title">{label} Cards</div>
        <div class="cg-section-count">{len(hand)} cards</div>
    </div>
    """, unsafe_allow_html=True)

    # Row 1
    row1 = hand[:5]
    row1_html = '<div class="cg-network-grid">'
    for i, card in enumerate(row1):
        contrib = ConnectionChecker.calculate_card_contribution(hand, i)
        row1_html += f'<div class="gc-card-wrapper">{_build_card_html(card, f"{side}_{i}", show_contrib=True, contrib=contrib)}</div>'
    row1_html += '</div>'
    st.markdown(row1_html, unsafe_allow_html=True)

    # Row 2 (staggered)
    row2 = hand[5:10]
    if row2:
        row2_html = '<div class="cg-network-grid staggered">'
        for j, card in enumerate(row2):
            idx = 5 + j
            contrib = ConnectionChecker.calculate_card_contribution(hand, idx)
            row2_html += f'<div class="gc-card-wrapper">{_build_card_html(card, f"{side}_{idx}", show_contrib=True, contrib=contrib)}</div>'
        row2_html += '</div>'
        st.markdown(row2_html, unsafe_allow_html=True)

    if connections:
        total = sum(c["points"] for p in connections for c in p["connections"])
        link_count = sum(len(p["connections"]) for p in connections)
        st.markdown(f"""
        <div class="cg-section-header">
            <div class="cg-section-title">Connections</div>
            <div class="cg-section-count">{link_count} links = {total} pts</div>
        </div>
        """, unsafe_allow_html=True)
        _render_connections_list(connections, f"{side}_reveal")
    else:
        st.info("No connections found.")


# ════════════════════════════════════════════════════════════════════
#  MAIN ENTRY
# ════════════════════════════════════════════════════════════════════
def render_card_game_page():
    _inject_card_game_css()

    game_data = st.session_state.get("card_game", None)
    if game_data is None:
        _render_lobby()
        return

    game = GameState.from_dict(game_data)

    if game.phase == GameState.PHASE_PLAYER_TURN:
        _render_game_screen(game)
    elif game.phase in [GameState.PHASE_REVEAL, GameState.PHASE_FINISHED]:
        _render_reveal_screen(game)
    else:
        _render_lobby()
