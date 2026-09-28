"""
Draft stratejisi hesaplari.

Tavsiyeler tahminle degil, havuzun kendi verisiyle uretiliyor:
ESPN sirali oyuncu havuzundaki kategori ortalamalarindan z-skorlari
cikariliyor, punt (bir kategoriden vazgecme) stratejileri o kategori
hesaptan dusurulerek yeniden siralaniyor ve kullanicinin gercek secim
siralarinda kimlerin masada kalacagi ADP'den bulunuyor.

Tek bir "dogru" strateji yok; bu modul her stratejiyi ayni olcutle
puanlayip karsilastirilabilir hale getiriyor.

Uretim olcusu gelecek sezonun mac basi projeksiyonu; musaitlik ise iki
ayri sinyalden geliyor: projeksiyondaki mac sayisi ve oyuncunun draft
gunu tasidigi sakatlik bayragi. Mac kacirmanin bedeli sifir sayilmiyor;
o kadro yerinde waiver seviyesinde bir oyuncu oynuyor kabul ediliyor.

Olcutun siniri: haftalik varyans, waiver hareketi, sezon ici takaslar ve
rakip takimlarin kendi stratejileri hesaba girmez. Bu yuzden cikti bir
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


# ==================== MUSAITLIK (SAKATLIK) ====================

FULL_SEASON_GAMES = 82

# ESPN'in draft havuzunda dondurdugu sakatlik durumlari. Bu kesinti
# projeksiyonun UZERINE biniyor: ESPN'in mac tahmini bilinen uzun sureli
# sakatliklari kismen zaten iceriyor (olculdu: havuz medyani 68 mac,
# kirilgan yildizlar 59-67 bandinda), ama draft gunu tasinan bir bayragi
# icermiyor - kadro disi bir oyuncunun projeksiyonu hala 70 mac olabiliyor.
INJURY_FLAG_PENALTY = {
    "ACTIVE": 0.00,
    "DAY_TO_DAY": 0.04,
    "QUESTIONABLE": 0.06,
    "DOUBTFUL": 0.12,
    "OUT": 0.25,
    "INJURY_RESERVE": 0.45,
    "SUSPENSION": 0.10,
}

# Kullanicinin sakatlik riskine karsi durusu. Katsayi, eksik mac sayisinin
# degere ne kadar yansiyacagini olceklendirir: 0 = hic bakma,
# 1 = oldugu gibi say, 1.6 = kirilgan oyuncudan kacin.
RISK_LEVELS = {
    "ignore": {
        "name": "Ignore injuries",
        "weight": 0.0,
        "note": "Players are ranked on per-game production alone.",
    },
    "balanced": {
        "name": "Price the risk in",
        "weight": 1.0,
        "note": "Missed games cost you what they actually cost: "
                "replacement-level production in that roster spot.",
    },
    "avoid": {
        "name": "Avoid fragile players",
        "weight": 1.6,
        "note": "Missed games are penalised beyond their projected cost, "
                "which pushes the board toward durable players.",
    },
}
DEFAULT_RISK = "balanced"

# Musaitlik agirligi bir oyuncunun beklenen bedelini zaten dusuyor. Bunun
# ustune, ortalama draft edilen oyuncudan DAHA kirilgan olmanin ayri bir
# cezasi var: "kirilgandan kacin" bir tahmin degil, tercih.
#
# Esik sabit bir sayi degil, ligin kendi temposu (ortalama bir draft edilen
# oyuncunun kacirdigi mac payi, olculdu: 0.154). Sabit bir toplam butce
# denendi ve ise yaramadi: 13 turluk bir kadroda ancak 8. turda asiliyordu,
# yani ayari en cok onemsendigi yerde - ilk turlarda - tamamen sessizdi.
RISK_FRAGILITY_WEIGHT = 1.5

# Bu esigin altinda kalan oyuncu kartlarda "kirilgan" olarak isaretlenir.
# Olcut ortalama draft edilen oyuncu (olculdu: 0.84, yani ~69 mac); esik
# onun biraz altinda duruyor ki her ikinci oyuncu isaretlenmesin.
FRAGILE_BELOW = 0.80          # ~66 mac
FRAGILE_SEVERE = 0.72         # ~59 mac: sezonun dortte birinden fazlasi


def fragility_tier(player_availability):
    """
    Bir oyuncunun kirilganlik seviyesi: 0 = sorun yok, 1 = dikkat,
    2 = sezonun dortte birinden fazlasini kacirmasi bekleniyor.

    Tabloda isaret koymak icin; esikler tek yerde dursun diye burada.
    """
    if player_availability < FRAGILE_SEVERE:
        return 2
    if player_availability < FRAGILE_BELOW:
        return 1
    return 0


def _numeric(df, column):
    """Sutunu sayiya cevirir; sutun yoksa tamami NaN olan seri doner."""
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


# Projeksiyon yoksa gecen sezonun mac sayisina dusuyoruz, ama o tek basina
# gurultulu bir tahmin: bes mac oynamis bir oyuncu "gelecek sezon %6 musait"
# demek degil, sadece gecen sezonu kaybetmis demek. Gozlem bu yuzden havuz
# medyanina dogru cekiliyor (yariya kadar).
FALLBACK_SHRINK = 0.5

# Hicbir sinyal yoksa (ne projeksiyon ne gecen sezon) kullanilan pay.
UNKNOWN_SHARE = 0.85


def expected_games(df):
    """
    Oyuncunun kac mac oynamasi beklendigi ve bunun sezona orani.

    Once ESPN'in gelecek sezon projeksiyonu - o zaten bir tahmin, oldugu
    gibi aliniyor. Projeksiyonu olmayan oyuncuda gecen sezonun gerceklesen
    mac sayisi medyana dogru cekilerek kullaniliyor. Sifir mac "bilinmiyor"
    demek (caylaklarda gecen sezon 0 olarak doluyor), o yuzden sifirlar
    NaN sayiliyor.

    Returns:
        (games, share) - ikisi de df ile ayni indeksli seriler.
    """
    projected = _numeric(df, "PROJ_GP")
    projected = projected.where(projected > 0)
    played = _numeric(df, "GP")
    played = played.where(played > 0)

    share = (projected / FULL_SEASON_GAMES).clip(upper=1.0)
    observed = (played / FULL_SEASON_GAMES).clip(upper=1.0)

    known = share.dropna()
    if not known.empty:
        median = float(known.median())
    elif observed.notna().any():
        median = float(observed.median())
    else:
        median = UNKNOWN_SHARE

    shrunk = median + FALLBACK_SHRINK * (observed - median)
    share = share.fillna(shrunk).fillna(median).clip(lower=0.05, upper=1.0)
    # Gosterilen mac sayisi hesabin kullandigi sayiyla ayni olsun: gecen
    # sezonun ham 5 maci ekranda durup arkada 37 varsaymak kafa karistirir.
    return (share * FULL_SEASON_GAMES).round(), share


def availability(df):
    """
    Sezonun ne kadarini oynamasi beklendigi (0-1).

    Iki sinyal carpilir: beklenen mac payi ve draft gunu sakatlik bayragi.
    Bayrak ayri durmak zorunda, cunku projeksiyon onu icermiyor: kadro disi
    bir oyuncunun projeksiyonu hala 70 mac olabiliyor.
    """
    _, share = expected_games(df)

    if "INJURY" not in df.columns:
        penalty = pd.Series(0.0, index=df.index)
    else:
        penalty = df["INJURY"].fillna("ACTIVE").map(INJURY_FLAG_PENALTY).fillna(0.0)

    return (share * (1.0 - penalty)).clip(lower=0.05, upper=1.0)


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

def _stat_column(df, cat, basis):
    """
    Bir kategorinin kaynak sutunu.

    'projection' modunda gelecek sezon projeksiyonu kullanilir; projeksiyonu
    olmayan oyuncu (havuzun derinindeki isimler) gecen sezonun gerceklesen
    mac basi uretimine duser. Boylece tek bir eksik tahmin oyuncuyu
    listeden silmiyor.
    """
    actual = _numeric(df, cat)
    if basis != "projection":
        return actual.fillna(0.0)
    return _numeric(df, f"PROJ_{cat}").fillna(actual).fillna(0.0)


def category_scores(board, depth=None, basis="projection"):
    """
    Her oyuncu icin kategori bazinda z-skoru tablosu.

    Sayilar mac basi, yani "oynadiginda ne uretiyor" sorusunun cevabi;
    kac mac oynayacagi ayri tutulur (bkz. availability_weighted).

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
        values = _stat_column(df, cat, basis)
        std = values.std(ddof=0)
        out[cat] = 0.0 if std == 0 else (values - values.mean()) / std

    for cat in NEGATIVE_CATS:
        values = _stat_column(df, cat, basis)
        std = values.std(ddof=0)
        out[cat] = 0.0 if std == 0 else -(values - values.mean()) / std

    for cat, (made_col, att_col) in PERCENT_CATS.items():
        made = _stat_column(df, made_col, basis)
        att = _stat_column(df, att_col, basis)
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
    out["INJURY"] = (df["INJURY"] if "INJURY" in df.columns
                     else pd.Series(["ACTIVE"] * len(df))).values
    out["FPTS"] = pd.to_numeric(df.get("FPTS"), errors="coerce").fillna(0).values
    # Sakatlik hesabi icin: beklenen mac sayisi ve ondan cikan musaitlik.
    out["GAMES"] = expected_games(df)[0].values
    out["AVAIL"] = availability(df).values
    # Kategorileri hangi kaynaktan aldigini kullaniciya soyleyebilmek icin.
    projected = _numeric(df, "PROJ_PTS").notna() if basis == "projection" else pd.Series(False, index=df.index)
    out["PROJECTED"] = projected.values
    return out


# ==================== MUSAITLIK AGIRLIKLI DEGER ====================

def replacement_level(scores, teams, rounds, cats=NINE_CAT):
    """
    Draft edilen havuzun hemen disindaki oyuncunun kategori z-skorlari.

    Bir oyuncu mac kacirdiginda kadro yeri bos durmuyor: waiver'dan alinan
    biri oynuyor. Kayip bu yuzden "sifir uretim" degil, yedek seviyesiyle
    aradaki fark. Sinirdaki bir avuc oyuncunun ortalamasi aliniyor.
    """
    drafted = teams * rounds
    window = max(10, teams * 2)
    tail = scores[(scores["ADP"] > drafted) & (scores["ADP"] <= drafted + window)]
    if tail.empty:
        # Havuz ligden kucukse en sondaki oyuncular yedek seviyesini verir.
        tail = scores.nlargest(min(window, len(scores)), "ADP")
    return {cat: float(tail[cat].mean()) for cat in cats}


def availability_weighted(scores, replacement, cats=NINE_CAT, risk_weight=1.0):
    """
    Mac basi z-skorlarini beklenen mac sayisina gore agirliklandirir.

    Her kategori icin:
        z_etkin = (1 - eksik) * z + eksik * z_yedek

    Kaciracagi maclarda kadro yerini yedek seviyesinde bir oyuncu
    doldurur. Bu kurgu sakatligi hicbir zaman odullendirmiyor: yedek
    seviyesi draft edilen her oyuncunun altinda oldugu icin eksik mac
    daima degeri dusuruyor - z'yi dogrudan musaitlikle carpmak ise
    negatif z'li oyuncuyu sakatlandikca "iyilestirirdi".

    risk_weight = 0 ise tablo oldugu gibi doner (sakatliga bakma).
    """
    out = scores.copy()
    if risk_weight <= 0:
        out["SHORTFALL"] = 0.0
        return out

    shortfall = ((1.0 - out["AVAIL"]) * risk_weight).clip(lower=0.0, upper=1.0)
    for cat in cats:
        out[cat] = (1.0 - shortfall) * out[cat] + shortfall * replacement.get(cat, 0.0)
    out["SHORTFALL"] = shortfall
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


def build_target_roster(scores, picks, punts=(), cats=NINE_CAT, reach=3,
                       risk_weight=1.0, pace=None):
    """
    Bir strateji icin tur tur hedef kadro.

    Her secimde masada kalmasi beklenen oyuncular arasindan stratejinin
    en degerlisi aliniyor; kadro dengesi icin eksik mevkiye kucuk bir
    oncelik veriliyor.

    'scores' musaitlik agirlikli tablo oldugu icin eksik mac beklentisi
    zaten degere girmis durumda. Buna ek olarak ortalamadan kirilgan her
    aday ayrica geriye dusuyor (bkz. RISK_FRAGILITY_WEIGHT); bu, uretim
    farki yeterince buyukse kirilgan yildizi yine de masada birakmaz -
    tercihi zorlar, matematigi bozmaz.
    """
    value = total_value(scores, punts, cats)
    table = scores.assign(VALUE=value)
    if pace is None:
        pace = 1.0 - baseline_availability(scores)
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

        # Ortalama bir draft edilen oyuncudan daha cok mac kacirmasi beklenen
        # aday, aradaki fark kadar geriye duser. Ortalama ve ustu dayanikli
        # oyuncuda ceza sifir, yani kimse "saglam" diye odullendirilmiyor.
        if risk_weight > 0 and pace > 0:
            frailty = ((1.0 - scored["AVAIL"]) - pace).clip(lower=0.0)
            scored["FIT"] -= RISK_FRAGILITY_WEIGHT * risk_weight * frailty

        best = scored.nlargest(1, "FIT").iloc[0]
        taken.add(best["PLAYER"])
        for group in _position_group(best["POSITIONS"]):
            counts[group] += 1
        games = best["GAMES"]
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
            "availability": float(best["AVAIL"]),
            "games": None if pd.isna(games) else int(round(float(games))),
            # Degerinin yuzde kaci eksik mac beklentisi yuzunden dusuldu.
            "shortfall": float(best["SHORTFALL"]) if "SHORTFALL" in best else 0.0,
        })
    return roster


def baseline_availability(scores, teams=None, rounds=None):
    """
    Ortalama bir draft edilen oyuncunun musaitligi.

    Kadronun %78 oynamasi tek basina bir sey soylemiyor; karsilastirilacak
    bir sey gerekiyor. Olculdu: bu deger lig sekli degisse de 0.84 civarinda
    duruyor, cunku havuzun tamami degil draft edilen kismi aliniyor.
    """
    if scores.empty:
        return 0.0
    pool = scores
    if teams and rounds:
        pool = scores.nsmallest(min(teams * rounds, len(scores)), "ADP")
    return float(pool["AVAIL"].mean())


def roster_durability(roster, reference=None):
    """
    Kadronun sakatlik ozeti.

    'games_missed' tum kadronun 82 maclik sezona gore beklenen eksigi;
    haftalik eslesmede kac kez eksik kadroyla cikilacaginin olcusu.
    'reference' ortalama draft edilen oyuncunun musaitligi - kadronun
    sayisi ancak buna gore okunabiliyor.
    """
    if not roster:
        return {"availability": 0.0, "games_missed": 0, "fragile": [],
                "flagged": [], "reference": reference or 0.0}
    shares = [item["availability"] for item in roster]
    return {
        "availability": sum(shares) / len(shares),
        "games_missed": int(round(sum((1.0 - s) * FULL_SEASON_GAMES for s in shares))),
        "fragile": [item["player"] for item in roster
                    if item["availability"] < FRAGILE_BELOW],
        "flagged": [(item["player"], item["injury"]) for item in roster
                    if item["injury"] not in ("ACTIVE", None, "")],
        "reference": reference if reference is not None else 0.0,
    }


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
                    teams=10, rounds=13, risk=DEFAULT_RISK):
    """
    Tum stratejileri ayni secimler icin kurup karsilastirir.

    Once tablo musaitlige gore agirliklandiriliyor; rakip takimin olcutu
    de ayni tablodan cikiyor, yoksa sakatliklari yalnizca kullanicinin
    kadrosuna yuklemis olurduk (lig geneli de mac kaybediyor).
    """
    risk_weight = RISK_LEVELS.get(risk, RISK_LEVELS[DEFAULT_RISK])["weight"]
    replacement = replacement_level(scores, teams, rounds, cats)
    table = availability_weighted(scores, replacement, cats, risk_weight)

    baseline = league_baseline(table, teams, rounds, cats)
    reference = baseline_availability(table, teams, rounds)
    pace = 1.0 - reference
    reports = []
    for strategy in STRATEGIES:
        punts = strategy["punts"]
        roster = build_target_roster(table, picks, punts, cats, reach,
                                     risk_weight, pace)
        profile = roster_profile(table, roster, cats)
        wins, chances = expected_category_wins(table, roster, punts, cats,
                                               baseline)
        live = [c for c in cats if c not in punts]
        reports.append({
            **strategy,
            "roster": roster,
            "profile": profile,
            "chances": chances,
            "expected_wins": wins,
            "durability": roster_durability(roster, reference),
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


def _auction_health(row):
    """Acik artirma satirina sakatlik alanlarini ayni sekilde ekler."""
    games = row["GAMES"] if "GAMES" in row else np.nan
    return {
        "injury": row["INJURY"] if "INJURY" in row else "ACTIVE",
        "availability": float(row["AVAIL"]) if "AVAIL" in row else 1.0,
        "games": None if pd.isna(games) else int(round(float(games))),
        "shortfall": float(row["SHORTFALL"]) if "SHORTFALL" in row else 0.0,
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
                       "value": float(best["VALUE"]), "tier": "star",
                       **_auction_health(best)})
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
                       "value": float(best["VALUE"]), "tier": "filler",
                       **_auction_health(best)})
        taken.add(best["PLAYER"])
        fill_budget -= price

    return {
        "shape": config,
        "roster": roster,
        "spent": sum(item["price"] for item in roster),
        "budget": budget,
        "profile": roster_profile(scores,
                                  [{"player": r["player"]} for r in roster], cats),
        "durability": roster_durability(roster, baseline_availability(scores)),
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


# Bayragin kullaniciya nasil okunacagi.
INJURY_WORDS = {
    "OUT": "out",
    "INJURY_RESERVE": "on injured reserve",
    "DOUBTFUL": "doubtful",
    "QUESTIONABLE": "questionable",
    "DAY_TO_DAY": "day to day",
    "SUSPENSION": "suspended",
}


def injury_notes(scores, picks, reach=3, limit=2):
    """
    Kullanicinin ilk turlarina denk gelen sakatlik uyarilari.

    Sadece erken secimler icin uretiliyor: orada bir bayrak kadronun
    tamamini belirliyor, onuncu turda ayni bayrak gurultuden ibaret.
    """
    notes = []
    if scores.empty:
        return notes

    early = [(rnd, pick) for rnd, pick in picks][:3]
    seen = set()
    for rnd, pick in early:
        pool = available_at(scores, pick, reach).nsmallest(4, "ADP")
        for _, row in pool.iterrows():
            status = row["INJURY"]
            name = row["PLAYER"]
            if name in seen or status in ("ACTIVE", None, ""):
                continue
            seen.add(name)
            word = INJURY_WORDS.get(status, str(status).replace("_", " ").lower())
            games = row["GAMES"]
            games_text = (f" He is projected for {int(round(float(games)))} games."
                          if not pd.isna(games) else "")
            notes.append(
                f"{name} is listed {word} and is still on the board around pick "
                f"{pick} (round {rnd}).{games_text} That discount is the reason he "
                "is there; the rosters below price it in rather than ignore it.")
            if len(notes) >= limit:
                return notes

    fragile = available_at(scores, early[0][1], reach).nsmallest(
        max(4, len(early) * 4), "ADP") if early else scores.iloc[0:0]
    if not notes and not fragile.empty:
        count = int((fragile["AVAIL"] < FRAGILE_BELOW).sum())
        if count >= 2:
            notes.append(
                f"{count} of the players likely to reach your first pick are "
                "projected for well under a full season. Nobody is flagged today, "
                "but the games are already priced into the rosters below.")
    return notes
