"""
Draft stratejisi hesaplari.

Tavsiyeler tahminle degil, havuzun kendi verisiyle uretiliyor:
ESPN sirali oyuncu havuzundaki kategori ortalamalarindan z-skorlari
cikariliyor, punt (bir kategoriden vazgecme) stratejileri o kategori
hesaptan dusurulerek yeniden siralaniyor ve kullanicinin gercek secim
siralarinda kimlerin masada kalacagi ADP'den bulunuyor.

Tek bir "dogru" strateji yok; bu modul her stratejiyi ayni olcutle
puanlayip karsilastirilabilir hale getiriyor.

Olcutun siniri: hesap gecen sezonun mac basi uretimine ve bugunku
ADP'ye dayanir. Haftalik varyans, sakatlik, waiver hareketi ve rakip
takimlarin kendi stratejileri hesaba girmez. Bu yuzden cikti bir
"kazanma olasiligi" degil, ayni kosullarda stratejilerin birbirine
gore nasil durduguna dair bir izdusumdur.
"""
import math

import numpy as np
import pandas as pd

# 9 kategori ligi. Yuzdeler ham oran degil, hacimle agirliklandirilmis
# etki olarak hesaplanir (asagida).
COUNTING_CATS = ["PTS", "REB", "AST", "STL", "BLK", "3Pts"]
NEGATIVE_CATS = ["TO"]          # az olmasi iyi
PERCENT_CATS = {"FG%": ("FGM", "FGA"), "FT%": ("FTM", "FTA")}
NINE_CAT = list(PERCENT_CATS) + ["3Pts", "PTS", "REB", "AST", "STL", "BLK", "TO"]

CAT_LABELS = {
    "FG%": "FG%", "FT%": "FT%", "3Pts": "3PM", "PTS": "PTS", "REB": "REB",
    "AST": "AST", "STL": "STL", "BLK": "BLK", "TO": "TO",
}

# Havuzun ilk kac oyuncusu "draft edilebilir" sayilsin. z-skorlari lig
# genelinde degil, gercekten secilen oyuncular arasinda anlamli.
def draftable_depth(teams, rounds):
    return max(60, min(int(teams * rounds * 1.25), 300))


STRATEGIES = [
    {
        "key": "balanced",
        "name": "Balanced",
        "punts": [],
        "blurb": "Take the best player available and stay competitive in all nine "
                 "categories.",
        "works_when": "You pick near the turn and want flexibility, or it is your "
                      "first season in the league.",
        "risk": "Winning a category by a lot is wasted value. Balanced teams often "
                "finish second in many categories instead of first in a few.",
    },
    {
        "key": "punt_ft",
        "name": "Punt FT%",
        "punts": ["FT%"],
        "blurb": "Give up free-throw percentage and load up on bigs who score, "
                 "rebound and block.",
        "works_when": "You can land one of the elite poor-shooting bigs early.",
        "risk": "You are locked in by round three. Guards who shoot well become "
                "hard to use.",
    },
    {
        "key": "punt_fg",
        "name": "Punt FG%",
        "punts": ["FG%"],
        "blurb": "Give up field-goal percentage and chase guards: threes, assists, "
                 "steals and free throws.",
        "works_when": "You pick late in round one and the elite bigs are gone.",
        "risk": "Volume scorers on bad efficiency still hurt you elsewhere if they "
                "turn the ball over.",
    },
    {
        "key": "punt_ast",
        "name": "Punt assists",
        "punts": ["AST"],
        "blurb": "Skip playmaking and build around bigs and wings with defensive "
                 "stats.",
        "works_when": "You have an early pick and want the best bigs without paying "
                      "for guard production.",
        "risk": "Assists correlate with usage; you may also give up points.",
    },
    {
        "key": "punt_3pm",
        "name": "Punt threes",
        "punts": ["3Pts"],
        "blurb": "Ignore three-pointers and win the interior categories plus "
                 "percentages.",
        "works_when": "Your league drafts shooters early and leaves bigs on the "
                      "board.",
        "risk": "Threes come attached to points; giving them up can cost two "
                "categories.",
    },
    {
        "key": "punt_pts",
        "name": "Punt points",
        "punts": ["PTS"],
        "blurb": "Give up raw scoring and collect specialists: steals, blocks, "
                 "percentages and assists.",
        "works_when": "You pick in the middle and the top scorers are gone.",
        "risk": "The hardest punt to run. Points are the easiest category to "
                "accumulate by accident, so your edge elsewhere must be large.",
    },
]

STRATEGY_BY_KEY = {s["key"]: s for s in STRATEGIES}


# ==================== Z-SKORLARI ====================

def category_scores(board, depth=None):
    """
    Her oyuncu icin kategori bazinda z-skoru tablosu.

    Yuzdeler icin ham oran kullanilmaz: %90 atan ama maclik iki serbest
    atisi olan bir oyuncu, %80 atan ama sekiz deneyen birinden daha
    degerli gorunurdu. Bunun yerine hacimle agirlikli etki hesaplanir:
    (oyuncunun orani - havuz orani) * oyuncunun denemesi.
    """
    df = board.copy()
    if depth:
        df = df.nsmallest(min(depth, len(df)), "ADP")
    df = df.reset_index(drop=True)

    out = pd.DataFrame(index=df.index)
    for cat in COUNTING_CATS:
        values = pd.to_numeric(df.get(cat), errors="coerce").fillna(0.0)
        std = values.std(ddof=0)
        out[cat] = 0.0 if std == 0 else (values - values.mean()) / std

    for cat in NEGATIVE_CATS:
        values = pd.to_numeric(df.get(cat), errors="coerce").fillna(0.0)
        std = values.std(ddof=0)
        out[cat] = 0.0 if std == 0 else -(values - values.mean()) / std

    for cat, (made_col, att_col) in PERCENT_CATS.items():
        made = pd.to_numeric(df.get(made_col), errors="coerce").fillna(0.0)
        att = pd.to_numeric(df.get(att_col), errors="coerce").fillna(0.0)
        pool_rate = made.sum() / att.sum() if att.sum() else 0.0
        impact = (np.where(att > 0, made / att.replace(0, np.nan), pool_rate)
                  - pool_rate) * att
        impact = pd.Series(impact, index=df.index).fillna(0.0)
        std = impact.std(ddof=0)
        out[cat] = 0.0 if std == 0 else (impact - impact.mean()) / std

    out["PLAYER"] = df["PLAYER"].values
    out["ADP"] = pd.to_numeric(df["ADP"], errors="coerce").fillna(999).values
    out["POS"] = df["POS"].values
    out["POSITIONS"] = df["POSITIONS"].values
    out["TEAM"] = df["TEAM"].values
    out["AUCTION"] = pd.to_numeric(df.get("AUCTION"), errors="coerce").fillna(1).values
    out["INJURY"] = df.get("INJURY", pd.Series(["ACTIVE"] * len(df))).values
    out["FPTS"] = pd.to_numeric(df.get("FPTS"), errors="coerce").fillna(0).values
    return out


def total_value(scores, punts=(), cats=NINE_CAT):
    """Punt edilen kategoriler disinda toplam z-skoru."""
    active = [c for c in cats if c not in punts]
    return scores[active].sum(axis=1)


# ==================== SECIM SIRALARI ====================

def snake_picks(teams, slot, rounds):
    """Snake draftta bir siranin tum genel secim numaralari."""
    picks = []
    for rnd in range(1, rounds + 1):
        if rnd % 2 == 1:
            picks.append((rnd, (rnd - 1) * teams + slot))
        else:
            picks.append((rnd, (rnd - 1) * teams + (teams - slot + 1)))
    return picks


def linear_picks(teams, slot, rounds):
    """Her turda ayni sira (linear/straight draft)."""
    return [(rnd, (rnd - 1) * teams + slot) for rnd in range(1, rounds + 1)]


def picks_for_slots(teams, slots, rounds, snake=True):
    """Birden fazla sirasi olan kullanici icin tum secimler, sirali."""
    fn = snake_picks if snake else linear_picks
    out = []
    for slot in slots:
        out.extend(fn(teams, slot, rounds))
    out.sort(key=lambda item: item[1])
    return out


# ==================== HEDEF KADRO ====================

# Kadro dengesi: bu sayilara ulasilana kadar eksik mevki onceliklidir.
MIN_POSITION_TARGETS = {"C": 2, "G": 4, "F": 4}


def _position_group(positions):
    groups = set()
    for pos in positions or []:
        if pos in ("PG", "SG", "G"):
            groups.add("G")
        elif pos in ("SF", "PF", "F"):
            groups.add("F")
        elif pos == "C":
            groups.add("C")
    return groups


def available_at(scores, pick, reach=3):
    """
    Bu secimde masada kalmasi beklenen oyuncular.

    ADP'si secim numarasindan kucuk olanlar gitmis sayilir; kucuk bir
    reach payi birakilir. Bu, diger takimlarin seciminin yerine gecer.
    """
    return scores[scores["ADP"] >= pick - reach]


def build_target_roster(scores, picks, punts=(), cats=NINE_CAT, reach=3):
    """
    Bir strateji icin tur tur hedef kadro.

    Her secimde masada kalmasi beklenen oyuncular arasindan stratejinin
    en degerlisi aliniyor; kadro dengesi icin eksik mevkiye kucuk bir
    oncelik veriliyor.
    """
    value = total_value(scores, punts, cats)
    table = scores.assign(VALUE=value)
    taken, roster = set(), []
    counts = {"C": 0, "G": 0, "F": 0}

    for rnd, pick in picks:
        pool = available_at(table, pick, reach)
        pool = pool[~pool["PLAYER"].isin(taken)]
        if pool.empty:
            continue

        need = {g for g, target in MIN_POSITION_TARGETS.items()
                if counts[g] < target}
        remaining = len(picks) - len(roster)
        scored = pool.copy()
        # Kadro dengesi bonusu: son turlara yaklasirken agirligi artar ki
        # bes guard'la kalmayalim.
        urgency = 0.35 if remaining > 4 else 0.9
        scored["FIT"] = scored["VALUE"] + scored["POSITIONS"].apply(
            lambda pos: urgency if _position_group(pos) & need else 0.0)

        best = scored.nlargest(1, "FIT").iloc[0]
        taken.add(best["PLAYER"])
        for group in _position_group(best["POSITIONS"]):
            counts[group] += 1
        roster.append({
            "round": rnd,
            "pick": pick,
            "player": best["PLAYER"],
            "team": best["TEAM"],
            "pos": best["POS"],
            "adp": int(best["ADP"]) if best["ADP"] < 999 else None,
            "value": float(best["VALUE"]),
            "auction": int(best["AUCTION"]),
            "injury": best["INJURY"],
        })
    return roster


def roster_profile(scores, roster, cats=NINE_CAT):
    """Kurulan kadronun kategori bazinda ortalama z-skoru."""
    names = [item["player"] for item in roster]
    rows = scores[scores["PLAYER"].isin(names)]
    if rows.empty:
        return {cat: 0.0 for cat in cats}
    return {cat: float(rows[cat].mean()) for cat in cats}


def _phi(x):
    """Standart normal dagilimin birikimli olasiligi."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def league_baseline(scores, teams, rounds, cats=NINE_CAT):
    """
    Ortalama bir rakip takimin kategori toplamlari.

    Rakip olarak "havuz ortalamasi" almak yaniltici: havuzda hic draft
    edilmeyen oyuncular da var, bu yuzden her strateji olduğundan iyi
    gorunuyor ve aralarindaki fark siliniyordu. Gercek olcut, draft
    edilen oyuncularin takim basina dusen payidir.
    """
    drafted = scores.nsmallest(min(teams * rounds, len(scores)), "ADP")
    return {cat: float(drafted[cat].sum()) / max(1, teams) for cat in cats}


def expected_category_wins(scores, roster, punts=(), cats=NINE_CAT,
                           baseline=None):
    """
    Haftalik eslesmede beklenen kazanilan kategori sayisi.

    Stratejileri "punt edilmeyen kategorilerin ortalamasi" ile
    kiyaslamak yaniltici: bir kategoriden vazgecen strateji, vazgectigi
    kategorinin bedelini hic odemeden ortalamasini yukseltiyordu. Burada
    punt edilen kategori dogrudan KAYIP sayiliyor, yani punt'in gercek
    maliyeti hesaba giriyor.
    """
    names = [item["player"] for item in roster]
    rows = scores[scores["PLAYER"].isin(names)]
    if rows.empty:
        return 0.0, {cat: 0.0 for cat in cats}

    spread = math.sqrt(max(2.0, 2.0 * len(rows)))
    chances = {}
    for cat in cats:
        if cat in punts:
            chances[cat] = 0.0          # vazgecilen kategori kaybedilir
            continue
        mine = float(rows[cat].sum())
        rival = (baseline or {}).get(cat, 0.0)
        chances[cat] = _phi((mine - rival) / spread)
    return sum(chances.values()), chances


def strategy_report(scores, picks, cats=NINE_CAT, reach=3,
                    teams=10, rounds=13):
    """Tum stratejileri ayni secimler icin kurup karsilastirir."""
    baseline = league_baseline(scores, teams, rounds, cats)
    reports = []
    for strategy in STRATEGIES:
        punts = strategy["punts"]
        roster = build_target_roster(scores, picks, punts, cats, reach)
        profile = roster_profile(scores, roster, cats)
        wins, chances = expected_category_wins(scores, roster, punts, cats,
                                               baseline)
        live = [c for c in cats if c not in punts]
        reports.append({
            **strategy,
            "roster": roster,
            "profile": profile,
            "chances": chances,
            "expected_wins": wins,
            "strong": sorted(live, key=lambda c: -chances[c])[:3],
            "weak": sorted(live, key=lambda c: chances[c])[:2],
        })
    reports.sort(key=lambda r: -r["expected_wins"])
    return reports


# ==================== ACIK ARTIRMA ====================

# Butcenin yildizlara ne kadarinin ayrilacagi. Ilk sayi en pahali
# oyuncunun payi, sonrakiler sirayla azalir.
AUCTION_SHAPES = {
    "stars": {
        "name": "Stars and scrubs",
        "top_share": 0.72,
        "stars": 3,
        "per_pick_cap": 0.50,
        "blurb": "Spend roughly three quarters of the budget on three players and "
                 "fill the rest at $1-3.",
        "works_when": "Your league overpays in the middle of the auction; the $1 "
                      "pool is where the value hides.",
        "risk": "One injury to a star ends the season.",
    },
    "balanced": {
        "name": "Balanced roster",
        "top_share": 0.55,
        "stars": 5,
        # Tek oyuncuya yildiz butcesinin en fazla dortte biri. Bu sinir
        # olmadan "dengeli" secim de en pahali oyuncuyu aliyordu.
        "per_pick_cap": 0.26,
        "blurb": "Buy five solid starters instead of three stars, then fill out.",
        "works_when": "Your league bids aggressively on elite players early.",
        "risk": "You may not win any category outright.",
    },
}


def auction_plan(scores, budget, roster_size, punts=(), shape="stars",
                 cats=NINE_CAT):
    """
    Butce dagilimi ve o butceye sigan ornek kadro.

    Her acik yer icin en az $1 ayrilir; kalan butce stratejinin sekline
    gore dagitilir.
    """
    config = AUCTION_SHAPES[shape]
    value = total_value(scores, punts, cats)
    table = scores.assign(VALUE=value).sort_values("VALUE", ascending=False)

    star_count = min(config["stars"], roster_size)
    star_budget = int(budget * config["top_share"])
    filler_slots = roster_size - star_count
    # Her doldurma yeri icin en az $1
    star_budget = min(star_budget, budget - filler_slots)

    roster, spent, taken = [], 0, set()
    for i in range(star_count):
        # Kalan yildiz butcesini kalan yildiz sayisina bol
        left = star_budget - spent
        slots_left = star_count - i
        cap = max(1, int(min(left - (slots_left - 1),
                             star_budget * config["per_pick_cap"])))
        pool = table[(~table["PLAYER"].isin(taken)) & (table["AUCTION"] <= cap)]
        if pool.empty:
            continue
        best = pool.iloc[0]
        price = int(best["AUCTION"])
        roster.append({"player": best["PLAYER"], "team": best["TEAM"],
                       "pos": best["POS"], "price": price,
                       "value": float(best["VALUE"]), "tier": "star"})
        taken.add(best["PLAYER"])
        spent += price

    fill_budget = budget - spent
    for _ in range(filler_slots):
        slots_left = filler_slots - (len(roster) - star_count)
        cap = max(1, fill_budget - (slots_left - 1))
        pool = table[(~table["PLAYER"].isin(taken)) & (table["AUCTION"] <= cap)]
        if pool.empty:
            break
        best = pool.iloc[0]
        price = max(1, int(best["AUCTION"]))
        roster.append({"player": best["PLAYER"], "team": best["TEAM"],
                       "pos": best["POS"], "price": price,
                       "value": float(best["VALUE"]), "tier": "filler"})
        taken.add(best["PLAYER"])
        fill_budget -= price

    return {
        "shape": config,
        "roster": roster,
        "spent": sum(item["price"] for item in roster),
        "budget": budget,
        "profile": roster_profile(scores,
                                  [{"player": r["player"]} for r in roster], cats),
    }


# ==================== SIRA ANALIZI ====================

def slot_notes(teams, slots, rounds, snake=True):
    """Secim siralarina bakip kisa, somut gozlemler uretir."""
    notes = []
    picks = picks_for_slots(teams, slots, rounds, snake)
    if not picks:
        return notes

    first = picks[0][1]
    if snake and len(slots) == 1:
        slot = slots[0]
        turn_gap = teams * 2 - (2 * slot - 1)
        if slot <= max(2, teams // 6):
            notes.append(
                f"You open at {first} overall, so one of the top few players is "
                "yours. The cost is the longest wait in the draft: "
                f"{turn_gap} picks between your first and second selection.")
        elif slot >= teams - max(1, teams // 6):
            back = teams * 2 - 2 * slot + 1
            notes.append(
                f"You pick {first} and {first + back} back to back. You never get "
                "an elite player, but you take two at every turn, which suits a "
                "punt build.")
        else:
            notes.append(
                f"A middle slot at {first} overall. You see the board settle "
                "before every pick and can react to what the room is doing.")

    early = [p for _, p in picks if p <= teams * 3]
    if len(early) >= 2 and snake:
        notes.append(
            f"Your first three rounds land at picks {', '.join(str(p) for p in early[:3])}.")
    return notes
