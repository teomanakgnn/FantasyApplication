// Hayat Acik Artirmasi: NBA Auction ile ayni sunucu motoru ve oda (web/routes/auction.py).
// Burada Turkce lobi, canli ekran ve sonuc. Gizli puanlar oyun bitene kadar gelmez.
(function () {
  const { $, toast, escapeHtml: h, api } = window.HL;
  const D = JSON.parse($("#au-data").textContent);
  const app = $("#au-app");
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const cid = load("hl_grid_cid", null) || (() => { const v = Math.random().toString(36).slice(2) + Date.now().toString(36); save("hl_grid_cid", v); return v; })();
  const first = (n) => (n || "?").trim().charAt(0).toLocaleUpperCase("tr");
  const themeName = (k) => (D.themes.find((t) => t.key === k) || {}).label || "Karışık";
  let name = load("hl_grid_name", "") || D.me || "";
  let ws = null, S = null, chat = [], retry = 0, leftAt = 0, lastSold = 0, shownRound = null;

  const send = (o) => { if (ws && ws.readyState === 1) { ws.send(JSON.stringify(o)); return true; } return false; };
  const modeLabel = () => `${themeName(S.theme)}${S.blind ? " · Kör" : ""}`;

  // ---------------- lobi ----------------
  function lobby() {
    const mode = load("hl_life_mode", { theme: "karisik", blind: "0" });
    const themeBtns = () => D.themes.map((t) => `<button type="button" class="btn btn-sm ${t.key === mode.theme ? "btn-primary" : ""}" data-theme="${t.key}">${h(t.label)}</button>`).join("");
    app.innerHTML = `<div class="au-lobby">
      <section class="card au-how">
        <div class="card-title">Nasıl oynanır</div>
        <ol>
          <li><b>Aç, artır ya da pas de.</b> Sırası gelen en az 1 dolar vererek açar. Sonra sırayla ya artırırsınız ya da pas dersiniz; pas diyen, son teklifi verene bırakır. Her şey birine satılır.</li>
          <li><b>Beş alım.</b> 20 dolarla başlarsın; boş her yer için en az 1 dolar kalmalı.</li>
          <li><b>Parası biten rakip.</b> Rakibin her boş yeri için yalnızca 1 dolar kaldıysa, açacağın şeyi ona paslayabilirsin. Rakip onu 1 dolara almak zorunda kalır.</li>
          <li><b>Gizli puanlar.</b> Her şeyin 100 üzerinden bir puanı var. Tatlıda ölçüt lezzet, ülkede orada yaşamak, randevuda birlikte geçen gün. Puanlar oyun sonunda açılır, ortalaması yüksek olan kazanır.</li>
        </ol>
        <div class="card-title" style="margin-top:14px">Kör oyun</div>
        <p class="small muted" style="margin:0">Yalnızca Karışık temada var: yalnızca "Bir tatlı" ya da "Bir ülke" görünür, ne olduğu satılınca açılır.</p>
      </section>
      <section class="card au-start">
        <label class="field"><span>Adın</span><input class="input" id="au-name" maxlength="20" value="${h(name)}" placeholder="Adın"></label>
        <div class="field"><span>Tema</span><div id="lf-themes" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:6px">${themeBtns()}</div></div>
        <div class="field" id="lf-blind-f"><span>Açık artırma</span><div class="seg seg-block" id="au-blind">${[["0", "Açık"], ["1", "Kör"]].map(([v, l]) => `<button type="button" data-v="${v}" class="${v === mode.blind ? "is-on" : ""}">${l}</button>`).join("")}</div></div>
        <button class="btn btn-primary btn-block" id="au-friend">Davet linki oluştur</button>
        <button class="btn btn-block" id="au-solo">Bota karşı dene</button>
        <p class="tiny dim" style="margin:0">Bu sayfa menüde yok, yalnızca sen açabilirsin. Davet ettiğin kişi linkle hesapsız katılır.</p>
      </section>
    </div>`;
    const blindF = () => { $("#lf-blind-f").style.display = mode.theme === "karisik" ? "" : "none"; };
    blindF();
    $("#lf-themes").addEventListener("click", (e) => {
      const b = e.target.closest("[data-theme]");
      if (!b) return;
      mode.theme = b.dataset.theme;
      $("#lf-themes").querySelectorAll("[data-theme]").forEach((x) => x.classList.toggle("btn-primary", x === b));
      blindF();
    });
    $("#au-blind").addEventListener("click", (e) => {
      const b = e.target.closest("[data-v]");
      if (!b) return;
      mode.blind = b.dataset.v;
      $("#au-blind").querySelectorAll("[data-v]").forEach((x) => x.classList.toggle("is-on", x === b));
    });
    const go = async (solo, btn) => {
      const n = $("#au-name").value.trim();
      if (n.length < 2) return toast("Ad en az 2 harf olmalı.", true);
      name = n; save("hl_grid_name", n);
      btn.disabled = true;
      try {
        save("hl_life_mode", mode);
        const r = await api("/api/auction/room", { method: "POST", body: { solo, life: true, theme: mode.theme, blind: mode.theme === "karisik" && mode.blind === "1" } });
        location.href = r.url;
      } catch (err) { toast(err.message, true); btn.disabled = false; }
    };
    $("#au-friend").onclick = (e) => go(false, e.target);
    $("#au-solo").onclick = (e) => go(true, e.target);
  }

  function askName() {
    app.innerHTML = `<section class="card au-join"><div class="card-title">Oyuna katıl</div>
      <p class="small muted">İkinizin de ${D.money} doları var. Sırayla gelen şeylere teklif verip beş alım yapacaksınız.</p>
      <form id="au-nf" class="ezr-row"><input class="input" id="au-name" maxlength="20" value="${h(name)}" placeholder="Adın" required><button class="btn btn-primary">Katıl</button></form></section>`;
    $("#au-nf").addEventListener("submit", (e) => {
      e.preventDefault();
      const n = $("#au-name").value.trim();
      if (n.length < 2) return toast("Ad en az 2 harf olmalı.", true);
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
      if (m.t === "state") apply(m);
      else if (m.t === "joined") toast(`${m.name} katıldı.`);
      else if (m.t === "round") toast(`Yeni oyun: ${m.by} rövanş istedi.`);
      else if (m.t === "chatlog") { chat = m.items; paintChat(); }
      else if (m.t === "chat") { chat.push(m); chat = chat.slice(-80); paintChat(); }
      else if (m.t === "error") { toast(tr(m.text), true); paint(); }
      else if (m.t === "gone") { retry = 99; app.innerHTML = '<p class="muted">Bu oyun bitti.</p>'; }
    };
    ws.onclose = () => { if (retry < 8) { retry += 1; setTimeout(connect, 800 * retry); } };
  }
  // Sunucu hatalari Ingilizce: en sik olanlari cevir
  function tr(t) {
    if (/two players/.test(t)) return "Bu oyunda zaten iki kişi var.";
    if (/Not your turn/.test(t)) return "Sıra sende değil.";
    if (/Pick a name/.test(t)) return "Ad en az 2 harf olmalı.";
    if (/bid at least/.test(t)) return "Açan sensin: en az 1 dolar vermelisin.";
    return t;
  }

  function apply(m) {
    const prev = S;
    S = m;
    leftAt = m.left != null ? performance.now() + m.left * 1000 : 0;
    if (shownRound !== m.round) { shownRound = m.round; lastSold = 0; }
    const sold = m.events.filter((e) => e.kind === "sold");
    if (prev && prev.round === m.round && sold.length && soldCount(m) > lastSold) {
      const e = sold[sold.length - 1];
      if (e.seat !== m.you) toast(`${e.seat_name}, ${e.name} için $${e.price} verdi`);
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
      slots.push(p ? `<li><span class="au-face"><em>${h(first(p.name))}</em></span><div><b>${h(p.name)}</b><small>${h(p.theme)}</small></div><i>$${p.price}</i></li>` : '<li class="open"><span class="au-face"></span><div><small>Boş yer</small></div></li>');
    }
    return `<section class="card au-team ${active ? "active" : ""} ${you ? "you" : ""}">
      <div class="au-team-h"><span><b>${h(t.name || "Bekleniyor...")}</b>${you ? ' <small class="dim">sen</small>' : ""}${t.online || !t.name ? "" : ' <small class="warn">ayrıldı</small>'}</span><strong>$${t.money}</strong></div>
      <ul class="au-slots">${slots.join("")}</ul></section>`;
  }

  function lotHtml() {
    const p = S.lot;
    const bidder = S.bidder != null ? S.teams[S.bidder] : null;
    const info = p.blind
      ? `<span class="au-face big au-mystery"><em>?</em></span><div class="au-lot-info"><div class="small muted">Gizli</div><h2>${h(p.category)}</h2></div>`
      : `<span class="au-face big"><em>${h(first(p.name))}</em></span><div class="au-lot-info"><div class="small muted">${h(p.theme)}</div><h2>${h(p.name)}</h2><div class="small dim">Puanın ölçütü: ${h(p.q.toLocaleLowerCase("tr"))}</div></div>`;
    const sold = S.events.filter((e) => e.kind === "sold");
    const last = S.blind && sold.length ? sold[sold.length - 1] : null;
    return `<section class="card au-lot">
      <div class="au-mode tiny dim">${modeLabel()}</div>
      ${last ? `<div class="au-reveal small">Açıldı: <b>${h(last.name)}</b>, ${h(last.seat_name)} $${last.price} verdi</div>` : ""}
      <div class="au-lot-top"><span class="dim small">${S.lot_no}. sıra</span><span class="au-clock"><i id="au-clock-bar"></i></span><span class="small" id="au-clock-txt"></span></div>
      <div class="au-lot-main">${info}
        <div class="au-bid"><small>${bidder ? h(bidder.name) : "Teklif yok"}</small><strong class="${S.bidder === S.you ? "good" : ""}">$${S.bid}</strong></div></div>
      ${controlsHtml()}
    </section>`;
  }

  function controlsHtml() {
    const me = S.you;
    if (S.turn !== me) {
      const other = S.turn != null ? S.teams[S.turn] : null;
      return `<p class="au-wait small muted">${other ? `${h(other.name)} düşünüyor...` : ""}</p>`;
    }
    const min = S.bid + 1;
    const opts = [...new Set([min, min + 1, min + 4, S.limit].filter((v) => v >= min && v <= S.limit))];
    const opp = S.teams[1 - me];
    const pass = S.bid > 0 ? `Pas: ${h(opp.name)} $${S.bid} ödesin` : S.can_give ? `${h(opp.name)} 1 dolara alsın` : "";
    const hint = S.can_give ? `${h(opp.name)} parasız kaldı: 1 dolar verip sen al ya da pas de, o almak zorunda.` : S.bid > 0 ? "" : "Bunu sen açıyorsun, en az 1 dolar vermelisin.";
    return `<div class="au-ctl">${opts.map((v, i) => `<button class="btn ${i === 0 ? "btn-primary" : ""}" data-bid="${v}">${v === S.limit && opts.length > 1 ? "En çok " : ""}$${v}</button>`).join("")}
      ${pass ? `<button class="btn btn-ghost au-pass" data-pass>${pass}</button>` : ""}</div>
      ${S.limit > min ? `<form id="au-bf" class="au-manual"><label for="au-amt">Teklifin</label><span class="au-dollar">$</span><input class="input" id="au-amt" type="number" inputmode="numeric" min="${min}" max="${S.limit}" step="1" value="${min}"><button class="btn">Ver</button></form>` : ""}
      <div class="tiny dim">${hint ? `${hint} ` : ""}En fazla $${S.limit} verebilirsin. Boş her yer için 1 dolar kalır.</div>`;
  }

  function logHtml() {
    const rows = S.events.slice().reverse().filter((e) => e.kind !== "bid").slice(0, 8).map((e) => {
      if (e.kind === "sold") return `<div><b>${h(e.seat_name)}</b> ${h(e.name)} ${e.given ? "paslandı" : "aldı"} <span class="dim">$${e.price}</span></div>`;
      return `<div class="dim">${h(e.seat_name)} ${e.timeout ? "süresi doldu" : "pas dedi"}</div>`;
    }).join("");
    return rows ? `<section class="card au-log"><div class="card-title">Geçmiş</div>${rows}</section>` : "";
  }

  function chatHtml() {
    if (S.solo) return "";
    return `<aside class="card ezr-chat au-chat"><div class="card-title">Sohbet</div><div class="ezr-chat-list" id="au-chat-list"></div>
      <form id="au-cf" class="ezr-row"><input class="input" id="au-msg" maxlength="300" placeholder="Mesaj" autocomplete="off"><button class="btn btn-sm btn-primary">Gönder</button></form></aside>`;
  }
  function paintChat() {
    const box = document.getElementById("au-chat-list");
    if (!box) return;
    box.innerHTML = chat.map((c) => `<div><b>${h(c.name)}</b> ${h(c.text)}</div>`).join("") || '<div class="dim small">Biraz laf at.</div>';
    box.scrollTop = box.scrollHeight;
  }

  function resultHtml() {
    const R = S.result;
    const names = [S.teams[0].name, S.teams[1].name];
    const verdict = R.verdict.replace(/Team A/g, names[0]).replace(/Team B/g, names[1]);
    const title = R.winner == null ? "Berabere" : `${h(names[R.winner])} kazandı`;
    const team = (t, i) => `<div class="au-score ${R.winner === i ? "won" : ""}">
      <div class="au-score-h"><b>${h(names[i])}</b><strong>${t.total.toFixed(1)}</strong></div>
      <ul class="au-final">${t.lineup.map((x) => `<li><i>${x.score}</i><span>${h(x.name)} <small class="dim">${h(x.theme)}</small></span><small>$${x.price}</small></li>`).join("")}</ul>
      <p class="tiny dim">$${t.money_left} harcanmadı</p></div>`;
    return `<section class="card au-result">
      <div class="au-mode tiny dim">${modeLabel()}</div>
      <div class="au-winner">${title}</div>
      <p class="au-verdict">${h(verdict)}</p>
      <div class="tiny dim">Puan = beş alımın gizli puan ortalaması. Eşitlikte artan para kazanır.</div>
      <div class="au-scores">${team(R.teams[0], 0)}${team(R.teams[1], 1)}</div>
      <div class="gr-actions"><button class="btn btn-primary" id="au-next">Rövanş</button>${D.admin ? '<a class="btn btn-ghost" href="/auction/life">Yeni oyun</a>' : ""}</div></section>`;
  }

  function paint() {
    if (!S || S.you == null) return;
    let mid;
    if (S.phase === "waiting") {
      mid = `<section class="card au-wait-box"><div class="card-title">Davet ettiğin kişi bekleniyor</div>
        <p class="small muted">${modeLabel()}. Bu linki gönder; açınca oyun başlar.</p>
        <div class="ezr-row"><input class="input" readonly id="au-link" value="${h(location.origin + location.pathname)}"><button class="btn btn-primary" id="au-copy">Linki kopyala</button></div></section>`;
    } else if (S.phase === "judging") {
      mid = '<section class="card au-judging"><div class="spinner"></div><b>Alımlar tamam.</b><p class="small muted">Puanlar açılıyor.</p></section>';
    } else if (S.phase === "done") {
      mid = resultHtml();
    } else {
      mid = lotHtml();
    }
    const live = S.phase === "live";
    if (!document.getElementById("au-main")) {
      app.innerHTML = `<div class="au-game"><div id="au-main"></div><div class="au-side"><div id="au-log-slot"></div>${chatHtml()}</div></div>`;
      paintChat();
    }
    document.getElementById("au-main").innerHTML = `${mid}${S.phase !== "done" ? `<div class="au-teams">${teamHtml(S.teams[S.you], live && S.turn === S.you)}${teamHtml(S.teams[1 - S.you], live && S.turn === 1 - S.you)}</div>` : ""}`;
    document.getElementById("au-log-slot").innerHTML = live ? logHtml() : "";
    tick();
  }

  function tick() {
    const bar = document.getElementById("au-clock-bar"), txt = document.getElementById("au-clock-txt");
    if (!bar || !S || S.phase !== "live" || !leftAt) return;
    const left = Math.max(0, (leftAt - performance.now()) / 1000);
    bar.style.width = `${Math.min(100, 100 * left / S.secs)}%`;
    bar.classList.toggle("low", left <= 5);
    txt.textContent = `${Math.ceil(left)} sn`;
  }
  setInterval(tick, 200);

  const lock = () => app.querySelectorAll(".au-ctl button, #au-bf button").forEach((x) => { x.disabled = true; });
  app.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-bid]");
    if (b && S) { send({ t: "bid", amount: +b.dataset.bid, round: S.round, lot: S.lot_no }); lock(); return; }
    if (e.target.closest("[data-pass]") && S) { send({ t: "pass", round: S.round, lot: S.lot_no }); lock(); return; }
    if (e.target.closest("#au-next")) return send({ t: "next" });
    if (e.target.closest("#au-copy")) {
      const url = location.origin + location.pathname;
      if (navigator.share && matchMedia("(pointer: coarse)").matches) { try { await navigator.share({ title: "Hayat Açık Artırması", url }); return; } catch (err) { if (err.name === "AbortError") return; } }
      try { await navigator.clipboard.writeText(url); toast("Link kopyalandı."); } catch (err) { window.prompt("Linki kopyala:", url); }
    }
  });
  app.addEventListener("submit", (e) => {
    if (e.target.id === "au-bf") {
      e.preventDefault();
      const v = parseInt(document.getElementById("au-amt").value, 10);
      if (!(v > S.bid && v <= S.limit)) return toast(`$${S.bid + 1} ile $${S.limit} arası ver.`, true);
      send({ t: "bid", amount: v, round: S.round, lot: S.lot_no });
      lock();
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
  else if (name.length >= 2) connect();
  else askName();
})();
