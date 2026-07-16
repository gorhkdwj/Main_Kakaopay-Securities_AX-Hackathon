"""calculation_id 단위 테스트 — 검증계획 §1 U-11.

계약 §2: 형식 ``CALC-YYYYMMDD-HHMMSS-<seq>``, seq는 프로세스 내 증가 카운터.
모든 정상 계산 결과 JSON에 고유 ID가 포함돼야 한다.
"""

import datetime

from src.engine import CALC_ID_PATTERN, buy_preview, sell_preview

SELL_ARGS = dict(
    qty=10,
    price=46_000,
    avg_price=50_000,
    holding_qty=30,
    portfolio_total_value=4_900_000,
    trade_date="2026-07-17",
)
BUY_ARGS = dict(qty=8, price=46_000, cash=1_000_000, trade_date="2026-07-17")


class TestCalculationId:
    def test_u11_id_present_and_well_formed(self):
        """U-11: 모든 결과에 계약 §2 형식의 calculation_id 포함."""
        for result in (sell_preview(**SELL_ARGS), buy_preview(**BUY_ARGS)):
            calc_id = result["calculation_id"]
            assert isinstance(calc_id, str)
            assert CALC_ID_PATTERN.match(calc_id), calc_id

    def test_u11_ids_are_unique_and_increasing(self):
        """U-11: 연속 발급 ID는 서로 다르고 seq가 단조 증가(프로세스 내 카운터)."""
        ids = [sell_preview(**SELL_ARGS)["calculation_id"] for _ in range(3)]
        assert len(set(ids)) == 3
        seqs = [int(i.rsplit("-", 1)[1]) for i in ids]
        assert seqs == sorted(seqs)
        assert seqs[1] == seqs[0] + 1 and seqs[2] == seqs[1] + 1

    def test_u11_timestamp_part_is_real_clock(self):
        """ID의 날짜부는 발급 시점 실시각(미래 시각 기재 금지 — 계약 §1 취지)."""
        calc_id = sell_preview(**SELL_ARGS)["calculation_id"]
        date_part = calc_id.split("-")[1]  # YYYYMMDD
        today = datetime.date.today().strftime("%Y%m%d")
        assert date_part == today
