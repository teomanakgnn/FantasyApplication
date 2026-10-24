// Pyramid: 10 oyuncuyu bir istatistige gore 1-2-3-4 piramide diz (tepe en cok).
// Dokun-yerlestir: oyuncuya dokun, sonra bir hucreye. Dolu hucreye dokunursan yer
// degistirirler; yerlesmis oyuncuya dokunup havuza dokunursan geri doner.
// Gunluk ilerleme bu cihazda; cevap sunucuda (/api/pyramid/check).
(function () {
  const { $, api, toast, escapeHtml: h } = window.HL;
  const data = JSON.parse($("#py-data").textContent);
  const root = $("#py-game");
  const KEY = "hl_pyr_game", STATS = "hl_pyr_stats";
  const ROWS = [1, 2, 3, 4];
  const photo = (id, w = 160) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=${w}&h=${Math.round(w * 0.727)}`;
  const last = (n) => n.split(" ").filter((w) => !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(w)).slice(-1)[0] || n;
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };

  let mode = "daily";
  let P = data;                                   // aktif bulmaca (gunluk ya da practice)
  let game = load(KEY, null);
  if (!game || game.puzzle !== data.puzzle) game = { puzzle: data.puzzle, slots: Array(10).fill(null), done: false, result: null };
  const stats = Object.assign({ played: 0, total: 0, best: 0, perfect: 0, last: 0, streak: 0 }, load(STATS, {}));
  let state = mode === "daily" ? game : null;
  let selected = null;                           // {from: "pool"|"slot", id, index}

  const byId = (id) => P.players.find((p) => p.id === id);
  const persist = () => { if (mode === "daily") save(KEY, game); };

  // ---------------- cizim ----------------
  function cell(i, id, mark, value) {
    const p = id ? byId(id) || (state.result && state.result.answer.find((a) => a.id === id)) : null;
    const sel = selected && selected.from === "slot" && selected.index === i;
    return `<button class="py-cell ${p ? "filled" : ""} ${mark || ""} ${sel ? "sel" : ""}" data-slot="${i}" ${state.done ? "disabled" : ""}>
      <span class="py-rank">${i + 1}</span>
      ${p ? `<img src="${photo(p.id)}" alt="" onerror="this.style.visibility='hidden'"><b>${h(last(p.name))}</b>${value !== undefined ? `<small>${value}</small>` : `<small>${h(p.team || "")}</small>`}` : `<em>${i === 0 ? "most" : i === 9 ? "least" : ""}</em>`}
    </button>`;
  }
  function pyramid(slots, marks, values) {
    let i = 0;
    return `<div class="py-pyr">${ROWS.map((n) => `<div class="py-row">${Array.from({ length: n }, () => { const k = i++; return cell(k, slots[k], marks && marks[k], values && values[k]); }).join("")}</div>`).join("")}</div>`;
  }

  function render() {
    const placed = new Set(state.slots.filter(Boolean));
    const pool = P.players.filter((p) => !placed.has(p.id));
    const head = `<div class="py-cat"><span>${mode === "daily" ? `Pyramid #${data.puzzle}` : "Practice"} · ${h(P.season)} season</span><b>${h(P.label)}</b></div>`;
    if (state.done && state.result) return renderResult(head);
    root.innerHTML = `${head}
      ${pyramid(state.slots)}
      <div class="py-pool" data-pool>${pool.map((p) => `
        <button class="py-chip ${selected && selected.from === "pool" && selected.id === p.id ? "sel" : ""}" data-pick="${p.id}">
          <img src="${photo(p.id, 96)}" alt="" onerror="this.style.visibility='hidden'"><span><b>${h(p.name)}</b><small>${h(p.team)}</small></span></button>`).join("")}
        ${pool.length ? "" : `<p class="dim small" style="margin:0">All ten placed. Tap two spots to swap them.</p>`}
      </div>
      <div class="py-actions">
        <button class="btn btn-primary" id="py-submit" ${placed.size === 10 ? "" : "disabled"}>Lock it in</button>
        <button class="btn btn-ghost" id="py-clear">Clear</button>
        ${mode === "daily" ? `<button class="btn btn-ghost" id="py-practice">Practice</button>` : `<button class="btn btn-ghost" id="py-daily">Back to today's</button>`}
      </div>`;
  }

  function renderResult(head) {
    const r = state.result;
    const truthValues = {};
    r.answer.forEach((a) => { truthValues[a.id] = a.value; });
    const yourValues = state.slots.map((id) => `${truthValues[id]} ${P.unit}`);
    const correctSlots = r.answer.map((a) => a.id);
    const correctValues = r.answer.map((a) => `${a.value}`);
    root.innerHTML = `${head}
      <div class="py-score"><b>${r.score}/10</b><span>in the right spot</span></div>
      <h3 class="py-h3">Your pyramid</h3>
      ${pyramid(state.slots, r.marks, yourValues)}
      <div class="py-legend small"><span class="hit">right spot</span><span class="near">one off</span><span class="miss">further</span></div>
      <h3 class="py-h3">Correct order</h3>
      ${pyramid(correctSlots, null, correctValues)}
      <div class="dp-actions">
        <button class="btn btn-primary" id="py-share">Share result</button>
        ${mode === "daily" ? `<button class="btn btn-ghost" id="py-practice">Play practice</button>` : `<button class="btn btn-ghost" id="py-practice">Another practice</button><button class="btn btn-ghost" id="py-daily">Back to today's</button>`}
      </div>
      ${mode === "daily" ? `<div class="dp-stats">
        <div><b>${stats.played}</b><span>Played</span></div>
        <div><b>${stats.played ? (stats.total / stats.played).toFixed(1) : "-"}</b><span>Avg</span></div>
        <div><b>${stats.best}</b><span>Best</span></div>
        <div><b>${stats.perfect}</b><span>Perfect</span></div>
      </div>
      <div class="small muted center dp-next" id="py-next"></div>` : ""}
      ${data.signed_in ? "" : `<div class="dp-keep"><div><b>Keep your streak</b><span>Free account: daily game streaks on every device.</span></div><a class="btn btn-sm" href="/register?next=/pyramid">Create account</a></div>`}`;
    if (mode === "daily") countdown();
  }

  // ---------------- etkilesim ----------------
  root.addEventListener("click", async (e) => {
    const t = e.target.closest("button, [data-pool]");
    if (!t || state.done && !t.id) return;
    if (t.dataset.pick) {                                         // havuzdaki oyuncu
      const id = t.dataset.pick;
      selected = selected && selected.from === "pool" && selected.id === id ? null : { from: "pool", id };
      // bos hucre varsa ilk bosa da konabilir: once secim, sonra hucre
      return render();
    }
    if (t.dataset.slot !== undefined) {
      const i = +t.dataset.slot, here = state.slots[i];
      if (selected && selected.from === "pool") {
        state.slots[i] = selected.id; selected = null;
      } else if (selected && selected.from === "slot") {
        if (selected.index !== i) { const j = selected.index; [state.slots[i], state.slots[j]] = [state.slots[j], state.slots[i]]; }
        selected = null;
      } else if (here) {
        selected = { from: "slot", id: here, index: i };
      } else {
        // bos hucreye dokunuldu, secim yok: havuzdaki ilk oyuncuyu koymak yerine ipucu
        toast("Tap a player first, then a spot.");
      }
      persist(); return render();
    }
    if (t.hasAttribute("data-pool") && selected && selected.from === "slot") {   // havuza geri
      state.slots[selected.index] = null; selected = null; persist(); return render();
    }
    if (t.id === "py-clear") { state.slots = Array(10).fill(null); selected = null; persist(); return render(); }
    if (t.id === "py-submit") return submit(t);
    if (t.id === "py-practice") return practice(t);
    if (t.id === "py-daily") { mode = "daily"; P = data; state = game; selected = null; return render(); }
    if (t.id === "py-share") return share();
  });

  async function submit(btn) {
    btn.classList.add("is-loading");
    try {
      const r = await api("/api/pyramid/check", { method: "POST", body: { seed: mode === "daily" ? "daily" : P.seed, order: state.slots } });
      state.result = r; state.done = true; selected = null;
      if (mode === "daily") {
        stats.played += 1; stats.total += r.score; stats.best = Math.max(stats.best, r.score);
        if (r.score === 10) stats.perfect += 1;
        stats.streak = stats.last === data.puzzle - 1 ? stats.streak + 1 : 1;
        stats.last = data.puzzle;
        save(STATS, stats); persist();
        if (window.gtag) gtag("event", "pyramid_finish", { score: r.score });
        if (data.signed_in) api("/api/streak", { method: "POST", body: { game: "pyramid", puzzle: data.puzzle } }).catch(() => {});
      }
      render();
    } catch (err) { toast(err.message, true); btn.classList.remove("is-loading"); }
  }

  async function practice(btn) {
    btn.classList.add("is-loading");
    try {
      const p = await api("/api/pyramid/practice");
      mode = "practice"; P = p; state = { slots: Array(10).fill(null), done: false, result: null }; selected = null;
      render(); root.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) { toast(err.message, true); btn.classList.remove("is-loading"); }
  }

  // ---------------- paylasim ----------------
  const SQ = { hit: "🟩", near: "🟨", miss: "⬛" };
  function shareText() {
    const m = state.result.marks;
    let i = 0;
    const grid = ROWS.map((n) => " ".repeat(4 - n) + Array.from({ length: n }, () => SQ[m[i++]]).join("")).join("\n");
    const title = mode === "daily" ? `HoopLife Pyramid #${data.puzzle}` : "HoopLife Pyramid (practice)";
    return `${title} · ${P.label} ${state.result.score}/10\n${grid}\n${location.origin}/pyramid?ref=pyramid-share${window.HL.inv()}`;
  }
  async function card() {
    const K = window.HLCard, { W, C } = K;
    const { cv, g } = await K.base("Pyramid", mode === "daily" ? data.puzzle : "");
    K.text(g, P.label, W / 2, 230, { weight: 900, size: 54, align: "center" });
    K.text(g, `${P.season} season · ${state.result.score}/10 in the right spot`, W / 2, 285, { weight: 700, size: 30, color: C.muted, align: "center" });
    const imgs = await Promise.all(state.slots.map((id) => K.loadImg(photo(id, 200))));
    const ring = { hit: C.good, near: C.gold, miss: "rgba(255,255,255,.25)" };
    let k = 0;
    ROWS.forEach((n, row) => {
      const y = 420 + row * 210, gap = 220, x0 = W / 2 - ((n - 1) * gap) / 2;
      for (let j = 0; j < n; j++, k++) {
        const p = byId(state.slots[k]) || {};
        K.disc(g, imgs[k], x0 + j * gap, y, 72, { ring: ring[state.result.marks[k]], ringW: 8, name: p.name || "" });
        K.pill(g, last(p.name || ""), x0 + j * gap, y + 92, { size: 24, h: 38 });
      }
    });
    K.footer(g, "/pyramid");
    return cv;
  }
  async function share() {
    const btn = $("#py-share");
    btn.classList.add("is-loading");
    try { await window.HLCard.share(await card(), { filename: `hooplife-pyramid-${data.puzzle}.png`, text: shareText(), title: "HoopLife Pyramid" }); }
    catch (err) { try { await navigator.clipboard.writeText(shareText()); toast("Result copied."); } catch (e) { toast(err.message, true); } }
    finally { btn.classList.remove("is-loading"); }
  }

  function countdown() {
    const el = $("#py-next");
    if (!el) return;
    let left = data.next_in;
    const tick = () => {
      if (!document.body.contains(el)) return;
      const hh = Math.floor(left / 3600), mm = Math.floor((left % 3600) / 60), ss = left % 60;
      el.textContent = `Next pyramid in ${hh}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
      if (left-- > 0) setTimeout(tick, 1000);
    };
    tick();
  }

  render();
})();
