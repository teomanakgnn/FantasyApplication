// Mac simulasyonu: "en tipik mac" 2D oyun gibi oynatilir. Sahada 10 oyuncu
// (takim renginde, forma numarali, isimli); her olay bir hucum: dizilis, pas,
// sut yerine kosu, sut, blok, top calma, serbest atis. Olaylar tipik macin
// kutu skorundan uretilir (gercek play-by-play degil); son skor kutu skorla
// ayni. Tohum mac kimliginden: herkes ayni maci izler.
(function () {
  const root = document.getElementById("sim-anim");
  if (!root) return;
  const D = JSON.parse(document.getElementById("sim-anim-data").textContent);
  const $ = (s) => root.querySelector(s);
  const NS = "http://www.w3.org/2000/svg";
  const GAME = 2880;
  const SIDES = ["away", "home"];
  const HOOP = { away: [5.25, 25], home: [88.75, 25] };        // away sola, home saga hucum eder
  const DIR = { away: 1, home: -1 };
  const other = (s) => (s === "away" ? "home" : "away");
  const last = (name) => name.split(" ").filter((w) => !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(w)).slice(-1)[0] || name;

  // ---------------- tohumlu rastgele ----------------
  let seed = 7;
  for (const ch of String(D.game)) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
  const rnd = () => { seed = (seed + 0x6D2B79F5) >>> 0; let t = seed; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const pick = (arr) => arr[Math.floor(rnd() * arr.length)];
  const shuffle = (a) => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };

  // ---------------- olaylar (kutu skordan) ----------------
  const events = [];
  SIDES.forEach((side) => {
    const team = D[side], opp = D[other(side)];
    team.forEach((p) => { p.side = side; });
    opp.forEach((p) => { p.side = other(side); });
    const astPool = shuffle(team.flatMap((p) => Array(p.ast).fill(p)));
    const blkPool = shuffle(opp.flatMap((p) => Array(p.blk).fill(p)));
    team.forEach((p) => {
      const shots = [];
      for (let i = 0; i < p.tpm; i++) shots.push({ kind: 3, made: true });
      for (let i = 0; i < p.tpa - p.tpm; i++) shots.push({ kind: 3, made: false });
      for (let i = 0; i < p.fgm - p.tpm; i++) shots.push({ kind: 2, made: true });
      for (let i = 0; i < (p.fga - p.tpa) - (p.fgm - p.tpm); i++) shots.push({ kind: 2, made: false });
      shots.forEach((s) => events.push({ t: Math.floor(rnd() * GAME), side, p, ...s }));
      let fta = p.fta;
      const trips = [];
      while (fta > 0) {
        const n = Math.min(fta, fta === 3 ? 3 : 2);
        const trip = { t: Math.floor(rnd() * GAME), side, p, kind: 1, shots: Array(n).fill(false) };
        trips.push(trip); events.push(trip);
        fta -= n;
      }
      // isabetli serbest atislari seyahatlere dagit (toplam kutu skorla ayni)
      shuffle(trips.flatMap((tr) => tr.shots.map((_, i) => [tr, i]))).slice(0, p.ftm).forEach(([tr, i]) => { tr.shots[i] = true; });
      for (let i = 0; i < p.stl; i++) events.push({ t: Math.floor(rnd() * GAME), side, p, kind: "stl" });
    });
    events.filter((e) => e.side === side && e.made && e.kind > 1).forEach((e) => {
      const i = astPool.findIndex((a) => a !== e.p);
      if (i >= 0 && rnd() < 0.85) e.ast = astPool.splice(i, 1)[0];
    });
    events.filter((e) => e.side === side && e.made === false && e.kind > 1).forEach((e) => {
      if (blkPool.length && rnd() < 0.18) e.blk = blkPool.pop();
    });
  });
  events.forEach((e, i) => { e.t += i * 0.001; });
  events.sort((a, b) => a.t - b.t);

  // ---------------- saha cizimi ----------------
  const svg = $(".sa-court");
  const el = (tag, attrs, parent = svg) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); parent.appendChild(n); return n; };
  const lines = el("g", { class: "sa-lines", fill: "none" });
  el("rect", { x: 0.5, y: 0.5, width: 93, height: 49 }, lines);
  el("line", { x1: 47, y1: 0.5, x2: 47, y2: 49.5 }, lines);
  el("circle", { cx: 47, cy: 25, r: 6 }, lines);
  const rims = {};
  SIDES.forEach((side) => {
    const [hx] = HOOP[side], dir = DIR[side], base = dir === 1 ? 0.5 : 93.5;
    el("rect", { x: dir === 1 ? base : base - 19, y: 17, width: 19, height: 16 }, lines);
    el("circle", { cx: base + dir * 19, cy: 25, r: 6 }, lines);
    el("path", { d: `M${base} 3 L${base + dir * 14} 3 A23.75 23.75 0 0 ${dir === 1 ? 1 : 0} ${base + dir * 14} 47 L${base} 47` }, lines);
    el("line", { x1: base + dir * 4, y1: 22, x2: base + dir * 4, y2: 28 }, lines);
    rims[side] = el("circle", { cx: hx, cy: 25, r: 0.9, class: "sa-rim" });
  });
  const actors = el("g", {});
  const ballShadow = el("ellipse", { rx: 0.7, ry: 0.35, class: "sa-ball-shadow" });
  const ballEl = el("circle", { r: 0.75, class: "sa-ball" });
  const fx = el("g", {});

  // ---------------- oyuncular ----------------
  const P = new Map();                              // oyuncu -> {g, x, y, tx, ty}
  SIDES.forEach((side) => D[side].forEach((p) => {
    const [c1, c2] = D.colors[side];
    const g = el("g", { class: "sa-p" }, actors);
    el("circle", { r: 1.55, fill: c1, stroke: c2, "stroke-width": 0.3 }, g);
    const num = el("text", { y: 0.55, class: "sa-num", fill: c2 }, g);
    num.textContent = p.jersey || last(p.name).slice(0, 2).toUpperCase();
    const lab = el("text", { y: 3.5, class: "sa-name" }, g);
    lab.textContent = last(p.name);
    P.set(p, { g, x: 47, y: 25, tx: 47, ty: 25, p });
  }));
  const court = { away: [], home: [] };
  const starters = (s) => [...D[s]].sort((a, b) => b.min - a.min).slice(0, 5);
  const onCourt = (p) => court[p.side].includes(p);
  function ensure(p, keep = []) {                    // sahada degilse en az suren takim arkadasiyla degisir
    if (!p || onCourt(p)) return;
    const out = court[p.side].filter((q) => !keep.includes(q)).sort((a, b) => a.min - b.min)[0];
    court[p.side][court[p.side].indexOf(out)] = p;
    const so = P.get(out), sp = P.get(p);
    sp.x = sp.tx = 47; sp.y = sp.ty = p.side === "away" ? 49 : 1;   // kenardan girer
    so.tx = 47 + (rnd() - 0.5) * 20; so.ty = p.side === "away" ? 53 : -3;   // kenara cikar
  }
  const rank = (p) => (/C/.test(p.pos || "") ? 2 : /F/.test(p.pos || "") ? 1 : 0);
  const SLOTS = [[24, 0], [22, 50], [22, -50], [20, 84], [6, -55]];   // tepe, kanatlar, kose, post
  const at = (side, dist, deg) => {
    const [hx, hy] = HOOP[side], a = (deg * Math.PI) / 180;
    return [hx + DIR[side] * Math.cos(a) * dist, hy + Math.sin(a) * dist];
  };
  const marks = new Map();                           // savunmaci -> tuttugu hucumcu
  function formation(side) {                         // hucum dizilisi + adam adama savunma
    const off = [...court[side]].sort((a, b) => rank(a) - rank(b));
    const def = [...court[other(side)]].sort((a, b) => rank(a) - rank(b));
    const [hx, hy] = HOOP[side];
    off.forEach((p, i) => {
      const [x, y] = at(side, SLOTS[i][0] + (rnd() - 0.5) * 3, SLOTS[i][1] + (rnd() - 0.5) * 14);
      const s = P.get(p); s.tx = x; s.ty = y;
      // savunmaci: adami ile pota arasinda, isimler cakismasin diye hafif yanda
      const d = P.get(def[i]); d.tx = hx + (x - hx) * 0.8; d.ty = hy + (y - hy) * 0.8 + (y >= hy ? -1.6 : 1.6);
      marks.set(def[i], p);
    });
  }
  function shotSpot(side, kind) {
    if (kind === 3 && rnd() < 0.25) return [HOOP[side][0] + DIR[side] * (rnd() * 6), rnd() < 0.5 ? 3.2 : 46.8];
    const d = kind === 3 ? 24 + rnd() * 2 : (rnd() < 0.6 ? 2 + rnd() * 4 : 9 + rnd() * 11);
    const [x, y] = at(side, d, (rnd() - 0.5) * (kind === 3 ? 120 : 150));
    return [Math.min(92.5, Math.max(1.5, x)), Math.min(48.5, Math.max(1.5, y))];
  }

  // ---------------- top ----------------
  const ball = { holder: null, x: 47, y: 25, flight: null };
  const giveBall = (p) => { ball.holder = p; ball.flight = null; };
  function throwBall(from, to, height, dur, onLand) {
    ball.holder = null;
    ball.flight = { x0: from[0], y0: from[1], x1: to[0], y1: to[1], h: height, t: 0, dur, onLand };
  }

  // ---------------- skor, akis, grafik, efekt ----------------
  let speed = 3;
  function pop(x, y, text, cls) {
    const t = el("text", { x, y, class: `sa-pop ${cls || ""}` }, fx);
    t.textContent = text;
    setTimeout(() => t.remove(), 1300 / Math.max(1, speed / 2));
  }
  function flash(side) { rims[side].classList.add("flash"); setTimeout(() => rims[side].classList.remove("flash"), 300); }
  const feed = $(".sa-feed");
  const flow = $(".sa-flow"), FW = 600, FH = 90;
  let maxM = 8;
  { let a = 0, h = 0; events.forEach((e) => { const n = e.kind === 1 ? e.shots.filter(Boolean).length : e.made ? e.kind : 0; if (e.side === "away") a += n; else h += n; maxM = Math.max(maxM, Math.abs(h - a)); }); }
  const gx = (t) => (t / GAME) * FW, gy = (m) => FH / 2 - (m / maxM) * (FH / 2 - 4);
  const fl = (tag, attrs) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); flow.appendChild(n); return n; };
  fl("line", { x1: 0, y1: FH / 2, x2: FW, y2: FH / 2, class: "sa-zero" });
  [1, 2, 3].forEach((q) => fl("line", { x1: gx(q * 720), y1: 0, x2: gx(q * 720), y2: FH, class: "sa-q" }));
  const path = fl("polyline", { class: "sa-line", points: `0,${FH / 2}` });
  let score = { away: 0, home: 0 }, pts = [[0, FH / 2]];
  const clockText = (t) => { const q = Math.min(4, Math.floor(t / 720) + 1), left = Math.max(0, q * 720 - t); return `Q${q} ${Math.floor(left / 60)}:${String(Math.floor(left % 60)).padStart(2, "0")}`; };
  function addPoints(e, n) {
    score[e.side] += n;
    $(".sa-a").textContent = score.away; $(".sa-h").textContent = score.home;
    pts.push([gx(e.t), gy(score.home - score.away)]);
    path.setAttribute("points", pts.map((p) => p.join(",")).join(" "));
  }
  function log(e, text, big) {
    const row = document.createElement("div");
    row.className = `sa-ev ${e.side}${big ? " big" : ""}`;
    row.innerHTML = `<time>${clockText(e.t)}</time><span>${window.HL.escapeHtml(text)}</span><b>${score.away}-${score.home}</b>`;
    feed.prepend(row);
    while (feed.childNodes.length > 60) feed.removeChild(feed.lastChild);
  }
  const WHAT2 = ["jump shot", "pull-up jumper", "fadeaway", "floater", "hook shot"];

  // ---------------- hucumlar: adimlar ----------------
  // Her adim {dur (sn, 1x hizda), start()}; oyuncular hedeflerine kendileri kosar.
  function steps(e) {
    const side = e.side, [hx, hy] = HOOP[side], out = [];
    out.push({ dur: 0, start: () => { $(".sa-clock").textContent = clockText(e.t); } });

    if (e.kind === "stl") {
      ensure(e.p);
      const victim = pick(court[other(side)]);
      out.push({ dur: 0.55, start: () => {
        formation(other(side));
        giveBall(victim);
        const v = P.get(victim); v.tx = 47 + DIR[side] * 8; v.ty = 25 + (rnd() - 0.5) * 16;
      } });
      out.push({ dur: 0.6, start: () => {
        const v = P.get(victim), s = P.get(e.p);
        s.tx = v.x + DIR[side] * 0.8; s.ty = v.y;
        giveBall(e.p); pop(v.x, v.y - 3, "STEAL!", "hot");
        log(e, `${e.p.name} steal`, true);
      } });
      return out;
    }

    if (e.kind === 1) {
      ensure(e.p);
      const line = [hx + DIR[side] * 13.75, 25];
      out.push({ dur: 0.6, start: () => {
        // atici cizgide, digerleri koridor boyunca
        [...court.away, ...court.home].filter((q) => q !== e.p).forEach((q, i) => {
          const s = P.get(q);
          if (i >= 8) { s.tx = hx + DIR[side] * 22; s.ty = 25 + (i - 8.5) * 6; return; }
          s.tx = hx + DIR[side] * (4 + (i % 4) * 3); s.ty = i < 4 ? 16.3 : 33.7;
        });
        const sp = P.get(e.p); sp.tx = line[0]; sp.ty = line[1];
        giveBall(e.p);
      } });
      e.shots.forEach((made, i) => {
        out.push({ dur: 0.55, start: () => {
          throwBall(line, [hx, hy], 3.5, 0.45, () => {
            if (made) { addPoints(e, 1); pop(hx, hy - 2.5, "+1"); flash(side); log(e, `${e.p.name} makes free throw ${i + 1} of ${e.shots.length}`); }
            else pop(hx, hy - 2.5, "miss", "cold");
            if (i < e.shots.length - 1) giveBall(e.p);
          });
        } });
      });
      return out;
    }

    // Sut: dizilis -> (pas) -> sut -> sonuc
    ensure(e.p, [e.ast]);
    if (e.ast) ensure(e.ast, [e.p]);
    if (e.blk) ensure(e.blk);
    const spot = shotSpot(side, e.kind);
    const guards = court[side].filter((q) => rank(q) === 0 && q !== e.p);
    const handler = e.ast || (rnd() < 0.5 || !guards.length ? e.p : pick(guards));
    out.push({ dur: 0.75, start: () => {
      formation(side);
      giveBall(handler);
      const s = P.get(e.p); s.tx = spot[0]; s.ty = spot[1];
      if (e.blk) { const b = P.get(e.blk); b.tx = spot[0] + DIR[side] * -1.8; b.ty = spot[1] + 0.6; }
      else {
        const mark = [...marks.entries()].find(([, o]) => o === e.p);
        if (mark) { const d = P.get(mark[0]); d.tx = spot[0] - DIR[side] * 2.6; d.ty = spot[1] + (rnd() - 0.5) * 2; }
      }
    } });
    if (handler !== e.p) {
      out.push({ dur: 0.4, start: () => {
        const a = P.get(handler), s = P.get(e.p);
        throwBall([a.x, a.y], [s.tx, s.ty], 0.6, 0.32, () => giveBall(e.p));
        if (e.ast) pop(a.x, a.y - 3, "assist", "ast");
      } });
    }
    out.push({ dur: e.kind === 3 ? 0.8 : 0.65, start: () => {
      const s = P.get(e.p), from = [s.x, s.y];
      if (e.blk) {
        const b = P.get(e.blk);
        throwBall(from, [b.x, b.y], 1.2, 0.22, () => {
          pop(b.x, b.y - 3, "BLOCK!", "hot");
          throwBall([b.x, b.y], shotSpot(side, 2), 0.4, 0.3, () => {});
        });
        log(e, `${e.blk.name} blocks ${last(e.p.name)}`, true);
        return;
      }
      const dist = Math.hypot(from[0] - hx, from[1] - hy);
      throwBall(from, [hx, hy], 2.5 + dist * 0.2, e.kind === 3 ? 0.65 : 0.5, () => {
        const what = e.kind === 3 ? "3-pt jumper" : (dist < 6 ? pick(["layup", "dunk", "layup"]) : pick(WHAT2));
        if (e.made) {
          addPoints(e, e.kind);
          pop(hx, hy - 2.5, `+${e.kind}`, e.kind === 3 ? "hot" : "");
          flash(side);
          log(e, `${e.p.name} makes ${what}${e.ast ? ` (${last(e.ast.name)} assists)` : ""}`, e.kind === 3);
        } else {
          pop(hx, hy - 2.5, "miss", "cold");
          const r = [hx + DIR[side] * (2 + rnd() * 6), hy + (rnd() - 0.5) * 12];
          throwBall([hx, hy], r, 1.5, 0.3, () => {
            const d2 = (q) => Math.hypot(P.get(q).x - r[0], P.get(q).y - r[1]);
            giveBall([...court.away, ...court.home].sort((a, b) => d2(a) - d2(b))[0]);
          });
          log(e, `${e.p.name} misses ${what}`);
        }
      });
    } });
    out.push({ dur: 0.3, start: () => {} });
    return out;
  }

  // ---------------- dongu ----------------
  let playing = false, idx = 0, queue = [], cur = null, curT = 0, lastTs = 0;
  function nextStep() {
    while (!queue.length && idx < events.length) queue = steps(events[idx++]);
    if (!queue.length) { cur = null; return false; }
    cur = queue.shift(); curT = 0; cur.start();
    return true;
  }
  function render(dt) {
    const k = 1 - Math.exp(-dt * 6 * speed);
    P.forEach((s) => {
      s.x += (s.tx - s.x) * k; s.y += (s.ty - s.y) * k;
      s.g.setAttribute("transform", `translate(${s.x.toFixed(2)} ${s.y.toFixed(2)})`);
      s.g.classList.toggle("bench", !onCourt(s.p));      // kenardakiler gorunmez
    });
    let bx, by, bh = 0;
    if (ball.flight) {
      const f = ball.flight;
      f.t += dt * speed;
      const u = Math.min(1, f.t / f.dur);
      bx = f.x0 + (f.x1 - f.x0) * u; by = f.y0 + (f.y1 - f.y0) * u; bh = 4 * f.h * u * (1 - u);
      if (u >= 1) { const cb = f.onLand; ball.flight = null; ball.x = f.x1; ball.y = f.y1; if (cb) cb(); }
    } else if (ball.holder) {
      const s = P.get(ball.holder);
      bx = s.x + 1.3; by = s.y - 0.5 + Math.abs(Math.sin(performance.now() / 110)) * 0.45;   // dripling
    } else { bx = ball.x; by = ball.y; }
    ball.x = bx; ball.y = by;
    ballShadow.setAttribute("cx", bx); ballShadow.setAttribute("cy", by + 0.7);
    ballEl.setAttribute("cx", bx); ballEl.setAttribute("cy", by - bh * 0.6);
    ballEl.setAttribute("r", (0.75 + bh * 0.05).toFixed(2));
  }
  function frame(ts) {
    const dt = lastTs ? Math.min(0.1, (ts - lastTs) / 1000) : 0;
    lastTs = ts;
    if (playing) {
      if (!cur && !nextStep()) { finish(); return requestAnimationFrame(frame); }
      curT += dt * speed;
      while (playing && cur && curT >= cur.dur && !ball.flight) { if (!nextStep()) { finish(); break; } }
    }
    render(dt);
    requestAnimationFrame(frame);
  }
  function finish() {
    playing = false; cur = null;
    $(".sa-clock").textContent = "Final";
    $(".sa-play").textContent = "Replay";
  }
  function reset() {
    seed = 11; for (const ch of String(D.game)) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
    idx = 0; queue = []; cur = null; score = { away: 0, home: 0 }; pts = [[0, FH / 2]]; marks.clear();
    path.setAttribute("points", `0,${FH / 2}`); feed.innerHTML = ""; fx.innerHTML = "";
    $(".sa-a").textContent = 0; $(".sa-h").textContent = 0; $(".sa-clock").textContent = "Q1 12:00";
    SIDES.forEach((s) => { court[s] = starters(s); });
    // Baslangic: ilk besler orta yuvarlak cevresinde, yedekler kenarda
    P.forEach((st) => {
      const bench = !onCourt(st.p), i = court[st.p.side].indexOf(st.p);
      st.x = st.tx = bench ? 47 + (rnd() - 0.5) * 30 : 47 - DIR[st.p.side] * (3 + (i % 3) * 5);
      st.y = st.ty = bench ? (st.p.side === "away" ? 53 : -3) : 25 + (i - 2) * 6;
    });
    giveBall(court.away[0]);
    render(0);
  }

  $(".sa-play").addEventListener("click", () => {
    if (!playing && !cur && idx >= events.length) reset();
    playing = !playing;
    $(".sa-play").textContent = playing ? "Pause" : "Play";
  });
  root.querySelectorAll("[data-speed]").forEach((b) => b.addEventListener("click", () => {
    speed = +b.dataset.speed;
    root.querySelectorAll("[data-speed]").forEach((x) => x.classList.toggle("is-on", x === b));
  }));
  $(".sa-skip").addEventListener("click", () => {
    // Kalan olaylar animasyonsuz: skor, akis ve grafik tamamlanir
    playing = false; queue = []; cur = null; ball.flight = null;
    for (; idx < events.length; idx++) {
      const e = events[idx];
      if (e.kind === 1) { const n = e.shots.filter(Boolean).length; if (n) addPoints(e, n); }
      else if (e.made) { addPoints(e, e.kind); log(e, `${e.p.name} makes ${e.kind === 3 ? "3-pt jumper" : "2-pt shot"}`); }
    }
    finish();
  });
  reset();
  requestAnimationFrame(frame);
})();
