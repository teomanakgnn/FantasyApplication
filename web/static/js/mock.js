/* Mock draft istemcisi. Durum sunucuda; burasi yalnizca cizer ve hamle gonderir. */
(function () {
  "use strict";
  const { api, toast, escapeHtml: h, hydrate } = window.HL;
  const $ = (id) => document.getElementById(id);
  const STORE = "hl_mock_draft";
  const SETTINGS = "hl_mock_settings";

  let draftId = null, view = null, pool = [], poolById = new Map();
  let posFilter = "ALL", busy = false, lastSeen = 0;

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
    del(k) { try { localStorage.removeItem(k); } catch (e) {} },
  };

  // ---------------- kurulum ----------------
  const form = $("setup-form");
  function syncSetup() {
    const fmt = form.format.value, mode = form.opponent_mode.value;
    form.querySelectorAll("[data-only]").forEach((el) => {
      const need = el.dataset.only;
      el.hidden = (need === "auction" && fmt !== "auction") || (need === "ai" && mode !== "ai");
    });
    const teams = +form.team_count.value;
    Array.from(form.user_slot.options).forEach((o) => { if (o.value !== "random") o.hidden = +o.value > teams; });
    if (form.user_slot.value !== "random" && +form.user_slot.value > teams) form.user_slot.value = String(teams);
  }
  try {
    const saved = JSON.parse(store.get(SETTINGS) || "{}");
    for (const [k, v] of Object.entries(saved)) {
      const el = form.elements[k];
      if (!el) continue;
      if (el instanceof RadioNodeList) { Array.from(el).forEach((r) => (r.checked = r.value === v)); }
      else el.value = v;
    }
  } catch (e) {}
  form.addEventListener("change", syncSetup);
  syncSetup();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    store.set(SETTINGS, JSON.stringify(data));
    if (data.user_slot === "random") data.user_slot = 1 + Math.floor(Math.random() * +data.team_count);
    const btn = form.querySelector("[type=submit]");
    btn.classList.add("is-loading");
    try {
      const res = await api("/api/mock", { method: "POST", body: data });
      start(res);
    } catch (err) { toast(err.message, true); }
    finally { btn.classList.remove("is-loading"); }
  });

  function start(res) {
    pool = res.pool || pool;
    poolById = new Map(pool.map((p) => [p.id, p]));
    draftId = res.view.id;
    store.set(STORE, draftId);
    lastSeen = 0;
    $("setup-view").hidden = true;
    $("draft-view").hidden = false;
    window.scrollTo(0, 0);
    apply(res);
  }

  // Suren bir draft varsa devam et
  const existing = store.get(STORE);
  if (existing) {
    $("resume-note").hidden = false;
    $("resume-btn").addEventListener("click", async () => {
      try { start(await api("/api/mock/" + existing)); }
      catch (err) { store.del(STORE); $("resume-note").hidden = true; toast(err.message, true); }
    });
  }

  $("new-draft").addEventListener("click", () => {
    if (view && !view.complete && !confirm("Leave this draft and start a new one?")) return;
    store.del(STORE);
    draftId = null; view = null;
    $("draft-view").hidden = true;
    $("setup-view").hidden = false;
    $("resume-note").hidden = true;
    window.scrollTo(0, 0);
  });

  // Kayitli draftlar
  document.addEventListener("click", async (e) => {
    const open = e.target.closest("[data-open-saved]");
    if (open) {
      open.classList.add("is-loading");
      try { start(await api(`/api/mock/load/${open.dataset.openSaved}`, { method: "POST" })); }
      catch (err) { toast(err.message, true); }
      finally { open.classList.remove("is-loading"); }
      return;
    }
    const del = e.target.closest("[data-delete-saved]");
    if (del) {
      if (!confirm("Delete this saved draft?")) return;
      try {
        await api(`/api/mock/saved/${del.dataset.deleteSaved}/delete`, { method: "POST" });
        del.closest("[data-saved]").remove();
        toast("Draft deleted.");
      } catch (err) { toast(err.message, true); }
    }
  });

  // ---------------- hamleler ----------------
  async function act(path, body) {
    if (busy) return;
    busy = true;
    document.body.classList.add("mock-busy");
    try {
      const res = await api(`/api/mock/${draftId}/${path}`, { method: "POST", body: body || {} });
      apply(res);
    } catch (err) {
      if (err.status === 404) { store.del(STORE); }
      toast(err.message, true);
      // Hata cevabi da guncel durumu tasiyabilir; yoksa yeniden iste
      try { apply(await api("/api/mock/" + draftId)); } catch (e) {}
    } finally {
      busy = false;
      document.body.classList.remove("mock-busy");
    }
  }

  function apply(res) {
    view = res.view;
    if (res.pool) { pool = res.pool; poolById = new Map(pool.map((p) => [p.id, p])); }
    const fresh = new Set((res.ai || []).map((a) => a.overall));
    render(fresh);
    if (res.ai && res.ai.length && view.user_turn && !view.complete) {
      const mine = res.ai.length;
      toast(`${mine} pick${mine === 1 ? "" : "s"} made - you're on the clock.`);
    }
    if (res.message && res.ok === false) toast(res.message, true);
  }

  // ---------------- cizim ----------------
  const me = () => view.teams.find((t) => t.is_user) || null;

  function render(fresh) {
    const fmtName = view.format === "auction" ? "Auction" : "Snake";
    $("d-title").textContent = `Mock Draft · ${fmtName}`;
    $("d-sub").textContent = `${view.team_count} teams · ${view.rounds} rounds · ${view.opponent_mode === "ai" ? "AI opponents" : "you pick for every team"}`;
    renderClock();
    $("progress").style.width = (100 * view.made / view.total) + "%";
    renderFeed(fresh);
    renderAuction();
    renderResults();
    renderPool();
    renderMyTeam();
    renderLeague();
    renderLog();
    renderBoard();
    $("pool-section").hidden = view.complete;
    hydrate(document.getElementById("draft-view"));
  }

  function renderClock() {
    const el = $("clock");
    if (view.complete) {
      el.className = "clock";
      el.innerHTML = `<span class="clock-pill">Done</span><span class="clock-main">Draft complete</span>`;
      return;
    }
    const on = view.user_turn;
    el.className = "clock" + (on ? " on" : "");
    let main, sub;
    if (view.format === "auction") {
      main = view.nomination ? `${h(view.nomination.player.name)} is up` : `${h(view.on_clock ? view.on_clock.name : "")} nominates`;
      sub = `Player ${view.made + 1} of ${view.total}`;
    } else {
      main = view.opponent_mode === "manual" ? `Picking for ${h(view.on_clock.name)}` : h(view.on_clock ? view.on_clock.name : "");
      sub = `Round ${view.round} · pick ${view.pick_in_round} (${view.pick_number} of ${view.total})`;
      if (!on && view.waiting) sub += ` · you pick in ${view.waiting}`;
    }
    el.innerHTML = `<span class="clock-pill">${on ? "Your turn" : "On the clock"}</span><span class="clock-main">${main}</span><span class="clock-sub">${sub}</span>`;
  }

  function renderFeed(fresh) {
    const el = $("feed");
    const log = view.log.slice(-12).reverse();
    if (!log.length) { el.innerHTML = `<div class="small muted">The feed fills in from the first pick.</div>`; return; }
    const userSlot = me() ? me().slot : -1;
    let delay = 0;
    el.innerHTML = log.map((e) => {
      const isFresh = fresh.has(e.overall);
      const style = isFresh ? ` style="animation-delay:${(delay++) * 0.09}s"` : "";
      const label = e.price !== null && e.price !== undefined ? "$" + e.price : "#" + e.overall;
      return `<div class="feed-card${e.slot === userSlot ? " mine" : ""}${isFresh ? " fresh" : ""}"${style}>
        <div class="feed-no">${label} · ${h(e.team)}</div>
        <div class="feed-name">${h(e.player)}</div>
        <div class="feed-meta"><span class="pos pos-${h(e.pos)}">${h(e.pos)}</span> · ${h(e.nba_team)} · ADP ${Math.round(e.adp)}</div></div>`;
    }).join("");
    el.scrollLeft = 0;
  }

  function renderAuction() {
    const el = $("auction");
    const n = view.nomination;
    if (!n || view.complete) { el.innerHTML = ""; return; }
    const p = n.player;
    let controls;
    if (n.awaiting_user) {
      const min = n.high_bid + 1;
      controls = n.max_bid >= min
        ? `<form class="row" id="bid-form" style="margin-top:10px">
             <input class="input" type="number" name="amount" min="${min}" max="${n.max_bid}" value="${min}" style="max-width:140px" aria-label="Your bid">
             <button class="btn btn-primary" type="submit">Bid</button>
             <button class="btn" type="button" id="pass-btn">Pass</button>
             <span class="small muted">You can bid up to $${n.max_bid}.</span></form>`
        : `<div class="row" style="margin-top:10px"><span class="small warn">You cannot afford to raise.</span><button class="btn" id="pass-btn">Pass</button></div>`;
    } else {
      controls = `<div class="row" style="margin-top:10px"><button class="btn btn-primary" id="close-btn">Sell to the highest bidder</button></div>`;
    }
    const trail = (n.history || []).map((x) => `${h(x.team)} $${x.bid}`).join(" → ");
    el.innerHTML = `<div class="nom">
      <div class="row-between"><div><b style="font-size:1.1rem">${h(p.name)}</b> <span class="small muted">${h(p.positions.join("/"))} · ${h(p.team)} · ADP ${Math.round(p.adp)} · ESPN value $${p.auction}</span></div></div>
      <div><span class="nom-bid">$${n.high_bid}</span> <span class="muted">high bid · <b>${h(n.high_team)}</b></span></div>
      ${trail ? `<div class="tiny dim">${trail}</div>` : ""}${controls}</div>`;
    const bidForm = $("bid-form");
    if (bidForm) bidForm.addEventListener("submit", (e) => { e.preventDefault(); act("bid", { amount: +bidForm.amount.value }); });
    const pass = $("pass-btn");
    if (pass) pass.addEventListener("click", () => act("pass"));
    const close = $("close-btn");
    if (close) close.addEventListener("click", () => act("close"));
  }

  function renderResults() {
    const el = $("results");
    if (!view.complete) { el.innerHTML = ""; return; }
    const mine = me();
    const g = mine ? view.grades[String(mine.slot)] || {} : {};
    const rows = view.teams.map((t) => ({ t, g: view.grades[String(t.slot)] || {} }))
      .sort((a, b) => (a.g.rank || 99) - (b.g.rank || 99));
    el.innerHTML = `
      ${mine ? `<div class="flash flash-ok">Draft complete. Your team graded <b>${h(g.grade || "-")}</b> - ranked <b>${g.rank || "-"}</b> of ${view.teams.length}.</div>` : `<div class="flash flash-ok">Draft complete.</div>`}
      <div class="table-wrap" style="margin-bottom:16px"><table class="table">
        <thead><tr><th>#</th><th class="l">Team</th><th>Grade</th><th>Fantasy pts</th>${view.format === "auction" ? "<th>Spent</th>" : ""}</tr></thead>
        <tbody>${rows.map(({ t, g }) => `<tr><td>${g.rank || "-"}</td><td class="l"><b>${h(t.name)}</b>${t.is_user ? " (you)" : ""}</td><td>${h(g.grade || "-")}</td><td>${t.fpts.toFixed(0)}</td>${view.format === "auction" ? `<td>$${t.spent}</td>` : ""}</tr>`).join("")}</tbody>
      </table></div>`;
  }

  function fitsNeeds(p, needs) {
    const elig = view.slot_eligibility;
    return needs.some((slot) => ["PG", "SG", "SF", "PF", "C", "G", "F"].includes(slot) &&
      p.positions.some((pos) => (elig[slot] || []).includes(pos)));
  }

  function renderPool() {
    if (view.complete) return;
    const drafted = new Set(view.drafted);
    const nomId = view.nomination ? view.nomination.player.id : null;
    const needTeam = view.opponent_mode === "manual" ? view.teams.find((t) => view.on_clock && t.slot === view.on_clock.slot) : me();
    const needs = needTeam ? needTeam.needs : [];
    const needle = $("pool-search").value.trim().toLowerCase();
    const needOnly = $("need-only").checked;
    const sort = $("pool-sort").value;
    let list = pool.filter((p) => !drafted.has(p.id) && p.id !== nomId);
    if (posFilter !== "ALL") list = list.filter((p) => p.positions.includes(posFilter));
    if (needle) list = list.filter((p) => p.name.toLowerCase().includes(needle) || p.team.toLowerCase().includes(needle));
    if (needOnly) list = list.filter((p) => fitsNeeds(p, needs));
    const key = { adp: (p) => p.adp, fpts: (p) => -p.fpts, auction: (p) => -p.auction, owned: (p) => -p.owned }[sort];
    list.sort((a, b) => key(a) - key(b));
    const shown = list.slice(0, 150);
    const canAct = view.user_turn && !view.nomination;
    const verb = view.format === "auction" ? "Nominate" : "Draft";
    $("pool-body").innerHTML = shown.map((p) => {
      const inj = p.injury && p.injury !== "ACTIVE" ? `<span class="inj inj-${h(p.injury)}">${{ OUT: "OUT", INJURY_RESERVE: "IR", DAY_TO_DAY: "GTD", SUSPENSION: "SUSP" }[p.injury] || ""}</span>` : "";
      return `<tr class="${fitsNeeds(p, needs) ? "is-need" : ""}">
        <td class="l sticky-col"><div class="player-name">${h(p.name)}${inj}</div><div class="player-sub"><span class="pos pos-${h(p.pos)}">${h(p.positions.join("/"))}</span> · ${h(p.team)}</div></td>
        <td><button class="btn btn-primary draft-btn" data-pick="${p.id}" ${canAct ? "" : "disabled"}>${verb}</button></td>
        <td>${Math.round(p.adp)}</td><td>$${p.auction}</td><td><b>${p.fpts.toFixed(1)}</b></td>
        <td>${p.pts.toFixed(1)}</td><td>${p.reb.toFixed(1)}</td><td>${p.ast.toFixed(1)}</td><td>${p.stl.toFixed(1)}</td><td>${p.blk.toFixed(1)}</td></tr>`;
    }).join("") || `<tr><td class="l" colspan="10">No players match this filter.</td></tr>`;
    $("pool-count").textContent = `${list.length} available${list.length > shown.length ? ` · showing the first ${shown.length}` : ""} · green bar = fits an open roster spot`;
  }

  function pickRows(team, mine) {
    return team.picks.map((p) => `<div class="pick-row${mine ? " mine" : ""}">
      <span class="pick-no">${p.price !== null && p.price !== undefined ? "$" + p.price : "R" + p.round}</span>
      <span class="pick-name">${h(p.player.name)}</span>
      <span class="pick-meta"><span class="pos pos-${h(p.player.pos)}">${h(p.player.pos)}</span> · ${h(p.player.team)} · ${p.player.fpts.toFixed(0)} FP</span></div>`).join("");
  }

  function renderMyTeam() {
    const el = $("my-team");
    const team = me();
    if (!team) { el.innerHTML = `<p class="muted small">In manual mode every team is yours - see the League tab.</p>`; return; }
    const chips = team.needs.length ? team.needs.map((s) => `<span class="slot-chip">${h(s)}</span>`).join("") : `<span class="slot-chip done">Roster full</span>`;
    const coming = (view.upcoming || []).map((u) => `<div class="small ${u.is_user ? "good" : "muted"}">#${u.overall} (R${u.round}) ${h(u.team)}${u.is_user ? " ← you" : ""}</div>`).join("");
    el.innerHTML = `
      <div class="grid grid-2" style="margin-bottom:10px">
        <div class="kpi"><div class="kpi-label">Players</div><div class="kpi-value">${team.players}/${view.rounds}</div></div>
        <div class="kpi"><div class="kpi-label">${view.format === "auction" ? "Budget left" : "Fantasy pts"}</div><div class="kpi-value">${view.format === "auction" ? "$" + team.remaining : team.fpts.toFixed(0)}</div></div>
      </div>
      <div style="margin-bottom:10px">Open spots: ${chips}</div>
      ${pickRows(team, true) || `<p class="muted small">You have not drafted anyone yet.</p>`}
      ${coming ? `<div style="margin-top:12px"><div class="label">Coming up</div>${coming}</div>` : ""}`;
  }

  function renderLeague() {
    $("league").innerHTML = view.teams.map((t) => {
      const g = view.grades[String(t.slot)];
      return `<details class="more" style="margin-bottom:6px" ${t.is_user ? "open" : ""}>
        <summary>${h(t.name)} <span class="small muted">· ${t.players} players · ${t.fpts.toFixed(0)} FP${g ? ` · ${h(g.grade)}` : ""}${view.format === "auction" ? ` · $${t.spent}/${t.budget}` : ""}</span></summary>
        <div class="more-body">${pickRows(t, t.is_user) || `<p class="muted small">No picks yet.</p>`}</div></details>`;
    }).join("");
  }

  function renderLog() {
    const userSlot = me() ? me().slot : -1;
    const rows = view.log.slice().reverse().map((e) => `<div class="pick-row${e.slot === userSlot ? " mine" : ""}">
      <span class="pick-no">${e.price !== null && e.price !== undefined ? "$" + e.price : "#" + e.overall}</span>
      <span class="pick-name">${h(e.player)}</span><span class="pick-meta">${h(e.nba_team)} → ${h(e.team)}</span></div>`).join("");
    $("log").innerHTML = rows || `<p class="muted small">No picks yet.</p>`;
  }

  function renderBoard() {
    const { headers, rows } = view.board;
    if (!rows.length || !view.log.length) { $("board").innerHTML = `<p class="muted small" style="padding:10px">The board fills in from the first pick.</p>`; return; }
    const head = headers.map((t) => `<th class="${t.is_user ? "mine" : ""}">${h(t.name.slice(0, 16))}</th>`).join("");
    const body = rows.map((row, i) => `<tr><td class="rnd">${view.format === "auction" ? i + 1 : "R" + (i + 1)}</td>${row.map((c) => c
      ? `<td class="${c.is_user ? "mine" : ""}"><span class="bd-name">${h(c.player)}</span><span class="bd-meta">${h(c.pos)} · ${h(c.nba_team)} · ${c.price !== null && c.price !== undefined ? "$" + c.price : "#" + c.overall}</span></td>`
      : `<td class="empty"></td>`).join("")}</tr>`).join("");
    $("board").innerHTML = `<table class="board"><thead><tr><th></th>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }

  // ---------------- havuz kontrolleri ----------------
  $("pool-search").addEventListener("input", () => view && renderPool());
  $("pool-sort").addEventListener("change", () => view && renderPool());
  $("need-only").addEventListener("change", () => view && renderPool());
  $("pos-filter").addEventListener("click", (e) => {
    const b = e.target.closest("[data-pos]");
    if (!b) return;
    posFilter = b.dataset.pos;
    $("pos-filter").querySelectorAll("button").forEach((x) => x.classList.toggle("is-on", x === b));
    renderPool();
  });
  $("pool-body").addEventListener("click", (e) => {
    const b = e.target.closest("[data-pick]");
    if (b && !b.disabled) act("pick", { player_id: +b.dataset.pick });
  });

  const saveBtn = $("save-btn");
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      saveBtn.classList.add("is-loading");
      try {
        const res = await api(`/api/mock/${draftId}/save`, { method: "POST", body: { name: $("save-name").value } });
        toast(res.message);
      } catch (err) { toast(err.message, true); }
      finally { saveBtn.classList.remove("is-loading"); }
    });
  }
  void lastSeen;
})();
