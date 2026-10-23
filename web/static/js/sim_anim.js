// Mac simulasyonu animasyonu: "en tipik mac" saha uzerinde oynatilir.
// Elimizde gercek play-by-play yok: olaylar tipik macin kutu skorundan uretilir
// (her oyuncunun isabet / kacirdigi sut / serbest atisi, asistler, bloklar, top
// calmalar), 48 dakikaya dagitilir. Son skor kutu skorla birebir ayni. Tohum mac
// kimliginden: herkes ayni maci izler.
(function () {
  const root = document.getElementById("sim-anim");
  if (!root) return;
  const D = JSON.parse(document.getElementById("sim-anim-data").textContent);
  const $ = (s) => root.querySelector(s);
  const NS = "http://www.w3.org/2000/svg";
  const GAME = 2880;  // saniye

  // ---------------- tohumlu rastgele ----------------
  let seed = 0;
  for (const ch of String(D.game)) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
  const rnd = () => { seed = (seed + 0x6D2B79F5) >>> 0; let t = seed; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const pick = (arr) => arr[Math.floor(rnd() * arr.length)];
  const shuffle = (a) => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const last = (name) => name.split(" ").slice(-1)[0];

  // ---------------- olaylar ----------------
  // Oyuncunun sahada oldugu anlar: dakikasi kadar, rastgele ama butun maca yayilmis
  const when = (p) => Math.floor(rnd() * GAME);
  const events = [];
  ["away", "home"].forEach((side) => {
    const opp = side === "away" ? "home" : "away";
    const team = D[side];
    const astPool = shuffle(team.flatMap((p) => Array(p.ast).fill(p)));
    const blkPool = shuffle(D[opp].flatMap((p) => Array(p.blk).fill(p)));
    team.forEach((p) => {
      const shots = [];
      for (let i = 0; i < p.tpm; i++) shots.push({ kind: 3, made: true });
      for (let i = 0; i < p.tpa - p.tpm; i++) shots.push({ kind: 3, made: false });
      for (let i = 0; i < p.fgm - p.tpm; i++) shots.push({ kind: 2, made: true });
      for (let i = 0; i < (p.fga - p.tpa) - (p.fgm - p.tpm); i++) shots.push({ kind: 2, made: false });
      shots.forEach((s) => events.push({ t: when(p), side, p, ...s }));
      // Serbest atislar ikiserli gruplar halinde
      let fta = p.fta;
      while (fta > 0) {
        const n = Math.min(fta, fta === 3 ? 3 : 2), t = when(p);
        for (let i = 0; i < n; i++) events.push({ t: t + i, side, p, kind: 1, made: false });
        fta -= n;
      }
      for (let i = 0; i < p.stl; i++) events.push({ t: when(p), side, p, kind: "stl" });
    });
    // Asist: takim arkadasinin isabetli sutuna (kendi sutuna degil)
    events.filter((e) => e.side === side && e.made && e.kind > 1).forEach((e) => {
      const i = astPool.findIndex((a) => a.name !== e.p.name);
      if (i >= 0 && rnd() < 0.85) e.ast = astPool.splice(i, 1)[0];
    });
    // Blok: rakibin kacirdigi sutlara
    events.filter((e) => e.side === side && e.made === false && e.kind > 1).forEach((e) => {
      if (blkPool.length && rnd() < 0.18) e.blk = blkPool.pop();
    });
  });
  // Ayni saniyede cakisma olmasin, sirala
  events.forEach((e, i) => { e.t += i * 0.001; });
  events.sort((a, b) => a.t - b.t);
  // Serbest atis sayilari kutu skorla tam tutsun (yukaridaki olasilikli dagitim sapabilir)
  ["away", "home"].forEach((side) => D[side].forEach((p) => {
    const fts = events.filter((e) => e.side === side && e.p === p && e.kind === 1);
    fts.forEach((e, i) => { e.made = i < p.ftm; });
    shuffle(fts.map((e) => e.made)).forEach((m, i) => { fts[i].made = m; });
  }));

  // ---------------- saha ----------------
  const svg = $(".sa-court");
  const el = (tag, attrs, parent = svg) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); parent.appendChild(n); return n; };
  const lines = el("g", { class: "sa-lines", fill: "none" });
  el("rect", { x: 0.5, y: 0.5, width: 93, height: 49 }, lines);
  el("line", { x1: 47, y1: 0.5, x2: 47, y2: 49.5 }, lines);
  el("circle", { cx: 47, cy: 25, r: 6 }, lines);
  [[5.25, 1], [88.75, -1]].forEach(([hx, dir]) => {
    const base = dir === 1 ? 0.5 : 93.5;
    el("rect", { x: dir === 1 ? base : base - 19, y: 17, width: 19, height: 16 }, lines);
    el("circle", { cx: base + dir * 19, cy: 25, r: 6 }, lines);
    el("path", { d: `M${base} 3 L${base + dir * 14} 3 A23.75 23.75 0 0 ${dir === 1 ? 1 : 0} ${base + dir * 14} 47 L${base} 47` }, lines);
    el("line", { x1: base + dir * 4, y1: 22, x2: base + dir * 4, y2: 28 }, lines);
    el("circle", { cx: hx, cy: 25, r: 0.75 }, lines);
  });
  const marks = el("g", {});
  const ball = el("circle", { r: 0.9, class: "sa-ball", cx: 0, cy: 0, opacity: 0 });
  // Top: sut yerinden potaya CSS gecisiyle ucar (SVG'de px = saha birimi)
  function fly(x, y, hx) {
    ball.style.transition = "none";
    ball.style.transform = `translate(${x}px, ${y}px)`;
    ball.setAttribute("opacity", 1);
    ball.getBoundingClientRect();
    ball.style.transition = `transform ${Math.max(0.12, 0.45 / speed)}s ease-out`;
    ball.style.transform = `translate(${hx}px, 25px)`;
  }

  // Sut yeri: away sola, home saga hucum eder
  function spot(e) {
    const hx = e.side === "away" ? 5.25 : 88.75, dir = e.side === "away" ? 1 : -1;
    if (e.kind === 1) return [hx + dir * 13.75, 25];
    if (e.kind === 3 && rnd() < 0.25) return [hx + dir * (rnd() * 8 - 4) + (dir === 1 ? 4 : -4), rnd() < 0.5 ? 3.2 : 46.8];
    const r = e.kind === 3 ? 24 + rnd() * 2.5 : (rnd() < 0.6 ? 1 + rnd() * 5 : 8 + rnd() * 12);
    const a = (rnd() - 0.5) * Math.PI * (e.kind === 3 ? 0.7 : 0.85);   // ucluk: kose disinda yay icinde
    const x = hx + dir * Math.cos(a) * r, y = 25 + Math.sin(a) * r;
    return [Math.min(92.5, Math.max(1.5, x)), Math.min(48.5, Math.max(1.5, y))];
  }

  // ---------------- akis grafigi ----------------
  const flow = $(".sa-flow"), FW = 600, FH = 90;
  const margins = [[0, 0]];
  let a = 0, h = 0;
  events.forEach((e) => { if (e.made && e.kind !== "stl") { if (e.side === "away") a += e.kind; else h += e.kind; margins.push([e.t, h - a]); } });
  const maxM = Math.max(8, ...margins.map((m) => Math.abs(m[1])));
  const fx = (t) => (t / GAME) * FW, fy = (m) => FH / 2 - (m / maxM) * (FH / 2 - 4);
  const fl = (tag, attrs) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); flow.appendChild(n); return n; };
  fl("line", { x1: 0, y1: FH / 2, x2: FW, y2: FH / 2, class: "sa-zero" });
  [1, 2, 3].forEach((q) => fl("line", { x1: fx(q * 720), y1: 0, x2: fx(q * 720), y2: FH, class: "sa-q" }));
  const path = fl("polyline", { class: "sa-line", points: "0," + FH / 2 });

  // ---------------- oynatma ----------------
  const feed = $(".sa-feed");
  let clock = 0, idx = 0, playing = false, speed = 1, lastTs = 0, score = { away: 0, home: 0 }, pts = [[0, FH / 2]];
  const REAL = 75;  // 1x'te butun mac ~75 saniye
  const fmt = (t) => { const q = Math.min(4, Math.floor(t / 720) + 1), left = Math.max(0, q * 720 - t); return [q, `${Math.floor(left / 60)}:${String(Math.floor(left % 60)).padStart(2, "0")}`]; };

  function shotText(e) {
    if (e.kind === "stl") return `${e.p.name} steal`;
    if (e.kind === 1) return `${e.p.name} ${e.made ? "makes" : "misses"} free throw`;
    const what = e.kind === 3 ? "3-pt jumper" : pick(["layup", "jump shot", "floater", "dunk", "hook shot", "pull-up"]);
    let s = `${e.p.name} ${e.made ? "makes" : "misses"} ${what}`;
    if (e.ast) s += ` (${last(e.ast.name)} assists)`;
    if (e.blk) s = `${e.blk.name} blocks ${last(e.p.name)}'s ${what}`;
    return s;
  }

  function show(e) {
    const [q, c] = fmt(e.t);
    if (e.kind !== "stl") {
      const [x, y] = spot(e);
      const hx = e.side === "away" ? 5.25 : 88.75;
      if (e.kind > 1 || e.made) fly(x, y, hx);
      if (e.kind > 1) {
        const m = el("g", { class: `sa-mark ${e.made ? "made" : "miss"} ${e.side}`, transform: `translate(${x} ${y})` }, marks);
        if (e.made) el("circle", { r: 0.95 }, m);
        else el("path", { d: "M-.7 -.7 L.7 .7 M.7 -.7 L-.7 .7" }, m);
        while (marks.childNodes.length > 40) marks.removeChild(marks.firstChild);
      }
      if (e.made) score[e.side] += e.kind;
    }
    $(".sa-a").textContent = score.away; $(".sa-h").textContent = score.home;
    $(".sa-clock").textContent = `Q${q} ${c}`;
    const big = e.kind === 3 && e.made || e.blk || e.kind === "stl";
    if (e.kind !== 1 || e.made) {
      const row = document.createElement("div");
      row.className = `sa-ev ${e.side}${big ? " big" : ""}${e.made ? " made" : ""}`;
      row.innerHTML = `<time>Q${q} ${c}</time><span>${window.HL.escapeHtml(shotText(e))}</span><b>${score.away}-${score.home}</b>`;
      feed.prepend(row);
      while (feed.childNodes.length > 60) feed.removeChild(feed.lastChild);
    }
    if (e.made && e.kind !== "stl") {
      pts.push([fx(e.t), fy(score.home - score.away)]);
      path.setAttribute("points", pts.map((p) => p.join(",")).join(" "));
    }
  }

  function frame(ts) {
    if (!playing) return;
    const dt = lastTs ? (ts - lastTs) / 1000 : 0;
    lastTs = ts;
    clock = Math.min(GAME, clock + dt * (GAME / REAL) * speed);
    while (idx < events.length && events[idx].t <= clock) show(events[idx++]);
    if (idx >= events.length) {
      $(".sa-clock").textContent = "Final";
      ball.setAttribute("opacity", 0);
      playing = false; $(".sa-play").textContent = "Replay";
      return;
    }
    requestAnimationFrame(frame);
  }

  function reset() {
    clock = 0; idx = 0; score = { away: 0, home: 0 }; pts = [[0, FH / 2]];
    path.setAttribute("points", "0," + FH / 2);
    marks.innerHTML = ""; feed.innerHTML = "";
    $(".sa-a").textContent = 0; $(".sa-h").textContent = 0; $(".sa-clock").textContent = "Q1 12:00";
  }

  $(".sa-play").addEventListener("click", () => {
    if (!playing && idx >= events.length) reset();
    playing = !playing;
    $(".sa-play").textContent = playing ? "Pause" : "Play";
    lastTs = 0;
    if (playing) requestAnimationFrame(frame);
  });
  root.querySelectorAll("[data-speed]").forEach((b) => b.addEventListener("click", () => {
    speed = +b.dataset.speed;
    root.querySelectorAll("[data-speed]").forEach((x) => x.classList.toggle("is-on", x === b));
  }));
  $(".sa-skip").addEventListener("click", () => {
    while (idx < events.length) show(events[idx++]);
    $(".sa-clock").textContent = "Final"; playing = false; $(".sa-play").textContent = "Replay";
  });
  reset();
})();
