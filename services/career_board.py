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


# Herkese acik tabloda kufur / nefret soylemi olmasin. Kayit silinmez, ad gizlenir.
ANON_NAME = "Anonymous Player"
_FOLD = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o",
                       "ç": "c", "Ç": "c", "â": "a", "î": "i", "û": "u", "0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
                       "7": "t", "$": "s", "@": "a"})
# Bitisik yazilsa da yakalanir (f.u.c.k, fuckyou)
_BAD_ANYWHERE = ("fuck", "bitch", "nigger", "nigga", "faggot", "dickhead", "asshole", "pussy", "pusy", "orospu", "orosbu",
                 "pezevenk", "amcik", "yarrak", "yarak", "siktir", "sikerim", "sikeyim", "kahpe", "gavat", "gotveren")
# Yalnizca tam kelime: baska adlarin icinde gecebilir (Sikma, Niger, Scunthorpe)
_BAD_WORDS = {"sik", "siki", "soktu", "amk", "aq", "pic", "ibne", "fuk", "shit", "shity", "bulshit", "whore", "slut", "cunt",
              "cock", "fag", "rape", "rapist", "nazi", "hitler", "retard", "anani", "ananin", "ananizi"}
_BAD_PREFIXES = ("sikt", "sikis", "siker", "sikim", "sikey", "sokt", "sokar", "sokay", "sokuy", "ibnel")


def is_offensive(raw):
    text = str(raw or "").translate(_FOLD).lower()
    joined = re.sub(r"[\W_]", "", text)
    squeezed = re.sub(r"(.)\1+", r"\1", joined)
    if any(w in joined or w in squeezed for w in _BAD_ANYWHERE):
        return True
    for token in re.findall(r"[^\W\d_]+", text):
        token = re.sub(r"(.)\1+", r"\1", token)
        if token in _BAD_WORDS or token.startswith(_BAD_PREFIXES):
            return True
    return False


def public_name(raw):
    """Tabloda gosterilecek ad; eski kayitlar da burada elenir."""
    return ANON_NAME if is_offensive(raw) else raw


def clean_ids(raw):
    """Istemciden gelen kariyer kimlikleri (sahiplenme icin)."""
    ids = raw if isinstance(raw, list) else []
    return [str(x) for x in ids[:30] if re.fullmatch(r"[a-z0-9]{10,40}", str(x))]


def clean_name(raw):
    name = re.sub(r"[^\w .'\-]", "", str(raw or ""), flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip()[:24]
    if len(name) < 3:
        return None
    return public_name(name)


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
