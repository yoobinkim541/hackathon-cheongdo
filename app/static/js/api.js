// 서버 API와 SSE 클라이언트. 모든 화면 모듈은 이 파일을 거쳐 서버와 통신한다.

export const RUN_EVENT_TYPES = [
  "masked", "transcribed", "normalized",
  "step_started", "step_completed", "step_failed", "step_retry",
  "token", "tool_call", "tool_result", "usage",
  "verified", "draft", "approval_required", "finalized", "approval_kept",
  "error", "replaced", "queued", "done",
];

export const EVAL_EVENT_TYPES = ["case_started", "case_completed", "eval_summary", "error", "done"];

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request(method, url, body, isForm = false) {
  const init = { method, headers: {} };
  if (body !== undefined) {
    if (isForm) {
      init.body = body;
    } else {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
  }
  let res;
  try {
    res = await fetch(url, init);
  } catch (e) {
    throw new ApiError(0, "network", "서버에 연결하지 못했습니다. 잠시 뒤 다시 시도하세요.");
  }
  let data = null;
  const text = await res.text();
  if (text) {
    try { data = JSON.parse(text); } catch { data = null; }
  }
  if (!res.ok) {
    const err = (data && data.error) || {};
    throw new ApiError(res.status, err.code || "http_" + res.status, err.message || defaultMessage(res.status));
  }
  return data;
}

function defaultMessage(status) {
  if (status === 404) return "실행을 찾을 수 없습니다. 30분이 지나 삭제되었을 수 있습니다.";
  if (status === 409) return "이미 처리된 요청이거나 지금 상태에서는 할 수 없는 작업입니다.";
  if (status === 429) return "요청이 너무 많습니다. 1분 뒤 다시 시도하세요.";
  if (status === 501) return "아직 준비되지 않은 기능입니다.";
  return "요청을 처리하지 못했습니다.";
}

export const getCases = () => request("GET", "/api/cases");

export async function getFeatures() {
  try {
    return await request("GET", "/api/features");
  } catch {
    return { image_input: false, audio_input: false, browser_recording: false, ask: false, reapproval: false };
  }
}

export const startRun = (body) => request("POST", "/api/runs", body);

export function startUpload(file, kind) {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);
  return request("POST", "/api/runs", form, true);
}

export const sendApproval = (runId, body) => request("POST", `/api/runs/${encodeURIComponent(runId)}/approval`, body);
export const ask = (runId, question) => request("POST", `/api/runs/${encodeURIComponent(runId)}/ask`, { question });
export const startEval = () => request("POST", "/api/eval");

function openStream(url, types, onEnvelope, onState) {
  const source = new EventSource(url);
  let closed = false;
  const close = () => {
    if (!closed) {
      closed = true;
      source.close();
      onState && onState("closed");
    }
  };
  source.onopen = () => onState && onState("open");
  source.onerror = () => {
    if (closed) return;
    if (source.readyState === EventSource.CLOSED) {
      close();
    } else {
      onState && onState("reconnecting");
    }
  };
  for (const type of types) {
    source.addEventListener(type, (ev) => {
      let env;
      try { env = JSON.parse(ev.data); } catch { return; }
      onEnvelope(env);
      if (type === "done") close();
    });
  }
  return { close };
}

// 실행 SSE. replaced를 받으면 새 실행으로 옮겨 같은 콜백으로 이어 받는다.
export function openEvents(runId, onEnvelope, onState) {
  let current = null;
  const follow = (id) => {
    current = openStream(`/api/runs/${encodeURIComponent(id)}/events`, RUN_EVENT_TYPES, (env) => {
      onEnvelope(env);
      if (env.type === "replaced" && env.data && env.data.run_id) {
        current.close();
        onState && onState("replaced", env.data.run_id);
        follow(env.data.run_id);
      }
    }, onState);
  };
  follow(runId);
  return { close: () => current && current.close() };
}

export function openEvalEvents(evalId, onEnvelope, onState) {
  return openStream(`/api/eval/${encodeURIComponent(evalId)}/events`, EVAL_EVENT_TYPES, onEnvelope, onState);
}
