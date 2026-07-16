"""fixture ↔ 계약 골든값 전제 정합 테스트 (직전 정합 QA — 헌법 §6-①).

S1 fixture(data/fixtures/)가 계약 §5.2·§5.2-b·§5.2-c 골든값의 전제와
일치하는지 확인한다. 이 테스트가 깨지면 엔진 골든값 테스트의 전제 자체가
어긋난 것이므로, 계약·fixture 정합부터 복구해야 한다(fixture는 읽기 전용).
"""


class TestLoss8Premises:
    """계약 §5.2 전제: 총평가 4,900,000 / 30주 / 평단 50,000 / 현재가 46,000."""

    def test_premises(self, loss8):
        assert loss8["price"]["close"] == 46_000
        assert loss8["holding"]["qty"] == 30
        assert loss8["holding"]["avg_price"] == 50_000
        assert loss8["portfolio_total_value"] == 4_900_000
        assert loss8["cash"] == 0  # 매도 시나리오는 cash 0(계약 §3.1)
        assert loss8["trade_date"] == "2026-07-17"
        assert loss8["instrument"]["market"] == "KOSPI"


class TestProfit15Premises:
    """계약 §5.2-b 전제: 총평가 4,900,000 / 20주 / 평단 40,000 / 현재가 46,000."""

    def test_premises(self, profit15):
        assert profit15["price"]["close"] == 46_000
        assert profit15["holding"]["qty"] == 20
        assert profit15["holding"]["avg_price"] == 40_000
        assert profit15["portfolio_total_value"] == 4_900_000
        assert profit15["cash"] == 0
        assert profit15["trade_date"] == "2026-07-17"


class TestFirstBuyPremises:
    """계약 §5.2-c 전제: 예수금 1,000,000(전액 현금) / 보유 0 / 현재가 46,000."""

    def test_premises(self, first_buy):
        assert first_buy["price"]["close"] == 46_000
        assert first_buy["holding"]["qty"] == 0
        assert first_buy["holding"]["avg_price"] is None
        assert first_buy["cash"] == 1_000_000
        assert first_buy["portfolio_total_value"] == 1_000_000
        assert first_buy["trade_date"] == "2026-07-17"


class TestEngineAcceptsFixtureValues:
    """fixture 값을 그대로 엔진에 넣었을 때 골든값이 재현되는지(엔드투엔드 정합)."""

    def test_loss8_fixture_drives_golden_u01(self, loss8):
        from src.engine import sell_preview

        r = sell_preview(
            qty=10,
            price=loss8["price"]["close"],
            avg_price=loss8["holding"]["avg_price"],
            holding_qty=loss8["holding"]["qty"],
            portfolio_total_value=loss8["portfolio_total_value"],
            trade_date=loss8["trade_date"],
        )
        assert r["net_proceeds"] == 459_011
        assert r["realized_pnl"] == -40_989
        assert r["remaining_weight_pct"] == 18.8
        assert r["settlement_date"] == "2026-07-21"

    def test_first_buy_fixture_drives_golden_u14(self, first_buy):
        from src.engine import buy_preview

        r = buy_preview(
            qty=10,
            price=first_buy["price"]["close"],
            cash=first_buy["cash"],
            trade_date=first_buy["trade_date"],
        )
        assert r["total_cost"] == 460_069
        assert r["remaining_cash"] == 539_931
        assert r["weight_after_pct"] == 46.0
        assert r["concentration_warning"] is True
