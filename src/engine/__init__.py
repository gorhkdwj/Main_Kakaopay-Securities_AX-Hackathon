"""결정론 계산 엔진(S2) — 판단 여권 데모의 '숫자의 유일한 생산자'.

기준 계약: docs/requirements-contract.md §2·§4·§5·§11.
불변 원칙(구현 계획 §0): 숫자는 이 엔진만 만들고, LLM은 근거가 붙은 설명만 한다.
표준 라이브러리만 사용 — LLM·네트워크·실주문 코드가 어떤 형태로도 없다.

공개 API(S4 웹 UI·S5 브리핑이 호출하는 인터페이스):
    from src.engine import sell_preview, buy_preview, hold_summary, settle_date, settle_order

    - sell_preview(qty, price, avg_price, holding_qty, portfolio_total_value, trade_date)
        → 매도 미리보기 dict(+calculation_id)
    - buy_preview(qty, price, cash, trade_date)
        → 매수 미리보기 dict(+calculation_id, 집중도 경고 포함)
    - hold_summary(price, avg_price, holding_qty, portfolio_total_value)
        → '유지' 표시용 평가 요약 dict(calculation_id 없음 — U-03)
    - settle_date(trade_date, n=2)
        → D+n 영업일 결제일 문자열(토·일만 제외 — [데모 고정] 공휴일 미반영)
    - settle_order(preview, confirmed_qty=None)
        → 모의 체결 기록 dict(is_mock=True 상시)

예외(전부 ValueError 파생 — 오류 시 계산 결과·calculation_id·체결 기록 미생성):
    EngineInputError ⊃ QuantityError · InsufficientCashError · InvalidPreviewError
"""

from .biz_days import settle_date
from .calculator import (
    CALC_ID_PATTERN,
    EngineInputError,
    InsufficientCashError,
    InvalidPreviewError,
    QuantityError,
    buy_preview,
    hold_summary,
    sell_preview,
)
from .settle import settle_order

__all__ = [
    # 계산 API
    "sell_preview",
    "buy_preview",
    "hold_summary",
    "settle_date",
    "settle_order",
    # 예외
    "EngineInputError",
    "QuantityError",
    "InsufficientCashError",
    "InvalidPreviewError",
    # 검증용 상수
    "CALC_ID_PATTERN",
]
