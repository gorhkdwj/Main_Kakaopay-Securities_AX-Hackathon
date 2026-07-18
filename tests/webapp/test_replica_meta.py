"""재현 화면 헤더 표기 데이터 계약 검증 (계약 §3.1·§5 — 2026-07-18 승인).

- meta.price.change_amount: 서버 파생 결정론 계산(close - prev_close) —
  프런트 산수 금지 원칙상 이 값이 없으면 화면이 등락 금액을 만들 수 없다.
- instrument.market_cap · volume.today: 재현 화면 거래량·시가총액 표기의
  데이터 원천(하드코딩 금지 — D-0718 사용자 지시).
"""

import pytest

SCENARIOS = ["loss8", "profit15", "first_buy"]


@pytest.mark.parametrize("sid", SCENARIOS)
def test_change_amount_is_server_derived(client, sid):
    meta = client.get(f"/api/scenario/{sid}").json()["meta"]
    price = meta["price"]
    assert price["change_amount"] == price["close"] - price["prev_close"]
    assert isinstance(price["change_amount"], int)


@pytest.mark.parametrize("sid", SCENARIOS)
def test_market_cap_and_volume_present(client, sid):
    meta = client.get(f"/api/scenario/{sid}").json()["meta"]
    cap = meta["instrument"]["market_cap"]
    assert isinstance(cap, int) and cap > 0
    today = meta["volume"]["today"]
    assert isinstance(today, int) and today > 0


def test_change_amount_matches_scenario_direction(client):
    """등락 금액 부호가 등락률 부호와 일치(표기 정합)."""
    expected = {"loss8": -4000, "profit15": 2000, "first_buy": 500}
    for sid, amt in expected.items():
        price = client.get(f"/api/scenario/{sid}").json()["meta"]["price"]
        assert price["change_amount"] == amt
        if amt:
            assert (price["change_amount"] > 0) == (price["change_pct"] > 0)
