"""
Hizli testler: GitHub Actions'ta her push'ta calisir, Railway ancak bunlar
gecerse yayina alir. Veritabani ve dis servis gerektirmezler (CI'da sir
yok); sayfalarin acildigini, guvenlik kontrollerini ve hesap motorlarini
dogrularlar.
"""
import os

os.environ.setdefault("SKIP_WARMUP", "1")

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import config
from web.app import app

client = TestClient(app)


# ==================== SAYFALAR ====================

@pytest.mark.parametrize("path", ["/healthz", "/login", "/register", "/forgot-password",
                                  "/reset-password?token=nope", "/robots.txt"])
def test_static_pages_open(path):
    assert client.get(path).status_code == 200


def test_unknown_page_is_404():
    assert client.get("/no-such-page").status_code == 404


def test_protected_pages_redirect_to_login():
    for path in ("/watchlist", "/account"):
        res = client.get(path, follow_redirects=False)
        assert res.status_code == 303
        assert res.headers["location"].startswith("/login")


# ==================== GUVENLIK ====================

def test_cross_site_post_is_blocked():
    res = client.post("/logout", headers={"Origin": "https://evil.example"})
    assert res.status_code == 403


def test_same_site_post_is_allowed():
    res = client.post("/logout", headers={"Origin": "http://testserver"}, follow_redirects=False)
    assert res.status_code == 303


def test_login_next_cannot_leave_the_site():
    from web.routes.auth import _safe_next
    assert _safe_next("https://evil.example/x") == "/"
    assert _safe_next("//evil.example") == "/"
    assert _safe_next("/watchlist") == "/watchlist"


def test_env_values_are_trimmed(monkeypatch):
    monkeypatch.setenv("HL_TEST_VALUE", "abc\r\n")
    assert config.get("HL_TEST_VALUE") == "abc"


# ==================== HESAP MOTORLARI ====================

def _board(n=60):
    positions = ["PG", "SG", "SF", "PF", "C"]
    rows = []
    for i in range(n):
        pos = positions[i % 5]
        rows.append({"PLAYER": f"Player {i}", "ESPN_ID": 1000 + i, "TEAM": "TST", "POS": pos,
                     "POSITIONS": [pos], "ADP": i + 1, "RANK": i + 1, "AUCTION": max(1, 60 - i),
                     "OWNED": 90.0, "INJURY": "ACTIVE", "FPTS": 50 - i * 0.5, "PTS": 20.0,
                     "REB": 5.0, "AST": 4.0, "STL": 1.0, "BLK": 0.5, "GP": 70, "ROOKIE": False})
    return pd.DataFrame(rows)


def test_snake_draft_with_ai_runs_to_completion():
    from services.draft_engine import (available_players, create_draft, is_user_turn,
                                       make_pick, run_ai_until_user, serialize, deserialize)
    board = _board()
    state = create_draft(board, team_count=4, rounds=5, user_slot=2, fmt="snake",
                         opponent_mode="ai", seed=7)
    run_ai_until_user(state)
    guard = 0
    while not state["complete"] and guard < 50:
        guard += 1
        assert is_user_turn(state)
        ok, _ = make_pick(state, available_players(state)[0]["id"])
        assert ok
        run_ai_until_user(state)
    assert state["complete"]
    assert len(state["log"]) == 20
    restored = deserialize(serialize(state), board)
    assert len(restored["drafted_ids"]) == 20


def test_ai_opponent_mode_is_not_manual():
    """Eski hata: 'AI opponents' secimi her draft'i manuel moda dusuruyordu."""
    from services.draft_engine import create_draft, is_user_turn, run_ai_until_user
    state = create_draft(_board(), team_count=4, rounds=3, user_slot=4, fmt="snake",
                         opponent_mode="ai", seed=1)
    made = run_ai_until_user(state)
    assert len(made) == 3 and is_user_turn(state)


def test_survival_odds_fall_as_the_pick_moves_later():
    from services.strategy_engine import survival
    odds = [float(survival([20.0], pick)[0]) for pick in (5, 15, 20, 25, 40)]
    assert odds == sorted(odds, reverse=True)
    assert odds[0] > 0.95 and odds[-1] < 0.05


def test_vegas_lean_removes_the_margin():
    from services.win_totals import implied_over
    assert abs(implied_over(-110, -110) - 0.5) < 1e-9
    assert implied_over(-130, 110) > 0.5


def test_fantasy_score_and_insight():
    from web import stats
    weights, locked = stats.weights_for("punt-ft", pro=False)
    assert weights["FTM"] == 0 and weights["FTA"] == 0 and not locked
    _, locked = stats.weights_for("punt-pts", pro=False)
    assert locked
    row = {"games": 1, "score": 40.0, "min": 36, "pts": 30, "reb": 10, "ast": 8, "stl": 2,
           "blk": 1, "to": 3, "fgm": 11, "fga": 20, "ftm": 6, "fta": 7, "tpm": 2, "tpa": 5, "pm": 12}
    info = stats.player_insight(row)
    assert info["outlook"]["title"] and info["notes"]


# ==================== GIZEMLI OYUNCU / KAYNAK ====================

def test_old_card_game_redirects_to_daily():
    res = client.get("/card-game", follow_redirects=False)
    assert res.status_code == 301 and res.headers["location"] == "/daily"


def test_daily_compare_marks_hits_near_and_direction():
    from services.daily_player import compare
    answer = {"id": "1", "team": "PHX", "pos": "G", "height": 77, "age": 29, "jersey": 1}
    guess = {"id": "2", "team": "LAL", "pos": "G", "height": 80, "age": 27, "jersey": 1}
    cells = {c["key"]: c for c in compare(guess, answer)}
    assert cells["team"]["status"] == "miss"
    assert cells["conf"]["status"] == "hit" and cells["div"]["status"] == "hit"
    assert cells["pos"]["status"] == "hit"
    assert cells["height"]["status"] == "miss" and cells["height"]["dir"] == "down"
    assert cells["age"]["status"] == "near" and cells["age"]["dir"] == "up"
    assert cells["jersey"]["status"] == "hit"


def test_daily_guess_rejects_stale_puzzle():
    res = client.post("/api/daily/guess", json={"puzzle": 0, "player_id": "1"},
                      headers={"Origin": "http://testserver"})
    assert res.status_code == 409


def test_first_visit_source_is_remembered():
    fresh = TestClient(app)
    res = fresh.get("/login?utm_source=Reddit&utm_medium=social")
    assert "reddit/social" in res.headers.get("set-cookie", "")
    res = fresh.get("/login", headers={"Referer": "https://www.google.com/"})
    assert "hl_src" not in res.headers.get("set-cookie", "")   # ilk gelis kazanir


def test_invite_code_link_prefills_register():
    fresh = TestClient(app)
    res = fresh.get("/register?code=hoops30")
    assert 'value="hoops30"' in res.text or 'value="HOOPS30"' in res.text


def test_legal_pages_open():
    for path in ("/privacy", "/terms"):
        res = client.get(path)
        assert res.status_code == 200 and "teomanakgn84@gmail.com" in res.text


# ==================== DAVET E-POSTALARI ====================

def test_outreach_recipient_parsing():
    from services.outreach import parse_recipients
    people, bad = parse_recipients("Jordan Smith, Jordan@Example.com\nalex@example.com\n"
                                   "Sam <sam@example.org>\njordan@example.com\nno email here")
    assert [p["email"] for p in people] == ["jordan@example.com", "alex@example.com", "sam@example.org"]
    assert people[0]["name"] == "Jordan Smith" and people[1]["name"] == "" and people[2]["name"] == "Sam"
    assert bad == ["no email here"]


def test_outreach_unsubscribe_link_is_signed():
    from urllib.parse import parse_qs, urlparse
    from services.outreach import unsubscribe_url, verify_unsubscribe
    q = parse_qs(urlparse(unsubscribe_url("a@b.com")).query)
    assert verify_unsubscribe(q["e"][0], q["t"][0]) == "a@b.com"
    assert verify_unsubscribe(q["e"][0], "0" * 32) is None


def test_outreach_message_is_personal():
    from services.outreach import DEFAULT_BODY, DEFAULT_SUBJECT, message
    m = message({"email": "a@b.com", "name": "Jordan"}, DEFAULT_SUBJECT, DEFAULT_BODY, "HOOPFRIENDS")
    assert m["to"] == ["a@b.com"] and "Hi Jordan," in m["text"]
    tr = message({"email": "a@b.com", "name": "Socrates Dergi ekibi"}, "Konu", "Merhaba {name},\n\nŞöyle: {link}", "X")
    assert "Merhaba Socrates Dergi ekibi," in tr["text"] and "abonelikten çık" in tr["html"]
    blank = message({"email": "a@b.com", "name": ""}, "Konu", "Merhaba {name},\n\nŞöyle", "X")
    assert blank["text"].startswith("Merhaba,")
    assert "code=HOOPFRIENDS" in m["html"] and "unsubscribe" in m["html"]
    assert m["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_outreach_panel_needs_login():
    res = client.get("/admin/outreach", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"].startswith("/login")


# ==================== ZIYARETCILER ====================

def test_visitor_bots_are_skipped():
    from services.visits import is_bot
    assert is_bot("Mozilla/5.0 (compatible; Googlebot/2.1)")
    assert is_bot("AdsBot-Google (+http://www.google.com/adsbot.html)")
    assert is_bot("")
    assert not is_bot("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1")


def test_visitors_panel_needs_login():
    res = client.get("/admin/visitors", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"].startswith("/login")


def test_stat_match_rounds_are_hard_pairs():
    import services.minigames as mg
    fake = [{"id": str(i), "name": f"P{i}", "team": "T", "pos": "PG", "group": "G" if i % 2 else "F",
             "gp": 60, "adp": i, "stats": {"PTS": 10 + i % 7, "REB": 3, "AST": 4, "STL": 1, "BLK": 0.5,
                                            "3PM": 2, "FG%": 45, "FT%": 80}} for i in range(60)]
    orig = mg.board_players
    mg.board_players = lambda limit=220: fake
    try:
        rounds = mg.stat_match_rounds("seed")
        assert len(rounds) == 10 and rounds == mg.stat_match_rounds("seed")
        ids = [p["id"] for r in rounds for p in r["players"]]
        assert len(ids) == len(set(ids))
        for r in rounds:
            a, b = r["players"]
            assert r["answer"] in (0, 1)
            left_line = r["lines"][r["answer"]]
            assert left_line == fake[int(a["id"])]["stats"]
    finally:
        mg.board_players = orig


def test_starting_five_hides_names_and_checks_guesses():
    from services import starting_five as sf
    gid = sf.daily_game_id()
    view = sf.view(gid)
    assert view["hidden"] == 6
    hidden = [(ti, si) for ti, t in enumerate(view["teams"]) for si, s in enumerate(t["slots"]) if not s.get("given")]
    assert len(hidden) == 6 and all("name" not in view["teams"][ti]["slots"][si] for ti, si in hidden)
    full = sf.reveal(gid)
    ti, si = hidden[0]
    hit = sf.guess(gid, full[ti][si]["name"].upper())
    assert hit and hit[0]["team"] == ti and hit[0]["slot"] == si
    assert sf.guess(gid, "Nobody Atall") == []


def test_eighty_two_game_and_scoring():
    from services import eighty_two as e82
    for span in (1, 5, 10):
        g = e82.game("seed", span)
        assert len(g) == e82.SPINS and g == e82.game("seed", span)
        keys = [s[k]["key"] for s in g for k in ("main", "t", "y", "ty", "yt")]
        assert len(keys) == len(set(keys))                     # ayni takim-donem tekrar etmez
        for s in g:
            # 'takim' alternatifi ayni yillar, 'yil' alternatifi ayni takim
            assert s["t"]["start"] == s["main"]["start"] and s["t"]["abbr"] != s["main"]["abbr"]
            assert s["y"]["abbr"] == s["main"]["abbr"] and s["y"]["start"] != s["main"]["start"]
            assert s["ty"]["abbr"] == s["t"]["abbr"] and s["yt"]["start"] == s["y"]["start"]
            assert 5 <= len(s["main"]["players"]) <= e82.ROSTER_LIMIT
    # Iki yildiz + uc zayif oyuncu artik 2-80 degil
    assert 25 <= e82.wins_for(e82.rating([95, 95, 60, 60, 60])) <= 40
    assert e82.wins_for(e82.rating([99, 99, 99, 99, 99])) == 82
    assert e82.wins_for(e82.rating([60] * 5)) < 10


def test_league_alerts_flag_injured_starter_and_hot_bench():
    from services.league_insights import alerts
    def p(i, slot, value, last15, injury="ACTIVE", trend=""):
        return {"id": str(i), "name": f"P{i}", "team": "T", "slot": slot, "value": value, "last15": last15,
                "last7": last15, "injury": injury, "trend": trend}
    me = {"roster": [p(1, 0, 40, 38), p(2, 1, 20, 12, trend="cold"), p(3, 2, 25, 25, injury="OUT"),
                     p(4, 12, 15, 30, trend="hot")]}
    keys = {a["key"].split("-")[0] for a in alerts(me, [])}
    assert {"out", "bench"} <= keys
    assert alerts(me, [])[0]["level"] == "bad"


def test_player_slug_and_outlook():
    from services.player_pages import outlook, slugify
    assert slugify("Nikola Jokić") == "nikola-jokic" and slugify("Shai Gilgeous-Alexander") == "shai-gilgeous-alexander"
    p = {"name": "Test Player", "rank": 40, "avail": 0.7, "injury": "ACTIVE",
         "s": {"pts": 20, "reb": 5, "ast": 4, "stl": 1, "blk": 0.5, "tpm": 2},
         "z": {"FG%": -1.2, "FT%": 1.0, "3PM": 1.1, "PTS": 1.0, "REB": -0.2, "AST": 0.1, "STL": 0.2, "BLK": -0.3, "TO": -0.6},
         "punt_rank": {"FT%": 50, "FG%": 22, "AST": 41, "3PM": 60, "PTS": 70, "TO": 35}}
    text = " ".join(outlook(p))
    assert "No. 40" in text and "punt FG%" in text and "57 games" in text


def test_lineup_assignment_picks_best_eligible_spots():
    """Gunun kadrosu: atama en yuksek toplam degeri verir, uygun olmayan yere koymaz (scipy'siz)."""
    import numpy as np
    from services.lineup import _assign
    w = np.array([[10.0, -1e6, 3.0], [9.0, 8.0, -1e6], [-1e6, 7.0, 6.0], [1.0, 1.0, 1.0]])
    rows, cols = _assign(w)
    assert sum(w[r, c] for r, c in zip(rows, cols)) == 10 + 8 + 6
    assert all(w[r, c] > -1 for r, c in zip(rows, cols))


def test_game_sim_minutes_rotation():
    """Simulasyon dakikalari: takim 240, yildiz dakikasini korur, sakat oynamaz."""
    import numpy as np
    from services import game_sim
    players = [{"min": m, "play": 1.0} for m in (36, 34, 32, 30, 28, 24, 20, 18, 14, 10, 8, 6)]
    players[1]["play"] = 0.0
    m = game_sim._minutes(np.random.default_rng(0), players, 500)
    assert np.allclose(m.sum(axis=1), 240, atol=1e-6)
    assert m[:, 1].max() == 0
    assert m[:, 0].mean() > 32 and m[:, -1].mean() < 6
