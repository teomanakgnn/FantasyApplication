// Gunluk kazi kazan (ana sayfa, giris yapan kullanici). Kaplama fare ya da parmakla
// kazinir; yarisi kazininca acilir ve sunucuya bildirilir. Kartta yalnizca ipucu
// SAYISI var - hangi oyunlarda oldugu yazmaz, kullanici oyunlari tek tek dener.
(function () {
  const box = document.getElementById("scratch-card");
  if (!box) return;
  const { api, toast, escapeHtml: h } = window.HL;
  const GAMES = [["Mystery Player", "/daily"], ["Stat Match", "/stat-match"], ["Starting Five", "/starting-five"],
                 ["82-0 Challenge", "/82-0"], ["Pyramid", "/pyramid"], ["3x3 Grid", "/grid"]];
  const links = () => `<div class="sc-games">${GAMES.map(([n, u]) => `<a href="${u}">${n}</a>`).join("")}</div>`;
  const word = (n) => (n === 1 ? "hint" : "hints");

  function status(c) {
    box.hidden = false;
    const done = c.found >= c.n;
    box.innerHTML = `<div class="sc-status ${done ? "done" : ""}">
      <div><b>${done ? "Every hint found today" : `${c.n} ${word(c.n)} hidden in today's games`}</b>
        <span>${done ? "Come back tomorrow for a new scratch card." : `Found ${c.found} of ${c.n}. Each game shows "no hint here" or your hint - try them all.`}</span></div>
      ${done ? "" : links()}</div>`;
  }

  function card(c) {
    box.hidden = false;
    box.innerHTML = `<div class="sc-wrap">
      <div class="sc-head"><b>Daily scratch card</b><span>Scratch it with your mouse or finger</span></div>
      <div class="sc-card" id="sc-card">
        <div class="sc-prize"><strong>${c.n}</strong><b>${word(c.n).toUpperCase()}</b>
          <span>Hidden in ${c.n} of today's games. Which ones? Play them to find out.</span></div>
        <canvas id="sc-canvas" aria-label="Scratch card - scratch to reveal"></canvas>
      </div></div>`;
    paint(c);
  }

  function paint(c) {
    const wrap = document.getElementById("sc-card"), cv = document.getElementById("sc-canvas");
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const W = wrap.clientWidth, H = wrap.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext("2d");
    g.scale(dpr, dpr);
    // Metalik kaplama
    const grad = g.createLinearGradient(0, 0, W, H);
    grad.addColorStop(0, "#B9BFCB"); grad.addColorStop(0.45, "#E6E9EF"); grad.addColorStop(0.55, "#AEB4C0"); grad.addColorStop(1, "#D3D7DF");
    g.fillStyle = grad; g.fillRect(0, 0, W, H);
    g.globalAlpha = 0.18;
    for (let i = 0; i < 260; i++) { g.fillStyle = Math.random() < 0.5 ? "#fff" : "#6B7280"; g.fillRect(Math.random() * W, Math.random() * H, 2, 2); }
    g.globalAlpha = 1;
    g.fillStyle = "#3A4150"; g.textAlign = "center";
    g.font = "900 26px Inter, system-ui, sans-serif"; g.fillText("SCRATCH HERE", W / 2, H / 2 + 2);
    g.font = "700 14px Inter, system-ui, sans-serif"; g.fillText("Today's hints are underneath", W / 2, H / 2 + 26);

    let down = false, last = null, moves = 0, opened = false;
    const pos = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    const scratchAt = (p) => {
      g.globalCompositeOperation = "destination-out";
      g.lineWidth = 38; g.lineCap = "round"; g.lineJoin = "round";
      g.beginPath();
      if (last) { g.moveTo(last[0], last[1]); g.lineTo(p[0], p[1]); g.stroke(); }
      g.arc(p[0], p[1], 19, 0, Math.PI * 2); g.fill();
      last = p;
      if (++moves % 6 === 0) check();
    };
    function check() {
      if (opened) return;
      const data = g.getImageData(0, 0, cv.width, cv.height).data;
      let clear = 0, total = 0;
      for (let i = 3; i < data.length; i += 4 * 24) { total++; if (data[i] < 40) clear++; }
      if (clear / total > 0.5) reveal();
    }
    async function reveal() {
      opened = true;
      cv.classList.add("sc-gone");
      box.querySelector(".sc-card").classList.add("sc-won");
      if (navigator.vibrate) navigator.vibrate(80);
      try {
        const r = await api("/api/scratch", { method: "POST", body: {} });
        if (window.gtag) gtag("event", "scratch_card", { hints: r.n });
        setTimeout(() => status(r), 2600);
      } catch (err) { toast(err.message, true); }
    }
    cv.addEventListener("pointerdown", (e) => { down = true; last = null; cv.setPointerCapture(e.pointerId); scratchAt(pos(e)); });
    cv.addEventListener("pointermove", (e) => { if (down) scratchAt(pos(e)); });
    const up = () => { down = false; last = null; check(); };
    cv.addEventListener("pointerup", up); cv.addEventListener("pointercancel", up);
  }

  api("/api/scratch").then((c) => (c.scratched ? status(c) : card(c))).catch(() => {});
})();
