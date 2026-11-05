// 사진·음성 입력 탭, 인식 결과 대조, 브라우저 녹음. 켜진 기능만 그린다.
import { escapeHtml } from "./timeline.js";

const IMAGE_MAX = 5 * 1024 * 1024;
const AUDIO_MAX = 10 * 1024 * 1024;
const RECORD_LIMIT_MS = 120000;

export function mount(ctx) {
  const { bus, api, features, connectRun, state } = ctx;
  const panel = document.getElementById("media-panel");
  const tabs = document.getElementById("input-tabs");
  const err = document.getElementById("input-error");
  const masked = document.getElementById("masked-view");
  if (!features.image_input && !features.audio_input) return;

  const modes = [{ key: "text", label: "텍스트" }];
  if (features.image_input) modes.push({ key: "image", label: "사진" });
  if (features.audio_input) modes.push({ key: "audio", label: "음성" });
  tabs.hidden = false;
  tabs.innerHTML = modes.map((m, i) => `<button type="button" role="tab" class="btn btn-small" data-mode="${m.key}" aria-selected="${i === 0}">${m.label}</button>`).join("");

  function show(mode) {
    tabs.querySelectorAll("[role=tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.mode === mode)));
    document.getElementById("direct-form").hidden = mode !== "text";
    if (mode === "image") {
      panel.innerHTML = `
        <label for="image-file">손글씨·인쇄 메모 사진(JPEG·PNG, 5MB 이하)</label>
        <input id="image-file" type="file" accept="image/jpeg,image/png">`;
      panel.querySelector("#image-file").addEventListener("change", (e) => upload(e.target.files[0], "image"));
    } else if (mode === "audio") {
      panel.innerHTML = `
        <label for="audio-file">상담 녹음(WAV·MP3·WebM, 2분·10MB 이하)</label>
        <input id="audio-file" type="file" accept="audio/wav,audio/mpeg,audio/webm,.wav,.mp3,.webm">
        ${features.browser_recording ? '<div class="form-row"><button id="rec-btn" type="button" class="btn">녹음 시작</button><span id="rec-time" class="muted"></span></div>' : ""}`;
      panel.querySelector("#audio-file").addEventListener("change", (e) => upload(e.target.files[0], "audio"));
      if (features.browser_recording) bindRecorder();
    } else {
      panel.innerHTML = "";
    }
  }

  async function upload(file, kind) {
    err.textContent = "";
    if (!file) return;
    const max = kind === "image" ? IMAGE_MAX : AUDIO_MAX;
    if (file.size > max) {
      err.textContent = kind === "image" ? "사진은 JPEG·PNG, 5MB 이하만 올릴 수 있습니다." : "녹음은 WAV·MP3·WebM, 2분·10MB 이하만 올릴 수 있습니다.";
      return;
    }
    try {
      const res = await api.startUpload(file, kind);
      connectRun(res.run_id);
    } catch (e) {
      err.textContent = e.message;
    }
  }

  function bindRecorder() {
    const btn = panel.querySelector("#rec-btn");
    const time = panel.querySelector("#rec-time");
    let rec = null;
    let timer = null;
    let started = 0;
    const stop = () => { if (rec && rec.state !== "inactive") rec.stop(); };
    btn.addEventListener("click", async () => {
      if (rec && rec.state === "recording") return stop();
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch {
        err.textContent = "녹음 권한이 없어 파일 올리기를 이용하세요";
        return;
      }
      const chunks = [];
      rec = new MediaRecorder(stream);
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        clearInterval(timer);
        stream.getTracks().forEach((t) => t.stop());
        btn.textContent = "녹음 시작";
        const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
        upload(new File([blob], "recording.webm", { type: blob.type }), "audio");
      };
      rec.start();
      started = Date.now();
      btn.textContent = "녹음 멈추기";
      timer = setInterval(() => {
        const ms = Date.now() - started;
        time.textContent = `${Math.floor(ms / 1000)}초 / 120초`;
        if (ms >= RECORD_LIMIT_MS) stop(); // 120초에서 자동 정지
      }, 250);
    });
  }

  tabs.addEventListener("click", (e) => {
    const b = e.target.closest("[role=tab]");
    if (b) show(b.dataset.mode);
  });

  bus.addEventListener("normalized", (e) => {
    const d = e.detail.data || {};
    const after = masked.querySelector(".after");
    const box = document.createElement("details");
    box.open = true;
    const edits = (d.edits || []).map((x) => `<li><del>${escapeHtml(x.original)}</del> → <ins>${escapeHtml(x.replacement)}</ins> <span class="muted">${escapeHtml(x.reason)}</span></li>`).join("");
    const unsure = (d.uncertain || []).map((u) => `<li><span class="uncertain">${escapeHtml(u)}</span> <span class="badge badge-warn">확인 필요</span></li>`).join("");
    box.innerHTML = `
      <summary><strong>인식 결과 정리</strong> <span class="badge badge-ai">AI 초안</span> ${d.skipped ? '<span class="badge badge-warn">정리 생략</span>' : ""}</summary>
      <div class="compare">
        <div><h3>인식 원문(가린 뒤)</h3><pre>${after ? after.innerHTML : ""}</pre></div>
        <div><h3>정리본</h3><textarea id="clean-note" rows="8"></textarea></div>
      </div>
      ${edits ? `<h3>바꾼 구간</h3><ul>${edits}</ul>` : ""}
      ${unsure ? `<h3>불확실 구간</h3><ul>${unsure}</ul>` : ""}
      <button type="button" class="btn" id="rerun-btn">고친 내용으로 다시 실행</button>`;
    masked.append(box);
    box.querySelector("#clean-note").value = d.clean_text || "";
    box.querySelector("#rerun-btn").addEventListener("click", () => {
      ctx.startRun({ note: box.querySelector("#clean-note").value, mode: "live", origin_run_id: state.runId });
    });
  });
}
