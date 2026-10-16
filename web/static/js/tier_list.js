// Tier list: oyuncular S-D kademelerine. Masaustunde surukle-birak,
// telefonda dokun-sec-dokun-birak. Durum bu cihazda; paylasim linki
// kademeleri adreste tasir (?t=), gorsel canvas ile uretilir.
(function () {
  const { $, toast, escapeHtml: h } = window.HL;
  const players = JSON.parse($("#tl-data").textContent).players;
  const byId = new Map(players.map((p) => [p.id, p]));
  const TIERS = [["S", "#E5484D"], ["A", "#F76B15"], ["B", "#F5B544"], ["C", "#46A758"], ["D", "#3987E5"]];
  const KEY = "hl_tierlist";
  const photo = (id) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=96&h=70`;
  const group = (pos) => (pos.includes("C") ? "C" : /PG|SG/.test(pos) && !/PF/.test(pos) ? "G" : "F");

  const empty = () => Object.fromEntries(TIERS.map(([t]) => [t, []]));
  let state = { title: "My 2026-27 fantasy tiers", tiers: empty() };
  let selected = null, poolLimit = 60, posFilter = "", query = "", dirty = false;

  function fromUrl() {
    const raw = new URLSearchParams(location.search).get("t");
    if (!raw) return null;
    const tiers = empty();
    raw.split("|").forEach((part) => {
      const [t, ids] = part.split(":");
      if (tiers[t]) tiers[t] = (ids || "").split(",").filter((id) => byId.has(id));
    });
    const title = new URLSearchParams(location.search).get("n");
    return { title: (title || "Shared tier list").slice(0, 60), tiers };
  }
  const shared = fromUrl();
  if (shared) { state = shared; $("#tl-shared").hidden = false; }
  else { try { const s = JSON.parse(localStorage.getItem(KEY)); if (s && s.tiers) state = { title: s.title || state.title, tiers: Object.assign(empty(), s.tiers) }; } catch (e) {} }

  function persist() {
    dirty = true;
    if (shared) { history.replaceState(null, "", "/tier-list"); $("#tl-shared").hidden = true; }
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }
  const placed = () => new Set(Object.values(state.tiers).flat());

  function chip(p) {
    return `<button class="tl-chip${selected === p.id ? " is-sel" : ""}" draggable="true" data-id="${p.id}" title="${h(p.name)}">
      <img src="${photo(p.id)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'"><span>${h(p.name.split(" ").slice(-1)[0])}</span></button>`;
  }

  function render() {
    $("#tl-title").value = state.title;
    $("#tl-board").innerHTML = TIERS.map(([t, color]) => `
      <div class="tl-row" data-tier="${t}">
        <div class="tl-label" style="background:${color}">${t}</div>
        <div class="tl-drop" data-tier="${t}">${state.tiers[t].map((id) => chip(byId.get(id))).join("") || '<span class="tl-empty">Drop players here</span>'}</div>
      </div>`).join("");
    const used = placed();
    let list = players.filter((p) => !used.has(p.id));
    const left = list.length;
    if (posFilter) list = list.filter((p) => group(p.pos) === posFilter);
    if (query) list = list.filter((p) => p.name.toLowerCase().includes(query));
    $("#tl-pool").innerHTML = list.slice(0, query ? 40 : poolLimit).map(chip).join("") || '<span class="tl-empty">No players left here.</span>';
    $("#tl-more").hidden = !!query || list.length <= poolLimit;
    $("#tl-left").textContent = `· ${left} unranked`;
    document.body.classList.toggle("tl-holding", !!selected);
  }

  function move(id, tier) {
    Object.keys(state.tiers).forEach((t) => { state.tiers[t] = state.tiers[t].filter((x) => x !== id); });
    if (tier) state.tiers[tier].push(id);
    selected = null; persist(); render();
  }

  // ---- dokun-sec / dokun-birak ----
  document.addEventListener("click", (e) => {
    const c = e.target.closest(".tl-chip");
    if (c) {
      if (selected && selected !== c.dataset.id && c.closest("[data-tier]") && c.closest(".tl-drop")) {
        // secili oyuncuyu bu oyuncunun onune yerlestir
        const tier = c.closest(".tl-drop").dataset.tier;
        const id = selected;
        Object.keys(state.tiers).forEach((t) => { state.tiers[t] = state.tiers[t].filter((x) => x !== id); });
        const arr = state.tiers[tier]; arr.splice(arr.indexOf(c.dataset.id), 0, id);
        selected = null; persist(); render(); return;
      }
      selected = selected === c.dataset.id ? null : c.dataset.id; render(); return;
    }
    const zone = e.target.closest(".tl-drop, .tl-label, #tl-pool");
    if (zone && selected) move(selected, zone.dataset.tier || zone.closest("[data-tier]").dataset.tier || "");
  });

  // ---- surukle-birak (masaustu) ----
  document.addEventListener("dragstart", (e) => {
    const c = e.target.closest(".tl-chip"); if (!c) return;
    e.dataTransfer.setData("text/plain", c.dataset.id); e.dataTransfer.effectAllowed = "move";
  });
  document.addEventListener("dragover", (e) => { if (e.target.closest(".tl-drop, #tl-pool, .tl-label")) e.preventDefault(); });
  document.addEventListener("drop", (e) => {
    const zone = e.target.closest(".tl-drop, #tl-pool, .tl-label"); if (!zone) return;
    e.preventDefault();
    const id = e.dataTransfer.getData("text/plain"); if (!byId.has(id)) return;
    const tier = zone.id === "tl-pool" ? "" : (zone.dataset.tier || zone.closest("[data-tier]").dataset.tier);
    const before = e.target.closest(".tl-chip");
    if (tier && before && before.dataset.id !== id) {
      Object.keys(state.tiers).forEach((t) => { state.tiers[t] = state.tiers[t].filter((x) => x !== id); });
      const arr = state.tiers[tier]; arr.splice(arr.indexOf(before.dataset.id), 0, id);
      persist(); render(); return;
    }
    move(id, tier);
  });

  // ---- kontroller ----
  $("#tl-title").addEventListener("input", (e) => { state.title = e.target.value.slice(0, 60); persist(); });
  $("#tl-search").addEventListener("input", (e) => { query = e.target.value.trim().toLowerCase(); render(); });
  $("#tl-pos").addEventListener("click", (e) => {
    const b = e.target.closest("[data-pos]"); if (!b) return;
    posFilter = b.dataset.pos; $("#tl-pos").querySelectorAll("button").forEach((x) => x.classList.toggle("is-on", x === b)); render();
  });
  $("#tl-more").addEventListener("click", () => { poolLimit += 60; render(); });
  $("#tl-reset").addEventListener("click", () => { if (confirm("Clear every tier?")) { state.tiers = empty(); persist(); render(); } });

  $("#tl-link").addEventListener("click", async () => {
    const t = TIERS.map(([k]) => `${k}:${state.tiers[k].join(",")}`).join("|");
    const url = `${location.origin}/tier-list?t=${encodeURIComponent(t)}&n=${encodeURIComponent(state.title)}&ref=tierlist-share${window.HL.inv()}`;
    if (window.gtag) gtag("event", "tierlist_share", { kind: "link" });
    if (navigator.share && matchMedia("(pointer: coarse)").matches) {
      try { await navigator.share({ title: state.title, url }); return; } catch (err) { if (err.name === "AbortError") return; }
    }
    try { await navigator.clipboard.writeText(url); toast("Link copied."); } catch (err) { window.prompt("Copy the link:", url); }
  });

  // ---- gorsel ----
  const loadImg = (src) => new Promise((ok) => { const i = new Image(); i.crossOrigin = "anonymous"; i.onload = () => ok(i); i.onerror = () => ok(null); i.src = src; });
  $("#tl-png").addEventListener("click", async (e) => {
    const btn = e.currentTarget; btn.classList.add("is-loading");
    try {
      const W = 1200, label = 110, cell = 104, pad = 16, perRow = Math.floor((W - label - pad * 2) / cell);
      const rows = TIERS.map(([t]) => Math.max(1, Math.ceil(state.tiers[t].length / perRow)));
      const H = 110 + rows.reduce((a, r) => a + r * cell + 8, 0) + 50;
      const cv = document.createElement("canvas"); cv.width = W; cv.height = H;
      const g = cv.getContext("2d");
      g.fillStyle = "#0B0F17"; g.fillRect(0, 0, W, H);
      g.fillStyle = "#E8ECF4"; g.font = "800 40px Inter, system-ui, sans-serif"; g.fillText(state.title || "Tier list", pad, 62);
      g.fillStyle = "#9AA6BD"; g.font = "600 20px Inter, system-ui, sans-serif"; g.fillText("Fantasy basketball 2026-27", pad, 92);
      const ids = Object.values(state.tiers).flat();
      const imgs = new Map(await Promise.all(ids.map(async (id) => [id, await loadImg(photo(id))])));
      let y = 110;
      TIERS.forEach(([t, color], ti) => {
        const hgt = rows[ti] * cell;
        g.fillStyle = "#131926"; g.fillRect(pad, y, W - pad * 2, hgt);
        g.fillStyle = color; g.fillRect(pad, y, label - 10, hgt);
        g.fillStyle = "#0B0F17"; g.font = "900 48px Inter, system-ui, sans-serif"; g.textAlign = "center";
        g.fillText(t, pad + (label - 10) / 2, y + hgt / 2 + 17); g.textAlign = "left";
        state.tiers[t].forEach((id, k) => {
          const x = pad + label + (k % perRow) * cell, yy = y + Math.floor(k / perRow) * cell;
          const im = imgs.get(id); if (im) g.drawImage(im, x + 6, yy + 4, 92, 67);
          g.fillStyle = "#E8ECF4"; g.font = "700 14px Inter, system-ui, sans-serif"; g.textAlign = "center";
          const last = byId.get(id).name.split(" ").slice(-1)[0];
          g.fillText(last.length > 12 ? last.slice(0, 11) + "." : last, x + 52, yy + 92); g.textAlign = "left";
        });
        y += hgt + 8;
      });
      g.fillStyle = "#6B7893"; g.font = "600 18px Inter, system-ui, sans-serif"; g.fillText("Make yours at hooplifenba.com/tier-list", pad, H - 18);
      const blob = await new Promise((ok) => cv.toBlob(ok, "image/png"));
      const file = new File([blob], "tier-list.png", { type: "image/png" });
      if (window.gtag) gtag("event", "tierlist_share", { kind: "image" });
      if (navigator.canShare && navigator.canShare({ files: [file] }) && matchMedia("(pointer: coarse)").matches) {
        try { await navigator.share({ files: [file], title: state.title }); return; } catch (err) { if (err.name === "AbortError") return; }
      }
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "tier-list.png"; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    } catch (err) { toast("Could not create the image. Try again.", true); }
    finally { btn.classList.remove("is-loading"); }
  });

  render();
})();
