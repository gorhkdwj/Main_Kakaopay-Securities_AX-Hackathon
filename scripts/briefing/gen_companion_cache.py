r"""동반자 문답 캐시 생성기 — 목업 4문답을 동결 스냅샷·엔진 산출값으로 재산출한다.

사용(프로젝트 루트에서):
    .\.venv\Scripts\python.exe scripts\briefing\gen_companion_cache.py

원본 대화 설계: docs/mockup/2026-07-18_동반자챗봇_목업.html (4문답 —
타이밍 불안 / 하락 사실 재프레임 / 분할 비교 / 결정 핸드오프).
목업의 서사(1,000만 원·13주×3회)는 프레임만 차용하고, 숫자는 전부 현재 동결
데이터로 재산출한다: 예산 = fixture cash(3,000,000원), 분할 비교 = 엔진
buy_preview 재사용(1회분 × 횟수 — 신규 산식 도입 금지), 백테스트류 문장 =
스냅샷 closes 결정론 계산(과거 사실 서술 + "미래에도 그렇다는 뜻 아님" 병기).

LLM 미사용(결정론 스크립트) — 계약 §6 companion의 "[데모 고정] 수기 검수
캐시, 단 숫자는 엔진·스냅샷 산출값" 규정 구현. 저장 전 각 문답에
guard(check_response — 숫자 대사·출처 실재) + reply_text 검사(§7 사전·숫자
대조)를 실행해 차단 0건인 경우에만 저장한다(gen_llm_cache.py 패턴).

출력: data/fixtures/companion_cache/real_005930.json
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windows 콘솔(cp949)에서 대시·한글 출력이 깨지지 않게 UTF-8로 재구성
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.briefing.companion import (  # noqa: E402
    DEFAULT_COMPANION_CACHE_DIR,
    MARKET_CONTEXT_SOURCE_ID,
    load_market_context,
    market_asof_label,
    sanitize_companion_response,
    stock_asof_label,
)
from src.briefing.llm import fixture_fingerprint  # noqa: E402
from src.engine import EngineInputError, buy_preview  # noqa: E402
from src.engine.calculator import CONCENTRATION_WARNING_PCT  # noqa: E402
from src.policy.guard import check_response, collect_allowed_numbers  # noqa: E402
from src.webapp.app import PRICE_FACT_SOURCE, known_source_ids_for  # noqa: E402

SCENARIO_ID = "real_005930"
FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"

#: 분할 비교 횟수(목업 3회 프레임 유지 — 1회분 × 횟수)
TRANCHES = 3


def won(v: int) -> str:
    return f"{v:,}원"


def pct1(v: float) -> str:
    return f"{v:+.1f}%"


def pct2(v: float) -> str:
    return f"{v:+.2f}%"


def load_fixture() -> dict:
    path = FIXTURES_DIR / f"scenario_{SCENARIO_ID}.json"
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def max_buy_qty(fx: dict) -> int:
    """예수금(cash) 안에서 가능한 최대 매수 수량 — 엔진 검증을 그대로 사용."""
    holding = fx.get("holding") or {}
    qty = 0
    while qty < 10_000:  # 데모 안전 상한
        try:
            buy_preview(
                qty + 1, fx["price"]["close"], fx["cash"], fx["trade_date"],
                holding_qty=holding.get("qty") or 0,
                avg_price=holding.get("avg_price"),
                portfolio_total_value=fx.get("portfolio_total_value"),
            )
        except EngineInputError:
            return qty
        qty += 1
    return qty


def preview_for(fx: dict, qty: int) -> dict:
    holding = fx.get("holding") or {}
    return buy_preview(
        qty, fx["price"]["close"], fx["cash"], fx["trade_date"],
        holding_qty=holding.get("qty") or 0,
        avg_price=holding.get("avg_price"),
        portfolio_total_value=fx.get("portfolio_total_value"),
    )


def build_entries(fx: dict, market_ctx: dict) -> list:
    """목업 4문답을 현재 데이터로 재산출한 캐시 entry 목록을 만든다."""
    price = fx["price"]
    close, prev_close = price["close"], price["prev_close"]
    change_pct = price["change_pct"]
    change_amount = close - prev_close  # 서버 파생 규칙(계약 §3.1)과 동일 결정론 파생
    stock_label = stock_asof_label(fx)
    market_label = market_asof_label(market_ctx)
    items = market_ctx["items"]
    disclosures = fx["disclosures"]  # [0]=52주 고저, [1]=거래량, [2]=섹터, [3]=IR 일정
    situation = fx["scenario_id"]

    # ── 엔진 산출(분할 비교 — 1회분 × 횟수, 신규 산식 없음) ────────────────
    q_max = max_buy_qty(fx)
    base_qty = q_max - (q_max % TRANCHES)
    if base_qty < TRANCHES:
        raise RuntimeError(f"분할 비교 불가 — 최대 매수 수량 {q_max}주로는 {TRANCHES}회 분할 수량이 없습니다")
    tranche_qty = base_qty // TRANCHES
    lump = preview_for(fx, base_qty)          # 한 번에 base_qty주
    tranche = preview_for(fx, tranche_qty)    # 1회분 tranche_qty주
    tranche_fee_total = tranche["fee"] * TRANCHES          # 1회분 × 횟수
    tranche_cost_total = tranche["total_cost"] * TRANCHES  # 1회분 × 횟수

    # ── 스냅샷 closes 결정론 계산(백테스트류 — 과거 사실로만 서술) ─────────
    closes = price["history"]["closes"]
    closes3 = closes[-3:]
    avg3 = sum(closes3) // len(closes3)

    # ── 시장 지표 사실 문구(스냅샷 원천값 그대로 — 반올림 재가공 없음) ─────
    market_fact_text = (
        f"코스피는 전일 대비 {pct2(items['kospi']['change_pct'])}, "
        f"코스닥은 {pct2(items['kosdaq']['change_pct'])}였어요."
    )

    common_user_inputs = {"quantity": None, "intent": None, "situation": situation}

    # ══ Q1 · 타이밍 불안 ══════════════════════════════════════════════════
    q1 = {
        "qa_id": "timing",
        "chip": "지금 사도 괜찮을까?",
        "question": "지금 사도 괜찮을까요? 오늘 많이 떨어진 것 같아서 무서워요",
        "match_questions": [
            "지금 사도 괜찮을까?",
            "지금 사도 괜찮을까요?",
            "지금 사도 괜찮을까요? 오늘 많이 떨어진 것 같아서 무서워요…",
        ],
        "keywords": ["지금", "사도", "괜찮", "무서", "타이밍"],
        "calculations": [],
        "derived": {
            "change_amount": change_amount,
            "note": "change_amount = close - prev_close (계약 §3.1 서버 파생 규칙과 동일)",
        },
        "allowed_extra_numbers": [abs(change_amount)],
        "response": {
            "reply_text": (
                "무서운 마음이 드실 수 있어요. 사라·팔라를 대신 정해 드릴 수는 없지만, "
                "결정에 쓸 사실과 양면 해석을 정리했어요 — 아래 카드를 함께 봐 주세요."
            ),
            "facts": [
                {
                    "text": (
                        f"종가 {won(close)} — 전일 종가 {won(prev_close)} 대비 "
                        f"{change_amount:+,}원({pct1(change_pct)})이에요."
                    ),
                    "source_id": PRICE_FACT_SOURCE[SCENARIO_ID],
                    "as_of": stock_label,
                },
                {
                    "text": disclosures[1]["text"],
                    "source_id": disclosures[1]["source_id"],
                    "as_of": disclosures[1]["published_at"],
                },
                {
                    "text": disclosures[0]["text"],
                    "source_id": disclosures[0]["source_id"],
                    "as_of": disclosures[0]["published_at"],
                },
                {
                    "text": market_fact_text,
                    "source_id": MARKET_CONTEXT_SOURCE_ID,
                    "as_of": market_label,
                },
            ],
            "interpretations": [
                {
                    "text": fx["interpretations"][0]["text"],
                    "basis": [disclosures[0]["source_id"]],
                    "stance": "긍정 시각",
                },
                {
                    "text": fx["interpretations"][1]["text"],
                    "basis": [disclosures[0]["source_id"]],
                    "stance": "부정 시각",
                },
                {
                    "text": (
                        "비슷한 시기에 지수도 함께 내려, 이 종목만의 일이 아니라 "
                        "시장 전체 흐름과 겹쳐 있을 수 있다고 보는 시각이 있어요."
                    ),
                    "basis": [MARKET_CONTEXT_SOURCE_ID],
                    "stance": "긍정 시각",
                },
                {
                    "text": (
                        f"이 종목의 하루 낙폭({pct1(change_pct)})이 상당히 커서, 시장 흐름과 "
                        "별개로 종목 고유의 부담이 있을 수 있다고 보는 시각도 있어요."
                    ),
                    "basis": [PRICE_FACT_SOURCE[SCENARIO_ID]],
                    "stance": "부정 시각",
                },
            ],
            "unknowns": [
                "다음 거래일의 가격 방향은 알 수 없어요 — 저는 예측하지 않아요.",
                "종목 종가와 시장 지표는 기준 시점이 달라요 — 같은 날의 비교로 읽지 않는 게 안전해요.",
            ],
            "user_inputs": dict(common_user_inputs),
            "calculation_id": None,
            "policy_result": "information_only",
            "next_questions": [
                "'종목·계획' 화면에서 이 종목을 담으셨을 때의 계획(목표 기간·감수 손실)을 다시 확인해 보시겠어요?",
                "오늘 상황이 적어 두신 재검토 조건(실적 2개 분기 연속 악화)에 해당하는지 '체크리스트' 화면에서 점검해 보시겠어요?",
            ],
        },
    }

    # ══ Q2 · 하락 사실 재프레임(왜를 확정할 수 없어요) ════════════════════
    q2 = {
        "qa_id": "why_drop",
        "chip": "왜 이렇게 떨어진 거예요?",
        "question": "왜 이렇게 떨어진 거예요?",
        "match_questions": [
            "왜 이렇게 떨어진 거예요?",
            "왜 이렇게 떨어졌어요?",
            "왜 떨어졌어요?",
            "오늘 시장 어땠어?",
            "오늘 시장 어땠어요?",
        ],
        "keywords": ["왜", "떨어", "하락", "시장", "이유"],
        "calculations": [],
        "derived": {},
        "allowed_extra_numbers": [],
        "response": {
            "reply_text": (
                "'왜'를 한 가지로 확정해 말씀드릴 수는 없어요. 대신 비슷한 시기에 "
                "함께 있었던 시장 사실을 보여드릴게요."
            ),
            "facts": [
                {
                    "text": market_fact_text,
                    "source_id": MARKET_CONTEXT_SOURCE_ID,
                    "as_of": market_label,
                },
                {
                    "text": (
                        f"원/달러 환율은 {items['usdkrw']['value']:,.2f}원"
                        f"(전일 대비 {pct2(items['usdkrw']['change_pct'])})이에요."
                    ),
                    "source_id": MARKET_CONTEXT_SOURCE_ID,
                    "as_of": market_label,
                },
                {
                    "text": (
                        f"변동성 지표 VIX는 {items['vix']['value']:,.2f}로 전일 대비 "
                        f"{pct2(items['vix']['change_pct'])}예요(미국 지표 참고)."
                    ),
                    "source_id": MARKET_CONTEXT_SOURCE_ID,
                    "as_of": market_label,
                },
                {
                    "text": (
                        f"미국 증시 대표 지수는 전일 대비 {pct2(items['sp500']['change_pct'])}"
                        "였어요(미국 지표 참고)."
                    ),
                    "source_id": MARKET_CONTEXT_SOURCE_ID,
                    "as_of": market_label,
                },
            ],
            "interpretations": [
                {
                    "text": (
                        "지수·환율·변동성 지표가 함께 움직인 시기라, 이 종목만의 사정보다 "
                        "시장 전체 흐름의 영향이 컸을 수 있다고 보는 시각이 있어요."
                    ),
                    "basis": [MARKET_CONTEXT_SOURCE_ID],
                    "stance": "긍정 시각",
                },
                {
                    "text": (
                        "시장 흐름이 진정되더라도 종목 고유의 부담이 남아 있을 수 있다고 "
                        "보는 시각도 있어요 — 회사가 공시한 다음 실적 발표 예정일에 확인할 부분이에요."
                    ),
                    "basis": [disclosures[3]["source_id"]],
                    "stance": "부정 시각",
                },
            ],
            "unknowns": [
                "이 사실들이 이번 하락을 얼마나 설명하는지는 확정할 수 없어요 — 하락과의 인과는 이 자료로 증명할 수 없어요.",
                "관련 뉴스·수급 주체 정보는 이 데모의 동결 데이터에 없어서 여기서는 확인할 수 없어요.",
            ],
            "user_inputs": dict(common_user_inputs),
            "calculation_id": None,
            "policy_result": "information_only",
            "next_questions": [
                "'종목·계획' 화면에서 지난 투자 일지에 적어 두셨던 구매 이유를 다시 읽어 보시겠어요?",
                "오늘 상황이 재검토 조건(실적 2개 분기 연속 악화)에 해당하는지 '체크리스트' 화면에서 대조해 보시겠어요?",
            ],
        },
    }

    # ══ Q3 · 분할 비교(엔진 buy_preview 재사용 — 1회분 × 횟수) ═══════════
    q3_reply = (
        f"정답을 정해 드릴 수는 없지만, 예수금 {won(fx['cash'])} 기준으로 결정론 엔진이 "
        f"계산한 비교예요. 한 번에는 최대 {q_max}주까지 가능하고, {TRANCHES}회로 똑같이 "
        f"나눌 수 있는 {base_qty}주로 비교하면 — 한 번에 {base_qty}주: 구매대금 "
        f"{won(lump['gross_amount'])} · 수수료 {won(lump['fee'])} · 총 결제예정액 "
        f"{won(lump['total_cost'])} · 남는 예수금 {won(lump['remaining_cash'])}. "
        f"{tranche_qty}주씩 {TRANCHES}회: 회당 구매대금 {won(tranche['gross_amount'])} · "
        f"회당 수수료 {won(tranche['fee'])} · 회당 총 결제예정액 {won(tranche['total_cost'])}"
        f"({TRANCHES}회 합계 {won(tranche_cost_total)}, 수수료 합계 {won(tranche_fee_total)} — "
        f"절사 때문에 한 번에보다 조금 다를 수 있어요). 결제는 각 체결일 +2영업일이에요. "
        f"참고로 {base_qty}주를 다 담으면 이 종목 비중이 총자산의 "
        f"{lump['weight_after_pct']}%가 되어 집중도 경고 기준({CONCENTRATION_WARNING_PCT:.0f}%)을 넘어요."
    )
    q3 = {
        "qa_id": "split_compare",
        "chip": "나눠 살까, 한 번에 살까?",
        "question": "한 번에 다 살까요, 나눠서 살까요?",
        "match_questions": [
            "한 번에 다 살까요, 나눠서 살까요?",
            "나눠 살까, 한 번에 살까?",
            "나눠서 살까요, 한 번에 살까요?",
            "분할 매수와 일괄 매수 비교해 주세요",
        ],
        "keywords": ["나눠", "나누", "분할", "한 번에", "한번에", "일괄"],
        "calculations": [lump, tranche],
        "derived": {
            "tranches": TRANCHES,
            "base_qty": base_qty,
            "tranche_qty": tranche_qty,
            "max_qty": q_max,
            "tranche_fee_total": tranche_fee_total,
            "tranche_cost_total": tranche_cost_total,
            "closes_last3": closes3,
            "avg_close_3d": avg3,
            "concentration_threshold_pct": CONCENTRATION_WARNING_PCT,
            "note": (
                "합계 = 1회분 엔진 결과 × 횟수(신규 산식 없음) · avg_close_3d = "
                "스냅샷 closes 마지막 3개 정수 평균(절사) — 과거 사실 서술 전용"
            ),
        },
        "allowed_extra_numbers": [
            TRANCHES, base_qty, tranche_qty, q_max,
            tranche_fee_total, tranche_cost_total, avg3,
            int(CONCENTRATION_WARNING_PCT),
        ],
        "response": {
            "reply_text": q3_reply,
            "facts": [
                {
                    "text": (
                        f"최근 3거래일 종가는 {won(closes3[0])} → {won(closes3[1])} → "
                        f"{won(closes3[2])} 순이었고, 세 값의 평균은 약 {won(avg3)}이에요"
                        f"(결정론 계산). 사흘에 나눠 샀다면 평균 근처에, 마지막 날 하루에 "
                        f"샀다면 {won(closes3[2])}에 산 셈이라 — 이 사흘만 보면 결과적으로 "
                        "하루 쪽이 쌌어요."
                    ),
                    "source_id": PRICE_FACT_SOURCE[SCENARIO_ID],
                    "as_of": stock_label,
                },
            ],
            "interpretations": [
                {
                    "text": (
                        "나눠 사면 '언제'의 부담을 여러 번으로 나눠 평균을 사게 돼요 — "
                        "타이밍이 두려울 때 마음의 부담을 줄이는 성격의 선택지라고 보는 시각이 있어요."
                    ),
                    "basis": [PRICE_FACT_SOURCE[SCENARIO_ID]],
                    "stance": "긍정 시각",
                },
                {
                    "text": (
                        "나눠 사는 동안 가격이 움직이면 평균 체결가가 지금보다 높아질 수도 있어요 — "
                        "한 번에 사면 가격이 지금 숫자로 확정되는 대신 이후 흔들림을 온전히 "
                        "감수하는 성격이라고 보는 시각이 있어요."
                    ),
                    "basis": [PRICE_FACT_SOURCE[SCENARIO_ID]],
                    "stance": "부정 시각",
                },
            ],
            "unknowns": [
                "어느 쪽이 더 좋은 결과가 될지는 지나 봐야 알아요 — 위 사흘 비교는 과거 사실일 뿐, 미래에도 그렇다는 뜻이 아니에요.",
            ],
            "user_inputs": dict(common_user_inputs),
            "calculation_id": lump["calculation_id"],
            "policy_result": "information_only",
            "next_questions": [
                "'시나리오 비교' 화면에서 수량을 바꿔 가며 예상 결제액과 비중 변화를 직접 비교해 보시겠어요?",
                "'모의 주문' 화면에서 실제 거래 없이 주문 흐름을 연습해 보시겠어요?",
            ],
        },
    }

    # ══ Q4 · 결정 핸드오프(사용자 결정 기록 + 4종 고지 + 모의 주문·일지) ══
    q4_reply = (
        f"「예수금 {won(fx['cash'])} 중 {tranche_qty}주(구매대금 {won(tranche['gross_amount'])})를 "
        "먼저, 나머지는 나중에」 — 제 의견이 아니라 직접 내리신 결정이에요. 주문 전 확인 "
        f"4가지예요: ① 수수료 {won(tranche['fee'])}(구매는 세금이 없어요) ② 총 결제예정액 "
        f"{won(tranche['total_cost'])} ③ 결제(출금)는 체결일 +2영업일인 "
        f"{tranche['settlement_date']}이에요 ④ 체결 후에는 취소할 수 없어요. 실제 주문 실행은 "
        "이 대화 밖 주문 화면에서 해요 — 저는 실행 버튼을 갖지 않아요. '모의 주문' 화면에서 "
        "먼저 연습하거나 '투자 일지'에 이유를 남길 수 있어요."
    )
    q4 = {
        "qa_id": "handoff",
        "chip": f"오늘은 {tranche_qty}주만 먼저 해볼게요",
        "question": f"그럼 오늘은 {tranche_qty}주만 먼저 해볼게요.",
        "match_questions": [
            f"그럼 오늘은 {tranche_qty}주만 먼저 해볼게요.",
            f"오늘은 {tranche_qty}주만 먼저 해볼게요",
            f"{tranche_qty}주만 먼저 살게요",
        ],
        "keywords": [f"{tranche_qty}주", "먼저", "해볼게", "할게요", "결정"],
        "calculations": [tranche],
        "derived": {"tranche_qty": tranche_qty},
        "allowed_extra_numbers": [tranche_qty],
        "response": {
            "reply_text": q4_reply,
            "facts": [
                {
                    "text": disclosures[3]["text"],
                    "source_id": disclosures[3]["source_id"],
                    "as_of": disclosures[3]["published_at"],
                },
            ],
            "interpretations": [
                {
                    "text": (
                        "일부만 먼저 사는 결정은 남은 예수금으로 다음 판단의 여지를 "
                        "남기는 성격이 있다고 보는 시각이 있어요."
                    ),
                    "basis": [PRICE_FACT_SOURCE[SCENARIO_ID]],
                    "stance": "긍정 시각",
                },
                {
                    "text": (
                        "나눠 사는 사이 가격이 움직이면 남은 몫의 구매 단가가 달라질 수 "
                        "있다는 점은 감수해야 한다고 보는 시각이 있어요."
                    ),
                    "basis": [PRICE_FACT_SOURCE[SCENARIO_ID]],
                    "stance": "부정 시각",
                },
            ],
            "unknowns": [
                "다음 구매 시점의 가격은 알 수 없어요 — 정해 두신 계획과 재검토 조건이 판단의 기준이 돼요.",
            ],
            "user_inputs": {
                "quantity": tranche_qty,
                "intent": f"{tranche_qty}주 구매 검토",
                "situation": situation,
            },
            "calculation_id": tranche["calculation_id"],
            "policy_result": "information_only",
            "next_questions": [
                f"'모의 주문' 화면에서 이번 결정({tranche_qty}주)을 실제 거래 없이 연습해 보시겠어요?",
                "'투자 일지'에 오늘 판단의 이유와 다음 재검토 메모를 남겨 보시겠어요?",
            ],
        },
    }

    return [q1, q2, q3, q4]


def main() -> int:
    fx = load_fixture()
    market_ctx = load_market_context()
    if market_ctx is None:
        print("market_context 스냅샷을 읽지 못했습니다 — 캐시를 생성하지 않습니다"
              "(data/snapshots/market_context_*.json 확인).")
        return 1

    entries = build_entries(fx, market_ctx)

    # ── 저장 전 검증: guard + reply_text 검사(서빙 경로와 동일 규칙) ───────
    known = known_source_ids_for(fx, SCENARIO_ID)
    known.add(MARKET_CONTEXT_SOURCE_ID)
    failures = 0
    for entry in entries:
        allowed = collect_allowed_numbers(
            fx, market_ctx, entry["calculations"], entry["allowed_extra_numbers"])
        sanitized, record, reply_blocked = sanitize_companion_response(
            copy_entry_response(entry), allowed_numbers=allowed,
            known_source_ids=known)
        if record["blocked"] or reply_blocked:
            failures += 1
            print(f"[{entry['qa_id']}] guard 차단 {len(record['blocked'])}건 — 저장 불가:")
            for b in record["blocked"]:
                print(f"    - {b['rule_id']} {b['field']}: {b['excerpt']}")
            continue
        # 수량이 있는 문답(Q4)은 엔진 계산과의 수량 일치도 확인한다(계약 §6)
        qty = entry["response"]["user_inputs"].get("quantity")
        if qty is not None:
            body = {k: v for k, v in entry["response"].items() if k != "reply_text"}
            _s, qrec = check_response(
                body, entry["calculations"][0],
                allowed_numbers=allowed, known_source_ids=known)
            if qrec["blocked"]:
                failures += 1
                print(f"[{entry['qa_id']}] 수량 대조 차단 — 저장 불가: {qrec['blocked']}")
                continue
        counts = (f"facts {len(sanitized['facts'])} · interp {len(sanitized['interpretations'])}"
                  f" · unknowns {len(sanitized['unknowns'])}")
        warn = f" · 경고 {len(record['warnings'])}건" if record["warnings"] else ""
        print(f"[{entry['qa_id']}] 검증 통과 — {counts}{warn}")

    if failures:
        print(f"차단 {failures}건 — 캐시를 저장하지 않습니다(문구 수정 후 재실행).")
        return 1

    out = {
        "scenario_id": SCENARIO_ID,
        "generated_by": "deterministic_script_v1(목업 4문답 재산출 — LLM 미사용)",
        "generated_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M} KST",
        "fixture_sha256": fixture_fingerprint(fx),
        "market_context_ref": market_ctx["snapshot_file"],
        "note": ("[데모 고정] 사전 준비 문답 — 숫자는 전부 스냅샷 원천값·엔진 산출값"
                 "(계약 §6 companion). 실서비스 전 재검토 대상."),
        "qa": entries,
    }
    DEFAULT_COMPANION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_COMPANION_CACHE_DIR / f"{SCENARIO_ID}.json"
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    print(f"저장 완료: {path.relative_to(PROJECT_ROOT)} (문답 {len(entries)}건)")
    return 0


def copy_entry_response(entry: dict) -> dict:
    """검증용 깊은 사본(원본 entry 무수정 — sanitize가 사본을 다루게 한다)."""
    return json.loads(json.dumps(entry["response"], ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
