// NBA Career: draft gecesinden emeklilige secimlerle bir kariyer. Her sezon simule
// edilir (gelisim, rol, istatistik, galibiyet, playoff, sakatlik, oduller); yazlari
// kararlar (antrenman, kontrat, serbest oyuncu, takas, olaylar). Sonda kariyer ozeti,
// Hall of Fame ihtimali, toplam kazanc ve paylasim. Ilerleme bu cihazda saklanir.
// Dil: Ingilizce / Turkce. Kayitta metin degil anahtar tutulur (log, oduller, kararlar),
// boylece dil degisince gecmis de cevrilir.
(function () {
  const { $, toast, escapeHtml: h } = window.HL;
  const D = JSON.parse($("#cr-data").textContent);
  const app = $("#cr-app");
  const KEY = "hl_career_v1", BEST = "hl_career_best", LANG_KEY = "hl_career_lang";
  const load = (k, d) => { try { const v = JSON.parse(localStorage.getItem(k)); return v == null ? d : v; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const rnd = Math.random;
  const gauss = (m = 0, s = 1) => { let u = 0, v = 0; while (!u) u = rnd(); while (!v) v = rnd(); return m + s * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const sig = (x) => 1 / (1 + Math.exp(-x));
  const pick = (arr) => arr[Math.floor(rnd() * arr.length)];
  const pickI = (n) => Math.floor(rnd() * n);
  const money = (m) => (m >= 1000 ? `$${(m / 1000).toFixed(2)}B` : `$${m >= 100 ? Math.round(m) : m.toFixed(1)}M`);
  const FIRST_YEAR = 2028;                      // ilk sezon 2027-28 (2027 draft'i)
  const seasonLabel = (y) => `${y - 1}-${String(y).slice(2)}`;
  const num = (n) => Math.round(n).toLocaleString("en-US");

  // ================= DIL =================
  let LANG = load(LANG_KEY, null) || ((navigator.language || "").toLowerCase().startsWith("tr") ? "tr" : "en");
  const ordEn = (n) => n + (["th", "st", "nd", "rd"][(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10 < 4 ? n % 10 : 0] || "th");
  const ord = (n) => (LANG === "tr" ? `${n}.` : ordEn(n));
  const S = {
    en: {
      head_eyebrow: "Career game", head_title: "NBA Career",
      head_p: "Draft night to retirement in a few minutes. Every summer you make the calls - teams, contracts, training, injuries. Win awards, chase rings, get paid, and see if you make the Hall of Fame.",
      your_player: "Your player", name: "Name", name_ph: "e.g. Jaylen Carter", position: "Position", ptype: "Player type", enter_draft: "Enter the draft",
      best: "Your best careers", seasons_n: "{n} seasons", need_name: "Give your player a name.",
      a_scorer: "Scorer", d_scorer: "Buckets in bunches. Scoring titles and All-Star nods.",
      a_playmaker: "Playmaker", d_playmaker: "Runs the offense. Assists, wins and MVP votes.",
      a_threeD: "3&D Wing", d_threeD: "Shoots it and guards the best player. Every contender wants one.",
      a_rim: "Rim Protector", d_rim: "Blocks, boards, defense. DPOY is in reach.",
      a_twoway: "Two-Way Star", d_twoway: "Does a bit of everything on both ends.",
      r_star: "Franchise star", r_starter: "Starter", r_rotation: "Rotation player", r_bench: "Bench",
      t_contender: "Title contender", t_playoff: "Playoff team", t_fringe: "Fringe playoff team", t_lottery: "Lottery team", t_rebuild: "Rebuilding",
      n_top: "Rebuilding team - the ball is yours from day one.", n_mid: "Middle of the pack - earn your minutes.", n_late: "Contender - small role, real ring chances.",
      draft_eyebrow: "{y} NBA Draft", draft_title: "Draft night, {name}",
      draft_p: "Three teams want you. Your agent can steer you to one of them - where you land shapes your minutes, your growth and your ring chances.",
      k_role: "Role", k_team: "Team", k_dev: "Player development", k_rookie: "Rookie deal", per_yr4: "{m} / yr · 4 yrs",
      age_line: "Age {age} · {season} season", year_n: " · year {n}",
      m_ovr: "Overall", m_fame: "Fame", m_contract: "Contract", m_earned: "Earned", yrs_left: "{n} yr left", yrs_left_p: "{n} yrs left",
      c_ring: "Champion", c_mvp: "MVP", c_fmvp: "Finals MVP", c_dpoy: "DPOY", c_allnba: "All-NBA", c_as: "All-Star", c_scoring: "Scoring title", c_roy: "ROY", c_smoy: "6MOY", c_mip: "MIP", c_gold: "Olympic gold",
      career: "Career", timeline: "Timeline", th_season: "Season", th_team: "Team", th_age: "Age", th_result: "Team result", th_awards: "Awards",
      ready: "Ready for the season", ready_p: "{role} for the {team} ({tier}).", play: "Play the {season} season", new_career_btn: "Start a new career",
      games_min: "{gp} games · {min} min", decision: "Decision",
      aw_roy: "Rookie of the Year", aw_mip: "Most Improved Player", aw_smoy: "Sixth Man of the Year", aw_as: "All-Star",
      aw_allnba: "All-NBA {tm} Team", tm_1: "1st", tm_2: "2nd", tm_3: "3rd", aw_mvp: "MVP", aw_dpoy: "Defensive Player of the Year",
      aw_scoring: "Scoring title", aw_ring: "NBA Champion", aw_fmvp: "Finals MVP",
      po_0: "Missed playoffs", po_1: "Lost in the first round", po_2: "Lost in the conference semis", po_3: "Lost in the conference finals", po_4: "Lost in the NBA Finals", po_5: "Won the NBA title",
      inj_minor: ["Ankle sprain", "Hamstring strain", "Knee soreness", "Back spasms", "Sprained wrist"],
      inj_mid: ["Broken hand", "High ankle sprain", "Calf strain", "Torn ligament in the thumb"],
      inj_major: ["Torn ACL", "Ruptured Achilles", "Torn meniscus", "Fractured kneecap"],
      inj_text_minor: "{name} cost you {g} games.", inj_text_mid: "{name} - out about {g} games.", inj_text_major: "{name} - out {out}.",
      out_season: "for the season", out_games: "about {g} games",
      inj_rushed: " You rushed back.", inj_full: " You took the full recovery.",
      inj_kicker: "{season} · injury", inj_ask: "The medical staff gives you two options.",
      rush: "Rush back", rush_sub: "Miss ~{g} games. Higher re-injury risk next season.", rush_sub_major: "Miss ~{g} games. Higher re-injury risk next season, and it may cost you some burst.",
      full: "Full recovery", full_sub: "Miss all ~{g} games. Come back healthy.",
      summer: "Summer {y}", camp: "Training camp {y}", fa_kicker: "Free agency {y}",
      ev_retire_t: "You're {age}. Keep going?", ev_retire_x: "Overall {ovr}. Your body feels it, but there's a market for you.",
      keep: "Keep playing", keep_sub: "Chase more numbers - or one more ring.", retire: "Retire", retire_sub: "Walk away on your own terms.",
      ev_ext_t: "The {team} offer a rookie extension", ev_ext_x: "5 years, {m} a year ({tot} total), starting next season.",
      sign: "Sign it", sign_sub: "Security now.", bet: "Bet on yourself", bet_sub: "Play out the rookie deal and hit free agency next summer.",
      ev_fa_t: "Your agent's phone is ringing", ev_fa_x: "You're {age} with an overall of {ovr}. Pick your next deal.",
      fa_label: "{team} · {m}/yr", fa_sub: "{tag} · {years} · {tier} · development {dev}", yr1: "1 yr", yrn: "{n} yrs",
      tag_min: "Minimum deal", tag_stay: "Stay put", tag_resign: "Re-sign with {abbr}", tag_ring: "Chase a ring", tag_pay: "Biggest payday", tag_role: "Bigger role",
      ev_trade_t: "Two losing seasons in a row", ev_trade_x: "You're a star on a team going nowhere. The front office asks what you want.",
      trade_req: "Request a trade", trade_req_sub: "Get moved to a winner. Some fans will burn your jersey.", loyal: "Stay loyal", loyal_sub: "Ride it out. The city will love you for it.",
      ev_sixth_t: "Coach wants you to lead the second unit", ev_sixth_x: "You'd come off the bench - fewer minutes, more shots when you're out there.",
      sixth_yes: "Accept the 6th man role", sixth_yes_sub: "Sixth Man of the Year is on the table. The team gets deeper.", sixth_no: "I'm a starter", sixth_no_sub: "Keep your spot. The locker room gets a little tense.",
      ev_oly_t: "Team USA calls", ev_oly_x: "An Olympic roster spot is yours if you want it.",
      oly_go: "Play in the Olympics", oly_go_sub: "Gold medal shot and fame - a long summer on your legs.", oly_rest: "Rest this summer", oly_rest_sub: "Stay fresh for the season.",
      ev_shoe_t: "A signature shoe offer", ev_shoe_x: "A brand wants to build a line around you.",
      shoe_yes: "Sign the shoe deal", shoe_yes_sub: "Endorsement money jumps. Expect a busy summer.", shoe_no: "Not yet", shoe_no_sub: "Stay focused on basketball - a bit more growth this summer.",
      ev_mentor_t: "The front office asks you to mentor the rookies", ev_mentor_x: "A veteran voice in the locker room.",
      mentor_yes: "Take them under your wing", mentor_yes_sub: "The team improves and you age a little more gracefully.", mentor_no: "Focus on my own game", mentor_no_sub: "Every rep counts at this age.",
      ev_viral_t: "Your summer workout video goes viral", ev_viral_x: "Millions of views overnight.",
      viral_fame: "Lean into it", viral_fame_sub: "Podcasts, appearances, brand deals. Fame up.", viral_gym: "Back to the gym", viral_gym_sub: "Quiet summer, a little more growth.",
      ev_train_t: "How do you spend the summer?", ev_train_x: "Overall {ovr} · age {age}.",
      tr_skill: "Skill work", tr_skill_sub: "Shooting, handles, footwork - the biggest jump in your game.",
      tr_strength: "Strength and conditioning", tr_strength_sub: "Fewer injuries from now on, steady growth.",
      tr_brand: "Build your brand", tr_brand_sub: "Fame and endorsement money, slower growth.",
      l_drafted: "Drafted {ord} overall by the {team}.", l_title: "Won the title with the {team}.", l_ext: "Signed a 5-year, {tot} extension.", l_bet: "Turned down the extension to bet on yourself.",
      l_signed: "Signed with the {team}: {years}, {tot}.", l_resigned: "Re-signed with the {team}: {years}, {tot}.", l_traded: "Requested a trade - dealt to the {team}.", l_loyal: "Stayed loyal through the losing.",
      l_sixth: "Accepted the sixth man role.", l_gold: "Won Olympic gold with Team USA.", l_nogold: "Played for Team USA - came home without gold.", l_shoe: "Launched a signature shoe.",
      l_retired: "Retired at {age}. {why}",
      why_age: "Father time is undefeated.", why_offer: "No team made you an offer.", why_choice: "You chose to walk away.",
      hl_goat: "All-time great", hl_hof: "Hall of Famer", hl_as: "Perennial All-Star", hl_fan: "Fan favorite", hl_journey: "Journeyman pro", hl_role: "Role player",
      sp_1: "the most points in NBA history", sp_2: "a top-3 all-time scoring total", sp_3: "a top-10 all-time scoring total", sp_4: "a top-25 all-time scoring total",
      sp_5: "a top-60 all-time scoring total", sp_6: "a long, productive career", sp_7: "a career many dream of",
      over: "Career over · {why}", end_line: "{pos} · {arch} · {ord} pick by {team} · {seasons} seasons, {nteams} team(s) ({teams})",
      e_pts: "Points", e_reb: "Rebounds", e_ast: "Assists", e_gp: "Games", per_game: "{v} per game",
      b_ring: "Championships", b_mvp: "MVPs", b_fmvp: "Finals MVPs", b_as: "All-Star selections", b_allnba: "All-NBA teams", b_dpoy: "DPOYs", b_scoring: "Scoring titles",
      b_roy: "Rookie of the Year", b_smoy: "Sixth Man awards", b_mip: "Most Improved", b_gold: "Olympic golds", no_awards: "No major awards - but you made it to the league.",
      earnings: "Career earnings", earn_split: "{s} salary · {e} endorsements", hof: "Hall of Fame chance", pts_place: "{pts} points: {place}",
      share: "Share my career", new_career: "New career", quit_confirm: "Abandon this career and start a new one?", copied: "Career copied.",
      share_text: "My NBA career: {name}, {ord} pick by {abbr}. {bits}. {m} earned, Hall of Fame chance {hof}%. Build yours: {url}",
      sb_seasons: "{n} seasons", sb_ppg: "{v} PPG", sb_ring: "{n}x champion", sb_mvp: "{n}x MVP", sb_fmvp: "{n}x Finals MVP", sb_as: "{n}x All-Star", sb_dpoy: "{n}x DPOY",
      best_line: "{ppg} PPG{extra} · HOF {hof}%", bx_ring: "{n}x champ", bx_mvp: "{n}x MVP", bx_as: "{n}x All-Star",
      card_title: "NBA CAREER", card_pick: "{ord} PICK", card_seasons: "{n} SEASONS", card_earn: "CAREER EARNINGS", card_hof: "HALL OF FAME CHANCE", card_tag: "Build your own career",
      cd_ring: "CHAMPIONSHIPS", cd_mvp: "MVP", cd_fmvp: "FINALS MVP", cd_as: "ALL-STAR", cd_allnba: "ALL-NBA", cd_dpoy: "DPOY", cd_roy: "ROOKIE OF THE YEAR", cd_scoring: "SCORING TITLES",
      lb_title: "Leaderboard", lb_sub: "Top 5 careers by every player · {n} careers played", lb_empty: "No finished careers yet - be the first.",
      lb_you: "Your career ranks #{rank} of {total} on the leaderboard.", lb_top: "Top 5 all-time! Your career is #{rank} of {total}.",
      lb_seasons: "{n} seasons", lb_rings: "{n} rings", lb_ring1: "1 ring", lb_mvp: "{n} MVP", lb_as: "{n}x All-Star", lb_guest: "guest", lb_failed: "Could not save to the leaderboard.",
    },
    tr: {
      head_eyebrow: "Kariyer oyunu", head_title: "NBA Kariyeri",
      head_p: "Draft gecesinden emekliliğe birkaç dakikada. Her yaz kararları sen veriyorsun - takımlar, kontratlar, antrenman, sakatlıklar. Ödüller kazan, yüzük peşinde koş, paranı al ve Hall of Fame'e girip girmeyeceğini gör.",
      your_player: "Oyuncun", name: "Ad", name_ph: "örn. Kerem Yılmaz", position: "Mevki", ptype: "Oyuncu tipi", enter_draft: "Drafta katıl",
      best: "En iyi kariyerlerin", seasons_n: "{n} sezon", need_name: "Oyuncuna bir ad ver.",
      a_scorer: "Skorer", d_scorer: "Sayıyı yağdırır. Sayı krallıkları ve All-Star seçimleri.",
      a_playmaker: "Oyun kurucu", d_playmaker: "Hücumu yönetir. Asistler, galibiyetler ve MVP oyları.",
      a_threeD: "3&D Kanat", d_threeD: "Üçlüğü atar, rakibin en iyisini savunur. Her şampiyonluk adayı ister.",
      a_rim: "Pota koruyucu", d_rim: "Blok, ribaund, savunma. Yılın Savunmacısı ödülü ulaşılabilir.",
      a_twoway: "Çift yönlü yıldız", d_twoway: "İki tarafta da her şeyi biraz yapar.",
      r_star: "Takımın yıldızı", r_starter: "İlk beş", r_rotation: "Rotasyon oyuncusu", r_bench: "Yedek",
      t_contender: "Şampiyonluk adayı", t_playoff: "Playoff takımı", t_fringe: "Playoff sınırında", t_lottery: "Lotarya takımı", t_rebuild: "Yeniden yapılanıyor",
      n_top: "Yeniden yapılanan takım - top ilk günden sende.", n_mid: "Orta sıralar - dakikalarını kazanman gerek.", n_late: "Şampiyonluk adayı - küçük rol, gerçek yüzük şansı.",
      draft_eyebrow: "{y} NBA Draftı", draft_title: "Draft gecesi, {name}",
      draft_p: "Üç takım seni istiyor. Menajerin seni bunlardan birine yönlendirebilir - gittiğin yer dakikalarını, gelişimini ve yüzük şansını belirler.",
      k_role: "Rol", k_team: "Takım", k_dev: "Oyuncu gelişimi", k_rookie: "Çaylak kontratı", per_yr4: "{m} / yıl · 4 yıl",
      age_line: "{age} yaşında · {season} sezonu", year_n: " · {n}. yıl",
      m_ovr: "Genel", m_fame: "Şöhret", m_contract: "Kontrat", m_earned: "Kazanç", yrs_left: "{n} yıl kaldı", yrs_left_p: "{n} yıl kaldı",
      c_ring: "Şampiyon", c_mvp: "MVP", c_fmvp: "Finaller MVP'si", c_dpoy: "Yılın Savunmacısı", c_allnba: "All-NBA", c_as: "All-Star", c_scoring: "Sayı kralı", c_roy: "Yılın Çaylağı", c_smoy: "6. Adam", c_mip: "En çok gelişen", c_gold: "Olimpiyat altını",
      career: "Kariyer", timeline: "Zaman çizelgesi", th_season: "Sezon", th_team: "Takım", th_age: "Yaş", th_result: "Takım sonucu", th_awards: "Ödüller",
      ready: "Sezona hazırsın", ready_p: "{team} formasıyla {role} ({tier}).", play: "{season} sezonunu oyna", new_career_btn: "Yeni kariyer başlat",
      games_min: "{gp} maç · {min} dk", decision: "Karar",
      aw_roy: "Yılın Çaylağı", aw_mip: "En Çok Gelişen Oyuncu", aw_smoy: "Yılın 6. Adamı", aw_as: "All-Star",
      aw_allnba: "All-NBA {tm} Takım", tm_1: "1.", tm_2: "2.", tm_3: "3.", aw_mvp: "MVP", aw_dpoy: "Yılın Savunmacısı",
      aw_scoring: "Sayı krallığı", aw_ring: "NBA Şampiyonu", aw_fmvp: "Finaller MVP'si",
      po_0: "Playoff'a kalamadı", po_1: "İlk turda elendi", po_2: "Konferans yarı finalinde elendi", po_3: "Konferans finalinde elendi", po_4: "NBA Finallerinde kaybetti", po_5: "NBA şampiyonu oldu",
      inj_minor: ["Bilek burkulması", "Arka adale zorlanması", "Diz ağrısı", "Bel tutulması", "El bileği burkulması"],
      inj_mid: ["El kırığı", "Yüksek ayak bileği burkulması", "Baldır zorlanması", "Başparmakta bağ yırtığı"],
      inj_major: ["Ön çapraz bağ kopması", "Aşil tendonu kopması", "Menisküs yırtığı", "Diz kapağı kırığı"],
      inj_text_minor: "{name} - {g} maç kaçırdın.", inj_text_mid: "{name} - yaklaşık {g} maç yoksun.", inj_text_major: "{name} - {out} yoksun.",
      out_season: "sezon boyunca", out_games: "yaklaşık {g} maç",
      inj_rushed: " Erken döndün.", inj_full: " Tam iyileşmeyi bekledin.",
      inj_kicker: "{season} · sakatlık", inj_ask: "Sağlık ekibi sana iki seçenek sunuyor.",
      rush: "Erken dön", rush_sub: "~{g} maç kaçır. Gelecek sezon tekrar sakatlanma riski artar.", rush_sub_major: "~{g} maç kaçır. Gelecek sezon tekrar sakatlanma riski artar ve patlayıcılığından biraz kaybedebilirsin.",
      full: "Tam iyileş", full_sub: "~{g} maçın tamamını kaçır. Sağlıklı dön.",
      summer: "{y} yazı", camp: "{y} hazırlık kampı", fa_kicker: "{y} serbest oyuncu dönemi",
      ev_retire_t: "{age} yaşındasın. Devam mı?", ev_retire_x: "Genel {ovr}. Vücudun hissediyor ama seni isteyen takımlar var.",
      keep: "Oynamaya devam", keep_sub: "Daha fazla istatistik - ya da bir yüzük daha.", retire: "Emekli ol", retire_sub: "Kendi şartlarınla bırak.",
      ev_ext_t: "{team} çaylak kontratını uzatmak istiyor", ev_ext_x: "5 yıl, yıllık {m} (toplam {tot}), gelecek sezondan itibaren.",
      sign: "İmzala", sign_sub: "Güvence şimdi.", bet: "Kendine güven", bet_sub: "Çaylak kontratını bitir, gelecek yaz serbest oyuncu ol.",
      ev_fa_t: "Menajerinin telefonu susmuyor", ev_fa_x: "{age} yaşındasın, genel {ovr}. Yeni kontratını seç.",
      fa_label: "{team} · {m}/yıl", fa_sub: "{tag} · {years} · {tier} · gelişim {dev}", yr1: "1 yıl", yrn: "{n} yıl",
      tag_min: "Minimum kontrat", tag_stay: "Takımda kal", tag_resign: "{abbr} ile uzat", tag_ring: "Yüzük peşinde", tag_pay: "En yüksek maaş", tag_role: "Daha büyük rol",
      ev_trade_t: "Üst üste iki kötü sezon", ev_trade_x: "Hiçbir yere gitmeyen bir takımda yıldızsın. Yönetim ne istediğini soruyor.",
      trade_req: "Takas iste", trade_req_sub: "Kazanan bir takıma git. Bazı taraftarlar formanı yakacak.", loyal: "Sadık kal", loyal_sub: "Sabret. Şehir seni bunun için sevecek.",
      ev_sixth_t: "Koç yedek kulübesini sana emanet etmek istiyor", ev_sixth_x: "Oyuna yedekten gireceksin - daha az dakika, sahadayken daha çok şut.",
      sixth_yes: "6. adam rolünü kabul et", sixth_yes_sub: "Yılın 6. Adamı ödülü masada. Takım derinleşir.", sixth_no: "Ben ilk beşim", sixth_no_sub: "Yerini koru. Soyunma odası biraz gerilir.",
      ev_oly_t: "ABD Milli Takımı arıyor", ev_oly_x: "İstersen olimpiyat kadrosunda yerin hazır.",
      oly_go: "Olimpiyatlarda oyna", oly_go_sub: "Altın madalya şansı ve şöhret - bacakların için uzun bir yaz.", oly_rest: "Bu yaz dinlen", oly_rest_sub: "Sezona dinç başla.",
      ev_shoe_t: "İmza ayakkabı teklifi", ev_shoe_x: "Bir marka senin adına bir seri çıkarmak istiyor.",
      shoe_yes: "Ayakkabı anlaşmasını imzala", shoe_yes_sub: "Sponsorluk gelirin fırlar. Yoğun bir yaz seni bekliyor.", shoe_no: "Henüz değil", shoe_no_sub: "Basketbola odaklan - bu yaz biraz daha gelişim.",
      ev_mentor_t: "Yönetim çaylaklara abilik yapmanı istiyor", ev_mentor_x: "Soyunma odasında tecrübeli bir ses.",
      mentor_yes: "Onları kanatlarının altına al", mentor_yes_sub: "Takım gelişir, sen de daha zarif yaşlanırsın.", mentor_no: "Kendi oyunuma odaklanırım", mentor_no_sub: "Bu yaşta her antrenman önemli.",
      ev_viral_t: "Yaz antrenman videon viral oldu", ev_viral_x: "Bir gecede milyonlarca izlenme.",
      viral_fame: "Bunun tadını çıkar", viral_fame_sub: "Podcastler, etkinlikler, marka anlaşmaları. Şöhret artar.", viral_gym: "Salona dön", viral_gym_sub: "Sessiz bir yaz, biraz daha gelişim.",
      ev_train_t: "Yazı nasıl geçireceksin?", ev_train_x: "Genel {ovr} · {age} yaşında.",
      tr_skill: "Beceri çalışması", tr_skill_sub: "Şut, top sürme, ayak hareketleri - oyununda en büyük sıçrama.",
      tr_strength: "Kuvvet ve kondisyon", tr_strength_sub: "Bundan sonra daha az sakatlık, istikrarlı gelişim.",
      tr_brand: "Markanı büyüt", tr_brand_sub: "Şöhret ve sponsorluk geliri, daha yavaş gelişim.",
      l_drafted: "{team} tarafından draftın {ord} sırasından seçildin.", l_title: "{team} ile şampiyon oldun.", l_ext: "5 yıllık, toplam {tot} uzatma imzaladın.", l_bet: "Uzatmayı reddedip kendine güvendin.",
      l_signed: "{team} ile anlaştın: {years}, {tot}.", l_resigned: "{team} ile uzattın: {years}, {tot}.", l_traded: "Takas istedin - {team} takımına gönderildin.", l_loyal: "Kötü günlerde takımına sadık kaldın.",
      l_sixth: "6. adam rolünü kabul ettin.", l_gold: "ABD ile olimpiyat altını kazandın.", l_nogold: "ABD formasıyla oynadın - altınsız döndün.", l_shoe: "İmza ayakkabın çıktı.",
      l_retired: "{age} yaşında emekli oldun. {why}",
      why_age: "Zamanı kimse yenemez.", why_offer: "Hiçbir takım teklif yapmadı.", why_choice: "Bırakmayı sen seçtin.",
      hl_goat: "Tüm zamanların en iyilerinden", hl_hof: "Hall of Fame'lik", hl_as: "Daimi All-Star", hl_fan: "Taraftarın sevgilisi", hl_journey: "Gezgin profesyonel", hl_role: "Rol oyuncusu",
      sp_1: "NBA tarihindeki en fazla sayı", sp_2: "tüm zamanların ilk 3'ü seviyesinde sayı", sp_3: "tüm zamanların ilk 10'u seviyesinde sayı", sp_4: "tüm zamanların ilk 25'i seviyesinde sayı",
      sp_5: "tüm zamanların ilk 60'ı seviyesinde sayı", sp_6: "uzun ve verimli bir kariyer", sp_7: "çoğu kişinin hayalindeki bir kariyer",
      over: "Kariyer bitti · {why}", end_line: "{pos} · {arch} · {team} tarafından {ord} sıradan seçildi · {seasons} sezon, {nteams} takım ({teams})",
      e_pts: "Sayı", e_reb: "Ribaund", e_ast: "Asist", e_gp: "Maç", per_game: "maç başı {v}",
      b_ring: "Şampiyonluk", b_mvp: "MVP", b_fmvp: "Finaller MVP'si", b_as: "All-Star seçimi", b_allnba: "All-NBA takımı", b_dpoy: "Yılın Savunmacısı", b_scoring: "Sayı krallığı",
      b_roy: "Yılın Çaylağı", b_smoy: "Yılın 6. Adamı", b_mip: "En Çok Gelişen", b_gold: "Olimpiyat altını", no_awards: "Büyük ödül yok - ama NBA'de oynadın.",
      earnings: "Kariyer kazancı", earn_split: "{s} maaş · {e} sponsorluk", hof: "Hall of Fame şansı", pts_place: "{pts} sayı: {place}",
      share: "Kariyerimi paylaş", new_career: "Yeni kariyer", quit_confirm: "Bu kariyeri bırakıp yenisine başlamak istiyor musun?", copied: "Kariyer kopyalandı.",
      share_text: "NBA kariyerim: {name}, {abbr} tarafından {ord} sıradan seçildim. {bits}. {m} kazanç, Hall of Fame şansı %{hof}. Seninkini kur: {url}",
      sb_seasons: "{n} sezon", sb_ppg: "maç başı {v} sayı", sb_ring: "{n} şampiyonluk", sb_mvp: "{n} MVP", sb_fmvp: "{n} Finaller MVP'si", sb_as: "{n} All-Star", sb_dpoy: "{n} Yılın Savunmacısı",
      best_line: "maç başı {ppg} sayı{extra} · HOF %{hof}", bx_ring: "{n} şampiyonluk", bx_mvp: "{n} MVP", bx_as: "{n} All-Star",
      card_title: "NBA KARİYERİ", card_pick: "{ord} SIRA", card_seasons: "{n} SEZON", card_earn: "KARİYER KAZANCI", card_hof: "HALL OF FAME ŞANSI", card_tag: "Kendi kariyerini kur",
      cd_ring: "ŞAMPİYONLUK", cd_mvp: "MVP", cd_fmvp: "FİNALLER MVP'Sİ", cd_as: "ALL-STAR", cd_allnba: "ALL-NBA", cd_dpoy: "YILIN SAVUNMACISI", cd_roy: "YILIN ÇAYLAĞI", cd_scoring: "SAYI KRALLIĞI",
      lb_title: "Liderlik tablosu", lb_sub: "Tüm oyuncuların en iyi 5 kariyeri · {n} kariyer oynandı", lb_empty: "Henüz biten kariyer yok - ilk sen ol.",
      lb_you: "Kariyerin liderlik tablosunda {total} kariyer içinde {rank}. sırada.", lb_top: "Tüm zamanların ilk 5'inde! Kariyerin {total} kariyer içinde {rank}. sırada.",
      lb_seasons: "{n} sezon", lb_rings: "{n} yüzük", lb_ring1: "1 yüzük", lb_mvp: "{n} MVP", lb_as: "{n} All-Star", lb_guest: "misafir", lb_failed: "Liderlik tablosuna kaydedilemedi.",
    },
  };
  function t(k, v) {
    const s = (S[LANG] && S[LANG][k] != null) ? S[LANG][k] : S.en[k] != null ? S.en[k] : k;
    if (typeof s !== "string") return s;
    return v ? s.replace(/\{(\w+)\}/g, (_, x) => (v[x] != null ? v[x] : "")) : s;
  }
  const yrs = (n) => (n === 1 ? t("yr1") : t("yrn", { n }));
  // Kayitli metin: {k, v} ise cevir; eski kayitlar (duz metin) oldugu gibi
  const tx = (x) => (x == null ? "" : typeof x === "string" ? x : t(x.k, resolve(x.v)));
  // Deger icindeki ic ice anahtarlar (ornek: takim adi, sakatlik adi) cizerken cozulur
  function resolve(v) {
    if (!v) return v;
    const o = { ...v };
    if (o.inj != null) { const list = t(`inj_${o.kind}`); o.name = Array.isArray(list) ? list[o.inj % list.length] : ""; }
    if (o.out === "season") o.out = t("out_season"); else if (o.out != null && typeof o.out === "number") o.out = t("out_games", { g: o.out });
    if (o.tmk) o.tm = t(o.tmk);
    if (o.whyk) o.why = t(o.whyk);
    if (o.ordn != null) o.ord = ord(o.ordn);
    if (o.yearsn != null) o.years = yrs(o.yearsn);
    if (o.tierk) o.tier = t(o.tierk);
    if (o.extra) o.extra = tx(o.extra);
    return o;
  }

  // ---------------- oyuncu tipleri ve mevkiler ----------------
  const ARCH = {
    scorer: { pts: 1.18, ast: 0.95, reb: 0.95, stl: 0.9, blk: 0.8, tpm: 1.15, def: 0.9 },
    playmaker: { pts: 0.97, ast: 1.45, reb: 0.9, stl: 1.15, blk: 0.7, tpm: 1.0, def: 0.95 },
    threeD: { pts: 0.85, ast: 0.85, reb: 1.0, stl: 1.3, blk: 1.05, tpm: 1.5, def: 1.2 },
    rim: { pts: 0.8, ast: 0.8, reb: 1.35, stl: 0.8, blk: 1.9, tpm: 0.25, def: 1.35 },
    twoway: { pts: 1.05, ast: 1.0, reb: 1.05, stl: 1.2, blk: 1.15, tpm: 0.95, def: 1.15 },
  };
  const POS = {
    PG: { reb: 4.2, ast: 6.8, stl: 1.4, blk: 0.3, tpm: 2.4 }, SG: { reb: 4.6, ast: 4.2, stl: 1.3, blk: 0.4, tpm: 2.6 },
    SF: { reb: 6.2, ast: 3.4, stl: 1.2, blk: 0.7, tpm: 2.0 }, PF: { reb: 8.2, ast: 2.8, stl: 0.9, blk: 1.1, tpm: 1.3 },
    C: { reb: 10.8, ast: 2.4, stl: 0.8, blk: 1.8, tpm: 0.6 },
  };
  const ROLE_MIN = { star: 35, starter: 31, rotation: 22, bench: 13 };
  const DEV = ["C", "B", "A"];

  // ---------------- lig ----------------
  const freshTeams = () => Object.fromEntries(D.teams.map((x) => [x.abbr, { ...x, dev: Math.floor(rnd() * 3) }]));
  const T = (st, abbr) => st.teams[abbr];
  const byStrength = (st) => Object.values(st.teams).sort((a, b) => a.s - b.s);

  // ---------------- para ----------------
  // Piyasa degeri (milyon $, bugunun parasi) OVR'ye gore; maas tavani yilda %4 buyur
  function marketValue(ovr, yearIdx) {
    const pts = [[55, 1.2], [62, 2.5], [68, 5], [72, 9], [76, 15], [80, 24], [84, 35], [87, 45], [90, 54], [93, 62], [99, 66]];
    let v = pts[0][1];
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
      if (ovr <= x1) { v = y0 + (y1 - y0) * (Math.max(ovr, x0) - x0) / (x1 - x0); break; }
      v = y1;
    }
    return v * Math.pow(1.04, yearIdx);
  }
  const rookieScale = (p) => Math.max(2.6, 13.2 * (1 - (p - 1) * 0.031));
  // Sponsorluk: yalnizca gercek yildizlarda buyuk (un 40 ~ $4M, 70 ~ $16M, 100 ~ $40M / yil)
  const endorsements = (fame) => Math.pow(clamp(fame, 0, 100), 2.5) / 2500;

  // ---------------- durum ----------------
  let st = load(KEY, null);
  const persist = () => save(KEY, st);
  const log = (year, k, v) => st.log.unshift({ year, k, v });

  // ================= EKRANLAR =================
  function langSwitch() {
    return `<div class="cr-lang"><div class="seg" role="group" aria-label="Language">
      <button type="button" data-lang="en" class="${LANG === "en" ? "is-on" : ""}">EN</button><button type="button" data-lang="tr" class="${LANG === "tr" ? "is-on" : ""}">TR</button></div></div>`;
  }
  function pageHead() {
    const ph = document.querySelector(".cr-wrap .page-head");
    if (!ph) return;
    const e = ph.querySelector(".eyebrow"), h1 = ph.querySelector("h1"), p = ph.querySelector("p");
    if (e) e.textContent = t("head_eyebrow");
    if (h1) h1.textContent = t("head_title");
    if (p) p.textContent = t("head_p");
    document.documentElement.lang = LANG;
  }

  function bestLine(b) {
    if (b.line) return b.line;                 // eski kayit
    const extra = [b.ring ? t("bx_ring", { n: b.ring }) : "", b.mvp ? t("bx_mvp", { n: b.mvp }) : "", b.as ? t("bx_as", { n: b.as }) : ""].filter(Boolean);
    return t("best_line", { ppg: b.ppg, extra: extra.length ? " · " + extra.join(" · ") : "", hof: b.hof });
  }

  function screenCreate() {
    if (!board) loadBoard().then(paintBoard);
    const best = load(BEST, []);
    let pos = "SG", arch = "scorer";
    app.innerHTML = langSwitch() + `
      <section class="card cr-create">
        <div class="card-title">${t("your_player")}</div>
        <label class="field"><span>${t("name")}</span><input class="input" id="cr-name" maxlength="24" placeholder="${h(t("name_ph"))}" value="${h(load("hl_career_name", ""))}"></label>
        <div class="field"><span>${t("position")}</span><div class="seg seg-block" id="cr-pos">${Object.keys(POS).map((p) => `<button type="button" data-pos="${p}" class="${p === pos ? "is-on" : ""}">${p}</button>`).join("")}</div></div>
        <div class="field"><span>${t("ptype")}</span><div class="cr-archs" id="cr-arch">${Object.keys(ARCH).map((k) => `<button type="button" data-arch="${k}" class="cr-arch ${k === arch ? "is-on" : ""}"><b>${t("a_" + k)}</b><small>${t("d_" + k)}</small></button>`).join("")}</div></div>
        <button class="btn btn-primary btn-block" id="cr-go">${t("enter_draft")}</button>
      </section>
      ${boardHtml()}
      ${best.length ? `<section class="card" style="margin-top:12px"><div class="card-title">${t("best")}</div>
        <div class="cr-best">${best.map((b) => `<div><b>${h(b.name)}</b> <span class="dim small">${h(b.pos)} · ${t("seasons_n", { n: b.seasons })}</span><span>${h(bestLine(b))}</span></div>`).join("")}</div></section>` : ""}`;
    app.onclick = (e) => {
      const p = e.target.closest("[data-pos]");
      if (p) { pos = p.dataset.pos; app.querySelectorAll("[data-pos]").forEach((b) => b.classList.toggle("is-on", b === p)); return; }
      const a = e.target.closest("[data-arch]");
      if (a) { arch = a.dataset.arch; app.querySelectorAll("[data-arch]").forEach((b) => b.classList.toggle("is-on", b === a)); return; }
      if (e.target.closest("#cr-go")) {
        const name = $("#cr-name").value.trim().replace(/\s+/g, " ").slice(0, 24);
        if (name.length < 3) return toast(t("need_name"), true);
        save("hl_career_name", name);
        newCareer(name, pos, arch);
      }
    };
  }

  const newId = () => Array.from({ length: 20 }, () => "abcdefghijklmnopqrstuvwxyz0123456789"[Math.floor(rnd() * 36)]).join("");

  // ---------------- liderlik tablosu (tum oyuncular) ----------------
  let board = null;
  async function loadBoard(force) {
    if (board && !force) return board;
    try { board = await window.HL.api("/api/career/leaderboard"); } catch (e) { board = { top: [], total: 0 }; }
    return board;
  }
  function boardHtml() {
    if (!board) return `<section class="card cr-board" id="cr-board"><div class="card-title">${t("lb_title")}</div><div class="spinner"></div></section>`;
    const rows = board.top.map((r, i) => {
      const bits = [t("lb_seasons", { n: r.seasons }), `${Number(r.ppg).toFixed(1)} PPG`];
      if (r.rings) bits.push(r.rings === 1 ? t("lb_ring1") : t("lb_rings", { n: r.rings }));
      if (r.mvps) bits.push(t("lb_mvp", { n: r.mvps }));
      if (r.allstars) bits.push(t("lb_as", { n: r.allstars }));
      return `<li class="${i === 0 ? "first" : ""}"><span class="cr-rank">${i + 1}</span>
        <div class="cr-lb-main"><b>${h(r.name)}</b> <span class="dim small">${h(r.owner === "Guest" ? t("lb_guest") : r.owner)} · ${h(r.pos)} · ${t("a_" + r.arch)}</span>
          <small>${bits.join(" · ")} · ${money(Number(r.earnings))}</small></div>
        <span class="cr-lb-hof">${r.hof}%<small>HOF</small></span></li>`;
    }).join("");
    return `<section class="card cr-board" id="cr-board"><div class="card-title">${t("lb_title")} <span class="dim small">· ${t("lb_sub", { n: num(board.total || 0) })}</span></div>
      ${st && st.board && st.board.rank ? `<p class="small ${st.board.rank <= 5 ? "good" : "muted"}" style="margin:0 0 8px">${t(st.board.rank <= 5 ? "lb_top" : "lb_you", { rank: num(st.board.rank), total: num(st.board.total) })}</p>` : ""}
      ${rows ? `<ol class="cr-lb">${rows}</ol>` : `<p class="small muted" style="margin:0">${t("lb_empty")}</p>`}</section>`;
  }
  function paintBoard() {
    const el = document.getElementById("cr-board");
    if (el) el.outerHTML = boardHtml();
  }
  // Eski kayitlardaki ingilizce odul adlari -> anahtar
  const awardKey = (a) => (typeof a !== "string" ? a.k : /^All-NBA/.test(a) ? "allnba" : ({ "Rookie of the Year": "roy", "Most Improved Player": "mip",
    "Sixth Man of the Year": "smoy", "All-Star": "as", "MVP": "mvp", "Defensive Player of the Year": "dpoy", "Scoring title": "scoring",
    "NBA Champion": "ring", "Finals MVP": "fmvp" })[a]);
  async function submitCareer() {
    if (st.submitted || st.submitting) return;
    st.submitting = true;
    st.id = st.id || newId();
    const body = { id: st.id, name: st.name, pos: st.pos, arch: st.arch, gold: st.awards.gold || 0,
      earnings: st.earnings.salary + st.earnings.endorse,
      seasons: st.seasons.map((x) => ({ gp: x.gp, pts: x.pts, age: x.age, aw: x.awards.map(awardKey).filter(Boolean) })) };
    try {
      const r = await window.HL.api("/api/career/submit", { method: "POST", body });
      st.submitted = true; st.board = { rank: r.rank, total: r.total }; persist();
      await loadBoard(true); paintBoard();
    } catch (e) { toast(t("lb_failed"), true); }
    finally { if (st) st.submitting = false; }
  }

  function newCareer(name, pos, arch) {
    st = { v: 2, id: newId(), name, pos, arch, age: 19 + (rnd() < 0.35 ? 1 : 0) + (rnd() < 0.15 ? 1 : 0), year: FIRST_YEAR,
           ovr: 0, pot: clamp(Math.round(gauss(85.5, 6)), 72, 99), dur: clamp(0.82 + gauss(0, 0.07), 0.6, 0.98),
           fame: 0, team: null, pick: 0, contract: null, seasons: [], awards: {}, earnings: { salary: 0, endorse: 0 },
           phase: "draft", pending: null, forcedRole: null, training: null, rushed: false, flags: {},
           teams: freshTeams(), offers: null, log: [] };
    st.offers = draftOffers();
    persist();
    if (window.gtag) gtag("event", "career_start", { pos, arch, lang: LANG });
    render();
  }

  // Draft: uc teklif - en ust siralar (zayif takim, hemen ilk bes), lotarya ortasi, ilk turun sonu (sampiyonluk adayi)
  function draftOffers() {
    const order = byStrength(st);
    const tiers = [
      { picks: [1, 3], teams: order.slice(0, 5), role: "starter", ovr: [68, 72], note: "n_top" },
      { picks: [7, 14], teams: order.slice(6, 16), role: "rotation", ovr: [63, 67], note: "n_mid" },
      { picks: [20, 30], teams: order.slice(-8), role: "bench", ovr: [59, 63], note: "n_late" },
    ];
    return tiers.map((x) => {
      const team = pick(x.teams);
      const p = x.picks[0] + Math.floor(rnd() * (x.picks[1] - x.picks[0] + 1));
      return { abbr: team.abbr, pick: p, role: x.role, ovr: x.ovr[0] + Math.floor(rnd() * (x.ovr[1] - x.ovr[0] + 1)), note: x.note, salary: rookieScale(p) };
    });
  }

  function teamBadge(abbr, big) {
    const x = T(st, abbr);
    return `<span class="cr-team ${big ? "big" : ""}" style="--tc:${x.color}"><img src="${x.logo}" alt="" onerror="this.style.visibility='hidden'"><b>${h(big ? x.name : x.abbr)}</b></span>`;
  }
  const tierKey = (s) => (s >= 6 ? "t_contender" : s >= 2 ? "t_playoff" : s >= -2 ? "t_fringe" : s >= -6 ? "t_lottery" : "t_rebuild");
  const tier = (s) => t(tierKey(s));

  function screenDraft() {
    app.innerHTML = langSwitch() + `
      <section class="card cr-draft">
        <div class="eyebrow">${t("draft_eyebrow", { y: st.year - 1 })}</div>
        <h2 style="margin:4px 0 6px">${t("draft_title", { name: h(st.name) })}</h2>
        <p class="small muted">${t("draft_p")}</p>
        <div class="cr-offers">${st.offers.map((o, i) => { const x = T(st, o.abbr); return `
          <button class="cr-offer" data-draft="${i}">
            <div class="cr-offer-top">${teamBadge(o.abbr, true)}<span class="cr-pick">#${o.pick}</span></div>
            <div class="cr-kv"><span>${t("k_role")}</span><b>${t("r_" + o.role)}</b></div>
            <div class="cr-kv"><span>${t("k_team")}</span><b>${tier(x.s)}</b></div>
            <div class="cr-kv"><span>${t("k_dev")}</span><b>${DEV[x.dev]}</b></div>
            <div class="cr-kv"><span>${t("k_rookie")}</span><b>${t("per_yr4", { m: money(o.salary) })}</b></div>
            <p class="small muted">${t(o.note.startsWith("n_") ? o.note : "n_mid")}</p>
          </button>`; }).join("")}</div>
      </section>`;
    app.onclick = (e) => {
      const b = e.target.closest("[data-draft]");
      if (!b) return;
      const o = st.offers[+b.dataset.draft];
      st.team = o.abbr; st.pick = o.pick; st.ovr = o.ovr; st.forcedRole = o.role;
      st.contract = { years: 4, salary: o.salary, rookie: true };
      st.fame = clamp(40 - o.pick * 1.2, 4, 40);
      st.draftedBy = o.abbr;
      log(st.year - 1, "l_drafted", { ordn: o.pick, team: T(st, o.abbr).name });
      st.phase = "preseason"; st.offers = null; persist(); render();
    };
  }

  // ---------------- ana ekran ----------------
  function header() {
    const x = st.team ? T(st, st.team) : null;
    const c = st.contract;
    return `<section class="card cr-head" style="--tc:${x ? x.color : "#3987E5"}">
      <div class="cr-who"><div><div class="eyebrow">${st.pos} · ${t("a_" + st.arch)}</div><h2>${h(st.name)}</h2>
        <span class="small muted">${t("age_line", { age: st.age, season: seasonLabel(st.year) })}${st.seasons.length ? t("year_n", { n: st.seasons.length + 1 }) : ""}</span></div>
        ${x ? teamBadge(st.team, true) : ""}</div>
      <div class="cr-meters">
        <div><span>${t("m_ovr")}</span><b>${Math.round(st.ovr)}</b></div>
        <div><span>${t("m_fame")}</span><b>${Math.round(st.fame)}</b></div>
        <div><span>${t("m_contract")}</span><b>${c ? money(c.salary) : "-"}</b><small>${c ? t(c.years === 1 ? "yrs_left" : "yrs_left_p", { n: c.years }) : ""}</small></div>
        <div><span>${t("m_earned")}</span><b>${money(st.earnings.salary + st.earnings.endorse)}</b></div>
      </div>
      ${trophies()}
    </section>`;
  }
  const TROPHY_ORDER = ["ring", "mvp", "fmvp", "dpoy", "allnba", "as", "scoring", "roy", "smoy", "mip", "gold"];
  function trophies() {
    const a = st.awards;
    const chips = TROPHY_ORDER.filter((k) => a[k]).map((k) => `<span class="cr-chip ${k}">${a[k] > 1 ? `${a[k]}x ` : ""}${t("c_" + k)}</span>`);
    return chips.length ? `<div class="cr-trophies">${chips.join("")}</div>` : "";
  }
  const awardText = (a) => (typeof a === "string" ? a : t("aw_" + a.k, a.tm ? { tm: t("tm_" + a.tm) } : null));
  const resultText = (s) => (s.po != null ? t("po_" + s.po) : s.result || "");
  function seasonRows() {
    if (!st.seasons.length) return "";
    return `<section class="card" style="margin-top:12px"><div class="card-title">${t("career")}</div>
      <div class="table-wrap"><table class="table small cr-table"><thead><tr><th class="l">${t("th_season")}</th><th class="l">${t("th_team")}</th><th>${t("th_age")}</th><th>OVR</th><th>GP</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th class="l">${t("th_result")}</th><th class="l">${t("th_awards")}</th></tr></thead>
      <tbody>${st.seasons.slice().reverse().map((s) => `<tr><td class="l">${seasonLabel(s.year)}</td><td class="l">${h(s.team)}</td><td>${s.age}</td><td>${s.ovr}</td><td>${s.gp}</td>
        <td><b>${s.pts.toFixed(1)}</b></td><td>${s.reb.toFixed(1)}</td><td>${s.ast.toFixed(1)}</td><td>${s.stl.toFixed(1)}</td><td>${s.blk.toFixed(1)}</td>
        <td class="l small">${s.w}-${82 - s.w} · ${h(resultText(s))}</td><td class="l small">${s.awards.map((a) => h(awardText(a))).join(", ") || '<span class="dim">-</span>'}</td></tr>`).join("")}</tbody></table></div></section>`;
  }
  function logHtml() {
    return st.log.length ? `<section class="card" style="margin-top:12px"><div class="card-title">${t("timeline")}</div><div class="cr-log">${st.log.slice(0, 14).map((l) => `<div><span>${l.year}</span>${h(l.text != null ? l.text : tx(l))}</div>`).join("")}</div></section>` : "";
  }

  // ---------------- karar kartlari (cizerken seçili dilde uretilir) ----------------
  function decisionView(p) {
    if (p.title) return p;                      // eski kayit (duz metin)
    const y = st.year - 1, d = p.data || {};
    const sm = { kicker: t("summer", { y }) };
    const opt = (k, v) => ({ label: t(k), sub: t(k + "_sub"), v });
    switch (p.kind) {
      case "injury": {
        const inj = d.ctx.inj, g = inj.games;
        return { kicker: t("inj_kicker", { season: seasonLabel(st.year) }), title: tx(inj.note), text: t("inj_ask"),
          options: [{ label: t("rush"), sub: t(inj.major ? "rush_sub_major" : "rush_sub", { g: Math.round(g * 0.55) }), v: "rush" },
                    { label: t("full"), sub: t("full_sub", { g: Math.min(82, g) }), v: "full" }] };
      }
      case "retire": return { ...sm, title: t("ev_retire_t", { age: st.age }), text: t("ev_retire_x", { ovr: Math.round(st.ovr) }), options: [opt("keep", "go"), opt("retire", "retire")] };
      case "extension": return { ...sm, title: t("ev_ext_t", { team: T(st, st.team).name }), text: t("ev_ext_x", { m: money(d.ext), tot: money(d.ext * 5) }), options: [opt("sign", "sign"), opt("bet", "bet")] };
      case "fa": return { kicker: t("fa_kicker", { y }), title: t("ev_fa_t"), text: t("ev_fa_x", { age: st.age, ovr: Math.round(st.ovr) }),
        options: d.offers.map((o, i) => ({ label: t("fa_label", { team: T(st, o.abbr).name, m: money(o.salary) }),
          sub: t("fa_sub", { tag: t(o.tag, { abbr: o.abbrTag || "" }), years: yrs(o.years), tier: tier(T(st, o.abbr).s), dev: DEV[T(st, o.abbr).dev] }), v: i })) };
      case "trade": return { ...sm, title: t("ev_trade_t"), text: t("ev_trade_x"), options: [opt("trade_req", "trade"), opt("loyal", "stay")] };
      case "sixth": return { kicker: t("camp", { y }), title: t("ev_sixth_t"), text: t("ev_sixth_x"), options: [opt("sixth_yes", "yes"), opt("sixth_no", "no")] };
      case "olympics": return { ...sm, title: t("ev_oly_t"), text: t("ev_oly_x"), options: [opt("oly_go", "go"), opt("oly_rest", "rest")] };
      case "shoe": return { ...sm, title: t("ev_shoe_t"), text: t("ev_shoe_x"), options: [opt("shoe_yes", "sign"), opt("shoe_no", "no")] };
      case "mentor": return { ...sm, title: t("ev_mentor_t"), text: t("ev_mentor_x"), options: [opt("mentor_yes", "yes"), opt("mentor_no", "no")] };
      case "viral": return { ...sm, title: t("ev_viral_t"), text: t("ev_viral_x"), options: [opt("viral_fame", "fame"), opt("viral_gym", "gym")] };
      case "training": return { ...sm, title: t("ev_train_t"), text: t("ev_train_x", { ovr: Math.round(st.ovr), age: st.age }), options: [opt("tr_skill", "skill"), opt("tr_strength", "strength"), opt("tr_brand", "brand")] };
    }
    return { title: "", options: [] };
  }
  function decisionCard(p) {
    const d = decisionView(p);
    return `<section class="card cr-decision"><div class="eyebrow">${h(d.kicker || t("decision"))}</div><h3>${h(d.title)}</h3>
      ${d.text ? `<p class="small muted">${h(d.text)}</p>` : ""}
      <div class="cr-choices">${d.options.map((o, i) => `<button class="cr-choice" data-opt="${i}"><b>${h(o.label)}</b>${o.sub ? `<small>${h(o.sub)}</small>` : ""}</button>`).join("")}</div></section>`;
  }

  function render() {
    pageHead();
    if (!st) return screenCreate();
    if (st.phase === "draft") return screenDraft();
    if (st.phase === "end") return screenEnd();
    let main = "";
    if (st.pending) main = decisionCard(st.pending);
    else if (st.phase === "preseason") {
      const role = st.forcedRole || roleFor();
      const x = T(st, st.team);
      main = `<section class="card cr-next"><div><div class="eyebrow">${seasonLabel(st.year)}</div><h3>${t("ready")}</h3>
        <p class="small muted">${h(t("ready_p", { role: t("r_" + role), team: x.name, tier: tier(x.s).toLowerCase() }))}</p></div>
        <button class="btn btn-primary" id="cr-play">${t("play", { season: seasonLabel(st.year) })}</button></section>`;
    }
    const last = st.lastSeason ? seasonCard(st.lastSeason) : "";
    app.innerHTML = langSwitch() + header() + last + main + seasonRows() + logHtml() +
      `<div class="cr-foot"><button class="btn btn-sm btn-ghost" id="cr-quit">${t("new_career_btn")}</button></div>`;
  }

  function seasonCard(s) {
    return `<section class="card cr-season ${s.awards.length ? "has-awards" : ""}">
      <div class="cr-season-h"><div><div class="eyebrow">${seasonLabel(s.year)} · ${h(s.team)}</div><h3>${s.pts.toFixed(1)} PTS · ${s.reb.toFixed(1)} REB · ${s.ast.toFixed(1)} AST</h3>
        <span class="small muted">${t("games_min", { gp: s.gp, min: s.min.toFixed(1) })} · ${s.stl.toFixed(1)} STL · ${s.blk.toFixed(1)} BLK · ${s.tpm.toFixed(1)} 3PM · OVR ${s.ovr}${s.dOvr ? ` (${s.dOvr > 0 ? "+" : ""}${s.dOvr})` : ""}</span></div>
        <div class="cr-rec"><b>${s.w}-${82 - s.w}</b><span>${h(resultText(s))}</span></div></div>
      ${s.awards.length ? `<div class="cr-trophies">${s.awards.map((a) => `<span class="cr-chip new">${h(awardText(a))}</span>`).join("")}</div>` : ""}
      ${s.notes.length ? `<p class="small muted" style="margin:6px 0 0">${s.notes.map((n) => h(tx(n))).join(" ")}</p>` : ""}
    </section>`;
  }

  // ================= SIMULASYON =================
  function roleFor() {
    const s = T(st, st.team).s;
    const bump = clamp(s, -6, 8) * 0.5;
    if (st.ovr >= 86 + bump) return "star";
    if (st.ovr >= 77 + bump) return "starter";
    if (st.ovr >= 69 + bump) return "rotation";
    return "bench";
  }

  function develop() {
    const age = st.age;
    const curve = age <= 21 ? 4.2 : age <= 23 ? 3.0 : age <= 25 ? 1.8 : age <= 27 ? 0.7 : age <= 29 ? -0.3 : age <= 31 ? -1.4 : age <= 33 ? -2.6 : age <= 35 ? -3.8 : -5;
    const role = st.forcedRole || roleFor();
    const minsBonus = { star: 0.6, starter: 0.5, rotation: 0.1, bench: -0.4 }[role];
    const devBonus = (T(st, st.team).dev - 1) * 0.6;
    const train = st.training === "skill" ? 1.2 : st.training === "strength" ? 0.4 : st.training === "brand" ? -0.6 : 0;
    let d = curve + (curve > 0 ? minsBonus + devBonus : 0) + train + gauss(0, 2.0);
    // Potansiyele yaklastikca yavaslar
    if (st.ovr + d > st.pot) d = Math.min(d, Math.max(0, (st.pot - st.ovr) * 0.6) + gauss(0, 0.6));
    if (st.flags.mentor && d < 0) d *= 0.75;
    const before = st.ovr;
    st.ovr = clamp(st.ovr + d, 40, 99);
    return Math.round(st.ovr) - Math.round(before);
  }

  function playSeason() {
    const dOvr = st.seasons.length ? develop() : 0;
    st.training = null;
    const team = T(st, st.team);
    const role = st.forcedRole || roleFor();
    st.forcedRole = null;
    const ovr = Math.round(st.ovr);
    // Sakatlik
    let missed = Math.round(Math.abs(gauss(0, 3)));       // dinlendirme, ufak tefek
    const inj = { note: null, major: false };
    const pInj = 0.11 + Math.max(0, st.age - 29) * 0.025 + (1 - st.dur) * 0.45 + (st.rushed ? 0.12 : 0) + (st.flags.olympics ? 0.04 : 0);
    st.rushed = false; st.flags.olympics = false;
    if (rnd() < pInj) {
      const r = rnd();
      if (r < 0.58) { const g = 4 + Math.floor(rnd() * 10); missed += g; inj.note = { k: "inj_text_minor", v: { kind: "minor", inj: pickI(5), g } }; }
      else if (r < 0.88) { const g = 15 + Math.floor(rnd() * 18); inj.note = { k: "inj_text_mid", v: { kind: "mid", inj: pickI(4), g } }; inj.games = g; inj.mid = true; }
      else { const g = 45 + Math.floor(rnd() * 37); inj.note = { k: "inj_text_major", v: { kind: "major", inj: pickI(4), out: g >= 82 ? "season" : g } }; inj.games = g; inj.major = true; }
    }
    // Ciddi sakatlikta karar (erken don / tam iyiles): sezon bu karardan sonra biter
    const ctx = { dOvr, role, ovr, missed, inj, team: team.abbr };
    if (inj.mid || inj.major) {
      st.pending = { kind: "injury", data: { ctx } };
      persist(); return render();
    }
    finishSeason(ctx);
  }

  function finishSeason(ctx) {
    const team = T(st, st.team);
    const { role, dOvr } = ctx;
    const ovr = ctx.ovr;
    const notes = [];
    const gp = clamp(82 - ctx.missed, 0, 82);
    if (ctx.inj.note) notes.push(ctx.inj.note);
    if (ctx.inj.choice) notes.push({ k: ctx.inj.choice });
    const a = ARCH[st.arch], p = POS[st.pos];
    const min = gp ? clamp(ROLE_MIN[role] + gauss(0, 1.5) + (role === "bench" ? (ovr - 62) * 0.3 : 0), 8, 39) : 0;
    const m36 = min / 36, k = 0.55 + (ovr - 60) * 0.017;
    const n = (x) => Math.max(0, x * (1 + gauss(0, 0.06)));
    const line = gp ? {
      pts: n((7 + (ovr - 60) * 0.62) * a.pts * m36 * (role === "star" ? 1.06 : 1)), reb: n(p.reb * a.reb * k * m36), ast: n(p.ast * a.ast * k * m36),
      stl: n(p.stl * a.stl * k * m36), blk: n(p.blk * a.blk * k * m36), tpm: n(p.tpm * a.tpm * k * m36),
    } : { pts: 0, reb: 0, ast: 0, stl: 0, blk: 0, tpm: 0 };
    // Takim: guc + senin etkin (dakika ve oynadigin mac kadar)
    const impact = (ovr - 72) * 0.26 * (min / 34) * (gp / 82);
    const net = team.s + impact;
    const w = clamp(Math.round(41 + 2.7 * net + gauss(0, 3.5)), 12, 70);
    const po = playoffs(w, net, gp);
    const awards = [], add = (key, extra) => { st.awards[key] = (st.awards[key] || 0) + 1; awards.push({ k: key, ...(extra || {}) }); };
    const rookie = st.seasons.length === 0;
    const ok = gp >= 58;
    // Oduller
    if (rookie && gp >= 50 && rnd() < sig((line.pts + line.reb * 0.5 + line.ast * 0.7 - 15) / 2)) { add("roy"); st.fame += 8; }
    if (!rookie && dOvr >= 5 && ok && rnd() < 0.45) add("mip");
    if ((role === "bench" || role === "rotation") && line.pts >= 12 && ok && rnd() < sig((line.pts - 15) / 1.8)) { add("smoy"); st.fame += 4; }
    if (gp >= 40 && rnd() < sig((ovr - 86) / 1.5 + (st.fame - 50) / 70 + (w - 41) / 45)) { add("as"); st.fame += 5; }
    if (ok && rnd() < sig((ovr - 89.5) / 1.3 + (w - 41) / 45)) { const tm = ovr >= 94 ? "1" : ovr >= 91.5 ? pick(["1", "2"]) : pick(["2", "3", "3"]); add("allnba", { tm }); st.fame += 6; }
    if (ok && gp >= 65 && ovr >= 91 && w >= 48 && rnd() < sig((ovr - 94) / 1.2 + (w - 55) / 7)) { add("mvp"); st.fame += 14; }
    const defScore = ovr * a.def + line.blk * 3 + line.stl * 3;
    if (gp >= 65 && ovr >= 84 && rnd() < sig((defScore - 133) / 2.5)) { add("dpoy"); st.fame += 5; }
    if (line.pts >= 28.5 && ok && rnd() < sig((line.pts - 31) / 1.2)) { add("scoring"); st.fame += 4; }
    if (po.champ && gp > 0) {
      add("ring"); st.fame += 9;
      if ((role === "star" && rnd() < 0.8) || (role === "starter" && ovr >= 84 && rnd() < 0.3)) { add("fmvp"); st.fame += 10; }
    }
    // Un tavani oyuncunun seviyesine bagli: yedek oyuncu marka kurarak superstar olamaz
    const fameCap = clamp(28 + Math.max(0, ovr - 70) * 3, 28, 100);
    st.fame = clamp(Math.min(fameCap, st.fame * 0.9 + Math.max(0, line.pts - 8) * 0.55 + (po.round >= 3 ? 3 : 0)), 0, 100);
    const salary = st.contract ? st.contract.salary : 0;
    const endorse = endorsements(st.fame) * (st.flags.shoe ? 1.6 : 1);
    st.earnings.salary += salary; st.earnings.endorse += endorse;
    const s = { year: st.year, team: team.abbr, age: st.age, ovr: Math.round(st.ovr), dOvr, role, gp, min, ...line,
                w, po: po.code, awards, notes, salary, endorse };
    st.seasons.push(s);
    st.lastSeason = s;
    if (po.champ) log(st.year, "l_title", { team: team.name });
    // Takimlar degisir (ortalamaya donus + rastgele)
    Object.values(st.teams).forEach((x) => { x.s = clamp(x.s * 0.72 + gauss(0, 3.3), -12, 12); });
    if (st.contract) st.contract.years -= 1;
    st.age += 1; st.year += 1;
    if (window.gtag && rookie) gtag("event", "career_rookie_done", {});
    offseason();
  }

  // code: 0 = playoff yok, 1-4 = o turda elendi, 5 = sampiyon
  function playoffs(w, net, gp) {
    const made = w >= 45 || (w >= 41 && rnd() < 0.7) || (w >= 38 && rnd() < 0.3);
    if (!made) return { code: 0, round: 0, champ: false };
    const opp = [1.5, 4.0, 6.0, 8.0];
    const power = net - (gp < 60 ? 2 : 0);
    for (let r = 0; r < 4; r++) {
      if (rnd() > sig((power - opp[r] + (w - 50) / 10) / 3.2)) return { code: r + 1, round: r, champ: false };
    }
    return { code: 5, round: 4, champ: true };
  }

  // ================= YAZ =================
  // Sira: emeklilik (33+), kontrat/serbest oyuncu, bir olay, antrenman. Her biri bir karar karti.
  function offseason() {
    st.queue = [];
    const ovr = st.ovr;
    // Imzalanmis uzatma: rookie kontrati bitince devreye girer (serbest oyuncu olmaz)
    if (st.contract && st.contract.years <= 0 && st.contract.next) st.contract = { ...st.contract.next };
    if (st.age >= 41 || (ovr < 58 && st.age >= 31)) return retire(st.age >= 41 ? "why_age" : "why_offer");
    if (st.age >= 33) st.queue.push("retire");
    const c = st.contract;
    if (c && c.rookie && c.years === 1 && ovr >= 74 && !st.flags.extDone) st.queue.push("extension");
    if (!c || c.years <= 0) st.queue.push("fa");
    const events = [];
    const team = T(st, st.team);
    const lastTwo = st.seasons.slice(-2);
    if (lastTwo.length === 2 && lastTwo.every((s) => s.w < 35) && ovr >= 84 && c && c.years > 0) events.push("trade");
    if (roleFor() === "starter" && team.s >= 3 && ovr < 84 && rnd() < 0.5) events.push("sixth");
    if (st.year % 4 === 0 && ovr >= 84) events.push("olympics");
    if (st.fame >= 35 && !st.flags.shoe && rnd() < 0.5) events.push("shoe");
    if (st.age >= 30 && !st.flags.mentor && rnd() < 0.4) events.push("mentor");
    if (rnd() < 0.3) events.push("viral");
    if (events.length) st.queue.push(pick(events));
    st.queue.push("training");
    nextDecision();
  }

  function nextDecision() {
    const k = st.queue.shift();
    if (!k) { st.pending = null; st.phase = "preseason"; persist(); return render(); }
    const data = {};
    if (k === "extension") data.ext = marketValue(st.ovr + 2, st.year - FIRST_YEAR) * 0.92;
    if (k === "fa") data.offers = faOffers();
    st.pending = { kind: k, data };
    persist(); render();
  }

  // Serbest oyuncu teklifleri
  function faOffers() {
    const yi = st.year - FIRST_YEAR, ovr = st.ovr, mv = marketValue(ovr, yi);
    const order = byStrength(st);
    const cur = T(st, st.team);
    const contender = pick(order.slice(-6).filter((x) => x.abbr !== st.team)) || order[order.length - 1];
    const rebuild = pick(order.slice(0, 8).filter((x) => x.abbr !== st.team)) || order[0];
    const mid = pick(order.slice(8, 22).filter((x) => x.abbr !== st.team)) || order[10];
    const old = st.age >= 32;
    const y = (n) => Math.max(1, Math.min(n, old ? 2 : n));
    if (ovr < 62) {
      return [{ abbr: pick([contender, mid]).abbr, salary: Math.max(1.2, mv), years: 1, tag: "tag_min" },
              { abbr: st.team, salary: Math.max(1.2, mv * 0.95), years: 1, tag: "tag_stay" }];
    }
    return [
      { abbr: st.team, salary: mv * 0.97, years: y(4), tag: "tag_resign", abbrTag: cur.abbr },
      { abbr: contender.abbr, salary: mv * 0.72, years: y(2), tag: "tag_ring" },
      { abbr: rebuild.abbr, salary: mv * 1.12, years: y(5), tag: "tag_pay" },
      ...(rnd() < 0.6 ? [{ abbr: mid.abbr, salary: mv * 0.92, years: y(3), tag: "tag_role" }] : []),
    ];
  }

  function choose(i) {
    const p = st.pending, d = p.data || {};
    const view = decisionView(p), v = view.options[i] && view.options[i].v;
    // Eski surumde kaydedilmis karar: teklif nesnesi seceneğin icinde, sakatlik baglami p.ctx'te
    if (p.title && p.kind === "fa") d.offers = p.options.map((o) => o.v);
    if (p.title && p.kind === "injury") d.ctx = p.ctx;
    const y = st.year - 1;
    switch (p.kind) {
      case "injury": {
        const ctx = d.ctx;
        if (v === "rush") { ctx.missed += Math.round(ctx.inj.games * 0.55); st.rushed = true; st.dur = clamp(st.dur - 0.03, 0.5, 0.99); if (ctx.inj.major) st.ovr -= 2; ctx.inj.choice = "inj_rushed"; }
        else { ctx.missed += Math.min(82, ctx.inj.games); if (ctx.inj.major) { st.ovr -= 1; st.pot = Math.max(st.ovr, st.pot - 2); } ctx.inj.choice = "inj_full"; }
        st.pending = null;
        if (ctx.inj.note) st.log.unshift({ year: st.year, k: ctx.inj.note.k, v: ctx.inj.note.v });
        else if (ctx.inj.text) st.log.unshift({ year: st.year, text: ctx.inj.text });
        return finishSeason(ctx);
      }
      case "retire": if (v === "retire") return retire("why_choice"); break;
      case "extension":
        st.flags.extDone = true;
        if (v === "sign") { st.contract.next = { years: 5, salary: d.ext }; log(y, "l_ext", { tot: money(d.ext * 5) }); }
        else log(y, "l_bet");
        break;
      case "fa": {
        const off = typeof v === "object" ? v : d.offers[v];
        const moved = off.abbr !== st.team;
        st.team = off.abbr; st.contract = { years: off.years, salary: off.salary };
        log(y, moved ? "l_signed" : "l_resigned", { team: T(st, off.abbr).name, yearsn: off.years, tot: money(off.salary * off.years) });
        break;
      }
      case "trade":
        if (v === "trade") {
          const dest = pick(byStrength(st).slice(-8).filter((x) => x.abbr !== st.team));
          log(y, "l_traded", { team: dest.name });
          st.team = dest.abbr; st.fame = clamp(st.fame - 3, 0, 100);
        } else { st.fame = clamp(st.fame + 4, 0, 100); T(st, st.team).s += 1.5; log(y, "l_loyal"); }
        break;
      case "sixth":
        if (v === "yes") { st.forcedRole = "rotation"; T(st, st.team).s += 1; log(y, "l_sixth"); }
        else T(st, st.team).s -= 0.8;
        break;
      case "olympics":
        if (v === "go") {
          st.flags.olympics = true; st.fame = clamp(st.fame + 5, 0, 100);
          if (rnd() < 0.6) { st.awards.gold = (st.awards.gold || 0) + 1; log(y, "l_gold"); } else log(y, "l_nogold");
        } else st.dur = clamp(st.dur + 0.01, 0.5, 0.99);
        break;
      case "shoe":
        if (v === "sign") { st.flags.shoe = true; st.fame = clamp(st.fame + 4, 0, 100); log(y, "l_shoe"); }
        else st.ovr = clamp(st.ovr + 0.7, 40, 99);
        break;
      case "mentor":
        if (v === "yes") { st.flags.mentor = true; T(st, st.team).s += 0.8; st.fame = clamp(st.fame + 2, 0, 100); }
        break;
      case "viral":
        if (v === "fame") st.fame = clamp(st.fame + 7, 0, 100); else st.ovr = clamp(st.ovr + 0.8, 40, 99);
        break;
      case "training":
        st.training = v;
        if (v === "strength") st.dur = clamp(st.dur + 0.04, 0.5, 0.99);
        if (v === "brand") st.fame = clamp(st.fame + 6, 0, 100);
        break;
    }
    nextDecision();
  }

  // ================= KARIYER SONU =================
  function totals() {
    const SS = st.seasons, gp = SS.reduce((a, s) => a + s.gp, 0) || 1;
    const sum = (k) => SS.reduce((a, s) => a + s[k] * s.gp, 0);
    return { seasons: SS.length, gp, pts: sum("pts"), reb: sum("reb"), ast: sum("ast"), stl: sum("stl"), blk: sum("blk"),
             ppg: sum("pts") / gp, rpg: sum("reb") / gp, apg: sum("ast") / gp, teams: [...new Set(SS.map((s) => s.team))] };
  }
  function hof(x) {
    const a = st.awards;
    const score = 15 * (a.mvp || 0) + 8 * (a.fmvp || 0) + 6 * (a.ring || 0) + 5 * (a.allnba || 0) + 3 * (a.as || 0) + 4 * (a.dpoy || 0)
      + 2 * (a.roy || 0) + 2 * (a.scoring || 0) + 2 * (a.gold || 0) + x.pts / 2000;
    return { score, p: Math.round(100 * sig((score - 36) / 6.5)) };
  }
  const scoringPlace = (pts) => t(pts >= 40000 ? "sp_1" : pts >= 36000 ? "sp_2" : pts >= 31000 ? "sp_3" : pts >= 26000 ? "sp_4" : pts >= 20000 ? "sp_5" : pts >= 12000 ? "sp_6" : "sp_7");
  function headline(x) {
    const a = st.awards;
    if ((a.mvp || 0) >= 3 || ((a.ring || 0) >= 4 && (a.fmvp || 0) >= 2)) return t("hl_goat");
    if (a.mvp || ((a.ring || 0) >= 2 && (a.as || 0) >= 6)) return t("hl_hof");
    if ((a.as || 0) >= 5) return t("hl_as");
    if (a.as || a.ring) return t("hl_fan");
    if (x.seasons >= 12) return t("hl_journey");
    return t("hl_role");
  }
  const whyText = () => (st.retiredWhyK ? t(st.retiredWhyK) : st.retiredWhy || "");
  function retire(whyK) {
    st.phase = "end"; st.retiredWhyK = whyK; st.pending = null;
    const x = totals(), H = hof(x);
    log(st.year - 1, "l_retired", { age: st.age, whyk: whyK });
    const best = load(BEST, []);
    const a = st.awards;
    best.push({ name: st.name, pos: st.pos, seasons: x.seasons, score: H.score, ppg: x.ppg.toFixed(1), ring: a.ring || 0, mvp: a.mvp || 0, as: a.as || 0, hof: H.p });
    best.sort((p, q) => q.score - p.score);
    save(BEST, best.slice(0, 5));
    if (window.gtag) gtag("event", "career_end", { seasons: x.seasons, hof: H.p });
    persist(); render();
  }

  const BIG = ["ring", "mvp", "fmvp", "as", "allnba", "dpoy", "scoring", "roy", "smoy", "mip", "gold"];
  function screenEnd() {
    const x = totals(), H = hof(x), a = st.awards;
    const earned = st.earnings.salary + st.earnings.endorse;
    const big = BIG.filter((k) => a[k]);
    app.innerHTML = langSwitch() + `
      <section class="card cr-end">
        <div class="eyebrow">${h(t("over", { why: whyText() }))}</div>
        <h2>${h(st.name)}</h2>
        <div class="cr-headline">${headline(x)}</div>
        <p class="small muted">${h(t("end_line", { pos: st.pos, arch: t("a_" + st.arch), ord: ord(st.pick), team: T(st, st.draftedBy).name, seasons: x.seasons, nteams: x.teams.length, teams: x.teams.join(", ") }))}</p>
        <div class="cr-meters">
          <div><span>${t("e_pts")}</span><b>${num(x.pts)}</b><small>${t("per_game", { v: x.ppg.toFixed(1) })}</small></div>
          <div><span>${t("e_reb")}</span><b>${num(x.reb)}</b><small>${t("per_game", { v: x.rpg.toFixed(1) })}</small></div>
          <div><span>${t("e_ast")}</span><b>${num(x.ast)}</b><small>${t("per_game", { v: x.apg.toFixed(1) })}</small></div>
          <div><span>${t("e_gp")}</span><b>${num(x.gp)}</b><small>${t("seasons_n", { n: x.seasons })}</small></div>
        </div>
        <div class="cr-awards">${big.length ? big.map((k) => `<div><b>${a[k]}</b><span>${t("b_" + k)}</span></div>`).join("") : `<p class="muted small">${t("no_awards")}</p>`}</div>
        <div class="cr-money">
          <div><span>${t("earnings")}</span><b>${money(earned)}</b><small>${t("earn_split", { s: money(st.earnings.salary), e: money(st.earnings.endorse) })}</small></div>
          <div><span>${t("hof")}</span><b class="${H.p >= 70 ? "good" : H.p >= 30 ? "warn" : ""}">${H.p}%</b><small>${h(t("pts_place", { pts: num(x.pts), place: scoringPlace(x.pts) }))}</small></div>
        </div>
        <div class="gr-actions"><button class="btn btn-primary" id="cr-share">${t("share")}</button><button class="btn" id="cr-new">${t("new_career")}</button></div>
      </section>` + boardHtml() + seasonRows() + logHtml();
    if (!st.submitted) submitCareer(); else if (!board) loadBoard().then(paintBoard);
    app.onclick = async (e) => {
      if (e.target.closest("#cr-new")) { st = null; save(KEY, null); return render(); }
      if (e.target.closest("#cr-share")) return share(x, H, earned);
    };
  }

  async function share(x, H, earned) {
    const a = st.awards;
    const bits = [t("sb_seasons", { n: x.seasons }), t("sb_ppg", { v: x.ppg.toFixed(1) })];
    ["ring", "mvp", "fmvp", "as", "dpoy"].forEach((k) => { if (a[k]) bits.push(t("sb_" + k, { n: a[k] })); });
    const text = t("share_text", { name: st.name, ord: ord(st.pick), abbr: T(st, st.draftedBy).abbr, bits: bits.join(", "), m: money(earned), hof: H.p,
                                   url: `${location.origin}/career?ref=career-share${window.HL.inv()}` });
    if (window.gtag) gtag("event", "career_share", { hof: H.p, lang: LANG });
    const btn = $("#cr-share"); if (btn) btn.classList.add("is-loading");
    try {
      const K = window.HLCard;
      const { cv, g } = await K.base(t("card_title"), "");
      const up = (s) => s.toLocaleUpperCase(LANG === "tr" ? "tr-TR" : "en-US");
      K.text(g, up(st.name), K.W / 2, 300, { weight: 900, size: st.name.length > 16 ? 70 : 92, align: "center" });
      K.pill(g, up(headline(x)), K.W / 2, 362, { bg: H.p >= 70 ? K.C.gold : "rgba(255,255,255,.12)", color: H.p >= 70 ? "#1B1300" : "#fff", size: 30, h: 56, padX: 26 });
      K.text(g, `${st.pos} · ${up(t("a_" + st.arch))} · ${t("card_pick", { ord: up(ord(st.pick)) })} · ${t("card_seasons", { n: x.seasons })}`, K.W / 2, 432, { weight: 800, size: 26, color: K.C.muted, align: "center" });
      [[x.ppg.toFixed(1), "PPG"], [x.rpg.toFixed(1), "RPG"], [x.apg.toFixed(1), "APG"]].forEach(([v, l], i) => {
        const cx = K.W / 2 + (i - 1) * 300;
        K.text(g, v, cx, 560, { weight: 900, size: 96, align: "center" });
        K.text(g, l, cx, 606, { weight: 800, size: 28, color: K.C.muted, align: "center" });
      });
      const rows = ["ring", "mvp", "fmvp", "as", "allnba", "dpoy", "roy", "scoring"].filter((k) => a[k]).slice(0, 6);
      rows.forEach((k, i) => {
        const col = i % 2, row = Math.floor(i / 2), bx = 140 + col * 420, by = 700 + row * 96;
        K.rr(g, bx, by, 380, 76, 18); g.fillStyle = "rgba(255,255,255,.07)"; g.fill();
        K.text(g, `${a[k]}x`, bx + 28, by + 52, { weight: 900, size: 40, color: k === "ring" || k === "mvp" ? K.C.gold : "#fff" });
        K.text(g, t("cd_" + k), bx + 120, by + 49, { weight: 800, size: 24 });
      });
      const y2 = 700 + Math.max(1, Math.ceil(rows.length / 2)) * 96 + 40;
      K.text(g, money(earned), K.W / 2 - 220, y2 + 60, { weight: 900, size: 64, align: "center", color: K.C.gold });
      K.text(g, t("card_earn"), K.W / 2 - 220, y2 + 100, { weight: 800, size: 24, color: K.C.muted, align: "center" });
      K.text(g, `${H.p}%`, K.W / 2 + 220, y2 + 60, { weight: 900, size: 64, align: "center" });
      K.text(g, t("card_hof"), K.W / 2 + 220, y2 + 100, { weight: 800, size: 24, color: K.C.muted, align: "center" });
      K.footer(g, "/career", t("card_tag"));
      await K.share(cv, { filename: "my-nba-career.png", text, title: t("card_title") });
    } catch (err) {
      try { await navigator.clipboard.writeText(text); toast(t("copied")); } catch (e2) { window.prompt("Copy:", text); }
    } finally { if (btn) btn.classList.remove("is-loading"); }
  }

  // ---------------- tiklamalar ----------------
  app.addEventListener("click", (e) => {
    const lb = e.target.closest("[data-lang]");
    if (lb) { LANG = lb.dataset.lang; save(LANG_KEY, LANG); if (window.gtag) gtag("event", "career_lang", { lang: LANG }); return render(); }
    if (!st || st.phase === "draft" || st.phase === "end") return;     // kendi isleyicileri var
    const o = e.target.closest("[data-opt]");
    if (o && st.pending) return choose(+o.dataset.opt);
    if (e.target.closest("#cr-play")) { st.lastSeason = null; return playSeason(); }
    if (e.target.closest("#cr-quit") && confirm(t("quit_confirm"))) { st = null; save(KEY, null); render(); }
  });
  // Ekranlar kendi app.onclick'ini kurar; ana ekran icin bosalt
  const baseRender = render;
  render = function () { app.onclick = null; baseRender(); };      // eslint-disable-line no-func-assign
  render();
})();
