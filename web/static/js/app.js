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
  window.HL = { $, $$, api, toast, openModal, openModalUrl, closeModal, escapeHtml, hydrate };
})();
