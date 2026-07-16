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
  partialQty: 10,      // ④ 일부 판매 수량(기본 10주)
  previews: {},        // key(partial|full|b8|b10) → {preview}|{error}
  intent: null,        // ⑤ 검토 의향(4택 라벨)
  settledIntent: null, // 체결 시점 의향 스냅샷 — ⑦ "선택:" 표기 고정(이후 의향 변경과 분리)
  diaryText: "",
  settlement: null,
  savedRecord: null,
};

const STEP_NAMES = ["홈", "① 종목·계획", "② 관련 사실", "③ 체크리스트",
  "④ 시나리오 비교", "⑤ 검토 의향", "⑥ 모의 주문", "⑦ 회고", "⑧ 주문 화면(재현)"];

const INTENTS = {
  sell: ["그대로 유지", "일부 판매 검토", "전량 판매 검토", "나중에 재검토"],
  buy: ["구매하지 않기", "8주 구매 검토", "10주 구매 검토", "나중에 재검토"],
};

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
  S.partialQty = 10;
  S.previews = {};
  S.intent = null;
  S.settledIntent = null;
  S.diaryText = "";
  S.settlement = null;
  S.savedRecord = null;
  el("diary-input").value = "";
  el("retro-input").value = "";
  el("sim-badge").textContent = S.data.meta.badge_text;
  renderDemoScenarios();
  await fetchScenarioPreviews();
  renderAll();
}
function holdingQty() {
  const h = S.data && S.data.meta.holding;
  return h && h.qty ? h.qty : 0;
}
async function fetchScenarioPreviews() {
  const side = S.data.meta.side;
  if (side === "sell") {
    await Promise.all([
      fetchPreview("partial", "sell", S.partialQty),
      fetchPreview("full", "sell", holdingQty()),
    ]);
  } else {
    await Promise.all([
      fetchPreview("b8", "buy", 8),
      fetchPreview("b10", "buy", 10),
    ]);
  }
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
  renderChrome();
  window.scrollTo({ top: 0 });
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
  // 모의 고정 바는 주문·체결 화면(⑥·⑧ 재현)에 상시 — 계약 §9 모의 표시
  el("mock-order-bar").hidden = safemode || !(S.step === 6 || S.step === 8 || expanded);
}
/* ⑤에서 주문 의향(판매·구매 검토)을 고른 상태의 "다음"은 주문 화면(⑥) 진입이다 —
   실서비스에서 기존 주문 모듈로 넘어가는 핸드오프 이음새를 라벨로 보여준다(스펙 §0·계약 §9).
   실행 버튼이 아니라 내비게이션이므로 ①~⑤ 주문 버튼 금지 제약과 무관. */
function nextButtonLabel() {
  if (S.step >= 8) return "처음으로 →";
  // ⑦ 종착 분기(계약 §9): 모의 체결이 있어야 실제 주문 화면(⑧ 재현)으로 —
  // 보류 사용자는 주문 화면으로 유도하지 않는다.
  if (S.step === 7) return S.settlement ? "실제 주문 화면으로 →" : "처음으로 →";
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

/* S0 · 보유 홈 */
function renderStep0() {
  const m = S.data.meta;
  const name = m.instrument ? m.instrument.name : "";
  const titles = {
    loss8: "시장이 크게 흔들린 날이에요",
    profit15: "보유 종목이 목표에 다가선 날이에요",
    first_buy: "탐색에서 발견한 종목을 살펴보는 중이에요",
  };
  el("s0-title").textContent = titles[S.scenarioId] || "오늘의 보유 현황이에요";
  let html = "";
  if (m.side === "sell") {
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
        이 종목 비중 ${hold ? hold.weight_pct.toFixed(1) + "%" : "확인 불가"}
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
  el("s0-holding").innerHTML = html;
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
function renderStep2() {
  const b = S.data.briefing;
  const m = S.data.meta;

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
  const side = S.data.meta.side;
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
function renderStep4() {
  const m = S.data.meta;
  const side = m.side;
  el("s4-basis").textContent =
    `가상 기준시각 ${m.as_of} · 지정가 ${num(m.price.close)}원 · 수수료 0.015%` +
    (side === "sell" ? " · 세금 0.20%" : " · 구매는 세금 없음");
  el("s4-remember").textContent = side === "sell"
    ? "판매는 되돌릴 수 없고, 대금 출금은 체결 2영업일 뒤예요."
    : "체결 후에는 취소할 수 없고, 결제 대금은 체결 2영업일 뒤에 움직여요.";

  if (side === "sell") {
    el("s4-qty").innerHTML = `<div class="qty-row">
      <label for="partial-qty">일부 판매 수량</label>
      <input id="partial-qty" type="number" inputmode="numeric" value="${S.partialQty}" aria-label="일부 판매 수량 입력">
      <span>주 (기본 10주)</span></div>
      <p id="partial-error" class="err-text" hidden></p>`;
    el("partial-qty").addEventListener("change", onPartialQtyChange);

    const hold = S.data.hold;
    const p = S.previews.partial || {};
    const f = S.previews.full || {};
    const pv = p.preview, fv = f.preview;
    if (p.error) { el("partial-error").hidden = false; el("partial-error").textContent = p.error; }

    el("s4-table").innerHTML = `<div class="cmp-wrap"><table class="cmp">
      <tr><th>항목</th><th>그대로 유지</th>
          <th>일부 판매(${pv ? num(pv.inputs.qty) : S.partialQty}주)</th>
          <th>전량 판매(${num(holdingQty())}주${fv && fv.is_full_sell ? " — 보유 전량입니다" : ""})</th></tr>
      <tr><td>대금</td><td>—</td><td>${pv ? won(pv.gross_amount) : "—"}</td><td>${fv ? won(fv.gross_amount) : "—"}</td></tr>
      <tr><td>수수료</td><td>—</td><td>${pv ? won(pv.fee) : "—"}</td><td>${fv ? won(fv.fee) : "—"}</td></tr>
      <tr><td>세금</td><td>—</td><td>${pv ? won(pv.tax) : "—"}</td><td>${fv ? won(fv.tax) : "—"}</td></tr>
      <tr><td>예상 수령액</td><td>—</td><td>${pv ? "<b>" + won(pv.net_proceeds) + "</b>" : "—"}</td><td>${fv ? "<b>" + won(fv.net_proceeds) + "</b>" : "—"}</td></tr>
      <tr><td>확정 손익</td><td>0원(평가손익 ${hold ? pnlMoney(hold.eval_pnl) : "—"} 유지)</td>
          <td>${pv ? pnlMoney(pv.realized_pnl) : "—"}</td><td>${fv ? pnlMoney(fv.realized_pnl) : "—"}</td></tr>
      <tr><td>잔여 수량</td><td>${num(holdingQty())}주</td><td>${pv ? num(pv.remaining_qty) + "주" : "—"}</td><td>${fv ? num(fv.remaining_qty) + "주" : "—"}</td></tr>
      <tr><td>남는 비중</td><td>${hold ? hold.weight_pct.toFixed(1) + "%" : "—"}</td>
          <td>${pv ? pv.remaining_weight_pct.toFixed(1) + "%" : "—"}</td><td>${fv ? fv.remaining_weight_pct.toFixed(1) + "%" : "—"}</td></tr>
      <tr><td>출금 가능일</td><td>—</td><td>${pv ? dateLabel(pv.settlement_date) : "—"}</td><td>${fv ? dateLabel(fv.settlement_date) : "—"}</td></tr>
    </table></div>`;
  } else {
    el("s4-qty").innerHTML = "";
    const a = S.previews.b8 || {};
    const b = S.previews.b10 || {};
    const av = a.preview, bv = b.preview;
    const warnBadge = (v) => (v && v.concentration_warning
      ? ` <span class="warn-note" style="display:inline;padding:1px 6px">집중도 경고</span>` : "");
    el("s4-table").innerHTML = `<div class="cmp-wrap"><table class="cmp">
      <tr><th>항목</th><th>8주 구매</th><th>10주 구매</th></tr>
      <tr><td>구매대금</td><td>${av ? won(av.gross_amount) : esc(a.error || "—")}</td><td>${bv ? won(bv.gross_amount) : esc(b.error || "—")}</td></tr>
      <tr><td>수수료</td><td>${av ? won(av.fee) : "—"}</td><td>${bv ? won(bv.fee) : "—"}</td></tr>
      <tr><td>총 결제예정액</td><td>${av ? "<b>" + won(av.total_cost) + "</b>" : "—"}</td><td>${bv ? "<b>" + won(bv.total_cost) + "</b>" : "—"}</td></tr>
      <tr><td>잔여 예수금</td><td>${av ? won(av.remaining_cash) : "—"}</td><td>${bv ? won(bv.remaining_cash) : "—"}</td></tr>
      <tr><td>구매 후 비중</td><td>${av ? av.weight_after_pct.toFixed(1) + "%" + warnBadge(av) : "—"}</td>
          <td>${bv ? bv.weight_after_pct.toFixed(1) + "%" + warnBadge(bv) : "—"}</td></tr>
      <tr><td>결제일</td><td>${av ? dateLabel(av.settlement_date) : "—"}</td><td>${bv ? dateLabel(bv.settlement_date) : "—"}</td></tr>
    </table></div>` +
    ((av && av.concentration_warning) || (bv && bv.concentration_warning)
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

/* ⑤ 검토 의향 4버튼 + 투자 일지 */
function renderStep5() {
  const side = S.data.meta.side;
  const labels = INTENTS[side];
  document.querySelectorAll(".intent-btn").forEach((btn, i) => {
    btn.textContent = labels[i];
    btn.dataset.intent = labels[i];
    btn.classList.toggle("sel", S.intent === labels[i]);
  });
  const hasDraft = Boolean(S.data.diary_draft);
  el("btn-draft").hidden = !hasDraft;
  el("draft-note").hidden = !hasDraft;
}

/* ⑥ 별도 모의 주문 화면 */
function orderPlanFromIntent() {
  if (!S.data) return null;
  const side = S.data.meta.side;
  if (side === "sell") {
    if (S.intent === "일부 판매 검토") return { key: "partial", side };
    if (S.intent === "전량 판매 검토") return { key: "full", side };
  } else {
    if (S.intent === "8주 구매 검토") return { key: "b8", side };
    if (S.intent === "10주 구매 검토") return { key: "b10", side };
  }
  return null;
}
function renderStep6() {
  const m = S.data.meta;
  const plan = orderPlanFromIntent();
  const sideWord = m.side === "sell" ? "판매" : "구매";

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
  if (m.side === "sell") {
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
  const sideSell = m.side === "sell";

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

  el("confirm-qty").value = v.inputs.qty;
  el("sheet-error").hidden = true;
  const btn = el("btn-settle");
  btn.textContent = sideSell ? "모의 판매 체결하기" : "모의 구매 체결하기";
  btn.classList.toggle("side-sell", sideSell);
  btn.classList.toggle("side-buy", !sideSell);
  btn.disabled = false;
  el("sheet-backdrop").hidden = false;
}
async function doSettle() {
  const plan = orderPlanFromIntent();
  if (!plan) return;
  const slot = S.previews[plan.key];
  if (!slot || !slot.preview) return;
  const raw = el("confirm-qty").value;
  if (raw === "") {
    el("sheet-error").hidden = false;
    el("sheet-error").textContent = "확인 수량을 입력해 주세요.";
    return;
  }
  const confirmed = Number(raw);
  const r = await api("/api/settle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: S.scenarioId, preview: slot.preview, confirmed_qty: confirmed }),
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
  </div>
  <button class="btn dark" type="button" onclick="goStep(7)">회고로 이동하기</button>`;
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

/* ⑧ 주문 화면(실앱 재현 — 비기능·계약 §9 재현 화면 규칙): 표시만, 주문 버튼 배선 없음 */
function renderStep8() {
  const m = S.data.meta;
  const name = m.instrument ? m.instrument.name : "";
  const sell = m.side === "sell";
  el("s8-header").innerHTML = `<div class="price-head">
    <div><span class="nm">${esc(name)} <span class="meta-inline">(가상)</span></span>
      <span class="mk">${esc(m.market_label)}</span></div>
    <div><span class="pr">${num(m.price.close)}</span>원 ${pctChange(m.price.change_pct)}</div>
  </div>`;
  el("s8-tab-buy").classList.toggle("on", !sell);
  el("s8-tab-sell").classList.toggle("on", sell);
  el("s8-order-buy").hidden = sell;   // 손실·판매 시나리오에서 구매 CTA 미노출(헌법 §14)
  el("s8-order-sell").hidden = !sell;
  el("s8-price").textContent = won(m.price.close);
  const st = S.settlement;
  el("s8-qty").textContent = st ? num(st.qty) + "주" : "—";
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
    renderSafemode();
  }
  renderChrome();
  window.scrollTo({ top: 0 });
}

/* ── 이벤트 배선 ──────────────────────────────────────── */
function wireEvents() {
  el("btn-start").addEventListener("click", () => goStep(1));
  // 레이어는 투자 행동을 막지 않는다 — 브리핑 스킵은 ⑧ 주문 화면(재현)으로 직행(계약 §9)
  el("btn-skip-briefing").addEventListener("click", () => goStep(8));
  el("btn-prev").addEventListener("click", () => goStep(S.step - 1));
  el("btn-next").addEventListener("click", () => {
    if (S.step >= 8) return goStep(0);
    if (S.step === 7 && !S.settlement) return goStep(0); // 보류 완주 → 처음으로(⑧ 미유도)
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
  el("btn-skip-order").addEventListener("click", () => goStep(7));
  el("btn-save-record").addEventListener("click", saveRecord);
  el("btn-safe-exit").addEventListener("click", () => {
    el("demo-safemode").checked = false; // 버튼 해제는 change 이벤트가 없으므로 수동 동기화
    toggleSafemode(false);
  });
  el("s8-briefing-entry").addEventListener("click", () => goStep(1)); // ⑧ 앞 연결(레이어 진입 재현)

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
    renderChrome();
  });
}

/* ── 시작 ─────────────────────────────────────────────── */
window.goStep = goStep; // 결과 카드 내 버튼에서 사용
document.addEventListener("DOMContentLoaded", () => {
  wireEvents();
  loadScenarioList();
});
