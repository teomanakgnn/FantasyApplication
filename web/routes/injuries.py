"""Sakatlik raporu. Filtreleme tarayicida; sunucu listeyi bir kez verir."""
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from services.espn_api import get_injuries
from web.core import redirect, render

router = APIRouter()


def _age(value):
    if not value:
        return None, "Date unknown"
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, "Date unknown"
    diff = datetime.now(timezone.utc) - when
    hours = diff.total_seconds() / 3600
    if hours < 1:
        text = f"{max(1, int(diff.total_seconds() // 60))}m ago"
    elif hours < 24:
        text = f"{int(hours)}h ago"
    elif diff.days == 1:
        text = "Yesterday"
    elif diff.days < 7:
        text = f"{diff.days}d ago"
    else:
        text = when.strftime("%b %d, %Y")
    return when.timestamp(), text


def _kind(status):
    s = (status or "").lower()
    if "out" in s:
        return "out"
    if "doubt" in s:
        return "doubtful"
    if "question" in s:
        return "questionable"
    if "day" in s:
        return "dtd"
    return "other"


@router.get("/injuries")
def injuries(request: Request):
    items = []
    for i in get_injuries() or []:
        ts, age = _age(i.get("date"))
        items.append({**i, "ts": ts or 0, "age": age, "kind": _kind(i.get("status")),
                      "recent": bool(ts and datetime.now(timezone.utc).timestamp() - ts < 86400)})
    items.sort(key=lambda x: -x["ts"])
    teams = sorted({(i["team"], i["team_name"], i["team_logo"]) for i in items})
    statuses = sorted({i["status"] for i in items})
    return render(request, "injuries.html", active="injuries", items=items, teams=teams,
                  statuses=statuses, today=datetime.now())


@router.post("/injuries/refresh")
def refresh(request: Request):
    get_injuries.clear()
    return redirect("/injuries", "Injury report refreshed.")
