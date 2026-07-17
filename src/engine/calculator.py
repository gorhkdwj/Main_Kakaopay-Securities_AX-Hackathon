"""결정론 계산 엔진 — 매도/매수 미리보기·보유 평가 요약.

기준 계약: docs/requirements-contract.md
  - §2  calculation_id 형식(``CALC-YYYYMMDD-HHMMSS-<seq>``)
  - §4  지표 정의(정의가 곧 코드 명세)
  - §5  수식·골든값(§5.2 loss8 / §5.2-b profit15 / §5.2-c first_buy)·임계값(§5.3)
  - §11 시간대·단위·반올림 총칙

불변 원칙(구현 계획 §0): 숫자는 이 엔진만 만든다(LLM 산수 금지).
같은 입력이면 언제나 같은 출력이다(calculation_id 제외 — 발급 시각·순번 포함).
표준 라이브러리만 사용하며 LLM·네트워크 호출이 없다.

수식([데모 고정] — 계약 §5.1, 금액은 전부 정수 연산으로 절사):
  - 수수료          = 대금 × 15 // 100000   (0.015%, 원 미만 절사)
  - 거래세·농특세    = 매도대금 × 20 // 10000 (0.20%, 원 미만 절사 — 매수는 없음)
  - 예상수령액      = 매도대금 − 수수료 − 거래세·농특세
  - 실현손익        = 예상수령액 − (평균 매수가 × 매도수량)  ※ 비용 차감 후(계약 §4)
  - 비중(%)         = round(값, 1) — 소수 1자리 반올림(계약 §11)
    · 매도 잔여비중 분모 = portfolio_total_value(매도 전 스냅샷 고정 — 재편입 없음)
    · 매수 후 비중 분모  = cash(매수 전 예수금 총액 고정)

반환 dict 필드 ↔ 계약 §4 한국어 지표 대응:
  gross_amount=매도대금/매수대금, fee=수수료, tax=거래세·농특세,
  net_proceeds=예상수령액, realized_pnl=실현손익, remaining_qty=잔여 수량,
  remaining_weight_pct=잔여 비중(%), total_cost=총 결제예정액,
  remaining_cash=잔여 예수금, weight_after_pct=매수 후 비중(%),
  concentration_warning=집중도 경고(>40%, 차단 아닌 정보 — 계약 §5.3),
  settlement_date=결제일(D+2), eval_pnl=평가손익, eval_pnl_pct=평가손익률(%),
  weight_pct=현재 비중(%), is_full_sell=전량 매도 여부("보유 전량입니다" 라벨).
"""

from __future__ import annotations

import datetime
import itertools
import re

from .biz_days import settle_date

__all__ = [
    "EngineInputError",
    "QuantityError",
    "InsufficientCashError",
    "InvalidPreviewError",
    "CALC_ID_PATTERN",
    "sell_preview",
    "buy_preview",
    "hold_summary",
]

# ---------------------------------------------------------------------------
# 상수 (계약 §5.1·§5.3 — 값 변경은 계약 문서 갱신이 선행돼야 한다)
# ---------------------------------------------------------------------------

#: 수수료율(0.015%)의 정수 연산 분자/분모 — 대금 × 15 // 100000
FEE_NUM, FEE_DEN = 15, 100_000

#: 거래세·농특세율(0.20%)의 정수 연산 분자/분모 — 매도대금 × 20 // 10000
TAX_NUM, TAX_DEN = 20, 10_000

#: 집중도 경고 임계(매수 후 비중 % 초과 시 — 차단 아님) [데모 고정]
CONCENTRATION_WARNING_PCT = 40.0

#: calculation_id 형식(계약 §2) 검증용 정규식
CALC_ID_PATTERN = re.compile(r"^CALC-\d{8}-\d{6}-\d+$")


# ---------------------------------------------------------------------------
# 예외 (계약 §5.3 — 오류 시 계산 결과·calculation_id를 생성하지 않는다)
# ---------------------------------------------------------------------------

class EngineInputError(ValueError):
    """계산 엔진 입력 오류의 공통 기반 예외(ValueError 파생)."""


class QuantityError(EngineInputError):
    """수량 오류 — 0·음수·비정수 또는 매도 시 보유수량 범위(1~보유수량) 밖."""


class InsufficientCashError(EngineInputError):
    """매수 오류 — 총 결제예정액(매수대금+수수료)이 가용 예수금을 초과."""


class InvalidPreviewError(EngineInputError):
    """모의 체결 오류 — preview 결과가 엔진 산출물과 정합하지 않음(settle.py 사용)."""


# ---------------------------------------------------------------------------
# calculation_id 발급기 (계약 §2 — seq는 프로세스 내 증가 카운터)
# ---------------------------------------------------------------------------

_seq_counter = itertools.count(1)


def _next_calculation_id() -> str:
    """``CALC-YYYYMMDD-HHMMSS-<seq>`` 형식의 ID를 발급한다.

    시각은 로컬 시각(데모는 KST 로컬 실행 전제 — 계약 §11).
    검증을 모두 통과한 뒤에만 호출된다 — 오류 입력은 seq를 소모하지 않는다.
    """
    now = datetime.datetime.now()
    return f"CALC-{now:%Y%m%d}-{now:%H%M%S}-{next(_seq_counter)}"


# ---------------------------------------------------------------------------
# 입력 검증 헬퍼
# ---------------------------------------------------------------------------

def _validate_qty(qty: object) -> int:
    """수량이 양의 정수인지 검증한다(계약 §5.3 — 소수점 거래 미지원).

    bool은 int의 서브클래스이므로 명시적으로 거부한다.
    """
    if isinstance(qty, bool) or not isinstance(qty, int):
        raise QuantityError(
            f"수량은 1 이상의 정수만 입력할 수 있습니다(소수점 거래 미지원): {qty!r}"
        )
    if qty < 1:
        raise QuantityError(f"수량은 1 이상이어야 합니다: {qty!r}")
    return qty


def _validate_int(value: object, name: str, *, minimum: int = 1) -> int:
    """금액·수량 파라미터가 정수(원 단위, 계약 §11)인지 검증한다."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise EngineInputError(f"{name}은(는) 정수(원 단위)여야 합니다: {value!r}")
    if value < minimum:
        raise EngineInputError(f"{name}은(는) {minimum} 이상이어야 합니다: {value!r}")
    return value


def _validate_trade_date(trade_date: object) -> str:
    """trade_date를 ISO 문자열로 정규화한다(형식 오류는 EngineInputError)."""
    try:
        if isinstance(trade_date, datetime.datetime):
            return trade_date.date().isoformat()
        if isinstance(trade_date, datetime.date):
            return trade_date.isoformat()
        if isinstance(trade_date, str):
            return datetime.date.fromisoformat(trade_date).isoformat()
    except ValueError as exc:
        raise EngineInputError(
            f"trade_date 형식이 잘못됐습니다('YYYY-MM-DD' 필요): {trade_date!r}"
        ) from exc
    raise EngineInputError(
        f"trade_date는 'YYYY-MM-DD' 문자열 또는 date여야 합니다: {trade_date!r}"
    )


def _pct(numerator: int, denominator: int) -> float:
    """비중·손익률(%)을 소수 1자리 반올림으로 반환한다(계약 §11)."""
    return round(numerator / denominator * 100, 1)


# ---------------------------------------------------------------------------
# 순수 계산부 — calculation_id 없이 결정론 결과만 산출
# (settle.py가 preview 재검증에 재사용한다)
# ---------------------------------------------------------------------------

def _compute_sell(
    qty: int,
    price: int,
    avg_price: int,
    holding_qty: int,
    portfolio_total_value: int,
    trade_date: "str | datetime.date",
) -> dict:
    """매도 미리보기 순수 계산(검증 포함, ID 미발급). 골든값: 계약 §5.2·§5.2-b."""
    _validate_qty(qty)
    _validate_int(holding_qty, "holding_qty(보유수량)")
    if qty > holding_qty:
        raise QuantityError(
            f"매도 수량은 1~보유수량({holding_qty}주) 범위여야 합니다: {qty!r}"
        )
    _validate_int(price, "price(기준가)")
    _validate_int(avg_price, "avg_price(평균 매수가)")
    _validate_int(portfolio_total_value, "portfolio_total_value(총 평가자산)")
    trade_date_iso = _validate_trade_date(trade_date)

    gross = price * qty                     # 매도대금 = 기준가 × 매도수량
    fee = gross * FEE_NUM // FEE_DEN        # 수수료 0.015% — 원 미만 절사
    tax = gross * TAX_NUM // TAX_DEN        # 거래세·농특세 0.20% — 원 미만 절사
    net = gross - fee - tax                 # 예상수령액
    realized_pnl = net - avg_price * qty    # 실현손익(비용 차감 후 — 계약 §4)
    remaining_qty = holding_qty - qty
    # 잔여 비중 분모 = 매도 전 스냅샷 총평가 고정(계약 §4 — 재편입 없음)
    remaining_weight_pct = _pct(remaining_qty * price, portfolio_total_value)

    return {
        "type": "sell_preview",
        "inputs": {
            "qty": qty,
            "price": price,
            "avg_price": avg_price,
            "holding_qty": holding_qty,
            "portfolio_total_value": portfolio_total_value,
            "trade_date": trade_date_iso,
        },
        "gross_amount": gross,
        "fee": fee,
        "tax": tax,
        "net_proceeds": net,
        "realized_pnl": realized_pnl,
        "remaining_qty": remaining_qty,
        "remaining_weight_pct": remaining_weight_pct,
        "is_full_sell": qty == holding_qty,  # "보유 전량입니다" 라벨(계약 §5.3)
        # 체결 후 평균 구매가 — 매도는 평균 구매가를 바꾸지 않는다(계약 §5.1).
        # 잔여 보유가 있으면 기존 값 유지, 전량 매도면 잔여 없음(None).
        "avg_price_after": None if qty == holding_qty else avg_price,
        "settlement_date": settle_date(trade_date_iso, 2),  # D+2(토·일 제외)
    }


def _compute_buy(
    qty: int,
    price: int,
    cash: int,
    trade_date: "str | datetime.date",
    holding_qty: int = 0,
    avg_price: "int | None" = None,
) -> dict:
    """매수 미리보기 순수 계산(검증 포함, ID 미발급). 골든값: 계약 §5.2-c.

    holding_qty·avg_price는 '체결 후 평균 구매가(예상)' 계산용(계약 §5.1 —
    사용자 요청 2026-07-18). 보유 0이면 평균 구매가 = 기준가.
    """
    _validate_qty(qty)
    _validate_int(price, "price(기준가)")
    _validate_int(cash, "cash(가용 예수금)", minimum=0)
    _validate_int(holding_qty, "holding_qty(보유수량)", minimum=0)
    if holding_qty > 0:
        _validate_int(avg_price, "avg_price(평균 구매가)")
    trade_date_iso = _validate_trade_date(trade_date)

    gross = price * qty                     # 매수대금
    fee = gross * FEE_NUM // FEE_DEN        # 수수료 0.015% — 원 미만 절사
    total_cost = gross + fee                # 총 결제예정액(매수는 거래세·농특세 없음)
    if total_cost > cash:
        raise InsufficientCashError(
            f"총 결제예정액 {total_cost:,}원이 가용 예수금 {cash:,}원을 초과합니다"
            " — 주문을 만들 수 없습니다"
        )
    remaining_cash = cash - total_cost      # 잔여 예수금
    # 매수 후 비중 분모 = 매수 전 예수금 총액 고정(계약 §4) / 분자 = 매수 후 평가액
    weight_after_pct = _pct(gross, cash)
    # 체결 후 평균 구매가(예상) — 순수 매입가 기준(수수료 미포함)·원 미만 절사(계약 §5.1)
    avg_price_after = (holding_qty * (avg_price or 0) + gross) // (holding_qty + qty)

    return {
        "type": "buy_preview",
        "inputs": {
            "qty": qty,
            "price": price,
            "cash": cash,
            "trade_date": trade_date_iso,
            "holding_qty": holding_qty,
            "avg_price": avg_price,
        },
        "gross_amount": gross,
        "fee": fee,
        "tax": 0,  # 매수에는 거래세·농특세 없음(계약 §5.1 — 화면 표기용 명시적 0)
        "total_cost": total_cost,
        "remaining_cash": remaining_cash,
        "weight_after_pct": weight_after_pct,
        # 집중도 경고: >40% 초과 시 True — 차단이 아니라 정보 표시(계약 §5.3)
        "concentration_warning": weight_after_pct > CONCENTRATION_WARNING_PCT,
        "avg_price_after": avg_price_after,  # 체결 후 평균 구매가(예상 — 계약 §5.1)
        "settlement_date": settle_date(trade_date_iso, 2),  # D+2(토·일 제외)
    }


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def sell_preview(
    qty: int,
    price: int,
    avg_price: int,
    holding_qty: int,
    portfolio_total_value: int,
    trade_date: "str | datetime.date",
) -> dict:
    """매도 주문 미리보기를 계산한다(계약 §5 — 골든값 §5.2·§5.2-b).

    예(loss8 10주): 매도대금 460,000 / 수수료 69 / 거래세·농특세 920 /
    예상수령액 459,011 / 실현손익 −40,989 / 잔여 20주·비중 18.8% / 결제일 2026-07-21.

    Args:
        qty: 매도수량(1~holding_qty의 정수 — 계약 §5.3).
        price: 기준가(원) — fixture close(지정가 가정, 계약 §5.1).
        avg_price: 평균 매수가(원).
        holding_qty: 보유수량(주).
        portfolio_total_value: 매도 전 스냅샷 총 평가자산(원) — 잔여 비중의 고정 분모.
        trade_date: 체결 기준일("YYYY-MM-DD" 또는 date).

    Returns:
        JSON 직렬화 가능한 dict:
        {calculation_id, type="sell_preview", inputs{...},
         gross_amount(매도대금), fee(수수료), tax(거래세·농특세),
         net_proceeds(예상수령액), realized_pnl(실현손익),
         remaining_qty(잔여 수량), remaining_weight_pct(잔여 비중 %),
         is_full_sell(전량 매도 여부), settlement_date(결제일 D+2)}

    Raises:
        QuantityError: 수량이 0·음수·비정수이거나 보유수량을 초과.
        EngineInputError: 그 외 입력 형식 오류.
        (오류 시 계산 결과·calculation_id를 생성하지 않는다 — 계약 §5.3)
    """
    result = _compute_sell(
        qty, price, avg_price, holding_qty, portfolio_total_value, trade_date
    )
    return {"calculation_id": _next_calculation_id(), **result}


def buy_preview(
    qty: int,
    price: int,
    cash: int,
    trade_date: "str | datetime.date",
    holding_qty: int = 0,
    avg_price: "int | None" = None,
) -> dict:
    """매수 주문 미리보기를 계산한다(계약 §5 — 골든값 §5.2-c).

    예(first_buy 10주): 매수대금 460,000 / 수수료 69 / 총 결제예정액 460,069 /
    잔여 예수금 539,931 / 매수 후 비중 46.0% → 집중도 경고 True / 결제일 2026-07-21.

    Args:
        qty: 매수수량(양의 정수 — 계약 §5.3).
        price: 기준가(원).
        cash: 가용 예수금(원) — 매수 한도 검증·매수 후 비중의 고정 분모.
        trade_date: 체결 기준일("YYYY-MM-DD" 또는 date).
        holding_qty: 기존 보유수량(주, 기본 0) — 체결 후 평균 구매가 계산용(§5.1).
        avg_price: 기존 평균 구매가(원) — holding_qty>0일 때 필수.

    Returns:
        JSON 직렬화 가능한 dict:
        {calculation_id, type="buy_preview", inputs{...},
         gross_amount(매수대금), fee(수수료), tax(항상 0 — 매수는 세금 없음),
         total_cost(총 결제예정액), remaining_cash(잔여 예수금),
         weight_after_pct(매수 후 비중 %),
         concentration_warning(비중>40% 시 True — 차단 아닌 정보),
         avg_price_after(체결 후 평균 구매가 — §5.1),
         settlement_date(결제일 D+2)}

    Raises:
        QuantityError: 수량이 0·음수·비정수.
        InsufficientCashError: 총 결제예정액 > 가용 예수금.
        EngineInputError: 그 외 입력 형식 오류.
        (오류 시 계산 결과·calculation_id를 생성하지 않는다 — 계약 §5.3)
    """
    result = _compute_buy(qty, price, cash, trade_date, holding_qty, avg_price)
    return {"calculation_id": _next_calculation_id(), **result}


def hold_summary(
    price: int,
    avg_price: int,
    holding_qty: int,
    portfolio_total_value: int,
) -> dict:
    """'유지' 선택지의 보유 평가 요약을 반환한다(계약 §4 — 검증계획 U-03).

    주문 계산이 아니므로 **calculation_id를 발급하지 않는다**
    (U-03 "유지 = 계산 호출 없음" — 표시값의 원천만 제공. 숫자는 엔진만
    만든다는 불변 원칙에 따라 S4 화면의 '유지' 열이 이 함수를 사용한다).

    예(loss8): 평가손익 −120,000 / 평가손익률 −8.0% / 현재 비중 28.2%.

    Returns:
        JSON 직렬화 가능한 dict:
        {type="hold_summary", inputs{...}, eval_pnl(평가손익),
         eval_pnl_pct(평가손익률 %), weight_pct(현재 비중 %)}
        — calculation_id 없음.

    Raises:
        EngineInputError: 입력 형식 오류(보유 없음 포함 — holding_qty ≥ 1 필요).
    """
    _validate_int(price, "price(현재가)")
    _validate_int(avg_price, "avg_price(평균 매수가)")
    _validate_int(holding_qty, "holding_qty(보유수량)")
    _validate_int(portfolio_total_value, "portfolio_total_value(총 평가자산)")

    return {
        "type": "hold_summary",
        "inputs": {
            "price": price,
            "avg_price": avg_price,
            "holding_qty": holding_qty,
            "portfolio_total_value": portfolio_total_value,
        },
        # 평가손익 = (현재가 − 평균 매수가) × 보유수량 (계약 §4 — 실현손익과 구분)
        "eval_pnl": (price - avg_price) * holding_qty,
        # 평가손익률 = (현재가 − 평균 매수가) ÷ 평균 매수가 × 100, 소수 1자리
        "eval_pnl_pct": _pct(price - avg_price, avg_price),
        # 현재 비중 = 보유 평가액 ÷ 총 평가자산 × 100, 소수 1자리
        "weight_pct": _pct(holding_qty * price, portfolio_total_value),
    }
