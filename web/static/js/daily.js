// Gunluk gizemli oyuncu. Cevap sunucuda; burada yalnizca tahminler,
// ilerleme ve istatistik (bu cihazda, localStorage) tutuluyor.
(function () {
  const { $, api, toast, escapeHtml } = window.HL;
  const data = JSON.parse($("#dp-data").textContent);
  const GAME_KEY = "hl_daily_game";
  const STATS_KEY = "hl_daily_stats";
  const logo = (abbr) => `https://a.espncdn.com/i/teamlogos/nba/500/${String(abbr).toLowerCase()}.png`;

  function load(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch (e) { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* gizli sekme */ }
  }

  let game = load(GAME_KEY, null);
  if (!game || game.puzzle !== data.puzzle) {
    game = { puzzle: data.puzzle, rows: [], done: false, won: false, answer: null };
  }
  const stats = Object.assign({ played: 0, wins: 0, streak: 0, best: 0, last: 0, lastWin: 0,
                                dist: [0, 0, 0, 0, 0, 0, 0, 0] }, load(STATS_KEY, {}));

  const input = $("#dp-input");
  const list = $("#dp-list");
  const rowsEl = $("#dp-rows");
  const resultEl = $("#dp-result");
  const countEl = $("#dp-count");
  let busy = false;
  let matches = [];
  let active = -1;

  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[.'’-]/g, " ").replace(/\s+/g, " ").trim();
  const players = data.players.map((p) => Object.assign({ key: norm(p.name) }, p));

  // ---------------- arama ----------------
  function search(q) {
    q = norm(q);
    if (!q) return [];
    const guessed = new Set(game.rows.map((r) => r.id));
    const starts = [], contains = [];
    for (const p of players) {
      if (guessed.has(p.id)) continue;
      if (p.key.startsWith(q) || p.key.split(" ").some((w) => w.startsWith(q))) starts.push(p);
      else if (p.key.includes(q)) contains.push(p);
      if (starts.length >= 8) break;
    }
    return starts.concat(contains).slice(0, 8);
  }

  function renderList() {
    const open = matches.length > 0 || norm(input.value).length > 1;
    list.hidden = !open;
    input.setAttribute("aria-expanded", open ? "true" : "false");
    if (!open) return;
    if (!matches.length) {
      list.innerHTML = '<li class="dp-empty">No active player by that name.</li>';
      return;
    }
    list.innerHTML = matches.map((p, i) => `
      <li role="option" aria-selected="${i === active}"><button type="button" data-id="${p.id}" class="${i === active ? "is-active" : ""}">
        <img src="${logo(p.team)}" alt="" loading="lazy"><span>${escapeHtml(p.name)}</span><span class="dp-team">${escapeHtml(p.team)}</span>
      </button></li>`).join("");
  }

  input.addEventListener("input", () => { matches = search(input.value); active = matches.length ? 0 : -1; renderList(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" && matches.length) { active = (active + 1) % matches.length; renderList(); e.preventDefault(); }
    else if (e.key === "ArrowUp" && matches.length) { active = (active - 1 + matches.length) % matches.length; renderList(); e.preventDefault(); }
    else if (e.key === "Enter") { e.preventDefault(); if (active >= 0 && matches[active]) guess(matches[active].id); }
    else if (e.key === "Escape") { matches = []; renderList(); }
  });
  list.addEventListener("mousedown", (e) => e.preventDefault());   // secim inputu bulaniklastirmasin
  list.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-id]");
    if (btn) guess(btn.dataset.id);
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#dp-search")) { list.hidden = true; input.setAttribute("aria-expanded", "false"); }
  });

  // ---------------- tahmin ----------------
  async function guess(id) {
    if (busy || game.done) return;
    busy = true;
    input.disabled = true;
    try {
      const res = await api("/api/daily/guess", { method: "POST", body: { puzzle: data.puzzle, player_id: id } });
      game.rows.push({ id: res.player.id, name: res.player.name, cells: res.cells });
      input.value = "";
      matches = [];
      renderList();
      if (res.correct) {
        game.done = true; game.won = true; game.answer = res.answer;
      } else if (game.rows.length >= data.max) {
        const rev = await api("/api/daily/reveal", { method: "POST", body: { puzzle: data.puzzle, guesses: game.rows.map((r) => r.id) } });
        game.done = true; game.won = false; game.answer = rev.answer;
      }
      save(GAME_KEY, game);
      if (game.done) finish();
      render(true);
    } catch (err) {
      toast(err.message, true);
      if (err.status === 409) setTimeout(() => location.reload(), 1500);
    } finally {
      busy = false;
      input.disabled = game.done;
      if (!game.done) input.focus();
    }
  }

  function finish() {
    if (stats.last === data.puzzle) return;
    stats.last = data.puzzle;
    stats.played += 1;
    if (game.won) {
      stats.wins += 1;
      stats.dist[game.rows.length - 1] += 1;
      stats.streak = stats.lastWin === data.puzzle - 1 ? stats.streak + 1 : 1;
      stats.lastWin = data.puzzle;
    } else {
      stats.streak = 0;
    }
    stats.best = Math.max(stats.best, stats.streak);
    save(STATS_KEY, stats);
    if (window.gtag) gtag("event", "daily_finish", { won: game.won, guesses: game.rows.length });
  }

  // ---------------- cizim ----------------
  function tile(c, i) {
    const arrow = c.dir === "up" ? '<span class="dp-arrow" aria-label="higher">▲</span>'
                : c.dir === "down" ? '<span class="dp-arrow" aria-label="lower">▼</span>' : "";
    const body = c.key === "team"
      ? `<img src="${logo(c.value)}" alt=""><small>${escapeHtml(c.value)}</small>`
      : `<span>${escapeHtml(c.value)}</span>${arrow}`;
    return `<div class="dp-tile ${c.status}" style="--i:${i}" title="${c.key}">${body}</div>`;
  }

  function render(animateLast) {
    rowsEl.innerHTML = game.rows.slice().reverse().map((r, idx) => {
      const n = game.rows.length - idx;
      const won = game.won && n === game.rows.length;
      return `<div class="dp-row${animateLast && idx === 0 ? " is-new" : ""}">
        <div class="dp-name"><span class="dim">${n}.</span> ${escapeHtml(r.name)}${won ? ' <span class="chip chip-accent">CORRECT</span>' : ""}</div>
        <div class="dp-cells">${r.cells.map(tile).join("")}</div>
      </div>`;
    }).join("");
    const left = data.max - game.rows.length;
    countEl.textContent = game.done ? "" : `Guess ${game.rows.length + 1} of ${data.max} · ${left} left`;
    input.disabled = game.done;
    $("#dp-search").hidden = game.done;
    renderResult();
  }

  function shareText() {
    const grid = game.rows.map((r) => r.cells.map((c) => c.status === "hit" ? "🟩" : c.status === "near" ? "🟨" : "⬛").join("")).join("\n");
    const score = game.won ? game.rows.length : "X";
    return `HoopLife Mystery Player #${data.puzzle} ${score}/${data.max}\n${grid}\n${location.origin}/daily?ref=daily-share`;
  }

  async function share() {
    const text = shareText();
    if (window.gtag) gtag("event", "daily_share");
    if (navigator.share && matchMedia("(pointer: coarse)").matches) {
      try { await navigator.share({ text }); return; } catch (e) { if (e.name === "AbortError") return; }
    }
    try {
      await navigator.clipboard.writeText(text);
      toast("Result copied - paste it anywhere.");
    } catch (e) {
      window.prompt("Copy your result:", text);
    }
  }

  let timer = null;
  const nextAt = Date.now() + data.next_in * 1000;
  function tick() {
    const el = $("#dp-next");
    if (!el) return;
    const ms = nextAt - Date.now();
    if (ms <= 0) { el.innerHTML = '<a href="/daily">A new player is up - play now</a>'; clearInterval(timer); return; }
    const s = Math.floor(ms / 1000);
    const pad = (v) => String(v).padStart(2, "0");
    el.textContent = `Next player in ${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
  }

  function renderResult() {
    if (!game.done || !game.answer) { resultEl.innerHTML = ""; return; }
    const a = game.answer;
    const streak = stats.lastWin >= data.puzzle - 1 ? stats.streak : 0;
    const winPct = stats.played ? Math.round(100 * stats.wins / stats.played) : 0;
    const maxDist = Math.max(1, ...stats.dist);
    const dist = stats.dist.map((v, i) => {
      const today = game.won && i === game.rows.length - 1;
      return `<div><span>${i + 1}</span><i class="${today ? "is-today" : ""}" style="width:${Math.max(8, 100 * v / maxDist)}%">${v}</i></div>`;
    }).join("");
    resultEl.innerHTML = `
      <div class="card dp-result">
        <div class="eyebrow">${game.won ? `Solved in ${game.rows.length}/${data.max}` : "Out of guesses"}</div>
        <div class="dp-answer">
          <img src="${escapeHtml(a.headshot)}" alt="" onerror="this.style.visibility='hidden'">
          <div><h2>${escapeHtml(a.name)}</h2><div class="muted small">${escapeHtml(a.team_name)}</div></div>
        </div>
        <div class="dp-actions">
          <button class="btn btn-primary" id="dp-share" type="button">Share result</button>
          <a class="btn btn-ghost" href="/mock-draft">Run a mock draft</a>
        </div>
        <div class="small muted dp-next" id="dp-next"></div>
        <div class="dp-stats">
          <div><b>${stats.played}</b><span>Played</span></div>
          <div><b>${winPct}</b><span>Win %</span></div>
          <div><b>${streak}</b><span>Streak</span></div>
          <div><b>${stats.best}</b><span>Best</span></div>
        </div>
        <div class="dp-dist">${dist}</div>
      </div>`;
    $("#dp-share").addEventListener("click", share);
    tick();
    clearInterval(timer);
    timer = setInterval(tick, 1000);
  }

  render(false);
})();
