// NBA Auction: tum kurallar sunucuda (services/auction.py). Burada lobi, canli durum,
// teklif dugmeleri, saat, sonuc ekrani ve paylasim. Puanlar oyun bitene kadar gelmez.
(function () {
  const { $, toast, escapeHtml: h, api } = window.HL;
  const D = JSON.parse($("#au-data").textContent);
  const app = $("#au-app");
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const cid = load("hl_grid_cid", null) || (() => { const v = Math.random().toString(36).slice(2) + Date.now().toString(36); save("hl_grid_cid", v); return v; })();
  const photo = (id) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=220&h=160`;
  const initials = (n) => n.split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]).join("");
  let name = load("hl_grid_name", "") || D.me || "";
  let ws = null, S = null, chat = [], retry = 0, leftAt = 0, lastSold = 0, shownRound = null;

  const send = (o) => { if (ws && ws.readyState === 1) { ws.send(JSON.stringify(o)); return true; } return false; };
  const era = (p) => (p.cur ? `${p.y0}-now` : `${p.y0}-${String(p.y1).slice(-2)}`);
  const SCORING = { judge: "100-point score", h2h3: "H2H: PTS REB AST", h2h5: "H2H: 5 categories" };
  const modeLabel = () => `${S.blind ? "Blind draft" : "Open draft"} · ${SCORING[S.scoring]}`;
  const face = (p, cls) => `<span class="au-face ${cls || ""}">${p.photo ? `<img src="${photo(p.id)}" alt="" onerror="this.remove()">` : ""}<em>${h(initials(p.name))}</em></span>`;

  // ---------------- lobi ----------------
  function lobby() {
    const mode = load("hl_auction_mode", { blind: "0", scoring: "judge" });
    app.innerHTML = `<div class="au-lobby">
      <section class="card au-how">
        <div class="card-title">How it works</div>
        <ol>
          <li><b>Open, raise or pass.</b> Whoever opens a player must bid at least $1. Then you take turns: raise, or pass and your opponent buys at their bid. Every player gets sold.</li>
          <li><b>Budget for five.</b> You start with $${D.money}, and every open spot must keep at least $1.</li>
          <li><b>Opponent out of money?</b> When they only have $1 per open spot left, you can pass a player to them and they must take him for $1.</li>
          <li><b>Pick any five.</b> Positions do not matter. Ratings stay hidden, only names and career numbers are shown.</li>
        </ol>
        <div class="card-title" style="margin-top:14px">Draft</div>
        <ul class="au-modes">
          <li><b>Open:</b> you see the player you are bidding on.</li>
          <li><b>Blind:</b> you only see a category, like "Career 8+ assists per game" or "San Antonio Spurs, 1990-2000". The player is revealed once he is sold.</li>
        </ul>
        <div class="card-title" style="margin-top:14px">Scoring</div>
        <ul class="au-modes">
          <li><b>100-point score:</b> talent counts most, then defense, shooting, playmaking and rebounding.</li>
          <li><b>H2H 3 categories:</b> career PTS, REB and AST of your five are added up. Win 2 of 3.</li>
          <li><b>H2H 5 categories:</b> adds STL and BLK. Win 3 of 5. The oldest legends sit out, since their steals and blocks are not on record.</li>
        </ul>
      </section>
      <section class="card au-start">
        <label class="field"><span>Your name</span><input class="input" id="au-name" maxlength="20" value="${h(name)}" placeholder="Your name"></label>
        <div class="field"><span>Draft</span><div class="seg seg-block" id="au-blind">${[["0", "Open"], ["1", "Blind"]].map(([v, l]) => `<button type="button" data-v="${v}" class="${v === mode.blind ? "is-on" : ""}">${l}</button>`).join("")}</div></div>
        <div class="field"><span>Scoring</span><div class="seg seg-block" id="au-scoring">${[["judge", "100 pts"], ["h2h3", "H2H 3"], ["h2h5", "H2H 5"]].map(([v, l]) => `<button type="button" data-v="${v}" class="${v === mode.scoring ? "is-on" : ""}">${l}</button>`).join("")}</div></div>
        <button class="btn btn-primary btn-block" id="au-friend">Play a friend</button>
        <button class="btn btn-block" id="au-solo">Play the bot</button>
        <p class="tiny dim" style="margin:0">No account needed. A friend joins with your invite link.</p>
      </section>
    </div>`;
    const go = async (solo, btn) => {
      const n = $("#au-name").value.trim();
      if (n.length < 2) return toast("Name needs 2+ letters.", true);
      name = n; save("hl_grid_name", n);
      btn.disabled = true;
      try {
        save("hl_auction_mode", mode);
        const r = await api("/api/auction/room", { method: "POST", body: { solo, blind: mode.blind === "1", scoring: mode.scoring } });
        if (window.gtag) gtag("event", "auction_start", { mode: solo ? "bot" : "friend", blind: mode.blind, scoring: mode.scoring });
        location.href = r.url;
      } catch (err) { toast(err.message, true); btn.disabled = false; }
    };
    [["#au-blind", "blind"], ["#au-scoring", "scoring"]].forEach(([sel, key]) => {
      $(sel).addEventListener("click", (e) => {
        const b = e.target.closest("[data-v]");
        if (!b) return;
        mode[key] = b.dataset.v;
        $(sel).querySelectorAll("[data-v]").forEach((x) => x.classList.toggle("is-on", x === b));
      });
    });
    $("#au-friend").onclick = (e) => go(false, e.target);
    $("#au-solo").onclick = (e) => go(true, e.target);
  }

  function askName() {
    app.innerHTML = `<section class="card au-join"><div class="card-title">Join the auction</div>
      <p class="small muted">You and your friend get $${D.money} each to bid on NBA players and build a five.</p>
      <form id="au-nf" class="ezr-row"><input class="input" id="au-name" maxlength="20" value="${h(name)}" placeholder="Your name" required><button class="btn btn-primary">Join</button></form></section>`;
    $("#au-nf").addEventListener("submit", (e) => {
      e.preventDefault();
      const n = $("#au-name").value.trim();
      if (n.length < 2) return toast("Name needs 2+ letters.", true);
      name = n; save("hl_grid_name", n); connect();
    });
  }

  // ---------------- baglanti ----------------
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/auction/${D.room.code}`);
    ws.onopen = () => { retry = 0; send({ t: "hello", cid, name }); };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.t === "state") { apply(m); }
      else if (m.t === "joined") toast(`${m.name} joined.`);
      else if (m.t === "round") toast(`New game - ${m.by} asked for a rematch.`);
      else if (m.t === "chatlog") { chat = m.items; paintChat(); }
      else if (m.t === "chat") { chat.push(m); chat = chat.slice(-80); paintChat(); }
      else if (m.t === "error") { toast(m.text, true); paint(); }
      else if (m.t === "gone") { retry = 99; app.innerHTML = '<p class="muted">This game has ended. <a href="/auction">Start a new one</a></p>'; }
    };
    ws.onclose = () => { if (retry < 8) { retry += 1; setTimeout(connect, 800 * retry); } };
  }

  function apply(m) {
    const prev = S;
    S = m;
    leftAt = m.left != null ? performance.now() + m.left * 1000 : 0;
    if (shownRound !== m.round) { shownRound = m.round; lastSold = 0; if (m.phase === "done" && window.gtag) gtag("event", "auction_end", {}); }
    const sold = m.events.filter((e) => e.kind === "sold");
    if (prev && prev.round === m.round && sold.length && soldCount(m) > lastSold) {
      const e = sold[sold.length - 1];
      if (e.seat !== m.you) toast(`${e.seat_name} bought ${e.name} for $${e.price}`);
      if (navigator.vibrate && e.seat !== m.you) navigator.vibrate(50);
    }
    lastSold = soldCount(m);
    paint();
  }
  const soldCount = (m) => m.teams[0].roster.length + m.teams[1].roster.length;

  // ---------------- ekran ----------------
  function teamHtml(t, active) {
    const you = t.seat === S.you;
    const slots = [];
    for (let i = 0; i < D.roster; i++) {
      const p = t.roster[i];
      slots.push(p ? `<li>${face(p)}<div><b>${h(p.name)}</b><small>${p.pos} · ${era(p)}</small></div><i>$${p.price}</i></li>` : '<li class="open"><span class="au-face"></span><div><small>Open spot</small></div></li>');
    }
    return `<section class="card au-team ${active ? "active" : ""} ${you ? "you" : ""}">
      <div class="au-team-h"><span><b>${h(t.name || "Waiting...")}</b>${you ? ' <small class="dim">you</small>' : ""}${t.online || !t.name ? "" : ' <small class="warn">away</small>'}</span><strong>$${t.money}</strong></div>
      <ul class="au-slots">${slots.join("")}</ul></section>`;
  }

  function lotHtml() {
    const p = S.lot;
    const bidder = S.bidder != null ? S.teams[S.bidder] : null;
    let info;
    if (p.blind) {
      info = `<span class="au-face big au-mystery"><em>?</em></span><div class="au-lot-info"><div class="small muted">Mystery player</div><h2>${h(p.category)}</h2></div>`;
    } else {
      const bits = [`${Number(p.pts).toFixed(1)} PTS`, `${Number(p.reb).toFixed(1)} REB`, `${Number(p.ast).toFixed(1)} AST`];
      if (S.scoring === "h2h5") bits.push(`${Number(p.stl).toFixed(1)} STL`, `${Number(p.blk).toFixed(1)} BLK`);
      const honors = [p.mvp ? `${p.mvp}x MVP` : "", p.ring ? `${p.ring}x champion` : "", p.as ? `${p.as}x All-Star` : ""].filter(Boolean);
      info = `${face(p, "big")}<div class="au-lot-info"><h2>${h(p.name)}</h2>
          <div class="small muted">${p.pos} · ${p.cur ? `active since ${p.y0}` : `${p.y0}-${p.y1}`}</div>
          <div class="au-stats">${bits.map((b) => `<span>${b}</span>`).join("")}</div>
          ${honors.length ? `<div class="small">${honors.join(" · ")}</div>` : '<div class="small dim">No major honors</div>'}</div>`;
    }
    const sold = S.events.filter((e) => e.kind === "sold");
    const last = S.blind && sold.length ? sold[sold.length - 1] : null;
    return `<section class="card au-lot">
      <div class="au-mode tiny dim">${modeLabel()}</div>
      ${last ? `<div class="au-reveal small">Revealed: <b>${h(last.name)}</b> went to ${h(last.seat_name)} for $${last.price}</div>` : ""}
      <div class="au-lot-top"><span class="dim small">Pick ${S.lot_no}</span><span class="au-clock"><i id="au-clock-bar"></i></span><span class="small" id="au-clock-txt"></span></div>
      <div class="au-lot-main">${info}
        <div class="au-bid"><small>${bidder ? h(bidder.name) : "No bid"}</small><strong class="${S.bidder === S.you ? "good" : ""}">$${S.bid}</strong></div></div>
      ${controlsHtml()}
</section>`;
  }

  function controlsHtml() {
    const me = S.you;
    if (S.turn !== me) {
      const other = S.turn != null ? S.teams[S.turn] : null;
      return `<p class="au-wait small muted">${other ? `${h(other.name)} is deciding...` : ""}</p>`;
    }
    const min = S.bid + 1;
    const opts = [...new Set([min, min + 1, min + 4, S.limit].filter((v) => v >= min && v <= S.limit))];
    const opp = S.teams[1 - me];
    const pass = S.bid > 0 ? `Pass - ${h(opp.name)} pays $${S.bid}` : S.can_give ? `Pass him to ${h(opp.name)} for $1` : "";
    const hint = S.can_give ? `${h(opp.name)} is out of money: bid $1 to take him, or pass and they must.` : S.bid > 0 ? "" : "You open this player, so you must bid at least $1.";
    return `<div class="au-ctl">${opts.map((v, i) => `<button class="btn ${i === 0 ? "btn-primary" : ""}" data-bid="${v}">${v === S.limit && opts.length > 1 ? "Max " : ""}$${v}</button>`).join("")}
      ${pass ? `<button class="btn btn-ghost au-pass" data-pass>${pass}</button>` : ""}</div>
      ${S.limit > min ? `<form id="au-bf" class="au-manual"><label for="au-amt">Your bid</label><span class="au-dollar">$</span><input class="input" id="au-amt" type="number" inputmode="numeric" min="${min}" max="${S.limit}" step="1" value="${min}"><button class="btn">Bid</button></form>` : ""}
      <div class="tiny dim">${hint ? `${hint} ` : ""}You can bid up to $${S.limit}. Every open spot keeps $1.</div>`;
  }

  function logHtml() {
    const rows = S.events.slice().reverse().filter((e) => e.kind !== "bid").slice(0, 8).map((e) => {
      if (e.kind === "sold") return `<div><b>${h(e.seat_name)}</b> ${e.given ? "was passed" : "bought"} ${h(e.name)} <span class="dim">for $${e.price}</span></div>`;
      return `<div class="dim">${h(e.seat_name)} ${e.timeout ? "ran out of time" : "passed"}</div>`;
    }).join("");
    return rows ? `<section class="card au-log"><div class="card-title">Auction log</div>${rows}</section>` : "";
  }

  function chatHtml() {
    if (S.solo) return "";
    return `<aside class="card ezr-chat au-chat"><div class="card-title">Chat</div><div class="ezr-chat-list" id="au-chat-list"></div>
      <form id="au-cf" class="ezr-row"><input class="input" id="au-msg" maxlength="300" placeholder="Message" autocomplete="off"><button class="btn btn-sm btn-primary">Send</button></form></aside>`;
  }
  function paintChat() {
    const box = document.getElementById("au-chat-list");
    if (!box) return;
    box.innerHTML = chat.map((c) => `<div><b>${h(c.name)}</b> ${h(c.text)}</div>`).join("") || '<div class="dim small">Talk some trash.</div>';
    box.scrollTop = box.scrollHeight;
  }

  function resultHtml() {
    const R = S.result, [a, b] = R.teams;
    const title = R.winner == null ? "It's a tie" : `${h(S.teams[R.winner].name)} wins`;
    const team = (t, i) => `<div class="au-score ${R.winner === i ? "won" : ""}">
      <div class="au-score-h"><b>${h(S.teams[i].name)}</b><strong>${t.total.toFixed(1)}</strong></div>
      ${t.note ? `<p class="small muted">${h(t.note)}</p>` : ""}
      <ul class="au-final">${t.lineup.map((x) => `<li><i>${x.slot}</i><span>${h(x.name)}</span><em>${x.ovr}</em>${x.price ? `<small>$${x.price}</small>` : ""}</li>`).join("")}</ul>
      <div class="au-cats">${t.cats.map((c) => `<div><span>${c.label}</span><span class="au-meter"><i style="width:${Math.round(100 * c.v / c.max)}%"></i></span><b>${c.v.toFixed(1)}<small>/${c.max}</small></b></div>`).join("")}
        ${t.chemistry ? `<div><span>Real teammates</span><span class="au-meter"><i style="width:${Math.round(100 * t.chemistry / 3)}%"></i></span><b>+${t.chemistry}</b></div>` : ""}</div>
      ${t.mates.length ? `<p class="tiny dim">Played together: ${t.mates.slice(0, 3).map((m) => h(m.join(" and "))).join("; ")}</p>` : ""}
      <p class="tiny dim">$${t.money_left} left unspent</p></div>`;
    const H = R.h2h;
    const table = H ? `<table class="au-h2h"><thead><tr><th>Career averages, added up</th><th>${h(S.teams[0].name)}</th><th>${h(S.teams[1].name)}</th></tr></thead><tbody>
      ${H.cats.map((c) => `<tr><td>${c.label}</td><td class="${c.w === 0 ? "won" : ""}">${c.a.toFixed(1)}</td><td class="${c.w === 1 ? "won" : ""}">${c.b.toFixed(1)}</td></tr>`).join("")}
      <tr class="au-h2h-total"><td>Categories won</td><td>${H.wins[0]}</td><td>${H.wins[1]}</td></tr></tbody></table>` : "";
    return `<section class="card au-result">
      <div class="au-mode tiny dim">${modeLabel()}</div>
      <div class="au-winner">${title}</div>
      <p class="au-verdict">${h(R.verdict)}</p>
      <div class="tiny dim">${R.by === "ai" ? "Judged by AI (Claude)" : R.by === "h2h" ? "Decided on career averages. Overall score breaks a tie." : "Scored by the HoopLife formula"}</div>
      ${table}
      <div class="au-scores">${team(a, 0)}${team(b, 1)}</div>
      <div class="gr-actions"><button class="btn btn-primary" id="au-share">Share result</button><button class="btn" id="au-next">Rematch</button><a class="btn btn-ghost" href="/auction">New game</a></div></section>`;
  }

  function signupHtml() {
    if (D.signed_in || !window.HL.gate) return "";
    return window.HL.gate({ title: "Liked that? There is more every day", text: "A free account gets you daily NBA games, streaks and a scratch card every day.", ref: "auction-end" });
  }

  function paint() {
    if (!S) return;
    if (S.you == null) return;
    let mid;
    if (S.phase === "waiting") {
      mid = `<section class="card au-wait-box"><div class="card-title">Waiting for your friend</div>
        <p class="small muted">${modeLabel()}. Send this link. The auction starts as soon as they join.</p>
        <div class="ezr-row"><input class="input" readonly id="au-link" value="${h(location.origin + location.pathname)}"><button class="btn btn-primary" id="au-copy">Copy invite link</button></div></section>`;
    } else if (S.phase === "judging") {
      mid = `<section class="card au-judging"><div class="spinner"></div><b>Rosters are in.</b><p class="small muted">${S.ai_on && S.scoring === "judge" ? "The AI judge is breaking down both teams." : "Scoring both teams."}</p></section>`;
    } else if (S.phase === "done") {
      mid = resultHtml() + signupHtml();
    } else {
      mid = lotHtml();
    }
    const live = S.phase === "live";
    const showTeams = S.phase !== "done";
    // Sohbet ayri kalir: her hamlede yeniden cizilirse yazi ve odak kaybolur
    if (!document.getElementById("au-main")) {
      app.innerHTML = `<div class="au-game"><div id="au-main"></div><div class="au-side"><div id="au-log-slot"></div>${chatHtml()}</div></div>`;
      paintChat();
    }
    document.getElementById("au-main").innerHTML = `${mid}${showTeams ? `<div class="au-teams">${teamHtml(S.teams[S.you], live && S.turn === S.you)}${teamHtml(S.teams[1 - S.you], live && S.turn === 1 - S.you)}</div>` : ""}`;
    document.getElementById("au-log-slot").innerHTML = live ? logHtml() : "";
    tick();
  }

  function tick() {
    const bar = document.getElementById("au-clock-bar"), txt = document.getElementById("au-clock-txt");
    if (!bar || !S || S.phase !== "live" || !leftAt) return;
    const left = Math.max(0, (leftAt - performance.now()) / 1000);
    bar.style.width = `${Math.min(100, 100 * left / S.secs)}%`;
    bar.classList.toggle("low", left <= 5);
    txt.textContent = `${Math.ceil(left)}s`;
  }
  setInterval(tick, 200);

  // ---------------- paylasim ----------------
  async function share() {
    const R = S.result, me = S.you, t = R.teams[me], opp = R.teams[1 - me];
    const head = R.winner == null ? "I tied" : R.winner === me ? "I won" : "I lost";
    const H = R.h2h;
    const big = H ? `${H.wins[me]}-${H.wins[1 - me]}` : t.total.toFixed(1);
    const text = `NBA Auction: ${head} ${H ? big : `${t.total.toFixed(1)}-${opp.total.toFixed(1)}`} against ${S.teams[1 - me].name}. My five for $${D.money}: ${t.lineup.filter((x) => !x.filler).map((x) => x.name).join(", ")}. Can you build a better one? ${location.origin}/auction?ref=auction-share${window.HL.inv()}`;
    if (window.gtag) gtag("event", "auction_share", { result: head });
    const btn = document.getElementById("au-share"); if (btn) btn.classList.add("is-loading");
    try {
      const K = window.HLCard;
      const { cv, g } = await K.base("NBA AUCTION", "");
      K.text(g, big, K.W / 2, 340, { weight: 900, size: 170, align: "center", color: R.winner === me ? K.C.gold : "#fff" });
      K.pill(g, (R.winner == null ? "TIE" : R.winner === me ? "WINNER" : "BEATEN").toUpperCase(), K.W / 2, 400, { bg: R.winner === me ? K.C.gold : "rgba(255,255,255,.12)", color: R.winner === me ? "#1B1300" : "#fff", size: 30, h: 56, padX: 26 });
      K.text(g, H ? `vs ${S.teams[1 - me].name} · ${H.cats.map((c) => c.label).join(" ")}` : `vs ${S.teams[1 - me].name} ${opp.total.toFixed(1)}`, K.W / 2, 482, { weight: 800, size: 30, color: K.C.muted, align: "center" });
      t.lineup.forEach((x, i) => {
        const by = 540 + i * 92;
        K.rr(g, 120, by, K.W - 240, 78, 18); g.fillStyle = "rgba(255,255,255,.07)"; g.fill();
        K.text(g, x.slot, 150, by + 50, { weight: 900, size: 28, color: K.C.gold });
        K.text(g, x.name, 235, by + 50, { weight: 800, size: 32 });
        if (x.price) K.text(g, `$${x.price}`, K.W - 150, by + 50, { weight: 900, size: 32, align: "right" });
      });
      K.footer(g, "/auction", "Build a better five");
      await K.share(cv, { filename: "nba-auction.png", text, title: "NBA Auction" });
    } catch (err) {
      try { await navigator.clipboard.writeText(text); toast("Result copied."); } catch (e2) { window.prompt("Copy:", text); }
    } finally { if (btn) btn.classList.remove("is-loading"); }
  }

  // ---------------- tiklamalar ----------------
  app.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-bid]");
    if (b && S) { send({ t: "bid", amount: +b.dataset.bid, round: S.round, lot: S.lot_no }); app.querySelectorAll(".au-ctl button, #au-bf button").forEach((x) => { x.disabled = true; }); return; }
    if (e.target.closest("[data-pass]") && S) { send({ t: "pass", round: S.round, lot: S.lot_no }); app.querySelectorAll(".au-ctl button, #au-bf button").forEach((x) => { x.disabled = true; }); return; }
    if (e.target.closest("#au-next")) return send({ t: "next" });
    if (e.target.closest("#au-share")) return share();
    if (e.target.closest("#au-copy")) {
      const url = location.origin + location.pathname;
      if (navigator.share && matchMedia("(pointer: coarse)").matches) { try { await navigator.share({ title: "NBA Auction - outbid me", url }); return; } catch (err) { if (err.name === "AbortError") return; } }
      try { await navigator.clipboard.writeText(url); toast("Invite link copied."); } catch (err) { window.prompt("Copy the link:", url); }
    }
  });
  app.addEventListener("submit", (e) => {
    if (e.target.id === "au-bf") {
      e.preventDefault();
      const v = parseInt(document.getElementById("au-amt").value, 10);
      if (!(v > S.bid && v <= S.limit)) return toast(`Bid between $${S.bid + 1} and $${S.limit}.`, true);
      send({ t: "bid", amount: v, round: S.round, lot: S.lot_no });
      app.querySelectorAll(".au-ctl button, #au-bf button").forEach((x) => { x.disabled = true; });
      return;
    }
    if (e.target.id !== "au-cf") return;
    e.preventDefault();
    const inp = document.getElementById("au-msg");
    const text = inp.value.trim();
    if (text) { send({ t: "chat", text }); inp.value = ""; }
  });
  setInterval(() => send({ t: "ping" }), 25000);

  if (!D.room) lobby();
  else if (!D.room.exists) app.innerHTML = '<p class="muted">This game has ended. <a href="/auction">Start a new one</a></p>';
  else if (D.room.solo || name.length >= 2) { if (name.length >= 2) connect(); else askName(); }
  else askName();
})();
