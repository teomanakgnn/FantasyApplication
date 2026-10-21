"""Plan metinleri: neyin ucretsiz, neyin Pro oldugu tek yerde."""
from services.database import FREE_WATCHLIST_LIMIT

# Yukseltme akisi yok: Pro'yu simdilik yonetici eliyle veriyoruz.
UPGRADE_NOTE = "Pro is currently invite-only while we finish the season rollout."

PRO_FEATURES = [
    ("Unlimited watchlist", f"Free accounts track up to {FREE_WATCHLIST_LIMIT} players."),
    ("Player trends", "Rolling form and trade rumour tracking."),
    ("Extra punt builds", "Punt points, assists, rebounds or threes on the stats page."),
]
