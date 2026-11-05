// 앱 진입점: 입력 구획, 이벤트 버스, 실행 연결. 화면 모듈은 mount(ctx)로 붙는다.
import * as api from "./api.js";
import { mount as mountTimeline } from "./timeline.js";
import { mount as mountResults } from "./results.js";
import { mount as mountDrafts } from "./drafts.js";
import { mount as mountEval } from "./eval.js";
import { mount as mountAsk } from "./ask.js";
import { mount as mountMedia } from "./media.js";

const $ = (sel) => document.querySelector(sel);

const bus = new EventTarget();
const state = { runId: null, mode: "live", stream: null, cases: [], selectedCase: null };

export function emit(type, detail) {
  bus.dispatchEvent(new CustomEvent(type, { detail }));
}

function dispatchEnvelope(env) {
  if (env.run_id && env.type !== "replaced") state.runId = env.run_id;
  state.mode = env.mode || state.mode;
  $("#replay-badge").hidden = state.mode !== "replay";
  emit(env.type, env);
}

function setError(message) {
  $("#input-error").textContent = message || "";
}

export function connectRun(runId) {
  if (state.stream) state.stream.close();
  state.runId = runId;
  state.mode = "live";
  $("#replay-badge").hidden = true;
  emit("run_started", { run_id: runId });
  state.stream = api.openEvents(runId, dispatchEnvelope, (s, newId) => {
    if (s === "replaced") {
      state.runId = newId;
      emit("run_replaced", { run_id: newId });
    }
    emit("connection", { state: s });
  });
}

export async function startRun(body) {
  setError("");
  try {
    const res = await api.startRun(body);
    connectRun(res.run_id);
  } catch (e) {
    setError(e.message);
  }
}

async function loadCases() {
  const list = $("#case-list");
  try {
    state.cases = await api.getCases();
  } catch (e) {
    state.cases = [];
    list.innerHTML = "";
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "데모 사례를 불러오지 못했습니다.";
    list.append(li);
    return;
  }
  list.innerHTML = "";
  for (const c of state.cases) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("aria-pressed", "false");
    btn.dataset.caseId = c.case_id;
    const kind = { image: " · 손글씨 사진", audio: " · 방문 녹음" }[c.input_type] || "";
    btn.innerHTML = `<span class="case-title"></span><span class="case-summary"></span>`;
    btn.querySelector(".case-title").textContent = c.title + kind;
    btn.querySelector(".case-summary").textContent = c.summary;
    btn.addEventListener("click", () => selectCase(c.case_id, true));
    li.append(btn);
    list.append(li);
  }
}

function selectCase(caseId, run) {
  state.selectedCase = caseId;
  for (const b of document.querySelectorAll("#case-list button")) {
    b.setAttribute("aria-pressed", String(b.dataset.caseId === caseId));
  }
  if (run) startRun({ case_id: caseId, mode: "live" });
}

function bindInput() {
  $("#start-demo").addEventListener("click", () => {
    const first = state.selectedCase || (state.cases[0] && state.cases[0].case_id) || "case1";
    selectCase(first, true);
  });

  const toggle = $("#toggle-direct");
  const form = $("#direct-form");
  toggle.addEventListener("click", () => {
    form.hidden = !form.hidden;
    toggle.setAttribute("aria-expanded", String(!form.hidden));
    if (!form.hidden) $("#note").focus();
  });

  const note = $("#note");
  const count = $("#note-count");
  note.addEventListener("input", () => {
    count.textContent = `${note.value.length.toLocaleString()} / 4,000자`;
  });
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const text = note.value.trim();
    if (!text) return setError("상담 메모를 입력하거나 데모 사례를 고르세요");
    if (text.length > 4000) return setError(`입력이 ${text.length.toLocaleString()}자입니다. 4,000자 이하로 줄여 주세요.`);
    startRun({ note: text, mode: "live" });
  });

  $("#start-eval").addEventListener("click", () => emit("eval_requested", {}));
}

async function runFake() {
  // ?fake=1: 백엔드 없이 저장된 봉투를 흘려 화면을 확인한다.
  const res = await fetch("/static/dev/fake-events.json");
  const envelopes = await res.json();
  state.runId = envelopes[0] && envelopes[0].run_id;
  emit("run_started", { run_id: state.runId, fake: true });
  let prev = 0;
  for (const env of envelopes) {
    const wait = Math.min(1200, Math.max(0, (env.t_ms || prev) - prev));
    prev = env.t_ms || prev;
    await new Promise((r) => setTimeout(r, wait));
    dispatchEnvelope(env);
  }
}

async function main() {
  const features = await api.getFeatures();
  const ctx = { bus, api, features, state, startRun, connectRun, emit };
  for (const mount of [mountTimeline, mountResults, mountDrafts, mountEval, mountAsk, mountMedia]) {
    try { mount(ctx); } catch (e) { console.error(e); }
  }
  bindInput();
  if (new URLSearchParams(location.search).has("fake")) {
    runFake();
  } else {
    loadCases();
  }
}

main();
