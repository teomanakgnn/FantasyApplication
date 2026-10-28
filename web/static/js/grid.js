// 3x3 Grid: her kareye hem satirin hem sutunun kategorisine uyan bir oyuncu.
// Modlar: gunluk grid (9 tahmin, bu cihazda kayitli), bota karsi XOX,
// arkadasa karsi canli XOX + sohbet (WebSocket). Cevaplar sunucuda kontrol edilir.
(function () {
  const { $, api, toast, escapeHtml: h } = window.HL;
  const D = JSON.parse($("#gr-data").textContent);
  const app = $("#gr-app");
  const KEY = "hl_grid_game", STATS = "hl_grid_stats";
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const photo = (id, w = 110) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=${w}&h=${Math.round(w * 0.727)}`;
  const logo = (abbr) => `https://a.espncdn.com/i/teamlogos/nba/500/${abbr}.png`;
  const last = (n) => n.split(" ").filter((w) => !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(w)).slice(-1)[0] || n;
  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z ]/g, "");
  const LINES = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]];

  // ---------------- oyuncu listesi ve secici ----------------
  let PLAYERS = null;
  async function players() {
    if (!PLAYERS) {
      const d = await api("/api/grid/players");
      PLAYERS = d.players.map((p) => ({ ...p, k: norm(p.name) }));
    }
    return PLAYERS;
  }
  players().catch(() => {});

  // Hucre icin oyuncu sec: arama kutusu + liste. used: kullanilmis kimlikler
  function pick(title, used) {
    return new Promise((resolve) => {
      const box = document.createElement("div");
      box.className = "gr-pick";
      box.innerHTML = `<div class="gr-pick-card card" role="dialog" aria-label="Pick a player">
        <div class="gr-pick-head"><b>${title}</b><button class="btn btn-sm btn-ghost" data-x>Close</button></div>
        <input class="input" id="gr-q" placeholder="Type a player's name" autocomplete="off" autocapitalize="off" spellcheck="false">
        <ul class="gr-res" id="gr-res"></ul></div>`;
      document.body.appendChild(box);
      const q = box.querySelector("#gr-q"), res = box.querySelector("#gr-res");
      let list = [], active = 0;
      const close = (val) => { box.remove(); document.removeEventListener("keydown", esc); resolve(val || null); };
      const esc = (e) => { if (e.key === "Escape") close(); };
      document.addEventListener("keydown", esc);
      box.addEventListener("click", (e) => {
        if (e.target === box || e.target.closest("[data-x]")) return close();
        const b = e.target.closest("[data-pid]");
        if (b && !b.disabled) close(list.find((p) => p.id === b.dataset.pid));
      });
      const draw = () => {
        res.innerHTML = list.map((p, i) => `<li><button data-pid="${p.id}" class="${i === active ? "is-active" : ""}" ${used.has(p.id) ? "disabled" : ""}>
          <img src="${photo(p.id, 64)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'"><span><b>${h(p.name)}</b><small>${h(p.years)}${used.has(p.id) ? " · already used" : ""}</small></span></button></li>`).join("")
          || (q.value.trim().length >= 2 ? '<li class="dim small" style="padding:8px">No player by that name in the 1985-2026 pool.</li>' : "");
      };
      q.addEventListener("input", async () => {
        const s = norm(q.value.trim());
        if (s.length < 2) { list = []; return draw(); }
        const all = await players();
        const words = s.split(" ").filter(Boolean);
        list = all.filter((p) => words.every((w) => p.k.split(" ").some((x) => x.startsWith(w)))).slice(0, 8);
        if (list.length < 8 && s.length >= 3) list = list.concat(all.filter((p) => !list.includes(p) && p.k.includes(s)).slice(0, 8 - list.length));
        active = 0; draw();
      });
      q.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown") { active = Math.min(active + 1, list.length - 1); draw(); e.preventDefault(); }
        else if (e.key === "ArrowUp") { active = Math.max(active - 1, 0); draw(); e.preventDefault(); }
        else if (e.key === "Enter" && list[active] && !used.has(list[active].id)) { e.preventDefault(); close(list[active]); }
      });
      setTimeout(() => q.focus(), 30);
    });
  }

  // ---------------- grid cizimi ----------------
  function head(c) {
    return `<div class="gr-head ${c.kind}">${c.kind === "team" ? `<img src="${logo(c.logo)}" alt="" onerror="this.remove()">` : ""}<span>${h(c.label)}</span></div>`;
  }
  // cell(i) -> {html, cls, click}
  function board(g, cell) {
    let out = `<div class="gr-board"><div class="gr-corner"></div>${g.cols.map(head).join("")}`;
    g.rows.forEach((r, ri) => {
      out += head(r);
      g.cols.forEach((c, ci) => {
        const i = ri * 3 + ci, x = cell(i);
        out += `<button class="gr-cell ${x.cls || ""}" data-cell="${i}" ${x.click ? "" : "disabled"} aria-label="${h(r.label)} and ${h(c.label)}">${x.html || ""}</button>`;
      });
    });
    return out + "</div>";
  }
  const filled = (card, mark) => `${mark ? `<i class="gr-mark">${mark}</i>` : ""}<img src="${photo(card.id)}" alt="" onerror="this.style.visibility='hidden'"><b>${h(last(card.name))}</b>`;
  const cellTitle = (g, i) => `${h(g.rows[Math.floor(i / 3)].label)} <span class="dim">+</span> ${h(g.cols[i % 3].label)}`;

  function lineOf(b, mark) { return LINES.find((l) => l.every((i) => b[i] === mark)) || null; }
  function result(b, turns) {
    for (const m of ["X", "O"]) if (lineOf(b, m)) return m;
    if (b.every(Boolean)) return "draw";
    if (turns >= D.max_turns) { const x = b.filter((v) => v === "X").length, o = b.filter((v) => v === "O").length; return x > o ? "X" : o > x ? "O" : "draw"; }
    return null;
  }

  // =============== GUNLUK GRID ===============
  function daily(practice) {
    const g = practice || D.daily;
    const isDaily = !practice;
    let st = isDaily ? load(KEY, null) : null;
    // v2: ilk gun cevaplar yanlis grid'e karsi kontrol ediliyordu; o kayitlar bir kez sifirlanir
    if (!st || st.puzzle !== D.puzzle || st.v !== 2) st = { v: 2, puzzle: D.puzzle, cells: Array(9).fill(null), left: D.guesses, wrong: [], done: false };
    if (!isDaily) st = { cells: Array(9).fill(null), left: D.guesses, wrong: [], done: false };
    let reveal = null;
    const persist = () => { if (isDaily) save(KEY, st); };

    function finish() {
      st.done = true; persist();
      if (isDaily) {
        const s = Object.assign({ played: 0, last: 0, streak: 0, best: 0, total: 0 }, load(STATS, {}));
        if (s.last !== D.puzzle) {
          s.streak = s.last === D.puzzle - 1 ? s.streak + 1 : 1;
          s.played += 1; s.last = D.puzzle;
          const score = st.cells.filter(Boolean).length;
          s.best = Math.max(s.best, score); s.total += score;
          save(STATS, s);
        }
        if (window.gtag) gtag("event", "grid_done", { score: st.cells.filter(Boolean).length });
      }
      api(`/api/grid/reveal?seed=${encodeURIComponent(g.seed)}`).then((r) => { reveal = r.cells; render(); }).catch(() => {});
      render();
    }

    async function guess(i) {
      if (st.done || st.cells[i]) return;
      const used = new Set(st.cells.filter(Boolean).map((c) => c.id));
      const p = await pick(cellTitle(g, i), used);
      if (!p) return;
      try {
        const r = await api("/api/grid/check", { method: "POST", body: { seed: g.seed, cell: i, pid: p.id } });
        st.left -= 1;
        if (r.ok) { st.cells[i] = r.player; toast(`${r.player.name} - correct.`); }
        else { st.wrong.push({ cell: i, name: r.player.name }); toast(`${r.player.name} does not fit that square.`, true); }
        persist();
        if (st.left <= 0 || st.cells.every(Boolean)) return finish();
        render();
      } catch (err) { toast(err.message, true); }
    }

    function shareText() {
      const rows = [0, 1, 2].map((r) => [0, 1, 2].map((c) => (st.cells[r * 3 + c] ? "🟩" : "⬜")).join("")).join("\n");
      return `HoopLife 3x3 Grid #${D.puzzle} - ${st.cells.filter(Boolean).length}/9\n${rows}\n${location.origin}/grid?ref=grid-share${window.HL.inv()}`;
    }

    function render() {
      const score = st.cells.filter(Boolean).length;
      const top = `<div class="gr-status"><span>${isDaily ? `Grid #${D.puzzle}` : "Practice grid"}</span>
        <b>${st.done ? `${score}/9` : `${st.left} guess${st.left === 1 ? "" : "es"} left`}</b></div>`;
      const html = board(g, (i) => {
        const c = st.cells[i];
        if (c) return { html: filled(c), cls: "ok" };
        if (st.done) {
          const rv = reveal && reveal[i];
          return { html: rv ? `<small class="gr-count">${rv.count} answers</small>${rv.top[0] ? `<em>${h(rv.top[0].name)}</em>` : ""}` : "", cls: "miss", click: !!rv };
        }
        return { html: `<small class="gr-count">${g.counts[Math.floor(i / 3)][i % 3]} answers</small>`, click: true };
      });
      const wrong = st.wrong.length ? `<p class="small dim gr-wrong">Missed: ${st.wrong.map((w) => h(w.name)).join(", ")}</p>` : "";
      const done = st.done ? `<div class="card gr-done">
          <b>${score === 9 ? "Perfect grid." : score >= 6 ? "Strong grid." : "Grid done."} ${score}/9</b>
          <p class="small muted">Tap an empty square to see who would have fit.</p>
          <div class="gr-actions">${isDaily ? '<button class="btn btn-primary" id="gr-share">Share result</button>' : ""}
          <button class="btn" id="gr-new">${isDaily ? "Play a random grid" : "Another random grid"}</button>
          ${isDaily ? `<span class="small dim">Next grid in ${Math.max(1, Math.round((D.next_in || 0) / 3600))}h</span>` : '<button class="btn btn-ghost" id="gr-back">Back to today\'s grid</button>'}</div></div>` : `
        <div class="gr-actions">${isDaily ? '<button class="btn btn-ghost" id="gr-new">Random grid</button>' : '<button class="btn btn-ghost" id="gr-back">Back to today\'s grid</button>'}
        <button class="btn btn-ghost" id="gr-give">Give up</button></div>`;
      app.innerHTML = top + html + wrong + done;
    }

    app.onclick = async (e) => {
      const c = e.target.closest(".gr-cell");
      if (c) {
        const i = +c.dataset.cell;
        if (st.done && reveal) {
          const rv = reveal[i];
          return window.HL.openModal(`<h3 style="margin:0 0 6px">${cellTitle(g, i)}</h3><p class="small muted">${rv.count} players fit. The best known:</p>
            <ul class="gr-reveal">${rv.top.map((p) => `<li><img src="${photo(p.id, 64)}" alt="" onerror="this.style.visibility='hidden'"><b>${h(p.name)}</b> <span class="dim small">${h(p.years)}</span></li>`).join("")}</ul>`);
        }
        return guess(i);
      }
      if (e.target.closest("#gr-share")) {
        const text = shareText();
        if (navigator.share && matchMedia("(pointer: coarse)").matches) { try { await navigator.share({ text }); return; } catch (err) { if (err.name === "AbortError") return; } }
        try { await navigator.clipboard.writeText(text); toast("Result copied."); } catch (err) { window.prompt("Copy:", text); }
      }
      if (e.target.closest("#gr-new")) {
        try { const ng = await api("/api/grid/new"); daily(ng); } catch (err) { toast(err.message, true); }
      }
      if (e.target.closest("#gr-back")) daily();
      if (e.target.closest("#gr-give") && confirm("End this grid and see the answers?")) finish();
    };
    if (st.done) finish(); else render();
  }

  // =============== BOTA KARSI ===============
  function bot() {
    let level = load("hl_grid_level", "medium");
    let g = null, b, cards, turns, turn, used, log, over, busy = false;

    async function start() {
      app.innerHTML = '<div class="spinner"></div>';
      try { g = await api("/api/grid/new"); } catch (err) { app.innerHTML = `<p class="muted">${h(err.message)}</p>`; return; }
      b = Array(9).fill(null); cards = Array(9).fill(null); turns = 0; turn = "X"; used = new Set(); log = []; over = null;
      render();
    }
    function advance() {
      turns += 1; turn = turn === "X" ? "O" : "X";
      over = result(b, turns);
      render();
      if (!over && turn === "O") setTimeout(botTurn, 700);
    }
    async function botTurn() {
      busy = true; render();
      try {
        const m = await api("/api/grid/bot", { method: "POST", body: { seed: g.seed, board: b, used: [...used], level, turn: turns } });
        await new Promise((r) => setTimeout(r, 600));
        if (m.ok) { b[m.cell] = "O"; cards[m.cell] = m.player; used.add(m.player.id); }
        log.unshift({ side: "O", ok: m.ok, cell: m.cell, name: m.player ? m.player.name : "nobody" });
      } catch (err) { log.unshift({ side: "O", ok: false, cell: null, name: "passed" }); }
      busy = false; advance();
    }
    async function mine(i) {
      if (over || busy || turn !== "X" || b[i]) return;
      const p = await pick(cellTitle(g, i), used);
      if (!p) return;
      busy = true;
      try {
        const r = await api("/api/grid/check", { method: "POST", body: { seed: g.seed, cell: i, pid: p.id } });
        if (r.ok) { b[i] = "X"; cards[i] = r.player; used.add(p.id); }
        log.unshift({ side: "X", ok: r.ok, cell: i, name: r.player.name });
        if (!r.ok) toast(`${r.player.name} does not fit - bot's turn.`, true);
      } catch (err) { toast(err.message, true); busy = false; return; }
      busy = false; advance();
    }
    function render() {
      const win = over && over !== "draw" ? lineOf(b, over) || [] : [];
      const status = over ? (over === "X" ? "You win." : over === "O" ? "The bot wins." : "Draw.")
        : turn === "X" ? "Your move - pick a square." : "Bot is thinking...";
      app.innerHTML = `
        <div class="gr-status"><span>Vs bot · <select class="input gr-level" id="gr-level" aria-label="Bot level">
          ${["easy", "medium", "hard"].map((l) => `<option value="${l}" ${l === level ? "selected" : ""}>${l[0].toUpperCase() + l.slice(1)}</option>`).join("")}</select></span>
          <b class="${over === "X" ? "good" : over === "O" ? "bad" : ""}">${status}</b></div>
        ${board(g, (i) => ({ html: cards[i] ? filled(cards[i], b[i]) : "", cls: `${b[i] ? "own-" + b[i] : ""} ${win.includes(i) ? "win" : ""}`, click: !over && !b[i] && turn === "X" && !busy }))}
        <p class="small dim">You are <b>X</b> and go first. Name a player to claim a square; a wrong name passes the turn. Three in a row wins${""} - after ${D.max_turns} turns the most squares wins.</p>
        <div class="gr-log">${log.slice(0, 6).map((l) => `<div><b class="m-${l.side}">${l.side === "X" ? "You" : "Bot"}</b> ${l.ok ? "claimed" : "missed"}${l.cell != null ? "" : ""}: ${h(l.name)}</div>`).join("")}</div>
        <div class="gr-actions"><button class="btn ${over ? "btn-primary" : "btn-ghost"}" id="gr-restart">${over ? "Play again" : "New game"}</button></div>`;
    }
    app.onclick = (e) => {
      const c = e.target.closest(".gr-cell");
      if (c) return mine(+c.dataset.cell);
      if (e.target.closest("#gr-restart")) start();
    };
    app.onchange = (e) => { if (e.target.id === "gr-level") { level = e.target.value; save("hl_grid_level", level); } };
    start();
  }

  // =============== ARKADAS: davet ===============
  function friend() {
    app.innerHTML = `<div class="card gr-invite">
      <b>Play a friend, live</b>
      <p class="small muted">Create a room and send the link. You both see the same grid, take turns naming players and chat while you play. No account needed. Each move has ${D.turn_secs} seconds.</p>
      <button class="btn btn-primary" id="gr-create">Create a room</button></div>`;
    app.onclick = async (e) => {
      if (!e.target.closest("#gr-create")) return;
      try { const r = await api("/api/grid/room", { method: "POST", body: {} }); location.href = r.url; } catch (err) { toast(err.message, true); }
    };
  }

  // =============== CANLI ODA ===============
  function room() {
    if (!D.exists) {
      app.innerHTML = `<div class="card gr-invite"><b>This room has ended</b><p class="small muted">Rooms close a few hours after the last player leaves.</p><a class="btn btn-primary" href="/grid">Start a new one</a></div>`;
      return;
    }
    const cid = load("hl_grid_cid", null) || (() => { const v = Math.random().toString(36).slice(2) + Date.now().toString(36); save("hl_grid_cid", v); return v; })();
    let name = load("hl_grid_name", "") || D.me || "";
    let S = null, ws = null, chat = [], retry = 0, tick = null;

    function askName() {
      app.innerHTML = `<div class="card gr-invite"><b>Join the match</b><p class="small muted">Pick a name your friend will see.</p>
        <form id="gr-nf" class="gr-actions"><input class="input" id="gr-name" maxlength="20" value="${h(name)}" placeholder="Your name" required><button class="btn btn-primary">Join</button></form></div>`;
      $("#gr-nf").addEventListener("submit", (e) => {
        e.preventDefault();
        const n = $("#gr-name").value.trim();
        if (n.length < 2) return toast("Name needs 2+ letters.", true);
        name = n; save("hl_grid_name", n); connect();
      });
    }
    function connect() {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws/grid/${D.room}`);
      ws.onopen = () => { retry = 0; ws.send(JSON.stringify({ t: "hello", cid, name })); };
      ws.onmessage = (ev) => {
        const m = JSON.parse(ev.data);
        if (m.t === "state") { S = m; S.at = Date.now(); render(); }
        else if (m.t === "chatlog") { chat = m.items; drawChat(); }
        else if (m.t === "chat") { chat.push(m); chat = chat.slice(-80); drawChat(); }
        else if (m.t === "move") toast(`${m.side === (S && S.you) ? "You" : m.side}: ${m.player.name} - ${m.ok ? "correct" : "does not fit"}`, !m.ok);
        else if (m.t === "error") toast(m.text, true);
        else if (m.t === "info") toast(m.text);
        else if (m.t === "gone") { D.exists = false; room(); }
      };
      ws.onclose = () => { if (D.exists !== false && retry < 8) { retry += 1; setTimeout(connect, 800 * retry); } };
    }
    const send = (o) => { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); };

    function drawChat() {
      const box = document.getElementById("gr-chat-list");
      if (!box) return;
      box.innerHTML = chat.map((c) => `<div><b class="${c.side ? "m-" + c.side : "dim"}">${h(c.name)}</b> ${h(c.text)}</div>`).join("") || '<div class="dim small">Say hi.</div>';
      box.scrollTop = box.scrollHeight;
    }
    function render() {
      if (!S) return;
      const me = S.you, g = S.grid;
      const win = S.result && S.result !== "draw" ? lineOf(S.board, S.result) || [] : [];
      const seat = (s) => `<span class="gr-seat m-${s} ${S.turn === s && !S.result ? "on" : ""}"><b>${s}</b> ${S.seats[s] ? h(S.seats[s]) : '<span class="dim">waiting...</span>'}${S.seats[s] && !S.online[s] ? ' <small class="dim">(away)</small>' : ""}${me === s ? ' <small class="dim">(you)</small>' : ""}</span>`;
      const ready = S.seats.X && S.seats.O;
      const left = S.left != null ? Math.max(0, S.left - Math.floor((Date.now() - S.at) / 1000)) : null;
      const status = S.result ? (S.result === "draw" ? "Draw." : S.result === me ? "You win." : me ? `${h(S.seats[S.result] || S.result)} wins.` : `${S.result} wins.`)
        : !ready ? "Waiting for your friend - send the link." : S.turn === me ? `Your move · ${left}s` : `${h(S.seats[S.turn] || S.turn)} is thinking · ${left}s`;
      const prevList = document.getElementById("gr-chat-list");
      const draft = document.getElementById("gr-msg") ? document.getElementById("gr-msg").value : "";
      app.innerHTML = `
        <div class="gr-room">
          <div class="gr-main">
            <div class="gr-seats">${seat("X")}<span class="dim">vs</span>${seat("O")}</div>
            <div class="gr-status"><span>${S.watchers ? `${S.watchers} watching` : "Live match"}</span><b class="${S.result && S.result === me ? "good" : ""}">${status}</b></div>
            ${board(g, (i) => ({ html: S.cards[i] ? filled(S.cards[i], S.board[i]) : "", cls: `${S.board[i] ? "own-" + S.board[i] : ""} ${win.includes(i) ? "win" : ""}`,
              click: !S.result && ready && me === S.turn && !S.board[i] }))}
            <div class="gr-log">${S.log.slice().reverse().map((l) => `<div><b class="m-${l.side}">${h(S.seats[l.side] || l.side)}</b> ${l.text ? h(l.text) : `${l.ok ? "claimed" : "missed"}: ${h(l.player)}`}</div>`).join("")}</div>
            <div class="gr-actions">
              <button class="btn btn-sm" id="gr-copy">Copy invite link</button>
              ${S.result && me ? `<button class="btn btn-sm btn-primary" id="gr-again" ${S.rematch.includes(me) ? "disabled" : ""}>${S.rematch.includes(me) ? "Waiting for rematch..." : "Rematch"}</button>` : ""}
              <a class="btn btn-sm btn-ghost" href="/grid">Leave</a>
            </div>
            ${!me ? '<p class="small dim">Both seats are taken - you are watching. You can still chat.</p>' : ""}
          </div>
          <aside class="card gr-chat"><div class="card-title">Chat</div><div class="gr-chat-list" id="gr-chat-list"></div>
            <form id="gr-cf" class="gr-cf"><input class="input" id="gr-msg" maxlength="300" placeholder="Message" autocomplete="off"><button class="btn btn-sm btn-primary">Send</button></form></aside>
        </div>`;
      drawChat();
      const inp = document.getElementById("gr-msg");
      if (draft) inp.value = draft;
      if (prevList && document.activeElement === document.body) inp.focus();
    }
    app.onclick = async (e) => {
      const c = e.target.closest(".gr-cell");
      if (c && S) {
        const i = +c.dataset.cell;
        const used = new Set(S.cards.filter(Boolean).map((x) => x.id));
        const p = await pick(cellTitle(S.grid, i), used);
        if (p) send({ t: "guess", cell: i, pid: p.id });
        return;
      }
      if (e.target.closest("#gr-copy")) {
        const url = `${location.origin}/grid/room/${D.room}`;
        if (navigator.share && matchMedia("(pointer: coarse)").matches) { try { await navigator.share({ title: "3x3 Grid - play me", url }); return; } catch (err) { if (err.name === "AbortError") return; } }
        try { await navigator.clipboard.writeText(url); toast("Invite link copied."); } catch (err) { window.prompt("Copy the link:", url); }
      }
      if (e.target.closest("#gr-again")) send({ t: "rematch" });
    };
    app.onsubmit = (e) => {
      if (e.target.id !== "gr-cf") return;
      e.preventDefault();
      const inp = document.getElementById("gr-msg");
      const text = inp.value.trim();
      if (text) { send({ t: "chat", text }); inp.value = ""; }
    };
    // Geri sayim: her saniye yalnizca durum satiri
    tick = setInterval(() => {
      if (!S || S.result || S.left == null) return;
      const el = app.querySelector(".gr-status b");
      if (!el) return;
      const left = Math.max(0, S.left - Math.floor((Date.now() - S.at) / 1000));
      el.textContent = el.textContent.replace(/\d+s$/, `${left}s`);
    }, 1000);
    setInterval(() => send({ t: "ping" }), 25000);
    if (name.length >= 2) connect(); else askName();
  }

  // ---------------- giris ----------------
  if (D.mode === "room") return room();
  if (D.mode === "gone") { app.innerHTML = '<p class="muted">Unknown room. <a href="/grid">Back to the grid</a></p>'; return; }
  const modes = { daily: () => daily(), bot, friend };
  const nav = document.getElementById("gr-modes");
  const go = (m) => {
    nav.querySelectorAll("button").forEach((b) => b.classList.toggle("is-on", b.dataset.mode === m));
    app.onclick = null; app.onchange = null; app.onsubmit = null;
    modes[m]();
    history.replaceState(null, "", m === "daily" ? "/grid" : `/grid#${m}`);
  };
  nav.addEventListener("click", (e) => { const b = e.target.closest("[data-mode]"); if (b) go(b.dataset.mode); });
  go(modes[location.hash.slice(1)] ? location.hash.slice(1) : "daily");
})();
