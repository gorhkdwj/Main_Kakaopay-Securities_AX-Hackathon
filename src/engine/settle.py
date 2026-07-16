"""모의 체결 모듈 — preview 결과 검증 후 가상 체결 기록 생성.

기준 계약: docs/requirements-contract.md §1(모의 체결 정의)·§5.3(입력 오류 시
체결 기록 미생성)·§11(시각 포맷). 헌법 §14: 실주문·AI 자동 주문 금지.

**이 모듈에는 실주문·외부 API 호출 코드가 어떤 형태로도 없다.**
입력(preview dict)을 결정론적으로 재계산·대조한 뒤 로컬 dict 기록만 만든다.
네트워크·LLM 호출 금지, 표준 라이브러리만 사용.

체결 기록에는 모의 여부 필드(``is_mock: True``)가 상시 포함된다
(계약 §1 "화면 전역에 '모의' 상시 표기"의 데이터 원천).
"""

from __future__ import annotations

import datetime

from .calculator import (
    CALC_ID_PATTERN,
    InvalidPreviewError,
    _compute_buy,
    _compute_sell,
)

__all__ = ["settle_order"]

#: preview type → (재계산 함수, side 라벨)
_PREVIEW_KINDS = {
    "sell_preview": (_compute_sell, "sell"),
    "buy_preview": (_compute_buy, "buy"),
}


def _now_kst_label() -> str:
    """체결 기록 생성 시각을 계약 §11 포맷(``YYYY-MM-DD HH:mm KST``)으로 반환.

    로컬 시각 = KST 전제(데모는 KST 로컬 노트북 실행 — 계약 §11).
    실제 현재 시각만 기록한다(미래 시각 기재 금지 — 계약 §1 as_of 원칙).
    """
    return f"{datetime.datetime.now():%Y-%m-%d %H:%M} KST"


def settle_order(preview: dict, confirmed_qty: "int | None" = None) -> dict:
    """preview 결과를 검증한 뒤 **가상(모의) 체결 기록** dict를 생성한다.

    검증 절차(모두 통과해야 기록 생성 — 실패 시 InvalidPreviewError):
      1. preview가 dict이고 type이 sell_preview/buy_preview 중 하나인지.
      2. calculation_id가 존재하고 계약 §2 형식(``CALC-YYYYMMDD-HHMMSS-<seq>``)인지.
      3. confirmed_qty가 주어지면 preview 입력 수량과 일치하는지
         (사용자 재확인 수량 대조 — 수량 불일치 차단, 계약 §6 취지).
      4. preview의 inputs로 엔진이 **재계산**한 결과와 모든 계산 필드가
         일치하는지(위·변조된 숫자로는 체결이 생성되지 않음 — 결정론 재검증).

    Args:
        preview: :func:`~src.engine.calculator.sell_preview` 또는
            :func:`~src.engine.calculator.buy_preview`가 반환한 dict.
        confirmed_qty: (선택) 사용자가 최종 확인 화면에서 입력한 수량.
            None이면 대조를 생략한다.

    Returns:
        JSON 직렬화 가능한 모의 체결 기록 dict:
        {type="mock_settlement", is_mock=True(상시), calculation_id,
         side("sell"|"buy"), qty, price,
         gross_amount, fee, tax,
         net_proceeds·realized_pnl·remaining_qty(매도) 또는
         total_cost·remaining_cash(매수),
         settlement_date(결제일 D+2), settled_at(기록 생성 시각 KST)}

    Raises:
        InvalidPreviewError: 위 검증 중 하나라도 실패(체결 기록 미생성).
        QuantityError·InsufficientCashError·EngineInputError:
            inputs 자체가 유효 범위를 벗어난 경우(재계산 단계에서 발생).
    """
    # 1. 구조 검증
    if not isinstance(preview, dict):
        raise InvalidPreviewError(
            f"preview는 엔진이 생성한 dict여야 합니다: {type(preview).__name__}"
        )
    kind = _PREVIEW_KINDS.get(preview.get("type"))
    if kind is None:
        raise InvalidPreviewError(
            f"알 수 없는 preview type입니다: {preview.get('type')!r}"
        )
    recompute, side = kind

    # 2. calculation_id 형식 검증(계약 §2)
    calc_id = preview.get("calculation_id")
    if not isinstance(calc_id, str) or not CALC_ID_PATTERN.match(calc_id):
        raise InvalidPreviewError(
            f"calculation_id가 없거나 형식이 잘못됐습니다: {calc_id!r}"
        )

    inputs = preview.get("inputs")
    if not isinstance(inputs, dict):
        raise InvalidPreviewError("preview에 inputs가 없습니다")

    # 3. 사용자 재확인 수량 대조(수량 불일치 차단 — 계약 §6 취지)
    if confirmed_qty is not None and confirmed_qty != inputs.get("qty"):
        raise InvalidPreviewError(
            f"확인 수량({confirmed_qty!r})이 계산된 수량({inputs.get('qty')!r})과"
            " 다릅니다 — 체결을 만들 수 없습니다"
        )

    # 4. 결정론 재계산 대조 — 계산 필드 전부 일치해야 한다
    try:
        recomputed = recompute(**inputs)
    except TypeError as exc:  # inputs 키 누락·과잉
        raise InvalidPreviewError(f"preview inputs가 불완전합니다: {exc}") from exc
    mismatched = [
        key
        for key, value in recomputed.items()
        if key != "type" and preview.get(key) != value
    ]
    if mismatched:
        raise InvalidPreviewError(
            f"preview 수치가 엔진 재계산과 다릅니다(변조 의심): {mismatched}"
        )

    # 5. 가상 체결 기록 생성 — is_mock 상시 True(계약 §1)
    record = {
        "type": "mock_settlement",
        "is_mock": True,
        "calculation_id": calc_id,
        "side": side,
        "qty": inputs["qty"],
        "price": inputs["price"],
        "gross_amount": recomputed["gross_amount"],
        "fee": recomputed["fee"],
        "tax": recomputed["tax"],
        "settlement_date": recomputed["settlement_date"],
        "settled_at": _now_kst_label(),
    }
    if side == "sell":
        record["net_proceeds"] = recomputed["net_proceeds"]
        record["realized_pnl"] = recomputed["realized_pnl"]
        record["remaining_qty"] = recomputed["remaining_qty"]
    else:
        record["total_cost"] = recomputed["total_cost"]
        record["remaining_cash"] = recomputed["remaining_cash"]
    return record
