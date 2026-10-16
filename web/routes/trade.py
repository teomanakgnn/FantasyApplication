"""
Trade Analyzer: kategori liglerinde (9-cat / 8-cat) ve puan liglerinde
takas degerlendirmesi.

Eski surum iki tarafi "oyuncu basi fantasy puani ortalamasi" ile
karsilastiriyordu: 2'ye 1 takasta bos kalan kadro yerini hic saymiyor,
kategori liginde yanlis olcuyu kullaniyor, yuzdelerde hacmi yok
sayiyordu. Simdi:

  * Deger = 9 kategori z-skoru (yuzdeler hacim agirlikli), punt edilen
    kategoriler haric; puan liginde ESPN varsayilan puanlamasi.
  * Kadro yeri: az oyuncu alan tarafa, bosalan her yer icin serbest
    oyuncu havuzundan "yedek seviyesi" bir oyuncu eklenir (standart yontem).
  * Istenirse sakatlik riski (projeksiyonda beklenen mac payi).
  * Kategori kategori net etki ve otomatik yorum.

Hesap tarayicida (static/js/trade.js); sunucu oyuncu tablosunu verir.
"""
from datetime import datetime

from fastapi import APIRouter, Request

from services.nba_season import get_current_season_year, get_season_start_date
from services.trade_values import BASES, players
from web.core import render

router = APIRouter()


def _available_bases():
    """Sezon baslamadan 'bu sezon' ve 'son 15/30 gun' anlamsiz (hazirlik maclari)."""
    try:
        started = datetime.now() >= get_season_start_date(get_current_season_year())
    except Exception:
        started = True
    keys = ["proj", "season", "30", "15", "last"] if started else ["proj", "last"]
    return {k: BASES[k] for k in keys}


@router.get("/trade-analyzer")
def trade(request: Request, basis: str = "proj"):
    bases = _available_bases()
    if basis not in bases:
        basis = "proj"
    rows = players(basis)
    return render(request, "trade.html", active="trade", basis=basis, bases=bases, players=rows)
