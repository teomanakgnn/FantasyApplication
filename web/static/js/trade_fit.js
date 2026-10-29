// Trade Fit (My League): bir takasin benim takimima etkisi + "Trade bul" (3 oneri).
// Sekme ilk acildiginda kadrolar yuklenir. Hesap sunucuda (services/trade_fit.py).
(function () {
  const root = document.getElementById("tf-app");
  if (!root) return;
  const { api, toast, escapeHtml: h } = window.HL;
  const $ = (s) => root.querySelector(s);
  const league = root.dataset.league, myTeam = +root.dataset.team;
  let data = null, punts = [], loaded = false;
  const PKEY = `hl_tf_punt_${league}`;
  try { punts = JSON.parse(localStorage.getItem(PKEY)) || []; } catch (e) { punts = []; }

  const row = (p) => `<label class="${p.slot === 13 ? "ir" : ""}"><input type="checkbox" value="${p.id}"><span><b>${h(p.name)}</b><small>${p.pts} pts · ${p.reb} reb · ${p.ast} ast${p.injury !== "ACTIVE" ? ` · <span class="bad">${h(p.injury.toLowerCase())}</span>` : ""}${p.slot === 13 ? " · IR" : ""}</small></span><em>${p.value}</em></label>`;
  function drawPunts() { root.querySelectorAll("[data-punt]").forEach((b) => { b.className = `btn btn-sm ${punts.includes(b.dataset.punt) ? "btn-primary" : "btn-ghost"}`; }); }

  async function load() {
    if (loaded) return; loaded = true;
    drawPunts();
    try {
      data = await api(`/api/league/${league}/trade-fit/rosters`);
      const me = data.teams.find((t) => t.id === myTeam);
      $("#tf-me-name").textContent = me ? `· ${me.name}` : "";
      $("#tf-mine").innerHTML = me ? me.players.map(row).join("") : "Team not found";
      $("#tf-partner").innerHTML = data.teams.filter((t) => t.id !== myTeam).map((t) => `<option value="${t.id}">${h(t.name)}</option>`).join("");
      partner(); $("#tf-go").disabled = false;
    } catch (e) { loaded = false; $("#tf-mine").innerHTML = `<p class="muted small">${h(e.message)}</p>`; }
  }
  function partner() {
    const t = data.teams.find((x) => x.id === +$("#tf-partner").value);
    $("#tf-theirs").innerHTML = t ? t.players.map(row).join("") : "";
  }
  const checked = (sel) => [...root.querySelectorAll(`${sel} input:checked`)].map((i) => +i.value);

  async function check() {
    const send = checked("#tf-mine"), get = checked("#tf-theirs");
    if (!send.length && !get.length) return toast("Tick players on at least one side.", true);
    $("#tf-go").classList.add("is-loading");
    try {
      const r = await api(`/api/league/${league}/trade-fit`, { method: "POST", body: { team: myTeam, partner: +$("#tf-partner").value, send, get, punts } });
      const me = r.me, col = me.delta >= 0.1 ? "good" : me.delta <= -0.1 ? "bad" : "";
      const res = $("#tf-res");
      res.hidden = false;
      res.innerHTML = `
        <div class="card">
          <div class="tf-verdict ${col}">${h(r.verdict)}</div>
          <div class="tf-big"><div><b>${me.before.toFixed(1)}</b><span>cats / week now${r.punts.length ? ` (of ${r.of})` : ""}</span></div><div class="dim">→</div>
            <div><b class="${col}">${me.after.toFixed(1)}</b><span>after trade</span></div>
            <div><b class="${col}">${me.delta >= 0 ? "+" : ""}${me.delta.toFixed(2)}</b><span>change</span></div></div>
          <div class="tf-notes">${r.notes.map((n) => `<p>${h(n)}</p>`).join("")}</div>
        </div>
        <section class="card" style="margin-top:12px"><div class="card-title">Your categories vs the league <span class="dim small">· win % against an average opponent, and your rank of ${r.teams}</span></div>
          <div class="table-wrap"><table class="table small"><thead><tr><th class="l">Cat</th><th>Win % now</th><th>After</th><th>Rank now</th><th>After</th></tr></thead><tbody>
          ${me.cats.map((c) => { const d = c.after - c.before; return `<tr class="${c.punt ? "tf-punted" : ""}"><td class="l"><b>${c.cat}</b>${c.punt ? ' <span class="tiny dim">punt</span>' : ""}</td><td>${c.before}%</td><td class="${d >= 5 ? "good" : d <= -5 ? "bad" : ""}"><b>${c.after}%</b> ${d ? `(${d > 0 ? "+" : ""}${d})` : ""}</td><td>${c.rank_before}</td><td class="${c.rank_after < c.rank_before ? "good" : c.rank_after > c.rank_before ? "bad" : ""}">${c.rank_after}</td></tr>`; }).join("")}
          </tbody></table></div></section>
        ${r.partner ? `<p class="small muted" style="margin-top:8px">${h(r.partner.name)}: ${r.partner.before.toFixed(1)} → ${r.partner.after.toFixed(1)} cats/week (${r.partner.delta >= 0 ? "+" : ""}${r.partner.delta.toFixed(2)}).</p>` : ""}`;
      res.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) { toast(e.message, true); }
    finally { $("#tf-go").classList.remove("is-loading"); }
  }

  async function find() {
    const btn = $("#tf-find"), box = $("#tf-found");
    btn.classList.add("is-loading"); btn.disabled = true;
    box.innerHTML = '<p class="small muted" style="margin:10px 0 0">Testing hundreds of trades against every team in your league - this takes a few seconds...</p>';
    try {
      const r = await api(`/api/league/${league}/trade-finder`, { method: "POST", body: { team: myTeam, punts } });
      if (!r.trades.length) { box.innerHTML = '<p class="small muted" style="margin:10px 0 0">No trade clearly helps you right now without hurting the other side. Check back after the next waiver run.</p>'; return; }
      const pl = (list) => list.map((p) => `<div class="tf-fp"><b>${h(p.name)}</b><small>${h(p.line)}</small></div>`).join("");
      box.innerHTML = `<div class="tf-found">${r.trades.map((t, i) => `
        <div class="tf-offer">
          <div class="tf-offer-h"><b>With ${h(t.partner_name)}</b><span class="good">+${t.delta.toFixed(2)} cats/week</span></div>
          <div class="tf-swap"><div><span>You send</span>${pl(t.send)}</div><div class="dim">⇄</div><div><span>You get</span>${pl(t.get)}</div></div>
          <p class="small muted">${t.up.length ? `Better in ${t.up.join(", ")}` : ""}${t.down.length ? `${t.up.length ? "; " : ""}costs you ${t.down.join(", ")}` : ""}. ${t.partner_delta >= 0.05 ? "They improve too - an easy sell." : "Roughly even for them."}</p>
          <button class="btn btn-sm" type="button" data-try="${i}">Check it in Trade Fit</button>
        </div>`).join("")}</div>`;
      box._trades = r.trades;
    } catch (e) { box.innerHTML = `<p class="small muted">${h(e.message)}</p>`; }
    finally { btn.classList.remove("is-loading"); btn.disabled = false; }
  }

  root.addEventListener("click", async (e) => {
    const pb = e.target.closest("[data-punt]");
    if (pb) {
      const c = pb.dataset.punt;
      if (punts.includes(c)) punts = punts.filter((x) => x !== c);
      else if (punts.length >= 4) return toast("Punting more than 4 categories leaves too few to win.", true);
      else punts.push(c);
      try { localStorage.setItem(PKEY, JSON.stringify(punts)); } catch (err) {}
      drawPunts();
      if (!$("#tf-res").hidden) check();
      return;
    }
    if (e.target.closest("#tf-go")) return check();
    if (e.target.closest("#tf-find")) return find();
    const tr = e.target.closest("[data-try]");
    if (tr) {
      const t = $("#tf-found")._trades[+tr.dataset.try];
      await load();
      $("#tf-partner").value = t.partner; partner();
      root.querySelectorAll("#tf-mine input, #tf-theirs input").forEach((i) => { i.checked = false; });
      t.send.forEach((p) => { const i = root.querySelector(`#tf-mine input[value="${p.id}"]`); if (i) i.checked = true; });
      t.get.forEach((p) => { const i = root.querySelector(`#tf-theirs input[value="${p.id}"]`); if (i) i.checked = true; });
      check();
    }
  });
  root.addEventListener("change", (e) => { if (e.target.id === "tf-partner") partner(); });
  // Sekme acilinca yukle (ya da adres #trade-fit ise hemen)
  document.querySelector('[data-tab="tradefit"]')?.addEventListener("click", load);
  if (location.hash === "#tradefit") load();
})();
