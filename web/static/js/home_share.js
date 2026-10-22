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
    const head = kind === "low" ? `Worst fantasy nights - ${when}` : `Top fantasy performances - ${when}`;
    const lines = list.map((p, i) => `${i + 1}. ${p.player} ${num(p.score, 1)}`);
    return `${head}\n${lines.join("\n")}\n\nFull list: ${location.origin}/?ref=top10-share${window.HL.inv()}`;
  }

  // Yonetici: listeyi r/fantasybball'in "Player Discussion" bicimiyle hazir
  // tablo gonderisi olarak acar (Reddit linkle resim eklemeye izin vermiyor).
  const espnScore = (p) => p.pts + p.tpm + 2 * p.fgm - p.fga + p.ftm - p.fta + p.reb + 2 * p.ast + 4 * p.stl + 4 * p.blk - 2 * p.to;

  function longDate() {
    if (!B.date) return B.label;
    const d = new Date(B.date + "T12:00:00");
    const n = d.getDate(), sfx = (n % 100 >= 11 && n % 100 <= 13) ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th");
    return `${d.toLocaleDateString("en-US", { month: "long" })} ${n}${sfx}, ${d.getFullYear()}`;
  }

  // Ust liste: buyuk sayilara alev; alt liste: kotu sayilara buz / kafatasi
  function hot(v, cat) {
    const t = { pts: [30, 40], reb: [12, 15], ast: [10, 13], stl: [3, 5], blk: [3, 5], tpm: [5, 8] }[cat];
    if (!t || v < t[0]) return "";
    if (cat === "tpm" && v >= t[1]) return "🚀🔥";
    return v >= t[1] ? "🔥🔥" : "🔥";
  }

  function redditPost(kind) {
    const low = kind === "low";
    const list = (low ? B.low : B.top).slice(0, 10);
    const avg = B.period !== "today";
    const f = (v) => (avg ? num(v, 1) : String(Math.round(v)));
    const when = avg ? `${B.label}${B.range ? " (" + B.range + ")" : ""}` : longDate();
    const star = list[0] ? list[0].player : "";
    const title = low ? `🧊 📉 Bottom 10 Player Discussion - ${star} Night 📉 🧊 - ${when}`
                      : `🔥 🚀 Top 10 Player Discussion - ${star} Night 🚀 🔥 - ${when}`;
    const rows = list.map((p, i) => {
      const fgBad = low && p.fga >= 8 && p.fgm / p.fga < 0.3 ? " 🧊" : "";
      const toBad = low && p.to >= 5 ? " 💀" : "";
      const ptsBad = low && p.pts <= 4 ? " 🧊" : "";
      const ftBad = low && p.fta - p.ftm >= 3 ? " 🧱" : "";
      const h = (v, c) => (low ? "" : hot(v, c));
      return `| ${i + 1} | ${p.player} | ${p.pos || "-"} | ${f(p.min)} mins | ${f(p.fgm)}-${f(p.fga)}${fgBad} | ${f(p.ftm)}-${f(p.fta)}${ftBad} | ` +
        `${f(p.tpm)}${h(p.tpm, "tpm")} | ${f(p.reb)}${h(p.reb, "reb")} | ${f(p.ast)}${h(p.ast, "ast")} | ${f(p.stl)}${h(p.stl, "stl")} | ` +
        `${f(p.blk)}${h(p.blk, "blk")} | ${f(p.to)}${toBad} | ${f(p.pts)}${h(p.pts, "pts")}${ptsBad} | ${num(p.score, 1)} | ${f(espnScore(p))} |`;
    });
    const body = [
      `Hello r/fantasybball! Here are the ${low ? "bottom" : "top"} 10 performing players for ${when}${low ? " (20+ minutes)" : ""}${avg ? ", per game" : ""}!`,
      "",
      "| Rank | Player | Pos | Time | FG | FT | 3PT | REB | AST | STL | BLK | TOV | PTS | Night Score | ESPN Score |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
      ...rows,
      "",
      "Night Score = 9-cat weighted value (makes and misses count, turnovers cost). ESPN Score = ESPN standard points scoring.",
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
