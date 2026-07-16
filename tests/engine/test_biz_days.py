"""결제일(D+2) 단위 테스트 — 검증계획 §1 U-08·U-09.

영업일 = 월~금(토·일만 제외). [데모 고정] 공휴일 미반영(계약 §11).
"""

import datetime

import pytest

from src.engine import settle_date


class TestSettleDate:
    def test_u08_weekend_crossing(self):
        """U-08 D+2 주말 걸침: 체결 2026-07-17(금) → 결제일 2026-07-21(화)
        — 토(7/18)·일(7/19) 제외, 월(7/20)=1·화(7/21)=2."""
        assert settle_date("2026-07-17", 2) == "2026-07-21"

    def test_u09_weekday_plain(self):
        """U-09 D+2 평일: 체결 2026-07-14(화) → 2026-07-16(목)."""
        assert settle_date("2026-07-14", 2) == "2026-07-16"

    def test_default_n_is_2(self):
        """기본 n=2(D+2 — 계약 §4)."""
        assert settle_date("2026-07-17") == "2026-07-21"

    def test_accepts_date_object(self):
        """date 객체 입력도 허용(엔진 내부·S4 양쪽 편의)."""
        assert settle_date(datetime.date(2026, 7, 17), 2) == "2026-07-21"

    def test_n_zero_returns_trade_date(self):
        """n=0이면 체결일 그대로."""
        assert settle_date("2026-07-17", 0) == "2026-07-17"

    @pytest.mark.parametrize("bad", ["2026/07/17", "20260717", 20260717, None])
    def test_invalid_trade_date_rejected(self, bad):
        """형식 오류 입력은 ValueError."""
        with pytest.raises(ValueError):
            settle_date(bad, 2)

    @pytest.mark.parametrize("bad_n", [-1, 1.5, "2"])
    def test_invalid_n_rejected(self, bad_n):
        with pytest.raises(ValueError):
            settle_date("2026-07-17", bad_n)
