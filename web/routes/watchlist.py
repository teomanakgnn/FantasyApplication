"""Izleme listesi."""
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from services.database import FREE_WATCHLIST_LIMIT, db
from utils.images import headshot_for_name
from web.core import current_user, is_pro, login_required, redirect, render

router = APIRouter()


@router.get("/watchlist")
def watchlist(request: Request, q: str = "", sort: str = "recent"):
    gate = login_required(request)
    if gate:
        return gate
    user = current_user(request)
    items = db.get_watchlist(user["id"])
    for item in items:
        item["photo"] = headshot_for_name(item["player_name"])
    if q:
        items = [i for i in items if q.lower() in i["player_name"].lower()]
    if sort == "name":
        items.sort(key=lambda i: i["player_name"].lower())
    elif sort == "notes":
        items.sort(key=lambda i: (not i.get("notes"), i["player_name"].lower()))
    return render(request, "watchlist.html", active="watchlist", items=items, q=q,
                  sort=sort, limit=FREE_WATCHLIST_LIMIT, total=db.watchlist_count(user["id"]),
                  now=datetime.now())


@router.post("/watchlist/add")
def add(request: Request, player: str = Form(""), notes: str = Form("")):
    user = current_user(request)
    if not user:
        return redirect("/login?next=/watchlist")
    name = player.strip()[:80]
    if not name:
        return redirect("/watchlist", "Enter a player name.", "error")
    if not is_pro(user) and db.watchlist_count(user["id"]) >= FREE_WATCHLIST_LIMIT:
        return redirect("/watchlist", f"Free accounts hold {FREE_WATCHLIST_LIMIT} players. "
                                      "Remove one to add another.", "error")
    if any(w["player_name"].lower() == name.lower() for w in db.get_watchlist(user["id"])):
        return redirect("/watchlist", f"{name} is already on your watchlist.", "info")
    if db.add_to_watchlist(user["id"], name, notes.strip()[:500]):
        return redirect("/watchlist", f"{name} added to your watchlist.")
    return redirect("/watchlist", "Could not add that player.", "error")


@router.post("/watchlist/{item_id}/notes")
def notes(request: Request, item_id: int, notes: str = Form("")):
    user = current_user(request)
    if not user:
        return redirect("/login?next=/watchlist")
    ok = db.update_watchlist_notes(item_id, notes.strip()[:500], user["id"])
    return redirect("/watchlist", "Notes saved." if ok else "Could not save notes.",
                    "ok" if ok else "error")


@router.post("/watchlist/{item_id}/remove")
def remove(request: Request, item_id: int):
    user = current_user(request)
    if not user:
        return redirect("/login?next=/watchlist")
    ok = db.remove_from_watchlist(item_id, user["id"])
    return redirect("/watchlist", "Player removed." if ok else "Could not remove that player.",
                    "ok" if ok else "error")


@router.post("/watchlist/clear")
def clear(request: Request):
    user = current_user(request)
    if not user:
        return redirect("/login?next=/watchlist")
    db.clear_watchlist(user["id"])
    return redirect("/watchlist", "Watchlist cleared.")


@router.get("/watchlist.csv")
def export(request: Request):
    user = current_user(request)
    if not user:
        return redirect("/login?next=/watchlist")
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["player", "notes", "added"])
    for w in db.get_watchlist(user["id"]):
        added = w.get("created_at")
        writer.writerow([w["player_name"], w.get("notes") or "",
                         added.strftime("%Y-%m-%d %H:%M") if added else ""])
    return Response(buffer.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="watchlist-{datetime.now():%Y%m%d}.csv"'})
