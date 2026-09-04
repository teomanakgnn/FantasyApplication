"""
Fantasy NBA mock draft motoru.

İki format destekler:
  - snake : sıra 1..N, N..1 şeklinde döner
  - auction : her takımın bütçesi vardır, oyuncular tek tek açık artırmaya çıkar

Rakipler iki modda olabilir:
  - ai     : sen bir takımı yönetirsin, diğerleri otomatik seçer
  - manual : bütün takımların seçimini sen yaparsın

Motor saf Python; Streamlit'e bağlı değil, bu yüzden test edilebilir.
Durum tek bir dict içinde tutulur ve JSON'a serileştirilebilir.
"""

import random
from datetime import datetime

# Doldurulması gereken kadro yapısı (sıra önem taşır - önce spesifik slotlar)
DEFAULT_ROSTER_SLOTS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL", "UTIL"]
DEFAULT_BENCH_SIZE = 4

# Hangi slotu hangi pozisyonlar doldurabilir
SLOT_ELIGIBILITY = {
    "PG": {"PG"},
    "SG": {"SG"},
    "SF": {"SF"},
    "PF": {"PF"},
    "C": {"C"},
    "G": {"PG", "SG"},
    "F": {"SF", "PF"},
    "UTIL": {"PG", "SG", "SF", "PF", "C"},
    "BENCH": {"PG", "SG", "SF", "PF", "C"},
}

AI_TEAM_NAMES = [
    "Pick & Rollers", "Dagger Threes", "Glass Cleaners", "Rim Runners",
    "Backdoor Cuts", "Full Court Press", "Triple Doubles", "Bench Mob",
    "Fast Break", "Paint Patrol", "Perimeter Kings", "Iso Ballers",
    "Zone Busters", "Transition Game", "Sixth Man Crew",
]


# --------------------------------------------------------------- kurulum

def create_draft(
    board,
    team_count=10,
    rounds=13,
    user_slot=1,
    fmt="snake",
    opponent_mode="ai",
    budget=200,
    ai_randomness=0.35,
    seed=None,
):
    """
    Yeni bir draft durumu oluşturur.

    Args:
        board: get_draft_board() çıktısı (DataFrame)
        team_count: takım sayısı
        rounds: tur sayısı (snake) / kadro büyüklüğü (auction)
        user_slot: kullanıcının draft pozisyonu (1 tabanlı)
        fmt: "snake" veya "auction"
        opponent_mode: "ai" veya "manual"
        budget: auction formatında takım başı bütçe
        ai_randomness: 0 = hep en iyi sıralı oyuncu, 1 = çok değişken
        seed: tekrarlanabilir draftlar için rastgelelik tohumu

    Returns:
        dict - draft durumu
    """
    if seed is None:
        seed = random.randrange(1_000_000)

    user_slot = max(1, min(int(user_slot), int(team_count)))

    teams = []
    rng = random.Random(seed)
    ai_names = AI_TEAM_NAMES[:]
    rng.shuffle(ai_names)

    for i in range(1, team_count + 1):
        is_user = (i == user_slot) and opponent_mode == "ai"
        teams.append({
            "slot": i,
            "name": "Senin Takımın" if is_user else (
                ai_names[(i - 1) % len(ai_names)] if opponent_mode == "ai" else f"Takım {i}"
            ),
            "is_user": is_user,
            "picks": [],           # [{player, round, pick, price}]
            "budget": budget,
            "spent": 0,
        })

    pool = _board_to_pool(board)

    state = {
        "format": fmt,
        "opponent_mode": opponent_mode,
        "team_count": team_count,
        "rounds": rounds,
        "user_slot": user_slot,
        "budget": budget,
        "ai_randomness": ai_randomness,
        "seed": seed,
        "teams": teams,
        "pool": pool,
        "drafted_ids": [],
        "pick_number": 1,          # 1 tabanlı genel sıra
        "log": [],
        "complete": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        # auction'a özel
        "nominating_slot": 1,
        "current_nomination": None,
    }
    return state


def _board_to_pool(board):
    """DataFrame'i motorun kullandığı sade sözlük listesine çevirir."""
    pool = []
    for _, row in board.iterrows():
        positions = row.get("POSITIONS")
        if not isinstance(positions, (list, tuple)):
            positions = [row.get("POS", "UTIL")]
        pool.append({
            "id": int(row["ESPN_ID"]) if row.get("ESPN_ID") is not None else None,
            "name": row["PLAYER"],
            "team": row.get("TEAM", "FA"),
            "pos": row.get("POS", "UTIL"),
            "positions": list(positions),
            "adp": int(row.get("ADP", 999)),
            "rank": int(row.get("RANK", 999)),
            "auction": int(row.get("AUCTION", 1)),
            "owned": float(row.get("OWNED", 0)),
            "injury": row.get("INJURY", "ACTIVE"),
            "fpts": float(row.get("FPTS", 0) or 0),
            "pts": float(row.get("PTS", 0) or 0),
            "reb": float(row.get("REB", 0) or 0),
            "ast": float(row.get("AST", 0) or 0),
            "stl": float(row.get("STL", 0) or 0),
            "blk": float(row.get("BLK", 0) or 0),
            "gp": float(row.get("GP", 0) or 0),
            "rookie": bool(row.get("ROOKIE", False)),
        })
    return pool


# --------------------------------------------------------------- sıra mantığı

def total_picks(state):
    return state["team_count"] * state["rounds"]


def pick_to_slot(state, pick_number):
    """Genel sıra numarasından hangi takımın seçeceğini bulur (snake)."""
    team_count = state["team_count"]
    index = pick_number - 1
    rnd = index // team_count
    position = index % team_count
    # Çift numaralı turlarda (1, 3, 5...) sıra tersine döner
    if rnd % 2 == 1:
        position = team_count - 1 - position
    return position + 1


def current_round(state):
    return (state["pick_number"] - 1) // state["team_count"] + 1


def pick_in_round(state):
    return (state["pick_number"] - 1) % state["team_count"] + 1


def current_team(state):
    """
    Sırası gelen takım.
    Snake'te seçim sırası, auction'da aday gösterme sırası geçerlidir.
    """
    if state["complete"]:
        return None
    if state["format"] == "auction":
        return _team_by_slot(state, state["nominating_slot"])
    slot = pick_to_slot(state, state["pick_number"])
    return _team_by_slot(state, slot)


def _team_by_slot(state, slot):
    for team in state["teams"]:
        if team["slot"] == slot:
            return team
    return None


def is_user_turn(state):
    """Kullanıcıdan bir aksiyon bekleniyor mu?"""
    if state["complete"]:
        return False
    if state["opponent_mode"] == "manual":
        return True
    if state["format"] == "auction":
        # Ya açık bir teklif kararı bekleniyordur ya da aday gösterme sırasıdır.
        if state.get("current_nomination"):
            return state["current_nomination"].get("awaiting_user", False)
        team = current_team(state)
        return bool(team and team["is_user"])
    team = current_team(state)
    return bool(team and team["is_user"])


def user_team(state):
    for team in state["teams"]:
        if team["is_user"]:
            return team
    return state["teams"][0] if state["teams"] else None


# --------------------------------------------------------------- kadro ihtiyacı

def roster_needs(team, rounds):
    """
    Takımın hâlâ boş olan kadro slotlarını döndürür.

    Doldurulmuş slotlar mevcut seçimlerden çıkarılır; kalan yerler
    yedek kabul edilir.
    """
    slots = DEFAULT_ROSTER_SLOTS[:]
    # Tur sayısı kadro yapısından fazlaysa gerisi yedektir.
    bench = max(0, rounds - len(slots))
    slots += ["BENCH"] * bench

    remaining = slots[:]
    for pick in team["picks"]:
        positions = set(pick["player"].get("positions") or [pick["player"].get("pos")])
        placed = False
        for i, slot in enumerate(remaining):
            if positions & SLOT_ELIGIBILITY.get(slot, set()):
                remaining.pop(i)
                placed = True
                break
        if not placed and remaining:
            remaining.pop()
    return remaining


def _need_bonus(player, needs):
    """
    Oyuncunun takımın açık ihtiyaçlarına ne kadar uyduğuna göre bonus.
    Spesifik slot (PG/C gibi) doldurmak, UTIL doldurmaktan değerlidir.
    """
    positions = set(player.get("positions") or [player.get("pos")])
    if not needs:
        return 0.0

    best = 0.0
    for slot in needs:
        if positions & SLOT_ELIGIBILITY.get(slot, set()):
            if slot in ("PG", "SG", "SF", "PF", "C"):
                best = max(best, 1.0)
            elif slot in ("G", "F"):
                best = max(best, 0.7)
            elif slot == "UTIL":
                best = max(best, 0.35)
            else:  # BENCH
                best = max(best, 0.15)
    return best


# --------------------------------------------------------------- yapay zekâ

def available_players(state):
    drafted = set(state["drafted_ids"])
    return [p for p in state["pool"] if p["id"] not in drafted]


def ai_choose(state, team, candidates=None):
    """
    Bir yapay zekâ takımının seçimini belirler.

    Mantık: sıralamaya (ADP) sadık kal ama kadro ihtiyacını ve biraz
    rastgeleliği hesaba kat. Gerçek mock draftlardaki gibi ara sıra
    "reach" ve "value pick" oluşur.
    """
    pool = candidates if candidates is not None else available_players(state)
    if not pool:
        return None

    needs = roster_needs(team, state["rounds"])
    rng = random.Random(state["seed"] * 7919 + state["pick_number"] * 104729 + team["slot"])

    # En iyi ~14 sıralı oyuncuya bak; hepsini puanla.
    window = sorted(pool, key=lambda p: p["adp"])[:14]
    best_adp = window[0]["adp"]

    scored = []
    for player in window:
        # ADP'den sapma cezası (sıra düştükçe puan azalır)
        score = 100.0 - (player["adp"] - best_adp) * 2.2
        # Kadro ihtiyacı bonusu
        score += _need_bonus(player, needs) * 12.0
        # Sakat oyuncuya küçük ceza
        if player["injury"] in ("OUT", "INJURY_RESERVE"):
            score -= 15.0
        elif player["injury"] == "DAY_TO_DAY":
            score -= 3.0
        # Rastgelelik - insan draftçıların öngörülemezliği
        score += rng.gauss(0, 10.0 * state["ai_randomness"])
        scored.append((score, player))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def max_affordable_bid(state, team):
    """
    Bir takımın verebileceği en yüksek teklif.
    Kalan her boş kadro yeri için 1$ ayrılır.
    """
    slots_left = state["rounds"] - len(team["picks"])
    if slots_left <= 0:
        return 0
    return max(0, team["budget"] - team["spent"] - (slots_left - 1))


def ai_bid(state, team, player):
    """
    Auction: bir yapay zekâ takımının bu oyuncuya vereceği maksimum fiyat.
    Bütçe, kalan kadro yeri ve oyuncunun değerine göre hesaplanır.
    """
    if is_roster_full(state, team):
        return 0

    ceiling = max_affordable_bid(state, team)
    if ceiling <= 0:
        return 0

    needs = roster_needs(team, state["rounds"])
    rng = random.Random(state["seed"] * 31 + team["slot"] * 977 + (player["adp"] or 0))
    value = player["auction"] or 1
    value *= 1 + _need_bonus(player, needs) * 0.25
    value *= 1 + rng.gauss(0, 0.12 * max(state["ai_randomness"], 0.1))

    return int(max(0, min(ceiling, round(value))))


# --------------------------------------------------------------- seçim yapma

def make_pick(state, player_id, price=None, buyer_slot=None):
    """
    Sıradaki takım için bir oyuncu seçer (snake) veya satın alır (auction).

    Args:
        player_id: seçilecek oyuncunun ESPN ID'si
        price: auction formatında ödenecek bedel
        buyer_slot: auction formatında alıcı takım (None ise aday gösteren)

    Returns:
        (ok: bool, message: str)
    """
    if state["complete"]:
        return False, "Draft zaten tamamlandı."

    player = next((p for p in state["pool"] if p["id"] == player_id), None)
    if player is None:
        return False, "Oyuncu havuzda bulunamadı."
    if player_id in state["drafted_ids"]:
        return False, f"{player['name']} zaten seçilmiş."

    if state["format"] == "auction":
        return _auction_purchase(state, player, price, buyer_slot)
    return _snake_pick(state, player)


def is_roster_full(state, team):
    """Takımın kadrosu dolu mu?"""
    return len(team["picks"]) >= state["rounds"]


def _snake_pick(state, player):
    team = current_team(state)
    if team is None:
        return False, "Sıradaki takım bulunamadı."

    team["picks"].append({
        "player": player,
        "round": current_round(state),
        "pick": pick_in_round(state),
        "overall": state["pick_number"],
        "price": None,
    })
    state["drafted_ids"].append(player["id"])
    state["log"].append({
        "overall": state["pick_number"],
        "round": current_round(state),
        "team": team["name"],
        "slot": team["slot"],
        "player": player["name"],
        "pos": player["pos"],
        "nba_team": player["team"],
        "adp": player["adp"],
        "price": None,
    })

    state["pick_number"] += 1
    if state["pick_number"] > total_picks(state):
        state["complete"] = True

    return True, f"{team['name']} → {player['name']}"


def _auction_purchase(state, player, price, buyer_slot=None):
    slot = buyer_slot or state.get("_pending_winner_slot") or state["nominating_slot"]
    state.pop("_pending_winner_slot", None)
    team = _team_by_slot(state, slot)

    if team is None:
        return False, "Alıcı takım bulunamadı."
    if is_roster_full(state, team):
        return False, f"{team['name']} kadrosu dolu ({state['rounds']} oyuncu)."

    price = max(1, int(price if price is not None else max(1, player["auction"])))

    # Kalan her boş yer için en az 1$ ayrılmalı.
    slots_left = state["rounds"] - len(team["picks"])
    remaining = team["budget"] - team["spent"]
    if price > remaining - (slots_left - 1):
        return False, (f"{team['name']} bu fiyatı karşılayamaz "
                       f"(kalan ${remaining}, doldurulacak {slots_left} yer).")

    team["picks"].append({
        "player": player,
        "round": len(team["picks"]) + 1,
        "pick": None,
        "overall": state["pick_number"],
        "price": price,
    })
    team["spent"] += price
    state["drafted_ids"].append(player["id"])
    state["log"].append({
        "overall": state["pick_number"],
        "round": len(team["picks"]),
        "team": team["name"],
        "slot": team["slot"],
        "player": player["name"],
        "pos": player["pos"],
        "nba_team": player["team"],
        "adp": player["adp"],
        "price": price,
    })

    state["pick_number"] += 1
    state["current_nomination"] = None
    _advance_nomination(state)

    if all(is_roster_full(state, t) for t in state["teams"]):
        state["complete"] = True

    return True, f"{team['name']} → {player['name']} (${price})"


def _advance_nomination(state):
    """
    Aday gösterme sırasını, kadrosu dolu olmayan bir sonraki takıma taşır.
    Bütün takımlar dolduysa draft biter.
    """
    count = state["team_count"]
    for _ in range(count):
        state["nominating_slot"] = state["nominating_slot"] % count + 1
        team = _team_by_slot(state, state["nominating_slot"])
        if team and not is_roster_full(state, team):
            return
    state["complete"] = True


def run_ai_until_user(state, max_picks=500):
    """
    Kullanıcının sırası gelene (veya draft bitene) kadar yapay zekâ
    takımlarının seçimlerini yapar.

    Returns:
        list - bu adımda yapılan seçimlerin log kayıtları
    """
    made = []
    if state["opponent_mode"] == "manual":
        return made

    guard = 0
    while not state["complete"] and not is_user_turn(state) and guard < max_picks:
        guard += 1
        entry = step_ai_once(state)
        if entry is None:
            break
        made.append(entry)

    state["last_ai_picks"] = made
    return made


def step_ai_once(state):
    """
    Tek bir yapay zekâ aksiyonu yapar (bir seçim ya da bir açık artırmanın
    sonuçlanması). Canlı akış için adım adım çağrılabilir.

    Returns:
        dict - log kaydı, aksiyon yapılamadıysa None.
        Kullanıcının kararı bekleniyorsa da None döner.
    """
    if state["complete"] or state["opponent_mode"] == "manual":
        return None
    if is_user_turn(state):
        return None

    team = current_team(state)
    if team is None:
        return None

    if state["format"] == "auction":
        # Kapanmayı bekleyen bir açık artırma varsa önce onu bitir.
        if state.get("current_nomination"):
            ok, _ = finalize_nomination(state)
        else:
            player = ai_choose(state, team)
            if player is None:
                return None
            ok, _ = nominate(state, player["id"])
            if not ok:
                return None
            if is_user_turn(state):
                # Kullanıcının teklif kararı bekleniyor - seçim tamamlanmadı.
                return None
            ok, _ = finalize_nomination(state)
        if not ok:
            return None
    else:
        player = ai_choose(state, team)
        if player is None:
            return None
        ok, _ = _snake_pick(state, player)
        if not ok:
            return None

    return state["log"][-1]


# --------------------------------------------------------------- auction akışı
#
# Akış: bir takım oyuncu aday gösterir -> yapay zekâlar teklif verir ->
# kullanıcı isterse üste çıkar -> yapay zekâlar cevap verir -> kimse
# artırmayınca oyuncu en yüksek teklifi verene satılır.


def nominate(state, player_id):
    """
    Sıradaki takım bir oyuncuyu açık artırmaya çıkarır ve yapay zekâlar
    ilk tekliflerini verir.

    Returns:
        (ok, message)
    """
    if state["format"] != "auction":
        return False, "Bu format açık artırma değil."
    if state["complete"]:
        return False, "Draft tamamlandı."
    if state.get("current_nomination"):
        return False, "Devam eden bir açık artırma var."

    player = next((p for p in state["pool"] if p["id"] == player_id), None)
    if player is None:
        return False, "Oyuncu havuzda bulunamadı."
    if player_id in state["drafted_ids"]:
        return False, f"{player['name']} zaten seçilmiş."

    state["current_nomination"] = {
        "player_id": player_id,
        "player": player,
        "nominator_slot": state["nominating_slot"],
        "high_bid": 1,
        "high_slot": state["nominating_slot"],
        "awaiting_user": False,
        "history": [],
    }
    _run_ai_bidding(state)
    return True, f"{player['name']} açık artırmada"


def _run_ai_bidding(state):
    """
    Yapay zekâların açık artırmaya cevabını çözer.

    Yükselen açık artırma tek adımda sonuçlandırılır: en yüksek tavana
    sahip takım kazanır, fiyat ikinci en yüksek tavanın bir üstünde kalır.
    Böylece kazanan tavanını ifşa etmez - gerçek artırmadaki davranış.
    """
    nom = state["current_nomination"]
    if not nom:
        return

    player = nom["player"]

    # Her yapay zekâ takımının bu oyuncu için tavanı
    ceilings = []
    for team in state["teams"]:
        if team["is_user"] or is_roster_full(state, team):
            continue
        ceiling = ai_bid(state, team, player)
        if ceiling > 0:
            ceilings.append((ceiling, team["slot"]))

    ceilings.sort(reverse=True)

    if ceilings:
        top_ceiling, top_slot = ceilings[0]
        runner_up = ceilings[1][0] if len(ceilings) > 1 else 0

        # Yapay zekâ ancak mevcut teklifi geçebiliyorsa devreye girer.
        if top_ceiling > nom["high_bid"]:
            new_bid = min(top_ceiling, max(runner_up, nom["high_bid"]) + 1)
            if new_bid > nom["high_bid"]:
                nom["high_bid"] = new_bid
                nom["high_slot"] = top_slot
                nom["history"].append({
                    "slot": top_slot,
                    "team": _team_by_slot(state, top_slot)["name"],
                    "bid": new_bid,
                })

    # Kullanıcı üste çıkabilir mi?
    user = user_team(state)
    if state["opponent_mode"] == "ai" and user and not is_roster_full(state, user):
        can_outbid = max_affordable_bid(state, user) > nom["high_bid"]
        nom["awaiting_user"] = bool(can_outbid and nom["high_slot"] != user["slot"])
    else:
        nom["awaiting_user"] = False


def user_bid(state, amount):
    """Kullanıcı mevcut teklifin üstüne çıkar; ardından yapay zekâlar cevap verir."""
    nom = state.get("current_nomination")
    if not nom:
        return False, "Devam eden bir açık artırma yok."

    user = user_team(state)
    if user is None:
        return False, "Kullanıcı takımı yok."
    if is_roster_full(state, user):
        return False, "Kadron dolu."

    amount = int(amount)
    if amount <= nom["high_bid"]:
        return False, f"Teklif en az ${nom['high_bid'] + 1} olmalı."

    ceiling = max_affordable_bid(state, user)
    if amount > ceiling:
        return False, f"En fazla ${ceiling} teklif verebilirsin (kalan yerler için 1$ ayrılıyor)."

    nom["high_bid"] = amount
    nom["high_slot"] = user["slot"]
    nom["history"].append({"slot": user["slot"], "team": user["name"], "bid": amount})

    _run_ai_bidding(state)
    return True, f"${amount} teklif verildi."


def user_pass(state):
    """Kullanıcı bu oyuncudan çekilir; açık artırma sonuçlanır."""
    nom = state.get("current_nomination")
    if not nom:
        return False, "Devam eden bir açık artırma yok."
    nom["awaiting_user"] = False
    return finalize_nomination(state)


def finalize_nomination(state):
    """Açık artırmayı kapatır ve oyuncuyu en yüksek teklifi verene satar."""
    nom = state.get("current_nomination")
    if not nom:
        return False, "Devam eden bir açık artırma yok."
    if nom.get("awaiting_user"):
        return False, "Önce teklif ver veya pas geç."

    return _auction_purchase(state, nom["player"], nom["high_bid"], nom["high_slot"])


# --------------------------------------------------------------- değerlendirme

def team_summary(state, team):
    """Bir takımın kadro toplamlarını ve fantasy puanını çıkarır."""
    players = [p["player"] for p in team["picks"]]
    if not players:
        return {
            "players": 0, "fpts": 0.0, "pts": 0.0, "reb": 0.0,
            "ast": 0.0, "stl": 0.0, "blk": 0.0,
            "positions": {}, "spent": team["spent"],
            "remaining": team["budget"] - team["spent"],
        }

    positions = {}
    for p in players:
        positions[p["pos"]] = positions.get(p["pos"], 0) + 1

    return {
        "players": len(players),
        "fpts": round(sum(p["fpts"] for p in players), 1),
        "pts": round(sum(p["pts"] for p in players), 1),
        "reb": round(sum(p["reb"] for p in players), 1),
        "ast": round(sum(p["ast"] for p in players), 1),
        "stl": round(sum(p["stl"] for p in players), 1),
        "blk": round(sum(p["blk"] for p in players), 1),
        "positions": positions,
        "spent": team["spent"],
        "remaining": team["budget"] - team["spent"],
    }


def grade_draft(state):
    """
    Her takıma toplam fantasy puanına göre harf notu verir.
    Lig ortalamasına göre bağıl notlama yapılır.
    """
    summaries = [(t, team_summary(state, t)) for t in state["teams"]]
    totals = [s["fpts"] for _, s in summaries]
    if not totals or max(totals) == 0:
        return {t["slot"]: {"grade": "-", "fpts": 0.0, "rank": i + 1}
                for i, (t, _) in enumerate(summaries)}

    average = sum(totals) / len(totals)
    spread = max(max(totals) - average, average - min(totals), 1e-6)

    ranked = sorted(summaries, key=lambda x: x[1]["fpts"], reverse=True)
    rank_by_slot = {t["slot"]: i + 1 for i, (t, _) in enumerate(ranked)}

    grades = {}
    for team, summary in summaries:
        # Ortalamadan sapmayı -1..+1 aralığına indir
        delta = (summary["fpts"] - average) / spread
        if delta >= 0.6:
            grade = "A+"
        elif delta >= 0.35:
            grade = "A"
        elif delta >= 0.15:
            grade = "B+"
        elif delta >= -0.05:
            grade = "B"
        elif delta >= -0.25:
            grade = "C+"
        elif delta >= -0.5:
            grade = "C"
        else:
            grade = "D"
        grades[team["slot"]] = {
            "grade": grade,
            "fpts": summary["fpts"],
            "rank": rank_by_slot[team["slot"]],
        }
    return grades


def draft_board_grid(state):
    """
    Klasik draft board'u üretir: satırlar tur, sütunlar takım.

    Returns:
        (takım_başlıkları, satırlar) - her hücre None ya da
        {player, pos, nba_team, adp, price, overall, is_user}
    """
    headers = [{"name": t["name"], "slot": t["slot"], "is_user": t["is_user"]}
               for t in state["teams"]]

    # Auction'da tur kavramı yok; her takımın aldığı sırayla dizilir.
    by_slot = {t["slot"]: t["picks"] for t in state["teams"]}
    max_rows = max((len(p) for p in by_slot.values()), default=0)
    if state["format"] != "auction":
        max_rows = state["rounds"]

    rows = []
    for r in range(max_rows):
        row = []
        for team in state["teams"]:
            picks = by_slot.get(team["slot"], [])
            if r < len(picks):
                pick = picks[r]
                player = pick["player"]
                row.append({
                    "player": player["name"],
                    "pos": player["pos"],
                    "nba_team": player["team"],
                    "adp": player["adp"],
                    "price": pick["price"],
                    "overall": pick["overall"],
                    "is_user": team["is_user"],
                })
            else:
                row.append(None)
        rows.append(row)

    return headers, rows


def best_available(state, position=None, limit=10):
    """Sıradaki en iyi mevcut oyuncular; istenirse pozisyona göre süzülür."""
    pool = available_players(state)
    if position and position != "TÜMÜ":
        pool = [p for p in pool if position in (p.get("positions") or [p["pos"]])]
    return sorted(pool, key=lambda p: p["adp"])[:limit]


def upcoming_picks(state, count=5):
    """Sıradaki birkaç seçimin hangi takıma ait olduğunu döndürür."""
    if state["complete"] or state["format"] == "auction":
        return []
    result = []
    total = total_picks(state)
    for n in range(state["pick_number"], min(state["pick_number"] + count, total + 1)):
        slot = pick_to_slot(state, n)
        team = _team_by_slot(state, slot)
        result.append({
            "overall": n,
            "round": (n - 1) // state["team_count"] + 1,
            "team": team["name"] if team else f"Takım {slot}",
            "is_user": bool(team and team["is_user"]),
        })
    return result


def picks_until_user_turn(state):
    """Kullanıcının sırasına kaç seçim kaldığı (snake)."""
    if state["complete"] or state["opponent_mode"] == "manual":
        return 0
    total = total_picks(state)
    for n in range(state["pick_number"], total + 1):
        if pick_to_slot(state, n) == state["user_slot"]:
            return n - state["pick_number"]
    return 0


# --------------------------------------------------------------- serileştirme

def serialize(state):
    """
    Durumu veritabanına yazmak için sadeleştirir.
    Havuzun tamamı yerine sadece seçilenler saklanır.
    """
    return {
        "format": state["format"],
        "opponent_mode": state["opponent_mode"],
        "team_count": state["team_count"],
        "rounds": state["rounds"],
        "user_slot": state["user_slot"],
        "budget": state["budget"],
        "ai_randomness": state["ai_randomness"],
        "seed": state["seed"],
        "created_at": state["created_at"],
        "complete": state["complete"],
        "pick_number": state["pick_number"],
        "nominating_slot": state.get("nominating_slot", 1),
        "log": state["log"],
        "teams": [
            {
                "slot": t["slot"],
                "name": t["name"],
                "is_user": t["is_user"],
                "budget": t["budget"],
                "spent": t["spent"],
                "picks": [
                    {
                        "round": p["round"],
                        "pick": p["pick"],
                        "overall": p["overall"],
                        "price": p["price"],
                        "player": p["player"],
                    }
                    for p in t["picks"]
                ],
            }
            for t in state["teams"]
        ],
    }


def deserialize(saved, board=None):
    """
    serialize() çıktısını tekrar oynanabilir bir duruma çevirir.

    board verilirse havuz yeniden kurulur (draft'a devam edilebilir);
    verilmezse sadece görüntüleme için yeterli bir durum döner.
    """
    state = dict(saved)
    state["pool"] = _board_to_pool(board) if board is not None else []
    state["drafted_ids"] = [
        p["player"]["id"]
        for t in saved.get("teams", [])
        for p in t.get("picks", [])
        if p.get("player", {}).get("id") is not None
    ]
    state.setdefault("current_nomination", None)
    state.setdefault("nominating_slot", 1)
    return state
