// Watch party odasi: skor, oyunlar, fantezi liderleri, sohbet ve tepkiler.
// WebSocket yerine kisa aralikli sorgu (tek sunucu, kucuk oda).
(function () {
  const { $, api, toast, escapeHtml: h, openModalUrl } = window.HL;
  const root = $(".wp-room");
  if (!root) return;
  const game = root.dataset.game, me = root.dataset.me;
  let after = 0, final = root.dataset.final === "1", tick = 0, firstLoad = true, busy = false;
  const seenPlays = new Set();

  // ---------- spoiler ----------
  const KEY = "hl_wp_spoiler";
  const spoiler = $("#wp-spoiler");
  try { spoiler.checked = localStorage.getItem(KEY) === "1"; } catch (e) { /* yok */ }
  const applySpoiler = () => root.classList.toggle("is-spoiler", spoiler.checked);
  spoiler.addEventListener("change", () => {
    try { localStorage.setItem(KEY, spoiler.checked ? "1" : "0"); } catch (e) { /* yok */ }
    applySpoiler();
  });
  applySpoiler();

  // ---------- sohbet ----------
  const msgs = $("#wp-msgs");
  function addMessage(m) {
    if (m.kind === "react") { if (!firstLoad) floatEmoji(m.body); return; }
    msgs.querySelector(".wp-hint")?.remove();
    const nearBottom = msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 60;
    const el = document.createElement("div");
    el.className = "wp-msg" + (m.user === me ? " mine" : "");
    el.innerHTML = `<b>${h(m.user)}</b><span>${h(m.body)}</span><time>${m.at ? new Date(m.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}</time>`;
    msgs.appendChild(el);
    if (nearBottom || m.user === me) msgs.scrollTop = msgs.scrollHeight;
  }

  function floatEmoji(e) {
    const el = document.createElement("span");
    el.textContent = e;
    el.style.left = 10 + Math.random() * 80 + "%";
    el.style.animationDuration = 2.2 + Math.random() * 1.2 + "s";
    $("#wp-float").appendChild(el);
    setTimeout(() => el.remove(), 3600);
  }

  async function send(kind, body) {
    try {
      await api(`/api/watch/${game}/post`, { method: "POST", body: { kind, body } });
      poll();
    } catch (e) { toast(e.message, true); }
  }

  $("#wp-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#wp-input"), text = input.value.trim();
    if (!text) return;
    input.value = "";
    send("msg", text);
  });
  document.querySelectorAll("[data-react]").forEach((b) =>
    b.addEventListener("click", () => { floatEmoji(b.dataset.react); send("react", b.dataset.react); }));

  // ---------- mac ----------
  function renderGame(g) {
    if (!g) return;
    final = g.final;
    $("#wp-away").textContent = g.away.score;
    $("#wp-home").textContent = g.home.score;
    $("#wp-detail").textContent = g.detail;
    $("#wp-score").classList.toggle("is-live", g.state === "in");
    const box = $("#wp-plays");
    const fresh = g.plays.filter((p) => !seenPlays.has(p.id));
    if (!fresh.length && box.children.length) return;
    g.plays.forEach((p) => seenPlays.add(p.id));
    box.innerHTML = g.plays.length ? g.plays.map((p) => `
      <div class="wp-play ${p.scoring ? "scoring" : ""}">
        <time>Q${p.q} ${h(p.clock)}</time>
        <span>${p.team ? `<b>${h(p.team)}</b> ` : ""}${h(p.text)}</span>
        ${p.scoring ? `<em class="spoil">${p.away}-${p.home}</em>` : ""}
      </div>`).join("") : '<div class="dim small">Plays show up once the game tips off.</div>';
  }

  function renderLeaders(list) {
    $("#wp-leaders").innerHTML = list && list.length ? list.map((p, i) => `
      <a href="#" class="wp-leader" ${p.id ? `data-modal-url="/api/player-card/${game}/${p.id}?final=${final ? 1 : 0}"` : ""}>
        <i>${i + 1}</i>
        <img src="https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${p.id}.png&w=96&h=70" alt="" onerror="this.style.visibility='hidden'">
        <span><b>${h(p.name)}</b><small class="spoil">${h(p.team)} · ${h(p.line)}</small></span>
        <em class="spoil">${p.fp}</em>
      </a>`).join("") : '<div class="dim small">No stats yet.</div>';
  }

  $("#wp-box").addEventListener("click", () => openModalUrl(`/api/boxscore/${game}?final=${final ? 1 : 0}`));

  async function poll() {
    if (busy) return;
    busy = true;
    try {
      const board = tick % 5 === 0 ? 1 : 0;  // liderler ~20 sn'de bir
      const r = await api(`/api/watch/${game}/feed?after=${after}&board=${board}`);
      r.messages.forEach((m) => { addMessage(m); after = Math.max(after, m.id); });
      renderGame(r.game);
      if (r.leaders) renderLeaders(r.leaders);
      firstLoad = false;
      tick++;
    } catch (e) { /* bir sonraki turda tekrar */ }
    finally { busy = false; }
  }

  poll();
  setInterval(() => { if (!document.hidden) poll(); }, 4000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
})();
