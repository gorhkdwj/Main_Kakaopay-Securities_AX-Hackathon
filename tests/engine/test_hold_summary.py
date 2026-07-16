"""'유지' 평가 요약 단위 테스트 — 검증계획 §1 U-03.

U-03: '유지'는 매도 계산 호출 없이 평가손익 -120,000·비중 28.2%를 표시한다.
그 표시값의 원천(hold_summary)이 계약 §4 정의와 일치하는지,
그리고 주문 계산이 아니므로 calculation_id를 발급하지 않는지 확인한다.
"""

import json

from src.engine import hold_summary


class TestHoldSummary:
    def test_u03_hold_display_values_loss8(self):
        """U-03 유지(계산 없음): 평가손익 -120,000 / 비중 28.2% 표시 일치
        (계약 §5.2 '유지' 열 — 평가손익률 -8.0%는 계약 §4 정의)."""
        r = hold_summary(
            price=46_000,
            avg_price=50_000,
            holding_qty=30,
            portfolio_total_value=4_900_000,
        )
        assert r["eval_pnl"] == -120_000
        assert r["eval_pnl_pct"] == -8.0
        assert r["weight_pct"] == 28.2

    def test_u03_no_calculation_id(self):
        """U-03 '계산 없음': 유지 요약은 주문 계산이 아니므로
        calculation_id를 포함하지 않는다(계약 §2 — ID는 주문 계산 연결용)."""
        r = hold_summary(
            price=46_000,
            avg_price=50_000,
            holding_qty=30,
            portfolio_total_value=4_900_000,
        )
        assert "calculation_id" not in r

    def test_hold_display_values_profit15(self):
        """profit15 전제 보강(계약 §5.2-b): 평가손익 +120,000 / 평단 대비 +15.0%
        / 매도 전 비중 18.8%."""
        r = hold_summary(
            price=46_000,
            avg_price=40_000,
            holding_qty=20,
            portfolio_total_value=4_900_000,
        )
        assert r["eval_pnl"] == +120_000
        assert r["eval_pnl_pct"] == +15.0
        assert r["weight_pct"] == 18.8

    def test_result_is_json_serializable(self):
        r = hold_summary(
            price=46_000,
            avg_price=50_000,
            holding_qty=30,
            portfolio_total_value=4_900_000,
        )
        assert json.loads(json.dumps(r, ensure_ascii=False)) == r
