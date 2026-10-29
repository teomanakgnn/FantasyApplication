// NBA Career: draft gecesinden emeklilige secimlerle bir kariyer. Her sezon simule
// edilir (gelisim, rol, istatistik, galibiyet, playoff, sakatlik, oduller); yazlari
// kararlar (antrenman, kontrat, serbest oyuncu, takas, olaylar). Sonda kariyer ozeti,
// Hall of Fame ihtimali, toplam kazanc ve paylasim. Ilerleme bu cihazda saklanir.
(function () {
  const { $, toast, escapeHtml: h } = window.HL;
  const D = JSON.parse($("#cr-data").textContent);
  const app = $("#cr-app");
  const KEY = "hl_career_v1", BEST = "hl_career_best";
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const rnd = Math.random;
  const gauss = (m = 0, s = 1) => { let u = 0, v = 0; while (!u) u = rnd(); while (!v) v = rnd(); return m + s * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const sig = (x) => 1 / (1 + Math.exp(-x));
  const pick = (arr) => arr[Math.floor(rnd() * arr.length)];
  const money = (m) => (m >= 1000 ? `$${(m / 1000).toFixed(2)}B` : `$${m >= 100 ? Math.round(m) : m.toFixed(1)}M`);
  const ord = (n) => n + (["th", "st", "nd", "rd"][(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10 < 4 ? n % 10 : 0] || "th");
  const FIRST_YEAR = 2028;                      // ilk sezon 2027-28 (2027 draft'i)
  const seasonLabel = (y) => `${y - 1}-${String(y).slice(2)}`;

  // ---------------- oyuncu tipleri ve mevkiler ----------------
  const ARCH = {
    scorer: { label: "Scorer", desc: "Buckets in bunches. Scoring titles and All-Star nods.", pts: 1.18, ast: 0.95, reb: 0.95, stl: 0.9, blk: 0.8, tpm: 1.15, def: 0.9 },
    playmaker: { label: "Playmaker", desc: "Runs the offense. Assists, wins and MVP votes.", pts: 0.97, ast: 1.45, reb: 0.9, stl: 1.15, blk: 0.7, tpm: 1.0, def: 0.95 },
    threeD: { label: "3&D Wing", desc: "Shoots it and guards the best player. Every contender wants one.", pts: 0.85, ast: 0.85, reb: 1.0, stl: 1.3, blk: 1.05, tpm: 1.5, def: 1.2 },
    rim: { label: "Rim Protector", desc: "Blocks, boards, defense. DPOY is in reach.", pts: 0.8, ast: 0.8, reb: 1.35, stl: 0.8, blk: 1.9, tpm: 0.25, def: 1.35 },
    twoway: { label: "Two-Way Star", desc: "Does a bit of everything on both ends.", pts: 1.05, ast: 1.0, reb: 1.05, stl: 1.2, blk: 1.15, tpm: 0.95, def: 1.15 },
  };
  const POS = {
    PG: { reb: 4.2, ast: 6.8, stl: 1.4, blk: 0.3, tpm: 2.4 }, SG: { reb: 4.6, ast: 4.2, stl: 1.3, blk: 0.4, tpm: 2.6 },
    SF: { reb: 6.2, ast: 3.4, stl: 1.2, blk: 0.7, tpm: 2.0 }, PF: { reb: 8.2, ast: 2.8, stl: 0.9, blk: 1.1, tpm: 1.3 },
    C: { reb: 10.8, ast: 2.4, stl: 0.8, blk: 1.8, tpm: 0.6 },
  };
  const ROLES = { star: { label: "Franchise star", min: 35 }, starter: { label: "Starter", min: 31 }, rotation: { label: "Rotation player", min: 22 }, bench: { label: "Bench", min: 13 } };
  const DEV = ["C", "B", "A"];

  // ---------------- lig ----------------
  const freshTeams = () => Object.fromEntries(D.teams.map((t) => [t.abbr, { ...t, dev: Math.floor(rnd() * 3) }]));
  const T = (st, abbr) => st.teams[abbr];
  const byStrength = (st) => Object.values(st.teams).sort((a, b) => a.s - b.s);

  // ---------------- para ----------------
  // Piyasa degeri (milyon $, bugunun parasi) OVR'ye gore; maas tavani yilda %4 buyur
  function marketValue(ovr, yearIdx) {
    const pts = [[55, 1.2], [62, 2.5], [68, 5], [72, 9], [76, 15], [80, 24], [84, 35], [87, 45], [90, 54], [93, 62], [99, 66]];
    let v = pts[0][1];
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
      if (ovr <= x1) { v = y0 + (y1 - y0) * (Math.max(ovr, x0) - x0) / (x1 - x0); break; }
      v = y1;
    }
    return v * Math.pow(1.04, yearIdx);
  }
  const rookieScale = (pick) => Math.max(2.6, 13.2 * (1 - (pick - 1) * 0.031));
  // Sponsorluk: yalnizca gercek yildizlarda buyuk (un 40 ~ $4M, 70 ~ $16M, 100 ~ $40M / yil)
  const endorsements = (fame) => Math.pow(clamp(fame, 0, 100), 2.5) / 2500;

  // ---------------- durum ----------------
  let st = load(KEY, null);
  const persist = () => save(KEY, st);

  // ================= EKRANLAR =================
  function screenCreate() {
    const best = load(BEST, []);
    let pos = "SG", arch = "scorer";
    app.innerHTML = `
      <section class="card cr-create">
        <div class="card-title">Your player</div>
        <label class="field"><span>Name</span><input class="input" id="cr-name" maxlength="24" placeholder="e.g. Jaylen Carter" value="${h(load("hl_career_name", ""))}"></label>
        <div class="field"><span>Position</span><div class="seg seg-block" id="cr-pos">${Object.keys(POS).map((p) => `<button type="button" data-pos="${p}" class="${p === pos ? "is-on" : ""}">${p}</button>`).join("")}</div></div>
        <div class="field"><span>Player type</span><div class="cr-archs" id="cr-arch">${Object.entries(ARCH).map(([k, a]) => `<button type="button" data-arch="${k}" class="cr-arch ${k === arch ? "is-on" : ""}"><b>${a.label}</b><small>${a.desc}</small></button>`).join("")}</div></div>
        <button class="btn btn-primary btn-block" id="cr-go">Enter the draft</button>
      </section>
      ${best.length ? `<section class="card" style="margin-top:12px"><div class="card-title">Your best careers</div>
        <div class="cr-best">${best.map((b) => `<div><b>${h(b.name)}</b> <span class="dim small">${h(b.pos)} · ${b.seasons} seasons</span><span>${h(b.line)}</span></div>`).join("")}</div></section>` : ""}`;
    app.onclick = (e) => {
      const p = e.target.closest("[data-pos]");
      if (p) { pos = p.dataset.pos; app.querySelectorAll("[data-pos]").forEach((b) => b.classList.toggle("is-on", b === p)); return; }
      const a = e.target.closest("[data-arch]");
      if (a) { arch = a.dataset.arch; app.querySelectorAll("[data-arch]").forEach((b) => b.classList.toggle("is-on", b === a)); return; }
      if (e.target.closest("#cr-go")) {
        const name = $("#cr-name").value.trim().replace(/\s+/g, " ").slice(0, 24);
        if (name.length < 3) return toast("Give your player a name.", true);
        save("hl_career_name", name);
        newCareer(name, pos, arch);
      }
    };
  }

  function newCareer(name, pos, arch) {
    st = { v: 1, name, pos, arch, age: 19 + (rnd() < 0.35 ? 1 : 0) + (rnd() < 0.15 ? 1 : 0), year: FIRST_YEAR,
           ovr: 0, pot: clamp(Math.round(gauss(85.5, 6)), 72, 99), dur: clamp(0.82 + gauss(0, 0.07), 0.6, 0.98),
           fame: 0, team: null, pick: 0, contract: null, seasons: [], awards: {}, earnings: { salary: 0, endorse: 0 },
           phase: "draft", pending: null, forcedRole: null, training: null, injured: 0, rushed: false, flags: {},
           teams: freshTeams(), offers: null, done: false, log: [] };
    st.offers = draftOffers();
    persist();
    if (window.gtag) gtag("event", "career_start", { pos, arch });
    render();
  }

  // Draft: uc teklif - en ust siralar (zayif takim, hemen ilk bes), lotarya ortasi, ilk turun sonu (sampiyonluk adayi)
  function draftOffers() {
    const order = byStrength(st);
    const tiers = [
      { picks: [1, 3], teams: order.slice(0, 5), role: "starter", ovr: [68, 72], note: "Rebuilding team - the ball is yours from day one." },
      { picks: [7, 14], teams: order.slice(6, 16), role: "rotation", ovr: [63, 67], note: "Middle of the pack - earn your minutes." },
      { picks: [20, 30], teams: order.slice(-8), role: "bench", ovr: [59, 63], note: "Contender - small role, real ring chances." },
    ];
    return tiers.map((t) => {
      const team = pick(t.teams);
      const p = t.picks[0] + Math.floor(rnd() * (t.picks[1] - t.picks[0] + 1));
      return { abbr: team.abbr, pick: p, role: t.role, ovr: t.ovr[0] + Math.floor(rnd() * (t.ovr[1] - t.ovr[0] + 1)), note: t.note, salary: rookieScale(p) };
    });
  }

  function teamBadge(abbr, big) {
    const t = T(st, abbr);
    return `<span class="cr-team ${big ? "big" : ""}" style="--tc:${t.color}"><img src="${t.logo}" alt="" onerror="this.style.visibility='hidden'"><b>${h(big ? t.name : t.abbr)}</b></span>`;
  }
  const tier = (s) => (s >= 6 ? "Title contender" : s >= 2 ? "Playoff team" : s >= -2 ? "Fringe playoff team" : s >= -6 ? "Lottery team" : "Rebuilding");

  function screenDraft() {
    app.innerHTML = `
      <section class="card cr-draft">
        <div class="eyebrow">${st.year - 1} NBA Draft</div>
        <h2 style="margin:4px 0 6px">Draft night, ${h(st.name)}</h2>
        <p class="small muted">Three teams want you. Your agent can steer you to one of them - where you land shapes your minutes, your growth and your ring chances.</p>
        <div class="cr-offers">${st.offers.map((o, i) => { const t = T(st, o.abbr); return `
          <button class="cr-offer" data-draft="${i}">
            <div class="cr-offer-top">${teamBadge(o.abbr, true)}<span class="cr-pick">#${o.pick}</span></div>
            <div class="cr-kv"><span>Role</span><b>${ROLES[o.role].label}</b></div>
            <div class="cr-kv"><span>Team</span><b>${tier(t.s)}</b></div>
            <div class="cr-kv"><span>Player development</span><b>${DEV[t.dev]}</b></div>
            <div class="cr-kv"><span>Rookie deal</span><b>${money(o.salary)} / yr · 4 yrs</b></div>
            <p class="small muted">${h(o.note)}</p>
          </button>`; }).join("")}</div>
      </section>`;
    app.onclick = (e) => {
      const b = e.target.closest("[data-draft]");
      if (!b) return;
      const o = st.offers[+b.dataset.draft];
      st.team = o.abbr; st.pick = o.pick; st.ovr = o.ovr; st.forcedRole = o.role;
      st.contract = { years: 4, salary: o.salary, rookie: true };
      st.fame = clamp(40 - o.pick * 1.2, 4, 40);
      st.draftedBy = o.abbr;
      st.log.unshift({ year: st.year - 1, text: `Drafted ${ord(o.pick)} overall by the ${T(st, o.abbr).name}.` });
      st.phase = "preseason"; st.offers = null; persist(); render();
    };
  }

  // ---------------- ana ekran ----------------
  function header() {
    const t = st.team ? T(st, st.team) : null;
    const c = st.contract;
    return `<section class="card cr-head" style="--tc:${t ? t.color : "#3987E5"}">
      <div class="cr-who"><div><div class="eyebrow">${st.pos} · ${ARCH[st.arch].label}</div><h2>${h(st.name)}</h2>
        <span class="small muted">Age ${st.age} · ${seasonLabel(st.year)} season${st.seasons.length ? ` · year ${st.seasons.length + 1}` : ""}</span></div>
        ${t ? teamBadge(st.team, true) : ""}</div>
      <div class="cr-meters">
        <div><span>Overall</span><b>${Math.round(st.ovr)}</b></div>
        <div><span>Fame</span><b>${Math.round(st.fame)}</b></div>
        <div><span>Contract</span><b>${c ? `${money(c.salary)}` : "-"}</b><small>${c ? `${c.years} yr${c.years === 1 ? "" : "s"} left` : ""}</small></div>
        <div><span>Earned</span><b>${money(st.earnings.salary + st.earnings.endorse)}</b></div>
      </div>
      ${trophies()}
    </section>`;
  }
  function trophies() {
    const a = st.awards, order = [["ring", "Champion"], ["mvp", "MVP"], ["fmvp", "Finals MVP"], ["dpoy", "DPOY"], ["allnba", "All-NBA"], ["as", "All-Star"], ["scoring", "Scoring title"], ["roy", "ROY"], ["smoy", "6MOY"], ["mip", "MIP"], ["gold", "Olympic gold"]];
    const chips = order.filter(([k]) => a[k]).map(([k, l]) => `<span class="cr-chip ${k}">${a[k] > 1 ? `${a[k]}x ` : ""}${l}</span>`);
    return chips.length ? `<div class="cr-trophies">${chips.join("")}</div>` : "";
  }
  function seasonRows() {
    if (!st.seasons.length) return "";
    return `<section class="card" style="margin-top:12px"><div class="card-title">Career</div>
      <div class="table-wrap"><table class="table small cr-table"><thead><tr><th class="l">Season</th><th class="l">Team</th><th>Age</th><th>OVR</th><th>GP</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th class="l">Team result</th><th class="l">Awards</th></tr></thead>
      <tbody>${st.seasons.slice().reverse().map((s) => `<tr><td class="l">${seasonLabel(s.year)}</td><td class="l">${h(s.team)}</td><td>${s.age}</td><td>${s.ovr}</td><td>${s.gp}</td>
        <td><b>${s.pts.toFixed(1)}</b></td><td>${s.reb.toFixed(1)}</td><td>${s.ast.toFixed(1)}</td><td>${s.stl.toFixed(1)}</td><td>${s.blk.toFixed(1)}</td>
        <td class="l small">${s.w}-${82 - s.w} · ${h(s.result)}</td><td class="l small">${s.awards.map(h).join(", ") || '<span class="dim">-</span>'}</td></tr>`).join("")}</tbody></table></div></section>`;
  }
  function logHtml() {
    return st.log.length ? `<section class="card" style="margin-top:12px"><div class="card-title">Timeline</div><div class="cr-log">${st.log.slice(0, 14).map((l) => `<div><span>${l.year}</span>${h(l.text)}</div>`).join("")}</div></section>` : "";
  }

  function decisionCard(d) {
    return `<section class="card cr-decision"><div class="eyebrow">${h(d.kicker || "Decision")}</div><h3>${h(d.title)}</h3>
      ${d.text ? `<p class="small muted">${d.text}</p>` : ""}
      <div class="cr-choices">${d.options.map((o, i) => `<button class="cr-choice" data-opt="${i}"><b>${h(o.label)}</b>${o.sub ? `<small>${o.sub}</small>` : ""}</button>`).join("")}</div></section>`;
  }

  function render() {
    if (!st) return screenCreate();
    if (st.phase === "draft") return screenDraft();
    if (st.phase === "end") return screenEnd();
    let main = "";
    if (st.pending) main = decisionCard(st.pending);
    else if (st.phase === "preseason") {
      const role = st.forcedRole || roleFor();
      main = `<section class="card cr-next"><div><div class="eyebrow">${seasonLabel(st.year)}</div><h3>Ready for the season</h3>
        <p class="small muted">${ROLES[role].label} for the ${h(T(st, st.team).name)} (${tier(T(st, st.team).s).toLowerCase()}).</p></div>
        <button class="btn btn-primary" id="cr-play">Play the ${seasonLabel(st.year)} season</button></section>`;
    }
    const last = st.lastSeason ? seasonCard(st.lastSeason) : "";
    app.innerHTML = header() + last + main + seasonRows() + logHtml() +
      `<div class="cr-foot"><button class="btn btn-sm btn-ghost" id="cr-quit">Start a new career</button></div>`;
  }

  function seasonCard(s) {
    return `<section class="card cr-season ${s.awards.length ? "has-awards" : ""}">
      <div class="cr-season-h"><div><div class="eyebrow">${seasonLabel(s.year)} · ${h(s.team)}</div><h3>${s.pts.toFixed(1)} PTS · ${s.reb.toFixed(1)} REB · ${s.ast.toFixed(1)} AST</h3>
        <span class="small muted">${s.gp} games · ${s.min.toFixed(1)} min · ${s.stl.toFixed(1)} STL · ${s.blk.toFixed(1)} BLK · ${s.tpm.toFixed(1)} 3PM · OVR ${s.ovr}${s.dOvr ? ` (${s.dOvr > 0 ? "+" : ""}${s.dOvr})` : ""}</span></div>
        <div class="cr-rec"><b>${s.w}-${82 - s.w}</b><span>${h(s.result)}</span></div></div>
      ${s.awards.length ? `<div class="cr-trophies">${s.awards.map((a) => `<span class="cr-chip new">${h(a)}</span>`).join("")}</div>` : ""}
      ${s.notes.length ? `<p class="small muted" style="margin:6px 0 0">${s.notes.map(h).join(" ")}</p>` : ""}
    </section>`;
  }

  // ================= SIMULASYON =================
  function roleFor() {
    const s = T(st, st.team).s;
    const bump = clamp(s, -6, 8) * 0.5;
    if (st.ovr >= 86 + bump) return "star";
    if (st.ovr >= 77 + bump) return "starter";
    if (st.ovr >= 69 + bump) return "rotation";
    return "bench";
  }

  function develop() {
    const age = st.age;
    const curve = age <= 21 ? 4.2 : age <= 23 ? 3.0 : age <= 25 ? 1.8 : age <= 27 ? 0.7 : age <= 29 ? -0.3 : age <= 31 ? -1.4 : age <= 33 ? -2.6 : age <= 35 ? -3.8 : -5;
    const role = st.forcedRole || roleFor();
    const minsBonus = { star: 0.6, starter: 0.5, rotation: 0.1, bench: -0.4 }[role];
    const devBonus = (T(st, st.team).dev - 1) * 0.6;
    const train = st.training === "skill" ? 1.2 : st.training === "strength" ? 0.4 : st.training === "brand" ? -0.6 : 0;
    let d = curve + (curve > 0 ? minsBonus + devBonus : 0) + train + gauss(0, 2.0);
    // Potansiyele yaklastikca yavaslar
    if (st.ovr + d > st.pot) d = Math.min(d, Math.max(0, (st.pot - st.ovr) * 0.6) + gauss(0, 0.6));
    if (st.flags.mentor && d < 0) d *= 0.75;
    const before = st.ovr;
    st.ovr = clamp(st.ovr + d, 40, 99);
    return Math.round(st.ovr) - Math.round(before);
  }

  function playSeason() {
    const dOvr = st.seasons.length ? develop() : 0;
    st.training = null;
    const team = T(st, st.team);
    const role = st.forcedRole || roleFor();
    st.forcedRole = null;
    const ovr = Math.round(st.ovr);
    // Sakatlik
    let missed = Math.round(Math.abs(gauss(0, 3)));       // dinlendirme, ufak tefek
    const inj = { text: null, major: false };
    const pInj = 0.11 + Math.max(0, st.age - 29) * 0.025 + (1 - st.dur) * 0.45 + (st.rushed ? 0.12 : 0) + (st.flags.olympics ? 0.04 : 0);
    st.rushed = false; st.flags.olympics = false;
    if (rnd() < pInj) {
      const r = rnd();
      if (r < 0.58) { const g = 4 + Math.floor(rnd() * 10); missed += g; inj.text = `${pick(["Ankle sprain", "Hamstring strain", "Knee soreness", "Back spasms", "Sprained wrist"])} cost you ${g} games.`; }
      else if (r < 0.88) { const g = 15 + Math.floor(rnd() * 18); inj.text = `${pick(["Broken hand", "High ankle sprain", "Calf strain", "Torn ligament in the thumb"])} - out about ${g} games.`; inj.games = g; inj.mid = true; }
      else { const g = 45 + Math.floor(rnd() * 37); inj.text = `${pick(["Torn ACL", "Ruptured Achilles", "Torn meniscus", "Fractured kneecap"])} - out ${g >= 82 ? "for the season" : `about ${g} games`}.`; inj.games = g; inj.major = true; }
    }
    // Ciddi sakatlikta karar (erken don / tam iyiles): sezon bu karardan sonra biter
    const ctx = { dOvr, role, ovr, missed, inj, team: team.abbr };
    if (inj.mid || inj.major) {
      st.pending = { kicker: `${seasonLabel(st.year)} · injury`, title: inj.text, text: "The medical staff gives you two options.", kind: "injury", ctx,
        options: [{ label: "Rush back", sub: `Miss ~${Math.round(inj.games * 0.55)} games. Higher re-injury risk next season${inj.major ? ", and it may cost you some burst" : ""}.`, v: "rush" },
                  { label: "Full recovery", sub: `Miss all ~${Math.min(82, inj.games)} games. Come back healthy.`, v: "full" }] };
      persist(); return render();
    }
    finishSeason(ctx);
  }

  function finishSeason(ctx) {
    const team = T(st, st.team);
    const { role, dOvr } = ctx;
    let ovr = ctx.ovr;
    const notes = [];
    const gp = clamp(82 - ctx.missed, 0, 82);
    if (ctx.inj.text) notes.push(ctx.inj.text);
    const a = ARCH[st.arch], p = POS[st.pos];
    const min = gp ? clamp(ROLES[role].min + gauss(0, 1.5) + (role === "bench" ? (ovr - 62) * 0.3 : 0), 8, 39) : 0;
    const m36 = min / 36, k = 0.55 + (ovr - 60) * 0.017;
    const n = (x) => Math.max(0, x * (1 + gauss(0, 0.06)));
    const line = gp ? {
      pts: n((7 + (ovr - 60) * 0.62) * a.pts * m36 * (role === "star" ? 1.06 : 1)), reb: n(p.reb * a.reb * k * m36), ast: n(p.ast * a.ast * k * m36),
      stl: n(p.stl * a.stl * k * m36), blk: n(p.blk * a.blk * k * m36), tpm: n(p.tpm * a.tpm * k * m36),
    } : { pts: 0, reb: 0, ast: 0, stl: 0, blk: 0, tpm: 0 };
    // Takim: guc + senin etkin (dakika ve oynadigin mac kadar)
    const impact = (ovr - 72) * 0.26 * (min / 34) * (gp / 82);
    const net = team.s + impact;
    const w = clamp(Math.round(41 + 2.7 * net + gauss(0, 3.5)), 12, 70);
    const po = playoffs(w, net, gp);
    const awards = [], add = (k, label) => { st.awards[k] = (st.awards[k] || 0) + 1; awards.push(label); };
    const rookie = st.seasons.length === 0;
    const ok = gp >= 58;
    // Oduller
    if (rookie && gp >= 50 && rnd() < sig((line.pts + line.reb * 0.5 + line.ast * 0.7 - 15) / 2)) { add("roy", "Rookie of the Year"); st.fame += 8; }
    if (!rookie && dOvr >= 5 && ok && rnd() < 0.45) add("mip", "Most Improved Player");
    if ((role === "bench" || role === "rotation") && line.pts >= 12 && ok && rnd() < sig((line.pts - 15) / 1.8)) { add("smoy", "Sixth Man of the Year"); st.fame += 4; }
    const allStar = gp >= 40 && rnd() < sig((ovr - 86) / 1.5 + (st.fame - 50) / 70 + (w - 41) / 45);
    if (allStar) { add("as", "All-Star"); st.fame += 5; }
    const allNba = ok && rnd() < sig((ovr - 89.5) / 1.3 + (w - 41) / 45);
    if (allNba) { const tm = ovr >= 94 ? "1st" : ovr >= 91.5 ? pick(["1st", "2nd"]) : pick(["2nd", "3rd", "3rd"]); add("allnba", `All-NBA ${tm} Team`); st.fame += 6; }
    if (ok && gp >= 65 && ovr >= 91 && w >= 48 && rnd() < sig((ovr - 94) / 1.2 + (w - 55) / 7)) { add("mvp", "MVP"); st.fame += 14; }
    const defScore = ovr * a.def + line.blk * 3 + line.stl * 3;
    if (gp >= 65 && ovr >= 84 && rnd() < sig((defScore - 133) / 2.5)) { add("dpoy", "Defensive Player of the Year"); st.fame += 5; }
    if (line.pts >= 28.5 && ok && rnd() < sig((line.pts - 31) / 1.2)) { add("scoring", "Scoring title"); st.fame += 4; }
    if (po.champ && gp > 0) {
      add("ring", "NBA Champion"); st.fame += 9;
      if ((role === "star" && rnd() < 0.8) || (role === "starter" && ovr >= 84 && rnd() < 0.3)) { add("fmvp", "Finals MVP"); st.fame += 10; }
    }
    // Un ve sponsorluk
    // Un tavani oyuncunun seviyesine bagli: yedek oyuncu marka kurarak superstar olamaz
    const fameCap = clamp(28 + Math.max(0, ovr - 70) * 3, 28, 100);
    st.fame = clamp(Math.min(fameCap, st.fame * 0.9 + Math.max(0, line.pts - 8) * 0.55 + (po.round >= 3 ? 3 : 0)), 0, 100);
    const salary = st.contract ? st.contract.salary : 0;
    const endorse = endorsements(st.fame) * (st.flags.shoe ? 1.6 : 1);
    st.earnings.salary += salary; st.earnings.endorse += endorse;
    const s = { year: st.year, team: team.abbr, age: st.age, ovr: Math.round(st.ovr), dOvr, role, gp, min, ...line,
                w, result: po.label, awards, notes, salary, endorse };
    st.seasons.push(s);
    st.lastSeason = s;
    if (awards.length) st.log.unshift({ year: st.year, text: awards.join(", ") + "." });
    if (po.champ) st.log.unshift({ year: st.year, text: `Won the title with the ${team.name}.` });
    // Takimlar degisir (ortalamaya donus + rastgele); senin takimin senin seviyene gore biraz kayar
    Object.values(st.teams).forEach((t) => { t.s = clamp(t.s * 0.72 + gauss(0, 3.3), -12, 12); });
    // Kontrat yili
    if (st.contract) st.contract.years -= 1;
    st.age += 1; st.year += 1;
    if (window.gtag && rookie) gtag("event", "career_rookie_done", {});
    offseason();
  }

  function playoffs(w, net, gp) {
    let made = w >= 45 || (w >= 41 && rnd() < 0.7) || (w >= 38 && rnd() < 0.3);
    if (!made) return { label: "Missed playoffs", round: 0, champ: false };
    const opp = [1.5, 4.0, 6.0, 8.0], names = ["Lost in the first round", "Lost in the conference semis", "Lost in the conference finals", "Lost in the NBA Finals"];
    const power = net - (gp < 60 ? 2 : 0);
    for (let r = 0; r < 4; r++) {
      if (rnd() > sig((power - opp[r] + (w - 50) / 10) / 3.2)) return { label: names[r], round: r, champ: false };
    }
    return { label: "Won the NBA title", round: 4, champ: true };
  }

  // ================= YAZ =================
  // Sira: emeklilik (33+), kontrat/serbest oyuncu, bir olay, antrenman. Her biri bir karar karti.
  function offseason() {
    st.queue = [];
    const ovr = st.ovr;
    // Imzalanmis uzatma: rookie kontrati bitince devreye girer (serbest oyuncu olmaz)
    if (st.contract && st.contract.years <= 0 && st.contract.next) st.contract = { ...st.contract.next };
    if (st.age >= 41 || (ovr < 58 && st.age >= 31)) { return retire(st.age >= 41 ? "Father time is undefeated." : "No team made you an offer."); }
    if (st.age >= 33) st.queue.push("retire");
    const c = st.contract;
    if (c && c.rookie && c.years === 1 && ovr >= 74 && !st.flags.extDone) st.queue.push("extension");
    if (!c || c.years <= 0) st.queue.push("fa");
    const events = [];
    const team = T(st, st.team);
    const lastTwo = st.seasons.slice(-2);
    if (lastTwo.length === 2 && lastTwo.every((s) => s.w < 35) && ovr >= 84 && c && c.years > 0) events.push("trade");
    if (roleFor() === "starter" && team.s >= 3 && ovr < 84 && rnd() < 0.5) events.push("sixth");
    if (st.year % 4 === 0 && ovr >= 84) events.push("olympics");
    if (st.fame >= 35 && !st.flags.shoe && rnd() < 0.5) events.push("shoe");
    if (st.age >= 30 && !st.flags.mentor && rnd() < 0.4) events.push("mentor");
    if (rnd() < 0.3) events.push("viral");
    if (events.length) st.queue.push(pick(events));
    st.queue.push("training");
    st.lastSeasonSeen = false;
    nextDecision();
  }

  function nextDecision() {
    const k = st.queue.shift();
    if (!k) { st.pending = null; st.phase = "preseason"; persist(); return render(); }
    const ev = EVENTS[k]();
    if (!ev) return nextDecision();
    st.pending = { ...ev, kind: k };
    persist(); render();
  }

  // Serbest oyuncu teklifleri
  function faOffers() {
    const yi = st.year - FIRST_YEAR, ovr = st.ovr, mv = marketValue(ovr, yi);
    const order = byStrength(st);
    const cur = T(st, st.team);
    const contender = pick(order.slice(-6).filter((t) => t.abbr !== st.team)) || order[order.length - 1];
    const rebuild = pick(order.slice(0, 8).filter((t) => t.abbr !== st.team)) || order[0];
    const mid = pick(order.slice(8, 22).filter((t) => t.abbr !== st.team)) || order[10];
    const old = st.age >= 32;
    const yrs = (n) => Math.max(1, Math.min(n, old ? 2 : n));
    if (ovr < 62) {
      return [{ abbr: pick([contender, mid]).abbr, salary: Math.max(1.2, mv), years: 1, tag: "Minimum deal" },
              { abbr: st.team, salary: Math.max(1.2, mv * 0.95), years: 1, tag: "Stay put" }];
    }
    return [
      { abbr: st.team, salary: mv * 0.97, years: yrs(4), tag: `Re-sign with ${cur.abbr}` },
      { abbr: contender.abbr, salary: mv * 0.72, years: yrs(2), tag: "Chase a ring" },
      { abbr: rebuild.abbr, salary: mv * 1.12, years: yrs(5), tag: "Biggest payday" },
      ...(rnd() < 0.6 ? [{ abbr: mid.abbr, salary: mv * 0.92, years: yrs(3), tag: "Bigger role" }] : []),
    ];
  }

  const EVENTS = {
    retire: () => ({ kicker: `Summer ${st.year - 1}`, title: `You're ${st.age}. Keep going?`, text: `Overall ${Math.round(st.ovr)}. Your body feels it, but there's a market for you.`,
      options: [{ label: "Keep playing", sub: "Chase more numbers - or one more ring.", v: "go" }, { label: "Retire", sub: "Walk away on your own terms.", v: "retire" }] }),
    extension: () => { const v = marketValue(st.ovr + 2, st.year - FIRST_YEAR) * 0.92; st.tmp = { ext: v };
      return { kicker: `Summer ${st.year - 1}`, title: `${T(st, st.team).name} offer a rookie extension`, text: `5 years, ${money(v)} a year (${money(v * 5)} total), starting next season.`,
        options: [{ label: "Sign it", sub: "Security now.", v: "sign" }, { label: "Bet on yourself", sub: "Play out the rookie deal and hit free agency next summer.", v: "bet" }] }; },
    fa: () => { const offers = faOffers(); st.tmp = { offers };
      return { kicker: `Free agency ${st.year - 1}`, title: "Your agent's phone is ringing", text: `You're ${st.age} with an overall of ${Math.round(st.ovr)}. Pick your next deal.`,
        options: offers.map((o) => ({ label: `${T(st, o.abbr).name} · ${money(o.salary)}/yr`, sub: `${o.tag} · ${o.years} yr${o.years > 1 ? "s" : ""} · ${tier(T(st, o.abbr).s)} · development ${DEV[T(st, o.abbr).dev]}`, v: o })) }; },
    trade: () => ({ kicker: `Summer ${st.year - 1}`, title: "Two losing seasons in a row", text: "You're a star on a team going nowhere. The front office asks what you want.",
      options: [{ label: "Request a trade", sub: "Get moved to a winner. Some fans will burn your jersey.", v: "trade" }, { label: "Stay loyal", sub: "Ride it out. The city will love you for it.", v: "stay" }] }),
    sixth: () => ({ kicker: `Training camp ${st.year - 1}`, title: "Coach wants you to lead the second unit", text: "You'd come off the bench - fewer minutes, more shots when you're out there.",
      options: [{ label: "Accept the 6th man role", sub: "Sixth Man of the Year is on the table. The team gets deeper.", v: "yes" }, { label: "I'm a starter", sub: "Keep your spot. The locker room gets a little tense.", v: "no" }] }),
    olympics: () => ({ kicker: `Summer ${st.year - 1}`, title: "Team USA calls", text: "An Olympic roster spot is yours if you want it.",
      options: [{ label: "Play in the Olympics", sub: "Gold medal shot and fame - a long summer on your legs.", v: "go" }, { label: "Rest this summer", sub: "Stay fresh for the season.", v: "rest" }] }),
    shoe: () => ({ kicker: `Summer ${st.year - 1}`, title: "A signature shoe offer", text: "A brand wants to build a line around you.",
      options: [{ label: "Sign the shoe deal", sub: "Endorsement money jumps. Expect a busy summer.", v: "sign" }, { label: "Not yet", sub: "Stay focused on basketball - a bit more growth this summer.", v: "no" }] }),
    mentor: () => ({ kicker: `Summer ${st.year - 1}`, title: "The front office asks you to mentor the rookies", text: "A veteran voice in the locker room.",
      options: [{ label: "Take them under your wing", sub: "The team improves and you age a little more gracefully.", v: "yes" }, { label: "Focus on my own game", sub: "Every rep counts at this age.", v: "no" }] }),
    viral: () => ({ kicker: `Summer ${st.year - 1}`, title: "Your summer workout video goes viral", text: "Millions of views overnight.",
      options: [{ label: "Lean into it", sub: "Podcasts, appearances, brand deals. Fame up.", v: "fame" }, { label: "Back to the gym", sub: "Quiet summer, a little more growth.", v: "gym" }] }),
    training: () => ({ kicker: `Summer ${st.year - 1}`, title: "How do you spend the summer?", text: `Overall ${Math.round(st.ovr)} · age ${st.age}.`,
      options: [{ label: "Skill work", sub: "Shooting, handles, footwork - the biggest jump in your game.", v: "skill" },
                { label: "Strength and conditioning", sub: "Fewer injuries from now on, steady growth.", v: "strength" },
                { label: "Build your brand", sub: "Fame and endorsement money, slower growth.", v: "brand" }] }),
  };

  function choose(i) {
    const d = st.pending, o = d.options[i], v = o.v;
    switch (d.kind) {
      case "injury": {
        const ctx = d.ctx;
        if (v === "rush") { ctx.missed += Math.round(ctx.inj.games * 0.55); st.rushed = true; st.dur = clamp(st.dur - 0.03, 0.5, 0.99); if (ctx.inj.major) st.ovr -= 2; ctx.inj.text += " You rushed back."; }
        else { ctx.missed += Math.min(82, ctx.inj.games); if (ctx.inj.major) { st.ovr -= 1; st.pot = Math.max(st.ovr, st.pot - 2); } ctx.inj.text += " You took the full recovery."; }
        st.pending = null;
        st.log.unshift({ year: st.year, text: ctx.inj.text });
        return finishSeason(ctx);
      }
      case "retire": if (v === "retire") return retire("You chose to walk away."); break;
      case "extension":
        st.flags.extDone = true;
        if (v === "sign") { st.contract.next = { years: 5, salary: st.tmp.ext }; st.log.unshift({ year: st.year - 1, text: `Signed a 5-year, ${money(st.tmp.ext * 5)} extension.` }); }
        else st.log.unshift({ year: st.year - 1, text: "Turned down the extension to bet on yourself." });
        break;
      case "fa": {
        const off = v;
        const moved = off.abbr !== st.team;
        st.team = off.abbr; st.contract = { years: off.years, salary: off.salary };
        st.log.unshift({ year: st.year - 1, text: `${moved ? "Signed with" : "Re-signed with"} the ${T(st, off.abbr).name}: ${off.years} yr${off.years > 1 ? "s" : ""}, ${money(off.salary * off.years)}.` });
        break;
      }
      case "trade":
        if (v === "trade") {
          const dest = pick(byStrength(st).slice(-8).filter((t) => t.abbr !== st.team));
          st.log.unshift({ year: st.year - 1, text: `Requested a trade - dealt to the ${dest.name}.` });
          st.team = dest.abbr; st.fame = clamp(st.fame - 3, 0, 100);
        } else { st.fame = clamp(st.fame + 4, 0, 100); T(st, st.team).s += 1.5; st.log.unshift({ year: st.year - 1, text: "Stayed loyal through the losing." }); }
        break;
      case "sixth":
        if (v === "yes") { st.forcedRole = "rotation"; T(st, st.team).s += 1; st.log.unshift({ year: st.year - 1, text: "Accepted the sixth man role." }); }
        else T(st, st.team).s -= 0.8;
        break;
      case "olympics":
        if (v === "go") {
          st.flags.olympics = true; st.fame = clamp(st.fame + 5, 0, 100);
          if (rnd() < 0.6) { st.awards.gold = (st.awards.gold || 0) + 1; st.log.unshift({ year: st.year - 1, text: "Won Olympic gold with Team USA." }); }
          else st.log.unshift({ year: st.year - 1, text: "Played for Team USA - came home without gold." });
        } else st.dur = clamp(st.dur + 0.01, 0.5, 0.99);
        break;
      case "shoe":
        if (v === "sign") { st.flags.shoe = true; st.fame = clamp(st.fame + 4, 0, 100); st.log.unshift({ year: st.year - 1, text: "Launched a signature shoe." }); }
        else st.ovr = clamp(st.ovr + 0.7, 40, 99);
        break;
      case "mentor":
        if (v === "yes") { st.flags.mentor = true; T(st, st.team).s += 0.8; st.fame = clamp(st.fame + 2, 0, 100); }
        break;
      case "viral":
        if (v === "fame") st.fame = clamp(st.fame + 7, 0, 100); else st.ovr = clamp(st.ovr + 0.8, 40, 99);
        break;
      case "training":
        st.training = v;
        if (v === "strength") st.dur = clamp(st.dur + 0.04, 0.5, 0.99);
        if (v === "brand") st.fame = clamp(st.fame + 6, 0, 100);
        break;
    }
    nextDecision();
  }

  // ================= KARIYER SONU =================
  function totals() {
    const S = st.seasons, gp = S.reduce((a, s) => a + s.gp, 0) || 1;
    const sum = (k) => S.reduce((a, s) => a + s[k] * s.gp, 0);
    return { seasons: S.length, gp, pts: sum("pts"), reb: sum("reb"), ast: sum("ast"), stl: sum("stl"), blk: sum("blk"),
             ppg: sum("pts") / gp, rpg: sum("reb") / gp, apg: sum("ast") / gp, teams: [...new Set(S.map((s) => s.team))] };
  }
  function hof(t) {
    const a = st.awards;
    const score = 15 * (a.mvp || 0) + 8 * (a.fmvp || 0) + 6 * (a.ring || 0) + 5 * (a.allnba || 0) + 3 * (a.as || 0) + 4 * (a.dpoy || 0)
      + 2 * (a.roy || 0) + 2 * (a.scoring || 0) + 2 * (a.gold || 0) + t.pts / 2000;
    return { score, p: Math.round(100 * sig((score - 36) / 6.5)) };
  }
  function scoringPlace(pts) {
    return pts >= 40000 ? "the most points in NBA history" : pts >= 36000 ? "a top-3 all-time scoring total" : pts >= 31000 ? "a top-10 all-time scoring total"
      : pts >= 26000 ? "a top-25 all-time scoring total" : pts >= 20000 ? "a top-60 all-time scoring total" : pts >= 12000 ? "a long, productive career" : "a career many dream of";
  }
  function headline(t) {
    const a = st.awards;
    if ((a.mvp || 0) >= 3 || ((a.ring || 0) >= 4 && (a.fmvp || 0) >= 2)) return "All-time great";
    if (a.mvp || ((a.ring || 0) >= 2 && (a.as || 0) >= 6)) return "Hall of Famer";
    if ((a.as || 0) >= 5) return "Perennial All-Star";
    if (a.as || a.ring) return "Fan favorite";
    if (t.seasons >= 12) return "Journeyman pro";
    return "Role player";
  }
  function retire(why) {
    st.phase = "end"; st.retiredWhy = why; st.pending = null;
    const t = totals(), H = hof(t);
    st.log.unshift({ year: st.year - 1, text: `Retired at ${st.age}. ${why}` });
    const best = load(BEST, []);
    const a = st.awards;
    const parts = [`${t.ppg.toFixed(1)} PPG`];
    if (a.ring) parts.push(`${a.ring}x champ`); if (a.mvp) parts.push(`${a.mvp}x MVP`); if (a.as) parts.push(`${a.as}x All-Star`);
    best.push({ name: st.name, pos: st.pos, seasons: t.seasons, score: H.score, line: `${parts.join(" · ")} · HOF ${H.p}%` });
    best.sort((x, y) => y.score - x.score);
    save(BEST, best.slice(0, 5));
    if (window.gtag) gtag("event", "career_end", { seasons: t.seasons, hof: H.p });
    persist(); render();
  }

  function screenEnd() {
    const t = totals(), H = hof(t), a = st.awards;
    const earned = st.earnings.salary + st.earnings.endorse;
    const big = [["ring", "Championships"], ["mvp", "MVPs"], ["fmvp", "Finals MVPs"], ["as", "All-Star selections"], ["allnba", "All-NBA teams"], ["dpoy", "DPOYs"], ["scoring", "Scoring titles"], ["roy", "Rookie of the Year"], ["smoy", "Sixth Man awards"], ["mip", "Most Improved"], ["gold", "Olympic golds"]].filter(([k]) => a[k]);
    app.innerHTML = `
      <section class="card cr-end">
        <div class="eyebrow">Career over · ${h(st.retiredWhy || "")}</div>
        <h2>${h(st.name)}</h2>
        <div class="cr-headline">${headline(t)}</div>
        <p class="small muted">${st.pos} · ${ARCH[st.arch].label} · ${ord(st.pick)} pick by ${h(T(st, st.draftedBy).name)} · ${t.seasons} seasons, ${t.teams.length} team${t.teams.length > 1 ? "s" : ""} (${t.teams.join(", ")})</p>
        <div class="cr-meters">
          <div><span>Points</span><b>${Math.round(t.pts).toLocaleString("en-US")}</b><small>${t.ppg.toFixed(1)} per game</small></div>
          <div><span>Rebounds</span><b>${Math.round(t.reb).toLocaleString("en-US")}</b><small>${t.rpg.toFixed(1)} per game</small></div>
          <div><span>Assists</span><b>${Math.round(t.ast).toLocaleString("en-US")}</b><small>${t.apg.toFixed(1)} per game</small></div>
          <div><span>Games</span><b>${t.gp.toLocaleString("en-US")}</b><small>${t.seasons} seasons</small></div>
        </div>
        <div class="cr-awards">${big.length ? big.map(([k, l]) => `<div><b>${a[k]}</b><span>${l}</span></div>`).join("") : '<p class="muted small">No major awards - but you made it to the league.</p>'}</div>
        <div class="cr-money">
          <div><span>Career earnings</span><b>${money(earned)}</b><small>${money(st.earnings.salary)} salary · ${money(st.earnings.endorse)} endorsements</small></div>
          <div><span>Hall of Fame chance</span><b class="${H.p >= 70 ? "good" : H.p >= 30 ? "warn" : ""}">${H.p}%</b><small>${Math.round(t.pts).toLocaleString("en-US")} points: ${scoringPlace(t.pts)}</small></div>
        </div>
        <div class="gr-actions"><button class="btn btn-primary" id="cr-share">Share my career</button><button class="btn" id="cr-new">New career</button></div>
      </section>` + seasonRows() + logHtml();
    app.onclick = async (e) => {
      if (e.target.closest("#cr-new")) { st = null; save(KEY, null); return render(); }
      if (e.target.closest("#cr-share")) return share(t, H, earned);
    };
  }

  async function share(t, H, earned) {
    const a = st.awards;
    const bits = [`${t.seasons} seasons`, `${t.ppg.toFixed(1)} PPG`];
    if (a.ring) bits.push(`${a.ring}x champion`); if (a.mvp) bits.push(`${a.mvp}x MVP`); if (a.fmvp) bits.push(`${a.fmvp}x Finals MVP`);
    if (a.as) bits.push(`${a.as}x All-Star`); if (a.dpoy) bits.push(`${a.dpoy}x DPOY`);
    const text = `My NBA career: ${st.name}, ${ord(st.pick)} pick by ${T(st, st.draftedBy).abbr}. ${bits.join(", ")}. ${money(earned)} earned, Hall of Fame chance ${H.p}%. Build yours: ${location.origin}/career?ref=career-share${window.HL.inv()}`;
    if (window.gtag) gtag("event", "career_share", { hof: H.p });
    const btn = $("#cr-share"); if (btn) btn.classList.add("is-loading");
    try {
      const K = window.HLCard;
      const { cv, g } = await K.base("NBA CAREER", "");
      K.text(g, st.name.toUpperCase(), K.W / 2, 300, { weight: 900, size: st.name.length > 16 ? 70 : 92, align: "center" });
      K.pill(g, headline(t).toUpperCase(), K.W / 2, 362, { bg: H.p >= 70 ? K.C.gold : "rgba(255,255,255,.12)", color: H.p >= 70 ? "#1B1300" : "#fff", size: 30, h: 56, padX: 26 });
      K.text(g, `${st.pos} · ${ARCH[st.arch].label.toUpperCase()} · ${ord(st.pick).toUpperCase()} PICK · ${t.seasons} SEASONS`, K.W / 2, 432, { weight: 800, size: 26, color: K.C.muted, align: "center" });
      const stats = [[t.ppg.toFixed(1), "PPG"], [t.rpg.toFixed(1), "RPG"], [t.apg.toFixed(1), "APG"]];
      stats.forEach(([v, l], i) => {
        const x = K.W / 2 + (i - 1) * 300;
        K.text(g, v, x, 560, { weight: 900, size: 96, align: "center" });
        K.text(g, l, x, 606, { weight: 800, size: 28, color: K.C.muted, align: "center" });
      });
      const rows = [["ring", "CHAMPIONSHIPS"], ["mvp", "MVP"], ["fmvp", "FINALS MVP"], ["as", "ALL-STAR"], ["allnba", "ALL-NBA"], ["dpoy", "DPOY"], ["roy", "ROOKIE OF THE YEAR"], ["scoring", "SCORING TITLES"]].filter(([k]) => a[k]).slice(0, 6);
      rows.forEach(([k, l], i) => {
        const col = i % 2, row = Math.floor(i / 2), x = 140 + col * 420, y = 700 + row * 96;
        K.rr(g, x, y, 380, 76, 18); g.fillStyle = "rgba(255,255,255,.07)"; g.fill();
        K.text(g, `${a[k]}x`, x + 28, y + 52, { weight: 900, size: 40, color: k === "ring" || k === "mvp" ? K.C.gold : "#fff" });
        K.text(g, l, x + 120, y + 49, { weight: 800, size: 24 });
      });
      const y2 = 700 + Math.max(1, Math.ceil(rows.length / 2)) * 96 + 40;
      K.text(g, money(earned), K.W / 2 - 220, y2 + 60, { weight: 900, size: 64, align: "center", color: K.C.gold });
      K.text(g, "CAREER EARNINGS", K.W / 2 - 220, y2 + 100, { weight: 800, size: 24, color: K.C.muted, align: "center" });
      K.text(g, `${H.p}%`, K.W / 2 + 220, y2 + 60, { weight: 900, size: 64, align: "center" });
      K.text(g, "HALL OF FAME CHANCE", K.W / 2 + 220, y2 + 100, { weight: 800, size: 24, color: K.C.muted, align: "center" });
      K.footer(g, "/career", "Build your own career");
      await K.share(cv, { filename: "my-nba-career.png", text, title: "My NBA career" });
    } catch (err) {
      try { await navigator.clipboard.writeText(text); toast("Career copied."); } catch (e2) { window.prompt("Copy:", text); }
    } finally { if (btn) btn.classList.remove("is-loading"); }
  }

  // ---------------- tiklamalar ----------------
  app.addEventListener("click", (e) => {
    if (!st || st.phase === "draft" || st.phase === "end") return;     // kendi isleyicileri var
    const o = e.target.closest("[data-opt]");
    if (o && st.pending) return choose(+o.dataset.opt);
    if (e.target.closest("#cr-play")) { st.lastSeason = null; return playSeason(); }
    if (e.target.closest("#cr-quit") && confirm("Abandon this career and start a new one?")) { st = null; save(KEY, null); render(); }
  });
  // Ekranlar kendi app.onclick'ini kurar; ana ekran icin bosalt
  const baseRender = render;
  render = function () { app.onclick = null; baseRender(); };      // eslint-disable-line no-func-assign
  render();
})();
