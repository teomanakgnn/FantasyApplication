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
      if (e.code === 4403) { toast("You are not in this room.", true); return leave(); }
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
      if (pc.connectionState === "failed") pc.restartIce();
      renderPeople();
    };
    if (mic) mic.getTracks().forEach((t) => pc.addTrack(t, mic));
    if (screen) screen.getTracks().forEach((t) => tuneVideo(pc.addTrack(t, screen), t));
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
    for (const [key, m] of meters) if (m.peer === id) meters.delete(key);
    if (stageOwner === id) hideStage();
  }

  // ---------------- gelen ses / goruntu ----------------
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
    const box = $("#wp-people");
    if (left) { box.innerHTML = '<span class="dim small">Voice room · join to talk and watch together</span>'; return; }
    const meMic = !!(mic && mic.getAudioTracks()[0]?.enabled);
    const chip = (id, name, micOn, sharing, state) => `
      <span class="wp-person ${state === "connecting" ? "connecting" : ""}" data-id="${id}" title="${state || ""}">
        <i>${h(name.slice(0, 1).toUpperCase())}</i><b>${h(name)}</b><em>${micOn ? "mic" : "muted"}${sharing ? " · sharing" : ""}</em></span>`;
    box.innerHTML = chip("me", "You", meMic, !!screen) +
      [...peers.entries()].map(([id, p]) => {
        const st = p.pc.connectionState;
        return chip(id, p.name, p.mic, p.sharing, st === "connected" || st === "new" ? "" : st === "connecting" ? "connecting" : st);
      }).join("");
  }

  // ---------------- dugmeler ----------------
  async function join() {
    if (!left) return;
    left = false;
    try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { audioCtx = null; }
    connect();
    show("wp-join", false); show("wp-mic", true); show("wp-leave", true); show("wp-share", canShare);
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

  function tuneVideo(sender, track) {
    if (track.kind !== "video") return;
    try {
      const prm = sender.getParameters();
      if (!prm.encodings || !prm.encodings.length) prm.encodings = [{}];
      prm.encodings[0].maxBitrate = 2500000;
      prm.degradationPreference = "maintain-framerate";
      sender.setParameters(prm).catch(() => {});
    } catch (e) { /* desteklenmiyor */ }
  }

  function renderShare() {
    btn("wp-share").textContent = screen ? "Stop sharing" : "Share screen";
    btn("wp-share").classList.toggle("btn-primary", !!screen);
  }

  async function startShare() {
    const other = [...peers.values()].find((p) => p.sharing);
    if (other) return toast(`${other.name} is already sharing.`, true);
    try {
      screen = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: { ideal: 30, max: 30 }, height: { ideal: 1080 } },
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
        systemAudio: "include", surfaceSwitching: "include", selfBrowserSurface: "exclude",
      });
    } catch (e) { screen = null; return; }
    const v = screen.getVideoTracks()[0];
    if (v) { v.contentHint = "motion"; v.onended = stopShare; }
    if (!screen.getAudioTracks().length) toast("Shared without sound - pick a tab and tick \"share tab audio\" for game sound.", true);
    for (const p of peers.values()) screen.getTracks().forEach((t) => tuneVideo(p.pc.addTrack(t, screen), t));
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
