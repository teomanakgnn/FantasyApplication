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
