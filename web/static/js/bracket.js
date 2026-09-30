/*
 * Playoff tahmin agaci.
 * Paylasim linki (?b=...) yalnizca JSON olarak okunur; icindeki her deger
 * bilinen bir takim kisaltmasi degilse yok sayilir ve ekrana her zaman
 * kacirilmis metin olarak basilir. Eski surumdeki kod enjeksiyonu acigi
 * boylece kapanir.
 */
(function () {
  "use strict";
  const { toast, escapeHtml: h } = window.HL;
  const data = window.BRACKET;
  const KEY = "hl_bracket_" + data.year;
  const teams = {};
  data.east.concat(data.west).forEach((t) => (teams[t.abbr] = t));
  const valid = (abbr) => (typeof abbr === "string" && teams[abbr] ? abbr : null);

  const blank = () => ({ e: { r1: [null, null, null, null], r2: [null, null], cf: null },
                         w: { r1: [null, null, null, null], r2: [null, null], cf: null }, champ: null });

  function sanitize(raw) {
    const s = blank();
    if (!raw || typeof raw !== "object") return s;
    for (const conf of ["e", "w"]) {
      const c = raw[conf] || {};
      for (let i = 0; i < 4; i++) s[conf].r1[i] = valid((c.r1 || [])[i]);
      for (let i = 0; i < 2; i++) s[conf].r2[i] = valid((c.r2 || [])[i]);
      s[conf].cf = valid(c.cf);
    }
    s.champ = valid(raw.champ);
    // Zincir tutarli olmali: bir tur kazanani, onceki turun eslesmesinden gelmeli.
    const seedOf = { e: data.east.map((t) => t.abbr), w: data.west.map((t) => t.abbr) };
    const PAIRS = [[0, 7], [3, 4], [2, 5], [1, 6]];
    for (const conf of ["e", "w"]) {
      const c = s[conf];
      c.r1 = c.r1.map((abbr, i) => ([seedOf[conf][PAIRS[i][0]], seedOf[conf][PAIRS[i][1]]].includes(abbr) ? abbr : null));
      c.r2 = c.r2.map((abbr, i) => ([c.r1[i * 2], c.r1[i * 2 + 1]].includes(abbr) && abbr ? abbr : null));
      if (!c.cf || !c.r2.includes(c.cf)) c.cf = null;
    }
    if (!s.champ || ![s.e.cf, s.w.cf].includes(s.champ)) s.champ = null;
    return s;
  }

  function decode(text) {
    try {
      const b64 = text.replace(/-/g, "+").replace(/_/g, "/");
      return sanitize(JSON.parse(decodeURIComponent(escape(atob(b64)))));
    } catch (e) { return null; }
  }
  function encode(state) {
    return btoa(unescape(encodeURIComponent(JSON.stringify(state)))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  let state = blank();
  const shared = new URLSearchParams(location.search).get("b");
  if (shared && decode(shared)) {
    state = decode(shared);
    toast("Shared bracket loaded.");
  } else {
    try { state = sanitize(JSON.parse(localStorage.getItem(KEY) || "null")); } catch (e) { state = blank(); }
  }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} };

  const seeds = { e: data.east, w: data.west };
  const PAIRS = [[0, 7], [3, 4], [2, 5], [1, 6]];

  function matchup(conf, round, index) {
    const c = state[conf];
    if (round === 0) { const [a, b] = PAIRS[index]; return [seeds[conf][a], seeds[conf][b]].map((t) => t && t.abbr); }
    if (round === 1) return [c.r1[index * 2], c.r1[index * 2 + 1]];
    if (round === 2) return [c.r2[0], c.r2[1]];
    return [state.e.cf, state.w.cf];
  }
  function winner(conf, round, index) {
    if (round === 0) return state[conf].r1[index];
    if (round === 1) return state[conf].r2[index];
    if (round === 2) return state[conf].cf;
    return state.champ;
  }

  // Bir secim degisince onu kullanan sonraki turlar temizlenir
  function pick(conf, round, index, abbr) {
    const c = state[conf];
    if (round === 0) {
      c.r1[index] = abbr;
      const next = Math.floor(index / 2);
      if (c.r2[next] && !matchup(conf, 1, next).includes(c.r2[next])) c.r2[next] = null;
    }
    if (round <= 1) {
      if (round === 1) c.r2[index] = abbr;
      if (c.cf && !matchup(conf, 2, 0).includes(c.cf)) c.cf = null;
    }
    if (round <= 2) {
      if (round === 2) c.cf = abbr;
      if (state.champ && !matchup("", 3, 0).includes(state.champ)) state.champ = null;
    }
    if (round === 3) state.champ = abbr;
    save();
    draw();
  }

  function row(conf, round, index, abbr, chosen) {
    if (!abbr) return `<div class="br-team is-empty"><span class="br-seed">?</span><span>TBD</span></div>`;
    const t = teams[abbr];
    const cls = chosen ? (chosen === abbr ? " is-win" : " is-lose") : "";
    return `<button class="br-team${cls}" data-conf="${conf}" data-round="${round}" data-index="${index}" data-abbr="${h(abbr)}">
      <span class="br-seed">${t.seed}</span><span class="br-name">${h(t.short)}</span></button>`;
  }
  function series(conf, round, index) {
    const [a, b] = matchup(conf, round, index);
    const w = winner(conf, round, index);
    return `<div class="br-series">${row(conf, round, index, a, w)}${row(conf, round, index, b, w)}</div>`;
  }
  function confBlock(conf, label) {
    return `<section class="br-conf br-${conf}">
      <div class="br-label">${label}</div>
      <div class="br-rounds">
        <div class="br-round"><div class="br-rh">First round</div>${[0, 1, 2, 3].map((i) => series(conf, 0, i)).join("")}</div>
        <div class="br-round"><div class="br-rh">Semifinals</div>${[0, 1].map((i) => series(conf, 1, i)).join("")}</div>
        <div class="br-round"><div class="br-rh">Conference finals</div>${series(conf, 2, 0)}</div>
      </div></section>`;
  }
  function draw() {
    const champ = state.champ ? teams[state.champ] : null;
    document.getElementById("bracket").innerHTML = `
      <div id="br-capture" class="br-capture">
        <div class="br-title">${data.year} NBA Playoff Bracket <span>hooplifenba.com</span></div>
        ${confBlock("e", "Eastern Conference")}
        <section class="br-finals">
          <div class="br-rh">NBA Finals</div>
          ${state.e.cf && state.w.cf ? series("", 3, 0) : `<p class="small muted">Pick both conference champions to unlock the Finals.</p>`}
          ${champ ? `<div class="br-champ"><span>Your champion</span><b>${h(champ.name)}</b></div>` : ""}
        </section>
        ${confBlock("w", "Western Conference")}
      </div>`;
  }

  document.getElementById("bracket").addEventListener("click", (e) => {
    const b = e.target.closest(".br-team[data-abbr]");
    if (!b) return;
    pick(b.dataset.conf, +b.dataset.round, +b.dataset.index, valid(b.dataset.abbr));
  });
  document.getElementById("br-reset").addEventListener("click", () => {
    if (!confirm("Clear every pick?")) return;
    state = blank(); save(); draw();
    history.replaceState(null, "", location.pathname);
  });
  document.getElementById("br-share").addEventListener("click", async () => {
    const url = `${location.origin}${location.pathname}?b=${encode(state)}`;
    try {
      if (navigator.share) { await navigator.share({ title: "My NBA playoff bracket", url }); return; }
      await navigator.clipboard.writeText(url);
      toast("Link copied.");
    } catch (err) {
      if (err.name !== "AbortError") prompt("Copy this link:", url);
    }
  });
  document.getElementById("br-download").addEventListener("click", async () => {
    if (!window.html2canvas) { toast("Still loading - try again in a second.", true); return; }
    const el = document.getElementById("br-capture");
    el.classList.add("is-capturing");
    try {
      const canvas = await window.html2canvas(el, { scale: 2, backgroundColor: "#0B0F17" });
      const link = document.createElement("a");
      link.download = `nba-bracket-${data.year}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
    } catch (err) { toast("Download failed. Try again.", true); }
    finally { el.classList.remove("is-capturing"); }
  });
  draw();
})();
