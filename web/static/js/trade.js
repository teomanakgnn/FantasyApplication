/* Trade analyzer: secim ve degerleme tamamen tarayicida. */
(function () {
  "use strict";
  if (!window.TRADE || !document.querySelector(".t-side")) return;
  const { escapeHtml: h, toast } = window.HL;
  const players = window.TRADE.players;
  const byName = new Map(players.map((p) => [p.name, p]));
  const sides = { a: [], b: [] };
  const BASE = { pts: 0.75, reb: 0.5, ast: 0.8, stl: 1.7, blk: 1.6, to: -1.5, fga: -0.9, fgm: 1.2, fta: -0.55, ftm: 1.1, tpm: 0.6 };
  const $ = (id) => document.getElementById(id);

  function weights() {
    const w = Object.assign({}, BASE);
    document.querySelectorAll(".t-punt:checked").forEach((c) => {
      if (c.value === "FG") { w.fgm = 0; w.fga = 0; }
      if (c.value === "FT") { w.ftm = 0; w.fta = 0; }
      if (c.value === "TO") { w.to = 0; }
    });
    return w;
  }
  const fp = (p, w) => Object.entries(w).reduce((s, [k, v]) => s + (p[k] || 0) * v, 0);

  function tier(raw) {
    if (raw >= 30) return "Elite"; if (raw >= 22) return "Solid starter"; if (raw >= 15) return "Starter";
    if (raw >= 12) return "Flex"; if (raw >= 8) return "Bench"; if (raw >= 4) return "Deep bench"; return "Streamer";
  }

  // Dort yontem eski sayfadakiyle ayni formuller
  function value(list) {
    if (!list.length) return { total: 0, detail: [] };
    const w = weights();
    const method = $("t-method").value;
    const raws = list.map((p) => ({ p, raw: fp(p, w) })).sort((a, b) => b.raw - a.raw);
    if (method === "threshold") {
      const min = +$("t-min").value, pen = +$("t-pen").value;
      const detail = raws.map(({ p, raw }) => {
        const mult = raw >= min ? 1 : Math.pow(Math.max(raw, 0) / min, 1 + pen);
        return { p, raw, adj: raw * mult, mult };
      });
      return { total: detail.reduce((s, d) => s + d.adj, 0) / detail.length, detail };
    }
    if (method === "quality") {
      const fps = raws.map((r) => r.raw);
      return { total: (fps[0] * 1.5 + fps.slice(1).reduce((s, x) => s + x, 0)) / fps.length, detail: raws.map((r) => ({ ...r, adj: r.raw, mult: 1 })) };
    }
    if (method === "diminishing") {
      const f = [1, 0.85, 0.7, 0.55, 0.45, 0.35, 0.25];
      let total = 0, sum = 0;
      raws.forEach((r, i) => { const k = f[i] !== undefined ? f[i] : 0.2; total += r.raw * k; sum += k; });
      return { total: total / sum, detail: raws.map((r) => ({ ...r, adj: r.raw, mult: 1 })) };
    }
    return { total: raws.reduce((s, r) => s + r.raw, 0) / raws.length, detail: raws.map((r) => ({ ...r, adj: r.raw, mult: 1 })) };
  }

  function fillLists() {
    document.querySelectorAll(".t-side").forEach((box) => {
      const side = box.dataset.side, other = side === "a" ? "b" : "a";
      const team = box.querySelector(".t-team").value;
      const taken = new Set(sides.a.concat(sides.b).map((p) => p.name));
      const opts = players.filter((p) => (!team || p.team === team) && !taken.has(p.name));
      box.querySelector("datalist").innerHTML = opts.map((p) => `<option value="${h(p.name)}">${h(p.team)} · ${p.pts.toFixed(1)} PTS</option>`).join("");
      void other;
    });
  }

  function add(side, name) {
    const p = byName.get(name);
    if (!p) return false;
    if (sides.a.concat(sides.b).some((x) => x.name === name)) { toast(`${name} is already in the trade.`, true); return true; }
    sides[side].push(p);
    render();
    return true;
  }

  function render() {
    const va = value(sides.a), vb = value(sides.b);
    const method = $("t-method").value;
    $("t-threshold-box").hidden = method !== "threshold";
    ["a", "b"].forEach((side) => {
      const box = document.querySelector(`.t-side[data-side="${side}"]`);
      const res = side === "a" ? va : vb;
      box.querySelector(".t-players").innerHTML = res.detail.map((d) => `
        <div class="t-chip"><b>${h(d.p.name)}</b><span class="small muted">${h(d.p.team)} · ${d.raw.toFixed(1)} FP${method === "threshold" && d.mult < 1 ? ` <span class="warn">×${d.mult.toFixed(2)}</span>` : ""} · ${tier(d.raw)}</span>
        <button class="x" data-remove="${h(d.p.name)}" data-side="${side}" aria-label="Remove ${h(d.p.name)}">×</button></div>`).join("") || `<p class="muted small">No players yet.</p>`;
      box.querySelector(".t-total").innerHTML = sides[side].length ? `Value: <b style="color:var(--text)">${res.total.toFixed(1)} FP</b>` : "";
    });
    fillLists();
    const ready = sides.a.length && sides.b.length;
    $("t-result").hidden = !ready;
    $("t-hint").hidden = !!ready;
    if (!ready) return;
    const diff = va.total - vb.total;
    $("t-v1").textContent = va.total.toFixed(1);
    $("t-v2").textContent = vb.total.toFixed(1);
    const verdict = $("t-verdict");
    if (Math.abs(diff) < 2) { verdict.textContent = "Fair trade"; verdict.className = "good"; }
    else { verdict.textContent = diff > 0 ? "Team 1 wins" : "Team 2 wins"; verdict.className = diff > 0 ? "good" : "bad"; }
    $("t-gap").textContent = `${Math.abs(diff).toFixed(1)} FP per player between the sides`;

    const avg = (list, k) => list.reduce((s, p) => s + p[k], 0) / list.length;
    const pct = (list, m, a) => { const A = list.reduce((s, p) => s + p[a], 0); return A ? 100 * list.reduce((s, p) => s + p[m], 0) / A : 0; };
    const cats = [["PTS", "pts"], ["REB", "reb"], ["AST", "ast"], ["STL", "stl"], ["BLK", "blk"], ["3PM", "tpm"], ["TO", "to", true]];
    let html = cats.map(([label, k, lower]) => {
      const x = avg(sides.a, k), y = avg(sides.b, k), m = Math.max(x, y) || 1;
      const win = lower ? (x < y ? 1 : x > y ? 2 : 0) : (x > y ? 1 : x < y ? 2 : 0);
      return `<div class="t-bar"><div class="l1"><i style="width:${50 * x / m}%;background:var(--accent)"></i>&nbsp;${x.toFixed(1)}</div>
        <div class="lab">${label}${win ? `<br><span class="${win === 1 ? "good" : "bad"}">T${win}</span>` : ""}</div>
        <div style="display:flex;align-items:center;gap:6px"><i style="width:${50 * y / m}%;background:#f97316"></i>${y.toFixed(1)}</div></div>`;
    }).join("");
    [["FG%", "fgm", "fga"], ["FT%", "ftm", "fta"]].forEach(([label, mk, ak]) => {
      const x = pct(sides.a, mk, ak), y = pct(sides.b, mk, ak);
      html += `<div class="t-bar"><div class="right">${x.toFixed(1)}%</div><div class="lab">${label}</div><div>${y.toFixed(1)}%</div></div>`;
    });
    $("t-bars").innerHTML = html + `<p class="tiny dim" style="margin:8px 0 0">Per-player averages on each side.</p>`;
  }

  document.querySelectorAll(".t-side").forEach((box) => {
    const input = box.querySelector(".t-add");
    const commit = () => { if (add(box.dataset.side, input.value.trim())) input.value = ""; };
    input.addEventListener("change", commit);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); commit(); } });
    box.querySelector(".t-team").addEventListener("change", fillLists);
  });
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-remove]");
    if (!b) return;
    sides[b.dataset.side] = sides[b.dataset.side].filter((p) => p.name !== b.dataset.remove);
    render();
  });
  ["t-method", "t-min", "t-pen"].forEach((id) => $(id).addEventListener("input", () => {
    $("t-min-v").textContent = $("t-min").value; $("t-pen-v").textContent = $("t-pen").value; render();
  }));
  document.querySelectorAll(".t-punt").forEach((c) => c.addEventListener("change", render));
  render();
})();
