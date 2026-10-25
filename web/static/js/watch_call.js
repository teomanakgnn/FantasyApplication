// Watch party sesli sohbet + ekran paylasimi (WebRTC, herkes herkese bagli).
// Sunucu (/ws/watch/{mac}) yalnizca sinyal tasir; ses ve goruntu dogrudan
// tarayicilar arasinda gider. "Perfect negotiation" kalibi: iki taraf ayni
// anda teklif yaparsa kibar olan (sonradan gelen) geri cekilir.
(function () {
  const { $, toast, escapeHtml: h } = window.HL;
  const root = $(".wp-room");
  if (!root || !window.RTCPeerConnection) {
    const c = $("#wp-call");
    if (c) c.querySelector(".wp-ctrls").innerHTML = '<span class="dim small">Voice needs a newer browser.</span>';
    return;
  }
  const game = root.dataset.game, k = root.dataset.k;
  const ice = JSON.parse(root.dataset.ice || "[]");
  const canShare = !!(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia);

  let ws = null, myId = null, left = true, retries = 0, pingTimer = null;
  let mic = null, screen = null, audioCtx = null, stageOwner = null;
  const peers = new Map();   // id -> {name, mic, sharing, pc, polite, makingOffer, ignoreOffer}
  const meters = new Map();  // ses seviyesi: anahtar -> {analyser, data, peer}

  const btn = (id) => $("#" + id);
  const show = (id, on) => { btn(id).hidden = !on; };

  // ---------------- sinyal ----------------
  function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws/watch/${game}?k=${encodeURIComponent(k)}`);
    ws.onmessage = (e) => onSignal(JSON.parse(e.data));
    ws.onopen = () => {
      retries = 0;
      clearInterval(pingTimer);
      pingTimer = setInterval(() => send({ type: "ping" }), 25000);
    };
    ws.onclose = (e) => {
      clearInterval(pingTimer);
      [...peers.keys()].forEach(dropPeer);
      renderPeople();
      if (left) return;
      if (e.code === 4403) { toast("Pick a name or use the invite link to join.", true); return leave(); }
      if (e.code === 4409) { toast("You joined from another tab.", true); return leave(); }
      if (retries++ < 8) setTimeout(() => { if (!left) connect(); }, 1500 * retries);
      else { toast("Voice connection lost.", true); leave(); }
    };
  }
  const send = (m) => { if (ws && ws.readyState === 1) ws.send(JSON.stringify(m)); };
  const sendState = () => send({ type: "state", mic: !!(mic && mic.getAudioTracks()[0]?.enabled), sharing: !!screen });

  function onSignal(m) {
    if (m.type === "welcome") {
      myId = m.id;
      m.peers.forEach(addPeer);
      sendState();
    } else if (m.type === "join") {
      addPeer(m);
    } else if (m.type === "leave") {
      dropPeer(m.id);
    } else if (m.type === "state") {
      const p = peers.get(m.id);
      if (p) { p.mic = m.mic; p.sharing = m.sharing; if (!m.sharing && stageOwner === m.id) hideStage(); }
    } else if (m.type === "signal") {
      handle(m.from, m.data);
    } else if (m.type === "full") {
      toast(`Voice room is full (${m.limit} people).`, true);
    }
    renderPeople();
  }

  // ---------------- esler ----------------
  function addPeer(info) {
    if (peers.has(info.id)) return;
    const pc = new RTCPeerConnection({ iceServers: ice });
    const p = { name: info.name, mic: info.mic, sharing: info.sharing, pc,
                polite: Number(myId) > Number(info.id), makingOffer: false, ignoreOffer: false };
    peers.set(info.id, p);
    pc.onicecandidate = (e) => { if (e.candidate) send({ type: "signal", to: info.id, data: { candidate: e.candidate } }); };
    pc.onnegotiationneeded = async () => {
      try {
        p.makingOffer = true;
        await pc.setLocalDescription();
        send({ type: "signal", to: info.id, data: { description: pc.localDescription } });
      } catch (err) { console.warn(err); } finally { p.makingOffer = false; }
    };
    pc.ontrack = (e) => onTrack(info.id, e);
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "failed") {
        if (!p.warned) { p.warned = true; toast(`Couldn't connect audio with ${p.name} - one of your networks blocks direct connections. Retrying...`, true); }
        pc.restartIce();
      }
      if (pc.connectionState === "connected") p.warned = false;
      renderPeople();
    };
    if (mic) mic.getTracks().forEach((t) => pc.addTrack(t, mic));
    if (screen) screen.getTracks().forEach((t) => tuneVideo(pc.addTrack(t, screen), t, pc));
  }

  async function handle(from, { description, candidate }) {
    const p = peers.get(from);
    if (!p) return;
    const pc = p.pc;
    try {
      if (description) {
        const collision = description.type === "offer" && (p.makingOffer || pc.signalingState !== "stable");
        p.ignoreOffer = !p.polite && collision;
        if (p.ignoreOffer) return;
        await pc.setRemoteDescription(description);
        if (description.type === "offer") {
          await pc.setLocalDescription();
          send({ type: "signal", to: from, data: { description: pc.localDescription } });
        }
      } else if (candidate) {
        try { await pc.addIceCandidate(candidate); } catch (err) { if (!p.ignoreOffer) throw err; }
      }
    } catch (err) { console.warn("signal", err); }
  }

  function dropPeer(id) {
    const p = peers.get(id);
    if (!p) return;
    try { p.pc.close(); } catch (e) { /* zaten kapali */ }
    peers.delete(id);
    document.querySelectorAll(`#wp-audio [data-peer="${id}"]`).forEach((a) => a.remove());
    for (const [key, g] of gains) if (g.peer === id) { try { g.gain.disconnect(); } catch (e) { /* yok */ } gains.delete(key); }
    for (const [key, m] of meters) if (m.peer === id) meters.delete(key);
    if (stageOwner === id) hideStage();
  }

  // ---------------- gelen ses / goruntu ----------------
  // ---------------- kisi basina ses ----------------
  // Her uzak ses akisi bir GainNode'dan gecer. <audio> ogesi sessiz calar (Chrome
  // uzak WebRTC sesini ancak bir ogeye bagliyken Web Audio'ya verir); duyulan ses
  // kazanc dugumunden. Ayarlar kisi adiyla bu tarayicida saklanir.
  const gains = new Map();                 // stream.id -> {gain, peer, stream}
  const VOL = "hl_wp_vol";
  const vols = (() => { try { return JSON.parse(localStorage.getItem(VOL)) || {}; } catch (e) { return {}; } })();
  const saveVols = () => { try { localStorage.setItem(VOL, JSON.stringify(vols)); } catch (e) { /* yok */ } };
  const isScreen = (stream) => stream.getVideoTracks().length > 0;
  const volKey = (peerId, screen) => `${screen ? "screen" : "voice"}:${(peers.get(peerId) || {}).name || peerId}`;
  function applyVolumes() {
    for (const g of gains.values()) {
      const v = vols[volKey(g.peer, isScreen(g.stream))] || { level: 1, muted: false };
      g.gain.gain.value = v.muted ? 0 : v.level;
    }
  }
  function renderVolumes() {
    const box = $("#wp-vol");
    if (!box || box.hidden) return;
    const rows = [];
    for (const [id, p] of peers) {
      rows.push({ key: volKey(id, false), label: p.name });
      if (p.sharing) rows.push({ key: volKey(id, true), label: `${p.name} - shared screen sound` });
    }
    box.innerHTML = rows.length ? rows.map((r) => {
      const v = vols[r.key] || { level: 1, muted: false };
      return `<div class="wp-vrow" data-key="${h(r.key)}"><b>${h(r.label)}</b>
        <input type="range" min="0" max="150" step="5" value="${Math.round(v.level * 100)}" aria-label="Volume for ${h(r.label)}">
        <span class="wp-vpct">${v.muted ? "muted" : Math.round(v.level * 100) + "%"}</span>
        <button type="button" class="btn btn-sm ${v.muted ? "btn-primary" : "btn-ghost"}" data-mute>${v.muted ? "Unmute" : "Mute"}</button></div>`;
    }).join("") : '<span class="dim small">Nobody else in the voice room yet.</span>';
  }

  function onTrack(id, e) {
    const stream = e.streams[0] || new MediaStream([e.track]);
    if (e.track.kind === "audio") {
      let a = document.querySelector(`#wp-audio audio[data-stream="${stream.id}"]`);
      if (!a) {
        a = document.createElement("audio");
        a.autoplay = true;
        a.dataset.stream = stream.id;
        a.dataset.peer = id;
        $("#wp-audio").appendChild(a);
      }
      a.srcObject = stream;
      if (audioCtx && !gains.has(stream.id)) {
        try {
          const src = audioCtx.createMediaStreamSource(stream);
          const gain = audioCtx.createGain();
          src.connect(gain).connect(audioCtx.destination);
          gains.set(stream.id, { gain, peer: id, stream });
          a.muted = true;                            // duyulan ses kazanc dugumunden
          applyVolumes();
        } catch (err) { a.muted = false; }
      }
      a.play().catch(() => show("wp-unmute-video", true));
      meter(stream.id, stream, id);
    } else {
      showStage(id, stream);
      const off = () => { if (stageOwner === id && !stream.getVideoTracks().some((t) => t.readyState === "live" && !t.muted)) hideStage(); };
      e.track.onended = off;
      e.track.onmute = off;
      e.track.onunmute = () => showStage(id, stream);
      stream.onremovetrack = off;
    }
  }

  function showStage(id, stream) {
    const v = $("#wp-video");
    stageOwner = id;
    if (v.srcObject !== stream) v.srcObject = stream;
    v.play().catch(() => {});
    const who = id === "me" ? "You are sharing your screen" : `${(peers.get(id) || {}).name || "Someone"} is sharing`;
    $("#wp-stage-who").textContent = who;
    $("#wp-stage").hidden = false;
  }
  function hideStage() {
    stageOwner = null;
    $("#wp-stage").hidden = true;
    $("#wp-video").srcObject = null;
  }

  // ---------------- konusuyor gostergesi ----------------
  function meter(key, stream, peer) {
    if (!audioCtx || meters.has(key)) return;
    try {
      const src = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      src.connect(analyser);
      meters.set(key, { analyser, data: new Uint8Array(analyser.fftSize), peer, stream });
    } catch (e) { /* bazi tarayicilar desteklemiyor */ }
  }
  setInterval(() => {
    if (left) return;
    const loud = new Set();
    for (const m of meters.values()) {
      if (m.stream.getVideoTracks().length) continue;  // ekran paylasimi sesi konusma sayilmaz
      m.analyser.getByteTimeDomainData(m.data);
      let sum = 0;
      for (const v of m.data) sum += (v - 128) * (v - 128);
      if (Math.sqrt(sum / m.data.length) > 6) loud.add(m.peer);
    }
    document.querySelectorAll(".wp-person").forEach((el) => el.classList.toggle("speaking", loud.has(el.dataset.id)));
  }, 150);

  // ---------------- kisiler ----------------
  function renderPeople() {
    renderVolumesIfChanged();
    const box = $("#wp-people");
    if (left) { box.innerHTML = '<span class="dim small">Voice room · join to talk and watch together</span>'; return; }
    const meMic = !!(mic && mic.getAudioTracks()[0]?.enabled);
    const chip = (id, name, micOn, sharing, state) => `
      <span class="wp-person ${state === "connecting" ? "connecting" : ""} ${state === "failed" || state === "disconnected" ? "lost" : ""}" data-id="${id}" title="${state || ""}">
        <i>${h(name.slice(0, 1).toUpperCase())}</i><b>${h(name)}</b><em>${state === "connecting" ? "connecting..." : state === "failed" ? "no connection" : state === "disconnected" ? "reconnecting..." : micOn ? "mic" : "muted"}${sharing ? " · sharing" : ""}</em></span>`;
    box.innerHTML = chip("me", "You", meMic, !!screen) +
      [...peers.entries()].map(([id, p]) => {
        const st = p.pc.connectionState;
        return chip(id, p.name, p.mic, p.sharing, st === "connected" || st === "new" ? "" : st === "connecting" ? "connecting" : st);
      }).join("");
  }

  let volSig = "";
  function renderVolumesIfChanged() {
    const sig = [...peers.entries()].map(([id, p]) => `${id}:${p.sharing ? 1 : 0}`).join(",");
    if (sig !== volSig) { volSig = sig; renderVolumes(); }   // kaydirirken yeniden cizilmesin
    applyVolumes();
  }

  // ---------------- canli kalite (sorun kimde?) ----------------
  // Paylasan: gonderilen cozunurluk / fps / Mbps ve tarayicinin kaliteyi dusurme nedeni
  // (bandwidth = paylasanin yukleme hizi yetmiyor, cpu = bilgisayar yetismiyor).
  // Izleyen: alinan cozunurluk / fps / Mbps, paket kaybi (izleyenin agi) ve aktarma (relay).
  const lastBytes = new Map();
  const REASON = { bandwidth: "your upload speed", cpu: "your computer (CPU)", other: "the browser", none: "" };
  async function qualityTick() {
    const el = $("#wp-stage-q");
    if (!el || left || $("#wp-stage").hidden) return;
    const now = performance.now();
    if (screen) {
      const v = screen.getVideoTracks()[0];
      let worst = null;
      for (const [id, p] of peers) {
        const sender = p.pc.getSenders().find((s) => s.track === v);
        if (!sender) continue;
        tuneVideo(sender, v);
        const st = await sender.getStats().catch(() => null);
        st && st.forEach((r) => {
          if (r.type !== "outbound-rtp" || r.kind !== "video") return;
          const prev = lastBytes.get("o" + id), mbps = prev ? ((r.bytesSent - prev.b) * 8) / ((now - prev.t) * 1000) : 0;
          lastBytes.set("o" + id, { b: r.bytesSent, t: now });
          const row = { w: r.frameWidth || 0, h: r.frameHeight || 0, fps: Math.round(r.framesPerSecond || 0), mbps, why: r.qualityLimitationReason || "none" };
          if (!worst || row.h < worst.h) worst = row;
        });
      }
      el.textContent = worst ? `Sending ${worst.w}x${worst.h} · ${worst.fps} fps · ${worst.mbps.toFixed(1)} Mbps per viewer`
        + (REASON[worst.why] ? ` · held back by ${REASON[worst.why]}` : "") : "Sending...";
      el.className = worst && worst.why !== "none" ? "warn" : "";
      return;
    }
    const p = peers.get(stageOwner);
    if (!p) return;
    const st = await p.pc.getStats().catch(() => null);
    if (!st) return;
    let row = null, relay = false;
    st.forEach((r) => {
      if (r.type === "inbound-rtp" && r.kind === "video") {
        const prev = lastBytes.get("i"), mbps = prev ? ((r.bytesReceived - prev.b) * 8) / ((now - prev.t) * 1000) : 0;
        const lostPct = prev ? (100 * (r.packetsLost - prev.l)) / Math.max(1, (r.packetsReceived - prev.r) + (r.packetsLost - prev.l)) : 0;
        lastBytes.set("i", { b: r.bytesReceived, t: now, l: r.packetsLost, r: r.packetsReceived });
        row = { w: r.frameWidth || 0, h: r.frameHeight || 0, fps: Math.round(r.framesPerSecond || 0), mbps, lost: Math.max(0, lostPct) };
      }
      if (r.type === "candidate-pair" && r.nominated && r.state === "succeeded") {
        const l = st.get(r.localCandidateId), rm = st.get(r.remoteCandidateId);
        relay = (l && l.candidateType === "relay") || (rm && rm.candidateType === "relay");
      }
    });
    if (!row) return;
    el.textContent = `Receiving ${row.w}x${row.h} · ${row.fps} fps · ${row.mbps.toFixed(1)} Mbps${row.lost >= 2 ? ` · ${row.lost.toFixed(0)}% packets lost (your connection)` : ""}${relay ? " · via relay" : ""}`;
    el.className = row.lost >= 2 || row.h && row.h < 540 ? "warn" : "";
  }
  setInterval(qualityTick, 2000);

  // ---------------- dugmeler ----------------
  async function join() {
    if (!left) return;
    if (window.HL_WP_NEEDS_NAME && window.HL_WP_NEEDS_NAME()) {
      const box = document.getElementById("wp-name");
      if (box) { box.hidden = false; document.getElementById("wp-name-input").focus(); }
      return toast("Pick a name first.", true);
    }
    left = false;
    try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { audioCtx = null; }
    connect();
    show("wp-join", false); show("wp-mic", true); show("wp-leave", true); show("wp-share", canShare); show("wp-volbtn", true);
    renderMic();
    renderPeople();
  }

  function leave() {
    left = true;
    if (ws) { try { ws.close(); } catch (e) { /* yok */ } }
    [...peers.keys()].forEach(dropPeer);
    if (mic) mic.getTracks().forEach((t) => t.stop());
    if (screen) screen.getTracks().forEach((t) => t.stop());
    mic = screen = null;
    meters.clear();
    $("#wp-audio").innerHTML = "";
    hideStage();
    if (audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
    show("wp-join", true); show("wp-mic", false); show("wp-leave", false); show("wp-share", false); show("wp-unmute-video", false);
    show("wp-volbtn", false); $("#wp-vol").hidden = true; gains.clear();
    renderShare();
    renderPeople();
  }

  function renderMic() {
    const on = !!(mic && mic.getAudioTracks()[0]?.enabled);
    btn("wp-mic").textContent = on ? "Mic on" : "Mic off";
    btn("wp-mic").classList.toggle("btn-primary", on);
  }

  async function toggleMic() {
    if (!mic) {
      try {
        mic = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      } catch (e) { return toast("Microphone blocked - allow it in your browser settings.", true); }
      for (const p of peers.values()) mic.getTracks().forEach((t) => p.pc.addTrack(t, mic));
      meter("me", mic, "me");
    } else {
      const t = mic.getAudioTracks()[0];
      t.enabled = !t.enabled;
    }
    renderMic(); sendState(); renderPeople();
  }

  // Kalite modu (paylasan secer): smooth = akicilik, sharp = netlik, balanced = ikisi
  const QUALITY = { smooth: ["motion", "maintain-framerate"], balanced: ["motion", "balanced"], sharp: ["detail", "maintain-resolution"] };
  let quality = (() => { try { return localStorage.getItem("hl_wp_quality") || "balanced"; } catch (e) { return "balanced"; } })();
  // Paylasan her izleyiciye ayri kopya gonderir: toplam ~9 Mbps yukleme butcesi izleyicilere bolunur
  const perViewerBitrate = () => Math.max(1500000, Math.min(6000000, Math.round(9000000 / Math.max(1, peers.size))));

  // VP9 (yoksa H264) once: ayni bant genisliginde VP8'den belirgin net
  function preferCodecs(pc, sender) {
    try {
      const tr = pc.getTransceivers().find((t) => t.sender === sender);
      const caps = RTCRtpSender.getCapabilities && RTCRtpSender.getCapabilities("video");
      if (!tr || !tr.setCodecPreferences || !caps) return;
      const rank = (c) => (/vp9/i.test(c.mimeType) ? 0 : /h264/i.test(c.mimeType) ? 1 : /vp8/i.test(c.mimeType) ? 2 : 3);
      tr.setCodecPreferences([...caps.codecs].sort((a, b) => rank(a) - rank(b)));
    } catch (e) { /* desteklenmiyor */ }
  }

  // Bit hizi ve oncelik; muzakere bitmeden ayarlanamadigi icin istatistik dongusunde de yenilenir
  function tuneVideo(sender, track, pc) {
    if (!track || track.kind !== "video") return;
    if (pc) preferCodecs(pc, sender);
    try {
      const prm = sender.getParameters();
      if (!prm.encodings || !prm.encodings.length) return;           // henuz muzakere edilmedi
      const want = perViewerBitrate();
      const pref = QUALITY[quality][1];
      if (prm.encodings[0].maxBitrate === want && prm.degradationPreference === pref) return;
      prm.encodings[0].maxBitrate = want;
      prm.encodings[0].maxFramerate = 30;
      prm.degradationPreference = pref;
      sender.setParameters(prm).catch(() => {});
    } catch (e) { /* desteklenmiyor */ }
  }

  function renderShare() {
    const q = document.getElementById("wp-quality");
    if (q) q.hidden = !screen;
    btn("wp-share").textContent = screen ? "Stop sharing" : "Share screen";
    btn("wp-share").classList.toggle("btn-primary", !!screen);
  }

  async function startShare() {
    const other = [...peers.values()].find((p) => p.sharing);
    if (other) return toast(`${other.name} is already sharing.`, true);
    try {
      screen = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: { ideal: 30, max: 30 }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
        systemAudio: "include", surfaceSwitching: "include", selfBrowserSurface: "exclude",
      });
    } catch (e) { screen = null; return; }
    const v = screen.getVideoTracks()[0];
    if (v) { v.contentHint = QUALITY[quality][0]; v.onended = stopShare; }
    if (!screen.getAudioTracks().length) toast("Shared without sound - pick a tab and tick \"share tab audio\" for game sound.", true);
    for (const p of peers.values()) screen.getTracks().forEach((t) => tuneVideo(p.pc.addTrack(t, screen), t, p.pc));
    showStage("me", screen);
    renderShare(); sendState(); renderPeople();
  }

  function stopShare() {
    if (!screen) return;
    const tracks = screen.getTracks();
    for (const p of peers.values()) {
      p.pc.getSenders().filter((s) => s.track && tracks.includes(s.track)).forEach((s) => { try { p.pc.removeTrack(s); } catch (e) { /* kapali */ } });
    }
    tracks.forEach((t) => t.stop());
    screen = null;
    if (stageOwner === "me") hideStage();
    renderShare(); sendState(); renderPeople();
  }

  btn("wp-volbtn").addEventListener("click", () => {
    const box = $("#wp-vol"); box.hidden = !box.hidden;
    btn("wp-volbtn").classList.toggle("btn-primary", !box.hidden);
    volSig = ""; renderVolumes();
  });
  $("#wp-vol").addEventListener("input", (e) => {
    const row = e.target.closest(".wp-vrow");
    if (!row || e.target.type !== "range") return;
    const v = vols[row.dataset.key] || { level: 1, muted: false };
    v.level = +e.target.value / 100; v.muted = false; vols[row.dataset.key] = v;
    row.querySelector(".wp-vpct").textContent = Math.round(v.level * 100) + "%";
    const b = row.querySelector("[data-mute]"); b.textContent = "Mute"; b.className = "btn btn-sm btn-ghost";
    applyVolumes(); saveVols();
  });
  $("#wp-vol").addEventListener("click", (e) => {
    const b = e.target.closest("[data-mute]");
    if (!b) return;
    const row = b.closest(".wp-vrow");
    const v = vols[row.dataset.key] || { level: 1, muted: false };
    v.muted = !v.muted; vols[row.dataset.key] = v;
    b.textContent = v.muted ? "Unmute" : "Mute"; b.className = `btn btn-sm ${v.muted ? "btn-primary" : "btn-ghost"}`;
    row.querySelector(".wp-vpct").textContent = v.muted ? "muted" : Math.round(v.level * 100) + "%";
    applyVolumes(); saveVols();
  });
  const qsel = document.getElementById("wp-quality");
  if (qsel) {
    qsel.value = quality;
    qsel.addEventListener("change", () => {
      quality = qsel.value;
      try { localStorage.setItem("hl_wp_quality", quality); } catch (e) { /* yok */ }
      const v = screen && screen.getVideoTracks()[0];
      if (v) v.contentHint = QUALITY[quality][0];
      for (const p of peers.values()) p.pc.getSenders().filter((s) => s.track === v).forEach((s) => tuneVideo(s, v));
    });
  }
  btn("wp-join").addEventListener("click", join);
  btn("wp-leave").addEventListener("click", leave);
  btn("wp-mic").addEventListener("click", toggleMic);
  btn("wp-share").addEventListener("click", () => (screen ? stopShare() : startShare()));
  btn("wp-unmute-video").addEventListener("click", () => {
    document.querySelectorAll("#wp-audio audio").forEach((a) => a.play().catch(() => {}));
    if (audioCtx && audioCtx.state === "suspended") audioCtx.resume();
    show("wp-unmute-video", false);
  });
  btn("wp-full").addEventListener("click", () => {
    const stage = $("#wp-stage"), v = $("#wp-video");
    if (document.fullscreenElement) document.exitFullscreen();
    else if (stage.requestFullscreen) stage.requestFullscreen().catch(() => {});
    else if (v.webkitEnterFullscreen) v.webkitEnterFullscreen();
  });
  window.addEventListener("pagehide", () => { if (!left) leave(); });
  renderPeople();
})();
