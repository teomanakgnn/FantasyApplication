// 82-0: bes cevirme, her takimdan bir oyuncu, bes mevki. Oyuncu puanlari
// oyun boyunca gizli; sezon sonunda acilir. Donem (1/5/10 sezon) ve kolay
// mod (yerlestirilen oyuncunun yeri degistirilebilir) secilebilir.
(function () {
  const { $, api, toast, escapeHtml: h } = window.HL;
  const data = JSON.parse($("#ez-data").textContent);
  const C = data.config;
  const root = $("#ez-game");
  const PREFS = "hl_82_prefs", STATS = "hl_82_stats";
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const photo = (id, w = 110, hh = 80) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=${w}&h=${hh}`;
  const fits = (pos, slot) => C.fits[slot].includes(pos);
  const yy = (season) => `'${String(season).slice(2)}`;
  // Soyadi: "Trey Murphy III" -> "Murphy", "Jaren Jackson Jr." -> "Jackson"
  const lastName = (n) => { const w = n.split(" ").filter((x) => !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(x)); return w[w.length - 1] || n; };
  const initials = (n) => n.split(" ").filter(Boolean).map((x) => x[0]).slice(0, 2).join("").toUpperCase();
  const SPAN_LABEL = { 1: "Single season", 5: "5-season era", 10: "10-season era" };

  const prefs = Object.assign({ span: 1, easy: false }, load(PREFS, {}));
  const stats = Object.assign({ played: 0, best: 0, perfect: 0, last: "" }, load(STATS, {}));
  let st = null;                       // aktif oyun
  let selected = null;                 // {src:"roster", p} | {src:"slot", slot}
  let animating = false, revealing = false;

  const gameKey = (daily, span, easy) => (daily ? `hl_82_d${span}${easy ? "e" : ""}` : "hl_82_practice");
  const persist = () => { if (st) save(st.key, st); };
  const filled = () => Object.keys(st.lineup).length;
  const effective = (slot) => { const x = st.lineup[slot]; return x ? x.ovr - (fits(x.pos, slot) ? 0 : C.penalty) : 0; };
  function rating() {
    const o = C.slots.map(effective).sort((a, b) => b - a);
    return o.reduce((a, v, i) => a + v * C.weights[i], 0);
  }
  function winsFor(r) {
    const cv = C.curve;
    if (r <= cv[0][0]) return cv[0][1];
    for (let i = 1; i < cv.length; i++) {
      const [x0, y0] = cv[i - 1], [x1, y1] = cv[i];
      if (r <= x1) return Math.round(y0 + (y1 - y0) * (r - x0) / (x1 - x0));
    }
    return 82;
  }
  const record = () => { const w = winsFor(rating()); return [w, 82 - w]; };
  const verdictOf = (w) => (w === 82 ? "Perfect season" : w >= 73 ? "All-time great" : w >= 60 ? "Title contender" : w >= 45 ? "Playoff team" : w >= 30 ? "Lottery bound" : "Tank commander");
  const ovrClass = (o) => (o >= 95 ? "elite" : o >= 88 ? "great" : o >= 78 ? "good" : "");
  // choice: o cevirmede kullanilan haklarin sirasi ("t", "y", "ty", "yt")
  const spinOf = (i) => st.spins[i][st.choice[i] || "main"];
  const current = () => spinOf(st.spin);
  const usedIds = () => new Set(Object.values(st.lineup).map((x) => x.id));
  const modeText = () => `${SPAN_LABEL[st.span]} · ${st.easy ? "Easy" : "Normal"}`;

  // ---------------- baslangic ----------------
  function picker() {
    const d = load(gameKey(true, prefs.span, prefs.easy), null);
    const resume = d && d.puzzle === data.puzzle && !d.done && Object.keys(d.lineup || {}).length;
    root.innerHTML = `
      <section class="card ez-setup">
        <div class="card-title">Era</div>
        <div class="seg seg-block" role="group" aria-label="Era">
          ${C.spans.map((s) => `<button type="button" class="${prefs.span === s ? "is-on" : ""}" data-span="${s}">${s === 1 ? "1 season" : `${s} seasons`}</button>`).join("")}
        </div>
        <p class="tiny dim">${prefs.span === 1 ? "Each spin is one team in one season." : `Each spin is a team over a ${prefs.span}-season stretch; every player from those years is there, with his best season.`}</p>
        <div class="card-title" style="margin-top:12px">Mode</div>
        <div class="seg seg-block" role="group" aria-label="Mode">
          <button type="button" class="${!prefs.easy ? "is-on" : ""}" data-easy="0">Normal</button>
          <button type="button" class="${prefs.easy ? "is-on" : ""}" data-easy="1">Easy</button>
        </div>
        <p class="tiny dim">${prefs.easy ? "Easy: move your players between spots any time before you finish the season." : "Normal: once a player is placed, he stays there."}</p>
        <div class="ez-setup-go">
          <button class="btn btn-primary btn-block" type="button" data-start="daily">${resume ? "Continue today's challenge" : "Play today's challenge"}</button>
          <button class="btn btn-block" type="button" data-start="random">Random game</button>
        </div>
        <p class="tiny dim" style="margin:8px 0 0">Each game you get one <b>new team</b> re-roll (same years, another team) and one <b>new years</b> re-roll (same team, another era). Ratings stay hidden until the season is played.</p>
      </section>`;
  }

  async function start(daily) {
    const key = gameKey(daily, prefs.span, prefs.easy);
    const saved = load(key, null);
    if (daily && saved && saved.puzzle === data.puzzle) { st = saved; return saved.done ? renderResult() : spinAnim(); }
    try {
      const res = await api(`/api/82-0/game?span=${prefs.span}&daily_game=${daily ? 1 : 0}`);
      st = { key, puzzle: daily ? data.puzzle : -1, daily, span: res.span, easy: prefs.easy, spins: res.spins,
             choice: {}, rr: { team: 1, year: 1 }, spin: 0, lineup: {}, done: false };
      selected = null; persist();
      window.scrollTo({ top: 0, behavior: "smooth" });
      spinAnim();
    } catch (err) { toast(err.message, true); }
  }

  // ---------------- kort ----------------
  const SPOT = { PG: [50, 80], SG: [84, 62], SF: [16, 62], PF: [30, 30], C: [68, 26] };
  function courtHtml(reveal) {
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
        const fromRoster = selected && selected.src === "roster";
        const fromSlot = selected && selected.src === "slot";
        const can = !st.done && !animating && ((fromRoster && !x) || (fromSlot && selected.slot !== s));
        const mover = fromSlot ? st.lineup[selected.slot] : fromRoster ? selected.p : null;
        const fitHint = can && mover ? (fits(mover.pos, s) ? "fit" : "off") : "";
        const pickable = st.easy && x && !st.done && !animating;
        const isSel = fromSlot && selected.slot === s;
        const off = x && !fits(x.pos, s);
        const enabled = can || pickable;
        return `<button type="button" class="ez-slot ${x ? "filled" : "open"} ${can ? "target " + fitHint : ""} ${isSel ? "is-sel" : ""}" data-slot="${s}" style="left:${l}%;top:${t}%" ${enabled ? "" : "disabled"}>
          <span class="ez-face">${x ? `<img src="${photo(x.id)}" alt="" onerror="this.nextElementSibling.hidden=false;this.remove()"><em hidden>${initials(x.name)}</em>` : `<em>${s}</em>`}
            ${x && reveal ? `<i class="ez-ovr ${ovrClass(effective(s))}">${effective(s)}</i>` : ""}</span>
          <span class="ez-tag">${x ? h(lastName(x.name)) : can ? (fitHint === "fit" ? "Put here" : `Off-position`) : s}</span>
          ${x ? `<span class="ez-sub ${off ? "off" : ""}" ${off ? 'title="Playing out of position"' : ""}>${s} · ${h(x.team)} ${yy(x.season)}</span>` : ""}
        </button>`;
      }).join("")}
    </div>`;
  }

  // ---------------- oyun ekrani ----------------
  function render() {
    if (st.done) return renderResult();
    const allIn = filled() >= C.slots.length;
    // Bes oyuncu da yerlestiyse (kolay mod) yeni cevirme yok: son takim gosterilir
    const sp = spinOf(Math.min(st.spin, C.spins - 1));
    const used = usedIds();
    const hint = selected && selected.src === "slot" ? `Tap another spot to move <b>${h(st.lineup[selected.slot].name)}</b> (swaps if taken).`
      : selected ? `Now tap a spot on the court for <b>${h(selected.p.name)}</b>.`
      : allIn ? "All five spots are filled." : "Pick one player from this team.";
    root.innerHTML = `
      <div class="ez-bar">
        <span class="chip">${st.daily ? `#${data.puzzle}` : "Random"} · ${modeText()}</span>
        <span class="chip">Spin ${Math.min(st.spin + 1, C.spins)} / ${C.spins}</span>
        <span class="ez-pips">${C.slots.map((s) => `<i class="${st.lineup[s] ? "on" : ""}">${s}</i>`).join("")}</span>
        <button class="btn btn-sm btn-ghost" type="button" data-menu>Change mode</button>
      </div>
      <div class="ez-grid">
        <div>${courtHtml(false)}
          ${st.easy ? `<p class="tiny dim center" style="margin-top:6px">Easy mode: tap a placed player, then another spot to move him.</p>` : ""}
          ${st.easy && allIn ? `<button class="btn btn-primary btn-block" type="button" id="ez-finish" style="margin-top:10px">Play the season</button>` : ""}
        </div>
        <section class="card ez-spin">
          ${allIn ? `<div class="ez-allin"><b>Lineup complete.</b><span>${st.easy ? "Move players between spots if you like, then play the season." : ""}</span></div>` : `
          <div class="ez-team ${animating ? "spinning" : revealing ? "landed" : ""}" id="ez-team">
            ${animating ? reelHtml(sp) : teamFace(sp)}
          </div>`}
          ${allIn ? "" : `<div class="ez-rerolls">
            <button class="btn btn-sm" type="button" data-reroll="team" ${st.rr.team && !animating ? "" : "disabled"}>New team <span class="dim">(${st.rr.team})</span></button>
            <button class="btn btn-sm" type="button" data-reroll="year" ${st.rr.year && !animating ? "" : "disabled"}>New years <span class="dim">(${st.rr.year})</span></button>
          </div>`}
          <p class="tiny dim" style="margin:6px 0 8px">${hint}</p>
          ${allIn ? "" : `<div class="ez-roster ${animating ? "is-spinning" : revealing ? "is-revealing" : ""}" id="ez-roster">${animating ? skeleton(sp.players.length) : sp.players.map((p, i) => {
            const dup = used.has(p.id);
            const sel = selected && selected.src === "roster" && selected.p.id === p.id;
            return `<button type="button" class="ez-p ${sel ? "is-sel" : ""}" data-pid="${p.id}" ${dup ? "disabled" : ""} style="--i:${i}">
              <img src="${photo(p.id)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
              <span class="ez-pn"><b>${h(p.name)}${st.span > 1 ? ` <span class="ez-yr">${yy(p.season)}</span>` : ""}</b>
                <small>${h(p.pos)} · ${p.pts.toFixed(1)} pts · ${p.reb.toFixed(1)} reb · ${p.ast.toFixed(1)} ast · ${p.stl.toFixed(1)} stl · ${p.blk.toFixed(1)} blk${dup ? " · on your team" : ""}</small></span>
            </button>`;
          }).join("")}</div>`}
        </section>
      </div>`;
  }

  function nextSpin() {
    st.spin += 1;
    if (filled() >= C.slots.length) {
      if (!st.easy) { st.done = true; persist(); return finish(); }
      persist(); return render();
    }
    persist(); spinAnim();
  }

  function clickSlot(slot) {
    if (!selected) {
      if (st.easy && st.lineup[slot]) { selected = { src: "slot", slot }; render(); }
      return;
    }
    if (selected.src === "roster") {
      if (st.lineup[slot]) return;
      const sp = current();
      st.lineup[slot] = Object.assign({ team: sp.abbr }, selected.p);
      selected = null;
      return nextSpin();
    }
    // Kolay mod: tasima / yer degistirme
    const from = selected.slot;
    if (from === slot) { selected = null; return render(); }
    const a = st.lineup[from], b = st.lineup[slot];
    st.lineup[slot] = a;
    if (b) st.lineup[from] = b; else delete st.lineup[from];
    selected = null; persist(); render();
  }

  // ---------------- cark ----------------
  const REEL_ITEMS = 18, REEL_MS = 1900;
  function teamFace(t) {
    return `${t.logo ? `<img class="ez-tlogo" src="${t.logo}" alt="" width="54" height="54" onerror="this.style.visibility='hidden'">` : `<span class="ez-nologo">${h(t.abbr)}</span>`}
      <div class="ez-tname"><span class="eyebrow" style="margin:0">${h(t.label)}</span><b>${h(t.name)}</b></div>`;
  }
  function reelHtml(target) {
    const fr = C.franchises, items = [];
    for (let k = 0; k < REEL_ITEMS - 1; k++) {
      const f = fr[Math.floor(Math.random() * fr.length)];
      const y = 1986 + Math.floor(Math.random() * (42 - st.span));
      const label = st.span === 1 ? `${y - 1}-${String(y).slice(2)}` : `${y - 1}-${y + st.span - 1}`;
      items.push({ logo: f.logo, abbr: f.abbr, name: f.name, label });
    }
    items.push(target);
    return `<div class="ez-reel"><div class="ez-strip" id="ez-strip">${items.map((t) => `<div class="ez-reel-item">${teamFace(t)}</div>`).join("")}</div></div>`;
  }
  function skeleton(n) {
    return Array.from({ length: n }, (_, i) => `<div class="ez-skel" style="--i:${i}"><i></i><span><b></b><small></small></span></div>`).join("");
  }
  function spinAnim() {
    if (filled() >= C.slots.length) return render();
    animating = true; render();
    const strip = $("#ez-strip");
    const done = () => { if (!animating) return; animating = false; revealing = true; render(); revealing = false; };
    if (!strip) return done();
    const item = strip.firstElementChild.getBoundingClientRect().height;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      strip.style.transition = `transform ${REEL_MS}ms cubic-bezier(.12,.72,.18,1)`;
      strip.style.transform = `translateY(${-(REEL_ITEMS - 1) * item}px)`;
    }));
    strip.addEventListener("transitionend", done, { once: true });
    setTimeout(done, REEL_MS + 300);
  }

  // ---------------- tiklamalar ----------------
  root.addEventListener("click", (e) => {
    const sp = e.target.closest("[data-span]");
    if (sp) { prefs.span = +sp.dataset.span; save(PREFS, prefs); return picker(); }
    const ez = e.target.closest("[data-easy]");
    if (ez) { prefs.easy = ez.dataset.easy === "1"; save(PREFS, prefs); return picker(); }
    const go = e.target.closest("[data-start]");
    if (go) return start(go.dataset.start === "daily");
    if (e.target.closest("[data-menu]")) { selected = null; return picker(); }
    if (animating) return;
    const p = e.target.closest("[data-pid]");
    if (p && !p.disabled) {
      const pl = current().players.find((x) => x.id === p.dataset.pid);
      selected = selected && selected.src === "roster" && selected.p.id === pl.id ? null : { src: "roster", p: pl };
      render();
      if (selected && matchMedia("(max-width: 900px)").matches) $(".ez-court").scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const s = e.target.closest("[data-slot]");
    if (s && !s.disabled) return clickSlot(s.dataset.slot);
    const rr = e.target.closest("[data-reroll]");
    if (rr && !rr.disabled) {
      const kind = rr.dataset.reroll;
      if (!st.rr[kind]) return;
      st.rr[kind] -= 1; st.choice[st.spin] = (st.choice[st.spin] || "") + kind[0]; selected = null;
      persist(); return spinAnim();
    }
    if (e.target.closest("#ez-finish")) { st.done = true; selected = null; persist(); return finish(); }
    if (e.target.closest("#ez-share")) return share();
    if (e.target.closest("#ez-again")) return start(false);
  });

  // ---------------- sonuc ----------------
  function finish() {
    const [w] = record();
    const tag = `${data.puzzle}-${st.span}${st.easy ? "e" : ""}`;
    if (st.daily && stats.last !== tag) {
      stats.last = tag; stats.played += 1; stats.best = Math.max(stats.best, w);
      if (w === 82) stats.perfect += 1;
      save(STATS, stats);
      if (window.gtag) gtag("event", "eightytwo_finish", { wins: w, span: st.span, easy: st.easy });
    }
    renderResult(true);
  }

  function renderResult(animate) {
    const r = rating(), [w, l] = record();
    root.innerHTML = `
      <div class="ez-bar"><span class="chip">${st.daily ? `#${data.puzzle}` : "Random"} · ${modeText()}</span>
        <button class="btn btn-sm btn-ghost" type="button" data-menu>Change mode</button></div>
      <div class="ez-grid">
        <div>${courtHtml(true)}</div>
        <section class="card ez-result">
          <div class="eyebrow">${st.daily ? `82-0 #${data.puzzle}` : "Random game"}</div>
          <div class="ez-record"><span id="ez-w">${animate ? 0 : w}</span>-<span id="ez-l">${animate ? 0 : l}</span></div>
          <div class="ez-verdict ${w === 82 ? "perfect" : ""}">${verdictOf(w)}</div>
          <p class="small muted">Team rating <b>${r.toFixed(1)}</b> · stars count most${C.slots.some((s) => !fits(st.lineup[s].pos, s)) ? " · off-position penalty applied" : ""}</p>
          <div class="ez-reveal">${C.slots.map((s) => { const x = st.lineup[s], e2 = effective(s);
            return `<div><span>${s}</span><b>${h(x.name)}</b><small>${h(x.team)} ${yy(x.season)}</small><i class="ez-ovr ${ovrClass(e2)}">${e2}</i></div>`; }).join("")}</div>
          <div class="dp-actions">
            <button class="btn btn-primary" id="ez-share" type="button">Share season</button>
            <button class="btn" id="ez-again" type="button">Random game</button>
          </div>
          ${st.daily ? `<div class="dp-stats"><div><b>${stats.played}</b><span>Played</span></div><div><b>${stats.best}</b><span>Best wins</span></div><div><b>${stats.perfect}</b><span>82-0s</span></div></div>
            <p class="small muted" style="margin-top:12px">New spins every day at midnight UK time. Try another era from "Change mode".</p>` : ""}
          ${data.signed_in ? "" : `<div class="dp-keep"><div><b>Like daily games?</b><span>Free account: keep your Mystery Player streak on every device and save mock drafts.</span></div>
            <a class="btn btn-primary btn-sm" href="/register?next=%2F82-0">Create free account</a></div>`}
        </section>
      </div>`;
    if (animate) {
      let i = 0; const steps = 30;
      const t = setInterval(() => {
        i++;
        $("#ez-w").textContent = Math.round(w * i / steps); $("#ez-l").textContent = Math.round(l * i / steps);
        if (i >= steps) clearInterval(t);
      }, 35);
    }
  }

  async function share() {
    const [w, l] = record();
    const head = st.daily ? `HoopLife 82-0 #${data.puzzle}` : "HoopLife 82-0";
    const text = `${head} (${modeText()}): I went ${w}-${l}${w === 82 ? " 🏆" : ""}. Can you beat it? ${location.origin}/82-0?ref=82-0-share${window.HL.inv()}`;
    if (window.gtag) gtag("event", "eightytwo_share", { wins: w });
    const btn = $("#ez-share"); if (btn) btn.classList.add("is-loading");
    try { await HLCard.share(await card(w, l), { filename: `82-0-${w}-${l}.png`, text, title: "82-0 Challenge" }); }
    catch (err) { toast("Could not create the image.", true); }
    finally { if (btn) btn.classList.remove("is-loading"); }
  }

  async function card(w, l) {
    const K = HLCard;
    const { cv, g } = await K.base("82-0 CHALLENGE", st.daily ? data.puzzle : "");
    K.text(g, `${w}-${l}`, K.W / 2, 330, { weight: 900, size: 190, align: "center", color: w === 82 ? K.C.gold : "#fff" });
    K.pill(g, verdictOf(w).toUpperCase(), K.W / 2, 392, { bg: w === 82 ? K.C.gold : "rgba(255,255,255,.12)", color: w === 82 ? "#1B1300" : "#fff", size: 30, h: 56, padX: 26 });
    K.text(g, `${modeText().toUpperCase()} · RATING ${rating().toFixed(1)}`, K.W / 2, 462, { weight: 800, size: 28, color: K.C.muted, align: "center" });

    const x0 = 60, y0 = 500, cw = K.W - 120, ch = 720;
    K.rr(g, x0, y0, cw, ch, 28); g.save(); g.clip();
    const wood = g.createLinearGradient(0, y0, 0, y0 + ch); wood.addColorStop(0, "#C88446"); wood.addColorStop(1, "#A9692F");
    g.fillStyle = wood; g.fillRect(x0, y0, cw, ch);
    for (let x = x0; x < x0 + cw; x += 46) { g.fillStyle = "rgba(0,0,0,.05)"; g.fillRect(x, y0, 2, ch); }
    g.strokeStyle = "rgba(255,255,255,.85)"; g.lineWidth = 4;
    const px = (v) => x0 + cw * v / 100, py = (v) => y0 + ch * v / 70, pct = (v) => y0 + ch * v / 100;
    g.fillStyle = "rgba(122,32,32,.55)"; g.fillRect(px(34), py(0), px(66) - px(34), py(38) - py(0)); g.strokeRect(px(34), py(0), px(66) - px(34), py(38) - py(0));
    g.beginPath(); g.ellipse(px(50), py(38), cw * .12, ch * .12, 0, 0, Math.PI * 2); g.stroke();
    g.beginPath(); g.moveTo(px(6), py(0)); g.lineTo(px(6), py(18)); g.ellipse(px(50), py(18), cw * .44, ch * .42, 0, Math.PI, 0, true); g.lineTo(px(94), py(0)); g.stroke();
    g.strokeStyle = "#FF7A1A"; g.beginPath(); g.arc(px(50), py(8), 16, 0, Math.PI * 2); g.stroke();
    g.restore();

    const imgs = await Promise.all(C.slots.map((s) => K.loadImg(photo(st.lineup[s].id, 350, 254))));
    C.slots.forEach((s, i) => {
      const x = st.lineup[s], [sx, sy] = SPOT[s];
      const cx = px(sx), cy = pct(sy) - 40, eff = effective(s);
      K.disc(g, imgs[i], cx, cy, 72, { ring: eff >= 95 ? K.C.gold : "#fff", ringW: 7, name: x.name });
      const bg = eff >= 95 ? K.C.gold : eff >= 88 ? "#1E9E5A" : eff >= 78 ? "#2F6FB6" : "#3A4357";
      K.pill(g, String(eff), cx + 60, cy + 50, { bg, color: eff >= 95 ? "#1B1300" : "#fff", size: 28, h: 46, padX: 12 });
      K.pill(g, lastName(x.name).toUpperCase(), cx, cy + 98, { size: 25, h: 42 });
      K.pill(g, `${s} · ${x.team} ${yy(x.season)}`, cx, cy + 136, { bg: "rgba(255,255,255,.9)", color: "#0B0F17", size: 20, h: 32, weight: 800 });
    });
    K.footer(g, "/82-0");
    return cv;
  }

  // Acilis: yarim kalmis gunluk oyun varsa oradan devam, yoksa mod secimi
  const pending = load(gameKey(true, prefs.span, prefs.easy), null);
  if (pending && pending.puzzle === data.puzzle && !pending.done) { st = pending; spinAnim(); }
  else picker();
})();
