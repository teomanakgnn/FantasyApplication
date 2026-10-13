// Starting Five: gecmis bir playoff macinin gizli ilk-bes oyunculari.
// Isimler tarayicida yok; her tahmini sunucu kontrol ediyor.
(function () {
  const { $, api, toast, escapeHtml: h } = window.HL;
  const data = JSON.parse($("#sf-data").textContent);
  const root = $("#sf-game");
  const KEY = "hl_sf_game", STATS = "hl_sf_stats";
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const photo = (id) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=110&h=80`;
  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[.'’-]/g, " ").replace(/\b(jr|sr|ii|iii|iv)\b/g, " ").replace(/\s+/g, " ").trim();
  const allNames = data.names.map((n) => ({ n, k: norm(n) }));

  const stats = Object.assign({ played: 0, total: 0, perfect: 0, last: 0 }, load(STATS, {}));
  let mode = "daily", game = data.game;
  let st = load(KEY, null);
  if (!st || st.puzzle !== data.puzzle) st = { puzzle: data.puzzle, found: {}, misses: [], done: false, revealed: null };

  const slotKey = (t, s) => `${t}-${s}`;
  const foundCount = () => Object.keys(st.found).length;
  const persist = () => { if (mode === "daily") save(KEY, st); };

  // ---------------- cizim ----------------
  function slotHtml(team, ti, slot, si) {
    const f = st.found[slotKey(ti, si)];
    const missed = st.done && !slot.given && !f && st.revealed;
    const who = slot.given ? slot : f || (missed ? st.revealed[ti][si] : null);
    const line = `${slot.pts} PTS · ${slot.reb} REB · ${slot.ast} AST · ${slot.min} MIN`;
    return `<div class="sf-slot ${slot.given ? "given" : f ? "found" : missed ? "missed" : "empty"}">
      <div class="sf-ph">${who ? `<img src="${photo(who.id)}" alt="" loading="lazy" onerror="this.nextElementSibling.hidden=false;this.remove()"><span hidden>${h(slot.pos || "?")}</span>` : `<span>${h(slot.pos || "?")}</span>`}</div>
      <div class="sf-info">
        <b>${who ? h(who.name) : "???"}</b>
        <span>${h(slot.pos || "")}${slot.jersey ? ` · #${h(slot.jersey)}` : ""}</span>
        <small>${line}</small>
      </div></div>`;
  }

  function render() {
    const g = game;
    const misses = st.misses.length, left = g.max_misses - misses;
    root.innerHTML = `
      <div class="sf-head card">
        <div class="sf-meta"><span class="chip chip-accent">${h(g.title)}</span><span class="dim small">${h(g.season)} season · ${new Date(g.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span></div>
        <div class="sf-score">
          ${g.teams.map((t) => `<div class="sf-team"><img src="${t.logo}" alt="" width="44" height="44"><b>${h(t.abbr)}</b><span class="sf-pts">${t.score}</span></div>`).join('<span class="sf-dash">–</span>')}
        </div>
      </div>
      ${st.done ? "" : `
      <div class="dp-search sf-search" id="sf-search">
        <input class="input" id="sf-input" type="search" autocomplete="off" spellcheck="false" placeholder="Name a starter..." aria-label="Name a starter" role="combobox" aria-expanded="false">
        <ul class="dp-list" id="sf-list" role="listbox" hidden></ul>
        <div class="small muted sf-status"><span><b>${foundCount()}</b> / ${g.hidden} found</span>
          <span class="sf-lives">${Array.from({ length: g.max_misses }, (_, i) => `<i class="${i < misses ? "used" : ""}"></i>`).join("")} ${left} miss${left === 1 ? "" : "es"} left</span>
          <button class="btn btn-sm btn-ghost" id="sf-share" type="button">Share ${foundCount()}/${g.hidden}</button>
          <button class="btn btn-sm btn-ghost" id="sf-giveup" type="button">Give up</button></div>
        ${st.misses.length ? `<div class="sf-misses tiny dim">Not starters: ${st.misses.map(h).join(", ")}</div>` : ""}
      </div>`}
      <div class="sf-teams">${g.teams.map((t, ti) => `
        <section class="sf-col" style="--team:${t.color}">
          <div class="sf-col-head"><img src="${t.logo}" alt="" width="26" height="26"> ${h(t.name)}</div>
          ${t.slots.map((s, si) => slotHtml(t, ti, s, si)).join("")}
        </section>`).join("")}</div>
      <div id="sf-result"></div>`;
    if (st.done) renderResult();
    else bindSearch();
  }

  // ---------------- arama ----------------
  function bindSearch() {
    const input = $("#sf-input"), list = $("#sf-list");
    let matches = [], active = 0;
    const known = () => new Set([...game.teams.flatMap((t) => t.slots.filter((s) => s.given).map((s) => norm(s.name))),
                                 ...Object.values(st.found).map((f) => norm(f.name)), ...st.misses.map(norm)]);
    const draw = () => {
      list.hidden = !matches.length;
      input.setAttribute("aria-expanded", matches.length ? "true" : "false");
      list.innerHTML = matches.map((m, i) => `<li><button type="button" data-name="${h(m.n)}" class="${i === active ? "is-active" : ""}"><span>${h(m.n)}</span></button></li>`).join("");
    };
    input.addEventListener("input", () => {
      const q = norm(input.value);
      const skip = known();
      matches = q.length < 2 ? [] : allNames.filter((m) => !skip.has(m.k) && (m.k.startsWith(q) || m.k.split(" ").some((w) => w.startsWith(q)))).slice(0, 8);
      active = 0; draw();
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" && matches.length) { active = (active + 1) % matches.length; draw(); e.preventDefault(); }
      else if (e.key === "ArrowUp" && matches.length) { active = (active - 1 + matches.length) % matches.length; draw(); e.preventDefault(); }
      else if (e.key === "Enter") { e.preventDefault(); if (matches[active]) guess(matches[active].n); }
    });
    list.addEventListener("mousedown", (e) => e.preventDefault());
    list.addEventListener("click", (e) => { const b = e.target.closest("[data-name]"); if (b) guess(b.dataset.name); });
  }

  let busy = false;
  async function guess(name) {
    if (busy || st.done) return;
    busy = true;
    try {
      const res = await api("/api/starting-five/guess", { method: "POST", body: { game: game.id, name } });
      if (res.hits.length) {
        res.hits.forEach((x) => { st.found[slotKey(x.team, x.slot)] = { name: x.name, id: x.id }; });
        toast(`${res.hits[0].name} started!`);
      } else {
        st.misses.push(name);
      }
      if (foundCount() >= game.hidden || st.misses.length >= game.max_misses) await end();
      persist(); render();
      const inp = $("#sf-input"); if (inp) inp.focus();
    } catch (err) { toast(err.message, true); }
    finally { busy = false; }
  }

  async function end() {
    try { st.revealed = (await api("/api/starting-five/reveal", { method: "POST", body: { game: game.id } })).teams; } catch (e) { st.revealed = null; }
    st.done = true;
    if (mode === "daily" && stats.last !== data.puzzle) {
      stats.last = data.puzzle; stats.played += 1; stats.total += foundCount();
      if (foundCount() >= game.hidden) stats.perfect += 1;
      save(STATS, stats);
      if (window.gtag) gtag("event", "startingfive_finish", { found: foundCount() });
    }
  }

  // ---------------- sonuc / paylasim ----------------
  function shareText() {
    const ticks = game.teams.map((t, ti) => t.slots.map((s, si) => (s.given ? "" : st.found[slotKey(ti, si)] ? "🟩" : "⬛")).join("")).join(" ");
    const head = mode === "daily" ? `HoopLife Starting Five #${data.puzzle}` : "HoopLife Starting Five (practice)";
    const prog = st.done ? "" : " so far";
    return `${head} · ${game.teams.map((t) => t.abbr).join(" vs ")} ${game.season}\n${foundCount()}/${game.hidden}${prog} ${ticks}\n${location.origin}/starting-five?ref=startingfive-share`;
  }
  async function share() {
    const text = shareText();
    if (window.gtag) gtag("event", "startingfive_share");
    if (navigator.share && matchMedia("(pointer: coarse)").matches) {
      try { await navigator.share({ text }); return; } catch (err) { if (err.name === "AbortError") return; }
    }
    try { await navigator.clipboard.writeText(text); toast("Result copied - paste it anywhere."); }
    catch (err) { window.prompt("Copy your result:", text); }
  }

  function renderResult() {
    const n = foundCount(), avg = stats.played ? (stats.total / stats.played).toFixed(1) : "-";
    $("#sf-result").innerHTML = `
      <div class="card sm-result">
        <div class="eyebrow">${n >= game.hidden ? "Perfect lineup" : "Final"}</div>
        <h2>${n} / ${game.hidden}</h2>
        <div class="dp-actions">
          <button class="btn btn-primary" id="sf-share" type="button">Share result</button>
          <button class="btn" id="sf-practice" type="button">Play a random game</button>
        </div>
        ${mode === "daily" ? `<div class="dp-stats"><div><b>${stats.played}</b><span>Played</span></div><div><b>${avg}</b><span>Average</span></div><div><b>${stats.perfect}</b><span>Perfect</span></div></div>
        <p class="small muted" style="margin-top:12px">A new game every day at midnight UK time. Also try <a href="/stat-match">Stat Match</a> and <a href="/daily">Mystery Player</a>.</p>` : ""}
        ${data.signed_in ? "" : `<div class="dp-keep"><div><b>Like daily games?</b><span>Free account: keep your Mystery Player streak on every device and save mock drafts.</span></div>
          <a class="btn btn-primary btn-sm" href="/register?next=%2Fstarting-five">Create free account</a></div>`}
      </div>`;
  }

  root.addEventListener("click", async (e) => {
    if (e.target.closest("#sf-share")) return share();
    if (e.target.closest("#sf-giveup")) {
      if (!confirm("Show the full lineups?")) return;
      await end(); persist(); return render();
    }
    if (e.target.closest("#sf-practice")) {
      try {
        const res = await api("/api/starting-five/random");
        mode = "practice"; game = res.game;
        st = { puzzle: -1, found: {}, misses: [], done: false, revealed: null };
        render(); window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (err) { toast(err.message, true); }
    }
  });

  render();
})();
