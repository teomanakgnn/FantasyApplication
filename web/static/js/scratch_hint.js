// Kazi kazan ipucu: gunluk oyun sayfalarinda (giris yapan kullanici). Bu oyunda
// ipucu varsa gosterir; yoksa "burada yok, aramaya devam" der. Hangi oyunlarda
// ipucu oldugu yalnizca sunucuda; her sayfa yalnizca kendisini sorar.
(function () {
  const game = document.currentScript && document.currentScript.dataset.game;
  if (!game || !window.HL) return;
  const { api, escapeHtml: h } = window.HL;
  let span = "";
  if (game === "eightytwo") {
    try { span = String((JSON.parse(localStorage.getItem("hl_82_prefs")) || {}).span || 1); } catch (e) { span = "1"; }
  }
  const face = (id) => `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${id}.png&w=110&h=80`;

  function place(el) {
    const head = document.querySelector("#main .page-head");
    if (head) head.after(el); else (document.querySelector("#main") || document.body).prepend(el);
  }

  api(`/api/scratch/hint?game=${game}${span ? `&span=${span}` : ""}`).then((r) => {
    const el = document.createElement("div");
    if (r.state === "hint") {
      const p = r.hint.player;
      el.className = "sc-hint";
      el.innerHTML = `${p && p.id ? `<img src="${face(p.id)}" alt="" onerror="this.remove()">` : ""}
        <div><span class="sc-hint-k">Scratch card hint · found ${r.found} of ${r.n}</span>
          <b>${h(r.hint.title)}</b><p>${h(r.hint.text)}</p></div>`;
      if (window.gtag) gtag("event", "scratch_hint_found", { game });
    } else if (r.state === "none") {
      el.className = "sc-hint none";
      el.innerHTML = `<div><span class="sc-hint-k">Scratch card</span><p>No hint in this game today - keep looking. Found ${r.found} of ${r.n}.</p></div>`;
    } else if (r.state === "not_scratched" || r.state === "no_card") {
      el.className = "sc-hint none";
      el.innerHTML = `<div><span class="sc-hint-k">Scratch card</span><p>${r.state === "not_scratched" ? "Your daily scratch card is waiting" : "Get your daily scratch card"} on the <a href="/">home page</a> - it hides hints in today's games.</p></div>`;
    } else return;
    place(el);
  }).catch(() => {});
})();
