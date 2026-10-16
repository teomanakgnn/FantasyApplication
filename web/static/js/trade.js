/* Trade analyzer: degerleme tamamen tarayicida (sunucu oyuncu tablosunu verir).
 *
 * Kategori ligi: deger = punt edilmeyen kategorilerin z toplami.
 * Puan ligi: ESPN varsayilan puanlamasi (mac basi).
 * Kadro yeri: az oyuncu alan taraf, bosalan her yer icin "yedek seviyesi"
 * bir serbest oyuncu kazanir; cok oyuncu alan taraf ayni kadar oyuncu birakir.
 * Yedek seviyesi = lig boyu x 13'uncu siradaki oyuncunun degeri.
 */
(function () {
  "use strict";
  const { $, escapeHtml: h, toast } = window.HL;
  const ALL = JSON.parse(document.getElementById("tr-data").textContent);
  const byName = new Map(ALL.map((p) => [p.name, p]));
  const CATS = ["FG%", "FT%", "3PM", "PTS", "REB", "AST", "STL", "BLK", "TO"];
  const RAW = { "3PM": "tpm", PTS: "pts", REB: "reb", AST: "ast", STL: "stl", BLK: "blk", TO: "to" };
  const PTS_W = { pts: 1, reb: 1, ast: 2, stl: 4, blk: 4, to: -2, fgm: 2, fga: -1, ftm: 1, fta: -1, tpm: 1 };
  const photo = (id) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=110&h=80`;
  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  const st = { a: [], b: [], lt: "9", teams: 12, punts: new Set() };

  // ---------------- ayarlar / adres ----------------
  const q = new URLSearchParams(location.search);
  if (q.get("lt")) st.lt = q.get("lt");
  if (q.get("t")) st.teams = +q.get("t") || 12;
  (q.get("p") || "").split(",").filter((c) => CATS.includes(c)).forEach((c) => st.punts.add(c));
  ["a", "b"].forEach((s) => (q.get(s) || "").split("|").forEach((n) => { const p = byName.get(n); if (p && !inTrade(p.name)) st[s].push(p); }));
  function inTrade(name) { return st.a.concat(st.b).some((p) => p.name === name); }
  const injuryOn = () => { const c = $("#tr-injury"); return !!(c && c.checked); };
  const cats = () => CATS.filter((c) => !(st.lt === "8" && c === "TO") && !st.punts.has(c));

  function shareUrl() {
    const u = new URLSearchParams({ basis: window.TRADE_BASIS, lt: st.lt, t: st.teams });
    if (st.punts.size) u.set("p", [...st.punts].join(","));
    if (st.a.length) u.set("a", st.a.map((p) => p.name).join("|"));
    if (st.b.length) u.set("b", st.b.map((p) => p.name).join("|"));
    return `${location.origin}/trade-analyzer?${u.toString()}`;
  }

  // ---------------- degerleme ----------------
  function baseValue(p) {
    if (st.lt === "pts") return Object.entries(PTS_W).reduce((s, [k, w]) => s + (p.s[k] || 0) * w, 0);
    return cats().reduce((s, c) => s + (p.z[c] || 0), 0);
  }
  let repCache = null;
  function replacement() {
    if (repCache) return repCache;
    const sorted = ALL.map((p) => ({ p, v: baseValue(p) })).sort((x, y) => y.v - x.v);
    const at = Math.min(sorted.length - 1, st.teams * 13);
    const near = sorted.slice(Math.max(0, at - 5), at + 6).map((x) => x.p);
    const avg = (f) => near.reduce((s, p) => s + f(p), 0) / near.length;
    repCache = {
      v: sorted[at].v,
      z: Object.fromEntries(CATS.map((c) => [c, avg((p) => p.z[c])])),
      s: Object.fromEntries(Object.keys(near[0].s).map((k) => [k, avg((p) => p.s[k])])),
    };
    return repCache;
  }
  // Deger = yedek seviyesinin ustu (VORP). Bos kadro yeri yedek seviyesi
  // bir oyuncuyla dolar ve 0 sayilir; 2'ye 1'in bedeli boylece kendiliginden
  // gorunur. Sakatlik: eksik maclarda yerini yedek seviyesi oyuncu doldurur.
  function value(p) {
    const rep = replacement().v;
    let v = baseValue(p);
    if (injuryOn() && p.avail < 0.999) v = p.avail * v + (1 - p.avail) * rep;
    return v - rep;
  }
  const sum = (list) => list.reduce((s, p) => s + value(p), 0);

  function tierOf(p) {
    const r = p.rank;
    return r <= 12 ? "Elite" : r <= 36 ? "Star" : r <= 72 ? "Starter" : r <= 120 ? "Rotation" : r <= 160 ? "Bench" : "Waiver";
  }

  // ---------------- arama ----------------
  document.querySelectorAll(".tr-side").forEach((box) => {
    const side = box.dataset.side, input = box.querySelector(".tr-input"), list = box.querySelector(".dp-list");
    let matches = [], active = 0;
    const draw = () => {
      list.hidden = !matches.length;
      list.innerHTML = matches.map((p, i) => `<li><button type="button" data-name="${h(p.name)}" class="${i === active ? "is-active" : ""}">
        <img src="${photo(p.id)}" alt="" onerror="this.style.visibility='hidden'" style="width:34px;height:25px;object-fit:cover"><span>${h(p.name)}</span><span class="dp-team">${h(p.team)} · #${p.rank}</span></button></li>`).join("");
    };
    input.addEventListener("input", () => {
      const t = norm(input.value.trim());
      matches = t.length < 2 ? [] : ALL.filter((p) => !inTrade(p.name) && norm(p.name).split(" ").some((w) => w.startsWith(t)) || (t.length > 3 && !inTrade(p.name) && norm(p.name).includes(t))).slice(0, 8);
      active = 0; draw();
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" && matches.length) { active = (active + 1) % matches.length; draw(); e.preventDefault(); }
      else if (e.key === "ArrowUp" && matches.length) { active = (active - 1 + matches.length) % matches.length; draw(); e.preventDefault(); }
      else if (e.key === "Enter") { e.preventDefault(); if (matches[active]) pick(matches[active]); }
      else if (e.key === "Escape") { matches = []; draw(); }
    });
    list.addEventListener("mousedown", (e) => e.preventDefault());
    list.addEventListener("click", (e) => { const b = e.target.closest("[data-name]"); if (b) pick(byName.get(b.dataset.name)); });
    input.addEventListener("blur", () => setTimeout(() => { list.hidden = true; }, 150));
    function pick(p) {
      if (!p || inTrade(p.name)) return;
      st[side].push(p); input.value = ""; matches = []; draw(); render(); input.focus();
    }
  });

  // ---------------- cizim ----------------
  function card(p, side) {
    const v = value(p), base = baseValue(p);
    const inj = p.injury && p.injury !== "ACTIVE";
    const unit = st.lt === "pts" ? " FP" : "";
    return `<div class="tr-p">
      <img src="${photo(p.id)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
      <div class="tr-pn"><b>${h(p.name)}</b>
        <small>${h(p.team || "")}${p.pos ? " · " + h(p.pos) : ""} · #${p.rank} ${tierOf(p)}${inj ? ` · <span class="bad">${h(p.injury.replace("_", " ").toLowerCase())}</span>` : ""}</small>
        <small class="dim">${p.s.pts.toFixed(1)} pts · ${p.s.reb.toFixed(1)} reb · ${p.s.ast.toFixed(1)} ast · ${p.s.stl.toFixed(1)} stl · ${p.s.blk.toFixed(1)} blk · ${p.s.tpm.toFixed(1)} 3pm</small></div>
      <div class="tr-pv"><b class="${v >= 0 ? "" : "bad"}">${v >= 0 ? "+" : ""}${v.toFixed(1)}${unit}</b>
        ${injuryOn() && p.avail < 0.97 ? `<small class="warn" title="Projected share of games played">${Math.round(p.avail * 100)}% games</small>` : `<small class="dim">above waiver</small>`}
        ${Math.abs(v - base) > 0.05 && injuryOn() ? "" : ""}</div>
      <button class="tr-x" data-remove="${h(p.name)}" data-side="${side}" aria-label="Remove ${h(p.name)}">×</button>
    </div>`;
  }

  function render() {
    repCache = null;
    document.querySelectorAll("#tr-league [data-lt]").forEach((b) => b.classList.toggle("is-on", b.dataset.lt === st.lt));
    document.querySelectorAll("#tr-punts [data-punt]").forEach((b) => {
      b.classList.toggle("is-on", st.punts.has(b.dataset.punt));
      b.disabled = st.lt === "8" && b.dataset.punt === "TO";
    });
    $("#tr-punt-row").hidden = st.lt === "pts";
    $("#tr-teams").value = String(st.teams);
    document.querySelectorAll("[data-basis]").forEach((a) => { const u = new URL(shareUrl()); u.searchParams.set("basis", a.dataset.basis); a.href = u.pathname + u.search; });

    ["a", "b"].forEach((side) => {
      const box = document.querySelector(`.tr-side[data-side="${side}"]`);
      box.querySelector(".tr-list").innerHTML = st[side].map((p) => card(p, side)).join("") || `<p class="muted small" style="margin:8px 0 0">No players yet.</p>`;
      box.querySelector(".tr-sum").textContent = st[side].length ? `${sum(st[side]).toFixed(1)}${st.lt === "pts" ? " FP" : ""}` : "";
    });
    const ready = st.a.length && st.b.length;
    $("#tr-result").hidden = !ready;
    $("#tr-hint").hidden = !!ready;
    history.replaceState(null, "", shareUrl().replace(location.origin, ""));
    if (ready) result();
  }

  function result() {
    const rep = replacement();
    const send = sum(st.a), get = sum(st.b);
    const spots = st.a.length - st.b.length;          // >0: yer acildi, <0: oyuncu birakilacak
    const net = get - send;
    const scale = Math.max(Math.abs(send), Math.abs(get), st.lt === "pts" ? 30 : 3);
    const fair = Math.abs(net) < Math.max(st.lt === "pts" ? 2.5 : 0.6, 0.08 * scale);
    const lean = Math.abs(net) < 0.22 * scale;
    const unit = st.lt === "pts" ? " FP" : "";

    const verdict = fair ? ["Fair trade", "fair"] : net > 0 ? [lean ? "You win - slightly" : "You win this trade", "win"] : [lean ? "You lose - slightly" : "You lose this trade", "lose"];
    $("#tr-verdict").className = "tr-verdict " + verdict[1];
    $("#tr-verdict").innerHTML = `${verdict[0]}<small>${net >= 0 ? "+" : ""}${net.toFixed(1)}${unit} value for you</small>`;
    const pct = Math.max(-1, Math.min(1, net / scale));
    const fill = $("#tr-meter-fill");
    fill.style.left = pct >= 0 ? "50%" : `${50 + pct * 50}%`;
    fill.style.width = `${Math.abs(pct) * 50}%`;
    fill.className = pct >= 0 ? "pos" : "neg";

    const lines = [`<div><span>You get</span><b>${get.toFixed(1)}${unit}</b></div>`, `<div><span>You send</span><b>-${send.toFixed(1)}${unit}</b></div>`];
    if (spots > 0) lines.push(`<div><span>${spots} open roster spot${spots > 1 ? "s" : ""} → waiver pickup</span><b>±0</b></div>`);
    if (spots < 0) lines.push(`<div><span>You drop ${-spots} waiver-level player${spots < -1 ? "s" : ""}</span><b>±0</b></div>`);
    lines.push(`<div class="tot"><span>Net for you</span><b>${net >= 0 ? "+" : ""}${net.toFixed(1)}${unit}</b></div>`);
    $("#tr-math").innerHTML = lines.join("");

    // Kategori etkisi (mac basi, takim toplamina)
    const zsum = (list, c) => list.reduce((s, p) => s + (p.z[c] || 0), 0);
    const ssum = (list, k) => list.reduce((s, p) => s + (p.s[k] || 0), 0);
    const rows = CATS.filter((c) => !(st.lt === "8" && c === "TO")).map((c) => {
      const dz = zsum(st.b, c) - zsum(st.a, c) + spots * rep.z[c];
      let raw;
      if (c === "FG%" || c === "FT%") {
        const [m, a, base] = c === "FG%" ? ["fgm", "fga", [520, 1100]] : ["ftm", "fta", [210, 270]];
        // Tipik bir haftalik takim (13 oyuncu) uzerinden yuzde degisimi
        const dm = ssum(st.b, m) - ssum(st.a, m) + spots * rep.s[m], da = ssum(st.b, a) - ssum(st.a, a) + spots * rep.s[a];
        const scaleW = 3.4;   // mac basi -> haftalik (oyuncu basi ~3.4 mac)
        raw = 100 * ((base[0] + dm * scaleW) / (base[1] + da * scaleW) - base[0] / base[1]);
        raw = `${raw >= 0 ? "+" : ""}${raw.toFixed(2)}%`;
      } else {
        const k = RAW[c];
        const d = ssum(st.b, k) - ssum(st.a, k) + spots * rep.s[k];
        raw = `${d >= 0 ? "+" : ""}${d.toFixed(1)}/g`;
        if (c === "TO") raw = `${d >= 0 ? "+" : ""}${d.toFixed(1)} TO/g`;
      }
      return { c, dz, raw, punt: st.punts.has(c) };
    });
    const maxZ = Math.max(1, ...rows.map((r) => Math.abs(r.dz)));
    $("#tr-cats").innerHTML = rows.map((r) => {
      const good = r.dz > 0.15, bad = r.dz < -0.15;
      const w = Math.abs(r.dz) / maxZ * 50;
      return `<div class="tr-cat ${r.punt ? "punt" : ""}">
        <b>${r.c}${r.punt ? ' <span class="tiny dim">punt</span>' : ""}</b>
        <div class="tr-bar"><span class="tr-zero"></span><i class="${good ? "pos" : bad ? "neg" : "flat"}" style="${r.dz >= 0 ? `left:50%;width:${w}%` : `left:${50 - w}%;width:${w}%`}"></i></div>
        <span class="tr-raw ${good ? "good" : bad ? "bad" : "dim"}">${r.raw}</span></div>`;
    }).join("");
    $("#tr-cats-note").textContent = st.lt === "pts" ? "Points leagues score totals, but category shifts still show where the production comes from." : "Bars: change in category strength (z-score). Numbers: per-game change for your team; FG%/FT% as the effect on a typical team's weekly percentage. Includes the roster-spot adjustment.";

    notes(rows, net, spots, rep, fair);
  }

  function notes(rows, net, spots, rep, fair) {
    const out = [];
    const live = rows.filter((r) => !r.punt);
    const gains = live.filter((r) => r.dz > 0.4).sort((a, b) => b.dz - a.dz).map((r) => r.c);
    const losses = live.filter((r) => r.dz < -0.4).sort((a, b) => a.dz - b.dz).map((r) => r.c);
    const won = live.filter((r) => r.dz > 0.15).length, lost = live.filter((r) => r.dz < -0.15).length;
    if (st.lt !== "pts") out.push(`<p><b>Categories:</b> you get better in <b>${won}</b> and worse in <b>${lost}</b> of the ${live.length} you play.${gains.length ? ` Biggest gains: ${gains.slice(0, 3).join(", ")}.` : ""}${losses.length ? ` Biggest losses: ${losses.slice(0, 3).join(", ")}.` : ""}</p>`);
    const puntHit = rows.filter((r) => r.punt && r.dz < -0.4).map((r) => r.c);
    if (puntHit.length) out.push(`<p>You lose ground in ${puntHit.join(", ")} - but you punt ${puntHit.length > 1 ? "them" : "it"}, so it costs you nothing.</p>`);
    // Punt uyumu
    const fitsPunt = ["FT%", "FG%", "AST", "3PM", "PTS", "REB", "BLK", "STL", "TO"].find((c) => !st.punts.has(c) && losses[0] === c && gains.length >= 2);
    if (fitsPunt && st.lt !== "pts") out.push(`<p>The shape of this deal - most of the loss in ${fitsPunt}, gains spread elsewhere - fits a <b>punt ${fitsPunt}</b> build. Good if you are already leaning that way.</p>`);
    if (spots > 0) out.push(`<p><b>${st.a.length}-for-${st.b.length}:</b> you consolidate. Values are measured above a waiver-level player in a ${st.teams}-team league, so the open roster spot counts as zero - you refill it from free agency. If your waiver wire is deep, consolidating is worth even more.</p>`);
    if (spots < 0) out.push(`<p><b>${st.a.length}-for-${st.b.length}:</b> you take on more players than you send, so you will have to drop ${-spots}. The math assumes you drop someone at waiver level; if your bench is better than that, this trade is worse for you than it looks.</p>`);
    const stars = (list) => list.reduce((best, p) => (!best || p.rank < best.rank ? p : best), null);
    const bestGet = stars(st.b), bestSend = stars(st.a);
    if (bestGet && bestSend && bestGet.rank + 15 < bestSend.rank) out.push(`<p>You get the best player in the deal (${h(bestGet.name)}, #${bestGet.rank}). Stars are harder to find than depth - in a close call that tips it your way.</p>`);
    else if (bestGet && bestSend && bestSend.rank + 15 < bestGet.rank) out.push(`<p>You give up the best player in the deal (${h(bestSend.name)}, #${bestSend.rank}). Only do it if the categories really fit your team better.</p>`);
    const risky = st.b.filter((p) => p.avail < 0.8 || (p.injury && p.injury !== "ACTIVE"));
    if (risky.length) out.push(`<p class="warn">Health check: ${risky.map((p) => `${h(p.name)}${p.avail < 0.8 ? ` (projected ~${Math.round(p.avail * 82)} games)` : ""}${p.injury !== "ACTIVE" ? ` (${h(p.injury.replace("_", " ").toLowerCase())})` : ""}`).join(", ")}.${injuryOn() ? " Already priced in above." : " Turn on injury risk to price it in."}</p>`);
    out.unshift(`<p class="tr-lead">${fair ? "Close enough to call it fair - decide on category fit." : net > 0 ? "The numbers favour you." : "The numbers favour the other side."} ${window.TRADE_BASIS === "proj" ? "Based on 2026-27 projections." : ""}</p>`);
    $("#tr-notes").innerHTML = out.join("");
  }

  // ---------------- olaylar ----------------
  document.addEventListener("click", (e) => {
    const rm = e.target.closest("[data-remove]");
    if (rm) { st[rm.dataset.side] = st[rm.dataset.side].filter((p) => p.name !== rm.dataset.remove); return render(); }
    const lt = e.target.closest("[data-lt]");
    if (lt) { st.lt = lt.dataset.lt; if (st.lt === "8") st.punts.delete("TO"); return render(); }
    const pu = e.target.closest("[data-punt]");
    if (pu && !pu.disabled) { st.punts.has(pu.dataset.punt) ? st.punts.delete(pu.dataset.punt) : st.punts.add(pu.dataset.punt); return render(); }
  });
  $("#tr-teams").addEventListener("change", (e) => { st.teams = +e.target.value; render(); });
  const inj = $("#tr-injury"); if (inj) inj.addEventListener("change", render);
  $("#tr-swap").addEventListener("click", () => { [st.a, st.b] = [st.b, st.a]; render(); });
  $("#tr-clear").addEventListener("click", () => { st.a = []; st.b = []; render(); });
  $("#tr-share").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(shareUrl()); toast("Link copied - send it to the other manager."); }
    catch (e) { window.prompt("Copy the link:", shareUrl()); }
    if (window.gtag) gtag("event", "trade_share");
  });
  render();
})();
