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

  // ---------------- donem ortalamalari karti (son 7 / 15 / 30 gun) ----------------
  const CATS = [["PTS", "pts"], ["REB", "reb"], ["AST", "ast"], ["STL", "stl"], ["BLK", "blk"], ["3PM", "tpm"], ["FG%", "fg"], ["FT%", "ft"], ["TO", "to"]];
  const fmt = (v, k) => (v == null ? "-" : k === "fg" || k === "ft" ? `${v.toFixed(1)}` : v.toFixed(1));
  async function drawPeriod(d, key) {
    await needCard();
    const K = window.HLCard, { W, C } = K;
    const P = d.periods[key], B = d.periods[d.base] || null;
    const { cv, g } = await K.base("Player form");
    const img = await K.loadImg(d.photo);
    K.disc(g, img, 170, 270, 100, { ring: C.brand, ringW: 6, name: d.name });
    K.text(g, d.name, 300, 245, { weight: 900, size: 56, max: 520 });
    K.text(g, `${d.team}${d.pos ? " · " + d.pos : ""} · ${P.label.toUpperCase()}`, 300, 292, { weight: 800, size: 30, color: C.muted, max: 520 });
    K.text(g, `${P.gp} game${P.gp === 1 ? "" : "s"} · ${P.min.toFixed(1)} MIN${B ? ` · vs ${B.label.toLowerCase()}` : ""}`, 300, 336, { weight: 700, size: 27, color: C.dim, max: 520 });
    K.text(g, P.fp.toFixed(1), W - 60, 280, { weight: 900, size: 88, color: C.good, align: "right" });
    K.text(g, "FANTASY PTS / GAME", W - 60, 318, { weight: 800, size: 20, color: C.dim, align: "right" });

    // 9 kategori: deger + karsilastirma donemine gore fark (TO'da dusus iyi)
    const top = 400, bw = (W - 120 - 8 * 10) / 9, bh = 140;
    CATS.forEach(([cat, k], i) => {
      const v = P[k], b = B ? B[k] : null;
      const diff = v != null && b != null ? v - b : null;
      const better = diff == null ? 0 : (k === "to" ? -diff : diff);
      const thr = k === "fg" || k === "ft" ? 2 : k === "pts" ? 1.5 : 0.4;
      const tier = better >= thr ? "good" : better <= -thr ? "bad" : "";
      const x = 60 + i * (bw + 10);
      K.rr(g, x, top, bw, bh, 16);
      g.fillStyle = tier === "good" ? "rgba(52,211,153,.14)" : tier === "bad" ? "rgba(239,100,100,.13)" : "rgba(255,255,255,.05)"; g.fill();
      g.lineWidth = 2; g.strokeStyle = tier === "good" ? "rgba(52,211,153,.6)" : tier === "bad" ? "rgba(239,100,100,.55)" : "rgba(255,255,255,.10)"; g.stroke();
      const cx = x + bw / 2;
      K.text(g, cat, cx, top + 34, { weight: 800, size: 20, color: C.muted, align: "center" });
      const val = fmt(v, k);
      K.text(g, val, cx, top + 86, { weight: 900, size: val.length > 4 ? 30 : 38, align: "center", color: tier === "good" ? C.good : tier === "bad" ? C.bad : C.text });
      if (diff != null) K.text(g, `${diff > 0 ? "+" : ""}${diff.toFixed(1)}`, cx, top + 120, { weight: 700, size: 19, color: C.dim, align: "center" });
    });

    // Form tablosu: 7 / 15 / 30 gun ve karsilastirma donemi
    const keys = ["7", "15", "30", d.base].filter((k, i, arr) => d.periods[k] && arr.indexOf(k) === i);
    const cols = [["GP", "gp"], ["MIN", "min"], ["PTS", "pts"], ["REB", "reb"], ["AST", "ast"], ["STL", "stl"], ["BLK", "blk"], ["3PM", "tpm"], ["FP", "fp"]];
    const ty = 600, rowH = 84, lx = 60, labelW = 250, cw2 = (W - 120 - labelW) / cols.length;
    K.rr(g, 60, ty, W - 120, 70 + keys.length * rowH, 22); g.fillStyle = "rgba(255,255,255,.04)"; g.fill();
    cols.forEach(([c], j) => K.text(g, c, lx + labelW + cw2 * j + cw2 / 2, ty + 46, { weight: 800, size: 22, color: C.muted, align: "center" }));
    keys.forEach((k, i) => {
      const r = d.periods[k], y = ty + 70 + i * rowH, on = k === key;
      if (on) { K.rr(g, 70, y + 6, W - 140, rowH - 12, 16); g.fillStyle = "rgba(208,17,43,.22)"; g.fill(); }
      K.text(g, r.label, lx + 28, y + rowH / 2 + 10, { weight: on ? 900 : 700, size: 28, color: on ? C.text : C.muted });
      cols.forEach(([, f], j) => {
        const v = r[f];
        K.text(g, f === "gp" ? String(v) : Number(v).toFixed(1), lx + labelW + cw2 * j + cw2 / 2, y + rowH / 2 + 12,
               { weight: f === "fp" || on ? 900 : 700, size: 30, color: f === "fp" ? C.good : on ? C.text : C.muted, align: "center" });
      });
    });
    K.footer(g, d.page || "/rankings", "Recent form");
    return cv;
  }

  document.addEventListener("click", async (e) => {
    const pb = e.target.closest("[data-pp-share]");
    if (!pb) return;
    const box = pb.closest("[data-pid]");
    const key = pb.dataset.ppShare;
    pb.classList.add("is-loading");
    try {
      const d = await window.HL.api(`/api/player-period/${box.dataset.pid}`);
      if (!d.periods[key]) throw new Error(`No games for ${d.name} in that window.`);
      const P = d.periods[key];
      const cv = await drawPeriod(d, key);
      const text = `${d.name}, ${P.label.toLowerCase()} (${P.gp} game${P.gp === 1 ? "" : "s"}): ${P.pts.toFixed(1)} PTS, ${P.reb.toFixed(1)} REB, ${P.ast.toFixed(1)} AST, `
        + `${P.stl.toFixed(1)} STL, ${P.blk.toFixed(1)} BLK, ${P.tpm.toFixed(1)} 3PM
${location.origin}${d.page}?ref=player-form${window.HL.inv()}`;
      const slug = d.name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
      await window.HLCard.share(cv, { filename: `${slug}-last-${key}-days.png`, text, title: `${d.name} - ${P.label}` });
      if (window.gtag) gtag("event", "player_form_share", { window: key });
    } catch (err) {
      window.HL.toast(err.message || "Could not build the image. Try again.", true);
    } finally {
      pb.classList.remove("is-loading");
    }
  });

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
