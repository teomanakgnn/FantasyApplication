// 82-0 arkadas odasi: ad sec, WebSocket'e baglan, turu baslat (eighty_two.js),
// herkesin ilerlemesi, sonuclar, kazanan, yeni tur ve sohbet.
(function () {
  const { $, toast, escapeHtml: h } = window.HL;
  const data = JSON.parse($("#ez-data").textContent);
  const R = data.room;
  if (!R || !R.exists) return;
  const top = $("#ez-room"), panel = $("#ez-room-panel");
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const cid = load("hl_grid_cid", null) || (() => { const v = Math.random().toString(36).slice(2) + Date.now().toString(36); save("hl_grid_cid", v); return v; })();
  let name = load("hl_grid_name", "") || R.me || "";
  let ws = null, S = null, chat = [], retry = 0, round = null, started = false, pendingSubmit = null;

  const send = (o) => { if (ws && ws.readyState === 1) { ws.send(JSON.stringify(o)); return true; } return false; };

  function askName() {
    top.innerHTML = `<div class="card ez-room-join"><b>Join the room</b><p class="small muted">Pick a name your friends will see. Everyone gets the same five spins - the better lineup wins.</p>
      <form id="ezr-nf" class="ezr-row"><input class="input" id="ezr-name" maxlength="20" value="${h(name)}" placeholder="Your name" required><button class="btn btn-primary">Join</button></form></div>`;
    $("#ezr-nf").addEventListener("submit", (e) => {
      e.preventDefault();
      const n = $("#ezr-name").value.trim();
      if (n.length < 2) return toast("Name needs 2+ letters.", true);
      name = n; save("hl_grid_name", n); top.innerHTML = ""; connect();
    });
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/82-0/${R.code}`);
    ws.onopen = () => {
      retry = 0; send({ t: "hello", cid, name });
      if (pendingSubmit) { send(pendingSubmit); pendingSubmit = null; }
    };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.t === "state") {
        S = m;
        if (!started || m.round !== round) { started = true; round = m.round; window.HL82.roomRound(); }
        draw();
      } else if (m.t === "round") { toast(`Round ${m.round} - new spins (started by ${m.by}).`); }
      else if (m.t === "chatlog") { chat = m.items; drawChat(); }
      else if (m.t === "chat") { chat.push(m); chat = chat.slice(-80); drawChat(); }
      else if (m.t === "error") toast(m.text, true);
      else if (m.t === "gone") { panel.innerHTML = '<p class="muted">This room has ended. <a href="/82-0">Back to 82-0</a></p>'; }
    };
    ws.onclose = () => { if (retry < 8) { retry += 1; setTimeout(connect, 800 * retry); } };
  }

  // eighty_two.js cagirir
  window.HL82Room = {
    progress: (n) => send({ t: "progress", n }),
    submit: (st) => {
      const lineup = {};
      Object.entries(st.lineup).forEach(([slot, x]) => { lineup[slot] = { spin: x.spin, id: x.id }; });
      const msg = { t: "submit", round: st.round, lineup, choice: st.choice };
      if (!send(msg)) pendingSubmit = msg;
    },
  };

  function drawChat() {
    const box = document.getElementById("ezr-chat-list");
    if (!box) return;
    box.innerHTML = chat.map((c) => `<div><b>${h(c.name)}</b> ${h(c.text)}</div>`).join("") || '<div class="dim small">Say hi.</div>';
    box.scrollTop = box.scrollHeight;
  }

  function draw() {
    if (!S) return;
    const me = S.players.find((p) => p.you);
    const draft = document.getElementById("ezr-msg") ? document.getElementById("ezr-msg").value : "";
    const rows = S.players.map((p, i) => {
      const status = p.done ? (p.wins != null ? `<b>${p.wins}-${82 - p.wins}</b> <span class="dim small">rating ${p.rating.toFixed(1)}</span>` : '<span class="good small">finished</span>')
        : `<span class="dim small">spin ${Math.min(5, (p.progress || 0) + 1)} / 5${p.online ? "" : " · away"}</span>`;
      const crown = S.all_done && S.winners.includes(p.name) ? '<span class="chip chip-accent">Winner</span>' : "";
      const line = p.lineup ? `<div class="ezr-lineup">${p.lineup.map((x) => `<span><i>${x.slot}</i> ${h(x.name)} <small>${h(x.team)} '${String(x.season).slice(2)} · ${x.ovr}</small></span>`).join("")}</div>` : "";
      return `<div class="ezr-player ${p.you ? "you" : ""}"><div class="ezr-ph"><span>${S.all_done && p.rating != null ? `${i + 1}.` : ""} <b>${h(p.name)}</b>${p.you ? ' <small class="dim">(you)</small>' : ""} ${crown}</span>${status}</div>${line}</div>`;
    }).join("");
    const head = S.all_done
      ? `<div class="ezr-winner">${S.winners.length > 1 ? `Tie: ${S.winners.map(h).join(" and ")}` : `${h(S.winners[0])} wins round ${S.round}`}</div>`
      : me && me.done ? '<p class="small muted" style="margin:0 0 8px">Waiting for the others to finish. Results show when everyone is done.</p>'
      : '<p class="small muted" style="margin:0 0 8px">Build your lineup above. Others\' ratings stay hidden until you finish.</p>';
    panel.innerHTML = `<div class="ezr-wrap">
      <section class="card">
        <div class="ezr-row" style="justify-content:space-between"><div class="card-title" style="margin:0">Room · round ${S.round} <span class="dim small">· ${S.span === 1 ? "1 season" : S.span + " seasons"} · ${S.easy ? "Easy" : "Normal"}</span></div>
          <button class="btn btn-sm" id="ezr-copy">Copy invite link</button></div>
        ${head}
        <div class="ezr-players">${rows}</div>
        ${S.all_done ? '<button class="btn btn-primary" id="ezr-next" style="margin-top:10px">Next round - new spins</button>' : ""}
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
