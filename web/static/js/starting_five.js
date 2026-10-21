// Starting Five: gecmis bir playoff macinin gizli ilk-bes oyunculari.
// Isimler tarayicida yok; her tahmini sunucu kontrol ediyor.
(function () {
  const { $, api, toast, escapeHtml: h } = window.HL;
  const data = JSON.parse($("#sf-data").textContent);
  const root = $("#sf-game");
  const KEY = "hl_sf_game", STATS = "hl_sf_stats";
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const photo = (id) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=110&h=80`;
  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[.'’-]/g, " ").replace(/\b(jr|sr|ii|iii|iv)\b/g, " ").replace(/\s+/g, " ").trim();
  const allNames = data.names.map((n) => ({ n, k: norm(n) }));

  const stats = Object.assign({ played: 0, total: 0, perfect: 0, last: 0 }, load(STATS, {}));
  let mode = "daily", game = data.game;
  let st = load(KEY, null);
  if (!st || st.puzzle !== data.puzzle) st = { puzzle: data.puzzle, found: {}, misses: [], done: false, revealed: null };

  const slotKey = (t, s) => `${t}-${s}`;
  const foundCount = () => Object.keys(st.found).length;
  const persist = () => { if (mode === "daily") save(KEY, st); };

  // ---------------- kort ----------------
  // Kort olculeri ayak cinsinden (94 x 50). Masaustunde yatay, telefonda
  // dikey: dikeyde kortun uzunlugu ekranin boyuna gider.
  const vertical = () => matchMedia("(max-width: 640px)").matches;
  // Sol yari sahadaki yerler (pota x=5.25). Sag takim aynalanir.
  const SPOTS = { G: [[31, 25], [24, 8.5]], F: [[24, 41.5], [13.5, 38]], C: [[11, 13]] };
  // Dikey kort dar: kartlar uc sira halinde (pivot, forvetler, gardlar)
  const SPOTS_V = { G: [[36, 33], [36, 17]], F: [[20, 43], [20, 7]], C: [[9, 25]] };
  const ORDER = [["G", 0], ["G", 1], ["F", 0], ["F", 1], ["C", 0]];
  const group = (pos) => (/C/.test(pos || "") ? "C" : /G/.test(pos || "") ? "G" : "F");

  function spotsFor(slots, vert = vertical()) {
    const free = ORDER.slice();
    const take = (g) => { const k = free.findIndex(([x]) => x === g); return k >= 0 ? free.splice(k, 1)[0] : null; };
    const picked = slots.map((s) => take(group(s.pos)));
    const spots = vert ? SPOTS_V : SPOTS;
    return picked.map((p) => p || free.shift()).map(([g, n]) => spots[g][n]);
  }

  function place(x, y, mirror) {
    if (mirror) x = 94 - x;
    return vertical() ? { left: (50 - y) / 50 * 100, top: x / 94 * 100 } : { left: x / 94 * 100, top: y / 50 * 100 };
  }

  function courtSvg() {
    const half = `<rect x="0" y="17" width="19" height="16" class="paint"/>
      <circle cx="19" cy="25" r="6" class="ln"/>
      <path d="M0 3 L14 3 A23.75 23.75 0 0 1 14 47 L0 47" class="ln"/>
      <path d="M4 25 m0 -4 l0 8" class="ln"/><circle cx="5.25" cy="25" r=".9" class="rim"/>
      <path d="M9 21 A4 4 0 0 1 9 29" class="ln"/>`;
    const body = `<rect x="0" y="0" width="94" height="50" class="floor"/>
      <rect x=".3" y=".3" width="93.4" height="49.4" class="ln"/>
      <line x1="47" y1="0" x2="47" y2="50" class="ln"/><circle cx="47" cy="25" r="6" class="ln"/><circle cx="47" cy="25" r="2" class="ln"/>
      <g>${half}</g><g transform="translate(94 0) scale(-1 1)">${half}</g>`;
    return vertical()
      ? `<svg class="sf-court-svg" viewBox="0 0 50 94" preserveAspectRatio="none" aria-hidden="true"><g transform="translate(50 0) rotate(90)">${body}</g></svg>`
      : `<svg class="sf-court-svg" viewBox="0 0 94 50" preserveAspectRatio="none" aria-hidden="true">${body}</svg>`;
  }

  function tokenHtml(team, ti, slot, si, spot) {
    const f = st.found[slotKey(ti, si)];
    const missed = st.done && !slot.given && !f && st.revealed;
    const who = slot.given ? slot : f || (missed ? st.revealed[ti][si] : null);
    const state = (slot.given ? "given" : f ? "found" : missed ? "missed" : "empty") + (lastFound === slotKey(ti, si) ? " just" : "");
    const at = place(spot[0], spot[1], ti === 1);
    const last = who ? who.name.split(" ").slice(1).join(" ") || who.name : "???";
    return `<button type="button" class="sf-tok ${state}" style="left:${at.left}%;top:${at.top}%;--team:${team.color}"
        data-tip="${h((who ? who.name + " · " : "") + `${slot.pos || "?"}${slot.jersey ? " #" + slot.jersey : ""} · ${slot.pts} PTS, ${slot.reb} REB, ${slot.ast} AST in ${slot.min} min`)}">
      <span class="sf-face">${who ? `<img src="${photo(who.id)}" alt="" loading="lazy" onerror="this.nextElementSibling.hidden=false;this.remove()"><em hidden>${h(slot.pos || "?")}</em>` : `<em>${h(slot.pos || "?")}</em>`}
        ${slot.jersey ? `<i class="sf-num">${h(slot.jersey)}</i>` : ""}</span>
      <span class="sf-name">${h(last)}</span>
      <span class="sf-line">${slot.pts}p ${slot.reb}r ${slot.ast}a</span>
    </button>`;
  }

  function courtHtml(g) {
    const marks = g.teams.map((t, ti) => {
      const at = place(23.5, 25, ti === 1);
      return `<img class="sf-mark" src="${t.logo}" alt="" style="left:${at.left}%;top:${at.top}%">
        <span class="sf-half-tag" style="${vertical() ? (ti ? "bottom:6px" : "top:6px") + ";left:8px" : (ti ? "right:8px" : "left:8px") + ";top:6px"}">${h(t.abbr)}</span>`;
    }).join("");
    const toks = g.teams.map((t, ti) => { const sp = spotsFor(t.slots); return t.slots.map((s, si) => tokenHtml(t, ti, s, si, sp[si])).join(""); }).join("");
    return `<div class="sf-court ${vertical() ? "is-vertical" : ""}">${courtSvg()}${marks}${toks}</div>
      <p class="tiny dim center" style="margin-top:6px">Tap a player for his full line from this game.</p>`;
  }

  function render() {
    const g = game;
    const misses = st.misses.length, left = g.max_misses - misses;
    root.innerHTML = `
      <div class="sf-head card">
        <div class="sf-meta"><span class="chip chip-accent">${h(g.title)}</span><span class="dim small">${h(g.season)} season · ${new Date(g.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span></div>
        <div class="sf-score">
          ${g.teams.map((t) => `<div class="sf-team"><img src="${t.logo}" alt="" width="44" height="44"><b>${h(t.abbr)}</b><span class="sf-pts">${t.score}</span></div>`).join('<span class="sf-dash">–</span>')}
        </div>
      </div>
      ${st.done ? "" : `
      <div class="dp-search sf-search" id="sf-search">
        <input class="input" id="sf-input" type="search" autocomplete="off" spellcheck="false" placeholder="Name a starter..." aria-label="Name a starter" role="combobox" aria-expanded="false">
        <ul class="dp-list" id="sf-list" role="listbox" hidden></ul>
        <div class="small muted sf-status"><span><b>${foundCount()}</b> / ${g.hidden} found</span>
          <span class="sf-lives">${Array.from({ length: g.max_misses }, (_, i) => `<i class="${i < misses ? "used" : ""}"></i>`).join("")} ${left} miss${left === 1 ? "" : "es"} left</span>
          <button class="btn btn-sm btn-ghost" id="sf-share" type="button">Share ${foundCount()}/${g.hidden}</button>
          <button class="btn btn-sm btn-ghost" id="sf-giveup" type="button">Give up</button></div>
        ${st.misses.length ? `<div class="sf-misses tiny dim">Not starters: ${st.misses.map(h).join(", ")}</div>` : ""}
      </div>`}
      ${courtHtml(g)}
      <div id="sf-result"></div>`;
    if (st.done) renderResult();
    else bindSearch();
  }

  // ---------------- arama ----------------
  function bindSearch() {
    const input = $("#sf-input"), list = $("#sf-list");
    let matches = [], active = 0;
    const known = () => new Set([...game.teams.flatMap((t) => t.slots.filter((s) => s.given).map((s) => norm(s.name))),
                                 ...Object.values(st.found).map((f) => norm(f.name)), ...st.misses.map(norm)]);
    const draw = () => {
      list.hidden = !matches.length;
      input.setAttribute("aria-expanded", matches.length ? "true" : "false");
      list.innerHTML = matches.map((m, i) => `<li><button type="button" data-name="${h(m.n)}" class="${i === active ? "is-active" : ""}"><span>${h(m.n)}</span></button></li>`).join("");
    };
    input.addEventListener("input", () => {
      const q = norm(input.value);
      const skip = known();
      matches = q.length < 2 ? [] : allNames.filter((m) => !skip.has(m.k) && (m.k.startsWith(q) || m.k.split(" ").some((w) => w.startsWith(q)))).slice(0, 8);
      active = 0; draw();
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" && matches.length) { active = (active + 1) % matches.length; draw(); e.preventDefault(); }
      else if (e.key === "ArrowUp" && matches.length) { active = (active - 1 + matches.length) % matches.length; draw(); e.preventDefault(); }
      else if (e.key === "Enter") { e.preventDefault(); if (matches[active]) guess(matches[active].n); }
    });
    list.addEventListener("mousedown", (e) => e.preventDefault());
    list.addEventListener("click", (e) => { const b = e.target.closest("[data-name]"); if (b) guess(b.dataset.name); });
  }

  let busy = false, lastFound = null;
  async function guess(name) {
    if (busy || st.done) return;
    busy = true;
    try {
      const res = await api("/api/starting-five/guess", { method: "POST", body: { game: game.id, name } });
      if (res.hits.length) {
        res.hits.forEach((x) => { st.found[slotKey(x.team, x.slot)] = { name: x.name, id: x.id }; });
        lastFound = slotKey(res.hits[0].team, res.hits[0].slot);
        toast(`${res.hits[0].name} started!`);
      } else {
        lastFound = null;
        st.misses.push(name);
      }
      if (foundCount() >= game.hidden || st.misses.length >= game.max_misses) await end();
      persist(); render();
      const inp = $("#sf-input"); if (inp) inp.focus();
    } catch (err) { toast(err.message, true); }
    finally { busy = false; }
  }

  async function end() {
    try { st.revealed = (await api("/api/starting-five/reveal", { method: "POST", body: { game: game.id } })).teams; } catch (e) { st.revealed = null; }
    st.done = true;
    if (mode === "daily" && stats.last !== data.puzzle) {
      stats.last = data.puzzle; stats.played += 1; stats.total += foundCount();
      if (foundCount() >= game.hidden) stats.perfect += 1;
      save(STATS, stats);
      if (window.gtag) gtag("event", "startingfive_finish", { found: foundCount() });
    }
  }

  // ---------------- sonuc / paylasim ----------------
  function shareText() {
    const ticks = game.teams.map((t, ti) => t.slots.map((s, si) => (s.given ? "" : st.found[slotKey(ti, si)] ? "🟩" : "⬛")).join("")).join(" ");
    const head = mode === "daily" ? `HoopLife Starting Five #${data.puzzle}` : "HoopLife Starting Five (practice)";
    const prog = st.done ? "" : " so far";
    return `${head} · ${game.teams.map((t) => t.abbr).join(" vs ")} ${game.season}\n${foundCount()}/${game.hidden}${prog} ${ticks}\n${location.origin}/starting-five?ref=startingfive-share${window.HL.inv()}`;
  }
  async function share() {
    const text = `${mode === "daily" ? `HoopLife Starting Five #${data.puzzle}` : "HoopLife Starting Five"}: I named ${foundCount()}/${game.hidden} starters from ${game.teams.map((t) => t.abbr).join(" vs ")} (${game.season}). ${location.origin}/starting-five?ref=startingfive-share${window.HL.inv()}`;
    if (window.gtag) gtag("event", "startingfive_share");
    try { await HLCard.share(await card(), { filename: "starting-five.png", text, title: "Starting Five" }); }
    catch (err) { toast("Could not create the image.", true); }
  }

  // Spoiler'siz gorsel: acik verilen iki oyuncu fotografli, bulunanlar
  // yesil tik, bulunamayanlar soru isareti. Gizli isimler gorselde yok.
  async function card() {
    const K = HLCard, g0 = game;
    const { cv, g } = await K.base("STARTING FIVE", mode === "daily" ? data.puzzle : "");
    K.text(g, g0.title.toUpperCase(), K.W / 2, 200, { weight: 800, size: 30, color: K.C.muted, align: "center", max: 960 });
    const logos = await Promise.all(g0.teams.map((t) => K.loadImg(t.logo)));
    g0.teams.forEach((t, ti) => {
      const cx = ti ? K.W - 250 : 250;
      if (logos[ti]) g.drawImage(logos[ti], cx - 60, 230, 120, 120);
      K.text(g, t.abbr, cx, 392, { weight: 900, size: 40, align: "center" });
      K.text(g, String(t.score), ti ? K.W / 2 + 130 : K.W / 2 - 130, 322, { weight: 900, size: 88, align: "center" });
    });
    K.text(g, "–", K.W / 2, 322, { weight: 900, size: 70, align: "center", color: K.C.dim });
    K.text(g, `${g0.season} season`, K.W / 2, 392, { weight: 700, size: 26, color: K.C.dim, align: "center" });
    const n = foundCount();
    K.text(g, `${n}/${g0.hidden}`, K.W / 2, 530, { weight: 900, size: 120, align: "center", color: n === g0.hidden ? K.C.good : "#fff" });
    K.text(g, n === g0.hidden ? "PERFECT LINEUP" : "STARTERS NAMED", K.W / 2, 580, { weight: 800, size: 28, align: "center", color: K.C.muted });

    // Tam saha
    const x0 = 40, y0 = 630, cw = K.W - 80, ch = cw * 50 / 94;
    K.rr(g, x0, y0, cw, ch, 26); g.save(); g.clip();
    const wood = g.createLinearGradient(0, y0, 0, y0 + ch); wood.addColorStop(0, "#C88446"); wood.addColorStop(1, "#A9692F");
    g.fillStyle = wood; g.fillRect(x0, y0, cw, ch);
    const fx = (v) => x0 + cw * v / 94, fy = (v) => y0 + ch * v / 50;
    g.strokeStyle = "rgba(255,255,255,.85)"; g.lineWidth = 3;
    g.beginPath(); g.moveTo(fx(47), fy(0)); g.lineTo(fx(47), fy(50)); g.stroke();
    g.beginPath(); g.arc(fx(47), fy(25), cw * 6 / 94, 0, Math.PI * 2); g.stroke();
    [0, 1].forEach((m) => {
      const X = (v) => fx(m ? 94 - v : v);
      g.fillStyle = "rgba(122,32,32,.55)"; const a = X(0), b = X(19);
      g.fillRect(Math.min(a, b), fy(17), Math.abs(b - a), fy(33) - fy(17)); g.strokeRect(Math.min(a, b), fy(17), Math.abs(b - a), fy(33) - fy(17));
      g.beginPath(); g.arc(X(19), fy(25), cw * 6 / 94, 0, Math.PI * 2); g.stroke();
      // uc sayi yayi: pota merkezli, 23.75 ayak
      const hx = X(5.25), hy = fy(25), rx = cw * 23.75 / 94;
      const half = Math.PI / 2 - 0.36;
      g.beginPath(); m ? g.arc(hx, hy, rx, Math.PI - half, Math.PI + half) : g.arc(hx, hy, rx, -half, half); g.stroke();
    });
    g.restore();

    const shown = [];
    g0.teams.forEach((t, ti) => t.slots.forEach((sl, si) => { if (sl.given) shown.push(sl.id); }));
    const imgs = new Map(await Promise.all(shown.map(async (id) => [id, await K.loadImg(`https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=220&h=160`)])));
    g0.teams.forEach((t, ti) => {
      const sp = spotsFor(t.slots, false);
      t.slots.forEach((sl, si) => {
        let [x, y] = sp[si]; if (ti) x = 94 - x;
        const cx = fx(x), cy = fy(y), r = 40;
        const found = st.found[slotKey(ti, si)];
        if (sl.given) {
          K.disc(g, imgs.get(sl.id), cx, cy, r, { ring: t.color, ringW: 5, name: sl.name });
          K.pill(g, sl.name.split(" ").slice(-1)[0], cx, cy + r + 18, { size: 18, h: 30, padX: 9 });
        } else {
          g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2);
          g.fillStyle = found ? K.C.good : "rgba(11,15,23,.8)"; g.fill();
          g.lineWidth = 5; g.strokeStyle = found ? "#fff" : st.done ? K.C.bad : "rgba(255,255,255,.7)"; g.stroke();
          K.text(g, found ? "✓" : "?", cx, cy + 16, { weight: 900, size: 46, align: "center", color: found ? "#0B0F17" : "#fff" });
          K.pill(g, sl.pos || "?", cx, cy + r + 18, { size: 18, h: 30, padX: 9 });
        }
      });
    });
    K.footer(g, "/starting-five");
    return cv;
  }

  function renderResult() {
    const n = foundCount(), avg = stats.played ? (stats.total / stats.played).toFixed(1) : "-";
    $("#sf-result").innerHTML = `
      <div class="card sm-result">
        <div class="eyebrow">${n >= game.hidden ? "Perfect lineup" : "Final"}</div>
        <h2>${n} / ${game.hidden}</h2>
        <div class="dp-actions">
          <button class="btn btn-primary" id="sf-share" type="button">Share result</button>
          <button class="btn" id="sf-practice" type="button">Play a random game</button>
        </div>
        ${mode === "daily" ? `<div class="dp-stats"><div><b>${stats.played}</b><span>Played</span></div><div><b>${avg}</b><span>Average</span></div><div><b>${stats.perfect}</b><span>Perfect</span></div></div>
        <p class="small muted" style="margin-top:12px">A new game every day at midnight UK time. Also try <a href="/stat-match">Stat Match</a> and <a href="/daily">Mystery Player</a>.</p>` : ""}
        ${data.signed_in ? "" : `<div class="dp-keep"><div><b>Like daily games?</b><span>Free account: keep your daily game streaks on every device and track players.</span></div>
          <a class="btn btn-primary btn-sm" href="/register?next=%2Fstarting-five">Create free account</a></div>`}
      </div>`;
  }

  root.addEventListener("click", async (e) => {
    const tok = e.target.closest(".sf-tok");
    if (tok) return toast(tok.dataset.tip);
    if (e.target.closest("#sf-share")) return share();
    if (e.target.closest("#sf-giveup")) {
      if (!confirm("Show the full lineups?")) return;
      await end(); persist(); return render();
    }
    if (e.target.closest("#sf-practice")) {
      try {
        const res = await api("/api/starting-five/random");
        mode = "practice"; game = res.game;
        st = { puzzle: -1, found: {}, misses: [], done: false, revealed: null };
        render(); window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (err) { toast(err.message, true); }
    }
  });

  // Telefon donunce kort yatay/dikey yeniden cizilir
  let wasVertical = vertical();
  addEventListener("resize", () => {
    if (vertical() === wasVertical) return;
    wasVertical = vertical();
    const typed = $("#sf-input") ? $("#sf-input").value : "";
    render();
    if (typed && $("#sf-input")) $("#sf-input").value = typed;
  });

  render();
})();
