"""
Hayat Acik Artirmasi: NBA Auction'in gunluk hayat surumu (yalnizca admin lobisi, davetle katilim).

Teklif kurallari services/auction.py'den gelir; burada yalnizca havuz, gizli puanlar ve sonuc var.
Her temada her seyin gizli bir puani (0-100) vardir, oyun bitince acilir. Bes alimin ortalamasi
yuksek olan kazanir; esitse artan para.
"""
import random

from services import auction

LOTS = 12
MAX_PER_THEME_MIX = 2

# (anahtar, ad, tekil kategori adi, puanin olcutu, "ad puan" listesi)
_RAW = (
    ("tatli", "Tatlılar", "Bir tatlı", "Ne kadar lezzetli",
     "Baklava 95, Künefe 94, Dondurma 91, Tiramisu 90, Sufle 88, Cheesecake 89, Kadayıf 87, Brownie 86, Waffle 85, "
     "Profiterol 84, Trileçe 83, Sütlaç 82, Lokma 81, Kazandibi 80, Magnolia 79, Güllaç 76, Makaron 74, Supangle 73, "
     "Tavuk göğsü 72, Kalburabastı 70, Lokum 68, Revani 66, Aşure 60, Helva 58"),
    ("ulke", "Ülkeler", "Bir ülke", "Orada yaşamak ne kadar güzel olurdu",
     "İsviçre 93, Japonya 92, İtalya 91, Norveç 90, Danimarka 89, İspanya 89, Yeni Zelanda 88, Avustralya 87, "
     "Kanada 86, Hollanda 85, Portekiz 84, Fransa 84, Almanya 83, Güney Kore 83, Türkiye 82, ABD 81, Yunanistan 80, "
     "İzlanda 79, Tayland 76, Brezilya 74, Arjantin 73, Meksika 72, Mısır 62, Rusya 60"),
    ("tatil", "Tatil yerleri", "Bir tatil yeri", "Tatil olarak ne kadar unutulmaz",
     "Maldivler 94, Santorini 92, Tokyo 91, Bali 90, İsviçre Alpleri 90, Roma 89, Paris 88, Venedik 88, Barselona 87, "
     "New York 86, İzlanda 86, Kapadokya 85, Kaş 84, Prag 84, Amsterdam 83, Phuket 83, Bodrum 82, Londra 81, "
     "Viyana 80, Antalya 80, Rio de Janeiro 79, Dubai 78, Kahire 77, Marakeş 75"),
    ("yemek", "Yemekler", "Bir yemek", "Ne kadar lezzetli",
     "İskender 93, Döner 92, Adana kebap 91, Pizza 91, Mantı 90, Biftek 90, Lahmacun 88, Sushi 87, Hünkar beğendi 87, "
     "Hamburger 86, Carbonara 86, İçli köfte 86, Kuru fasulye pilav 85, Ramen 85, Pide 85, Karnıyarık 84, Menemen 84, "
     "Sarma 83, Tavuk şiş 82, Paella 81, Taco 80, Kokoreç 79, Mercimek çorbası 78, Balık ekmek 77"),
    ("kahvalti", "Kahvaltılık", "Bir kahvaltılık", "Kahvaltı sofrasında ne kadar vazgeçilmez",
     "Bal kaymak 94, Sucuklu yumurta 92, Menemen 91, Simit 90, Sigara böreği 88, Gözleme 87, Pankek 86, "
     "Beyaz peynir 85, Zeytin 84, Kaşarlı tost 84, Çılbır 83, Poğaça 82, Pişi 85, Avokado tost 78, Omlet 80, "
     "Domates salatalık 76, Tereyağı reçel 81, Nutella 83, Kruvasan 82, Granola 66, Haşlanmış yumurta 72, "
     "Lor peyniri 62, Mısır gevreği 64, Sosis 74"),
    ("icecek", "İçecekler", "Bir içecek", "Ne kadar keyif verir",
     "Çay 92, Taze portakal suyu 89, Türk kahvesi 88, Latte 87, Sıcak çikolata 86, Buzlu kahve 86, Limonata 85, "
     "Milkshake 85, Ayran 84, Salep 83, Filtre kahve 80, Smoothie 80, Ice tea 79, Kola 78, Bubble tea 76, "
     "Matcha 72, Boza 66, Şalgam 64, Kefir 63, Soda 62"),
    ("meyve", "Meyveler", "Bir meyve", "Ne kadar lezzetli",
     "Karpuz 94, Kiraz 93, Çilek 92, Mango 91, Şeftali 88, Ananas 87, Üzüm 85, İncir 84, Mandalina 84, Portakal 83, "
     "Muz 82, Dut 82, Yaban mersini 81, Kayısı 80, Böğürtlen 80, Nar 79, Elma 78, Kivi 76, Erik 75, Armut 74, "
     "Avokado 72, Hurma 70, Ayva 60"),
    ("atistirmalik", "Atıştırmalıklar", "Bir atıştırmalık", "Film gecesinde ne kadar iyi gider",
     "Patlamış mısır 94, Çikolata 93, Cips 91, Nachos 88, Kurabiye 86, Çekirdek 85, Karışık kuruyemiş 84, Gofret 83, "
     "Jelibon 80, Antep fıstığı 87, Kraker 74, Leblebi 68, Pringles 85, Bisküvi 76, Pişmaniye 72, Mısır cipsi 82, "
     "Kuru meyve 65, Pirinç patlağı 52, Simit 79, Kumpir 81"),
    ("hayvan", "Evcil hayvanlar", "Bir evcil hayvan", "Evde beslemek ne kadar güzel olurdu",
     "Köpek 94, Kedi 93, At 82, Alpaka 80, Tavşan 78, Papağan 75, Chinchilla 74, Mini domuz 73, Kirpi 72, "
     "Muhabbet kuşu 71, Hamster 70, Sincap 69, Gelincik 68, Kaplumbağa 66, Kanarya 65, Tilki 64, Baykuş 62, "
     "Ördek 61, Balık 60, Keçi 58, Iguana 55, Yılan 45, Tarantula 35"),
    ("guc", "Süper güçler", "Bir süper güç", "Gerçek hayatta ne kadar işe yarardı",
     "Işınlanma 95, Zamanı durdurmak 94, Uçmak 93, Zamanda yolculuk 92, İyileştirme 88, Telekinezi 86, "
     "Görünmezlik 85, Her dili konuşmak 84, Süper hız 84, Şekil değiştirme 83, Zihin okuma 82, Geleceği görmek 81, "
     "Ölümsüzlük 80, Hava kontrolü 79, Süper güç 78, Kopyalanma 77, Hayvanlarla konuşmak 76, Hiç uyumamak 74, "
     "Su altında nefes almak 70, Gece görüşü 60"),
    ("araba", "Arabalar", "Bir araba", "Garajında olsa ne kadar mutlu ederdi",
     "Bugatti Chiron 96, Rolls-Royce 95, Ferrari 94, Lamborghini 93, Porsche 911 92, Aston Martin 92, Bentley 91, "
     "Mercedes G-Class 90, Range Rover 88, BMW M3 87, Audi RS6 86, Ford Mustang 85, Tesla Model S 85, Volvo XC90 82, "
     "Jeep Wrangler 80, Mini Cooper 78, Vosvos 74, Togg 72, Toyota Corolla 65, Renault Clio 62, Tofaş Şahin 60, "
     "Fiat Doblo 50"),
    ("meslek", "Meslekler", "Bir meslek", "Hayal mesleği olarak ne kadar güzel",
     "Pilot 90, Astronot 89, Gezgin içerik üreticisi 88, Mimar 85, Şef 84, Veteriner 86, Doktor 83, Yazılımcı 82, "
     "Fotoğrafçı 81, Aktör 87, Futbolcu 88, Pastacı 80, Dalış eğitmeni 79, Arkeolog 78, Psikolog 77, Diplomat 80, "
     "DJ 76, Öğretmen 75, Avukat 72, Muhasebeci 55, Banka memuru 58, Çağrı merkezi 40"),
    ("randevu", "Randevu fikirleri", "Bir randevu fikri", "Birlikte ne kadar güzel bir gün olurdu",
     "Kapadokya balon turu 96, Sahilde gün batımı 93, Tekne turu 92, Yıldız izlemek 91, Konser 90, Kamp 88, "
     "Evde film gecesi 89, Piknik 87, Spa günü 86, Şık restoran 85, Lunapark 84, Kayak 83, Kaçış odası 82, "
     "Yemek kursu 81, Karaoke 80, Sinema 79, Bowling 77, Paten 75, Müze 74, Alışveriş 70"),
)

THEMES = {}
ITEMS = []          # {"id", "name", "theme", "score"}
for key, label, one, q, raw in _RAW:
    ids = []
    for part in raw.split(","):
        name, score = part.strip().rsplit(" ", 1)
        ids.append(len(ITEMS))
        ITEMS.append({"id": len(ITEMS), "name": name, "theme": key, "score": int(score)})
    THEMES[key] = {"key": key, "label": label, "one": one, "q": q, "ids": ids,
                   "mean": sum(ITEMS[i]["score"] for i in ids) / len(ids)}
MIX = "karisik"


def theme_list():
    return [{"key": t["key"], "label": t["label"]} for t in THEMES.values()] + [{"key": MIX, "label": "Karışık"}]


def valid_theme(key):
    return key if key in THEMES or key == MIX else MIX


def card(iid):
    """Istemciye giden bilgi: puan yok."""
    it = ITEMS[iid]
    t = THEMES[it["theme"]]
    return {"id": iid, "name": it["name"], "theme": t["label"], "q": t["q"]}


def build_lots(rng, theme):
    if theme in THEMES:
        return rng.sample(THEMES[theme]["ids"], LOTS)
    keys = list(THEMES)
    picks, used = [], {}
    while len(picks) < LOTS:
        k = rng.choice(keys)
        if used.get(k, 0) >= MAX_PER_THEME_MIX:
            continue
        iid = rng.choice(THEMES[k]["ids"])
        if iid in picks:
            continue
        used[k] = used.get(k, 0) + 1
        picks.append(iid)
    return picks


def new_game(seed=None, opener=0, theme=MIX, blind=False):
    rng = random.Random(seed)
    theme = valid_theme(theme)
    blind = bool(blind) and theme == MIX          # tek temada kor oyun anlamsiz
    lots = build_lots(rng, theme)
    themes = [THEMES[ITEMS[i]["theme"]] for i in lots]
    g = {"lots": lots, "labels": [t["one"] for t in themes] if blind else None,
         "means": [t["mean"] for t in themes] if blind else None,
         "lot_names": [ITEMS[i]["name"] for i in lots], "lot_scores": [ITEMS[i]["score"] for i in lots],
         "life": True, "theme": theme, "blind": blind, "scoring": "life", "i": 0, "bid": 0, "bidder": None,
         "opener": opener, "turn": opener,
         "seats": [{"money": auction.START_MONEY, "roster": []}, {"money": auction.START_MONEY, "roster": []}],
         "over": False, "events": []}
    auction._settle_turn(g)
    return g


def score_team(roster):
    rows = []
    for x in roster:
        it = ITEMS[x["id"]]
        rows.append({"id": it["id"], "name": it["name"], "theme": THEMES[it["theme"]]["label"],
                     "score": it["score"], "price": x["price"]})
    rows.sort(key=lambda r: -r["score"])
    total = sum(r["score"] for r in rows) / auction.ROSTER
    return {"lineup": rows, "total": round(total, 1)}


def _verdict(teams, winner):
    a, b = teams
    buys = [(r["score"] / r["price"], r, i) for i, t in enumerate(teams) for r in t["lineup"]]
    best = max(buys, key=lambda x: (x[0], x[1]["score"]))
    worst = min((x for x in buys if x[1]["price"] >= 3), key=lambda x: x[0], default=None)
    if winner is None:
        text = f"Berabere: ikiniz de {a['total']:.1f} ortalama yaptınız."
    else:
        w, l = teams[winner], teams[1 - winner]
        name = "Team A" if winner == 0 else "Team B"
        text = f"Ortalama {w['total']:.1f}, karşısında {l['total']:.1f}."
        if w["total"] == l["total"]:
            text = f"Ortalama eşit ({w['total']:.1f}), {name} daha çok para biriktirdiği için kazandı."
    seat = "Team A" if best[2] == 0 else "Team B"
    text += f" Günün kapışı: {seat}, {best[1]['name']} ({best[1]['score']}) için yalnızca ${best[1]['price']} ödedi."
    if worst and worst[1]["score"] < 80:
        seat = "Team A" if worst[2] == 0 else "Team B"
        text += f" En pahalı hayal kırıklığı: {seat}, {worst[1]['name']} ({worst[1]['score']}) için ${worst[1]['price']} verdi."
    return text


def result(g):
    teams = []
    for s in g["seats"]:
        t = score_team(s["roster"])
        t["money_left"] = s["money"]
        teams.append(t)
    res = auction.decide({"teams": teams, "by": "life"})
    res["verdict"] = _verdict(teams, res["winner"])
    return res
