// Stat Match: iki oyuncu, iki istatistik satiri. Gunluk tur 5 ya da 10
// tur; skor her an paylasilabilir. Ilerleme bu cihazda saklanir.
(function () {
  const { $, api, toast, escapeHtml: h } = window.HL;
  const data = JSON.parse($("#sm-data").textContent);
  const root = $("#sm-game");
  const KEY = "hl_statmatch_game", STATS = "hl_statmatch_stats";
  const ORDER = ["PTS", "REB", "AST", "STL", "BLK", "3PM", "FG%", "FT%"];
  const photo = (id) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=220&h=160`;
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };

  let game = load(KEY, null);
  if (!game || game.puzzle !== data.puzzle) game = { puzzle: data.puzzle, picks: [], length: 0 };
  if (!game.length && game.picks.length) game.length = 10;      // eski kayit
  const stats = Object.assign({ played: 0, best: 0, total: 0, last: 0 }, load(STATS, {}));
  // mode: "daily" ya da "practice"
  let mode = "daily", rounds = data.rounds, picks = game.picks;
  const total = () => (mode === "daily" ? Math.min(game.length || 10, data.rounds.length) : rounds.length);
  const score = (arr, rs) => arr.filter((p, i) => p === rs[i].answer).length;
  const grid = (arr, rs) => arr.map((p, i) => (p === rs[i].answer ? "🟩" : "🟥")).join("");

  function statLine(line, idx, r, chosen) {
    let cls = "";
    if (chosen !== undefined) {
      cls = idx === r.answer ? "is-left" : "is-right";
      if (idx === chosen) cls += chosen === r.answer ? " is-right-pick" : " is-wrong-pick";
    }
    const owner = chosen !== undefined ? r.players[idx === r.answer ? 0 : 1] : null;
    return `<button class="sm-line ${cls}" data-line="${idx}" ${chosen !== undefined ? "disabled" : ""}>
      <span class="sm-line-tag">${owner ? h(owner.name) : `Line ${idx === 0 ? "A" : "B"}`}</span>
      <span class="sm-stats">${ORDER.map((k) => `<span><b>${line[k] !== undefined ? line[k].toFixed(1) : "-"}</b><i>${k}</i></span>`).join("")}</span>
    </button>`;
  }

  function chooser() {
    root.innerHTML = `
      <div class="card sm-choose">
        <div class="card-title">How many rounds?</div>
        <div class="sm-choose-row">
          <button class="btn btn-primary" data-len="5"><b>Quick</b><span>5 rounds</span></button>
          <button class="btn" data-len="10"><b>Full</b><span>10 rounds</span></button>
        </div>
        <p class="tiny dim" style="margin:10px 0 0">Share your score at any point. Pick Quick and you can play the other 5 later.</p>
      </div>`;
  }

  function shareLabel() { return `Share ${score(picks, rounds)}/${picks.length}`; }

  function render() {
    if (mode === "daily" && !game.length) return chooser();
    const i = picks.length;
    if (i >= total()) return finish();
    const r = rounds[i];
    root.innerHTML = `
      <div class="sm-top"><span class="chip">${mode === "practice" ? "Practice" : "Round"} ${i + 1} / ${total()}</span>
        ${i > 0 ? `<button class="btn btn-sm btn-ghost sm-share-mini" id="sm-share" type="button">${shareLabel()}</button>` : ""}
        <span class="sm-dots">${rounds.slice(0, total()).map((x, j) => `<i class="${j < i ? (picks[j] === rounds[j].answer ? "ok" : "no") : j === i ? "now" : ""}"></i>`).join("")}</span></div>
      <div class="sm-players">
        ${r.players.map((p, side) => `
          <div class="sm-player ${side === 0 ? "left" : "right"}">
            <img src="${photo(p.id)}" alt="" loading="eager" onerror="this.style.visibility='hidden'">
            <b>${h(p.name)}</b><span>${h(p.team)} · ${h(p.pos)}</span>
            ${side === 0 ? '<em class="sm-target">Find his line</em>' : ""}
          </div>`).join('<div class="sm-vs">VS</div>')}
      </div>
      <div class="sm-lines">${r.lines.map((l, idx) => statLine(l, idx, r)).join("")}</div>
      <p class="tiny dim center" style="margin-top:10px">2025-26 per-game averages.</p>`;
  }

  function reveal(chosen) {
    const i = picks.length;
    const r = rounds[i];
    picks.push(chosen);
    if (mode === "daily") { game.picks = picks; save(KEY, game); }
    const ok = chosen === r.answer;
    root.querySelector(".sm-lines").innerHTML = r.lines.map((l, idx) => statLine(l, idx, r, chosen)).join("") +
      `<div class="sm-verdict ${ok ? "good" : "bad"}">${ok ? "Correct!" : "Not this time."}</div>
       <div class="sm-next-row">
         <button class="btn btn-primary" id="sm-next">${picks.length >= total() ? "See result" : "Next round"}</button>
         <button class="btn" id="sm-share" type="button">${shareLabel()}</button>
       </div>`;
    root.querySelectorAll(".sm-dots i")[i].className = ok ? "ok" : "no";
    const mini = root.querySelector(".sm-share-mini");
    if (mini) mini.remove();
    $("#sm-next").focus();
  }

  root.addEventListener("click", (e) => {
    const line = e.target.closest("[data-line]");
    if (line && !line.disabled) return reveal(+line.dataset.line);
    const len = e.target.closest("[data-len]");
    if (len) { game.length = +len.dataset.len; save(KEY, game); return render(); }
    if (e.target.closest("#sm-next")) return render();
    if (e.target.closest("#sm-share")) return share();
    if (e.target.closest("#sm-practice")) return practice();
    if (e.target.closest("#sm-more")) {
      mode = "daily"; rounds = data.rounds; picks = game.picks; game.length = data.rounds.length; save(KEY, game);
      return render();
    }
  });

  async function share() {
    const done = picks.length, sc = score(picks, rounds);
    const head = mode === "practice" ? "HoopLife Stat Match" : `HoopLife Stat Match #${data.puzzle}`;
    const text = `${head}: ${sc}/${done}${done < total() ? ` after ${done} of ${total()}` : ""}. Which stat line is whose? ${location.origin}/stat-match?ref=statmatch-share${window.HL.inv()}`;
    if (window.gtag) gtag("event", "statmatch_share", { done });
    try { await HLCard.share(await card(), { filename: "stat-match.png", text, title: "Stat Match" }); }
    catch (err) { toast("Could not create the image.", true); }
  }

  // Spoiler'siz: bugunun eslesmeleri yok, yalnizca skor ve tur tur sonuc.
  async function card() {
    const K = HLCard, done = picks.length, sc = score(picks, rounds), n = total();
    const { cv, g } = await K.base("STAT MATCH", mode === "daily" ? data.puzzle : "");
    const pct = done ? sc / done : 0;
    const title = done < n ? "IN PROGRESS" : pct === 1 ? "PERFECT" : pct >= .8 ? "STAT GENIUS" : pct >= .6 ? "BALL KNOWER" : pct >= .4 ? "COIN FLIPPER" : "CHECK THE BOX SCORE";
    K.text(g, `${sc}/${done}`, K.W / 2, 400, { weight: 900, size: 230, align: "center", color: pct === 1 && done === n ? K.C.gold : "#fff" });
    K.pill(g, title, K.W / 2, 470, { bg: pct === 1 && done === n ? K.C.gold : "rgba(255,255,255,.12)", color: pct === 1 && done === n ? "#1B1300" : "#fff", size: 30, h: 56, padX: 26 });
    K.text(g, done < n ? `after ${done} of ${n} rounds` : `${n} rounds · ${Math.round(pct * 100)}% correct`, K.W / 2, 545, { weight: 700, size: 30, color: K.C.muted, align: "center" });

    // Tur kutulari: ust uste iki sira
    const cols = 5, size = 150, gap = 26, rows = Math.ceil(n / cols);
    const x0 = (K.W - (cols * size + (cols - 1) * gap)) / 2, y0 = 620;
    for (let k = 0; k < n; k++) {
      const x = x0 + (k % cols) * (size + gap), y = y0 + Math.floor(k / cols) * (size + gap);
      const has = k < done, ok = has && picks[k] === rounds[k].answer;
      K.rr(g, x, y, size, size, 26);
      g.fillStyle = !has ? "rgba(255,255,255,.06)" : ok ? K.C.good : K.C.bad; g.fill();
      if (!has) { g.lineWidth = 3; g.strokeStyle = "rgba(255,255,255,.14)"; g.stroke(); }
      K.text(g, has ? (ok ? "✓" : "✗") : String(k + 1), x + size / 2, y + size / 2 + 24, { weight: 900, size: has ? 76 : 44, align: "center", color: has ? "#0B0F17" : K.C.dim });
    }
    const yb = y0 + rows * (size + gap) + 30;
    K.text(g, "Two players. Two stat lines. Which is whose?", K.W / 2, yb + 30, { weight: 700, size: 32, color: K.C.muted, align: "center" });
    K.footer(g, "/stat-match");
    return cv;
  }

  async function practice() {
    try {
      const res = await api("/api/stat-match/practice");
      mode = "practice"; rounds = res.rounds.slice(0, game.length || 10); picks = [];
      render(); window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) { toast(err.message, true); }
  }

  function finish() {
    if (mode === "practice") {
      const s = score(picks, rounds);
      root.innerHTML = `<div class="card sm-result"><div class="eyebrow">Practice</div><h2>${s} / ${rounds.length}</h2>
        <div class="sm-grid">${grid(picks, rounds)}</div>
        <div class="dp-actions"><button class="btn btn-primary" id="sm-share" type="button">Share result</button>
          <button class="btn" id="sm-practice" type="button">Another practice round</button></div></div>`;
      return;
    }
    const n = total(), s = score(game.picks.slice(0, n), data.rounds);
    // Istatistik tam gunluk turda (10) tutulur; 5'lik tur sonra tamamlanabilir.
    if (stats.last !== data.puzzle && n >= data.rounds.length) {
      stats.last = data.puzzle; stats.played += 1; stats.total += s; stats.best = Math.max(stats.best, s);
      save(STATS, stats);
      if (window.gtag) gtag("event", "statmatch_finish", { score: s });
    }
    const avg = stats.played ? (stats.total / stats.played).toFixed(1) : "-";
    const more = data.rounds.length - n;
    root.innerHTML = `
      <div class="card sm-result">
        <div class="eyebrow">Stat Match #${data.puzzle}</div>
        <h2>${s} / ${n}</h2>
        <div class="sm-grid">${grid(game.picks.slice(0, n), data.rounds)}</div>
        <div class="dp-actions">
          <button class="btn btn-primary" id="sm-share" type="button">Share result</button>
          ${more > 0 ? `<button class="btn" id="sm-more" type="button">Play ${more} more</button>` : ""}
          <button class="btn ${more > 0 ? "btn-ghost" : ""}" id="sm-practice" type="button">Practice round</button>
        </div>
        <div class="dp-stats"><div><b>${stats.played}</b><span>Full games</span></div><div><b>${avg}</b><span>Average</span></div><div><b>${stats.best}</b><span>Best</span></div></div>
        <p class="small muted" style="margin-top:12px">New pairs every day at midnight UK time. Also try <a href="/daily">Mystery Player</a>.</p>
        ${data.signed_in ? "" : `<div class="dp-keep"><div><b>Track your scores</b><span>Free account: keep your daily game streaks on every device and track players.</span></div>
          <a class="btn btn-primary btn-sm" href="/register?next=%2Fstat-match">Create free account</a></div>`}
      </div>`;
  }

  render();
})();
