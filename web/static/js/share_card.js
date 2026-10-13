// Oyun sonuclari icin paylasim gorseli (1080x1350, Instagram/WhatsApp dikey).
// Telefonda dogrudan paylasim menusu; masaustunde onizleme + indir + metni kopyala.
(function () {
  const W = 1080, H = 1350;
  const FONT = '"Inter", system-ui, -apple-system, "Segoe UI", sans-serif';
  const C = { bg: "#0B0F17", panel: "#131926", line: "rgba(255,255,255,.10)", text: "#E8ECF4", muted: "#9AA6BD",
              dim: "#6B7893", brand: "#D0112B", good: "#34D399", bad: "#EF6464", gold: "#F2C94C", wood: "#B9773F" };

  const loadImg = (src) => new Promise((ok) => {
    if (!src) return ok(null);
    const i = new Image(); i.crossOrigin = "anonymous";
    i.onload = () => ok(i); i.onerror = () => ok(null); i.src = src;
  });

  function rr(g, x, y, w, h, r) {
    g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
  }
  function font(g, weight, size) { g.font = `${weight} ${size}px ${FONT}`; }
  function text(g, s, x, y, { weight = 700, size = 32, color = C.text, align = "left", max } = {}) {
    font(g, weight, size); g.fillStyle = color; g.textAlign = align; g.textBaseline = "alphabetic";
    let str = String(s);
    if (max) while (g.measureText(str).width > max && str.length > 3) str = str.slice(0, -2) + "…";
    g.fillText(str, x, y); g.textAlign = "left";
  }
  // Yuvarlak fotograf (oyuncu yuzu ust kisimda kalsin diye kirpilir)
  function disc(g, img, cx, cy, r, { ring = "#fff", ringW = 6, fill = "#1A2130", name = "" } = {}) {
    g.save(); g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2); g.fillStyle = fill; g.fill(); g.clip();
    if (img) {
      const s = (r * 2) / Math.min(img.width, img.height * 1.0) * 1.25;
      const w = img.width * s, h = img.height * s;
      g.drawImage(img, cx - w / 2, cy - r * 1.05, w, h);
    } else if (name) {
      const ini = name.split(" ").filter(Boolean).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
      font(g, 900, Math.round(r * .8)); g.fillStyle = "#E8ECF4"; g.textAlign = "center"; g.textBaseline = "middle";
      g.fillText(ini, cx, cy + 2); g.textAlign = "left"; g.textBaseline = "alphabetic";
    }
    g.restore();
    g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2); g.lineWidth = ringW; g.strokeStyle = ring; g.stroke();
  }
  function pill(g, s, cx, cy, { bg = "rgba(11,15,23,.85)", color = "#fff", size = 26, weight = 800, padX = 14, h = 40 } = {}) {
    font(g, weight, size); const w = g.measureText(s).width + padX * 2;
    rr(g, cx - w / 2, cy - h / 2, w, h, h / 2); g.fillStyle = bg; g.fill();
    g.fillStyle = color; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(s, cx, cy + 1);
    g.textAlign = "left"; g.textBaseline = "alphabetic";
    return w;
  }

  async function base(game, num) {
    await (document.fonts ? document.fonts.ready : Promise.resolve());
    const cv = document.createElement("canvas"); cv.width = W; cv.height = H;
    const g = cv.getContext("2d");
    g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
    const glow = g.createRadialGradient(W / 2, -120, 40, W / 2, -120, 900);
    glow.addColorStop(0, "rgba(208,17,43,.38)"); glow.addColorStop(1, "rgba(208,17,43,0)");
    g.fillStyle = glow; g.fillRect(0, 0, W, H);
    const logo = await loadImg("/static/img/logo.png");
    if (logo) g.drawImage(logo, 60, 48, 76, 76);
    text(g, "HoopLife NBA", 152, 100, { weight: 800, size: 36 });
    pill(g, `${game}${num ? "  #" + num : ""}`, W - 60 - 150, 86, { bg: C.brand, size: 26, h: 52, padX: 22 });
    return { cv, g };
  }

  function footer(g, path) {
    g.fillStyle = "rgba(255,255,255,.06)"; g.fillRect(0, H - 110, W, 110);
    text(g, "Can you beat it?", 60, H - 46, { weight: 800, size: 34 });
    text(g, `app.hooplifenba.com${path}`, W - 60, H - 46, { weight: 700, size: 30, color: C.muted, align: "right" });
  }

  async function share(cv, { filename, text: msg, title }) {
    const blob = await new Promise((ok) => cv.toBlob(ok, "image/png"));
    const file = new File([blob], filename, { type: "image/png" });
    const mobile = matchMedia("(pointer: coarse)").matches;
    if (mobile && navigator.canShare && navigator.canShare({ files: [file] })) {
      try { await navigator.share({ files: [file], text: msg, title }); return; }
      catch (err) { if (err.name === "AbortError") return; }
    }
    const url = URL.createObjectURL(blob);
    window.HL.openModal(`
      <div class="share-preview">
        <img src="${url}" alt="Share image">
        <div class="share-actions">
          <a class="btn btn-primary" href="${url}" download="${filename}">Download image</a>
          <button class="btn" type="button" data-copy>Copy link text</button>
        </div>
        <p class="tiny dim">Post the image with the text so friends can play too.</p>
      </div>`);
    const btn = document.querySelector("[data-copy]");
    if (btn) btn.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(msg); window.HL.toast("Copied."); }
      catch (e) { window.prompt("Copy:", msg); }
    });
  }

  window.HLCard = { W, H, C, loadImg, rr, text, disc, pill, base, footer, share, font };
})();
