(function () {
  "use strict";

  // 합성 데이터. 서버 호출 없이 화면 흐름만 보여 주는 목업이다.
  var OK_BASE = [
    { icon: "₩", tone: "c-primary", name: "생계급여", desc: "소득 34만 원 ≤ 기준 76만 원", id: "d-0012", src: "복지부 2026 지침", msg: "신청 가능해 보여요" },
    { icon: "♡", tone: "c-bad", name: "노인맞춤돌봄", desc: "만 65세 이상 · 1인 가구", id: "d-0015", src: "복지부 2026 지침", msg: "만 65세 이상 독거 가구예요" },
    { icon: "◆", tone: "c-ok", name: "응급안전안심", desc: "독거 · 고립 신호", id: "d-0018", src: "복지부 2026 지침", msg: "독거 가구라 연계 대상이에요" },
    { icon: "₩", tone: "c-warn", name: "기초연금", desc: "소득인정액 기준 충족", id: "d-0019", src: "복지부 2026 지침", msg: "소득인정액 기준을 충족해요" }
  ];
  var OK_EXTRA = [
    { icon: "◎", tone: "c-warn", name: "장애인연금", desc: "등록 장애 · 소득인정액 기준 충족", id: "d-0023", src: "복지부 2026 지침", msg: "답을 반영해 다시 판정했어요" },
    { icon: "✚", tone: "c-bad", name: "본인부담 경감(차상위)", desc: "병원비 입력값 반영", id: "d-0024", src: "복지부 2026 지침", msg: "답을 반영해 다시 판정했어요" }
  ];
  var NEED = [
    { icon: "◎", tone: "c-warn", name: "장애인연금", desc: "장애 정도 확인 필요" },
    { icon: "✚", tone: "c-bad", name: "본인부담 경감(차상위)", desc: "병원비·소득 확인 필요" }
  ];
  var NONE = [
    { icon: "⌂", tone: "c-primary", name: "주거급여", desc: "자가 거주" },
    { icon: "!", tone: "c-warn", name: "긴급복지 생계지원", desc: "위기 사유 없음" },
    { icon: "☀", tone: "c-warn", name: "에너지바우처", desc: "수급자 요건 미충족" },
    { icon: "✚", tone: "c-bad", name: "의료급여", desc: "수급 요건 미해당" },
    { icon: "♥", tone: "c-ok", name: "건강검진·방문건강관리", desc: "이미 이용 중" },
    { icon: "✎", tone: "c-primary", name: "노인일자리(공익활동)", desc: "참여 의사 없음" },
    { icon: "☎", tone: "c-ok", name: "고독사 예방 안부 확인", desc: "이미 연계 중" }
  ];

  var state = fresh();
  var screenEl = document.getElementById("screen");
  var toastEl = document.getElementById("toast");
  var toastTimer = 0;

  function fresh() {
    return { screen: "home", tab: "ok", open: {}, resolved: false, confirmed: false, disability: "심한 장애", cost: "120만 원" };
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function okList() { return state.resolved ? OK_BASE.concat(OK_EXTRA) : OK_BASE; }
  function needList() { return state.resolved ? [] : NEED; }

  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 2200);
  }

  /* ---------- 화면 ---------- */

  function row(item, extra) {
    return (
      '<div class="row">' +
      '<div class="icon ' + item.tone + '" aria-hidden="true">' + item.icon + "</div>" +
      '<div class="text"><strong>' + item.name + "</strong><span>" + item.desc + "</span></div>" +
      extra +
      "</div>"
    );
  }

  function homeScreen() {
    function act(icon, tone, title, sub, label) {
      return (
        '<div class="row">' +
        '<div class="icon ' + tone + '" aria-hidden="true">' + icon + "</div>" +
        '<div class="text"><strong>' + title + "</strong><span>" + sub + "</span></div>" +
        '<button type="button" class="btn primary" data-act="start" aria-label="' + title + '">' + label + "</button>" +
        "</div>"
      );
    }
    function todo(icon, tone, title, sub, label, act) {
      return (
        '<div class="row">' +
        '<div class="icon ' + tone + '" aria-hidden="true">' + icon + "</div>" +
        '<div class="text"><strong>' + title + "</strong><span>" + sub + "</span></div>" +
        '<button type="button" class="btn" data-go="' + act + '" aria-label="' + title + ' ' + label + '">' + label + "</button>" +
        "</div>"
      );
    }
    return (
      '<section class="hero"><p class="eyebrow">박지은 주무관님</p><h2>오늘 정리할 상담<br>3건이 있어요</h2></section>' +
      '<section class="card" aria-label="새 상담"><p class="label">새 상담</p><p class="title">방문 메모를 어떻게 올릴까요?</p>' +
      act("▤", "c-primary", "직접 입력하기", "붙여넣기도 돼요", "입력") +
      act("◉", "c-ok", "메모 사진 찍기", "손글씨 인식 (OCR)", "촬영") +
      act("●", "c-bad", "상담 녹음하기", "2분 이내 · 화자 자동 구분", "녹음") +
      "</section>" +
      '<section class="card" aria-label="이어서 할 일"><p class="label">이어서 할 일</p><p class="title">확인이 필요한 상담 2건</p>' +
      todo("?", "c-warn", "고령 부부 · 청도읍", "소득 정보 누락 · 질문 3개", "보기", "check") +
      todo("✓", "c-ok", "독거노인 · ○○면", "의뢰서 승인 대기", "승인", "approve") +
      "</section>"
    );
  }

  function resultScreen() {
    var ok = okList(), need = needList();
    var tabs = [
      { id: "ok", label: "충족 " + ok.length },
      { id: "need", label: "확인 필요 " + need.length },
      { id: "none", label: "해당 없음 " + NONE.length }
    ];
    var seg = tabs.map(function (t) {
      return '<button type="button" role="tab" data-tab="' + t.id + '" aria-selected="' + (state.tab === t.id) + '">' + t.label + "</button>";
    }).join("");

    var list = "";
    if (state.tab === "ok") {
      list = ok.map(function (it, i) {
        var opened = !!state.open[i];
        var head =
          '<button type="button" class="row" data-toggle="' + i + '" aria-expanded="' + opened + '">' +
          '<div class="icon ' + it.tone + '" aria-hidden="true">' + it.icon + "</div>" +
          '<div class="text"><strong>' + it.name + "</strong><span>" + it.desc + "</span></div>" +
          '<span class="badge ok">충족</span></button>';
        var evid = opened
          ? '<div class="evidence"><p>근거 ' + it.id + " · " + it.src + '</p><div class="line"><span class="badge ai">AI 초안</span><span>' + it.msg + "</span></div></div>"
          : "";
        return head + evid;
      }).join("");
    } else if (state.tab === "need") {
      list = need.length
        ? need.map(function (it) {
            return row(it, '<button type="button" class="btn" data-go="check">입력</button>');
          }).join("")
        : '<p class="empty">확인할 항목이 없어요</p>';
    } else {
      list = NONE.map(function (it) { return row(it, '<span class="badge none">해당 없음</span>'); }).join("");
    }

    return (
      '<section class="score"><h2>받을 수 있는 제도를</h2>' +
      '<div class="big"><b>' + ok.length + "</b><span>건 찾았어요</span></div>" +
      "<p>규칙 함수로 판정 · 71초 · 개인정보 3건 가림</p></section>" +
      '<div class="seg" role="tablist" aria-label="판정 결과 분류">' + seg + "</div>" +
      '<section class="card list" aria-live="polite">' + list + "</section>" +
      '<button type="button" class="btn primary block" data-go="approve">문서 초안 만들기</button>'
    );
  }

  var DISABILITY = ["심한 장애", "심하지 않은 장애", "장애 없음"];

  function conditionText() {
    return state.disability === "장애 없음"
      ? "장애인이 아니면 추가로 충족되는 제도는 없어요"
      : "등록 장애인이면 2건이 더 충족돼요";
  }

  function checkScreen() {
    var opts = DISABILITY.map(function (d) {
      return '<option value="' + d + '"' + (d === state.disability ? " selected" : "") + ">" + d + "</option>";
    }).join("");
    return (
      '<section class="hero"><p class="eyebrow">다음 방문 때</p><h2>2가지만 물어보세요</h2></section>' +
      '<section class="card q"><div class="row"><div class="icon c-warn" aria-hidden="true">◎</div>' +
      '<div class="text"><strong>장애인 등록 여부와 정도</strong><span>→ 장애인활동지원 · 장애인연금</span></div></div>' +
      '<div class="field"><label class="sr" for="q-disability">장애인 등록 여부와 정도</label>' +
      '<select id="q-disability">' + opts + '</select><span class="state">입력됨</span></div></section>' +
      '<section class="card q"><div class="row"><div class="icon c-bad" aria-hidden="true">✚</div>' +
      '<div class="text"><strong>최근 3개월 병원비</strong><span>→ 재난적 의료비 지원</span></div></div>' +
      '<div class="field"><label class="sr" for="q-cost">최근 3개월 병원비</label>' +
      '<input id="q-cost" type="text" inputmode="text" autocomplete="off" placeholder="예: 120만 원" value="' + esc(state.cost) + '">' +
      '<span class="state' + (state.cost.trim() ? "" : " empty-state") + '" id="cost-state">' + (state.cost.trim() ? "입력됨" : "미입력") + "</span></div></section>" +
      '<section class="card"><p class="label">조건 바꿔보기</p><p class="title sm" id="cond-text">' + conditionText() + "</p>" +
      '<p class="note">가정한 값은 실제 기록에 저장되지 않아요</p></section>' +
      '<button type="button" class="btn primary block" data-act="save">답 저장하고 다시 판정</button>'
    );
  }

  function approveScreen() {
    var names = okList().slice(0, 3).map(function (i) { return i.name; });
    if (state.confirmed) {
      return (
        '<div class="center">' +
        '<div class="done-mark" aria-hidden="true">✓</div>' +
        "<h2>의뢰서를 <em>확정</em>했어요</h2>" +
        '<section class="approval"><h3>연계 제도 3건</h3><p class="list">' + names.slice(0, 2).join(" · ") + "<br>" + names[2] + "</p>" +
        '<p class="hint">승인 후 코드가 인쇄용 문서를 만들었어요.<br>이 화면은 목업이라 실제 문서는 만들어지지 않아요.</p>' +
        '<button type="button" class="btn white" data-act="reset">처음으로</button></section></div>'
      );
    }
    return (
      '<div class="center">' +
      "<h2>의뢰서를<br><em>확정</em> 할까요?</h2>" +
      '<section class="approval" aria-label="확정할 연계 제도"><h3>연계 제도 3건</h3><p class="list">생계급여 · 노인맞춤돌봄<br>응급안전안심</p>' +
      '<p class="hint">검증을 통과한 제도만 담겼어요.<br>확정은 승인 후 코드가 실행해요.</p>' +
      '<button type="button" class="btn white" data-act="confirm">승인하고 확정</button></section>' +
      '<button type="button" class="link-btn" data-act="reject">거부하고 초안으로</button></div>'
    );
  }

  function evalScreen() {
    function m(name, target) {
      return '<div class="metric"><b>' + name + "</b><span>목표 " + target + "</span></div>";
    }
    return (
      '<section class="hero"><p class="eyebrow">평가 실행</p><h2>데모 사례 5건<br>지표 목표</h2></section>' +
      '<section class="card" aria-label="평가 지표 목표">' +
      m("제도 재현율", "90% 이상") + m("추천 정밀도", "90% 이상") + m("근거 일치율", "100%") +
      m("처리 시간", "1건 90초 이내") + m("가리기 누락", "0건") +
      '<p class="note note-top">실측값은 서버에서 평가를 실행해야 나와요. 이 목업은 목표만 보여 줘요.</p></section>'
    );
  }

  var SCREENS = { home: homeScreen, result: resultScreen, check: checkScreen, approve: approveScreen, eval: evalScreen };

  /* ---------- 렌더·이동 ---------- */

  function render(moveFocus) {
    screenEl.innerHTML = SCREENS[state.screen]();
    var cur = state.screen;
    document.querySelectorAll(".tabbar button").forEach(function (b) {
      if (b.getAttribute("data-go") === cur) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
    if (moveFocus) {
      screenEl.scrollTop = 0;
      screenEl.focus({ preventScroll: true });
    }
  }

  function go(name) {
    if (!SCREENS[name]) return;
    state.screen = name;
    if (name === "result") state.tab = "ok";
    render(true);
    try { history.replaceState(null, "", "#" + name); } catch (err) { /* 무시 */ }
  }

  /* ---------- 이벤트 ---------- */

  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-go],[data-act],[data-tab],[data-toggle]");
    if (!t) return;

    if (t.hasAttribute("data-go")) { go(t.getAttribute("data-go")); return; }
    if (t.hasAttribute("data-tab")) { state.tab = t.getAttribute("data-tab"); render(false); return; }
    if (t.hasAttribute("data-toggle")) {
      var i = t.getAttribute("data-toggle");
      state.open[i] = !state.open[i];
      render(false);
      var again = screenEl.querySelector('[data-toggle="' + i + '"]');
      if (again) again.focus({ preventScroll: true });
      return;
    }

    switch (t.getAttribute("data-act")) {
      case "start":
        toast("데모 사례로 분석했어요");
        go("result");
        break;
      case "save":
        if (state.disability === "장애 없음") { toast("추가로 충족되는 제도는 없어요"); break; }
        state.resolved = true;
        toast("답을 저장하고 다시 판정했어요");
        go("result");
        break;
      case "confirm":
        state.confirmed = true;
        render(true);
        break;
      case "reject":
        toast("확정을 취소하고 초안으로 돌아갔어요");
        go("result");
        break;
      case "reset":
        state = fresh();
        go("home");
        break;
    }
  });

  document.addEventListener("input", function (e) {
    if (e.target.id === "q-cost") {
      state.cost = e.target.value;
      var s = document.getElementById("cost-state");
      var has = !!state.cost.trim();
      s.textContent = has ? "입력됨" : "미입력";
      s.classList.toggle("empty-state", !has);
    }
  });

  document.addEventListener("change", function (e) {
    if (e.target.id === "q-disability") {
      state.disability = e.target.value;
      document.getElementById("cond-text").textContent = conditionText();
    }
  });

  /* ---------- 테마 ---------- */

  var themeBtn = document.getElementById("theme-toggle");

  function applyTheme(mode) {
    document.documentElement.setAttribute("data-theme", mode);
    themeBtn.textContent = mode === "dark" ? "라이트 모드" : "다크 모드";
    themeBtn.setAttribute("aria-pressed", String(mode === "dark"));
  }

  function initialTheme() {
    var q = /[?&]theme=(light|dark)/.exec(location.search);
    if (q) return q[1];
    try {
      var saved = localStorage.getItem("donghaeng-mockup-theme");
      if (saved === "dark" || saved === "light") return saved;
    } catch (err) { /* 저장소를 쓸 수 없으면 시스템 설정을 따른다 */ }
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  themeBtn.addEventListener("click", function () {
    var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem("donghaeng-mockup-theme", next); } catch (err) { /* 무시 */ }
  });

  applyTheme(initialTheme());

  // 주소의 #result, #check, #approve, #eval로 해당 화면을 바로 연다.
  var hash = location.hash.replace("#", "");
  if (SCREENS[hash]) state.screen = hash;
  if (state.screen === "result" && /[?&]tab=(need|none)/.test(location.search)) {
    state.tab = /[?&]tab=need/.test(location.search) ? "need" : "none";
  }
  render(false);
})();
