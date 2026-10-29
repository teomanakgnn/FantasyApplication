"""
Mac rotasyonu: hangi oyuncu hangi ceyrekte hangi dakikalarda sahadaydi.

Kaynak ESPN oyun-oyun kaydi (summary "plays"): "X enters the game for Y"
degisiklikleri. ESPN ceyrek basindaki degisiklikleri cogu zaman yazmaz; bu
yuzden her ceyregin ilk besi cikarilir: ceyrekte ilk izi "oyuna girmek" olmayan
(oyundan cikan ya da bir oyunda adi gecen) oyuncu ceyrege sahada baslamistir.
Bes kisi bulunamazsa onceki ceyregin sonundaki besten tamamlanir; ilk ceyrek
icin kutu skorundaki ilk bes.
"""
from services.cache import cache_data

REG, OT = 720, 300          # ceyrek ve uzatma suresi (sn)


def _secs(clock):
    """'8:16' ya da '45.3' -> kalan saniye."""
    s = str(clock or "0")
    if ":" in s:
        m, sec = s.split(":", 1)
        return int(m) * 60 + float(sec)
    try:
        return float(s)
    except ValueError:
        return 0.0


def _plen(n):
    return REG if n <= 4 else OT


def _pstart(n):
    """Ceyregin mac icindeki baslangic saniyesi."""
    return sum(_plen(k) for k in range(1, n))


def _clock(t, periods, end=False):
    """Mac saniyesi -> 'Q2 7:12' (ceyrekte kalan sure). Ceyrek sonu: 'end of Q2'."""
    for n in periods:
        st, ln = _pstart(n), _plen(n)
        if st <= t < st + ln or (end and st < t <= st + ln):
            left = st + ln - t
            name = f"Q{n}" if n <= 4 else "OT" if n == 5 else f"OT{n - 4}"
            if end and left < 0.5:
                return f"end of {name}"
            return f"{name} {int(left // 60)}:{int(left % 60):02d}"
    return ""


def build(summary):
    plays = summary.get("plays") or []
    box = (summary.get("boxscore") or {}).get("players") or []
    if not plays or not box:
        return None
    teams, team_of, info = [], {}, {}
    for t in box:
        tid = str((t.get("team") or {}).get("id"))
        abbr = (t.get("team") or {}).get("abbreviation") or ""
        roster = []
        stats = (t.get("statistics") or [{}])[0]
        keys = stats.get("keys") or stats.get("labels") or []
        for a in stats.get("athletes") or []:
            pid = str((a.get("athlete") or {}).get("id") or "")
            if not pid or a.get("didNotPlay"):
                continue
            vals = a.get("stats") or []
            mins = 0.0
            for k, v in zip(keys, vals):
                if str(k).lower() in ("minutes", "min"):
                    try:
                        mins = float(v)
                    except (TypeError, ValueError):
                        mins = 0.0
            team_of[pid] = tid
            info[pid] = {"id": pid, "name": (a.get("athlete") or {}).get("displayName") or "",
                         "short": (a.get("athlete") or {}).get("shortName") or "", "starter": bool(a.get("starter")),
                         "box_min": mins}
            roster.append(pid)
        teams.append({"id": tid, "abbr": abbr, "roster": roster})

    periods = sorted({int((p.get("period") or {}).get("number") or 0) for p in plays} - {0})
    if not periods:
        return None
    by_period = {n: [p for p in plays if int((p.get("period") or {}).get("number") or 0) == n] for n in periods}

    stints = {pid: [] for pid in info}
    on_end = {t["id"]: {pid for pid in t["roster"] if info[pid]["starter"]} for t in teams}   # ilk ceyrek: ilk bes
    for n in periods:
        ps = by_period[n]
        start, plen = _pstart(n), _plen(n)
        # Ceyregin ilk besi: ilk izi "girmek" olmayanlar
        first = {}
        for p in ps:
            is_sub = (p.get("type") or {}).get("text") == "Substitution"
            parts = [str((x.get("athlete") or {}).get("id")) for x in p.get("participants") or []]
            for k, pid in enumerate(parts):
                if pid not in info or pid in first:
                    continue
                first[pid] = "in" if (is_sub and k == 0) else "out" if is_sub else "seen"
        on = {}
        for t in teams:
            tid = t["id"]
            starters = {pid for pid in t["roster"] if first.get(pid) in ("out", "seen")}
            if n == 1:
                starters |= {pid for pid in on_end[tid] if first.get(pid) != "in"}
            if len(starters) < 5:
                # sessiz oynayan: onceki ceyregin sonunda sahada ve bu ceyrek "girmeyen"
                for pid in sorted(on_end[tid], key=lambda x: -info[x]["box_min"]):
                    if len(starters) >= 5:
                        break
                    if first.get(pid) != "in":
                        starters.add(pid)
            if len(starters) < 5:
                for pid in sorted(t["roster"], key=lambda x: -info[x]["box_min"]):
                    if len(starters) >= 5:
                        break
                    if first.get(pid) is None:
                        starters.add(pid)
            on[tid] = {pid: start for pid in list(starters)[:5] if True}
        # Degisiklikler
        for p in ps:
            if (p.get("type") or {}).get("text") != "Substitution":
                continue
            parts = [str((x.get("athlete") or {}).get("id")) for x in p.get("participants") or []]
            if len(parts) < 2:
                continue
            pin, pout = parts[0], parts[1]
            tid = team_of.get(pin) or team_of.get(pout)
            if not tid:
                continue
            t_abs = start + plen - _secs((p.get("clock") or {}).get("displayValue"))
            if pout in on[tid]:
                if t_abs > on[tid][pout]:
                    stints[pout].append([on[tid][pout], t_abs])
                on[tid].pop(pout, None)
            if pin in info:
                on[tid][pin] = t_abs
        end = start + plen
        for tid, cur in on.items():
            for pid, t0 in cur.items():
                if end > t0:
                    stints[pid].append([t0, end])
            on_end[tid] = set(cur)

    total = _pstart(periods[-1]) + _plen(periods[-1])
    out_teams = []
    for t in teams:
        rows = []
        for pid in t["roster"]:
            # Ceyrek gecisinde kesintisiz oynayan: tek parca
            merged = []
            for a, b in sorted(stints[pid]):
                if merged and a - merged[-1][1] <= 1:
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b])
            st = [{"a": round(a), "b": round(b), "label": f"{_clock(a, periods)} - {_clock(b, periods, end=True)} · "
                   f"{(b - a) / 60:.1f} min"} for a, b in merged if b - a >= 1]
            mins = sum(x["b"] - x["a"] for x in st) / 60
            if not st:
                continue
            rows.append({**info[pid], "stints": st, "min": round(mins, 1), "first": st[0]["a"]})
        rows.sort(key=lambda r: (not r["starter"], -r["min"]))
        out_teams.append({"abbr": t["abbr"], "players": rows})
    return {"total": total, "periods": [{"n": n, "start": _pstart(n), "len": _plen(n),
                                         "label": f"Q{n}" if n <= 4 else f"OT{n - 4}" if n > 5 else "OT"} for n in periods],
            "teams": out_teams}


@cache_data(ttl=600, show_spinner=False, copy_result=False)
def rotation(game_id):
    from services.nba_pages import _summary
    try:
        return build(_summary(str(game_id)))
    except Exception as exc:
        print(f"rotation {game_id} failed: {exc}")
        return None
