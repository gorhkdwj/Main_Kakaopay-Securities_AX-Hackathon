"""매도 미리보기 단위 테스트 — 검증계획 §1 U-01·02·04·05·06·07·10·12·13.

기대값은 계약(docs/requirements-contract.md) §5.2(loss8)·§5.2-b(profit15)
골든값 표의 수치를 **그대로 하드코딩**한다(재계산 금지 — 골든값 표가 정답지).
"""

import json

import pytest

from src.engine import QuantityError, sell_preview

# 계약 §5.2 전제(loss8): 총평가 4,900,000 / 30주 / 평단 50,000 / 현재가 46,000
LOSS8 = dict(
    price=46_000,
    avg_price=50_000,
    holding_qty=30,
    portfolio_total_value=4_900_000,
    trade_date="2026-07-17",
)

# 계약 §5.2-b 전제(profit15): 총평가 4,900,000 / 20주 / 평단 40,000 / 현재가 46,000
PROFIT15 = dict(
    price=46_000,
    avg_price=40_000,
    holding_qty=20,
    portfolio_total_value=4_900_000,
    trade_date="2026-07-17",
)


class TestGoldenLoss8:
    """계약 §5.2 골든값 재현 — U-01·U-02·U-04·U-05."""

    def test_u01_partial_sell_10(self):
        """U-01 일부 매도 골든값(10주): 대금 460,000 / 수수료 69 / 거래세 920
        / 수령 459,011 / 실현손익 -40,989 / 잔여 비중 18.8%."""
        r = sell_preview(qty=10, **LOSS8)
        assert r["gross_amount"] == 460_000
        assert r["fee"] == 69
        assert r["tax"] == 920
        assert r["net_proceeds"] == 459_011
        assert r["realized_pnl"] == -40_989
        assert r["remaining_qty"] == 20
        assert r["remaining_weight_pct"] == 18.8
        assert r["is_full_sell"] is False
        assert r["settlement_date"] == "2026-07-21"

    def test_u02_full_sell_30(self):
        """U-02 전량 매도 골든값(30주): 대금 1,380,000 / 수수료 207 / 거래세 2,760
        / 수령 1,377,033 / 실현손익 -122,967 / 잔여 비중 0.0%."""
        r = sell_preview(qty=30, **LOSS8)
        assert r["gross_amount"] == 1_380_000
        assert r["fee"] == 207
        assert r["tax"] == 2_760
        assert r["net_proceeds"] == 1_377_033
        assert r["realized_pnl"] == -122_967
        assert r["remaining_qty"] == 0
        assert r["remaining_weight_pct"] == 0.0
        assert r["is_full_sell"] is True  # "보유 전량입니다" 라벨(계약 §5.3)
        assert r["settlement_date"] == "2026-07-21"

    def test_u04_min_qty_1(self):
        """U-04 최소 수량(1주): 대금 46,000 / 수수료 6 / 거래세 92
        / 수령 45,902 / 실현손익 -4,098. 잔여 비중 27.2%(계약 §5.2 표)."""
        r = sell_preview(qty=1, **LOSS8)
        assert r["gross_amount"] == 46_000
        assert r["fee"] == 6
        assert r["tax"] == 92
        assert r["net_proceeds"] == 45_902
        assert r["realized_pnl"] == -4_098
        assert r["remaining_qty"] == 29
        assert r["remaining_weight_pct"] == 27.2
        assert r["settlement_date"] == "2026-07-21"

    def test_u05_floor_rounding_each(self):
        """U-05 절사 규칙: 수수료·거래세·농특세 **각각** 원 미만 내림(계약 §5.1).
        1주 매도에서 수수료 46,000×0.00015=6.9→6(절사 증거), 거래세 92."""
        r = sell_preview(qty=1, **LOSS8)
        assert r["fee"] == 6      # 6.9 → 6 (원 미만 절사)
        assert r["tax"] == 92     # 92.0 → 92
        # 차감 순서 검증: 예상수령액 = 대금 − 수수료 − 거래세·농특세
        assert r["net_proceeds"] == r["gross_amount"] - r["fee"] - r["tax"]


class TestGoldenProfit15:
    """계약 §5.2-b 골든값 재현 — U-13."""

    def test_u13_profit15_sell_10(self):
        """U-13 profit15 골든값(10주): 수령 459,011 / 실현손익 +59,011
        / 잔여 비중 9.4% — loss8 10주와 대금·비용·수령 동일, 부호만 반대."""
        r = sell_preview(qty=10, **PROFIT15)
        assert r["gross_amount"] == 460_000
        assert r["fee"] == 69
        assert r["tax"] == 920
        assert r["net_proceeds"] == 459_011
        assert r["realized_pnl"] == +59_011
        assert r["remaining_qty"] == 10
        assert r["remaining_weight_pct"] == 9.4
        assert r["settlement_date"] == "2026-07-21"

    def test_u13b_profit15_full_sell_20(self):
        """계약 §5.2-b 보강(20주 전량): 대금 920,000 / 수수료 138 / 거래세 1,840
        / 수령 918,022 / 실현손익 +118,022 / 잔여 비중 0.0%."""
        r = sell_preview(qty=20, **PROFIT15)
        assert r["gross_amount"] == 920_000
        assert r["fee"] == 138
        assert r["tax"] == 1_840
        assert r["net_proceeds"] == 918_022
        assert r["realized_pnl"] == +118_022
        assert r["remaining_weight_pct"] == 0.0
        assert r["is_full_sell"] is True


class TestWeightDenominator:
    """U-10 비중 분모 고정 — 계약 §4."""

    def test_u10_denominator_is_pre_sell_snapshot(self):
        """U-10: 잔여 비중 분모는 매도 전 스냅샷 총평가 4,900,000 **고정**
        (계약 §4 정의 — 수령액 재편입 없음). 계약 §5.2 각주 산식 그대로:
        10주 매도 → 20×46,000=920,000 ÷ 4,900,000 = 18.77 → 18.8%."""
        r = sell_preview(qty=10, **LOSS8)
        # 계약 각주의 분모 4,900,000 기준 산식과 결과가 일치
        assert r["remaining_weight_pct"] == round(920_000 / 4_900_000 * 100, 1) == 18.8
        # 분모 입력이 그대로 보존됨(다른 값으로 대체되지 않았음의 증거)
        assert r["inputs"]["portfolio_total_value"] == 4_900_000


class TestSellErrors:
    """U-06·U-07·U-12 — 오류 입력은 계산·calculation_id를 생성하지 않는다."""

    def test_u06_qty_zero(self):
        """U-06 수량 0: 입력 오류(주문 아님)."""
        with pytest.raises(QuantityError):
            sell_preview(qty=0, **LOSS8)

    def test_u07_qty_exceeds_holding(self):
        """U-07 보유 초과(31주): 오류 반환 — 체결·계산 생성 금지."""
        with pytest.raises(QuantityError):
            sell_preview(qty=31, **LOSS8)

    @pytest.mark.parametrize("bad_qty", [-5, 2.5])
    def test_u12_negative_and_non_integer(self, bad_qty):
        """U-12 음수·비정수 수량(-5, 2.5): 입력 오류."""
        with pytest.raises(QuantityError):
            sell_preview(qty=bad_qty, **LOSS8)

    @pytest.mark.parametrize("bad_qty", [True, "10", None, 10.0])
    def test_u12_boundary_types_rejected(self, bad_qty):
        """U-12 보강: bool·문자열·None·정수값 float도 '양의 정수'가 아니므로 거부
        (계약 §5.3 — 수량은 양의 정수만)."""
        with pytest.raises(QuantityError):
            sell_preview(qty=bad_qty, **LOSS8)

    def test_error_does_not_issue_calculation_id(self):
        """오류 시 calculation_id를 생성하지 않음(계약 §5.3) — seq 미소모 확인:
        오류 시도 전후의 정상 호출 seq가 정확히 1 증가."""
        before = int(sell_preview(qty=1, **LOSS8)["calculation_id"].rsplit("-", 1)[1])
        with pytest.raises(QuantityError):
            sell_preview(qty=99, **LOSS8)
        after = int(sell_preview(qty=1, **LOSS8)["calculation_id"].rsplit("-", 1)[1])
        assert after == before + 1


class TestDeterminismAndSerialization:
    """엔진 공통 성질 — 결정론·JSON 직렬화(구현 규칙)."""

    def test_same_input_same_output_except_calculation_id(self):
        """같은 입력 → calculation_id 제외 항상 같은 출력(결정론 원칙)."""
        r1 = sell_preview(qty=10, **LOSS8)
        r2 = sell_preview(qty=10, **LOSS8)
        r1.pop("calculation_id")
        r2.pop("calculation_id")
        assert r1 == r2

    def test_result_is_json_serializable(self):
        """정상 결과는 JSON 직렬화 가능한 dict여야 한다(S4·S5 인터페이스)."""
        r = sell_preview(qty=10, **LOSS8)
        restored = json.loads(json.dumps(r, ensure_ascii=False))
        assert restored == r
