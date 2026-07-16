"""모의 체결(settle_order) 단위 테스트.

계약 §1(모의 체결 — 기록에 모의 여부 상시 표기)·§5.3(오류 시 체결 미생성).
preview 검증(형식·수량 대조·재계산 대조)과 기록 필드를 확인한다.
"""

import json
import re

import pytest

from src.engine import InvalidPreviewError, buy_preview, sell_preview, settle_order

SELL_ARGS = dict(
    qty=10,
    price=46_000,
    avg_price=50_000,
    holding_qty=30,
    portfolio_total_value=4_900_000,
    trade_date="2026-07-17",
)
BUY_ARGS = dict(qty=8, price=46_000, cash=1_000_000, trade_date="2026-07-17")

SETTLED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} KST$")  # 계약 §11 포맷


class TestMockSettlementRecord:
    def test_sell_settlement_record(self):
        """매도 preview → 모의 체결 기록: is_mock=True 상시, 금액 필드 일치."""
        p = sell_preview(**SELL_ARGS)
        rec = settle_order(p)
        assert rec["type"] == "mock_settlement"
        assert rec["is_mock"] is True  # 모의 여부 필드 상시 포함(계약 §1)
        assert rec["calculation_id"] == p["calculation_id"]
        assert rec["side"] == "sell"
        assert rec["qty"] == 10
        assert rec["price"] == 46_000
        assert rec["gross_amount"] == 460_000
        assert rec["fee"] == 69
        assert rec["tax"] == 920
        assert rec["net_proceeds"] == 459_011
        assert rec["realized_pnl"] == -40_989
        assert rec["remaining_qty"] == 20
        assert rec["settlement_date"] == "2026-07-21"
        assert SETTLED_AT_RE.match(rec["settled_at"])

    def test_buy_settlement_record(self):
        """매수 preview → 모의 체결 기록(총 결제·잔여 예수금 포함)."""
        p = buy_preview(**BUY_ARGS)
        rec = settle_order(p)
        assert rec["is_mock"] is True
        assert rec["side"] == "buy"
        assert rec["gross_amount"] == 368_000
        assert rec["fee"] == 55
        assert rec["tax"] == 0
        assert rec["total_cost"] == 368_055
        assert rec["remaining_cash"] == 631_945
        assert rec["settlement_date"] == "2026-07-21"

    def test_confirmed_qty_match_passes(self):
        """사용자 재확인 수량이 일치하면 체결 생성."""
        p = sell_preview(**SELL_ARGS)
        rec = settle_order(p, confirmed_qty=10)
        assert rec["qty"] == 10

    def test_record_is_json_serializable(self):
        rec = settle_order(sell_preview(**SELL_ARGS))
        assert json.loads(json.dumps(rec, ensure_ascii=False)) == rec


class TestSettleValidation:
    """검증 실패 시 체결 기록을 생성하지 않는다(InvalidPreviewError)."""

    def test_confirmed_qty_mismatch_rejected(self):
        """재확인 수량 불일치 → 체결 금지(수량 조작 방지 — 계약 §6 취지)."""
        p = sell_preview(**SELL_ARGS)
        with pytest.raises(InvalidPreviewError):
            settle_order(p, confirmed_qty=30)

    def test_tampered_amount_rejected(self):
        """수령액이 변조된 preview는 재계산 대조에서 차단."""
        p = sell_preview(**SELL_ARGS)
        p["net_proceeds"] = 999_999
        with pytest.raises(InvalidPreviewError):
            settle_order(p)

    def test_tampered_settlement_date_rejected(self):
        """결제일이 변조된 preview도 차단."""
        p = buy_preview(**BUY_ARGS)
        p["settlement_date"] = "2026-07-18"  # 토요일로 조작
        with pytest.raises(InvalidPreviewError):
            settle_order(p)

    def test_missing_calculation_id_rejected(self):
        """calculation_id 없는 dict는 엔진 산출물이 아니므로 거부."""
        p = sell_preview(**SELL_ARGS)
        del p["calculation_id"]
        with pytest.raises(InvalidPreviewError):
            settle_order(p)

    def test_malformed_calculation_id_rejected(self):
        p = sell_preview(**SELL_ARGS)
        p["calculation_id"] = "CALC-BAD-ID"
        with pytest.raises(InvalidPreviewError):
            settle_order(p)

    @pytest.mark.parametrize(
        "bad_preview",
        [None, "preview", 42, {}, {"type": "hold_summary"}, {"type": "sell_preview"}],
    )
    def test_non_preview_inputs_rejected(self, bad_preview):
        """dict가 아니거나 type·필수 구조가 없는 입력은 전부 거부."""
        with pytest.raises(InvalidPreviewError):
            settle_order(bad_preview)
