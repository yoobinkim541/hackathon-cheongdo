"use strict";

// ---------- constants ----------

const MAX_TEXT = 4000;
const MAX_IMAGE = 5 * 1024 * 1024;
const MAX_AUDIO = 10 * 1024 * 1024;
const MAX_REC_SECONDS = 120;

const STEP_LABELS = {
  input_router: "입력 분기",
  ocr: "사진 인식",
  stt: "음성 전사",
  intake: "개인정보 가리기",
  normalizer: "메모 정리",
  profiler: "사실 구조화",
  match_living: "생계·주거 매칭",
  match_health: "건강·의료 매칭",
  match_care: "돌봄·고립·일자리 매칭",
  verifier: "근거 검증",
  documenter: "문서 초안",
  referral_gate: "승인 대기",
};
const STEP_ORDER = Object.keys(STEP_LABELS);
const MATCH_STEPS = ["match_living", "match_health", "match_care"];

const STATUS_LABELS = { pending: "대기", running: "진행", done: "완료", failed: "실패", retry: "재시도" };
const STATUS_BADGE = { pending: "badge-neutral", running: "badge-run", done: "badge-ok", failed: "badge-fail", retry: "badge-warn" };

const RUN_STATUS = {
  running: ["진행 중", "badge-run"],
  awaiting_approval: ["승인 대기", "badge-warn"],
  resuming: ["확정 처리 중", "badge-run"],
  finalized: ["확정", "badge-ok"],
  drafted: ["초안", "badge-neutral"],
  failed: ["실패", "badge-fail"],
  expired: ["만료", "badge-fail"],
};

const INPUT_TYPE_LABELS = { text: "텍스트", image: "사진", audio: "음성" };
const DOMAIN_LABELS = { living: "생계·주거", health: "건강·의료", care: "돌봄·고립·일자리" };
const MASK_KIND_LABELS = { rrn: "주민등록번호", phone: "전화번호", account: "계좌번호", address: "주소", name: "이름" };
const FIELD_LABELS = {
  age: "나이",
  household_type: "가구 유형",
  household_size: "가구원 수",
  monthly_income_krw: "월 소득",
  assets_krw: "재산",
  disability: "장애 정도",
  chronic_illness: "만성 질환",
  housing: "주거 형태",
  monthly_rent_krw: "월세",
  caregiver_available: "보호자 유무",
  isolation_signals: "고립 신호",
  crisis_events: "위기 사건",
  missing_fields: "알 수 없는 필드",
};
const ERROR_LABELS = {
  rate_limit: "요청이 많습니다. 잠시 뒤 다시 시도하세요.",
  timeout: "응답 시간이 초과되었습니다.",
  tool_missing: "필요한 도구 호출이 없었습니다.",
  pii_residual: "가린 뒤에도 개인정보 형태가 남아 실행을 멈췄습니다.",
  input_invalid: "입력을 확인하세요.",
  ai_unavailable: "사진·녹음을 읽지 못했습니다. 텍스트로 입력하거나 다시 올려 주세요",
  copilot_unavailable: "AI 실행 환경을 사용할 수 없습니다.",
  other: "처리 중 오류가 발생했습니다.",
  media_invalid: "지원하지 않는 파일 형식이거나 크기 한도를 넘었습니다.",
  run_not_found: "실행을 찾을 수 없거나 만료되었습니다.",
  run_forbidden: "이 실행에 접근할 권한이 없습니다.",
  state_conflict: "현재 상태에서는 처리할 수 없습니다.",
  rate_limited: "요청이 많습니다. 잠시 뒤 다시 시도하세요.",
  payload_too_large: "입력이 너무 큽니다. 한도를 확인하세요.",
};
const SECTION_ORDER = [
  "record.basic_info", "record.summary", "record.needs", "record.linked_schemes", "record.follow_up",
  "referral.agency", "referral.subject", "referral.schemes", "referral.officer",
];

const RUN_EVENT_TYPES = [
  "run_started", "step_started", "step_completed", "step_failed", "step_retry", "transcribed", "masked",
  "normalized", "profile", "token", "tool_call", "tool_result", "usage", "verified", "draft",
  "approval_required", "finalized", "approval_kept", "error", "done",
];
const EVAL_EVENT_TYPES = ["case_started", "case_completed", "eval_summary", "error", "done"];

// ---------- state ----------

const app = {
  cases: [],
  schemes: {},
  copilotReady: true,
  inputTab: "text",
  recordedFile: null,
  recorder: null,
  recTimer: null,
  run: null,
  evalRun: null,
};

function newRunState(runId, opts) {
  return {
    runId,
    caseId: opts.caseId || null,
    isDemo: Boolean(opts.caseId),
    fellBack: Boolean(opts.fellBack),
    retry: opts.retry || null,
    mode: opts.mode || "live",
    source: opts.source || "text",
    es: null,
    seen: new Set(),
    steps: {},
    decisions: {},
    verified: null,
    verifiedItems: {},
    draftOriginal: {},
    pendingRequestId: null,
    approvalSchemeIds: [],
    documentsSummary: [],
    transcribed: null,
    maskedAfter: null,
    normalized: null,
    finished: false,
    reconnectTries: 0,
  };
}

// ---------- DOM helpers ----------

const $ = (id) => document.getElementById(id);

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

function badge(text, cls) {
  return el("span", { class: `badge ${cls}`, text });
}

function announce(text) {
  const region = $("live-region");
  region.textContent = "";
  window.setTimeout(() => { region.textContent = text; }, 50);
}

function fmtNumber(n) {
  return typeof n === "number" ? n.toLocaleString("ko-KR") : "-";
}

function fmtPct(v, digits = 0) {
  return typeof v === "number" ? `${(v * 100).toFixed(digits)}%` : "-";
}

function fieldLabel(name) {
  return FIELD_LABELS[name] || name;
}

function countOf(v) {
  if (Array.isArray(v)) return v.length;
  return typeof v === "number" ? v : 0;
}

function shortJson(value, limit = 160) {
  let text;
  try { text = typeof value === "string" ? value : JSON.stringify(value); } catch { text = String(value); }
  return text && text.length > limit ? `${text.slice(0, limit)}…` : (text || "");
}

// ---------- HTTP ----------

async function api(path, options = {}) {
  const opts = { ...options, credentials: "same-origin" };
  if ((opts.method || "GET").toUpperCase() !== "GET") {
    opts.headers = { ...(opts.headers || {}), "X-Requested-With": "dongheng" };
  }
  const res = await fetch(path, opts);
  let body = null;
  try { body = await res.json(); } catch { body = null; }
  if (!res.ok) {
    const err = body && body.error ? body.error : { code: "other", message: `요청이 실패했습니다 (${res.status})` };
    let message = err.message || ERROR_LABELS[err.code] || ERROR_LABELS.other;
    if (res.status === 429 || err.code === "rate_limited") {
      const wait = res.headers.get("Retry-After");
      message = `요청이 많습니다. 잠시 뒤 다시 시도하세요.${wait ? ` (${wait}초 뒤 가능)` : ""}`;
    }
    const error = new Error(message);
    error.code = err.code || "other";
    error.status = res.status;
    throw error;
  }
  return body;
}

function postJson(path, payload) {
  return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
}

// ---------- screens ----------

function showScreen(name) {
  for (const id of ["home", "direct", "run", "eval"]) $(id).hidden = id !== name;
  if (name !== "run") closeRunStream();
  if (name !== "eval") closeEvalStream();
  if (name === "home") $("replay-badge").hidden = true;
  window.scrollTo(0, 0);
}

function closeRunStream() {
  if (app.run && app.run.es) { app.run.es.close(); app.run.es = null; }
}

function closeEvalStream() {
  if (app.evalRun && app.evalRun.es) { app.evalRun.es.close(); app.evalRun.es = null; }
}

// ---------- home ----------

async function loadReadiness() {
  try {
    const ready = await api("/readyz");
    app.copilotReady = ready && ready.copilot_ready !== false;
  } catch {
    app.copilotReady = false;
  }
  const notice = $("ready-notice");
  if (!app.copilotReady) {
    notice.textContent = "AI 실행 환경이 준비되지 않아 데모 사례는 저장된 실행을 재생합니다. 직접 입력은 준비된 뒤 이용할 수 있습니다.";
    notice.hidden = false;
  } else {
    notice.hidden = true;
  }
}

async function loadSchemes() {
  try {
    const list = await api("/api/schemes");
    for (const s of list || []) app.schemes[s.id] = s;
  } catch {
    // Evidence panel falls back to decision source_url when schemes are unavailable.
  }
}

async function loadCases() {
  const list = $("case-list");
  try {
    app.cases = await api("/api/cases");
  } catch (e) {
    $("case-error").textContent = `사례 목록을 불러오지 못했습니다: ${e.message}`;
    $("case-error").hidden = false;
    return;
  }
  clear(list);
  app.cases.forEach((c) => list.append(renderCaseCard(c)));
}

function mediaPreview(type, url, label) {
  if (!url || !/^\/samples\/[^/]+$/.test(url)) return null;
  if (type === "image") return el("img", { class: "preview-img", src: url, alt: `${label} 사진 미리보기`, loading: "lazy" });
  if (type === "audio") return el("audio", { controls: true, preload: "none", src: url, "aria-label": `${label} 녹음 미리듣기` });
  return null;
}

function renderCaseCard(c) {
  const typeLabel = INPUT_TYPE_LABELS[c.input_type] || c.input_type;
  return el("li", { class: "case-card" },
    el("div", { class: "row-between" },
      el("span", { class: "case-title", text: c.title }),
      badge(typeLabel, "badge-neutral")),
    c.household ? el("span", { class: "case-meta", text: c.household }) : null,
    mediaPreview(c.input_type, c.media_url, c.title),
    el("button", { type: "button", class: "btn btn-secondary", onclick: () => startDemo(c.id), text: "이 사례로 실행" }));
}

function startFirstDemo() {
  if (app.cases.length) startDemo(app.cases[0].id);
  else $("case-list").scrollIntoView();
}

// ---------- run start ----------

async function startDemo(caseId, forceReplay = false) {
  const mode = forceReplay || !app.copilotReady ? "replay" : "live";
  const c = app.cases.find((x) => x.id === caseId);
  try {
    const res = await postJson("/api/runs", { case_id: caseId, mode });
    beginRun(res.run_id, { caseId, mode: res.mode || mode, source: c ? c.input_type : "text", fellBack: mode === "replay" });
  } catch (e) {
    if (mode === "live") {
      startDemo(caseId, true);
      return;
    }
    showScreen("home");
    $("case-error").textContent = `사례를 시작하지 못했습니다: ${e.message}`;
    $("case-error").hidden = false;
  }
}

async function submitDirect(builder, source) {
  const btn = $("btn-submit");
  btn.disabled = true;
  try {
    const res = await api("/api/runs", builder());
    beginRun(res.run_id, { mode: res.mode || "live", source, retry: { builder, source } });
  } catch (e) {
    paneMsg(source).textContent = e.message;
    paneMsg(source).classList.add("msg-error");
  } finally {
    btn.disabled = false;
  }
}

function beginRun(runId, opts) {
  closeRunStream();
  app.run = newRunState(runId, opts);
  resetRunView();
  showScreen("run");
  renderInputSummary();
  connectRun();
}

// ---------- run view reset ----------

function resetRunView() {
  const run = app.run;
  $("run-id-text").textContent = run.runId;
  $("trace-id").textContent = "-";
  $("replay-badge").hidden = run.mode !== "replay";
  setRunStatus("running");
  $("run-kept").hidden = true;
  $("reconnect").hidden = true;
  $("run-error").hidden = true;
  $("mask-view").hidden = true;
  $("recog-view").hidden = true;
  $("verified-view").hidden = true;
  $("evidence").hidden = true;
  $("draft-view").hidden = true;
  $("final-view").hidden = true;
  $("result-empty").hidden = false;
  $("btn-approve-open").disabled = true;
  $("rerun-msg").textContent = "";
  renderTimeline();
}

function setRunStatus(status) {
  const [text, cls] = RUN_STATUS[status] || [status, "badge-neutral"];
  const node = $("run-status");
  node.textContent = text;
  node.className = `badge ${cls}`;
}

function renderInputSummary() {
  const run = app.run;
  const box = clear($("input-summary"));
  const c = run.caseId ? app.cases.find((x) => x.id === run.caseId) : null;
  const dl = el("dl", { class: "summary-dl" });
  const add = (k, v) => { if (v) dl.append(el("dt", { text: k }), el("dd", { text: v })); };
  add("입력 방식", INPUT_TYPE_LABELS[run.source] || run.source);
  if (c) {
    add("데모 사례", c.title);
    add("가구", c.household);
  } else {
    add("구분", "직접 입력");
  }
  box.append(dl);
  if (c) {
    const preview = mediaPreview(c.input_type, c.media_url, c.title);
    if (preview) box.append(preview);
  }
  box.append(el("div", { id: "profile-view" }));
}

// ---------- timeline ----------

function renderTimeline() {
  const list = clear($("timeline"));
  const steps = app.run.steps;
  const visible = STEP_ORDER.filter((id) => isStepVisible(id));
  let parallel = null;
  for (const id of visible) {
    if (!steps[id]) steps[id] = { status: "pending", ms: null, startedAt: null, tokens: "", chips: [], usage: null, error: null, retries: 0 };
    const node = el("li", { class: "step", id: `step-${id}` });
    if (MATCH_STEPS.includes(id)) {
      if (!parallel) {
        parallel = el("ol", { class: "parallel", "aria-label": "분야별 매칭(동시 실행)" });
        list.append(el("li", { class: "parallel-wrap" }, parallel));
      }
      parallel.append(node);
    } else {
      list.append(node);
    }
    renderStep(id);
  }
}

function isStepVisible(id) {
  const run = app.run;
  if (id === "ocr") return run.source === "image" || Boolean(run.steps.ocr && run.steps.ocr.status !== "pending");
  if (id === "stt") return run.source === "audio" || Boolean(run.steps.stt && run.steps.stt.status !== "pending");
  return true;
}

function ensureStep(id) {
  const run = app.run;
  if (!STEP_LABELS[id]) return null;
  if (!run.steps[id] || !$(`step-${id}`)) {
    if (!run.steps[id]) run.steps[id] = { status: "pending", ms: null, startedAt: null, tokens: "", chips: [], usage: null, error: null, retries: 0 };
    renderTimeline();
  }
  return run.steps[id];
}

function renderStep(id) {
  const node = $(`step-${id}`);
  const s = app.run.steps[id];
  if (!node || !s) return;
  node.className = `step st-${s.status}`;
  const wasOpen = node.querySelector("details") ? node.querySelector("details").open : false;
  clear(node);
  const elapsed = s.ms !== null ? `${fmtNumber(s.ms)}ms` : (s.startedAt ? `${fmtNumber(Date.now() - s.startedAt)}ms` : "");
  const statusBadge = badge(STATUS_LABELS[s.status], STATUS_BADGE[s.status]);
  node.append(el("div", { class: "step-head" },
    el("span", { class: "step-name" }, s.status === "running" ? el("span", { class: "spinner", "aria-hidden": "true" }) : null, STEP_LABELS[id]),
    el("span", { class: "step-meta" }, statusBadge, " ", el("span", { "data-elapsed": "", text: elapsed }))));
  if (s.error) node.append(el("p", { class: "step-error", text: s.error }));
  if (s.retries) node.append(el("p", { class: "step-meta", text: `재시도 ${s.retries}회` }));
  if (s.chips.length) {
    node.append(el("ul", { class: "chips", "aria-label": "도구 호출" },
      s.chips.map((c) => el("li", {}, el("span", { class: `chip ${c.kind === "call" ? "chip-tool" : "chip-result"}`, title: c.detail, text: c.label })))));
  }
  if (s.usage) node.append(el("p", { class: "step-meta", text: `토큰 입력 ${fmtNumber(s.usage.input)} · 출력 ${fmtNumber(s.usage.output)}` }));
  if (s.tokens) {
    const details = el("details", {}, el("summary", { text: `모델 출력 보기 (${fmtNumber(s.tokens.length)}자)` }), el("pre", { text: s.tokens }));
    details.open = wasOpen;
    node.append(details);
  }
}

function updateTokens(id) {
  const node = $(`step-${id}`);
  const s = app.run.steps[id];
  const pre = node ? node.querySelector("details pre") : null;
  if (!pre) { renderStep(id); return; }
  pre.textContent = s.tokens;
  node.querySelector("details summary").textContent = `모델 출력 보기 (${fmtNumber(s.tokens.length)}자)`;
}

function tickElapsed() {
  const run = app.run;
  if (!run) return;
  for (const [id, s] of Object.entries(run.steps)) {
    if ((s.status === "running" || s.status === "retry") && s.startedAt && s.ms === null) {
      const span = document.querySelector(`#step-${id} [data-elapsed]`);
      if (span) span.textContent = `${fmtNumber(Date.now() - s.startedAt)}ms`;
    }
  }
}

// ---------- SSE (run) ----------

function connectRun() {
  const run = app.run;
  const es = new EventSource(`/api/runs/${encodeURIComponent(run.runId)}/events`);
  run.es = es;
  const handler = (ev) => onRunMessage(run, ev);
  for (const type of RUN_EVENT_TYPES) es.addEventListener(type, handler);
  es.onmessage = handler;
  es.onerror = () => onRunStreamError(run, es);
}

function onRunStreamError(run, es) {
  if (run !== app.run || run.finished) return;
  $("reconnect").hidden = false;
  if (es.readyState === EventSource.CLOSED) {
    es.close();
    run.reconnectTries += 1;
    if (run.reconnectTries > 5) {
      $("reconnect").hidden = true;
      handleRunFailure(run, "연결을 다시 열지 못했습니다.");
      return;
    }
    window.setTimeout(() => { if (run === app.run && !run.finished) connectRun(); }, 2000);
  }
}

function onRunMessage(run, ev) {
  if (run !== app.run) return;
  let env;
  try { env = JSON.parse(ev.data); } catch { return; }
  $("reconnect").hidden = true;
  run.reconnectTries = 0;
  if (typeof env.seq === "number") {
    if (run.seen.has(env.seq)) return;
    run.seen.add(env.seq);
  }
  if (env.trace_id) $("trace-id").textContent = env.trace_id;
  if (env.mode === "replay") {
    run.mode = "replay";
    $("replay-badge").hidden = false;
  }
  const fn = RUN_HANDLERS[env.type || ev.type];
  if (fn) fn(run, env.data || {}, env.step);
}

const RUN_HANDLERS = {
  run_started: onRunStarted,
  step_started: onStepStarted,
  step_completed: onStepCompleted,
  step_failed: onStepFailed,
  step_retry: onStepRetry,
  transcribed: onTranscribed,
  masked: onMasked,
  normalized: onNormalized,
  profile: onProfile,
  token: onToken,
  tool_call: onToolCall,
  tool_result: onToolResult,
  usage: onUsage,
  verified: onVerified,
  draft: onDraft,
  approval_required: onApprovalRequired,
  finalized: onFinalized,
  approval_kept: onApprovalKept,
  error: onRunError,
  done: onRunDone,
};

function onRunStarted(run, data) {
  if (data.source && data.source !== run.source) {
    run.source = data.source;
    renderInputSummary();
    renderTimeline();
  }
  if (data.mode === "replay") { run.mode = "replay"; $("replay-badge").hidden = false; }
  setRunStatus("running");
}

function onStepStarted(run, data, step) {
  const s = ensureStep(step);
  if (!s || s.status === "failed") return;
  s.status = "running";
  s.startedAt = Date.now();
  s.ms = null;
  renderStep(step);
  announce(`${STEP_LABELS[step]} 진행`);
  if (step === "referral_gate") setRunStatus("awaiting_approval");
}

function onStepCompleted(run, data, step) {
  const s = ensureStep(step);
  if (!s || s.status === "failed") return;
  s.status = "done";
  s.ms = typeof data.ms === "number" ? data.ms : (s.startedAt ? Date.now() - s.startedAt : null);
  renderStep(step);
  announce(`${STEP_LABELS[step]} 완료`);
}

function onStepFailed(run, data, step) {
  const s = ensureStep(step);
  if (!s) return;
  s.status = "failed";
  if (s.startedAt && s.ms === null) s.ms = Date.now() - s.startedAt;
  s.error = data.message || ERROR_LABELS[data.code] || ERROR_LABELS.other;
  renderStep(step);
  announce(`${STEP_LABELS[step]} 실패: ${s.error}`);
}

function onStepRetry(run, data, step) {
  const s = ensureStep(step);
  if (!s || s.status === "failed") return;
  s.status = "retry";
  s.tokens = "";
  s.retries = data.attempt || s.retries + 1;
  if (!s.startedAt) s.startedAt = Date.now();
  s.error = data.reason ? `재시도 사유: ${data.reason}` : null;
  renderStep(step);
  announce(`${STEP_LABELS[step]} 재시도`);
}

function onToken(run, data, step) {
  const s = ensureStep(step);
  if (!s || !data.text) return;
  if (s.status === "retry" && !s.error) s.status = "running";
  const hadTokens = Boolean(s.tokens);
  s.tokens += data.text;
  if (hadTokens) updateTokens(step); else renderStep(step);
}

function onToolCall(run, data, step) {
  const s = ensureStep(step);
  if (!s) return;
  s.chips.push({ kind: "call", label: `호출 ${data.tool}`, detail: shortJson(data.args, 400) });
  renderStep(step);
}

function onToolResult(run, data, step) {
  collectDecisions(run, data.result, 0);
  const s = ensureStep(step);
  if (!s) return;
  s.chips.push({ kind: "result", label: `결과 ${data.tool}${resultHint(data.result)}`, detail: shortJson(data.result, 400) });
  renderStep(step);
}

function resultHint(result) {
  if (result && typeof result === "object" && !Array.isArray(result)) {
    if (result.status) return ` · ${statusText(result.status)}`;
    if (result.ok === false) return " · 실패";
  }
  if (Array.isArray(result)) return ` · ${result.length}건`;
  return "";
}

function collectDecisions(run, obj, depth) {
  if (!obj || typeof obj !== "object" || depth > 3) return;
  if (Array.isArray(obj)) { obj.forEach((x) => collectDecisions(run, x, depth + 1)); return; }
  if (obj.decision_id && Array.isArray(obj.conditions)) run.decisions[obj.decision_id] = obj;
  for (const v of Object.values(obj)) if (v && typeof v === "object") collectDecisions(run, v, depth + 1);
}

function onUsage(run, data, step) {
  const s = ensureStep(step);
  if (!s) return;
  const prev = s.usage || { input: 0, output: 0 };
  s.usage = { input: prev.input + (data.input || 0), output: prev.output + (data.output || 0) };
  renderStep(step);
}

// ---------- masking / recognition ----------

function onMasked(run, data) {
  $("mask-view").hidden = false;
  $("mask-before").textContent = data.before || "";
  $("mask-after").textContent = data.after || "";
  const spans = clear($("mask-spans"));
  (data.spans || []).forEach((sp) => spans.append(el("li", {}, el("span", { class: "chip", text: `${MASK_KIND_LABELS[sp.kind] || sp.kind} → ${sp.placeholder}` }))));
  if (!(data.spans || []).length) spans.append(el("li", { class: "msg", text: "가린 항목이 없습니다." }));
  run.maskedAfter = data.after || "";
  renderRecognition(run);
}

function onTranscribed(run, data) {
  run.transcribed = data;
  renderRecognition(run);
}

function onNormalized(run, data) {
  run.normalized = data;
  renderRecognition(run);
}

function renderRecognition(run) {
  const n = run.normalized;
  const show = Boolean(run.transcribed) || Boolean(n && !n.skipped);
  $("recog-view").hidden = !show;
  if (!show) return;
  const t = run.transcribed;
  const meta = [];
  if (t) {
    meta.push(`${INPUT_TYPE_LABELS[t.source] || t.source} 인식 ${fmtNumber(t.chars)}자`);
    if (typeof t.ms === "number") meta.push(`${fmtNumber(t.ms)}ms`);
    if (t.speakers) meta.push(`화자 ${t.speakers}명`);
  }
  $("recog-meta").textContent = meta.join(" · ");
  const rawText = run.maskedAfter !== null ? run.maskedAfter : "";
  const raw = clear($("recog-raw"));
  raw.append(highlightUncertain(rawText || "가리기 결과를 기다리는 중입니다.", t ? t.uncertain || [] : []));
  const cleanBox = clear($("recog-clean"));
  const edits = clear($("norm-edits"));
  $("norm-skipped").hidden = !(n && n.skipped);
  if (!n) {
    cleanBox.append(el("span", { class: "msg", text: "정리 결과를 기다리는 중입니다." }));
    return;
  }
  const cleanText = n.skipped ? rawText : n.clean_text || "";
  cleanBox.append(highlightUncertain(cleanText, n.uncertain || []));
  (n.edits || []).forEach((e) => edits.append(el("li", {},
    el("del", { text: e.original }), " → ", el("ins", { text: e.replacement }),
    e.reason ? el("span", { class: "msg", text: ` (${e.reason})` }) : null)));
  const rerun = $("rerun-text");
  if (!rerun.dataset.touched) rerun.value = cleanText;
}

function highlightUncertain(text, terms) {
  const frag = document.createDocumentFragment();
  const ranges = [];
  for (const term of terms) {
    if (!term) continue;
    let from = 0;
    for (;;) {
      const idx = text.indexOf(term, from);
      if (idx < 0) break;
      ranges.push([idx, idx + term.length]);
      from = idx + term.length;
    }
  }
  ranges.sort((a, b) => a[0] - b[0]);
  let pos = 0;
  for (const [start, end] of ranges) {
    if (start < pos) continue;
    frag.append(text.slice(pos, start));
    frag.append(el("span", { class: "uncertain" }, text.slice(start, end)), el("span", { class: "uncertain-tag", text: "확인 필요" }));
    pos = end;
  }
  frag.append(text.slice(pos));
  const missing = terms.filter((term) => term && !text.includes(term));
  if (missing.length) {
    frag.append(el("span", { class: "msg" }, "\n확인 필요: ", missing.join(", ")));
  }
  return frag;
}

async function rerunWithClean() {
  const text = $("rerun-text").value.trim();
  const msg = $("rerun-msg");
  if (!text) { msg.textContent = "상담 메모를 입력하거나 데모 사례를 고르세요"; return; }
  if (text.length > MAX_TEXT) { msg.textContent = `현재 ${fmtNumber(text.length)}자 · 한도 4,000자`; return; }
  const builder = () => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note: text }) });
  try {
    const res = await api("/api/runs", builder());
    beginRun(res.run_id, { mode: res.mode || "live", source: "text", retry: { builder, source: "text" } });
  } catch (e) {
    msg.textContent = e.message;
  }
}

// ---------- profile ----------

function onProfile(run, data) {
  const box = $("profile-view");
  if (!box) return;
  clear(box);
  const profile = data.profile || {};
  const dl = el("dl", { class: "summary-dl" });
  for (const [key, value] of Object.entries(profile)) {
    if (key === "missing_fields") continue;
    let text;
    if (value === null || value === undefined) text = "모름";
    else if (Array.isArray(value)) text = value.length ? value.join(", ") : "없음";
    else if (typeof value === "boolean") text = value ? "있음" : "없음";
    else if (typeof value === "number" && key.endsWith("_krw")) text = `${fmtNumber(value)}원`;
    else text = String(value);
    dl.append(el("dt", { text: fieldLabel(key) }), el("dd", { text }));
  }
  box.append(el("h3", { text: "구조화된 사실" }), dl);
  const missing = profile.missing_fields || [];
  if (missing.length) box.append(el("p", { class: "msg" }, badge("확인 필요", "badge-warn"), " ", missing.map(fieldLabel).join(", ")));
}

// ---------- verified / evidence ----------

function statusText(status) {
  return { eligible: "자격 충족", unknown: "확인 필요", ineligible: "해당 없음" }[status] || status;
}

function onVerified(run, data) {
  run.verified = data;
  run.verifiedItems = {};
  $("result-empty").hidden = true;
  $("verified-view").hidden = false;
  $("evidence").hidden = true;
  const groups = { eligible: $("grp-eligible"), unknown: $("grp-unknown"), ineligible: $("grp-ineligible") };
  for (const [key, list] of Object.entries(groups)) {
    clear(list);
    const items = data[key] || [];
    if (!items.length) list.append(el("li", { class: "msg", text: "없음" }));
    items.forEach((item) => {
      run.verifiedItems[item.decision_id] = item;
      list.append(el("li", {}, renderVerifiedItem(item)));
    });
  }
  const removed = data.removed || [];
  $("removed-view").hidden = !removed.length;
  const rl = clear($("removed-list"));
  removed.forEach((r) => rl.append(el("li", { class: "removed-item" },
    badge("검증에서 제외됨", "badge-neutral"), " ", schemeName(r.scheme_id), el("span", { class: "item-sub", text: `사유: ${r.reason}` }))));
  const warn = $("verified-warn");
  const failed = data.failed_domains || [];
  warn.hidden = !failed.length;
  warn.textContent = failed.length ? `다음 분야 매칭이 실패해 결과가 빠졌을 수 있습니다: ${failed.map((d) => DOMAIN_LABELS[d] || d).join(", ")}` : "";
  const filled = countOf(data.verifier_filled);
  const skipped = countOf(data.audit_rule_skipped);
  $("verified-meta").textContent = `Verifier 보완 ${filled}건${skipped ? ` · 감사 규칙 생략 ${skipped}건` : ""}`;
  const counts = `자격 충족 ${(data.eligible || []).length}건, 확인 필요 ${(data.unknown || []).length}건, 해당 없음 ${(data.ineligible || []).length}건`;
  announce(`근거 검증 완료. ${counts}`);
  $("result-title").focus();
}

function schemeName(id) {
  return app.schemes[id] ? app.schemes[id].name : id;
}

function renderVerifiedItem(item) {
  return el("button", {
    type: "button",
    class: "item-btn",
    "aria-pressed": "false",
    "data-decision": item.decision_id,
    onclick: () => openEvidence(item.decision_id),
  },
  el("strong", { text: item.scheme_name || schemeName(item.scheme_id) }), " ",
  badge(DOMAIN_LABELS[item.domain] || item.domain, "badge-neutral"),
  item.source === "verifier" ? [" ", badge("Verifier 보완", "badge-warn")] : null,
  el("span", { class: "item-sub", text: item.explanation || "" }));
}

function openEvidence(decisionId) {
  const run = app.run;
  const item = run.verifiedItems[decisionId];
  if (!item) return;
  document.querySelectorAll(".item-btn").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.decision === decisionId)));
  const decision = run.decisions[decisionId];
  const scheme = app.schemes[item.scheme_id];
  const rawUrl = (scheme && scheme.source_url) || (decision && decision.source_url) || "";
  const sourceUrl = /^https:\/\//i.test(rawUrl) ? rawUrl : "";
  const body = clear($("evidence-body"));
  const statusCls = { eligible: "badge-ok", unknown: "badge-warn", ineligible: "badge-neutral" }[item.status] || "badge-neutral";
  body.append(el("p", {},
    el("strong", { text: item.scheme_name || schemeName(item.scheme_id) }), " ",
    badge(statusText(item.status), statusCls), " ", badge("판정: 규칙 도구", "badge-run")));
  const dl = el("dl");
  dl.append(el("dt", { text: "판정 ID" }), el("dd", { text: item.decision_id }));
  dl.append(el("dt", { text: "근거 조건" }), el("dd", {}, renderConditions(item, decision)));
  const missing = item.missing_fields || [];
  dl.append(el("dt", { text: "부족한 정보" }), el("dd", { text: missing.length ? missing.map(fieldLabel).join(", ") : "없음" }));
  if (scheme && scheme.summary) dl.append(el("dt", { text: "제도 요약" }), el("dd", { text: scheme.summary }));
  dl.append(el("dt", { text: "출처" }), el("dd", {},
    sourceUrl ? el("a", { href: sourceUrl, target: "_blank", rel: "noopener noreferrer", text: sourceUrl }) : (rawUrl ? rawUrl : "출처 정보 없음"),
    scheme && scheme.checked_at ? el("span", { class: "item-sub", text: `확인일 ${scheme.checked_at}${scheme.is_example ? " · 예시 데이터" : ""}` }) : null));
  body.append(dl);
  body.append(el("h4", {}, "설명 ", badge("AI 초안", "badge-warn")), el("p", { text: item.explanation || "설명 없음" }));
  const qs = item.follow_up_questions || [];
  if (qs.length) body.append(el("h4", { text: "다음 방문 질문" }), el("ul", { class: "cond-list" }, qs.map((q) => el("li", { text: q }))));
  $("evidence").hidden = false;
  $("evidence-title").focus();
}

function renderConditions(item, decision) {
  const ids = item.condition_ids || [];
  const conds = decision && Array.isArray(decision.conditions) ? decision.conditions : [];
  const byId = Object.fromEntries(conds.map((c) => [c.id, c]));
  const list = el("ul", { class: "cond-list" });
  const shown = ids.length ? ids : conds.map((c) => c.id);
  if (!shown.length) return el("span", { text: "인용된 조건 없음" });
  for (const id of shown) {
    const c = byId[id];
    if (!c) { list.append(el("li", { text: id })); continue; }
    const met = c.met === true ? badge("충족", "badge-ok") : c.met === false ? badge("미충족", "badge-fail") : badge("모름", "badge-warn");
    list.append(el("li", {}, met, " ", c.label || id, c.used_value ? el("span", { class: "item-sub", text: `사용한 값: ${c.used_value}` }) : null));
  }
  return list;
}

// ---------- draft / approval ----------

function onDraft(run, data) {
  $("draft-view").hidden = false;
  $("result-empty").hidden = true;
  const box = clear($("draft-sections"));
  run.draftOriginal = {};
  sortSections(data.sections || []).forEach((sec) => {
    run.draftOriginal[sec.id] = sec.text || "";
    const taId = `draft-${sec.id.replace(/[^a-z0-9_-]/gi, "-")}`;
    const ta = el("textarea", { id: taId, rows: "4", "data-section": sec.id });
    ta.value = sec.text || "";
    const cited = sec.cited_decisions || [];
    box.append(el("div", { class: "draft-sec" },
      el("label", { for: taId, text: sec.title || sec.id }),
      ta,
      el("div", { class: "row-between" },
        el("span", { class: "cited", text: cited.length ? `인용 판정: ${cited.join(", ")}` : "" }),
        el("button", { type: "button", class: "btn btn-link", onclick: () => { ta.value = run.draftOriginal[sec.id]; ta.focus(); }, text: "되돌리기" }))));
  });
  const fq = clear($("draft-followup"));
  const qs = data.follow_up_questions || [];
  if (qs.length) fq.append(el("h4", { text: "다음 방문 질문" }), el("ul", { class: "cond-list" }, qs.map((q) => el("li", { text: q }))));
  announce("문서 초안이 준비되었습니다.");
}

function sortSections(sections) {
  const rank = (id) => { const i = SECTION_ORDER.indexOf(id); return i < 0 ? 99 : i; };
  return [...sections].sort((a, b) => rank(a.id) - rank(b.id));
}

function editedSections() {
  const out = {};
  document.querySelectorAll("#draft-sections textarea").forEach((ta) => {
    const id = ta.dataset.section;
    if (ta.value !== app.run.draftOriginal[id]) out[id] = ta.value;
  });
  return out;
}

function onApprovalRequired(run, data) {
  run.pendingRequestId = data.request_id;
  run.approvalSchemeIds = data.scheme_ids || [];
  run.documentsSummary = data.documents_summary || [];
  setRunStatus("awaiting_approval");
  $("btn-approve-open").disabled = false;
  announce("승인 대기 중입니다. 의뢰서 확정 버튼으로 내용을 확인하세요.");
}

function openApproval() {
  const run = app.run;
  if (!run || !run.pendingRequestId) return;
  const box = clear($("approve-schemes"));
  const ids = [...run.approvalSchemeIds];
  const v = run.verified || {};
  for (const item of [...(v.eligible || []), ...(v.unknown || [])]) if (!ids.includes(item.scheme_id)) ids.push(item.scheme_id);
  if (!ids.length) box.append(el("p", { class: "msg", text: "포함할 제도가 없습니다." }));
  ids.forEach((id) => {
    const cbId = `ap-${id.replace(/[^a-z0-9_-]/gi, "-")}`;
    const cb = el("input", { type: "checkbox", id: cbId, value: id });
    cb.checked = run.approvalSchemeIds.includes(id);
    box.append(el("div", { class: "check-row" }, cb, el("label", { for: cbId, text: verifiedName(id) })));
  });
  const summary = clear($("approve-summary"));
  run.documentsSummary.forEach((s) => summary.append(el("li", { text: s })));
  const edited = Object.keys(editedSections());
  $("approve-edited").textContent = edited.length ? `담당자가 고친 구획 ${edited.length}개가 반영됩니다.` : "고친 구획이 없습니다.";
  $("approve-msg").textContent = "";
  $("approve-dialog").showModal();
}

function verifiedName(id) {
  const v = app.run.verified || {};
  for (const item of [...(v.eligible || []), ...(v.unknown || []), ...(v.ineligible || [])]) if (item.scheme_id === id) return item.scheme_name;
  return schemeName(id);
}

async function sendApproval(approved) {
  const run = app.run;
  const schemeIds = [...document.querySelectorAll("#approve-schemes input:checked")].map((x) => x.value);
  if (approved && !schemeIds.length) { $("approve-msg").textContent = "포함할 제도를 하나 이상 고르세요."; return; }
  const edited = approved ? editedSections() : {};
  const tooLong = Object.entries(edited).find(([, text]) => text.length > MAX_TEXT);
  if (tooLong) { $("approve-msg").textContent = `고친 구획이 4,000자를 넘었습니다 (현재 ${fmtNumber(tooLong[1].length)}자).`; return; }
  const payload = { request_id: run.pendingRequestId, approved, edited_sections: edited };
  if (approved) payload.scheme_ids = schemeIds;
  $("btn-approve").disabled = true;
  $("btn-reject").disabled = true;
  try {
    await postJson(`/api/runs/${encodeURIComponent(run.runId)}/approval`, payload);
    $("approve-dialog").close();
    run.pendingRequestId = null;
    $("btn-approve-open").disabled = true;
    setRunStatus(approved ? "resuming" : "drafted");
  } catch (e) {
    $("approve-msg").textContent = e.message;
  } finally {
    $("btn-approve").disabled = false;
    $("btn-reject").disabled = false;
  }
}

function onFinalized(run, data) {
  setRunStatus("finalized");
  $("btn-approve-open").disabled = true;
  $("draft-view").hidden = true;
  $("final-view").hidden = false;
  const box = clear($("final-docs"));
  const stamp = data.finalized_at ? new Date(data.finalized_at).toLocaleString("ko-KR") : "";
  box.append(renderDoc("상담기록지", data.record || [], stamp), renderDoc("서비스 연계 의뢰서", data.referral || [], stamp));
  announce("의뢰서가 확정되었습니다.");
  $("result-title").focus();
}

function renderDoc(title, sections, stamp) {
  return el("article", { class: "doc" },
    el("h4", { text: title }),
    stamp ? el("p", { class: "doc-meta", text: `확정 시각 ${stamp} · 합성 데이터` }) : null,
    sortSections(sections).map((s) => [el("h5", { text: s.title || s.id }), el("p", { text: s.text || "" })]));
}

function onApprovalKept(run) {
  setRunStatus("drafted");
  $("run-kept").hidden = false;
  $("btn-approve-open").disabled = true;
  announce("확정이 취소되어 초안 상태로 남습니다.");
}

// ---------- errors / done ----------

function onRunError(run, data) {
  const message = data.message || ERROR_LABELS[data.code] || ERROR_LABELS.other;
  handleRunFailure(run, message);
}

function handleRunFailure(run, message) {
  if (run.isDemo && !run.fellBack && run.mode !== "replay") {
    run.finished = true;
    closeRunStream();
    startReplayFallback(run.caseId);
    return;
  }
  setRunStatus("failed");
  $("run-error-text").textContent = message;
  $("btn-retry").hidden = !run.retry;
  $("run-error").hidden = false;
  announce(`오류: ${message}`);
}

async function startReplayFallback(caseId) {
  const c = app.cases.find((x) => x.id === caseId);
  try {
    const res = await postJson("/api/runs", { case_id: caseId, mode: "replay" });
    beginRun(res.run_id, { caseId, mode: "replay", source: c ? c.input_type : "text", fellBack: true });
    announce("라이브 실행이 실패해 저장된 실행을 재생합니다.");
  } catch (e) {
    setRunStatus("failed");
    $("run-error-text").textContent = `저장된 실행을 재생하지 못했습니다: ${e.message}`;
    $("btn-retry").hidden = true;
    $("run-error").hidden = false;
  }
}

function onRunDone(run, data) {
  const status = data.status || "drafted";
  if (status === "failed" && run.isDemo && !run.fellBack && run.mode !== "replay") {
    handleRunFailure(run, ERROR_LABELS.other);
    return;
  }
  run.finished = true;
  closeRunStream();
  $("reconnect").hidden = true;
  setRunStatus(status);
  if (status === "expired") {
    $("run-error-text").textContent = "실행이 만료되었습니다. 처음부터 다시 실행하세요.";
    $("btn-retry").hidden = !run.retry;
    $("run-error").hidden = false;
  } else if (status === "failed" && $("run-error").hidden) {
    handleRunFailure(run, ERROR_LABELS.other);
  }
  announce(`실행 종료: ${(RUN_STATUS[status] || [status])[0]}`);
}

function retryRun() {
  const run = app.run;
  if (!run || !run.retry) return;
  submitDirect(run.retry.builder, run.retry.source);
}

// ---------- direct input ----------

function paneMsg(source) {
  return $({ text: "note-msg", image: "image-msg", audio: "audio-msg" }[source]);
}

function selectTab(name, focus) {
  app.inputTab = name;
  for (const t of ["text", "image", "audio"]) {
    const tab = $(`tab-${t}`);
    const on = t === name;
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
    $(`pane-${t}`).hidden = !on;
    if (on && focus) tab.focus();
  }
}

function onTabKey(ev) {
  const order = ["text", "image", "audio"];
  const i = order.indexOf(app.inputTab);
  if (ev.key === "ArrowRight") selectTab(order[(i + 1) % 3], true);
  else if (ev.key === "ArrowLeft") selectTab(order[(i + 2) % 3], true);
  else if (ev.key === "Home") selectTab(order[0], true);
  else if (ev.key === "End") selectTab(order[2], true);
  else return;
  ev.preventDefault();
}

function updateCounter() {
  const len = $("note-input").value.length;
  const counter = $("note-count");
  counter.textContent = `${fmtNumber(len)} / 4,000자`;
  counter.classList.toggle("over", len > MAX_TEXT);
  const msg = $("note-msg");
  msg.classList.toggle("msg-error", len > MAX_TEXT);
  msg.textContent = len > MAX_TEXT ? `현재 ${fmtNumber(len)}자 · 한도 4,000자를 넘었습니다.` : "";
}

function validateFile(file, kind) {
  if (kind === "image") {
    const okType = ["image/jpeg", "image/png"].includes(file.type) || /\.(jpe?g|png)$/i.test(file.name);
    if (!okType) return "지원하지 않는 파일 형식입니다. 허용 형식: JPEG, PNG";
    if (file.size > MAX_IMAGE) return `파일이 너무 큽니다 (${(file.size / 1048576).toFixed(1)}MB). 한도 5MB`;
  } else {
    const okType = /^audio\/(wav|x-wav|wave|mpeg|mp3|webm)/.test(file.type) || /\.(wav|mp3|webm)$/i.test(file.name);
    if (!okType) return "지원하지 않는 파일 형식입니다. 허용 형식: WAV, MP3, WebM";
    if (file.size > MAX_AUDIO) return `파일이 너무 큽니다 (${(file.size / 1048576).toFixed(1)}MB). 한도 10MB`;
  }
  return "";
}

function onImageChange() {
  const file = $("image-input").files[0];
  const msg = $("image-msg");
  const img = $("image-preview");
  msg.classList.remove("msg-error");
  img.hidden = true;
  if (!file) { msg.textContent = ""; return; }
  const err = validateFile(file, "image");
  msg.textContent = err || `${file.name} · ${(file.size / 1048576).toFixed(2)}MB`;
  msg.classList.toggle("msg-error", Boolean(err));
  if (!err) { img.src = swapObjectUrl("image", file); img.hidden = false; }
}

function onAudioChange() {
  const file = $("audio-input").files[0];
  app.recordedFile = null;
  if (!file) { $("audio-msg").textContent = ""; $("audio-preview").hidden = true; return; }
  showAudio(file);
}

function showAudio(file) {
  const msg = $("audio-msg");
  const err = validateFile(file, "audio");
  msg.textContent = err || `${file.name} · ${(file.size / 1048576).toFixed(2)}MB`;
  msg.classList.toggle("msg-error", Boolean(err));
  const audio = $("audio-preview");
  audio.hidden = Boolean(err);
  if (!err) audio.src = swapObjectUrl("audio", file);
}

function swapObjectUrl(slot, file) {
  const key = `${slot}Url`;
  if (app[key]) URL.revokeObjectURL(app[key]);
  app[key] = URL.createObjectURL(file);
  return app[key];
}

async function startRecording() {
  const msg = $("audio-msg");
  msg.classList.remove("msg-error");
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    msg.textContent = "이 브라우저는 녹음을 지원하지 않습니다. 파일 올리기를 이용하세요.";
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    msg.textContent = "녹음 권한이 없어 파일 올리기를 이용하세요";
    msg.classList.add("msg-error");
    return;
  }
  const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
  const recorder = new MediaRecorder(stream, MediaRecorder.isTypeSupported(mimeType) ? { mimeType } : undefined);
  const chunks = [];
  const started = Date.now();
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  recorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    window.clearInterval(app.recTimer);
    const file = new File(chunks, "recording.webm", { type: "audio/webm" });
    app.recordedFile = file;
    $("audio-input").value = "";
    showAudio(file);
    $("btn-rec").disabled = false;
    $("btn-rec-stop").disabled = true;
  };
  recorder.start(1000);
  app.recorder = recorder;
  $("btn-rec").disabled = true;
  $("btn-rec-stop").disabled = false;
  $("btn-rec-stop").focus();
  msg.textContent = "녹음 중입니다.";
  app.recTimer = window.setInterval(() => {
    const sec = Math.floor((Date.now() - started) / 1000);
    $("rec-time").textContent = `${sec}초 / ${MAX_REC_SECONDS}초`;
    if (sec >= MAX_REC_SECONDS) stopRecording();
  }, 250);
}

function stopRecording() {
  if (app.recorder && app.recorder.state !== "inactive") app.recorder.stop();
}

function onSubmit() {
  const tab = app.inputTab;
  const msg = paneMsg(tab);
  msg.classList.add("msg-error");
  if (tab === "text") {
    const note = $("note-input").value.trim();
    if (!note) { msg.textContent = "상담 메모를 입력하거나 데모 사례를 고르세요"; return; }
    if (note.length > MAX_TEXT) { msg.textContent = `현재 ${fmtNumber(note.length)}자 · 한도 4,000자를 넘었습니다.`; return; }
    msg.textContent = "";
    submitDirect(() => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note }) }), "text");
    return;
  }
  const file = tab === "image" ? $("image-input").files[0] : (app.recordedFile || $("audio-input").files[0]);
  if (!file) { msg.textContent = tab === "image" ? "메모 사진을 고르세요." : "녹음하거나 녹음 파일을 고르세요."; return; }
  const err = validateFile(file, tab);
  if (err) { msg.textContent = err; return; }
  msg.classList.remove("msg-error");
  msg.textContent = "";
  submitDirect(() => {
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("kind", tab);
    return { method: "POST", body: form };
  }, tab);
}

function openDirect() {
  showScreen("direct");
  if (!app.copilotReady) {
    $("note-msg").textContent = "AI 실행 환경이 준비되지 않아 직접 입력 실행이 실패할 수 있습니다.";
  }
  $(`tab-${app.inputTab}`).focus();
}

// ---------- eval ----------

async function startEval() {
  showScreen("eval");
  clear($("eval-body"));
  clear($("eval-foot"));
  $("eval-id-text").textContent = "-";
  $("eval-trace-id").textContent = "-";
  $("eval-status").textContent = "평가를 시작하는 중입니다.";
  try {
    const res = await postJson("/api/eval", {});
    app.evalRun = { evalId: res.eval_id, es: null, seen: new Set(), finished: false };
    $("eval-id-text").textContent = res.eval_id;
    connectEval();
  } catch (e) {
    $("eval-status").textContent = `평가를 시작하지 못했습니다: ${e.message}`;
  }
}

function connectEval() {
  const ev = app.evalRun;
  const es = new EventSource(`/api/eval/${encodeURIComponent(ev.evalId)}/events`);
  ev.es = es;
  const handler = (m) => onEvalMessage(ev, m);
  for (const type of EVAL_EVENT_TYPES) es.addEventListener(type, handler);
  es.onmessage = handler;
  es.onerror = () => {
    if (ev.finished || ev !== app.evalRun) return;
    $("eval-status").textContent = "연결이 끊겨 다시 연결하는 중";
    if (es.readyState === EventSource.CLOSED) {
      es.close();
      window.setTimeout(() => { if (ev === app.evalRun && !ev.finished) connectEval(); }, 2000);
    }
  };
}

function onEvalMessage(ev, m) {
  if (ev !== app.evalRun) return;
  let env;
  try { env = JSON.parse(m.data); } catch { return; }
  if (typeof env.seq === "number") {
    if (ev.seen.has(env.seq)) return;
    ev.seen.add(env.seq);
  }
  if (env.trace_id) $("eval-trace-id").textContent = env.trace_id;
  const data = env.data || {};
  const type = env.type || m.type;
  if (type === "case_started") onCaseStarted(data);
  else if (type === "case_completed") onCaseCompleted(data);
  else if (type === "eval_summary") onEvalSummary(data);
  else if (type === "error") $("eval-status").textContent = `평가 오류: ${data.message || ERROR_LABELS[data.code] || ERROR_LABELS.other}`;
  else if (type === "done") {
    ev.finished = true;
    closeEvalStream();
    if (!/오류/.test($("eval-status").textContent)) $("eval-status").textContent = "평가가 끝났습니다.";
  }
}

function evalRowId(caseId) {
  return `eval-row-${String(caseId).replace(/[^a-z0-9_-]/gi, "-")}`;
}

function onCaseStarted(data) {
  $("eval-status").textContent = `${data.title || data.case_id} 평가 중`;
  const row = el("tr", { id: evalRowId(data.case_id) },
    el("th", { scope: "row", text: data.title || data.case_id }),
    el("td", { colspan: "12" }, badge("진행", "badge-run")));
  $("eval-body").append(row);
}

function stageMsText(stageMs) {
  const entries = Object.entries(stageMs || {});
  if (!entries.length) return "-";
  return entries.map(([k, v]) => `${STEP_LABELS[k] || k} ${fmtNumber(v)}`).join(" · ");
}

function onCaseCompleted(d) {
  let row = $(evalRowId(d.case_id));
  if (!row) { row = el("tr", { id: evalRowId(d.case_id) }); $("eval-body").append(row); }
  clear(row);
  row.className = d.replayed ? "replayed" : "";
  const missing = d.missing_fields || [];
  row.append(
    el("th", { scope: "row", text: d.title || d.case_id }),
    el("td", {}, d.replayed ? [badge("재생", "badge-warn"), el("span", { class: "stage-ms", text: " 평균 제외" })] : badge("라이브", "badge-ok")),
    el("td", { text: fmtPct(d.recall) }),
    el("td", { text: fmtPct(d.precision) }),
    el("td", { text: fmtPct(d.evidence_match) }),
    el("td", { text: fmtNumber(d.ms) }),
    el("td", { class: "stage-ms", text: stageMsText(d.stage_ms) }),
    el("td", { text: fmtNumber(d.mask_residual) }),
    el("td", { text: fmtPct(d.mask_recall) }),
    el("td", { text: typeof d.mask_false_positive === "number" && d.mask_false_positive <= 1 && !Number.isInteger(d.mask_false_positive) ? fmtPct(d.mask_false_positive) : fmtNumber(d.mask_false_positive) }),
    el("td", { text: d.cer === null || d.cer === undefined ? "-" : fmtPct(d.cer, 1) }),
    el("td", {}, String(countOf(d.auto_filled)), missing.length ? el("span", { class: "stage-ms", text: ` (모름: ${missing.map(fieldLabel).join(", ")})` }) : null),
    el("td", { text: String(countOf(d.verifier_filled)) }));
}

function onEvalSummary(s) {
  const foot = clear($("eval-foot"));
  foot.append(el("tr", {},
    el("td", { text: `요약 (${fmtNumber(s.cases)}건)` }),
    el("td", { text: `라이브 ${fmtNumber(s.live_cases)}건` }),
    el("td", { text: fmtPct(s.recall) }),
    el("td", { text: fmtPct(s.precision) }),
    el("td", { text: fmtPct(s.evidence_match) }),
    el("td", { text: fmtNumber(typeof s.avg_ms === "number" ? Math.round(s.avg_ms) : s.avg_ms) }),
    el("td", { text: "-" }),
    el("td", { text: fmtNumber(s.mask_residual_total) }),
    el("td", { text: fmtPct(s.mask_recall) }),
    el("td", { text: "-" }),
    el("td", { text: s.cer_avg === null || s.cer_avg === undefined ? "-" : fmtPct(s.cer_avg, 1) }),
    el("td", { text: "-" }),
    el("td", { text: "-" })));
  $("eval-status").textContent = "평가 요약이 준비되었습니다. 평균은 라이브 사례만 반영합니다.";
}

// ---------- wiring ----------

function bind() {
  $("btn-demo").addEventListener("click", startFirstDemo);
  $("btn-direct").addEventListener("click", openDirect);
  $("btn-eval").addEventListener("click", startEval);
  document.querySelectorAll("[data-go='home']").forEach((b) => b.addEventListener("click", () => showScreen("home")));
  for (const t of ["text", "image", "audio"]) {
    $(`tab-${t}`).addEventListener("click", () => selectTab(t, false));
    $(`tab-${t}`).addEventListener("keydown", onTabKey);
  }
  $("note-input").addEventListener("input", updateCounter);
  $("image-input").addEventListener("change", onImageChange);
  $("audio-input").addEventListener("change", onAudioChange);
  $("btn-rec").addEventListener("click", startRecording);
  $("btn-rec-stop").addEventListener("click", stopRecording);
  $("btn-submit").addEventListener("click", onSubmit);
  $("btn-retry").addEventListener("click", retryRun);
  $("btn-rerun").addEventListener("click", rerunWithClean);
  $("rerun-text").addEventListener("input", (e) => { e.target.dataset.touched = "1"; });
  $("btn-evidence-close").addEventListener("click", () => {
    $("evidence").hidden = true;
    const pressed = document.querySelector(".item-btn[aria-pressed='true']");
    if (pressed) { pressed.setAttribute("aria-pressed", "false"); pressed.focus(); }
  });
  $("btn-approve-open").addEventListener("click", openApproval);
  $("btn-approve").addEventListener("click", () => sendApproval(true));
  $("btn-reject").addEventListener("click", () => sendApproval(false));
  $("btn-print").addEventListener("click", () => window.print());
  window.setInterval(tickElapsed, 500);
}

async function init() {
  bind();
  updateCounter();
  await Promise.all([loadReadiness(), loadCases(), loadSchemes()]);
}

document.addEventListener("DOMContentLoaded", init);
