// 82-0 arkadas odasi: ad sec, WebSocket'e baglan; tur ve saat eighty_two.js'te
// (HL82.sync). Burada: rakibin sahasi (canli secimler), baski bildirimleri
// (rakip secti / kilitledi), sonuclar, yeni tur ve sohbet.
(function () {
  const { $, toast, escapeHtml: h } = window.HL;
  const data = JSON.parse($("#ez-data").textContent);
  const R = data.room;
  if (!R || !R.exists) return;
  const top = $("#ez-room"), panel = $("#ez-room-panel");
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const cid = load("hl_grid_cid", null) || (() => { const v = Math.random().toString(36).slice(2) + Date.now().toString(36); save("hl_grid_cid", v); return v; })();
  const photo = (id) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=110&h=80`;
  const lastName = (n) => { const w = n.split(" ").filter((x) => !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(x)); return w[w.length - 1] || n; };
  const SPOT = { PG: [50, 80], SG: [84, 62], SF: [16, 62], PF: [30, 30], C: [68, 26] };
  const SLOTS = data.config.slots;
  let name = load("hl_grid_name", "") || R.me || "";
  let ws = null, S = null, chat = [], retry = 0, round = null, queued = null;

  const send = (o) => { if (ws && ws.readyState === 1) { ws.send(JSON.stringify(o)); return true; } return false; };

  function askName() {
    top.innerHTML = `<div class="card ez-room-join"><b>Join the room</b><p class="small muted">Pick a name your friends will see. Same five spins for everyone, ${R.secs} seconds for all your picks - the better lineup wins.</p>
      <form id="ezr-nf" class="ezr-row"><input class="input" id="ezr-name" maxlength="20" value="${h(name)}" placeholder="Your name" required><button class="btn btn-primary">Join</button></form></div>`;
    $("#ezr-nf").addEventListener("submit", (e) => {
      e.preventDefault();
      const n = $("#ezr-name").value.trim();
      if (n.length < 2) return toast("Name needs 2+ letters.", true);
      name = n; save("hl_grid_name", n); top.innerHTML = ""; connect();
    });
  }

  // ---------------- baski bildirimi ----------------
  let alertTimer = null;
  function alert(text, strong) {
    let el = document.getElementById("ezr-alert");
    if (!el) { el = document.createElement("div"); el.id = "ezr-alert"; el.className = "ezr-alert"; document.body.appendChild(el); }
    el.className = `ezr-alert show ${strong ? "strong" : ""}`;
    el.innerHTML = text;
    void el.offsetWidth;                            // animasyonu yeniden baslat
    el.classList.add("pop");
    clearTimeout(alertTimer);
    alertTimer = setTimeout(() => { el.className = "ezr-alert"; }, strong ? 3200 : 2400);
    if (navigator.vibrate) navigator.vibrate(strong ? [120, 60, 120] : 60);
  }
  function flashOpp() {
    const el = document.getElementById("ez-opp-slot");
    if (!el) return;
    el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash");
  }

  // ---------------- rakip sahasi ----------------
  function court(p) {
    return `<div class="ez-court">
      <svg viewBox="0 0 100 70" preserveAspectRatio="none" aria-hidden="true" class="ez-court-svg">
        <rect x="0" y="0" width="100" height="70" class="floor"/><rect x="34" y="0" width="32" height="38" class="paint"/>
        <circle cx="50" cy="38" r="12" class="ln"/><path d="M6 0 L6 18 A44 44 0 0 0 94 18 L94 0" class="ln"/>
        <line x1="44" y1="5" x2="56" y2="5" class="ln"/><circle cx="50" cy="8" r="1.6" class="rim"/></svg>
      ${SLOTS.map((s) => {
        const x = p.picks[s], [l, t] = SPOT[s];
        return `<div class="ez-slot ${x ? "filled" : "open"}" style="left:${l}%;top:${t}%">
          <span class="ez-face">${x ? `<img src="${photo(x.id)}" alt="" onerror="this.style.visibility='hidden'">` : `<em>${s}</em>`}
            ${x && x.ovr != null ? `<i class="ez-ovr">${x.ovr}</i>` : ""}</span>
          <span class="ez-tag">${x ? h(lastName(x.name)) : s}</span>
          ${x ? `<span class="ez-sub">${s} · ${h(x.team)} '${String(x.season).slice(2)}</span>` : ""}</div>`;
      }).join("")}</div>`;
  }
  function oppHtml() {
    if (!S) return '<div class="ez-side-h"><b>Opponent</b><span>-</span></div><div class="ez-opp-empty">Waiting for a friend...</div>';
    const opps = S.players.filter((p) => !p.you);
    if (!opps.length) return '<div class="ez-side-h"><b>Opponent</b><span>-</span></div><div class="ez-opp-empty">Waiting for a friend - send the invite link.</div>';
    return opps.map((p) => `<div class="ez-opp-one"><div class="ez-side-h"><b>${h(p.name)}</b><span>${p.count}/5${p.done ? ' · <span class="good">locked</span>' : ""}${p.online ? "" : " · away"}</span></div>${court(p)}</div>`).join("");
  }
  function paintOpp() {
    const el = document.getElementById("ez-opp-slot");
    if (el) el.innerHTML = oppHtml();
  }

  // eighty_two.js cagirir
  window.HL82Room = {
    oppHtml,
    start: () => send({ t: "start" }),
    lineup: (st, final) => {
      const lineup = {};
      Object.entries(st.lineup).forEach(([slot, x]) => { lineup[slot] = { spin: x.spin, id: x.id }; });
      const msg = { t: "lineup", round: st.round, lineup, choice: st.choice, final };
      if (!send(msg)) queued = msg;
    },
  };

  // ---------------- baglanti ----------------
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/82-0/${R.code}`);
    ws.onopen = () => {
      retry = 0; send({ t: "hello", cid, name });
      if (queued) { send(queued); queued = null; }
    };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.t === "state") {
        S = m;
        if (m.round !== round) { round = m.round; window.HL82.sync(m); window.HL82.roomRound(); }
        else window.HL82.sync(m);
        paintOpp(); draw();
      } else if (m.t === "pick") {
        alert(`<b>${h(m.name)}</b> took <b>${h(m.player)}</b> at ${h(m.slot)} <span>${m.n}/5</span>`);
        flashOpp();
      } else if (m.t === "locked") {
        const mine = window.HL82.state();
        alert(`<b>${h(m.name)}</b> locked in the lineup${mine && !mine.done ? ` - <span>your clock is still running</span>` : ""}`, true);
        flashOpp();
      } else if (m.t === "joined") { toast(`${m.name} joined.`); }
      else if (m.t === "timeup") { /* eighty_two.js kilitler */ }
      else if (m.t === "round") { toast(`Round ${m.round} - new spins (${m.by}).`); }
      else if (m.t === "chatlog") { chat = m.items; drawChat(); }
      else if (m.t === "chat") { chat.push(m); chat = chat.slice(-80); drawChat(); }
      else if (m.t === "error") toast(m.text, true);
      else if (m.t === "gone") { panel.innerHTML = '<p class="muted">This room has ended. <a href="/82-0">Back to 82-0</a></p>'; }
    };
    ws.onclose = () => { if (retry < 8) { retry += 1; setTimeout(connect, 800 * retry); } };
  }

  // ---------------- panel: sonuclar + sohbet ----------------
  function drawChat() {
    const box = document.getElementById("ezr-chat-list");
    if (!box) return;
    box.innerHTML = chat.map((c) => `<div><b>${h(c.name)}</b> ${h(c.text)}</div>`).join("") || '<div class="dim small">Talk some trash.</div>';
    box.scrollTop = box.scrollHeight;
  }
  function draw() {
    if (!S) return;
    const draft = document.getElementById("ezr-msg") ? document.getElementById("ezr-msg").value : "";
    let body;
    if (S.all_done) {
      body = `<div class="ezr-winner">${S.winners.length > 1 ? `Tie: ${S.winners.map(h).join(" and ")}` : S.winners.length ? `${h(S.winners[0])} wins round ${S.round}` : "Round over"}</div>
        <div class="ezr-players">${S.players.map((p, i) => `<div class="ezr-player ${p.you ? "you" : ""}">
          <div class="ezr-ph"><span>${i + 1}. <b>${h(p.name)}</b>${p.you ? ' <small class="dim">(you)</small>' : ""}</span>
          <span>${p.wins != null ? `<b>${p.wins}-${82 - p.wins}</b> <span class="dim small">rating ${p.rating.toFixed(1)}</span>` : '<span class="dim small">no lineup</span>'}</span></div>
          ${p.lineup ? `<div class="ezr-lineup">${p.lineup.map((x) => `<span><i>${x.slot}</i> ${h(x.name)} <small>${x.team ? `${h(x.team)} '${String(x.season).slice(2)} · ` : ""}${x.ovr}</small></span>`).join("")}</div>` : ""}</div>`).join("")}</div>
        <button class="btn btn-primary" id="ezr-next" style="margin-top:10px">Rematch - new spins</button>`;
    } else if (S.phase === "waiting") {
      body = `<p class="small muted" style="margin:0">Send the link. The ${S.secs}-second clock starts for everyone at once when your friend joins.</p>`;
    } else {
      const me = S.players.find((p) => p.you);
      body = `<p class="small muted" style="margin:0">${me && me.done ? "You're locked in. Results show when the round ends." : "Ratings stay hidden until the round ends - pick fast."}</p>`;
    }
    panel.innerHTML = `<div class="ezr-wrap">
      <section class="card">
        <div class="ezr-row" style="justify-content:space-between;margin-bottom:6px"><div class="card-title" style="margin:0">Round ${S.round} <span class="dim small">· ${S.span === 1 ? "1 season" : S.span + " seasons"} · ${S.easy ? "Easy" : "Normal"} · ${S.secs}s</span></div>
          <button class="btn btn-sm" id="ezr-copy">Copy invite link</button></div>
        ${body}
      </section>
      <aside class="card ezr-chat"><div class="card-title">Chat</div><div class="ezr-chat-list" id="ezr-chat-list"></div>
        <form id="ezr-cf" class="ezr-row"><input class="input" id="ezr-msg" maxlength="300" placeholder="Message" autocomplete="off"><button class="btn btn-sm btn-primary">Send</button></form></aside>
    </div>`;
    drawChat();
    if (draft) document.getElementById("ezr-msg").value = draft;
  }

  panel.addEventListener("click", async (e) => {
    if (e.target.closest("#ezr-next")) send({ t: "next" });
    if (e.target.closest("#ezr-copy")) {
      const url = `${location.origin}/82-0/room/${R.code}`;
      if (navigator.share && matchMedia("(pointer: coarse)").matches) { try { await navigator.share({ title: "82-0 Challenge - beat my lineup", url }); return; } catch (err) { if (err.name === "AbortError") return; } }
      try { await navigator.clipboard.writeText(url); toast("Invite link copied."); } catch (err) { window.prompt("Copy the link:", url); }
    }
  });
  panel.addEventListener("submit", (e) => {
    if (e.target.id !== "ezr-cf") return;
    e.preventDefault();
    const inp = document.getElementById("ezr-msg");
    const text = inp.value.trim();
    if (text) { send({ t: "chat", text }); inp.value = ""; }
  });
  setInterval(() => send({ t: "ping" }), 25000);
  if (name.length >= 2) connect(); else askName();
})();
