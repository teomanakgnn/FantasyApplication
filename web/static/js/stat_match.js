// Stat Match: iki oyuncu, iki istatistik satiri. Gunluk tur bu cihazda
// saklanir; bitince pratik turlari acilir.
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
  if (!game || game.puzzle !== data.puzzle) game = { puzzle: data.puzzle, picks: [] };
  const stats = Object.assign({ played: 0, best: 0, total: 0, last: 0 }, load(STATS, {}));
  // mode: "daily" ya da "practice"
  let mode = "daily", rounds = data.rounds, picks = game.picks;

  const score = (arr, rs) => arr.filter((p, i) => p === rs[i].answer).length;

  function statLine(line, idx, r, chosen) {
    let cls = "";
    if (chosen !== undefined) {
      const owner = idx === r.answer ? 0 : 1;   // bu satir kimin
      cls = owner === 0 ? "is-left" : "is-right";
      if (idx === chosen) cls += chosen === r.answer ? " is-right-pick" : " is-wrong-pick";
    }
    const owner = chosen !== undefined ? r.players[idx === r.answer ? 0 : 1] : null;
    return `<button class="sm-line ${cls}" data-line="${idx}" ${chosen !== undefined ? "disabled" : ""}>
      <span class="sm-line-tag">${owner ? h(owner.name) : `Line ${idx === 0 ? "A" : "B"}`}</span>
      <span class="sm-stats">${ORDER.map((k) => `<span><b>${line[k] !== undefined ? line[k].toFixed(1) : "-"}</b><i>${k}</i></span>`).join("")}</span>
    </button>`;
  }

  function render() {
    const i = picks.length;
    if (i >= rounds.length) return finish();
    const r = rounds[i];
    root.innerHTML = `
      <div class="sm-top"><span class="chip">${mode === "practice" ? "Practice" : "Round"} ${i + 1} / ${rounds.length}</span>
        <span class="sm-dots">${rounds.map((x, j) => `<i class="${j < i ? (picks[j] === rounds[j].answer ? "ok" : "no") : j === i ? "now" : ""}"></i>`).join("")}</span></div>
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
       <button class="btn btn-primary btn-block" id="sm-next">${picks.length >= rounds.length ? "See result" : "Next round"}</button>`;
    root.querySelectorAll(".sm-dots i")[i].className = ok ? "ok" : "no";
    $("#sm-next").focus();
  }

  root.addEventListener("click", (e) => {
    const line = e.target.closest("[data-line]");
    if (line && !line.disabled) return reveal(+line.dataset.line);
    if (e.target.closest("#sm-next")) return render();
    if (e.target.closest("#sm-share")) return share();
    if (e.target.closest("#sm-practice")) return practice();
  });

  function grid(arr, rs) { return arr.map((p, i) => (p === rs[i].answer ? "🟩" : "🟥")).join(""); }

  async function share() {
    const s = score(game.picks, data.rounds);
    const text = `HoopLife Stat Match #${data.puzzle} ${s}/${data.rounds.length}\n${grid(game.picks, data.rounds)}\n${location.origin}/stat-match?ref=statmatch-share`;
    if (window.gtag) gtag("event", "statmatch_share");
    if (navigator.share && matchMedia("(pointer: coarse)").matches) {
      try { await navigator.share({ text }); return; } catch (err) { if (err.name === "AbortError") return; }
    }
    try { await navigator.clipboard.writeText(text); toast("Result copied - paste it anywhere."); }
    catch (err) { window.prompt("Copy your result:", text); }
  }

  async function practice() {
    try {
      const res = await api("/api/stat-match/practice");
      mode = "practice"; rounds = res.rounds; picks = [];
      render(); window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) { toast(err.message, true); }
  }

  function finish() {
    if (mode === "practice") {
      const s = score(picks, rounds);
      root.innerHTML = `<div class="card sm-result"><div class="eyebrow">Practice</div><h2>${s} / ${rounds.length}</h2>
        <div class="sm-grid">${grid(picks, rounds)}</div>
        <div class="dp-actions"><button class="btn btn-primary" id="sm-practice">Another practice round</button><a class="btn btn-ghost" href="/mock-draft">Run a mock draft</a></div></div>`;
      return;
    }
    const s = score(game.picks, data.rounds);
    if (stats.last !== data.puzzle) {
      stats.last = data.puzzle; stats.played += 1; stats.total += s; stats.best = Math.max(stats.best, s);
      save(STATS, stats);
      if (window.gtag) gtag("event", "statmatch_finish", { score: s });
    }
    const avg = stats.played ? (stats.total / stats.played).toFixed(1) : "-";
    root.innerHTML = `
      <div class="card sm-result">
        <div class="eyebrow">Stat Match #${data.puzzle}</div>
        <h2>${s} / ${data.rounds.length}</h2>
        <div class="sm-grid">${grid(game.picks, data.rounds)}</div>
        <div class="dp-actions">
          <button class="btn btn-primary" id="sm-share" type="button">Share result</button>
          <button class="btn" id="sm-practice" type="button">Practice round</button>
        </div>
        <div class="dp-stats"><div><b>${stats.played}</b><span>Played</span></div><div><b>${avg}</b><span>Average</span></div><div><b>${stats.best}</b><span>Best</span></div></div>
        <p class="small muted" style="margin-top:12px">New pairs every day at midnight UK time. Also try <a href="/daily">Mystery Player</a>.</p>
        ${data.signed_in ? "" : `<div class="dp-keep"><div><b>Track your scores</b><span>Free account: save mock drafts, keep your Mystery Player streak on every device.</span></div>
          <a class="btn btn-primary btn-sm" href="/register?next=%2Fstat-match">Create free account</a></div>`}
      </div>`;
  }

  render();
})();
