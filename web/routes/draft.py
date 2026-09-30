"""
Draft Strategy: lig ayarlarina gore stratejilerin karsilastirmasi.

Hesap services/strategy_engine.py'de; burasi parametreleri alip sonucu
ciziyor. Ayarlar URL'de duruyor, yani sonuc sayfasi paylasilabilir ve
geri tusu calisiyor.
"""
from fastapi import APIRouter, Request

from services.cache import cache_data
from services.draft_data import get_draft_board
from services.nba_season import get_season_label
from services.strategy_engine import (AUCTION_SHAPES, CAT_LABELS, DEFAULT_RISK,
                                      FULL_SEASON_GAMES, INJURY_WORDS, NINE_CAT,
                                      RISK_LEVELS, auction_plan,
                                      availability_weighted, category_scores,
                                      draftable_depth, fragility_tier,
                                      injury_notes, picks_for_slots,
                                      replacement_level, slot_notes,
                                      strategy_report)
from utils.text import esc
from web.core import render

router = APIRouter()

ABOVE, BELOW, MIDLINE, MUTED = "#3987e5", "#e66767", "#383835", "#898781"


def _int(value, default, low, high):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def profile_svg(profile, punts):
    """Kategori profili: ortalama takima gore arti/eksi, iraksak cubuk."""
    values = [profile.get(c, 0.0) for c in NINE_CAT]
    span = max(0.9, max(abs(v) for v in values) * 1.15)
    row_h, label_w, plot_w = 26, 42, 230
    width, height = label_w + plot_w + 46, len(NINE_CAT) * row_h + 16
    mid_x = label_w + plot_w / 2
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" style="max-width:420px;display:block" '
             f'role="img" aria-label="Category profile against an average team">',
             f'<line x1="{mid_x}" y1="6" x2="{mid_x}" y2="{height - 10}" stroke="{MIDLINE}" stroke-width="1"/>']
    for i, cat in enumerate(NINE_CAT):
        cy = 8 + i * row_h + row_h / 2 - 4
        value = values[i]
        punted = cat in punts
        bar = max((abs(value) / span) * (plot_w / 2), 1.5)
        colour = MUTED if punted else (ABOVE if value >= 0 else BELOW)
        x = mid_x if value >= 0 else mid_x - bar
        parts.append(f'<text x="{label_w - 8}" y="{cy + 4}" text-anchor="end" font-size="10.5" '
                     f'font-weight="700" fill="#A9B6CE">{CAT_LABELS[cat]}</text>')
        parts.append(f'<rect x="{x:.1f}" y="{cy - 6:.1f}" width="{bar:.1f}" height="12" rx="3" '
                     f'fill="{colour}" opacity="{".45" if punted else "1"}"><title>{CAT_LABELS[cat]}: '
                     f'{value:+.2f} vs average team</title></rect>')
        text_x = mid_x + bar + 6 if value >= 0 else mid_x - bar - 6
        parts.append(f'<text x="{text_x:.1f}" y="{cy + 4:.1f}" text-anchor="{"start" if value >= 0 else "end"}" '
                     f'font-size="9.5" font-weight="700" fill="{MUTED}">{"punted" if punted else f"{value:+.2f}"}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _why_now(item):
    later = item.get("next_odds")
    if later is None:
        return "last pick"
    if later < 0.5:
        return f"likely gone by your next pick ({later * 100:.0f}% he lasts)"
    return "rated well above his ADP"


def _decorate(roster):
    for item in roster:
        tier = fragility_tier(item.get("availability", 1.0))
        item["fragile"] = tier
        status = item.get("injury")
        item["status"] = "" if not status or status == "ACTIVE" else \
            INJURY_WORDS.get(status, str(status).replace("_", " ").lower())
        cut = item.get("shortfall") or 0.0
        item["cut"] = f"-{cut * 100:.0f}%" if cut > 0.005 else "-"
        item["why"] = _why_now(item)
    return roster


def _health(durability):
    share = durability["availability"]
    reference = durability.get("reference") or 0.0
    gap = share - reference
    colour = ABOVE if gap >= -0.01 else (MUTED if gap >= -0.05 else BELOW)
    return {"share": share, "reference": reference, "missed": durability["games_missed"],
            "fragile": len(durability["fragile"]), "colour": colour,
            "flagged": [f"{n} ({INJURY_WORDS.get(s, str(s).lower())})"
                        for n, s in durability["flagged"][:3]]}


@cache_data(ttl=900, show_spinner=False, copy_result=False)
def _compute(teams, rounds, draft_type, slots, budget, risk):
    board = get_draft_board()
    if board.empty:
        return None
    scores = category_scores(board, draftable_depth(teams, rounds))
    covered = int(scores["PROJECTED"].sum())
    result = {"fallback": covered < len(scores) * 0.5}
    if draft_type == "auction":
        weighted = availability_weighted(scores, replacement_level(scores, teams, rounds),
                                         risk_weight=RISK_LEVELS[risk]["weight"])
        shapes = []
        for key, shape in AUCTION_SHAPES.items():
            plan = auction_plan(weighted, budget, rounds, punts=[], shape=key)
            shapes.append({**shape, "key": key, "plan": plan,
                           "roster": _decorate(plan["roster"]),
                           "health": _health(plan["durability"]),
                           "svg": profile_svg(plan["profile"], []),
                           "top_budget": int(budget * shape["top_share"])})
        result["shapes"] = shapes
        return result

    picks = picks_for_slots(teams, list(slots), rounds, snake=(draft_type == "snake"))
    notes = slot_notes(teams, list(slots), rounds, snake=(draft_type == "snake"))
    notes += injury_notes(scores, picks)
    reports = strategy_report(scores, picks, teams=teams, rounds=rounds, risk=risk)
    for report in reports:
        report["roster"] = _decorate(report["roster"])
        report["health"] = _health(report["durability"])
        report["svg"] = profile_svg(report["profile"], report["punts"])
    result.update({"picks": picks, "notes": notes, "reports": reports})
    return result


@router.get("/draft-strategy")
def strategy(request: Request):
    q = request.query_params
    teams = _int(q.get("teams"), 10, 4, 20)
    rounds = _int(q.get("rounds"), 13, 5, 20)
    draft_type = q.get("type", "snake")
    if draft_type not in ("snake", "linear", "auction"):
        draft_type = "snake"
    slots = sorted({_int(s, 0, 0, teams) for s in q.getlist("slot")} - {0}) or [min(3, teams)]
    budget = _int(q.get("budget"), 200, 50, 500)
    risk = q.get("risk", DEFAULT_RISK)
    if risk not in RISK_LEVELS:
        risk = DEFAULT_RISK

    result = _compute(teams, rounds, draft_type, tuple(slots), budget, risk)
    return render(request, "draft_strategy.html", active="strategy",
                  teams=teams, rounds=rounds, draft_type=draft_type, slots=slots,
                  budget=budget, risk=risk, risk_levels=RISK_LEVELS, result=result,
                  cat_labels=CAT_LABELS, season=get_season_label(),
                  full_games=FULL_SEASON_GAMES, esc=esc)
