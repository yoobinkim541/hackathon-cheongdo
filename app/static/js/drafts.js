// 초안 편집, 승인 창, 확정 문서 인쇄 화면.
import { escapeHtml } from "./timeline.js";
import { SCHEME_NAMES } from "./results.js";

export const SECTIONS = [
  { id: "record.basic_info", doc: "record", label: "기본 정보" },
  { id: "record.summary", doc: "record", label: "상담 내용 요약" },
  { id: "record.needs", doc: "record", label: "욕구 분류" },
  { id: "record.linked_schemes", doc: "record", label: "연계 제도" },
  { id: "record.follow_up", doc: "record", label: "확인 필요 항목" },
  { id: "referral.agency", doc: "referral", label: "의뢰 기관" },
  { id: "referral.subject", doc: "referral", label: "대상자 요약" },
  { id: "referral.schemes", doc: "referral", label: "의뢰 제도와 근거 조건" },
  { id: "referral.officer", doc: "referral", label: "담당자" },
];
const DOC_TITLES = { record: "상담기록지", referral: "서비스 연계 의뢰서" };

export function mount(ctx) {
  const { bus, api, state } = ctx;
  const view = document.getElementById("draft-view");
  const finalView = document.getElementById("final-view");
  const dialog = document.getElementById("approval-dialog");
  const body = document.getElementById("approval-body");
  const acceptBtn = document.getElementById("approval-accept");
  const rejectBtn = document.getElementById("approval-reject");
  let original = {};
  let pending = null;
  let sending = false;

  const on = (type, fn) => bus.addEventListener(type, (e) => fn(e.detail));

  function editedSections() {
    const out = {};
    for (const s of SECTIONS) {
      const ta = view.querySelector(`textarea[data-section="${s.id}"]`);
      if (ta && ta.value !== (original[s.id] ?? "")) out[s.id] = ta.value;
    }
    return out;
  }

  function renderDraft(draft) {
    original = { ...(draft.sections || {}) };
    let html = "";
    for (const doc of ["record", "referral"]) {
      html += `<section class="draft-watermark"><h3>${DOC_TITLES[doc]} <span class="badge badge-ai">AI 초안</span></h3>`;
      for (const s of SECTIONS.filter((x) => x.doc === doc)) {
        html += `
          <div class="draft-section" data-edited="false">
            <label for="sec-${s.id}">${s.label}
              <button type="button" class="btn btn-small" data-revert="${s.id}" aria-label="${s.label} AI 초안으로 되돌리기">되돌리기</button>
            </label>
            <textarea id="sec-${s.id}" data-section="${s.id}" rows="3"></textarea>
          </div>`;
      }
      html += "</section>";
    }
    html += `
      <div class="draft-actions">
        <span id="draft-state" class="badge badge-warn">초안</span>
        <button id="finalize-btn" class="btn btn-primary" type="button" disabled>의뢰서 확정</button>
        <span id="draft-msg" class="muted" role="status"></span>
      </div>`;
    view.innerHTML = html;
    for (const s of SECTIONS) {
      const ta = view.querySelector(`textarea[data-section="${s.id}"]`);
      ta.value = original[s.id] ?? "";
      ta.addEventListener("input", () => {
        ta.closest(".draft-section").dataset.edited = String(ta.value !== (original[s.id] ?? ""));
      });
    }
    view.querySelectorAll("[data-revert]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.revert;
        const ta = view.querySelector(`textarea[data-section="${id}"]`);
        ta.value = original[id] ?? "";
        ta.closest(".draft-section").dataset.edited = "false";
        ta.focus();
      });
    });
    view.querySelector("#finalize-btn").addEventListener("click", openDialog);
    if (pending) enableFinalize();
  }

  function enableFinalize() {
    const btn = view.querySelector("#finalize-btn");
    if (btn) btn.disabled = false;
  }

  function openDialog() {
    if (!pending) return;
    const edited = Object.keys(editedSections());
    const schemes = (pending.scheme_ids || []).map((id) => `<li>${escapeHtml(SCHEME_NAMES[id] || id)}</li>`).join("");
    body.innerHTML = `
      <p><strong>확정할 문서</strong>: 상담기록지, 서비스 연계 의뢰서</p>
      <p><strong>포함 제도</strong></p><ul>${schemes || "<li>없음</li>"}</ul>
      ${pending.documents_summary ? `<p class="muted">${escapeHtml(pending.documents_summary)}</p>` : ""}
      <p>담당자가 고친 구획: ${edited.length ? edited.length + "곳" : "없음"}</p>`;
    dialog.showModal();
    rejectBtn.focus(); // 위험한 작업 전에는 거부에 먼저 포커스
  }

  async function respond(approved) {
    if (!pending || sending) return;
    sending = true;
    acceptBtn.disabled = rejectBtn.disabled = true;
    const msg = view.querySelector("#draft-msg");
    try {
      await api.sendApproval(state.runId, {
        request_id: pending.request_id,
        approved,
        edited_sections: editedSections(),
      });
      pending = null;
      const btn = view.querySelector("#finalize-btn");
      if (btn) btn.disabled = true;
      if (msg) msg.textContent = approved ? "확정 문서를 만드는 중입니다…" : "";
    } catch (e) {
      if (msg) msg.textContent = e.status === 409 ? "이미 처리된 승인 요청입니다." : e.message;
    } finally {
      sending = false;
      acceptBtn.disabled = rejectBtn.disabled = false;
      dialog.close();
    }
  }

  acceptBtn.addEventListener("click", () => respond(true));
  rejectBtn.addEventListener("click", () => respond(false));
  dialog.addEventListener("cancel", () => dialog.close());

  on("run_started", () => {
    view.innerHTML = "";
    finalView.innerHTML = "";
    pending = null;
    original = {};
  });
  on("draft", (env) => renderDraft(env.data || {}));
  on("approval_required", (env) => {
    pending = env.data;
    enableFinalize();
  });
  on("approval_kept", () => {
    const st = view.querySelector("#draft-state");
    if (st) st.textContent = "초안";
    const msg = view.querySelector("#draft-msg");
    if (msg) msg.textContent = "확정 취소됨" + (ctx.features.reapproval ? ". 초안을 고친 뒤 다시 확정할 수 있습니다." : "");
  });
  on("finalized", (env) => {
    const f = env.data || {};
    const st = view.querySelector("#draft-state");
    if (st) { st.textContent = "확정"; st.className = "badge badge-ok"; }
    const msg = view.querySelector("#draft-msg");
    if (msg) msg.textContent = "";
    let html = `<article class="final-doc"><div class="no-print draft-actions"><button type="button" class="btn btn-primary" id="print-btn">인쇄</button><span class="muted">확정 시각 ${escapeHtml(f.finalized_at || "")}</span></div>`;
    for (const doc of ["record", "referral"]) {
      html += `<section class="${doc === "referral" ? "page-break" : ""}"><h2>${DOC_TITLES[doc]}</h2>`;
      for (const s of SECTIONS.filter((x) => x.doc === doc)) {
        html += `<h3>${s.label}</h3><p>${escapeHtml((f.sections || {})[s.id] || "")}</p>`;
      }
      html += "</section>";
    }
    html += "</article>";
    finalView.innerHTML = html;
    finalView.querySelector("#print-btn").addEventListener("click", () => window.print());
    finalView.querySelector("#print-btn").focus();
  });
}
