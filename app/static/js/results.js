// 결과 구획: 제도 분류, 근거 패널, 검증에서 제외됨, 규칙 보완.
import { escapeHtml } from "./timeline.js";

const DOMAIN_LABELS = { living: "생계·주거", health: "건강·의료", care: "돌봄·고립·일자리" };
const GROUPS = [
  { key: "eligible", title: "자격 충족", badge: "badge-ok" },
  { key: "needs_check", title: "확인 필요", badge: "badge-warn" },
  { key: "ineligible", title: "해당 없음", badge: "badge-bad" },
];

export const SCHEME_NAMES = {
  livelihood_benefit: "생계급여",
  housing_benefit: "주거급여",
  emergency_livelihood: "긴급복지 생계지원",
  energy_voucher: "에너지바우처",
  medical_benefit: "의료급여",
  copay_reduction: "본인부담 경감(차상위)",
  disability_pension: "장애인연금",
  health_checkup_visit: "건강검진·방문건강관리",
  basic_pension: "기초연금",
  elderly_care_service: "노인맞춤돌봄서비스",
  emergency_safety_service: "응급안전안심서비스",
  senior_job_public: "노인일자리(공익활동)",
  lonely_death_prevention: "고독사 예방 안부 확인",
};

const FIELD_LABELS = {
  age: "나이",
  household_type: "가구 유형",
  household_size: "가구원 수",
  monthly_income_krw: "월 소득",
  disability: "장애",
  housing: "주거",
};

function fmtValue(v) {
  if (typeof v === "number") return v.toLocaleString();
  if (v === null || v === undefined) return "모름";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function conditionLine(c) {
  const mark = c.met === true ? "충족" : c.met === false ? "미충족" : "확인 필요";
  const cls = c.met === true ? "badge-ok" : c.met === false ? "badge-bad" : "badge-warn";
  const used = Object.entries(c.used_values || {})
    .map(([k, v]) => `${FIELD_LABELS[k] || k} ${fmtValue(v)}`)
    .join(", ");
  return `<li><span class="badge ${cls}">${mark}</span> <code>${escapeHtml(c.id)}</code>${used ? ` · 판정 값: ${escapeHtml(used)}` : ""}${c.note ? ` · ${escapeHtml(c.note)}` : ""}</li>`;
}

function itemHtml(item, group, supplemented) {
  const d = item.decision;
  const name = SCHEME_NAMES[d.scheme_id] || d.scheme_id;
  const missing = (d.missing_fields || []).map((f) => FIELD_LABELS[f] || f).join(", ");
  const questions = (item.follow_up_questions || []).map((q) => `<li>${escapeHtml(q)}</li>`).join("");
  const isSupp = supplemented.has(d.scheme_id);
  return `
    <details class="scheme" data-scheme="${escapeHtml(d.scheme_id)}">
      <summary>
        <span class="badge ${group.badge}">${group.title}</span>
        <strong>${escapeHtml(name)}</strong>
        <span class="muted">${DOMAIN_LABELS[d.domain] || ""}</span>
        <span class="badge badge-info">규칙 판정</span>
        ${isSupp ? '<span class="badge badge-info">규칙으로 보완</span>' : ""}
      </summary>
      <div class="scheme-body">
        ${item.explanation ? `<p><span class="badge badge-ai">AI 초안</span> ${escapeHtml(item.explanation)}</p>` : ""}
        <ul class="conditions">${(d.conditions || []).map(conditionLine).join("")}</ul>
        ${missing ? `<p>필요한 값: ${escapeHtml(missing)}</p>` : ""}
        ${questions ? `<p><strong>다음 방문 때 물을 질문</strong> <span class="badge badge-ai">AI 초안</span></p><ul>${questions}</ul>` : ""}
        <p class="muted">판정 ID <code>${escapeHtml(d.decision_id)}</code> · <a href="${escapeHtml(d.source_url)}" target="_blank" rel="noopener">공식 출처</a> · 예시 제도 데이터</p>
        <div class="ask-slot" data-scheme="${escapeHtml(d.scheme_id)}"></div>
      </div>
    </details>`;
}

export function mount(ctx) {
  const { bus } = ctx;
  const view = document.getElementById("verified-view");
  const on = (type, fn) => bus.addEventListener(type, (e) => fn(e.detail));

  on("run_started", () => { view.innerHTML = '<p class="muted">진행 중입니다…</p>'; });
  on("error", (env) => {
    if (!view.querySelector(".group")) view.innerHTML = `<p class="error-text">${escapeHtml((env.data && env.data.message) || "실행이 실패했습니다.")}</p>`;
  });

  on("verified", (env) => {
    const v = env.data || {};
    const supplemented = new Set(v.supplemented || []);
    let html = "";
    if ((v.failed_domains || []).length) {
      html += `<p class="notice">${v.failed_domains.map((d) => DOMAIN_LABELS[d] || d).join(", ")} 분야 매칭이 실패해 규칙 판정만으로 채웠습니다.</p>`;
    }
    for (const g of GROUPS) {
      const items = v[g.key] || [];
      html += `<section class="group"><h3><span class="badge ${g.badge}">${g.title}</span> ${items.length}건</h3>`;
      html += items.length ? items.map((i) => itemHtml(i, g, supplemented)).join("") : '<p class="muted">없음</p>';
      html += "</section>";
    }
    if ((v.removed || []).length) {
      html += `<section class="removed"><h3>검증에서 제외됨 ${v.removed.length}건</h3><ul>${v.removed
        .map((r) => `<li><strong>${escapeHtml(SCHEME_NAMES[r.scheme_id] || r.scheme_id)}</strong>: ${escapeHtml(r.reason)}</li>`)
        .join("")}</ul><p class="muted">AI 추천이 규칙 판정 기록과 맞지 않아 화면에서 뺐습니다.</p></section>`;
    }
    if ((v.audit_rule_skipped || []).length) {
      html += `<p class="muted">감사 기록이 불완전해 일부 단계의 인용 대조(규칙 7)를 건너뛰었습니다.</p>`;
    }
    view.innerHTML = html;
    bus.dispatchEvent(new CustomEvent("results_rendered", { detail: v }));
  });
}
