// Ana sayfa: Top 10 / en kotu 10 fantezi listesi paylasim gorseli (1080x1350).
(function () {
  const B = window.HL_BOARD;
  if (!B || !window.HLCard) return;
  const K = window.HLCard, { W, H, C } = K;

  const num = (v, d) => (Math.round(v * 10 ** d) / 10 ** d).toFixed(d);

  function statLine(p) {
    const d = B.period === "today" ? 0 : 1;
    const parts = [`${num(p.pts, d)} PTS`, `${num(p.reb, d)} REB`, `${num(p.ast, d)} AST`];
    if (p.stl >= (d ? 1.5 : 2)) parts.push(`${num(p.stl, d)} STL`);
    if (p.blk >= (d ? 1.5 : 2)) parts.push(`${num(p.blk, d)} BLK`);
    if (p.tpm >= (d ? 2.5 : 3)) parts.push(`${num(p.tpm, d)} 3PM`);
    if (B.period === "today" && p.fga) parts.push(`${p.fgm}-${p.fga} FG`);
    if (p.to >= (d ? 3.5 : 5)) parts.push(`${num(p.to, d)} TO`);
    return parts.join(" · ");
  }

  async function draw(kind) {
    const list = (kind === "low" ? B.low : B.top).slice(0, 10);
    const low = kind === "low";
    const accent = low ? C.bad : C.good;
    const { cv, g } = await K.base(low ? "Worst 10" : "Top 10");

    // Baslik
    const when = B.period === "today" ? (B.day || "Last night") : `${B.label}${B.range ? " · " + B.range : ""}`;
    K.text(g, low ? "Worst fantasy nights" : "Best fantasy nights", 60, 212, { weight: 900, size: 58 });
    K.text(g, `${when}${B.period === "today" ? "" : " · per game"}${low ? " · 20+ min" : ""}`, 60, 262, { weight: 700, size: 30, color: C.muted });

    // Satirlar
    const top = 300, rowH = 92;
    const imgs = await Promise.all(list.map((p) => K.loadImg(p.photo)));
    list.forEach((p, i) => {
      const y = top + i * rowH;
      if (i % 2 === 0) { K.rr(g, 40, y, W - 80, rowH - 8, 18); g.fillStyle = "rgba(255,255,255,.045)"; g.fill(); }
      const cy = y + (rowH - 8) / 2;
      K.text(g, String(i + 1), 100, cy + 15, { weight: 900, size: 42, color: i < 3 ? (low ? C.bad : C.gold) : C.dim, align: "center" });
      K.disc(g, imgs[i], 186, cy, 34, { ring: i < 3 ? accent : "rgba(255,255,255,.25)", ringW: 4, name: p.player });
      K.text(g, p.player, 240, cy - 4, { weight: 800, size: 34, max: 560 });
      K.text(g, `${p.team} · ${statLine(p)}`, 240, cy + 32, { weight: 600, size: 23, color: C.muted, max: 610 });
      K.text(g, num(p.score, 1), W - 70, cy + 16, { weight: 900, size: 46, color: accent, align: "right" });
    });
    K.text(g, "FANTASY PTS", W - 70, top - 10, { weight: 800, size: 20, color: C.dim, align: "right" });

    K.footer(g, "/", low ? "Who let you down?" : "Who carried your team?");
    return cv;
  }

  function shareText(kind) {
    const list = (kind === "low" ? B.low : B.top).slice(0, 3);
    const when = B.period === "today" ? (B.day || "last night") : B.label.toLowerCase();
    const head = kind === "low" ? `Worst fantasy nights - ${when} 📉` : `Top fantasy performances - ${when} 🔥`;
    const lines = list.map((p, i) => `${i + 1}. ${p.player} ${num(p.score, 1)}`);
    return `${head}\n${lines.join("\n")}\n\nFull list: ${location.origin}/?ref=top10-share${window.HL.inv()}`;
  }

  // Yonetici: en kotu 10'u r/fantasybball'a hazir metin gonderisi olarak ac
  // (Reddit linkle resim eklemeye izin vermiyor; tablo + site linki).
  function redditPost(kind) {
    const low = kind === "low";
    const list = (low ? B.low : B.top).slice(0, 10);
    const d = B.period === "today" ? 0 : 1;
    const when = B.period === "today" ? (B.day || "last night") : `${B.label}${B.range ? " (" + B.range + ")" : ""}`;
    const title = low ? `Worst fantasy nights - ${when} (20+ min)` : `Best fantasy nights - ${when}`;
    const rows = list.map((p, i) => `| ${i + 1} | ${p.player} | ${p.team} | ${num(p.pts, d)} | ${num(p.reb, d)} | ${num(p.ast, d)} | ` +
      `${num(p.stl, d)} | ${num(p.blk, d)} | ${num(p.tpm, d)} | ${num(p.to, d)} | ${num(p.fgm, d)}-${num(p.fga, d)} | **${num(p.score, 1)}** |`);
    const body = [
      low ? `The ten worst fantasy lines${B.period === "today" ? "" : " (per game)"} among players with 20+ minutes:` :
            `The ten best fantasy lines${B.period === "today" ? "" : " (per game)"}:`,
      "",
      "| # | Player | Team | PTS | REB | AST | STL | BLK | 3PM | TO | FG | Score |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|",
      ...rows,
      "",
      "Score = HoopLife 9-cat weighted fantasy points (makes and misses count, turnovers cost).",
      "",
      `Full list, box scores and shot charts: ${location.origin}/?ref=reddit`,
    ].join("\n");
    const url = `https://www.reddit.com/r/fantasybball/submit?type=TEXT&title=${encodeURIComponent(title)}&text=${encodeURIComponent(body)}`;
    window.open(url, "_blank", "noopener");
  }

  document.addEventListener("click", (e) => {
    const rb = e.target.closest("[data-reddit-board]");
    if (!rb) return;
    e.stopPropagation();
    redditPost(rb.dataset.redditBoard);
  }, true);

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-share-board]");
    if (!btn) return;
    e.stopPropagation();
    const kind = btn.dataset.shareBoard;
    btn.classList.add("is-loading");
    try {
      const cv = await draw(kind);
      const stamp = (B.day || B.label).replace(/[^A-Za-z0-9]+/g, "-").toLowerCase();
      await K.share(cv, { filename: `hooplife-${kind === "low" ? "worst" : "top"}-10-${stamp}.png`, text: shareText(kind),
                          title: kind === "low" ? "Worst 10 fantasy nights" : "Top 10 fantasy nights" });
    } catch (err) {
      window.HL.toast("Could not build the image. Try again.", true);
    } finally {
      btn.classList.remove("is-loading");
    }
  }, true);
})();
