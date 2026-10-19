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
  // ---------------- gunluk oyun rozetleri ----------------
  // Bugunun oyunu bu cihazda oynanmadiysa menude "!" , bittiyse tik.
  function dailyBadges() {
    const P = window.HL_PUZZLES || {};
    const get = (k) => { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } };
    const done = {
      daily: () => {
        const g = get("hl_daily_game"); if (g && g.puzzle === P.daily && g.done) return true;
        const n = window.HL_STREAKS && window.HL_STREAKS.daily_native; return !!(n && n.last === P.daily);
      },
      statmatch: () => { const g = get("hl_statmatch_game"); return !!(g && g.puzzle === P.statmatch && g.picks && g.picks.length >= (g.length || 10)); },
      starting5: () => { const g = get("hl_sf_game"); return !!(g && g.puzzle === P.starting5 && g.done); },
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
    // Seri: cihazdaki kayit + (giris yaptiysa) sunucudaki kayit; Mystery
    // Player kendi istatistiginden (galibiyet serisi, sunucuyla esitleniyor).
    const SRV = window.HL_STREAKS || null;
    let streaks = get("hl_streaks") || {};
    let pending = 0, changed = false;
    const pick = (a, b) => (!a ? b : !b ? a : (b.last > a.last || (b.last === a.last && b.streak > a.streak)) ? b : a);
    Object.keys(done).forEach((key) => {
      if (!P[key]) return;
      const link = document.querySelector(`.nav-link[data-nav="${key}"]`);
      let ok = done[key]();
      let alive;
      if (key === "daily") {
        const native = pick(get("hl_daily_stats"), SRV && SRV.daily_native);
        alive = native && (native.lastWin === P.daily || native.lastWin === P.daily - 1) ? native.streak : 0;
      } else {
        let s = pick(streaks[key], SRV && SRV[key]) || { last: 0, streak: 0 };
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
  window.addEventListener("storage", dailyBadges);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) dailyBadges(); });
  setInterval(dailyBadges, 5000);

  // Paylasim linklerine paylasanin davet kodu: linkle gelen uye olursa ikisi de Pro kazanir
  const inv = () => (window.HL_INV ? `&inv=${window.HL_INV}` : "");
  window.HL = { $, $$, api, toast, openModal, openModalUrl, closeModal, escapeHtml, hydrate, inv };
})();
