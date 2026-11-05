// 평가 실행 화면: 사례별 라이브/재생, 지표, 단계별 시간.
import { escapeHtml, STEP_LABELS } from "./timeline.js";

const pct = (v) => (v === null || v === undefined ? "–" : `${Math.round(v * 100)}%`);
const sec = (ms) => (ms === null || ms === undefined ? "–" : `${(ms / 1000).toFixed(1)}초`);
const TARGETS = { recall: 0.9, precision: 0.9, grounding: 1.0 };

export function mount(ctx) {
  const { bus, api } = ctx;
  const panel = document.getElementById("eval");
  const view = document.getElementById("eval-view");
  let stream = null;
  let rows = new Map();

  function table() {
    view.innerHTML = `
      <p id="eval-status" class="status" aria-live="polite">평가를 시작합니다…</p>
      <div style="overflow-x:auto">
      <table class="eval-table">
        <thead><tr><th>사례</th><th>방식</th><th>재현율</th><th>정밀도</th><th>근거 일치</th><th>가리기</th><th>자동 채움</th><th>보완</th><th>CER</th><th>처리 시간</th></tr></thead>
        <tbody id="eval-rows"></tbody>
      </table></div>
      <div id="eval-summary"></div>`;
  }

  function caseRow(caseId) {
    if (rows.has(caseId)) return rows.get(caseId);
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(caseId)}</td><td colspan="9"><span class="spinner" aria-hidden="true"></span> 진행 중</td>`;
    document.getElementById("eval-rows").append(tr);
    rows.set(caseId, tr);
    return tr;
  }

  function stepBars(stepMs) {
    const entries = Object.entries(stepMs || {});
    const max = Math.max(1, ...entries.map(([, v]) => v));
    return entries
      .map(([k, v]) => `<div class="muted" style="font-size:.8rem">${escapeHtml(STEP_LABELS[k] || k)} <span class="bar" style="width:${Math.max(4, (v / max) * 120)}px"></span> ${sec(v)}</div>`)
      .join("");
  }

  async function start() {
    panel.hidden = false;
    rows = new Map();
    table();
    document.getElementById("eval-title").focus();
    if (stream) stream.close();
    try {
      const res = await api.startEval();
      stream = api.openEvalEvents(res.eval_id, onEnvelope, (s) => {
        if (s === "reconnecting") document.getElementById("eval-status").textContent = "연결이 끊겨 다시 연결하는 중";
      });
    } catch (e) {
      document.getElementById("eval-status").textContent = e.message;
    }
  }

  function onEnvelope(env) {
    const d = env.data || {};
    const status = document.getElementById("eval-status");
    if (env.type === "case_started") {
      caseRow(d.case_id);
      status.textContent = `${d.case_id} 처리 중`;
    } else if (env.type === "case_completed") {
      const tr = caseRow(d.case_id);
      tr.innerHTML = `
        <td>${escapeHtml(d.case_id)}</td>
        <td>${d.replayed ? '<span class="badge badge-warn">재생</span>' : '<span class="badge badge-ok">라이브</span>'}</td>
        <td>${pct(d.recall)}</td><td>${pct(d.precision)}</td><td>${pct(d.grounding)}</td>
        <td>${pct(d.pii_recall)}${d.pii_residual ? ` · 잔존 ${d.pii_residual}` : ""}</td>
        <td>${d.autofilled_fields ?? "–"} / ${(d.autofilled_fields ?? 0) + (d.manual_fields ?? 0)}</td>
        <td>${d.supplemented ?? 0}</td>
        <td>${d.cer === null || d.cer === undefined ? "–" : d.cer.toFixed(3)}</td>
        <td>${sec(d.total_ms)}${stepBars(d.step_ms)}</td>`;
    } else if (env.type === "eval_summary") {
      const s = d;
      const line = (label, key) => {
        const v = s[key];
        const ok = v !== null && v !== undefined && v >= TARGETS[key];
        return `<li>${label}: <strong>${pct(v)}</strong> <span class="badge ${ok ? "badge-ok" : "badge-warn"}">목표 ${pct(TARGETS[key])}</span></li>`;
      };
      document.getElementById("eval-summary").innerHTML = `
        <h3>요약</h3>
        <ul>
          ${line("재현율", "recall")}${line("정밀도", "precision")}${line("근거 일치율", "grounding")}
          <li>처리 시간 p50 ${sec(s.p50_ms)}, p95 ${sec(s.p95_ms)} (목표 90초)</li>
          <li>라이브 ${s.live_count}건, 저장된 실행 재생 ${s.replay_count}건(재생은 평균에서 뺐습니다)</li>
        </ul>`;
      status.textContent = "평가를 마쳤습니다.";
    } else if (env.type === "error") {
      status.textContent = `평가 실패: ${d.message || ""}`;
    }
  }

  bus.addEventListener("eval_requested", start);
}
