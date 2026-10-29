"""
NBA Career liderlik tablosu. Oyun tarayicida oynandigi icin gelen kariyer
sunucuda tutarlilik kontrolunden gecer ve puani burada yeniden hesaplanir
(career.js'teki Hall of Fame puaniyla ayni formul):

  - sezon sayisi, yas, mac, sayi ortalamasi gercekci sinirlar icinde
  - oduller sezon satirlarindan sayilir (ozetteki sayilarla tutmali)
  - bir sezonda en fazla bir MVP / sampiyonluk ...; Finals MVP sampiyonluk ister
"""
import math
import re

AWARDS = ("roy", "mip", "smoy", "as", "allnba", "mvp", "dpoy", "scoring", "ring", "fmvp")
ARCHS = {"scorer", "playmaker", "threeD", "rim", "twoway"}
POSS = {"PG", "SG", "SF", "PF", "C"}


def score_of(awards, pts):
    a = awards
    return (15 * a.get("mvp", 0) + 8 * a.get("fmvp", 0) + 6 * a.get("ring", 0) + 5 * a.get("allnba", 0)
            + 3 * a.get("as", 0) + 4 * a.get("dpoy", 0) + 2 * a.get("roy", 0) + 2 * a.get("scoring", 0)
            + 2 * a.get("gold", 0) + pts / 2000)


def hof_pct(score):
    return round(100 / (1 + math.exp(-(score - 36) / 6.5)))


def clean_name(raw):
    name = re.sub(r"[^\w .'\-]", "", str(raw or ""), flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip()[:24]
    return name if len(name) >= 3 else None


def _num(x, lo, hi):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi and v == v else None


def validate(body):
    """Gelen kariyeri dogrula; (satir, hata)."""
    name = clean_name(body.get("name"))
    if not name:
        return None, "Bad name."
    pos, arch = body.get("pos"), body.get("arch")
    if pos not in POSS or arch not in ARCHS:
        return None, "Bad player."
    cid = str(body.get("id") or "")
    if not re.fullmatch(r"[a-z0-9]{10,40}", cid):
        return None, "Bad career id."
    seasons = body.get("seasons") or []
    if not 1 <= len(seasons) <= 23:
        return None, "Bad career length."
    counts = {k: 0 for k in AWARDS}
    pts_total, gp_total, ages = 0.0, 0, []
    for s in seasons:
        gp = _num(s.get("gp"), 0, 82)
        ppg = _num(s.get("pts"), 0, 42)
        age = _num(s.get("age"), 18, 42)
        if gp is None or ppg is None or age is None:
            return None, "Bad season."
        aw = [str(x) for x in s.get("aw") or []]
        if len(aw) != len(set(aw)) or any(x not in AWARDS for x in aw):
            return None, "Bad awards."
        if "fmvp" in aw and "ring" not in aw:
            return None, "Bad awards."
        if aw and gp == 0:
            return None, "Bad awards."
        for x in aw:
            counts[x] += 1
        pts_total += ppg * gp
        gp_total += int(gp)
        ages.append(int(age))
    if ages != sorted(ages) or len(set(ages)) != len(ages):
        return None, "Bad ages."
    if counts["roy"] > 1:
        return None, "Bad awards."
    gold = int(_num(body.get("gold") or 0, 0, 6) or 0)
    counts["gold"] = gold
    earnings = _num(body.get("earnings"), 0, 6000)
    if earnings is None:
        return None, "Bad earnings."
    sc = score_of(counts, pts_total)
    return {"career_id": cid, "name": name, "pos": pos, "arch": arch, "seasons": len(seasons),
            "ppg": round(pts_total / max(gp_total, 1), 1), "pts": int(round(pts_total)),
            "rings": counts["ring"], "mvps": counts["mvp"], "allstars": counts["as"],
            "earnings": round(earnings, 1), "hof": hof_pct(sc), "score": round(sc, 3)}, None
