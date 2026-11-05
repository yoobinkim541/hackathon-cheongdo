// 단계 타임라인: 단계 시작·완료·실패, 도구 호출, 토큰, 가리기 전/후.

export const STEP_LABELS = {
  input_router: "입력 분기",
  ocr: "사진 인식",
  stt: "음성 전사",
  intake: "개인정보 가리기",
  normalizer: "인식 결과 정리",
  profiler: "사실 구조화",
  match_living: "생계·주거 매칭",
  match_health: "건강·의료 매칭",
  match_care: "돌봄·고립·일자리 매칭",
  verifier: "근거 검증",
  documenter: "문서 초안",
  referral_gate: "승인 대기",
  ask: "후속 질문",
};

const TOOL_LABELS = {
  record_case_profile: "프로필 기록",
  search_schemes: "제도 검색",
  check_eligibility: "자격 판정",
  submit_matches: "추천 제출",
  lookup_decision: "판정 조회",
  submit_draft: "초안 제출",
  record_clean_note: "정리본 기록",
};

const MATCH_STEPS = ["match_living", "match_health", "match_care"];
const HIDDEN_STEPS = new Set(["input_router", "ask"]);

export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function mount(ctx) {
  const { bus } = ctx;
  const stepsEl = document.getElementById("steps");
  const statusEl = document.getElementById("run-status");
  const maskedEl = document.getElementById("masked-view");
  const connEl = document.getElementById("connection");
  let rows = new Map();
  let timers = new Map();
  let matchGroup = null;

  const setStatus = (text) => { statusEl.textContent = text; };

  function reset() {
    for (const t of timers.values()) clearInterval(t);
    rows = new Map();
    timers = new Map();
    matchGroup = null;
    stepsEl.innerHTML = "";
    maskedEl.innerHTML = "";
  }

  function row(step) {
    if (!step || HIDDEN_STEPS.has(step)) return null;
    if (rows.has(step)) return rows.get(step);
    const li = document.createElement("li");
    li.className = "step";
    li.dataset.step = step;
    li.dataset.state = "running";
    li.innerHTML = `
      <div class="step-head">
        <span class="step-name"></span>
        <span class="step-meta"><span class="spinner" aria-hidden="true"></span> <span class="elapsed">0.0초</span> <span class="tokens"></span></span>
      </div>
      <ul class="step-tools"></ul>
      <p class="step-tokens" hidden></p>`;
    li.querySelector(".step-name").textContent = STEP_LABELS[step] || step;
    if (MATCH_STEPS.includes(step)) {
      if (!matchGroup) {
        const wrap = document.createElement("li");
        wrap.className = "step-group";
        wrap.setAttribute("aria-label", "분야별 제도 매칭");
        matchGroup = wrap;
        stepsEl.append(wrap);
      }
      const div = document.createElement("div");
      div.className = li.className;
      div.dataset.step = step;
      div.dataset.state = "running";
      div.innerHTML = li.innerHTML;
      // 세 분야를 고정 순서로 둔다.
      const order = MATCH_STEPS.indexOf(step);
      const after = [...matchGroup.children].find((c) => MATCH_STEPS.indexOf(c.dataset.step) > order);
      matchGroup.insertBefore(div, after || null);
      rows.set(step, div);
      return div;
    }
    stepsEl.append(li);
    rows.set(step, li);
    return li;
  }

  function startTimer(step, el, startTs) {
    const started = startTs ? Date.parse(startTs) : Date.now();
    const elapsed = el.querySelector(".elapsed");
    clearInterval(timers.get(step));
    timers.set(step, setInterval(() => {
      elapsed.textContent = `${((Date.now() - started) / 1000).toFixed(1)}초`;
    }, 200));
  }

  function stopTimer(step, el, ms) {
    clearInterval(timers.get(step));
    timers.delete(step);
    const spinner = el.querySelector(".spinner");
    if (spinner) spinner.remove();
    if (typeof ms === "number") el.querySelector(".elapsed").textContent = `${(ms / 1000).toFixed(1)}초`;
  }

  const on = (type, fn) => bus.addEventListener(type, (e) => fn(e.detail));

  on("run_started", () => { reset(); setStatus("실행을 시작했습니다."); });
  on("connection", ({ state }) => {
    connEl.hidden = state !== "reconnecting";
  });
  on("queued", (env) => setStatus(`대기 중입니다. 현재 순서: ${env.data.position}`));

  on("step_started", (env) => {
    const el = row(env.step);
    if (!el) return;
    el.dataset.state = "running";
    startTimer(env.step, el, env.ts);
    setStatus(`${STEP_LABELS[env.step] || env.step} 진행 중`);
  });

  on("step_completed", (env) => {
    const el = row(env.step);
    if (!el || el.dataset.state === "failed") return; // step_failed를 덮어쓰지 않는다
    el.dataset.state = "done";
    stopTimer(env.step, el, env.data && env.data.ms);
  });

  on("step_failed", (env) => {
    const el = row(env.step);
    if (!el) return;
    el.dataset.state = "failed";
    stopTimer(env.step, el);
    const p = document.createElement("p");
    p.className = "error-text";
    p.textContent = `${env.data.message || "실패"}${env.data.code ? ` (${env.data.code})` : ""}`;
    el.append(p);
  });

  on("step_retry", (env) => {
    const el = row(env.step);
    if (!el) return;
    const tok = el.querySelector(".step-tokens");
    tok.textContent = "";
    tok.hidden = true;
    el.querySelector(".step-tools").innerHTML = "";
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = `다시 시도 ${env.data.attempt}회: ${env.data.reason || ""}`;
    el.append(p);
  });

  on("token", (env) => {
    if (env.step === "ask" || (env.data && env.data.ask_id)) return;
    const el = row(env.step);
    if (!el) return;
    const tok = el.querySelector(".step-tokens");
    tok.hidden = false;
    tok.textContent += env.data.text || "";
    tok.scrollTop = tok.scrollHeight;
  });

  on("tool_call", (env) => {
    if (env.data && env.data.ask_id) return;
    const el = row(env.step);
    if (!el) return;
    const li = document.createElement("li");
    const label = TOOL_LABELS[env.data.tool] || env.data.tool;
    const arg = env.data.args && (env.data.args.scheme_id || env.data.args.domain || env.data.args.decision_id);
    li.textContent = `${label}${arg ? ` · ${arg}` : ""}`;
    el.querySelector(".step-tools").append(li);
  });

  on("tool_result", (env) => {
    if (env.data && env.data.ask_id) return;
    const el = row(env.step);
    if (!el || !env.data.decision_id) return;
    const last = el.querySelector(".step-tools li:last-child");
    if (last) last.textContent += ` → ${env.data.decision_id}`;
  });

  on("usage", (env) => {
    if (env.data && env.data.ask_id) return;
    const el = row(env.step);
    if (!el) return;
    const t = el.querySelector(".tokens");
    const prev = Number(t.dataset.total || 0) + (env.data.input || 0) + (env.data.output || 0);
    t.dataset.total = String(prev);
    t.textContent = `· 토큰 ${prev.toLocaleString()}`;
  });

  on("masked", (env) => {
    const d = env.data || {};
    maskedEl.innerHTML = `
      <details open>
        <summary><strong>개인정보 가리기</strong> <span class="badge badge-info">모델에는 가린 글만 갑니다</span></summary>
        <div class="compare">
          <div><h3>가리기 전</h3><pre class="before"></pre></div>
          <div><h3>가린 뒤</h3><pre class="after"></pre></div>
        </div>
      </details>`;
    maskedEl.querySelector(".before").textContent = d.before || "";
    maskedEl.querySelector(".after").innerHTML = escapeHtml(d.after || "").replace(/\[[^\]\s]{1,8}\d+\]/g, (m) => `<mark class="pii">${m}</mark>`);
  });

  on("transcribed", (env) => {
    const d = env.data || {};
    setStatus(`인식 완료: ${d.chars ?? 0}자, 불확실 구간 ${(d.uncertain || []).length}곳${d.speakers ? `, 화자 ${d.speakers}명` : ""}`);
  });

  on("verified", () => setStatus("근거 검증을 마쳤습니다. 결과를 확인하세요."));
  on("draft", () => setStatus("문서 초안이 준비되었습니다."));
  on("approval_required", () => {
    setStatus("초안을 검토하고 '의뢰서 확정'을 누르세요.");
    const title = document.getElementById("results-title");
    if (title) title.focus();
  });
  on("finalized", () => setStatus("의뢰서를 확정했습니다."));
  on("approval_kept", () => setStatus("확정을 취소했습니다. 초안 상태입니다."));
  on("replaced", () => setStatus("호출 한도로 저장된 실행 재생으로 전환합니다."));
  on("error", (env) => {
    for (const [step, el] of rows) {
      if (el.dataset.state === "running") { el.dataset.state = "failed"; stopTimer(step, el); }
    }
    const d = env.data || {};
    setStatus(`실패: ${d.message || "실행을 끝내지 못했습니다."}`);
  });
  on("done", (env) => {
    for (const [step, el] of rows) stopTimer(step, el);
    if (env.data && env.data.status === "expired") setStatus("실행이 만료되었습니다(30분).");
  });
}
