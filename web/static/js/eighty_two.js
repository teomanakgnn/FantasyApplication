// 82-0: bes cevirme, her takimdan bir oyuncu, bes mevki. Ortalama OVR
// (mevki disi cezali) 82 maclik sezona cevrilir. Gunluk oyun bu cihazda saklanir.
(function () {
  const { $, api, toast, escapeHtml: h } = window.HL;
  const data = JSON.parse($("#ez-data").textContent);
  const C = data.config;
  const root = $("#ez-game");
  const KEY = "hl_82_game", STATS = "hl_82_stats";
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const photo = (id) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=110&h=80`;
  const fits = (pos, slot) => C.fits[slot].includes(pos);

  const stats = Object.assign({ played: 0, best: 0, perfect: 0, last: 0 }, load(STATS, {}));
  let mode = "daily", spins = data.spins;
  let st = load(KEY, null);
  if (!st || st.puzzle !== data.puzzle) st = fresh(data.puzzle);
  let selected = null, animating = false, revealing = false;

  function fresh(puzzle) { return { puzzle, spin: 0, rerolls: C.rerolls, lineup: {}, done: false }; }
  const persist = () => { if (mode === "daily") save(KEY, st); };
  const filled = () => Object.keys(st.lineup).length;
  const effective = (slot) => { const x = st.lineup[slot]; return x ? x.ovr - (fits(x.pos, slot) ? 0 : C.penalty) : 0; };
  const avg = () => C.slots.reduce((a, s) => a + effective(s), 0) / C.slots.length;
  function record(a) { const p = 1 / (1 + Math.exp(-(a - C.mu) / C.k)); const w = Math.round(82 * p); return [w, 82 - w]; }
  const ovrClass = (o) => (o >= 95 ? "elite" : o >= 88 ? "great" : o >= 78 ? "good" : "");
  const current = () => spins[st.spin];
  const usedIds = () => new Set(Object.values(st.lineup).map((x) => x.id));

  // ---------------- kort ----------------
  const SPOT = { PG: [50, 80], SG: [84, 62], SF: [16, 62], PF: [30, 30], C: [68, 26] };
  function courtHtml() {
    return `<div class="ez-court">
      <svg viewBox="0 0 100 70" preserveAspectRatio="none" aria-hidden="true" class="ez-court-svg">
        <rect x="0" y="0" width="100" height="70" class="floor"/>
        <rect x="34" y="0" width="32" height="38" class="paint"/>
        <circle cx="50" cy="38" r="12" class="ln"/>
        <path d="M6 0 L6 18 A44 44 0 0 0 94 18 L94 0" class="ln"/>
        <line x1="44" y1="5" x2="56" y2="5" class="ln"/><circle cx="50" cy="8" r="1.6" class="rim"/>
        <line x1="0" y1="69.7" x2="100" y2="69.7" class="ln"/>
      </svg>
      ${C.slots.map((s) => {
        const x = st.lineup[s], [l, t] = SPOT[s];
        const can = selected && !st.done && !x;
        const off = x && !fits(x.pos, s);
        const fitHint = can && selected ? (fits(selected.pos, s) ? "fit" : "off") : "";
        return `<button type="button" class="ez-slot ${x ? "filled" : "open"} ${can ? "target " + fitHint : ""}" data-slot="${s}" style="left:${l}%;top:${t}%" ${can ? "" : x ? "" : "disabled"}>
          <span class="ez-face">${x ? `<img src="${photo(x.id)}" alt="" onerror="this.remove()">` : `<em>${s}</em>`}
            ${x ? `<i class="ez-ovr ${ovrClass(effective(s))}">${effective(s)}</i>` : ""}</span>
          <span class="ez-tag">${x ? h(x.name.split(" ").slice(-1)[0]) : can ? (fitHint === "fit" ? "Put here" : `-${C.penalty} here`) : s}</span>
          ${x ? `<span class="ez-sub">${h(x.team)} ’${String(x.season).slice(2)}${off ? ` · off-pos` : ""}</span>` : ""}
        </button>`;
      }).join("")}
    </div>`;
  }

  // ---------------- cizim ----------------
  function render() {
    if (st.done) return renderResult();
    const sp = current();
    const used = usedIds();
    // Simdiye kadar secilenlerin ortalamasiyla gidisat
    const live = filled() ? record(avg() * C.slots.length / filled()) : null;
    root.innerHTML = `
      <div class="ez-bar">
        <span class="chip">${mode === "practice" ? "Practice · " : ""}Spin ${Math.min(st.spin + 1, C.spins)} / ${C.spins}</span>
        <span class="ez-pips">${C.slots.map((s) => `<i class="${st.lineup[s] ? "on" : ""}">${s}</i>`).join("")}</span>
        ${filled() ? `<span class="small muted">Pace: <b>${live[0]}-${live[1]}</b></span>` : ""}
      </div>
      <div class="ez-grid">
        <div>${courtHtml()}</div>
        <section class="card ez-spin">
          <div class="ez-team ${animating ? "spinning" : ""}" id="ez-team">
            ${sp.logo ? `<img src="${sp.logo}" alt="" width="54" height="54">` : `<span class="ez-nologo">${h(sp.abbr)}</span>`}
            <div><span class="eyebrow" style="margin:0">${h(sp.label)}</span><b>${h(sp.name)}</b></div>
            ${st.rerolls > 0 ? `<button class="btn btn-sm btn-ghost" id="ez-reroll" type="button" title="Spin a different team">Re-spin (${st.rerolls})</button>` : ""}
          </div>
          <p class="tiny dim" style="margin:6px 0 8px">${selected ? `Now tap a spot on the court for <b>${h(selected.name)}</b>.` : "Pick one player from this team."}</p>
          <div class="ez-roster ${animating ? "is-spinning" : revealing ? "is-revealing" : ""}" id="ez-roster">${animating ? spinRows(sp.players.length) : sp.players.map((p, i) => {
            const dup = used.has(p.id);
            return `<button type="button" class="ez-p ${selected && selected.id === p.id ? "is-sel" : ""}" data-pid="${p.id}" ${dup ? "disabled" : ""} style="--i:${i}">
              <img src="${photo(p.id)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
              <span class="ez-pn"><b>${h(p.name)}</b><small>${h(p.pos)} · ${p.pts.toFixed(1)} pts · ${p.reb.toFixed(1)} reb · ${p.ast.toFixed(1)} ast${dup ? " · already on your team" : ""}</small></span>
              <i class="ez-ovr ${ovrClass(p.ovr)}">${p.ovr}</i></button>`;
          }).join("")}</div>
        </section>
      </div>`;
  }

  function place(slot) {
    if (!selected || st.lineup[slot]) return;
    const sp = current();
    st.lineup[slot] = Object.assign({ team: sp.abbr, season: sp.season }, selected);
    selected = null;
    st.spin += 1;
    if (filled() >= C.slots.length) st.done = true;
    persist();
    if (st.done) return finish();
    spinAnim();
  }

  // Cark donerken kadro da doner: takim adi, logo, sezon ve oyuncu
  // satirlari birlikte rastgele akar, yavaslar; durunca gercek kadro
  // satir satir acilir. Boylece takim adi bitmeden kadro gorunmez.
  const pool = () => data.spins.concat(spins).flatMap((t) => t.players);
  function rowHtml(p) {
    return `<div class="ez-p ez-ghost"><img src="${photo(p.id)}" alt="" onerror="this.style.visibility='hidden'"><span class="ez-pn"><b>${h(p.name)}</b><small>${h(p.pos)} · ${p.pts.toFixed(1)} pts</small></span><i class="ez-ovr ${ovrClass(p.ovr)}">${p.ovr}</i></div>`;
  }
  function spinRows(n) { const all = pool(); return Array.from({ length: n }, () => rowHtml(all[Math.floor(Math.random() * all.length)])).join(""); }

  function spinAnim() {
    animating = true; render();
    const teams = data.spins.concat(spins);
    const head = $("#ez-team"), roster = $("#ez-roster");
    const n = current().players.length;
    const delays = [60, 60, 60, 70, 70, 80, 90, 110, 130, 160, 200, 250];
    let k = 0;
    const tick = () => {
      if (k >= delays.length) { animating = false; revealing = true; render(); revealing = false; return; }
      const r = teams[Math.floor(Math.random() * teams.length)];
      if (head) {
        head.querySelector("b").textContent = r.name;
        head.querySelector(".eyebrow").textContent = r.label;
        const img = head.querySelector("img"); if (img && r.logo) img.src = r.logo;
      }
      if (roster) roster.innerHTML = spinRows(n);
      setTimeout(tick, delays[k++]);
    };
    tick();
  }

  root.addEventListener("click", async (e) => {
    const p = e.target.closest("[data-pid]");
    if (p && !p.disabled && !animating) {
      const pl = current().players.find((x) => x.id === p.dataset.pid);
      selected = selected && selected.id === pl.id ? null : pl;
      render();
      if (selected && matchMedia("(max-width: 900px)").matches) $(".ez-court").scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const s = e.target.closest("[data-slot]");
    if (s && !s.disabled) return place(s.dataset.slot);
    if (e.target.closest("#ez-reroll") && st.rerolls > 0 && !animating) {
      // Yedek takim: listenin sonundaki fazladan cevirme
      const spare = spins.splice(spins.length - st.rerolls, 1)[0];
      spins.splice(st.spin, 1, spare);
      st.rerolls -= 1; selected = null;
      if (mode === "daily") { st.order = spins.map((x) => x.abbr + x.season); }
      persist(); return spinAnim();
    }
    if (e.target.closest("#ez-share")) return share();
    if (e.target.closest("#ez-practice")) return practice();
  });

  // Gunluk oyunda yeniden cevirme yapildiysa sirayi geri kur
  if (mode === "daily" && st.order) {
    const byKey = new Map(data.spins.map((x) => [x.abbr + x.season, x]));
    const restored = st.order.map((k) => byKey.get(k)).filter(Boolean);
    if (restored.length === data.spins.length) spins = restored;
  }

  // ---------------- sonuc ----------------
  function lineupText() {
    return C.slots.map((s) => { const x = st.lineup[s]; return `${s} ${x.name.split(" ").slice(-1)[0]} '${String(x.season).slice(2)}`; }).join(" · ");
  }
  function finish() {
    const [w] = record(avg());
    if (mode === "daily" && stats.last !== data.puzzle) {
      stats.last = data.puzzle; stats.played += 1; stats.best = Math.max(stats.best, w);
      if (w === 82) stats.perfect += 1;
      save(STATS, stats);
      if (window.gtag) gtag("event", "eightytwo_finish", { wins: w });
    }
    renderResult(true);
  }

  function renderResult(animate) {
    const a = avg(), [w, l] = record(a);
    const verdict = w === 82 ? "PERFECT SEASON" : w >= 73 ? "All-time great" : w >= 60 ? "Title contender" : w >= 45 ? "Playoff team" : w >= 30 ? "Lottery bound" : "Tank commander";
    root.innerHTML = `
      <div class="ez-grid">
        <div>${courtHtml()}</div>
        <section class="card ez-result">
          <div class="eyebrow">${mode === "daily" ? `82-0 #${data.puzzle}` : "Practice"}</div>
          <div class="ez-record"><span id="ez-w">${animate ? 0 : w}</span>-<span id="ez-l">${animate ? 0 : l}</span></div>
          <div class="ez-verdict ${w === 82 ? "perfect" : ""}">${verdict}</div>
          <p class="small muted">Team OVR <b>${a.toFixed(1)}</b>${C.slots.some((s) => !fits(st.lineup[s].pos, s)) ? " · includes off-position penalty" : ""}</p>
          <div class="dp-actions">
            <button class="btn btn-primary" id="ez-share" type="button">Share season</button>
            <button class="btn" id="ez-practice" type="button">Play again</button>
          </div>
          ${mode === "daily" ? `<div class="dp-stats"><div><b>${stats.played}</b><span>Played</span></div><div><b>${stats.best}</b><span>Best wins</span></div><div><b>${stats.perfect}</b><span>82-0s</span></div></div>
            <p class="small muted" style="margin-top:12px">New spins every day at midnight UK time. Also try <a href="/starting-five">Starting Five</a>.</p>` : ""}
          ${data.signed_in ? "" : `<div class="dp-keep"><div><b>Like daily games?</b><span>Free account: keep your Mystery Player streak on every device and save mock drafts.</span></div>
            <a class="btn btn-primary btn-sm" href="/register?next=%2F82-0">Create free account</a></div>`}
        </section>
      </div>`;
    if (animate) {
      let i = 0; const steps = 30;
      const t = setInterval(() => {
        i++; const ww = Math.round(w * i / steps), ll = Math.round(l * i / steps);
        $("#ez-w").textContent = ww; $("#ez-l").textContent = ll;
        if (i >= steps) clearInterval(t);
      }, 35);
    }
  }

  async function share() {
    const [w, l] = record(avg());
    const head = mode === "daily" ? `HoopLife 82-0 #${data.puzzle}` : "HoopLife 82-0";
    const text = `${head}: I went ${w}-${l}${w === 82 ? " 🏆" : ""}. Can you beat it? ${location.origin}/82-0?ref=82-0-share`;
    if (window.gtag) gtag("event", "eightytwo_share", { wins: w });
    const btn = $("#ez-share"); if (btn) btn.classList.add("is-loading");
    try { await HLCard.share(await card(w, l), { filename: `82-0-${w}-${l}.png`, text, title: "82-0 Challenge" }); }
    catch (err) { toast("Could not create the image.", true); }
    finally { if (btn) btn.classList.remove("is-loading"); }
  }

  async function card(w, l) {
    const K = HLCard, a = avg();
    const { cv, g } = await K.base("82-0 CHALLENGE", mode === "daily" ? data.puzzle : "");
    const verdict = w === 82 ? "PERFECT SEASON" : w >= 73 ? "ALL-TIME GREAT" : w >= 60 ? "TITLE CONTENDER" : w >= 45 ? "PLAYOFF TEAM" : w >= 30 ? "LOTTERY BOUND" : "TANK COMMANDER";
    K.text(g, `${w}-${l}`, K.W / 2, 330, { weight: 900, size: 190, align: "center", color: w === 82 ? K.C.gold : "#fff" });
    K.pill(g, verdict, K.W / 2, 392, { bg: w === 82 ? K.C.gold : "rgba(255,255,255,.12)", color: w === 82 ? "#1B1300" : "#fff", size: 30, h: 56, padX: 26 });
    K.text(g, `TEAM OVR ${a.toFixed(1)}`, K.W / 2, 462, { weight: 800, size: 30, color: K.C.muted, align: "center" });

    // Yari saha
    const x0 = 60, y0 = 500, cw = K.W - 120, ch = 720;
    K.rr(g, x0, y0, cw, ch, 28); g.save(); g.clip();
    const wood = g.createLinearGradient(0, y0, 0, y0 + ch); wood.addColorStop(0, "#C88446"); wood.addColorStop(1, "#A9692F");
    g.fillStyle = wood; g.fillRect(x0, y0, cw, ch);
    for (let x = x0; x < x0 + cw; x += 46) { g.fillStyle = "rgba(0,0,0,.05)"; g.fillRect(x, y0, 2, ch); }
    g.strokeStyle = "rgba(255,255,255,.85)"; g.lineWidth = 4;
    // Sahadaki cizgiler 100x70 birimde; oyuncu yerleri (SPOT) yuzde.
    const px = (v) => x0 + cw * v / 100, py = (v) => y0 + ch * v / 70, pct = (v) => y0 + ch * v / 100;
    g.fillStyle = "rgba(122,32,32,.55)"; g.fillRect(px(34), py(0), px(66) - px(34), py(38) - py(0)); g.strokeRect(px(34), py(0), px(66) - px(34), py(38) - py(0));
    g.beginPath(); g.ellipse(px(50), py(38), cw * .12, ch * .12 / .7 * .7 * 1.0, 0, 0, Math.PI * 2); g.stroke();
    g.beginPath(); g.moveTo(px(6), py(0)); g.lineTo(px(6), py(18)); g.ellipse(px(50), py(18), cw * .44, ch * .44 * 0.95, 0, Math.PI, 0, true); g.lineTo(px(94), py(0)); g.stroke();
    g.strokeStyle = "#FF7A1A"; g.beginPath(); g.arc(px(50), py(8), 16, 0, Math.PI * 2); g.stroke();
    g.restore();

    const imgs = await Promise.all(C.slots.map((s) => K.loadImg(`https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${st.lineup[s].id}.png&w=350&h=254`)));
    C.slots.forEach((s, i) => {
      const x = st.lineup[s], [sx, sy] = SPOT[s];
      const cx = px(sx), cy = pct(sy) - 40, eff = effective(s);
      K.disc(g, imgs[i], cx, cy, 72, { ring: eff >= 95 ? K.C.gold : "#fff", ringW: 7, name: x.name });
      const bg = eff >= 95 ? K.C.gold : eff >= 88 ? "#1E9E5A" : eff >= 78 ? "#2F6FB6" : "#3A4357";
      K.pill(g, String(eff), cx + 60, cy + 50, { bg, color: eff >= 95 ? "#1B1300" : "#fff", size: 28, h: 46, padX: 12 });
      K.pill(g, x.name.split(" ").slice(-1)[0].toUpperCase(), cx, cy + 98, { size: 25, h: 42 });
      K.pill(g, `${s} · ${x.team} '${String(x.season).slice(2)}`, cx, cy + 136, { bg: "rgba(255,255,255,.9)", color: "#0B0F17", size: 20, h: 32, weight: 800 });
    });
    K.footer(g, "/82-0");
    return cv;
  }

  async function practice() {
    try {
      const res = await api("/api/82-0/practice");
      mode = "practice"; spins = res.spins; st = fresh(-1); selected = null;
      window.scrollTo({ top: 0, behavior: "smooth" }); spinAnim();
    } catch (err) { toast(err.message, true); }
  }

  // Acilista cark doner (oyun bitmemisse)
  if (st.done) render(); else spinAnim();
})();
