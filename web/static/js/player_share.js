// Oyuncu mac karti paylasim gorseli (1080x1350): foto, mac, 9 kategori,
// fantezi puani, sut haritasi. Kart her sayfadan (box score, mac sayfasi,
// ana sayfa) acildigi icin genel; HLCard yoksa share_card.js'i yukler.
(function () {
  function needCard() {
    if (window.HLCard) return Promise.resolve();
    return new Promise((ok, fail) => {
      const s = document.createElement("script");
      s.src = "/static/js/share_card.js"; s.onload = ok; s.onerror = fail;
      document.head.appendChild(s);
    });
  }

  function court(g, x, y, w, d, C) {
    const s = w / 50, h = 36 * s, P = (fx, fy) => [x + fx * s, y + fy * s];
    const K = window.HLCard;
    K.rr(g, x, y, w, h, 22); g.fillStyle = "#2A2119"; g.fill();
    g.save(); K.rr(g, x, y, w, h, 22); g.clip();
    g.strokeStyle = "rgba(232,236,244,.35)"; g.lineWidth = 3;
    g.strokeRect(...P(17, 0), 16 * s, 19 * s);
    g.beginPath(); g.arc(...P(25, 19), 6 * s, 0, Math.PI * 2); g.stroke();
    g.beginPath(); g.moveTo(...P(3, 0)); g.lineTo(...P(3, 14.2));
    g.arc(...P(25, 5.25), 23.75 * s, Math.atan2(8.95, -22), Math.atan2(8.95, 22), true);
    g.lineTo(...P(47, 0)); g.stroke();
    g.beginPath(); g.arc(...P(25, 5.25), 4 * s, Math.PI, 0, true); g.stroke();
    g.beginPath(); g.moveTo(...P(22, 4)); g.lineTo(...P(28, 4)); g.stroke();
    g.beginPath(); g.arc(...P(25, 5.25), 0.75 * s, 0, Math.PI * 2); g.stroke();
    // Kacanlar altta, isabetler ustte
    d.shots.filter((t) => !t.made).forEach((t) => {
      const [cx, cy] = P(t.sx, t.sy), r = 0.75 * s;
      g.strokeStyle = C.bad; g.lineWidth = 5; g.lineCap = "round";
      g.beginPath(); g.moveTo(cx - r, cy - r); g.lineTo(cx + r, cy + r); g.moveTo(cx + r, cy - r); g.lineTo(cx - r, cy + r); g.stroke();
    });
    d.shots.filter((t) => t.made).forEach((t) => {
      const [cx, cy] = P(t.sx, t.sy);
      g.beginPath(); g.arc(cx, cy, 0.95 * s, 0, Math.PI * 2); g.fillStyle = C.good; g.fill();
      g.lineWidth = 2; g.strokeStyle = "rgba(0,0,0,.4)"; g.stroke();
    });
    g.restore();
    return h;
  }

  async function draw(d) {
    await needCard();
    const K = window.HLCard, { W, C } = K;
    const { cv, g } = await K.base("Game card");
    const m = d.meta || {};

    // Ust: foto, ad, mac
    const img = await K.loadImg(d.photo);
    K.disc(g, img, 170, 270, 100, { ring: C.brand, ringW: 6, name: d.name });
    K.text(g, d.name, 300, 245, { weight: 900, size: 56, max: 520 });
    const vs = m.away && m.home ? (d.team === m.home ? `vs ${m.away}` : `@ ${m.home}`) : "";
    K.text(g, `${d.team}${vs ? " " + vs : ""} · ${d.min} MIN${d.pm ? " · " + d.pm + " +/-" : ""}`, 300, 292, { weight: 700, size: 30, color: C.muted, max: 520 });
    if (m.away) K.text(g, `${m.away} ${m.away_score} - ${m.home_score} ${m.home}${m.date ? " · " + m.date : ""}`, 300, 336, { weight: 700, size: 28, color: C.dim, max: 520 });
    K.text(g, String(d.fp), W - 60, 280, { weight: 900, size: 88, color: C.good, align: "right" });
    K.text(g, "FANTASY PTS", W - 60, 318, { weight: 800, size: 22, color: C.dim, align: "right" });

    // 9 kategori
    const top = 400, bw = (W - 120 - 8 * 10) / 9, bh = 132;
    d.cats.forEach(([cat, v, sub, tier], i) => {
      const x = 60 + i * (bw + 10);
      K.rr(g, x, top, bw, bh, 16);
      g.fillStyle = tier === "good" ? "rgba(52,211,153,.14)" : tier === "bad" ? "rgba(239,100,100,.13)" : "rgba(255,255,255,.05)"; g.fill();
      g.lineWidth = 2; g.strokeStyle = tier === "good" ? "rgba(52,211,153,.6)" : tier === "bad" ? "rgba(239,100,100,.55)" : "rgba(255,255,255,.10)"; g.stroke();
      const cx = x + bw / 2;
      K.text(g, cat, cx, top + 34, { weight: 800, size: 20, color: C.muted, align: "center" });
      K.text(g, String(v), cx, top + 84, { weight: 900, size: String(v).length > 3 ? 32 : 40, align: "center",
                                          color: tier === "good" ? C.good : tier === "bad" ? C.bad : C.text });
      if (sub) K.text(g, String(sub), cx, top + 115, { weight: 600, size: 18, color: C.dim, align: "center" });
    });

    // Sut haritasi + bolgeler (sagda), aciklama haritanin altinda
    const cy0 = 560, cw = 770;
    const ch = court(g, 60, cy0, cw, d, C);
    const zx = 60 + cw + 20, zw = W - 60 - zx;
    const zones = Object.entries(d.zones), gap = 14;
    const zh = (ch - gap * (zones.length - 1)) / zones.length;
    zones.forEach(([z, [mk, at]], i) => {
      const y = cy0 + i * (zh + gap);
      K.rr(g, zx, y, zw, zh, 18); g.fillStyle = "rgba(255,255,255,.05)"; g.fill();
      K.text(g, z.toUpperCase(), zx + zw / 2, y + 46, { weight: 800, size: 21, color: C.muted, align: "center" });
      K.text(g, `${mk}/${at}`, zx + zw / 2, y + zh / 2 + 22, { weight: 900, size: 50, align: "center" });
      K.text(g, at ? `${Math.round((100 * mk) / at)}%` : "-", zx + zw / 2, y + zh - 30, { weight: 700, size: 26, color: C.dim, align: "center" });
    });
    const ly = cy0 + ch + 52;
    g.beginPath(); g.arc(72, ly - 9, 11, 0, Math.PI * 2); g.fillStyle = C.good; g.fill();
    K.text(g, `Made ${d.made}`, 94, ly, { weight: 700, size: 28, color: C.muted });
    K.text(g, "×", 268, ly + 2, { weight: 900, size: 40, color: C.bad });
    K.text(g, `Missed ${d.missed}`, 300, ly, { weight: 700, size: 28, color: C.muted });
    K.text(g, "Free throws not shown", W - 60, ly, { weight: 600, size: 24, color: C.dim, align: "right" });

    K.footer(g, "/nba/scores", "Every game's shot chart");
    return cv;
  }

  function shareText(d) {
    const line = d.cats.filter(([c]) => ["PTS", "REB", "AST", "STL", "BLK", "3PM"].includes(c) && Number(d.cats.find((x) => x[0] === c)[1]) > 0)
      .map(([c, v]) => `${v} ${c}`).slice(0, 5).join(", ");
    const m = d.meta || {};
    const when = m.date ? ` (${m.date})` : "";
    return `${d.name}: ${line}${when} - shot chart and fantasy line\n${location.origin}${d.page}?ref=player-card${window.HL.inv()}`;
  }

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-pc-share]");
    if (!btn) return;
    const el = btn.closest(".pc") && btn.closest(".pc").querySelector(".pc-data");
    if (!el) return;
    const d = JSON.parse(el.textContent);
    btn.classList.add("is-loading");
    try {
      const cv = await draw(d);
      const slug = d.name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
      await window.HLCard.share(cv, { filename: `${slug}-${(d.meta && d.meta.date || "game").replace(/[^A-Za-z0-9]+/g, "-")}.png`,
                                      text: shareText(d), title: `${d.name} game card` });
    } catch (err) {
      window.HL.toast("Could not build the image. Try again.", true);
    } finally {
      btn.classList.remove("is-loading");
    }
  });
})();
