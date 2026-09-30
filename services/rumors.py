"""
Takas soylentileri: RSS kaynaklari ve ESPN haber ucu.

Eski surumde kaynaklar bos donunce uydurma uc soylenti ("Mock Data")
gercekmis gibi gosteriliyordu; artik bos liste donuyor ve sayfa bunu
acikca soyluyor. Reddit anonim erisimi 2023'ten beri kapali (her istek
403), o yuzden kaynak listesinden cikarildi.
"""
from datetime import datetime, timezone

import feedparser
import requests

from services.cache import cache_data

NBA_TEAMS = [
    "Hawks", "Celtics", "Nets", "Hornets", "Bulls", "Cavaliers", "Mavericks", "Nuggets",
    "Pistons", "Warriors", "Rockets", "Pacers", "Clippers", "Lakers", "Grizzlies", "Heat",
    "Bucks", "Timberwolves", "Pelicans", "Knicks", "Thunder", "Magic", "76ers", "Suns",
    "Blazers", "Kings", "Spurs", "Raptors", "Jazz", "Wizards",
]
TRADE_WORDS = ["trade", "traded", "trading", "deal", "acquire", "acquired", "sign", "signed",
               "signing", "rumor", "rumors", "interest", "interested", "pursuing", "target",
               "available", "shopping", "waive", "waived", "release", "released", "buyout",
               "extension", "free agent"]
EXCLUDE = ["injury report", "game preview", "game recap", "highlights", "fantasy", "prop bet",
           "betting", "odds", "prediction", "starting lineup", "final score"]
FEEDS = [
    ("https://www.cbssports.com/rss/headlines/nba/", "CBS Sports"),
    ("https://basketball.realgm.com/rss/wiretap/0/0.xml", "RealGM"),
    ("https://sports.yahoo.com/nba/rss.xml", "Yahoo Sports"),
    ("https://clutchpoints.com/feed", "ClutchPoints"),
]


def _likelihood(text):
    if any(k in text for k in ("official", "confirmed", "agreed", "done deal", "finalizing", "completed")):
        return "High", 4
    if any(k in text for k in ("close to", "nearing", "likely", "expected", "imminent")):
        return "Medium-High", 3
    if any(k in text for k in ("monitoring", "considering", "could", "might", "potential", "exploring")):
        return "Low", 1
    return "Medium", 2


def _item(title, summary, source, published):
    text = f"{title} {summary}".lower()
    if any(x in text for x in EXCLUDE) or not any(k in text for k in TRADE_WORDS):
        return None
    teams = [t for t in NBA_TEAMS if t.lower() in text]
    if not teams:
        return None
    days = (datetime.now(timezone.utc) - published).days if published else 0
    if days > 7:
        return None
    likelihood, confidence = _likelihood(text)
    import re
    clean = re.sub(r"<[^>]+>", "", summary or "").strip()
    return {"title": title.strip(), "content": clean[:350], "source": source, "days_ago": days,
            "date": published.strftime("%b %d, %Y") if published else "Recent",
            "teams": teams, "likelihood": likelihood, "confidence": confidence}


@cache_data(ttl=1800, show_spinner=False)
def trade_rumors(limit=15):
    out = []
    for url, source in FEEDS:
        try:
            resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0 HoopLife"})
            feed = feedparser.parse(resp.content)
        except Exception:
            continue
        for entry in feed.entries[:10]:
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                published = None
            item = _item(entry.get("title", ""), entry.get("summary", ""), source, published)
            if item:
                item["link"] = entry.get("link")
                out.append(item)
    try:
        data = requests.get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news",
                            timeout=8).json()
        for article in data.get("articles", [])[:15]:
            try:
                published = datetime.fromisoformat(article.get("published", "").replace("Z", "+00:00"))
            except ValueError:
                published = None
            item = _item(article.get("headline", ""), article.get("description", ""), "ESPN", published)
            if item:
                item["link"] = ((article.get("links") or {}).get("web") or {}).get("href")
                out.append(item)
    except Exception:
        pass
    seen, unique = set(), []
    for item in out:
        key = item["title"].lower()[:40]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    unique.sort(key=lambda r: (-r["confidence"], r["days_ago"]))
    return unique[:limit]
