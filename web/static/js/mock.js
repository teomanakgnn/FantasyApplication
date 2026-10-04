/*
 * Mock draft istemcisi. Durum sunucuda; burasi cizer, hamle gonderir ve
 * rakiplerin hamlelerini sahnede tek tek oynatir.
 *
 * Sunucu bir hamlede rakiplerin butun secimlerini birden yapip liste
 * olarak dondurur. Eskiden bu liste bir anda ekrana basiliyordu ve ne
 * oldugu anlasilmiyordu; simdi her secim (acik artirmada aday gosterme,
 * teklifler ve satis) secilen hizda sahnede canlandiriliyor.
 */
(function () {
  "use strict";
  const { api, toast, escapeHtml: h, hydrate } = window.HL;
  const $ = (id) => document.getElementById(id);
  const STORE = "hl_mock_draft";
  const SETTINGS = "hl_mock_settings";
  const SPEED_KEY = "hl_mock_speed";
  const SPEEDS = { slow: 1.6, normal: 1, fast: 0.35 };

  let draftId = null, view = null, pool = [], poolById = new Map();
  let posFilter = "ALL", busy = false, playing = false, skipPlayback = false;
  let hiddenDrafted = new Set();      // oynatma sirasinda henuz "secilmemis" gorunenler
  let visibleLogLength = 0;
  let speed = "normal";

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
    del(k) { try { localStorage.removeItem(k); } catch (e) {} },
  };
  const photo = (id, w = 96, hgt = 70) => id
    ? `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=${w}&h=${hgt}`
    : "/static/img/player.svg";
  const img = (id, cls = "") => `<img ${cls ? `class="${cls}"` : ""} src="${photo(id)}" alt="" loading="lazy" onerror="this.onerror=null;this.src='/static/img/player.svg'">`;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms * SPEEDS[speed]));
  async function wait(ms) {
    // Atla'ya basilirsa beklemeyi hemen bitir
    const step = 40;
    for (let t = 0; t < ms * SPEEDS[speed]; t += step) {
      if (skipPlayback) return;
      await new Promise((r) => setTimeout(r, step));
    }
  }
  void sleep;

  // ---------------- hiz ----------------
  speed = store.get(SPEED_KEY) || "normal";
  function paintSpeed() {
    document.querySelectorAll("[data-speed]").forEach((b) => b.classList.toggle("is-on", b.dataset.speed === speed));
  }
  document.querySelectorAll("[data-speed]").forEach((b) => b.addEventListener("click", () => {
    speed = b.dataset.speed; store.set(SPEED_KEY, speed); paintSpeed();
  }));
  paintSpeed();

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
      if (el instanceof RadioNodeList) Array.from(el).forEach((r) => (r.checked = r.value === v));
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
      await start(await api("/api/mock", { method: "POST", body: data }));
      // Reklam olcumu: kayittan once gelen "gercekten kullandi" sinyali
      if (window.gtag) gtag("event", "mock_start", { format: data.format || "snake", teams: +data.team_count || 0 });
    }
    catch (err) { toast(err.message, true); }
    finally { btn.classList.remove("is-loading"); }
  });

  async function start(res) {
    pool = res.pool || pool;
    poolById = new Map(pool.map((p) => [p.id, p]));
    draftId = res.view.id;
    store.set(STORE, draftId);
    view = null;
    visibleLogLength = res.view.log.length - (res.ai || []).length;
    $("setup-view").hidden = true;
    $("draft-view").hidden = false;
    window.scrollTo(0, 0);
    await apply(res);
  }

  const existing = store.get(STORE);
  if (existing) {
    $("resume-note").hidden = false;
    $("resume-btn").addEventListener("click", async () => {
      try { await start(await api("/api/mock/" + existing)); }
      catch (err) { store.del(STORE); $("resume-note").hidden = true; toast(err.message, true); }
    });
  }

  $("new-draft").addEventListener("click", () => {
    if (view && !view.complete && !confirm("Leave this draft and start a new one?")) return;
    store.del(STORE);
    draftId = null; view = null; skipPlayback = true;
    $("draft-view").hidden = true;
    $("setup-view").hidden = false;
    $("resume-note").hidden = true;
    window.scrollTo(0, 0);
  });

  document.addEventListener("click", async (e) => {
    const open = e.target.closest("[data-open-saved]");
    if (open) {
      open.classList.add("is-loading");
      try { await start(await api(`/api/mock/load/${open.dataset.openSaved}`, { method: "POST" })); }
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
    if (busy || playing) return;
    busy = true;
    document.body.classList.add("mock-busy");
    // Sunucu cevap verene kadar ikinci tiklama olmasin
    document.querySelectorAll("#draft-view [data-pick], #draft-view .bid-actions .btn").forEach((b) => (b.disabled = true));
    try {
      await apply(await api(`/api/mock/${draftId}/${path}`, { method: "POST", body: body || {} }));
    } catch (err) {
      if (err.status === 404) store.del(STORE);
      toast(err.message, true);
      try { await apply(await api("/api/mock/" + draftId)); } catch (e) {}
    } finally {
      busy = false;
      document.body.classList.remove("mock-busy");
    }
  }

  async function apply(res) {
    const previous = view;
    view = res.view;
    if (res.pool) { pool = res.pool; poolById = new Map(pool.map((p) => [p.id, p])); }
    const events = res.ai || [];
    const mineLen = previous ? previous.log.length : view.log.length - events.length;
    // Kullanicinin kendi hamlesi (varsa) rakiplerinkinden once gorunsun
    visibleLogLength = Math.max(0, view.log.length - events.length);
    if (visibleLogLength < mineLen) visibleLogLength = mineLen;
    if (events.length) {
      await playback(events);
    }
    visibleLogLength = view.log.length;
    hiddenDrafted = new Set();
    render(new Set(events.map((e) => e.overall)));
    if (res.message && res.ok === false) toast(res.message, true);
  }

  // ---------------- oynatma ----------------
  async function playback(events) {
    playing = true; skipPlayback = false;
    document.body.classList.add("mock-busy");
    hiddenDrafted = new Set(events.map((e) => e.player_id).filter(Boolean));
    renderStatic();
    renderPool();   // dugmeler oynatma boyunca pasif gorunsun
    for (const ev of events) {
      if (skipPlayback) break;
      if (view.format === "auction") await playAuction(ev);
      else await playPick(ev);
      hiddenDrafted.delete(ev.player_id);
      visibleLogLength += 1;
      renderFeed(new Set([ev.overall]));
      renderPool();
      $("progress").style.width = (100 * visibleLogLength / view.total) + "%";
      $("progress-label").textContent = `${visibleLogLength} of ${view.total} picks`;
    }
    playing = false;
    document.body.classList.remove("mock-busy");
  }

  function stageHtml(cls, pill, title, sub, body, skip = true) {
    return { cls, html: `<div class="stage-top"><span class="stage-pill">${pill}</span><span class="stage-title">${title}</span>
      ${sub ? `<span class="stage-sub">${sub}</span>` : ""}
      ${skip ? `<button class="btn btn-sm btn-ghost stage-skip" data-skip>Skip ▸</button>` : ""}</div>${body || ""}` };
  }
  function setStage(s) {
    const el = $("stage");
    el.className = "stage" + (s.cls ? " " + s.cls : "");
    el.innerHTML = s.html;
  }
  $("stage").addEventListener("click", (e) => { if (e.target.closest("[data-skip]")) skipPlayback = true; });

  async function playPick(ev) {
    const p = poolById.get(ev.player_id) || {};
    setStage(stageHtml("", "On the clock", h(ev.team), `Round ${ev.round} · pick ${ev.pick_in_round || ""} (#${ev.overall})`,
      `<div class="thinking"><i></i><i></i><i></i> ${h(ev.team)} is picking…</div>`));
    await wait(650);
    if (skipPlayback) return;
    setStage(stageHtml("", "The pick is in", h(ev.team), `Round ${ev.round} · #${ev.overall}`,
      `<div class="announce">${img(ev.player_id)}<div><div class="announce-team">${h(ev.team)} select</div>
        <div class="announce-name">${h(ev.player)}</div>
        <div class="announce-meta"><span class="pos pos-${h(ev.pos)}">${h((p.positions || [ev.pos]).join("/"))}</span> · ${h(ev.nba_team)} · ADP ${Math.round(ev.adp)}${p.fpts ? ` · ${p.fpts.toFixed(1)} FP` : ""}</div></div></div>`));
    await wait(1000);
  }

  async function playAuction(ev) {
    const p = poolById.get(ev.player_id) || {};
    const head = `<div class="announce">${img(ev.player_id)}<div><div class="announce-team">${h(ev.nominator || ev.team)} nominates</div>
      <div class="announce-name">${h(ev.player)}</div>
      <div class="announce-meta"><span class="pos pos-${h(ev.pos)}">${h((p.positions || [ev.pos]).join("/"))}</span> · ${h(ev.nba_team)} · ESPN value $${p.auction || "-"}</div></div>
      <div class="announce-price" id="stage-price">$1</div></div>`;
    setStage(stageHtml("is-bid", "Auction", "Bidding", `player ${ev.overall} of ${view.total}`, head + `<div class="ladder" id="stage-ladder"></div>`));
    await wait(700);
    const bids = ev.bids || [];
    for (let i = 0; i < bids.length && !skipPlayback; i++) {
      const b = bids[i];
      const ladder = $("stage-ladder"), price = $("stage-price");
      if (!ladder) return;
      ladder.querySelectorAll("span").forEach((s) => s.classList.remove("lead"));
      ladder.insertAdjacentHTML("beforeend", `<span class="lead ${b.team === (me() || {}).name ? "mine" : ""}"><b>$${b.bid}</b> ${h(b.team)}</span>`);
      price.textContent = "$" + b.bid;
      await wait(520);
    }
    if (skipPlayback) return;
    const ladder = $("stage-ladder");
    if (ladder) ladder.insertAdjacentHTML("afterend", `<span class="sold">SOLD · ${h(ev.team)} · $${ev.price}</span>`);
    const price = $("stage-price");
    if (price) price.textContent = "$" + ev.price;
    await wait(1000);
  }

  // ---------------- cizim ----------------
  const me = () => (view ? view.teams.find((t) => t.is_user) : null) || null;

  function render(fresh) {
    renderStatic();
    renderStage();
    renderFeed(fresh);
    renderResults();
    renderPool();
    renderMyTeam();
    renderLeague();
    renderLog();
    renderBoard();
    $("pool-section").hidden = view.complete;
    hydrate(document.getElementById("draft-view"));
  }

  function renderStatic() {
    const fmtName = view.format === "auction" ? "Auction" : "Snake";
    $("d-title").textContent = `Mock Draft · ${fmtName}`;
    $("d-sub").textContent = `${view.team_count} teams · ${view.rounds} rounds · ${view.opponent_mode === "ai" ? "AI opponents" : "you pick for every team"}`;
    $("progress").style.width = (100 * visibleLogLength / view.total) + "%";
    $("progress-label").textContent = `${visibleLogLength} of ${view.total} picks`;
  }

  function suggestions(limit = 3) {
    const team = view.opponent_mode === "manual" ? view.teams.find((t) => view.on_clock && t.slot === view.on_clock.slot) : me();
    const needs = team ? team.needs : [];
    const drafted = new Set(view.drafted);
    const avail = pool.filter((p) => !drafted.has(p.id)).sort((a, b) => a.adp - b.adp);
    const fits = avail.filter((p) => fitsNeeds(p, needs));
    const out = fits.slice(0, limit);
    for (const p of avail) { if (out.length >= limit) break; if (!out.includes(p)) out.push(p); }
    return out.sort((a, b) => a.adp - b.adp);
  }

  function renderStage() {
    if (view.complete) {
      const mine = me(); const g = mine ? view.grades[String(mine.slot)] || {} : {};
      setStage(stageHtml("", "Draft complete", mine ? `Your team graded ${h(g.grade || "-")}` : "All picks are in",
        mine ? `ranked ${g.rank || "-"} of ${view.teams.length}` : "", "", false));
      return;
    }
    const n = view.nomination;
    if (n) return renderBidStage(n);
    if (view.user_turn) {
      const verb = view.format === "auction" ? "Nominate" : "Draft";
      const who = view.opponent_mode === "manual" ? `Picking for ${h(view.on_clock.name)}` : "You're on the clock";
      const sub = view.format === "auction" ? "put a player up for auction"
        : `Round ${view.round} · pick ${view.pick_in_round} (#${view.pick_number})`;
      const cards = suggestions().map((p) => `<div class="suggest-card">${img(p.id)}<div style="min-width:0">
          <div class="pname" style="font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${h(p.name)}</div>
          <div class="tiny dim"><span class="pos pos-${h(p.pos)}">${h(p.positions.join("/"))}</span> · ADP ${Math.round(p.adp)} · ${p.fpts.toFixed(0)} FP</div></div>
          <button class="btn btn-primary" data-pick="${p.id}">${verb}</button></div>`).join("");
      setStage(stageHtml("is-user", "Your turn", who, sub, `<div class="tiny dim" style="margin-bottom:6px">Best available for your open spots - or pick anyone from the list below.</div><div class="suggest">${cards}</div>`, false));
      return;
    }
    setStage(stageHtml("", "Waiting", "Opponents are picking", "", `<div class="thinking"><i></i><i></i><i></i></div>`, false));
  }

  function renderBidStage(n) {
    const p = n.player;
    const ladder = (n.history || []).map((b, i, arr) => `<span class="${i === arr.length - 1 ? "lead" : ""} ${b.team === (me() || {}).name ? "mine" : ""}"><b>$${b.bid}</b> ${h(b.team)}</span>`).join("");
    const top = `<div class="bid-box">${img(p.id)}<div style="min-width:0">
        <div class="announce-team">${h(n.nominator || "")} nominated</div>
        <div class="announce-name">${h(p.name)}</div>
        <div class="announce-meta"><span class="pos pos-${h(p.pos)}">${h(p.positions.join("/"))}</span> · ${h(p.team)} · ADP ${Math.round(p.adp)} · ESPN value $${p.auction} · ${p.fpts.toFixed(1)} FP</div></div>
        <div class="bid-high"><b>$${n.high_bid}</b><span>${n.high_is_user ? "your bid - you're winning" : "high bid · " + h(n.high_team)}</span></div></div>
        <div class="ladder">${ladder}</div>`;
    let actions;
    if (n.awaiting_user) {
      const min = n.high_bid + 1, max = n.max_bid;
      if (max >= min) {
        const quick = [1, 5, 10].map((d) => Math.min(max, n.high_bid + d)).filter((v, i, a) => v >= min && a.indexOf(v) === i);
        actions = `<form class="bid-actions" id="bid-form">
          ${quick.map((v) => `<button class="btn btn-primary" type="button" data-bid="${v}">Bid $${v}</button>`).join("")}
          ${max > (quick[quick.length - 1] || 0) ? `<button class="btn" type="button" data-bid="${max}">Max $${max}</button>` : ""}
          <input class="input" type="number" name="amount" min="${min}" max="${max}" value="${min}" aria-label="Custom bid">
          <button class="btn" type="submit">Bid</button>
          <button class="btn btn-ghost" type="button" id="pass-btn">Pass</button>
          <span class="tiny dim">You can go up to $${max} ($1 is held back for each open spot).</span></form>`;
      } else {
        actions = `<div class="bid-actions"><span class="small warn">You can't afford to raise on this player.</span><button class="btn" id="pass-btn">Pass</button></div>`;
      }
    } else {
      actions = `<div class="bid-actions"><button class="btn btn-primary" id="close-btn">Sell to ${h(n.high_team)} for $${n.high_bid}</button></div>`;
    }
    setStage(stageHtml(n.awaiting_user ? "is-bid is-user" : "is-bid", n.awaiting_user ? "Your bid" : "Auction",
      n.awaiting_user ? "Raise or pass" : "Bidding closed", `player ${view.made + 1} of ${view.total}`, top + actions, false));
    const bidForm = $("bid-form");
    if (bidForm) {
      bidForm.addEventListener("submit", (e) => { e.preventDefault(); act("bid", { amount: +bidForm.amount.value }); });
      bidForm.querySelectorAll("[data-bid]").forEach((b) => b.addEventListener("click", () => act("bid", { amount: +b.dataset.bid })));
    }
    const pass = $("pass-btn"); if (pass) pass.addEventListener("click", () => act("pass"));
    const close = $("close-btn"); if (close) close.addEventListener("click", () => act("close"));
  }

  function renderFeed(fresh) {
    const el = $("feed");
    const log = view.log.slice(0, visibleLogLength).slice(-12).reverse();
    if (!log.length) { el.innerHTML = `<div class="small muted">The feed fills in from the first pick.</div>`; return; }
    const userSlot = me() ? me().slot : -1;
    el.innerHTML = log.map((e) => {
      const label = e.price !== null && e.price !== undefined ? "$" + e.price : "#" + e.overall;
      return `<div class="feed-card${e.slot === userSlot ? " mine" : ""}${fresh && fresh.has(e.overall) ? " fresh" : ""}">
        ${img(e.player_id)}<div class="feed-body"><div class="feed-no">${label} · ${h(e.team)}</div>
        <div class="feed-name">${h(e.player)}</div>
        <div class="feed-no"><span class="pos pos-${h(e.pos)}">${h(e.pos)}</span> · ${h(e.nba_team)}</div></div></div>`;
    }).join("");
    el.scrollLeft = 0;
  }

  function renderResults() {
    const el = $("results");
    if (!view.complete) { el.innerHTML = ""; return; }
    const rows = view.teams.map((t) => ({ t, g: view.grades[String(t.slot)] || {} })).sort((a, b) => (a.g.rank || 99) - (b.g.rank || 99));
    el.innerHTML = `<div class="table-wrap" style="margin-bottom:16px"><table class="table">
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
    if (!view || view.complete) return;
    const drafted = new Set(view.drafted.filter((id) => !hiddenDrafted.has(id)));
    const nomId = view.nomination && !playing ? view.nomination.player.id : null;
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
    const canAct = view.user_turn && !view.nomination && !playing;
    const verb = view.format === "auction" ? "Nominate" : "Draft";
    const INJ = { OUT: "OUT", INJURY_RESERVE: "IR", DAY_TO_DAY: "GTD", SUSPENSION: "SUSP" };
    const head = `<div class="prow head"><span></span><span>Player</span><span class="num">ADP</span><span class="num">$</span><span class="num">FP</span><span class="num">PTS</span><span></span></div>`;
    $("pool-list").innerHTML = head + (shown.map((p) => {
      const inj = p.injury && p.injury !== "ACTIVE" && INJ[p.injury] ? `<span class="inj inj-${h(p.injury)}">${INJ[p.injury]}</span>` : "";
      return `<div class="prow${fitsNeeds(p, needs) ? " is-need" : ""}">${img(p.id)}
        <div style="min-width:0"><div class="pname">${h(p.name)}${inj}</div><div class="psub"><span class="pos pos-${h(p.pos)}">${h(p.positions.join("/"))}</span> · ${h(p.team)}</div></div>
        <span class="num">${Math.round(p.adp)}</span><span class="num">$${p.auction}</span><span class="num"><b>${p.fpts.toFixed(1)}</b></span><span class="num">${p.pts.toFixed(1)}</span>
        <button class="btn btn-primary" data-pick="${p.id}" ${canAct ? "" : "disabled"}>${verb}</button>
        <div class="mlabel">ADP ${Math.round(p.adp)} · $${p.auction} · <b>${p.fpts.toFixed(1)} FP</b> · ${p.pts.toFixed(1)} pts · ${p.reb.toFixed(1)} reb · ${p.ast.toFixed(1)} ast</div>
      </div>`;
    }).join("") || `<div class="prow"><span></span><span class="muted">No players match this filter.</span></div>`);
    let note = `${list.length} available${list.length > shown.length ? ` · showing ${shown.length}` : ""} · green edge = fits an open roster spot`;
    if (!canAct && !view.complete) note += view.nomination ? " · finish the auction above first" : " · buttons open on your turn";
    $("pool-count").textContent = note;
  }

  function pickRows(team, mine) {
    return team.picks.map((p) => `<div class="pick-row${mine ? " mine" : ""}">
      <span class="pick-no">${p.price !== null && p.price !== undefined ? "$" + p.price : "R" + p.round}</span>
      <span class="pick-name">${h(p.player.name)}</span>
      <span class="pick-meta"><span class="pos pos-${h(p.player.pos)}">${h(p.player.pos)}</span> · ${h(p.player.team)} · ${p.player.fpts.toFixed(0)} FP</span></div>`).join("");
  }

  function lineupHtml(team) {
    return `<div class="lineup">${(team.lineup || []).map((s) => s.player
      ? `<div class="slot-row"><span class="slot-tag">${h(s.slot)}</span><span class="pname">${h(s.player.name)}</span><span class="meta"><span class="pos pos-${h(s.player.pos)}">${h(s.player.pos)}</span> · ${s.player.price !== null && s.player.price !== undefined ? "$" + s.player.price : "R" + s.player.round}</span></div>`
      : `<div class="slot-row empty"><span class="slot-tag">${h(s.slot)}</span><span>Open</span><span></span></div>`).join("")}</div>`;
  }

  function renderMyTeam() {
    const el = $("my-team");
    const team = me() || (view.opponent_mode === "manual" ? view.teams.find((t) => view.on_clock && t.slot === view.on_clock.slot) : null);
    if (!team) { el.innerHTML = `<p class="muted small">Every team is yours in manual mode - see the League tab.</p>`; return; }
    const coming = (view.upcoming || []).map((u) => `<div class="small ${u.is_user ? "good" : "muted"}">#${u.overall} (R${u.round}) ${h(u.team)}${u.is_user ? " ← you" : ""}</div>`).join("");
    el.innerHTML = `
      <div class="grid grid-2" style="margin-bottom:10px">
        <div class="kpi"><div class="kpi-label">Players</div><div class="kpi-value">${team.players}/${view.rounds}</div></div>
        <div class="kpi"><div class="kpi-label">${view.format === "auction" ? "Budget left" : "Fantasy pts"}</div><div class="kpi-value">${view.format === "auction" ? "$" + team.remaining : team.fpts.toFixed(0)}</div></div>
      </div>
      ${team.lineup ? lineupHtml(team) : pickRows(team, true)}
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
      ? `<td class="${c.is_user ? "mine" : ""} p-${h(c.pos)}"><span class="bd-name">${h(c.player)}</span><span class="bd-meta">${h(c.pos)} · ${h(c.nba_team)} · ${c.price !== null && c.price !== undefined ? "$" + c.price : "#" + c.overall}</span></td>`
      : `<td class="empty"></td>`).join("")}</tr>`).join("");
    $("board").innerHTML = `<table class="board"><thead><tr><th></th>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }

  // ---------------- kontroller ----------------
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
  document.getElementById("draft-view").addEventListener("click", (e) => {
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
})();
