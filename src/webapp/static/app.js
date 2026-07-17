/* 판단 여권 · S4 데모 화면 로직.
   - 숫자는 전부 서버(결정론 계산 엔진) 결과를 표시만 한다 — 이 파일은 금액 산수를 하지 않는다.
   - 화면의 사실·해석·모름·질문 블록은 guard를 통과한 응답(briefing)만 그린다.
   - 외부 네트워크 요청 0 — fetch 대상은 같은 서버의 /api/* 뿐이다. */
"use strict";

/* ── 상태 ─────────────────────────────────────────────── */
const S = {
  scenarioId: null,
  scenarios: [],
  data: null,          // GET /api/scenario/{id} 응답
  step: 0,             // 0=홈, 1~8=위저드
  flowSide: null,      // 흐름 방향("sell"|"buy") — S0 진입 클릭이 결정(양방향, D-0718-0225).
                       // 기본값은 서버 meta.side(보유 기반). ③④⑤⑥이 이 값을 따른다.
  partialQty: 10,      // ④ 일부 판매 수량(기본 10주)
  buyQty: 10,          // ④ 구매 수량(기본 10주 — D-0718-0255 수량 조정)
  previews: {},        // key(partial|full|b8|b10) → {preview}|{error}
  intent: null,        // ⑤ 검토 의향(4택 라벨)
  settledIntent: null, // 체결 시점 의향 스냅샷 — ⑦ "선택:" 표기 고정(이후 의향 변경과 분리)
  diaryText: "",
  settlement: null,
  savedRecord: null,
  briefingLoading: false, // ② 브리핑 생성 중 여부(진입 지연 생성 — D-0718-0355)
};

const STEP_NAMES = ["주문 화면(진입)", "① 종목·계획", "② 관련 사실", "③ 체크리스트",
  "④ 시나리오 비교", "⑤ 검토 의향", "⑥ 모의 주문", "⑦ 회고", "⑧ 주문 화면(재현)"];

/* 검토 의향 4버튼 라벨(계약 §9 — 방향별 세트). 구매 3번째는 ④ 수량 입력을
   반영한 동적 라벨("N주 구매 검토" — 서버가 패턴으로 검증, D-0718-0255). */
/* 구매 흐름의 '아무 것도 안 함' 라벨(D-0718-0327) — 보유가 있으면 '그대로 유지'
   (더 담지 않고 현 보유 유지 = 판매 흐름의 '그대로 유지'와 같은 상태·같은 이름),
   보유 0(첫 구매)이면 유지할 대상이 없어 '구매하지 않기'. ④ 표 열·⑤ 버튼이 공유. */
function buyKeepLabel() {
  return holdingQty() > 0 ? "그대로 유지" : "구매하지 않기";
}
function intentLabels(side) {
  // 구매는 3버튼(D-0718-0310) — 수량 분화는 ④ 입력이 담당, 자의적 수량 버튼 없음.
  return side === "sell"
    ? ["그대로 유지", "일부 판매 검토", "전량 판매 검토", "나중에 재검토"]
    : [buyKeepLabel(), `${S.buyQty}주 구매 검토`, "나중에 재검토"];
}

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/* ── 표시 헬퍼(형식화만 — 계산 없음) ───────────────────── */
function esc(t) {
  return String(t == null ? "" : t)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
function num(n) { return Number(n).toLocaleString("ko-KR"); }
function won(n) { return num(n) + "원"; }
function dateLabel(iso) { // "2026-07-21" → "2026-07-21(화)"
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
  if (!m) return esc(iso);
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return `${iso}(${WEEKDAYS[d.getUTCDay()]})`;
}
/* 손익 4중 표기: 색 + 부호 + 아이콘 + 텍스트(계약 §9) */
function pnlMoney(v) {
  const cls = v > 0 ? "up" : v < 0 ? "down" : "flat";
  const icon = v > 0 ? "▲" : v < 0 ? "▼" : "—";
  const word = v > 0 ? "수익" : v < 0 ? "손실" : "변동 없음";
  return `<span class="pnl ${cls}">${icon} ${(v > 0 ? "+" : "")}${num(v)}원 (${word})</span>`;
}
function pctChange(p) {
  const cls = p > 0 ? "up" : p < 0 ? "down" : "flat";
  const icon = p > 0 ? "▲" : p < 0 ? "▼" : "—";
  const word = p > 0 ? "상승" : p < 0 ? "하락" : "보합";
  return `<span class="pnl ${cls}">${icon} ${(p > 0 ? "+" : "")}${Number(p).toFixed(1)}% (${word})</span>`;
}
function el(id) { return document.getElementById(id); }

/* ── API ──────────────────────────────────────────────── */
async function api(path, options) {
  let res;
  try { res = await fetch(path, options); }
  catch (e) { return { status: 0, body: null }; } // 네트워크 예외 — 호출부가 오류를 표시한다
  let body = null;
  try { body = await res.json(); } catch (e) { body = null; }
  if (body && body.safety) updateSafety(body.safety);
  return { status: res.status, body };
}

/* ── 불러오기 오류 카드(§5.3 — 어떤 fetch 실패도 화면에 흔적을 남긴다, T-0716-2046) ── */
let retryAction = null;
function showAppError(msg, retry) {
  el("app-error").hidden = false;
  el("app-error-text").textContent = msg;
  retryAction = retry || null;
  el("app-error-retry").hidden = !retry;
}
function clearAppError() {
  el("app-error").hidden = true;
  retryAction = null;
}
function loadFailReason(r) {
  if (r.status === 0) return "서버에 연결하지 못했어요.";
  if (r.body && r.body.error && r.body.error.message) return r.body.error.message;
  return `서버 응답을 읽지 못했어요(HTTP ${r.status}).`;
}
function updateSafety(sf) {
  el("sf-facts").textContent = sf.facts_rendered;
  el("sf-nosrc").textContent = sf.no_source;
  el("sf-forbid").textContent = sf.forbidden;
  el("sf-asof").textContent = sf.asof_missing;
}

/* ── 시나리오 로드 ────────────────────────────────────── */
async function loadScenarioList() {
  const r = await api("/api/scenarios");
  if (!r.body || !r.body.ok || !(r.body.scenarios || []).length) {
    showAppError(
      `시나리오 목록을 불러오지 못했어요 — ${loadFailReason(r)} 서버가 실행 중인지 확인해 주세요.`,
      loadScenarioList);
    return;
  }
  clearAppError();
  S.scenarios = r.body.scenarios;
  renderDemoScenarios();
  const def = S.scenarios.find((s) => s.is_default) || S.scenarios[0];
  if (def) await loadScenario(def.scenario_id);
}
async function loadScenario(id) {
  const r = await api("/api/scenario/" + encodeURIComponent(id));
  if (!r.body || !r.body.ok) {
    showAppError(
      `시나리오를 불러오지 못했어요 — ${loadFailReason(r)} 화면은 이전 상태 그대로예요.`,
      () => loadScenario(id));
    return;
  }
  clearAppError();
  S.scenarioId = id;
  S.data = r.body;
  S.step = 0;
  // 흐름 방향(양방향 — D-0718-0225): 시나리오 기본값은 서버 meta.side(보유 기반),
  // 이후 S0의 구매/판매 클릭(setFlowSide)이 이 값을 전환한다.
  S.flowSide = r.body.meta.side;
  S.partialQty = 10;
  S.buyQty = 10;
  S.previews = {};
  S.intent = null;
  S.settledIntent = null;
  S.diaryText = "";
  S.settlement = null;
  S.savedRecord = null;
  S.briefingLoading = false;  // 브리핑은 '브리핑 시작' 시점에 별도 요청(D-0718-0355)
  el("diary-input").value = "";
  el("retro-input").value = "";
  el("sim-badge").textContent = S.data.meta.badge_text;
  renderDemoScenarios();
  await fetchScenarioPreviews();
  renderAll();
  // 팝업은 자동으로 열지 않는다 — S0 주문 화면의 구매/판매 클릭이 유일한
  // 발동 경로(클릭→인터셉트 인과의 재현, D-0718-0210 — 계약 §9)
}
function holdingQty() {
  const h = S.data && S.data.meta.holding;
  return h && h.qty ? h.qty : 0;
}
async function fetchScenarioPreviews() {
  // 양방향(D-0718-0225): 가능한 방향의 미리보기를 전부 선취득 —
  // 보유가 있으면 판매 2종, 예수금이 있으면 구매 2종(최대 4슬롯).
  const jobs = [];
  if (holdingQty() > 0) {
    jobs.push(fetchPreview("partial", "sell", S.partialQty));
    jobs.push(fetchPreview("full", "sell", holdingQty())); // ⑤ "전량 판매 검토"→⑥ 경로용
  }
  if ((S.data.meta.cash || 0) > 0) {
    jobs.push(fetchPreview("b10", "buy", S.buyQty));
  }
  await Promise.all(jobs);
}
async function fetchPreview(key, side, qty) {
  const r = await api("/api/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: S.scenarioId, side, qty }),
  });
  if (r.body && r.body.ok) S.previews[key] = { preview: r.body.preview };
  else S.previews[key] = { error: r.body && r.body.error ? r.body.error.message : "미리보기를 만들 수 없어요." };
}

/* ── 단계 이동 ────────────────────────────────────────── */
function goStep(n) {
  S.step = Math.max(0, Math.min(8, n));
  // 단계 이동 시 팝업은 항상 닫는다 — 발동은 S0 구매/판매 클릭만(D-0718-0210)
  closeIntercept();
  if (S.data) {
    // ②는 진입 시점의 브리핑 상태(로딩/완성)를 반영해 재렌더(D-0718-0355),
    // ⑦·⑧은 ⑤ 일지·재검토 입력을 인용하므로 진입 시점 값으로 재렌더(스테일 방지)
    if (S.step === 2) renderStep2();
    if (S.step === 7) renderStep7();
    if (S.step === 8) renderStep8();
  }
  renderChrome();
  window.scrollTo({ top: 0 });
}
function openIntercept() { el("intercept-backdrop").hidden = false; }
function closeIntercept() { el("intercept-backdrop").hidden = true; }
/* ② 브리핑을 '브리핑 시작' 시점에 요청한다(D-0718-0355) — ①을 읽는 동안
   백그라운드로 생성되고, ② 진입 시 미완이면 renderStep2가 로딩을 표시한다.
   live 모드에서 '바로 주문'을 택한 사용자는 이 요청 자체를 겪지 않는다. */
async function requestBriefing() {
  if (!S.data || S.data.briefing || S.briefingLoading) return;
  S.briefingLoading = true;
  if (S.step === 2) renderStep2();  // 이미 ②에 있으면 즉시 로딩 표시
  const r = await api("/api/briefing/" + encodeURIComponent(S.scenarioId));
  S.briefingLoading = false;
  if (r.body && r.body.ok) {
    S.data.briefing = r.body.briefing;
    S.data.briefing_source = r.body.briefing_source;
    S.data.guard = r.body.guard;
    if (S.step === 2) renderStep2();
  } else {
    showAppError(
      `브리핑을 준비하지 못했어요 — ${loadFailReason(r)} 다시 시도해 주세요.`,
      () => requestBriefing());
    if (S.step === 2) renderStep2();
  }
}
/* S0 구매/판매 클릭 = 흐름 방향 결정 + 인터셉트 발동(양방향 — D-0718-0225) */
function setFlowSide(next) {
  if (next === "sell" && holdingQty() === 0) {
    // 보유 0이면 판매 흐름이 성립하지 않는다 — 방향 유지 + 사실 안내만
    renderStep0();
    el("itc-side-note").textContent =
      "지금은 판매할 보유 수량이 없어요 — 이 종목은 구매 검토만 할 수 있어요.";
    openIntercept();
    return;
  }
  if (S.flowSide === next) {  // 같은 방향 재클릭 = 팝업만(상태 리셋 없음)
    el("itc-side-note").textContent = "";
    openIntercept();
    return;
  }
  applyFlowSideChange(next); // 팝업 내용까지 새 방향 기준으로 재렌더한 뒤
  openIntercept();           // 연다(순서 고정 — 내용 정합)
}
/* 방향 전환 공통 규칙 — 새 검토의 시작: 이전 방향의 의향·체결·기록 표시 초기화 */
function applyFlowSideChange(next) {
  S.flowSide = next;
  S.intent = null;
  S.settledIntent = null;
  S.settlement = null;
  S.savedRecord = null;
  renderAll();
}
/* ④ 검토 방향 전환 세그먼트(D-0718-0255) — 브리핑 후 방향 변경 지원(팝업 없음) */
function switchFlowSide(next) {
  if (S.flowSide === next) return;
  if (next === "sell" && holdingQty() === 0) return; // 보유 0 — 버튼도 disabled
  applyFlowSideChange(next);
}
function renderChrome() {
  document.querySelectorAll(".step-panel").forEach((p) => {
    p.classList.toggle("active", Number(p.dataset.step) === S.step);
  });
  document.querySelectorAll("#progress .pg").forEach((b) => {
    const n = Number(b.dataset.goto);
    b.classList.toggle("on", n === S.step);
    b.classList.toggle("done", n < S.step);
  });
  el("progress-label").textContent = STEP_NAMES[S.step];
  el("wizard-nav").style.display = S.step === 0 ? "none" : "flex";
  el("btn-next").textContent = nextButtonLabel();
  const expanded = document.body.classList.contains("expanded");
  const safemode = document.body.classList.contains("safemode");
  // 모의 고정 바는 주문·체결 화면(S0·⑥·⑧)에 상시 — 계약 §9 모의 표시
  el("mock-order-bar").hidden =
    safemode || !(S.step === 0 || S.step === 6 || S.step === 8 || expanded);
}
/* ⑤에서 주문 의향(판매·구매 검토)을 고른 상태의 "다음"은 주문 화면(⑥) 진입이다 —
   실서비스에서 기존 주문 모듈로 넘어가는 핸드오프 이음새를 라벨로 보여준다(스펙 §0·계약 §9).
   실행 버튼이 아니라 내비게이션이므로 ①~⑤ 주문 버튼 금지 제약과 무관. */
function nextButtonLabel() {
  if (S.step >= 8) return "처음으로 →";
  // ⑦ 종착 분기(계약 §9): 주문 의향을 유지한 상태면 실제 주문 화면(⑧)으로 —
  // 모의 체결 여부와 무관(일지만 쓰고 주문 가는 경로 보존). 보류자는 미유도.
  if (S.step === 7) return orderPlanFromIntent() ? "실제 주문 화면으로 →" : "처음으로 →";
  if (S.step === 5 && orderPlanFromIntent()) return "주문 화면으로 →";
  return "다음 단계 →";
}

/* ── 렌더: 전체 ───────────────────────────────────────── */
function renderAll() {
  renderStep0();
  renderStep1();
  renderStep2();
  renderStep3();
  renderStep4();
  renderStep5();
  renderStep6();
  renderStep7();
  renderStep8();
  renderSafemode();
  renderChrome();
}

/* 주문 화면 재현 공용(S0 진입·⑧ 종착 — 계약 §9): 표시만.
   side 강조 없음 — 구매/판매 병렬·색 구분만(전 시나리오 공통, D-0717-2121).
   실앱 종목 상세 크롬 재현(캡처 27 — 리디자인 S3): 네비 행·탭·거래량 행·차트·기간 칩은
   전부 비기능 장식(span·aria-hidden — 버튼 아님·배선 없음)이다. 수치는 가상 fixture 장식
   [데모 고정]. 차트 방향은 이미 렌더 중인 change_pct 부호를 따른다(표시 전용). */
function replicaChartSvg(changePct) {
  const down = "0,26 28,20 52,38 78,30 106,52 134,46 162,66 190,58 214,78 242,72 270,88 300,82 330,94 360,98";
  const flat = "0,60 30,56 60,63 90,58 120,64 150,59 180,62 210,57 240,63 270,59 300,62 330,58 360,61";
  const pts = changePct < 0 ? down
    : changePct > 0 ? down.split(" ").map(p => { const [x, y] = p.split(","); return `${x},${120 - y}`; }).join(" ")
    : flat;
  const color = changePct < 0 ? "var(--down)" : changePct > 0 ? "var(--up)" : "var(--flat)";
  return `<div class="kp-chart" aria-hidden="true"><svg viewBox="0 0 360 120" preserveAspectRatio="none">
    <line x1="0" y1="30" x2="360" y2="30" stroke="#f2f4f6" stroke-width="1"/>
    <line x1="0" y1="60" x2="360" y2="60" stroke="#f2f4f6" stroke-width="1"/>
    <line x1="0" y1="90" x2="360" y2="90" stroke="#f2f4f6" stroke-width="1"/>
    <polyline points="${pts} 360,120 0,120" fill="${color}" opacity=".05" stroke="none"/>
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
  </svg></div>`;
}

function renderOrderReplica(prefix) {
  const m = S.data.meta;
  const name = m.instrument ? m.instrument.name : "";
  el(prefix + "-header").innerHTML = `
  <div class="kp-nav" aria-hidden="true">
    <svg class="kp-ic" viewBox="0 0 24 24"><path d="M15 4l-8 8 8 8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <span class="kp-nav-sp"></span>
    <svg class="kp-ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 16l4.2 4.2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
    <svg class="kp-ic" viewBox="0 0 24 24"><path d="M6 3h12v18l-6-4.5L6 21z" fill="#ffd338"/></svg>
    <svg class="kp-ic" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></svg>
  </div>
  <div class="price-head kp">
    <div class="kp-nm-row"><span class="nm">${esc(name)} <span class="meta-inline">(가상)</span></span><span class="kp-caret" aria-hidden="true"></span></div>
    <div><span class="pr">${num(m.price.close)}원</span></div>
    <div class="kp-chg-row">${pctChange(m.price.change_pct)} <span class="mk">${esc(m.market_label)}</span></div>
  </div>
  <div class="kp-tabs" aria-hidden="true">
    <span class="kp-tab on">정보</span><span class="kp-tab">차트<i class="kp-dot"></i></span><span class="kp-tab">호가<i class="kp-dot"></i></span><span class="kp-tab">보유</span><span class="kp-tab">토론<i class="kp-dot"></i></span>
  </div>
  <div class="kp-stat-row" aria-hidden="true"><span>거래량 <b>1,842,113</b></span><span>시가총액 <b>3.2조원</b></span></div>
  ${replicaChartSvg(m.price.change_pct)}
  <div class="kp-range" aria-hidden="true"><span class="kp-range-chip">1일</span><span class="kp-range-chip on">1주</span><span class="kp-range-chip">1달</span><span class="kp-range-chip">3달</span><span class="kp-range-chip">1년</span></div>`;
  el(prefix + "-price").textContent = won(m.price.close);
  const st = S.settlement;
  el(prefix + "-qty").textContent = st ? num(st.qty) + "주" : "—";
}

/* S0 · 주문 화면(재현) + 인터셉트 팝업 내용(보유/계좌 요약·리마인드 — 고불안 강조 신호) */
function renderStep0() {
  renderOrderReplica("s0");
  const m = S.data.meta;
  const name = m.instrument ? m.instrument.name : "";
  const titles = {
    loss8: "시장이 크게 흔들린 날이에요",
    profit15: "보유 종목이 목표에 다가선 날이에요",
    first_buy: "탐색에서 발견한 종목을 살펴보는 중이에요",
  };
  el("s0-title").textContent = titles[S.scenarioId] || "판단이 필요한 순간이에요";
  // 팝업 카드는 흐름 방향이 아니라 '보유 유무(데이터 사실)' 기준이다 —
  // 보유 30주 상태에서 구매 클릭 시 "보유 없음"이 뜨는 허위 표시 방지(D-0718-0225).
  let html = "";
  if (holdingQty() > 0) {
    const hold = S.data.hold;
    html += `<div class="kcard">
      <div class="tag fact">보유 종목</div>
      <div><b>${esc(name)}</b> <span class="meta-inline">(가상)</span> ${pctChange(m.price.change_pct)}</div>
      <div class="price-head" style="border:none;margin:0;padding:2px 0 0">
        <span class="pr">${num(m.price.close)}</span><span>원</span>
      </div>
      <div class="sub-note" style="margin:4px 0 0">
        ${num(m.holding.qty)}주 보유 · 평균 구매가 ${won(m.holding.avg_price)}<br>
        평가손익 ${hold ? pnlMoney(hold.eval_pnl) : "확인 불가"} ·
        이 종목 비중 ${hold ? hold.weight_pct.toFixed(1) + "%" : "확인 불가"}${
        (m.cash || 0) > 0 ? `<br>예수금 <b>${won(m.cash)}</b>` : ""}
      </div>
    </div>`;
  } else {
    html += `<div class="kcard">
      <div class="tag fact">내 계좌</div>
      보유 종목이 아직 없어요 · 예수금 <b>${won(m.cash)}</b>
    </div>
    <div class="kcard">
      <div class="tag fact">살펴보는 종목</div>
      <div><b>${esc(name)}</b> <span class="meta-inline">(가상)</span> ${pctChange(m.price.change_pct)}</div>
      <div class="sub-note" style="margin:4px 0 0">현재가 ${won(m.price.close)} · 탐색하기에서 발견한 종목이에요</div>
    </div>`;
  }
  el("itc-holding").innerHTML = html;
  el("itc-side-note").textContent = "";  // 방향 안내는 setFlowSide가 필요 시 채운다

  const records = S.data.past_records || [];
  el("itc-remind").innerHTML = records.map((r) => `
    <div class="kcard quote">
      <div class="tag fact">지난 투자 일지 — 그때 이렇게 적으셨어요</div>
      <div>“${esc(r.reason_text)}”</div>
      <div class="meta"><span>${esc(r.recorded_at)}</span>
        <span>${r.side === "buy" ? "구매" : "판매"} ${num(r.qty)}주 당시 기록</span></div>
    </div>`).join("");
}

/* ① 종목 상세 + 계획 회상 */
function renderStep1() {
  const m = S.data.meta;
  const name = m.instrument ? m.instrument.name : "";
  el("s1-header").innerHTML = `<div class="price-head">
    <div><span class="nm">${esc(name)} <span class="meta-inline">(가상)</span></span>
      <span class="mk">${esc(m.market_label)}</span></div>
    <div><span class="pr">${num(m.price.close)}</span>원 ${pctChange(m.price.change_pct)}</div>
  </div>`;

  const plan = m.plan;
  if (plan) {
    el("s1-plan").innerHTML = `<div class="kcard">
      <div class="tag fact">내 계획 · ${esc(plan.recorded_at)} 기록</div>
      <div class="checkline">목표 기간: <b>${esc(plan.horizon)}</b></div>
      <div class="checkline">감수 가능한 손실: <b>${esc(plan.max_loss_pct)}%까지</b></div>
      <div class="checkline">재검토 조건: <b>${esc(plan.review_condition)}</b></div>
    </div>`;
  } else {
    const qs = (S.data.briefing.next_questions || [])
      .map((q) => `<div class="checkline">${esc(q)}</div>`).join("");
    el("s1-plan").innerHTML = `<div class="kcard notice">
      <div class="tag interp">아직 계획이 없어요</div>
      첫 구매 전이라 기록된 계획과 투자 일지가 0건이에요.
      아래 질문 초안 3가지에 답하면 그것이 첫 계획이 돼요.
    </div>
    <div class="kcard"><div class="tag unk">질문 초안</div>${qs}</div>`;
  }

  const records = S.data.past_records || [];
  el("s1-remind").innerHTML = records.map((r) => `
    <div class="kcard quote">
      <div class="tag fact">지난 투자 일지 — 그때 이렇게 적으셨어요</div>
      <div>“${esc(r.reason_text)}”</div>
      <div class="meta"><span>${esc(r.recorded_at)}</span>
        <span>${r.side === "buy" ? "구매" : "판매"} ${num(r.qty)}주 당시 기록</span>
        <span>내가 쓴 글 인용</span></div>
    </div>`).join("");

  const dc = S.data.discovery_context;
  el("s1-discovery").innerHTML = dc ? `
    <div class="kcard">
      <div class="tag fact">진입 맥락</div>
      <b>${esc(dc.path)}</b> &gt; 「${esc(dc.theme)}」에서 발견했어요
      <div class="meta"><span>기준: ${esc(dc.criteria)}</span><span>${esc(dc.entered_at)}</span></div>
    </div>` : "";
}

/* ② 관련 사실 브리핑 */
const BRIEFING_SOURCE_LABELS = {
  live: "AI 생성(실시간)",
  cache: "준비된 응답(캐시)",
  static: "기본 구성(정적)",
};

function renderStep2() {
  const b = S.data.briefing;
  const m = S.data.meta;

  // 브리핑은 '브리핑 시작' 시점에 별도 요청한다(D-0718-0355) — 아직 없으면
  // 로딩 표시. requestBriefing 완료 시 renderStep2가 다시 불려 실제 내용이 채워진다.
  if (!b) {
    el("s2-src").innerHTML = "";
    el("s2-facts").innerHTML = `<div class="kcard notice">${
      S.briefingLoading
        ? "브리핑을 준비하고 있어요… 잠시만 기다려 주세요."
        : "‘판단 전 브리핑 시작하기’를 누르면 브리핑을 준비해요."}</div>`;
    ["s2-interps", "s2-unknowns", "s2-questions", "s2-buzz"].forEach((id) =>
      (el(id).innerHTML = ""));
    return;
  }

  const srcLabel = BRIEFING_SOURCE_LABELS[S.data.briefing_source] || "";
  el("s2-src").innerHTML = srcLabel
    ? `<span>브리핑 생성: ${esc(srcLabel)}</span>` : "";

  let facts = (b.facts || []).map((f) => `
    <div class="kcard">
      <div class="tag fact">확인된 사실</div>
      ${esc(f.text)}
      <div class="meta"><span>출처: ${esc(f.source_id)}(가상)</span><span>기준시각 ${esc(f.as_of)}</span></div>
    </div>`).join("");
  if (m.disclosures_state) {
    facts += `<div class="kcard state">공시 — ${esc(m.disclosures_state)} · 여기서는 값을 만들어 채우지 않아요</div>`;
  }
  if ((m.unavailable || []).includes("price")) {
    facts += `<div class="kcard state">시세 — 확인 불가(데이터 없음)</div>`;
  }
  el("s2-facts").innerHTML = facts;

  const warn = (S.data.guard.record.warnings || [])
    .some((w) => w.code === "one_sided_interpretation");
  let interps = (b.interpretations || []).map((it) => `
    <div class="kcard">
      <div class="tag interp">해석 — 사실이 아니에요</div>
      <span class="stance-pill">${esc(it.stance)}</span>${esc(it.text)}
    </div>`).join("");
  if (warn) interps += `<div class="kcard state">반대 시각 확인 안 됨 — 한쪽 해석만 남았어요</div>`;
  if ((m.unavailable || []).includes("interpretations")) {
    interps += `<div class="kcard state">해석 — 확인 불가(등록된 해석 없음)</div>`;
  }
  el("s2-interps").innerHTML = interps;

  el("s2-unknowns").innerHTML = (b.unknowns || []).length ? `
    <div class="kcard">
      <div class="tag unk">알 수 없는 것</div>
      ${(b.unknowns || []).map((u) => `<div class="checkline">${esc(u)}</div>`).join("")}
    </div>` : "";

  el("s2-questions").innerHTML = (b.next_questions || []).length ? `
    <div class="kcard">
      <div class="tag unk">다음에 확인할 질문</div>
      ${(b.next_questions || []).map((q) => `<div class="checkline">${esc(q)}</div>`).join("")}
    </div>` : "";

  const buzz = S.data.community_buzz;
  el("s2-buzz").innerHTML = buzz ? `
    <div class="kcard">
      <div class="tag buzz">커뮤니티 관심 지표</div>
      ${esc(buzz.note)}
      <div class="meta"><span>관심 수준: ${esc(buzz.level)}</span><span>사실 카드와 분리 표시</span></div>
    </div>` : "";
}

/* ③ 체크리스트 5문 + 이해 확인 */
function renderStep3() {
  const side = S.flowSide;  // 흐름 방향 = S0 진입 클릭(양방향 — D-0718-0225)
  const items = side === "sell" ? [
    "오늘 상황이 내 재검토 조건에 해당하는지 확인했나요?",
    "사실과 해석을 구분해서 봤나요?",
    "판매할 경우의 비용·세금·출금일을 알고 있나요?",
    "오늘 꼭 결정해야 하는 이유가 있나요?",
    "내 결정의 이유를 한 문장으로 쓸 수 있나요?",
  ] : [
    "나만의 목표 기간·감수 손실·재검토 조건을 정했나요?",
    "사실과 해석을 구분해서 봤나요?",
    "구매할 경우의 비용과 결제일(D+2)을 알고 있나요?",
    "오늘 꼭 구매를 결정해야 하는 이유가 있나요?",
    "내 결정의 이유를 한 문장으로 쓸 수 있나요?",
  ];
  el("s3-checklist").innerHTML = `<div class="kcard">
    ${items.map((t, i) => `<label class="checkline"><input type="checkbox" aria-label="체크 항목 ${i + 1}"> <span>${esc(t)}</span></label>`).join("")}
  </div>`;

  const cost = side === "sell"
    ? "비용: 수수료 0.015% + 세금 0.20%가 판매대금에서 빠져요 — 여기서 세금은 증권거래세·농어촌특별세를 합한 금액이에요."
    : "비용: 수수료 0.015%가 결제액에 더해져요 — 구매할 때는 세금이 붙지 않아요.";
  el("s3-notice").innerHTML = `<div class="kcard">
    <div class="tag fact">주문 전 알아 둘 것</div>
    <div class="checkline">주문 유형: 이 데모는 지정가(표시 가격) 기준이에요 — 시장가는 표시 가격과 다르게 체결될 수 있어요.</div>
    <div class="checkline">${esc(cost)}</div>
    <div class="checkline">출금·결제: 대금은 체결 2영업일 뒤(D+2)에 움직여요.</div>
    <div class="checkline">취소: 체결 뒤에는 되돌릴 수 없어요.</div>
  </div>`;
}

/* ④ 대칭 시나리오 비교(엔진 결과 표시 — 모든 열 동일 크기·강조색 없음) */
function renderSideToggle() {
  const canSell = holdingQty() > 0;
  el("s4-side-toggle").innerHTML = `<div class="side-toggle" role="group" aria-label="검토 방향 전환">
    <button type="button" class="side-toggle-btn${S.flowSide === "sell" ? " on" : ""}"
      data-side="sell" ${canSell ? "" : "disabled"}>판매 검토</button>
    <button type="button" class="side-toggle-btn${S.flowSide === "buy" ? " on" : ""}"
      data-side="buy">구매 검토</button>
  </div>${canSell ? "" : `<p class="sub-note">판매할 보유 수량이 없어 구매 검토만 할 수 있어요.</p>`}`;
  el("s4-side-toggle").querySelectorAll("button").forEach((btn) =>
    btn.addEventListener("click", () => switchFlowSide(btn.dataset.side)));
}
function renderStep4() {
  const m = S.data.meta;
  const side = S.flowSide;
  renderSideToggle();
  el("s4-basis").textContent =
    `가상 기준시각 ${m.as_of} · 지정가 ${num(m.price.close)}원 · 수수료 0.015%` +
    (side === "sell" ? " · 세금 0.20%" : " · 구매는 세금 없음");
  el("s4-remember").textContent = side === "sell"
    ? "판매는 되돌릴 수 없고, 대금 출금은 체결 2영업일 뒤예요."
    : "체결 후에는 취소할 수 없고, 결제 대금은 체결 2영업일 뒤에 움직여요.";

  if (side === "sell") {
    // 양방향 공통 2열 = [현 상태 유지 / N주(입력)] — 자의적 고정 수량 열 없음
    // (D-0718-0310). 전량은 입력으로 표현(보유 전량 입력 시 라벨 병기).
    el("s4-qty").innerHTML = `<div class="qty-row">
      <label for="partial-qty">판매 수량</label>
      <input id="partial-qty" type="number" inputmode="numeric" value="${S.partialQty}" aria-label="판매 수량 입력">
      <span>주 (기본 10주 · 보유 ${num(holdingQty())}주)</span></div>
      <p id="partial-error" class="err-text" hidden></p>`;
    el("partial-qty").addEventListener("change", onPartialQtyChange);

    const hold = S.data.hold;
    const p = S.previews.partial || {};
    const pv = p.preview;
    if (p.error) { el("partial-error").hidden = false; el("partial-error").textContent = p.error; }
    const sellHead = pv
      ? `${num(pv.inputs.qty)}주 판매${pv.is_full_sell ? " — 보유 전량입니다" : ""}`
      : `${esc(String(S.partialQty))}주 판매`;

    el("s4-table").innerHTML = `<div class="cmp-wrap"><table class="cmp">
      <tr><th>항목</th><th>그대로 유지</th><th>${sellHead}</th></tr>
      <tr><td>대금</td><td>—</td><td>${pv ? won(pv.gross_amount) : "—"}</td></tr>
      <tr><td>수수료</td><td>—</td><td>${pv ? won(pv.fee) : "—"}</td></tr>
      <tr><td>세금</td><td>—</td><td>${pv ? won(pv.tax) : "—"}</td></tr>
      <tr><td>예상 수령액</td><td>—</td><td>${pv ? "<b>" + won(pv.net_proceeds) + "</b>" : "—"}</td></tr>
      <tr><td>확정 손익</td><td>0원(평가손익 ${hold ? pnlMoney(hold.eval_pnl) : "—"} 유지)</td>
          <td>${pv ? pnlMoney(pv.realized_pnl) : "—"}</td></tr>
      <tr><td>잔여 수량</td><td>${num(holdingQty())}주</td><td>${pv ? num(pv.remaining_qty) + "주" : "—"}</td></tr>
      <tr><td>체결 후 평균 구매가</td><td>${won(m.holding.avg_price)}</td>
          <td>${pv ? (pv.avg_price_after == null ? "— (잔여 없음)" : won(pv.avg_price_after) + " (변동 없음)") : "—"}</td></tr>
      <tr><td>남는 비중</td><td>${hold ? hold.weight_pct.toFixed(1) + "%" : "—"}</td>
          <td>${pv ? pv.remaining_weight_pct.toFixed(1) + "%" : "—"}</td></tr>
      <tr><td>출금 가능일</td><td>—</td><td>${pv ? dateLabel(pv.settlement_date) : "—"}</td></tr>
    </table></div>`;
  } else {
    // 구매 수량 조정(D-0718-0255) — 판매의 '일부 판매 수량'과 대칭
    el("s4-qty").innerHTML = `<div class="qty-row">
      <label for="buy-qty">구매 수량</label>
      <input id="buy-qty" type="number" inputmode="numeric" value="${S.buyQty}" aria-label="구매 수량 입력">
      <span>주 (기본 10주)</span></div>
      <p id="buy-error" class="err-text" hidden></p>`;
    el("buy-qty").addEventListener("change", onBuyQtyChange);
    const b = S.previews.b10 || {};
    const bv = b.preview;
    if (b.error) { el("buy-error").hidden = false; el("buy-error").textContent = b.error; }
    const warnBadge = (v) => (v && v.concentration_warning
      ? ` <span class="warn-note" style="display:inline;padding:1px 6px">집중도 경고</span>` : "");
    const hasHolding = holdingQty() > 0;
    el("s4-table").innerHTML = `<div class="cmp-wrap"><table class="cmp">
      <tr><th>항목</th><th>${buyKeepLabel()}</th><th>${bv ? num(bv.inputs.qty) : esc(String(S.buyQty))}주 구매</th></tr>
      <tr><td>구매대금</td><td>—</td><td>${bv ? won(bv.gross_amount) : esc(b.error || "—")}</td></tr>
      <tr><td>수수료</td><td>—</td><td>${bv ? won(bv.fee) : "—"}</td></tr>
      <tr><td>총 결제예정액</td><td>—</td><td>${bv ? "<b>" + won(bv.total_cost) + "</b>" : "—"}</td></tr>
      <tr><td>잔여 예수금</td><td>${won(m.cash)} (그대로)</td><td>${bv ? won(bv.remaining_cash) : "—"}</td></tr>
      <tr><td>구매 후 비중</td><td>—</td>
          <td>${bv ? bv.weight_after_pct.toFixed(1) + "%" + warnBadge(bv) : "—"}</td></tr>
      <tr><td>체결 후 평균 구매가</td><td>${hasHolding ? won(m.holding.avg_price) + " (변동 없음)" : "—"}</td>
          <td>${bv ? won(bv.avg_price_after) : "—"}</td></tr>
      <tr><td>결제일</td><td>—</td><td>${bv ? dateLabel(bv.settlement_date) : "—"}</td></tr>
    </table></div>` +
    (bv && bv.concentration_warning
      ? `<div class="warn-note">구매 후 비중이 40%를 넘는 열이 있어요 — 집중도 경고예요(주문을 막지는 않아요 · 정보 표시).</div>`
      : "");
  }
}
async function onPartialQtyChange(ev) {
  const raw = ev.target.value;
  const n = Number(raw);
  S.partialQty = Number.isInteger(n) ? n : raw; // 검증은 서버(엔진)가 한다 — §5.3 메시지 표시
  await fetchPreview("partial", "sell", S.partialQty);
  renderStep4();
  renderStep6();
}
async function onBuyQtyChange(ev) {
  const raw = ev.target.value;
  const n = Number(raw);
  const prevLabel = `${S.buyQty}주 구매 검토`;
  S.buyQty = Number.isInteger(n) ? n : raw; // 검증은 서버(엔진)가 한다 — §5.3 메시지 표시
  await fetchPreview("b10", "buy", S.buyQty);
  // 이전 수량 라벨의 구매 의향을 선택해 둔 상태면 새 수량 라벨로 갱신(계약 §9 —
  // 체결 스냅샷 settledIntent는 불변)
  if (S.intent === prevLabel) S.intent = `${S.buyQty}주 구매 검토`;
  renderStep4();
  renderStep5();
  renderStep6();
}

/* ⑤ 검토 의향 버튼(판매 4·구매 3 — 계약 §9) + 투자 일지 */
function renderStep5() {
  const side = S.flowSide;
  const labels = intentLabels(side);
  document.querySelectorAll(".intent-btn").forEach((btn, i) => {
    const label = labels[i];
    btn.hidden = !label;                 // 구매는 3버튼 — 남는 슬롯 숨김
    if (!label) return;
    btn.textContent = label;
    btn.dataset.intent = label;
    btn.classList.toggle("sel", S.intent === label);
  });
  const hasDraft = Boolean(S.data.diary_draft);
  el("btn-draft").hidden = !hasDraft;
  el("draft-note").hidden = !hasDraft;
}

/* ⑥ 별도 모의 주문 화면 */
function orderPlanFromIntent() {
  if (!S.data) return null;
  const side = S.flowSide;
  if (side === "sell") {
    if (S.intent === "일부 판매 검토") return { key: "partial", side };
    if (S.intent === "전량 판매 검토") return { key: "full", side };
  } else {
    if (S.intent === `${S.buyQty}주 구매 검토`) return { key: "b10", side };
  }
  return null;
}
function renderStep6() {
  const m = S.data.meta;
  const plan = orderPlanFromIntent();
  const sideWord = S.flowSide === "sell" ? "판매" : "구매";

  if (S.settlement) {
    el("s6-summary").innerHTML = "";
    el("btn-open-sheet").hidden = true;
    el("btn-skip-order").hidden = true;
    renderSettleResult();
    return;
  }
  el("s6-result").innerHTML = "";

  if (!plan) {
    el("s6-summary").innerHTML = `<div class="kcard state">
      지금 검토 의향은 <b>${esc(S.intent || "아직 선택 없음")}</b> — 주문으로 이어지지 않는 선택이에요.
      주문 없이 회고로 갈 수 있어요.</div>`;
    el("btn-open-sheet").hidden = true;
    el("btn-skip-order").hidden = false;
    return;
  }
  const slot = S.previews[plan.key] || {};
  if (!slot.preview) {
    el("s6-summary").innerHTML = `<div class="kcard state">미리보기를 만들 수 없어요 — ${esc(slot.error || "수량을 다시 확인해 주세요.")}</div>`;
    el("btn-open-sheet").hidden = true;
    el("btn-skip-order").hidden = false;
    return;
  }
  const v = slot.preview;
  const name = m.instrument ? m.instrument.name : "";
  const rows = [
    ["종목", `${esc(name)} (가상)`],
    ["주문 유형", `지정가 ${won(m.price.close)} (시장가 아님)`],
    ["수량", `<b>${num(v.inputs.qty)}주</b> — 입력하신 수량 그대로`],
    ["예상 체결시장", "KRX·NXT 중 유리한 시장 자동 배분(SOR) · 계산은 KRX 기준"],
  ];
  if (S.flowSide === "sell") {
    rows.push(["예상 판매대금", won(v.gross_amount)],
      ["수수료", won(v.fee)],
      ["세금", won(v.tax)],
      ["예상 수령액", `<b>${won(v.net_proceeds)}</b>`],
      ["실현손익(예상)", pnlMoney(v.realized_pnl)],
      ["출금 가능일", `${dateLabel(v.settlement_date)} — 체결 2영업일 뒤(D+2)`]);
  } else {
    rows.push(["구매대금", won(v.gross_amount)],
      ["수수료", won(v.fee)],
      ["총 결제예정액", `<b>${won(v.total_cost)}</b>`],
      ["잔여 예수금", won(v.remaining_cash)],
      ["결제일", `${dateLabel(v.settlement_date)} — 체결 2영업일 뒤(D+2)`]);
    if (v.concentration_warning) {
      rows.push(["집중도", `구매 후 비중 ${v.weight_after_pct.toFixed(1)}% — 40%를 넘어요(정보 표시)`]);
    }
  }
  el("s6-summary").innerHTML = `<div class="kcard">
    <div class="tag fact">주문 요약 — ${esc(S.intent)}</div>
    ${rows.map(([k, val]) => `<div class="sheet-row"><span>${k}</span><span>${val}</span></div>`).join("")}
  </div>`;
  el("btn-open-sheet").hidden = false;
  el("btn-skip-order").hidden = false;
  el("btn-open-sheet").textContent = `${sideWord} 주문 내용 확인하기`;
}
function openSheet() {
  const plan = orderPlanFromIntent();
  if (!plan) return;
  const slot = S.previews[plan.key];
  if (!slot || !slot.preview) return;
  const v = slot.preview;
  const m = S.data.meta;
  const name = m.instrument ? m.instrument.name : "";
  const sideSell = S.flowSide === "sell";

  el("sheet-rows").innerHTML = [
    ["종목", `${esc(name)} (가상)`],
    ["수량", `${num(v.inputs.qty)}주`],
    [sideSell ? "예상 수령액" : "총 결제예정액",
      `<b>${won(sideSell ? v.net_proceeds : v.total_cost)}</b>`],
  ].map(([k, val]) => `<div class="sheet-row"><span>${k}</span><span>${val}</span></div>`).join("");

  const notices = sideSell ? [
    `수수료 ${won(v.fee)}과 세금 ${won(v.tax)}이 대금에서 빠져요.`,
    `실현손익(예상): ${pnlMoney(v.realized_pnl)} — 체결 시 확정돼요.`,
    `출금 가능일: ${dateLabel(v.settlement_date)} — 체결 2영업일 뒤(D+2)예요.`,
    "체결 후에는 취소할 수 없어요.",
  ] : [
    `수수료 ${won(v.fee)}이 결제액에 더해져요(구매는 세금 없음).`,
    `총 결제예정액 ${won(v.total_cost)} · 잔여 예수금 ${won(v.remaining_cash)}.`,
    `결제일: ${dateLabel(v.settlement_date)} — 체결 2영업일 뒤(D+2)예요.`,
    "체결 후에는 취소할 수 없어요."
      + (v.concentration_warning ? ` 구매 후 비중 ${v.weight_after_pct.toFixed(1)}% — 집중도 경고(정보 표시).` : ""),
  ];
  el("sheet-notices").innerHTML = notices.map((t, i) =>
    `<div class="notice-item"><span class="no">고지 ${i + 1}</span>${t}</div>`).join("");

  el("confirm-ack").checked = false;
  el("sheet-error").hidden = true;
  const btn = el("btn-settle");
  btn.textContent = sideSell ? "모의 판매 체결하기" : "모의 구매 체결하기";
  btn.classList.toggle("side-sell", sideSell);
  btn.classList.toggle("side-buy", !sideSell);
  btn.disabled = true;   // 비가역 확인 체크 전까지 비활성
  el("sheet-backdrop").hidden = false;
}
async function doSettle() {
  const plan = orderPlanFromIntent();
  if (!plan) return;
  const slot = S.previews[plan.key];
  if (!slot || !slot.preview) return;
  if (!el("confirm-ack").checked) {
    el("sheet-error").hidden = false;
    el("sheet-error").textContent = "체결 전에 확인 항목에 체크해 주세요.";
    return;
  }
  const r = await api("/api/settle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: S.scenarioId, preview: slot.preview, confirmed_qty: slot.preview.inputs.qty }),
  });
  if (r.body && r.body.ok) {
    S.settlement = r.body.settlement;
    S.settledIntent = S.intent; // 체결 시점 의향 스냅샷 — ⑦ 표기는 이후 의향 변경과 분리
    el("sheet-backdrop").hidden = true;
    renderStep6();
    renderStep7();
    renderStep8();
  } else {
    el("sheet-error").hidden = false;
    el("sheet-error").textContent = (r.body && r.body.error) ? r.body.error.message : "체결을 만들 수 없어요.";
  }
}
function renderSettleResult() {
  const st = S.settlement;
  if (!st) return;
  const m = S.data.meta;
  const name = m.instrument ? m.instrument.name : "";
  const sideWord = st.side === "sell" ? "판매" : "구매";
  el("s6-result").innerHTML = `<div class="kcard">
    <div class="tag fact">모의 체결 완료(실제 거래 아님)</div>
    ${esc(name)} ${num(st.qty)}주 · ${won(st.price)} ${sideWord} 체결(모의)<br>
    ${st.side === "sell"
      ? `예상 수령 ${won(st.net_proceeds)} · 출금 가능일 ${dateLabel(st.settlement_date)}`
      : `총 결제 ${won(st.total_cost)} · 결제일 ${dateLabel(st.settlement_date)}`}
    <div class="meta"><span>${esc(st.calculation_id)}</span><span>${esc(st.settled_at)}</span><span>모의 여부: 항상 예</span></div>
  </div>`;
}

/* ⑦ 사후 회고 + 기록 저장 */
function renderStep7() {
  const st = S.settlement;
  const m = S.data.meta;
  el("s7-settlement").innerHTML = st ? `<div class="kcard">
      <div class="tag fact">모의 체결 요약</div>
      ${st.side === "sell" ? "판매" : "구매"} ${num(st.qty)}주 · ${won(st.price)} ·
      ${st.side === "sell" ? `수령 ${won(st.net_proceeds)}` : `결제 ${won(st.total_cost)}`}
      · ${dateLabel(st.settlement_date)}
    </div>` : `<div class="kcard state">이번에는 주문 없이 검토를 마쳤어요 — 그것도 하나의 결정이에요.</div>`;

  const plan = m.plan;
  el("s7-contrast").innerHTML = `<div class="kcard quote">
      <div class="tag fact">내가 적은 투자 일지</div>
      <div>${S.diaryText ? "“" + esc(S.diaryText) + "”" : "아직 일지를 적지 않았어요 — ⑤에서 적을 수 있어요."}</div>
      <div class="meta"><span>선택: ${esc((S.settlement ? (S.settledIntent || S.intent) : S.intent) || "선택 없음")}</span></div>
    </div>` +
    (plan ? `<div class="kcard">
      <div class="tag fact">계획과 나란히 보기</div>
      <div class="checkline">계획(${esc(plan.recorded_at)} 기록): ${esc(plan.horizon)} · 감수 ${esc(plan.max_loss_pct)}% · 재검토 조건 「${esc(plan.review_condition)}」</div>
      <div class="checkline">오늘의 일지가 이 계획과 이어지는지 스스로 견줘 보세요.</div>
    </div>` : "");

  el("s7-saved").innerHTML = S.savedRecord ? `<div class="kcard">
      <div class="tag fact">기록 완료</div>
      ${esc(S.savedRecord.record_id)} 로 저장됐어요.
      결과 수익률은 저장하지 않아요 — 과정(계획 확인 → 사실·해석 구분 → 비용·일정 확인 → 내 문장 기록)이 남아요.
    </div>` : "";
}
async function saveRecord() {
  const errEl = el("record-error");
  errEl.hidden = true;
  if (!S.intent) {
    errEl.hidden = false;
    errEl.textContent = "⑤에서 검토 의향을 먼저 선택해 주세요.";
    return;
  }
  if (!S.diaryText.trim()) {
    errEl.hidden = false;
    errEl.textContent = "⑤에서 투자 일지를 한 문장 적어 주세요.";
    return;
  }
  const plan = orderPlanFromIntent();
  const previewCalc = plan && S.previews[plan.key] && S.previews[plan.key].preview
    ? S.previews[plan.key].preview.calculation_id : null;
  const calcId = S.settlement ? S.settlement.calculation_id : previewCalc;
  const review = el("retro-input").value.trim();
  const r = await api("/api/record", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario_id: S.scenarioId,
      intent: S.intent,
      reason_text: S.diaryText.trim(),
      calculation_id: calcId,
      review_date: review || null,
    }),
  });
  if (r.body && r.body.ok) {
    S.savedRecord = r.body.record;
    renderStep7();
  } else {
    errEl.hidden = false;
    errEl.textContent = (r.body && r.body.error) ? r.body.error.message : "저장하지 못했어요.";
  }
}

/* ⑧ 주문 화면(실앱 재현·종착 — 계약 §9): 버튼 전부 disabled·배선 없음(재인터셉트 없음).
   브리핑 재진입 배너 대신 '내 판단 기록 상기' 카드 — 주문 직전에 내 일지를 다시 본다. */
function renderStep8() {
  renderOrderReplica("s8");
  const st = S.settlement;
  const chosen = st ? (S.settledIntent || S.intent) : S.intent;
  const review = el("retro-input").value.trim();
  const diary = S.diaryText.trim();
  el("s8-judgment").innerHTML = diary ? `<div class="kcard quote">
      <div class="tag fact">내 판단 기록 — 주문 전에 다시 봐요</div>
      <div>“${esc(diary)}”</div>
      <div class="meta"><span>선택: ${esc(chosen || "선택 없음")}</span>${review ? `<span>다음 재검토: ${esc(review)}</span>` : ""}</div>
    </div>` : `<div class="kcard state">이번 주문에는 아직 투자 일지가 없어요.</div>`;
  el("s8-handoff").innerHTML = st ? `<div class="kcard state">
    모의 체결 기록: ${st.side === "sell" ? "판매" : "구매"} ${num(st.qty)}주 · ${won(st.price)} — 실제 거래 아님</div>` : "";
}

/* 장애 안전모드 화면(오버레이 — 계약 §8): 주문 상태 카드만 동적 */
function renderSafemode() {
  const st = S.settlement;
  el("safe-order-state").innerHTML = `<div class="kcard">
    <div class="tag fact">내 주문 상태</div>
    ${st ? `모의 ${st.side === "sell" ? "판매" : "구매"} ${num(st.qty)}주 — 체결 기록이 있어요(${esc(st.settled_at)})`
         : "진행 중인 주문이 없어요."}
  </div>`;
}

/* ── DEMO 패널 ────────────────────────────────────────── */
function renderDemoScenarios() {
  el("demo-scenarios").innerHTML = S.scenarios.map((s) =>
    `<button class="demo-scn${s.scenario_id === S.scenarioId ? " on" : ""}" data-sid="${esc(s.scenario_id)}" type="button">
      ${esc(s.title)}${s.is_default ? " · 기본" : ""}</button>`).join("");
  document.querySelectorAll(".demo-scn").forEach((b) => {
    b.addEventListener("click", () => loadScenario(b.dataset.sid));
  });
}
function toggleSafemode(onFlag) {
  // 오버레이 방식: S.step을 바꾸지 않는다 — 해제하면 보던 화면·전체 펼침 상태 그대로 복귀(계약 §8)
  document.body.classList.toggle("safemode", onFlag);
  if (onFlag) {
    el("sheet-backdrop").hidden = true; // 열린 재확인 시트도 주문 유도 — 강제로 닫는다
    closeIntercept();                   // 진입 팝업도 동일 취급
    renderSafemode();
  }
  renderChrome();
  window.scrollTo({ top: 0 });
}

/* ── 이벤트 배선 ──────────────────────────────────────── */
function wireEvents() {
  el("btn-start").addEventListener("click", () => {
    requestBriefing();  // 비동기 시작 — ①(계획 회상)을 읽는 동안 백그라운드 생성
    goStep(1);          // goStep이 팝업을 닫는다
  });
  // 레이어는 투자 행동을 막지 않는다 — "바로 주문"은 팝업만 닫고 주문 화면(S0 재현)에 머묾(계약 §9)
  el("btn-skip-briefing").addEventListener("click", closeIntercept);
  // S0 배경 주문 버튼 = 흐름 방향 결정 + 인터셉트 발동(주문 실행 아님 — D-0718-0225)
  el("s0-order-buy").addEventListener("click", () => setFlowSide("buy"));
  el("s0-order-sell").addEventListener("click", () => setFlowSide("sell"));
  el("btn-prev").addEventListener("click", () => goStep(S.step - 1));
  el("btn-next").addEventListener("click", () => {
    if (S.step >= 8) return goStep(0);
    if (S.step === 7 && !orderPlanFromIntent()) return goStep(0); // 보류 완주 → 처음으로(⑧ 미유도)
    goStep(S.step + 1);
  });
  document.querySelectorAll("#progress .pg").forEach((b) => {
    b.addEventListener("click", () => goStep(Number(b.dataset.goto)));
  });

  el("quiz-o").addEventListener("click", () => {
    el("quiz-o").classList.add("sel"); el("quiz-x").classList.remove("sel");
    el("quiz-answer").hidden = false;
  });
  el("quiz-x").addEventListener("click", () => {
    el("quiz-x").classList.add("sel"); el("quiz-o").classList.remove("sel");
    el("quiz-answer").hidden = false;
  });

  document.querySelectorAll(".intent-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      S.intent = btn.dataset.intent;
      document.querySelectorAll(".intent-btn").forEach((x) =>
        x.classList.toggle("sel", x === btn));
      renderStep6();
      renderStep7();
      renderChrome(); // ⑤에 머문 상태에서 진행 버튼 라벨 즉시 갱신
    });
  });

  el("diary-input").addEventListener("input", (ev) => {
    S.diaryText = ev.target.value;
  });
  el("btn-draft").addEventListener("click", () => {
    if (!S.data.diary_draft) return;
    el("diary-input").value = S.data.diary_draft; // 채우기만 — 저장은 사용자 버튼으로만
    S.diaryText = S.data.diary_draft;
  });

  el("app-error-retry").addEventListener("click", () => { if (retryAction) retryAction(); });
  el("btn-open-sheet").addEventListener("click", openSheet);
  el("btn-sheet-back").addEventListener("click", () => { el("sheet-backdrop").hidden = true; });
  el("btn-settle").addEventListener("click", doSettle);
  el("confirm-ack").addEventListener("change", (e) => {
    el("btn-settle").disabled = !e.target.checked;
    if (e.target.checked) el("sheet-error").hidden = true;
  });
  el("btn-skip-order").addEventListener("click", () => goStep(7));
  el("btn-save-record").addEventListener("click", saveRecord);
  el("btn-safe-exit").addEventListener("click", () => {
    el("demo-safemode").checked = false; // 버튼 해제는 change 이벤트가 없으므로 수동 동기화
    toggleSafemode(false);
  });

  el("demo-toggle").addEventListener("click", () => {
    const panel = el("demo-panel");
    panel.classList.toggle("collapsed");
    const open = !panel.classList.contains("collapsed");
    el("demo-toggle").textContent = open ? "DEMO 패널 접기" : "DEMO 패널 열기";
    el("demo-toggle").setAttribute("aria-expanded", String(open));
  });
  el("demo-safemode").addEventListener("change", (ev) => toggleSafemode(ev.target.checked));
  el("demo-expand").addEventListener("change", (ev) => {
    document.body.classList.toggle("expanded", ev.target.checked);
    if (ev.target.checked) closeIntercept(); // 전체 펼침 열람을 팝업이 가리지 않게
    renderChrome();
  });
}

/* ── 시작 ─────────────────────────────────────────────── */
window.goStep = goStep; // 시연 검증(playwright)·콘솔 진단에서 사용
document.addEventListener("DOMContentLoaded", () => {
  wireEvents();
  loadScenarioList();
});
