// 후속 질문(F9): "확인 필요" 항목마다 질문 칩과 자유 질문. 플래그가 꺼졌거나 재생이면 그리지 않는다.
import { escapeHtml } from "./timeline.js";
import { SCHEME_NAMES } from "./results.js";

export function mount(ctx) {
  const { bus, api, features, state } = ctx;
  if (!features.ask) return;
  const answers = new Map();
  let ready = false;

  const on = (type, fn) => bus.addEventListener(type, (e) => fn(e.detail));

  async function send(question, slot) {
    const out = document.createElement("div");
    out.className = "ask-answer";
    out.innerHTML = `<p><strong>질문</strong> ${escapeHtml(question)}</p><p class="answer"><span class="badge badge-ai">AI 초안</span> </p>`;
    slot.append(out);
    try {
      const res = await api.ask(state.runId, question);
      answers.set(res.ask_id, out.querySelector(".answer"));
    } catch (e) {
      out.querySelector(".answer").textContent = e.message;
    }
  }

  function render() {
    if (state.mode === "replay" || !ready) return;
    document.querySelectorAll('.group .scheme .ask-slot').forEach((slot) => {
      const details = slot.closest(".scheme");
      const isUnknown = details.querySelector(".badge-warn") && details.querySelector("summary .badge-warn");
      if (!isUnknown || slot.dataset.mounted) return;
      slot.dataset.mounted = "1";
      const name = SCHEME_NAMES[slot.dataset.scheme] || slot.dataset.scheme;
      slot.innerHTML = `
        <div class="ask-box">
          <div class="ask-chips">
            <button type="button" class="btn btn-small" data-q="${escapeHtml(name)}은(는) 왜 확인 필요인가요?">왜 확인 필요인가요?</button>
            <button type="button" class="btn btn-small" data-q="${escapeHtml(name)}의 조건이 바뀌면 판정이 어떻게 달라지나요?">조건이 바뀌면?</button>
          </div>
        </div>`;
      slot.querySelectorAll("[data-q]").forEach((b) => b.addEventListener("click", () => send(b.dataset.q, slot)));
    });
  }

  on("run_started", () => { ready = false; answers.clear(); });
  on("approval_required", () => { ready = true; render(); });
  on("finalized", () => { ready = true; render(); });
  on("results_rendered", render);
  on("token", (env) => {
    const id = env.data && env.data.ask_id;
    if (!id || !answers.has(id)) return;
    answers.get(id).append(document.createTextNode(env.data.text || ""));
  });
}
