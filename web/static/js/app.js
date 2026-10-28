/* HoopLife NBA - ortak istemci kodu (cekmece, pencere, tablo, sekme). */
(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ---------------- cekmece (mobil menu) ----------------
  const drawer = $("#drawer");
  const scrim = $("#scrim");
  const openBtn = $("#menu-open");
  function setDrawer(open) {
    if (!drawer) return;
    drawer.classList.toggle("is-open", open);
    scrim.hidden = !open;
    document.body.classList.toggle("no-scroll", open);
    if (openBtn) openBtn.setAttribute("aria-expanded", String(open));
  }
  openBtn && openBtn.addEventListener("click", () => setDrawer(true));
  $("#menu-close") && $("#menu-close").addEventListener("click", () => setDrawer(false));
  scrim && scrim.addEventListener("click", () => setDrawer(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setDrawer(false); });
  // Menudeki bir linke basinca yeni sayfa aciliyor; geri tusuyla donuste
  // tarayici sayfayi onbellekten getirirse menu acik kalmasin.
  window.addEventListener("pageshow", () => setDrawer(false));

  // ---------------- bildirim ----------------
  let toastTimer;
  function toast(message, isError) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = message;
    el.classList.toggle("is-error", !!isError);
    el.classList.add("is-on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("is-on"), 3200);
  }

  // ---------------- istek ----------------
  async function api(url, options = {}) {
    const opts = Object.assign({ headers: {} }, options);
    if (opts.body && typeof opts.body !== "string" && !(opts.body instanceof FormData)) {
      opts.body = JSON.stringify(opts.body);
      opts.headers["Content-Type"] = "application/json";
    }
    opts.credentials = "same-origin";
    let res;
    try {
      res = await fetch(url, opts);
    } catch (err) {
      throw new Error("Connection lost. Check your network and try again.");
    }
    const type = res.headers.get("content-type") || "";
    const data = type.includes("application/json") ? await res.json() : await res.text();
    if (!res.ok) {
      const message = (data && data.error) || (data && data.detail) || "Something went wrong.";
      const error = new Error(message);
      error.status = res.status;
      throw error;
    }
    return data;
  }

  // ---------------- pencere ----------------
  const modal = $("#modal");
  const modalBody = $("#modal-body");
  function openModal(html) {
    modalBody.innerHTML = html;
    if (!modal.open) modal.showModal();
    document.body.classList.add("no-scroll");
    modalBody.scrollTop = 0;
    hydrate(modalBody);
  }
  function closeModal() {
    if (modal.open) modal.close();
  }
  if (modal) {
    modal.addEventListener("close", () => { document.body.classList.remove("no-scroll"); modalBody.innerHTML = ""; });
    modal.addEventListener("click", (e) => {
      if (e.target === modal || e.target.closest("[data-close]")) closeModal();
    });
  }
  async function openModalUrl(url, options) {
    openModal('<div class="spinner"></div>');
    try {
      openModal(await api(url, options));
    } catch (err) {
      openModal(`<p class="bad">${escapeHtml(err.message)}</p>`);
    }
  }

  // ---------------- tablo siralama ----------------
  function sortTable(th) {
    const table = th.closest("table");
    const index = Array.from(th.parentNode.children).indexOf(th);
    const body = table.tBodies[0];
    const rows = Array.from(body.rows);
    // Ilk tiklama buyukten kucuge (skorlar icin dogal olan), sonraki
    // tiklamalar yon degistirir. Ad sutunlari data-first="asc" ile A-Z baslar.
    const dir = th.classList.contains("sorted-desc") ? 1 : th.classList.contains("sorted-asc") ? -1 : (th.dataset.first === "asc" ? 1 : -1);
    $$("th", th.parentNode).forEach((h) => h.classList.remove("sorted-asc", "sorted-desc"));
    th.classList.add(dir === 1 ? "sorted-asc" : "sorted-desc");
    const value = (row) => {
      const cell = row.cells[index];
      const raw = cell ? (cell.dataset.v !== undefined ? cell.dataset.v : cell.textContent.trim()) : "";
      const n = parseFloat(raw);
      return isNaN(n) ? raw.toLowerCase() : n;
    };
    rows.sort((a, b) => {
      const x = value(a), y = value(b);
      if (x < y) return -dir;
      if (x > y) return dir;
      return 0;
    });
    rows.forEach((r) => body.appendChild(r));
  }

  // ---------------- sekmeler ----------------
  function setupTabs(root) {
    $$("[data-tabs]", root).forEach((group) => {
      if (group.dataset.ready) return;
      group.dataset.ready = "1";
      const name = group.dataset.tabs;
      const tabs = $$(".tab", group);
      const panels = $$(`[data-panel-of="${name}"]`);
      function show(id, push) {
        tabs.forEach((t) => t.classList.toggle("is-on", t.dataset.tab === id));
        panels.forEach((p) => p.classList.toggle("is-on", p.dataset.panel === id));
        if (push && group.dataset.hash !== undefined) history.replaceState(null, "", "#" + id);
      }
      tabs.forEach((t) => t.addEventListener("click", () => show(t.dataset.tab, true)));
      const fromHash = location.hash.slice(1);
      const initial = tabs.find((t) => t.dataset.tab === fromHash) ? fromHash : (tabs[0] && tabs[0].dataset.tab);
      if (initial) show(initial, false);
    });
  }

  // ---------------- form yukleniyor durumu ----------------
  function setupForms(root) {
    $$("form[data-loading]", root).forEach((form) => {
      if (form.dataset.ready) return;
      form.dataset.ready = "1";
      form.addEventListener("submit", (e) => {
        // Butonun kendi onay sorusu (birden cok gonder butonu olan formlar)
        const ask = e.submitter && e.submitter.dataset.confirm;
        if (ask && !confirm(ask)) { e.preventDefault(); return; }
        const btn = e.submitter || form.querySelector("[type=submit]");
        if (btn) { btn.classList.add("is-loading"); btn.setAttribute("aria-busy", "true"); }
        const target = form.dataset.loading && document.getElementById(form.dataset.loading);
        if (target) target.hidden = false;
      });
    });
    $$("form[data-confirm]", root).forEach((form) => {
      if (form.dataset.confirmReady) return;
      form.dataset.confirmReady = "1";
      form.addEventListener("submit", (e) => { if (!confirm(form.dataset.confirm)) e.preventDefault(); });
    });
    $$("select[data-autosubmit], input[data-autosubmit]", root).forEach((el) => {
      if (el.dataset.ready) return;
      el.dataset.ready = "1";
      el.addEventListener("change", () => el.form && el.form.requestSubmit());
    });
  }

  function hydrate(root = document) {
    setupTabs(root);
    setupForms(root);
  }

  document.addEventListener("click", (e) => {
    const th = e.target.closest("th.sortable");
    if (th) { sortTable(th); return; }
    const opener = e.target.closest("[data-modal-url]");
    if (opener) { e.preventDefault(); openModalUrl(opener.dataset.modalUrl); }
  });

  // Izleme listesine ekle: data-watch="Oyuncu Adi" olan her buton
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-watch]");
    if (!btn) return;
    e.preventDefault();
    btn.disabled = true;
    try {
      const res = await api("/api/watchlist", { method: "POST", body: { player: btn.dataset.watch } });
      toast(res.message);
      btn.textContent = "On your watchlist";
    } catch (err) {
      toast(err.message, true);
      btn.disabled = false;
      if (err.status === 401) location.href = "/login?next=" + encodeURIComponent(location.pathname);
    }
  });

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  hydrate();
  // ---------------- uyelik karti ----------------
  // Uye olmayan ziyaretci bir sinira gelince (ikinci oyun, 3. tahmin, kutu
  // skorun devami...) gosterilir. Sunucu tarafindaki karsiligi partials/gate.html.
  function gate({ title, text, ref }) {
    const next = encodeURIComponent(location.pathname + location.search);
    const google = window.HL_GOOGLE ? `<a class="btn btn-google" href="/auth/google?next=${next}" rel="nofollow">Continue with Google</a>` : "";
    if (window.gtag) gtag("event", "gate_view", { gate: ref });
    return `<div class="gate card" data-gate="${escapeHtml(ref)}">
      <div class="gate-title">${escapeHtml(title)}</div>
      <p>${escapeHtml(text)}</p>
      <div class="gate-actions">${google}<a class="btn btn-primary" href="/register?next=${next}">Create free account</a>
        <a class="btn btn-ghost" href="/login?next=${next}">Sign in</a></div>
      <div class="tiny dim">Free forever. Keeps your streaks on every device.</div>
    </div>`;
  }

  const getJSON = (k) => { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } };

  // Bugun bu cihazda bitirilen gunluk oyunlar
  function gamesDone() {
    const P = window.HL_PUZZLES || {};
    const get = getJSON;
    return {
      daily: () => {
        const g = get("hl_daily_game"); if (g && g.puzzle === P.daily && g.done) return true;
        const n = window.HL_STREAKS && window.HL_STREAKS.daily_native; return !!(n && n.last === P.daily);
      },
      statmatch: () => { const g = get("hl_statmatch_game"); return !!(g && g.puzzle === P.statmatch && g.picks && g.picks.length >= (g.length || 10)); },
      starting5: () => { const g = get("hl_sf_game"); return !!(g && g.puzzle === P.starting5 && g.done); },
      pyramid: () => { const g = get("hl_pyr_game"); return !!(g && g.puzzle === P.pyramid && g.done); },
      grid: () => { const g = get("hl_grid_game"); return !!(g && g.puzzle === P.grid && g.done); },
      eightytwo: () => {
        try {
          for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            if (k && k.indexOf("hl_82_d") === 0) { const g = get(k); if (g && g.puzzle === P.eightytwo && g.done) return true; }
          }
        } catch (e) {}
        return false;
      },
    };
  }

  // Uye olmayan ziyaretci gunde bir oyun oynar; baska bir oyuna gecince uyelik karti
  function oneGameGate() {
    const games = { daily: "Mystery Player", statmatch: "Stat Match", starting5: "Starting Five", eightytwo: "82-0 Challenge", pyramid: "Pyramid", grid: "3x3 Grid" };
    const here = window.HL_ACTIVE;
    if (window.HL_USER || !games[here]) return;
    const done = gamesDone();
    const played = Object.keys(games).find((k) => k !== here && (window.HL_PUZZLES || {})[k] && done[k]());
    if (!played) return;
    const main = document.querySelector("#main");
    if (!main) return;
    const head = main.querySelector(".page-head");
    const box = document.createElement("div");
    box.innerHTML = gate({ title: `You played ${games[played]} today`,
      text: `Create a free account to play ${games[here]} and every other daily game - and keep all your streaks.`, ref: "second-game" });
    if (!head) {
      [...main.children].forEach((el) => { el.hidden = true; });
      main.prepend(box);
      return;
    }
    // Basliktan #main'e kadar her seviyede kardesleri gizle (oyun kapsayici icinde olabilir)
    for (let node = head; node && node !== main; node = node.parentElement) {
      [...node.parentElement.children].forEach((el) => { if (el !== node) el.hidden = true; });
    }
    head.querySelectorAll("p").forEach((el) => { el.hidden = true; });
    head.after(box);
  }

  // ---------------- gunluk oyun rozetleri ----------------
  // Bugunun oyunu bu cihazda oynanmadiysa menude "!" , bittiyse tik.
  function dailyBadges() {
    const P = window.HL_PUZZLES || {};
    const get = getJSON;
    const done = gamesDone();
    // Seri: cihazdaki kayit + (giris yaptiysa) sunucudaki kayit; Mystery
    // Player kendi istatistiginden (galibiyet serisi, sunucuyla esitleniyor).
    const SRV = window.HL_STREAKS || null;
    let streaks = get("hl_streaks") || {};
    let pending = 0, changed = false;
    // Oyunlarin kendi istatistiginden seri tahmini: oyunlar #1 ile basladi; oynanan
    // oyun sayisi son oynanan gunun numarasina esitse ilk gunden beri her gun oynanmis.
    const NATIVE = { statmatch: "hl_statmatch_stats", starting5: "hl_sf_stats", eightytwo: "hl_82_stats", pyramid: "hl_pyr_stats", grid: "hl_grid_stats" };
    function nativeSeed(key) {
      const st = get(NATIVE[key]); if (!st) return null;
      const last = parseInt(st.last, 10) || 0;
      if (!last || (last !== P[key] && last !== P[key] - 1)) return null;
      return (st.played || 0) >= last ? { last, streak: last } : { last, streak: 1 };
    }
    // Iki kaydi birlestir: ayni gun -> buyuk seri; ardisik gunler -> eskisinin uzerine devam
    const pick = (a, b) => {
      if (!a) return b; if (!b) return a;
      if (a.last === b.last) return a.streak >= b.streak ? a : b;
      const [hi, lo] = a.last > b.last ? [a, b] : [b, a];
      return hi.last === lo.last + 1 ? { last: hi.last, streak: Math.max(hi.streak, lo.streak + 1) } : hi;
    };
    Object.keys(done).forEach((key) => {
      if (!P[key]) return;
      const link = document.querySelector(`.nav-link[data-nav="${key}"]`);
      let ok = done[key]();
      let alive;
      if (key === "daily") {
        const native = pick(get("hl_daily_stats"), SRV && SRV.daily_native);
        alive = native && (native.lastWin === P.daily || native.lastWin === P.daily - 1) ? native.streak : 0;
      } else {
        let s = pick(pick(streaks[key], SRV && SRV[key]), nativeSeed(key)) || { last: 0, streak: 0 };
        if (ok && s.last !== P[key]) {
          const before = s.last === P[key] - 1 ? s.streak : 0;
          s = { last: P[key], streak: before + 1 };
          streaks[key] = s; changed = true;
          if (SRV) {
            SRV[key] = s;
            api("/api/streak", { method: "POST", body: { game: key, puzzle: P[key], seed: before } }).catch(() => {});
          }
        }
        alive = s.last === P[key] || s.last === P[key] - 1 ? s.streak : 0;
        // Bu cihaz daha uzun bir seri biliyorsa sunucuya da yaz (diger cihazlar gorsun)
        const srv = SRV && SRV[key];
        if (SRV && alive && (!srv || srv.last < s.last || (srv.last === s.last && srv.streak < s.streak))) {
          SRV[key] = { last: s.last, streak: s.streak };
          api("/api/streak", { method: "POST", body: { game: key, sync: true, last: s.last, streak: s.streak } }).catch(() => {});
        }
        if (s.last === P[key]) ok = true;      // baska cihazda bugun oynandi
      }
      if (!ok) pending++;
      if (!link) return;
      let b = link.querySelector(".nav-badge");
      if (!b) { b = document.createElement("span"); link.appendChild(b); }
      b.className = "nav-badge " + (ok ? "lit" : "cold");
      b.innerHTML = `<i>🔥</i>${alive ? `<b>${alive}</b>` : ""}`;
      b.title = ok ? `Played today · ${alive}-day streak` : alive ? `Play today to keep your ${alive}-day streak` : "Play today to start a streak";
    });
    if (changed) { try { localStorage.setItem("hl_streaks", JSON.stringify(streaks)); } catch (e) {} }
    const burger = document.getElementById("menu-open");
    if (burger) burger.classList.toggle("has-todo", pending > 0);
  }
  dailyBadges();
  oneGameGate();
  window.addEventListener("storage", dailyBadges);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) dailyBadges(); });
  setInterval(dailyBadges, 5000);

  // Paylasim linklerine paylasanin davet kodu: linkle gelen uye olursa ikisi de Pro kazanir
  const inv = () => (window.HL_INV ? `&inv=${window.HL_INV}` : "");
  // ---------------- ana ekrana ekle (PWA) ----------------
  // Android / Chrome / Edge: tarayicinin kendi kurulum penceresi (tek dokunus).
  // iPhone / iPad: Apple programla kuruluma izin vermiyor; adim adim yol gosterilir.
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  let deferredInstall = null;
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const ua = navigator.userAgent;
  const ios = /iphone|ipad|ipod/i.test(ua) || (ua.includes("Macintosh") && navigator.maxTouchPoints > 1);
  const inApp = /FBAN|FBAV|Instagram|Line\/|Twitter|TikTok|Snapchat/i.test(ua);
  const dismissed = () => { try { return +localStorage.getItem("hl_install_x") > Date.now(); } catch (e) { return false; } };
  function showInstall(on) {
    $$("[data-install]").forEach((b) => { b.hidden = !on; });
    const card = $("#install-card");
    if (card) card.hidden = !on || dismissed();
  }
  if (!standalone) {
    window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferredInstall = e; showInstall(true); });
    if (ios) showInstall(true);
  }
  window.addEventListener("appinstalled", () => { showInstall(false); if (window.gtag) gtag("event", "pwa_installed"); });
  const shareIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-3px"><path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/></svg>';
  document.addEventListener("click", async (e) => {
    if (e.target.closest("[data-install-dismiss]")) {
      try { localStorage.setItem("hl_install_x", String(Date.now() + 14 * 864e5)); } catch (err) { /* yok */ }
      const card = $("#install-card"); if (card) card.hidden = true;
      return;
    }
    if (!e.target.closest("[data-install]")) return;
    if (window.gtag) gtag("event", "pwa_install_click", { ios });
    if (deferredInstall) {
      deferredInstall.prompt();
      const choice = await deferredInstall.userChoice.catch(() => null);
      deferredInstall = null;
      if (choice && choice.outcome === "accepted") showInstall(false);
      return;
    }
    openModal(inApp ? `
      <div class="install-steps"><h2>Open in Safari first</h2>
        <p>This app's browser can't add sites to your home screen. Tap <b>•••</b> and choose <b>Open in Safari</b> (or Chrome), then tap <b>Add to Home Screen</b> again.</p></div>` : ios ? `
      <div class="install-steps"><h2>Add HoopLife to your home screen</h2>
        <ol>
          <li>Tap the <b>Share</b> button ${shareIcon} at the bottom of Safari (top right on iPad).</li>
          <li>Scroll down and tap <b>Add to Home Screen</b>.</li>
          <li>Tap <b>Add</b>. HoopLife opens like an app from your home screen.</li>
        </ol></div>` : `
      <div class="install-steps"><h2>Add HoopLife to your device</h2>
        <p>Open your browser menu (<b>⋮</b> or <b>•••</b>) and choose <b>Install app</b> or <b>Add to Home Screen</b>.</p></div>`);
  });

  window.HL = { $, $$, api, toast, openModal, openModalUrl, closeModal, escapeHtml, hydrate, inv, gate };
})();
