"""매수 미리보기 단위 테스트 — 검증계획 §1 U-14·U-15.

기대값은 계약(docs/requirements-contract.md) §5.2-c 골든값 표를 그대로 하드코딩.
전제: 다온소재(KOSPI) / 예수금 1,000,000 / 현재가 46,000 / trade_date 2026-07-17.
매수는 거래세·농특세 없음(수수료 0.015%만 — 계약 §5.1).
"""

import json

import pytest

from src.engine import InsufficientCashError, QuantityError, buy_preview

# 계약 §5.2-c 전제(first_buy)
FIRST_BUY = dict(price=46_000, cash=1_000_000, trade_date="2026-07-17")


class TestGoldenFirstBuy:
    """계약 §5.2-c 골든값 재현 — U-14·U-15와 경계 보강."""

    def test_u14_buy_10_concentration_warning(self):
        """U-14 집중도 경고(10주): 총 결제 460,069 / 잔여 예수금 539,931
        / 매수 후 비중 46.0% → 집중도 경고 True(>40%, 차단 아님)."""
        r = buy_preview(qty=10, **FIRST_BUY)
        assert r["gross_amount"] == 460_000
        assert r["fee"] == 69
        assert r["tax"] == 0  # 매수는 거래세·농특세 없음
        assert r["total_cost"] == 460_069
        assert r["remaining_cash"] == 539_931
        assert r["weight_after_pct"] == 46.0
        assert r["concentration_warning"] is True
        assert r["settlement_date"] == "2026-07-21"

    def test_u15_buy_22_insufficient_cash(self):
        """U-15 예수금 초과(22주): 총 결제예정액 1,012,151 > 예수금 1,000,000
        → 오류 반환(체결·계산 생성 금지)."""
        with pytest.raises(InsufficientCashError):
            buy_preview(qty=22, **FIRST_BUY)

    def test_golden_buy_8_no_warning(self):
        """계약 §5.2-c(8주): 매수대금 368,000 / 수수료 55(55.2→55 절사)
        / 총 결제 368,055 / 잔여 631,945 / 비중 36.8% → 경고 없음."""
        r = buy_preview(qty=8, **FIRST_BUY)
        assert r["gross_amount"] == 368_000
        assert r["fee"] == 55
        assert r["total_cost"] == 368_055
        assert r["remaining_cash"] == 631_945
        assert r["weight_after_pct"] == 36.8
        assert r["concentration_warning"] is False
        assert r["settlement_date"] == "2026-07-21"

    def test_golden_max_buyable_21(self):
        """계약 §5.2-c 경계: 매수 가능 최대 수량 21주
        (총 결제 966,000+144=966,144 ≤ 1,000,000) — 22주부터 오류."""
        r = buy_preview(qty=21, **FIRST_BUY)
        assert r["gross_amount"] == 966_000
        assert r["fee"] == 144
        assert r["total_cost"] == 966_144
        assert r["remaining_cash"] == 33_856


class TestBuyErrors:
    """매수 입력 오류 — 계약 §5.3(수량은 양의 정수만)."""

    @pytest.mark.parametrize("bad_qty", [0, -5, 2.5, True, "10", None])
    def test_invalid_qty_rejected(self, bad_qty):
        """0·음수·비정수·비수치 수량은 QuantityError."""
        with pytest.raises(QuantityError):
            buy_preview(qty=bad_qty, **FIRST_BUY)

    def test_zero_cash_scenario_rejects_any_buy(self):
        """매도 시나리오 전제(cash=0 — 계약 §3.1)에서는 어떤 매수도 예수금 초과."""
        with pytest.raises(InsufficientCashError):
            buy_preview(qty=1, price=46_000, cash=0, trade_date="2026-07-17")

    def test_error_does_not_issue_calculation_id(self):
        """오류(예수금 초과) 시 calculation_id 미발급 — seq 미소모 확인."""
        before = int(buy_preview(qty=1, **FIRST_BUY)["calculation_id"].rsplit("-", 1)[1])
        with pytest.raises(InsufficientCashError):
            buy_preview(qty=22, **FIRST_BUY)
        after = int(buy_preview(qty=1, **FIRST_BUY)["calculation_id"].rsplit("-", 1)[1])
        assert after == before + 1


class TestBuyDeterminismAndSerialization:
    """엔진 공통 성질 — 결정론·JSON 직렬화."""

    def test_same_input_same_output_except_calculation_id(self):
        r1 = buy_preview(qty=10, **FIRST_BUY)
        r2 = buy_preview(qty=10, **FIRST_BUY)
        r1.pop("calculation_id")
        r2.pop("calculation_id")
        assert r1 == r2

    def test_result_is_json_serializable(self):
        r = buy_preview(qty=10, **FIRST_BUY)
        restored = json.loads(json.dumps(r, ensure_ascii=False))
        assert restored == r


class TestAvgPriceAfter:
    """체결 후 평균 구매가(계약 §5.1 — 사용자 요청 2026-07-18, D-0718-0255 후속).

    순수 매입가 기준(수수료 미포함)·원 미만 절사. 보유 0이면 = 기준가.
    """

    def test_first_buy_no_holding_equals_price(self):
        r = buy_preview(qty=10, **FIRST_BUY)
        assert r["avg_price_after"] == 46_000
        assert r["inputs"]["holding_qty"] == 0

    def test_loss8_holding_10_shares(self):
        # (30×50,000 + 460,000) ÷ 40 = 49,000 (정확)
        r = buy_preview(qty=10, holding_qty=30, avg_price=50_000, **FIRST_BUY)
        assert r["avg_price_after"] == 49_000

    def test_loss8_holding_8_shares_floor(self):
        # (1,500,000 + 368,000) ÷ 38 = 49,157.89… → 49,157 (절사)
        r = buy_preview(qty=8, holding_qty=30, avg_price=50_000, **FIRST_BUY)
        assert r["avg_price_after"] == 49_157

    def test_profit15_holding_10_shares(self):
        # (20×40,000 + 460,000) ÷ 30 = 42,000 (정확)
        r = buy_preview(qty=10, holding_qty=20, avg_price=40_000, **FIRST_BUY)
        assert r["avg_price_after"] == 42_000

    def test_holding_requires_avg_price(self):
        from src.engine import EngineInputError

        with pytest.raises(EngineInputError):
            buy_preview(qty=10, holding_qty=30, avg_price=None, **FIRST_BUY)


def test_sell_avg_price_unchanged_and_full_sell_none():
    """매도는 평균 구매가를 바꾸지 않는다(계약 §5.1) — 전량 매도는 잔여 없음."""
    from src.engine import sell_preview

    partial = sell_preview(10, 46_000, 50_000, 30, 4_900_000, "2026-07-17")
    assert partial["avg_price_after"] == 50_000
    full = sell_preview(30, 46_000, 50_000, 30, 4_900_000, "2026-07-17")
    assert full["avg_price_after"] is None
