"""통합 테스트 I-01·I-03 — 대표 시나리오 API 시퀀스 완주(검증 계획 §3).

I-01: scenario_loss8 8단계 흐름의 API 시퀀스
      (scenarios → scenario → preview 10주·30주 → settle → record)
      — LLM·외부 네트워크 0회(TestClient만 사용), 골든값은 계약 §5.2.
I-03: scenario_profit15 — +수익 판매 흐름의 세금·수령·D+2·부호(+59,011).
"""

from __future__ import annotations

import json
import re


# ---------------------------------------------------------------------------
# I-01 · loss8 완주
# ---------------------------------------------------------------------------

def test_i01_scenario_list_defaults_to_loss8(client):
    body = client.get("/api/scenarios").json()
    assert body["ok"] is True
    ids = [s["scenario_id"] for s in body["scenarios"]]
    assert ids[0] == "loss8"
    assert body["scenarios"][0]["is_default"] is True
    assert {"loss8", "profit15", "first_buy"} <= set(ids)


def test_i01_loss8_full_api_sequence(client, records_dir):
    # ── ①② 시나리오 로드: 정적 브리핑이 guard를 통과해 돌아온다 ──────
    data = client.get("/api/scenario/loss8").json()
    assert data["ok"] is True
    b = data["briefing"]

    # facts = 공시(DEMO-SRC-101) + 시세·거래량 카드(DEMO-SRC-102) — 전부 출처·기준시각 보유
    assert [f["source_id"] for f in b["facts"]] == ["DEMO-SRC-101", "DEMO-SRC-102"]
    assert all(isinstance(f["as_of"], str) and f["as_of"] for f in b["facts"])
    assert "3분기 잠정 영업이익 128억" in b["facts"][0]["text"]
    assert "종가 46,000원" in b["facts"][1]["text"]
    assert "3.2배" in b["facts"][1]["text"]

    # 해석 양면 + 모름 최소 1건(모름은 구체적 — 언제 확인되는지 병기)
    assert {i["stance"] for i in b["interpretations"]} == {"긍정 시각", "부정 시각"}
    assert len(b["unknowns"]) >= 1
    assert any("누구도 알 수 없습니다" in u for u in b["unknowns"])
    assert any("다음 실적 발표에서 확인됩니다" in u for u in b["unknowns"])

    # next_questions — plan의 재검토 조건 대조 질문
    assert any("실적 2개 분기 연속 악화" in q for q in b["next_questions"])

    # guard: 차단 0·경고 0·information_only
    assert b["policy_result"] == "information_only"
    assert data["guard"]["record"]["blocked"] == []
    assert data["guard"]["record"]["warnings"] == []
    assert b["user_inputs"]["situation"] == "loss8"

    # 지난 투자 일지 리마인드(past_records — 사용자 글 인용용)
    assert len(data["past_records"]) == 1
    rec = data["past_records"][0]
    assert rec["recorded_at"] == "2026-03-02"
    assert rec["side"] == "buy" and rec["qty"] == 30
    assert rec["reason_text"].strip()

    # '유지' 열의 표시값(hold_summary — U-03: calculation_id 없음)
    hold = data["hold"]
    assert hold["eval_pnl"] == -120000
    assert hold["eval_pnl_pct"] == -8.0
    assert hold["weight_pct"] == 28.2
    assert "calculation_id" not in hold

    # community_buzz — 사실 카드와 분리 반환('관심 지표' 프레임)
    assert data["community_buzz"]["level"] == "높음"

    # 시세 헤더용 메타
    assert data["meta"]["market_label"] == "SOR 정규장"
    assert data["meta"]["side"] == "sell"

    # ── ④ 미리보기: 10주 골든값(계약 §5.2) ────────────────────────────
    r10 = client.post("/api/preview",
                      json={"scenario_id": "loss8", "side": "sell", "qty": 10})
    assert r10.status_code == 200
    body10 = r10.json()
    p10 = body10["preview"]
    assert p10["gross_amount"] == 460000
    assert p10["fee"] == 69
    assert p10["tax"] == 920
    assert p10["net_proceeds"] == 459011
    assert p10["realized_pnl"] == -40989
    assert p10["remaining_qty"] == 20
    assert p10["remaining_weight_pct"] == 18.8
    assert p10["is_full_sell"] is False
    assert p10["settlement_date"] == "2026-07-21"
    assert re.match(r"^CALC-\d{8}-\d{6}-\d+$", p10["calculation_id"])
    # guard에 calculation이 전달돼 수량 대조를 통과했다
    assert body10["guard"]["policy_result"] == "information_only"
    assert body10["guard"]["record"]["blocked"] == []

    # ── ④ 미리보기: 30주 전량 골든값 ──────────────────────────────────
    p30 = client.post("/api/preview",
                      json={"scenario_id": "loss8", "side": "sell", "qty": 30}).json()["preview"]
    assert p30["gross_amount"] == 1380000
    assert p30["fee"] == 207
    assert p30["tax"] == 2760
    assert p30["net_proceeds"] == 1377033
    assert p30["realized_pnl"] == -122967
    assert p30["remaining_weight_pct"] == 0.0
    assert p30["is_full_sell"] is True  # "보유 전량입니다" 라벨의 데이터 원천

    # ── ⑥ 모의 체결(재확인 수량 대조 포함) ────────────────────────────
    rs = client.post("/api/settle", json={"preview": p10, "confirmed_qty": 10})
    assert rs.status_code == 200
    st = rs.json()["settlement"]
    assert st["type"] == "mock_settlement"
    assert st["is_mock"] is True  # '모의' 상시 표기의 데이터 원천
    assert st["side"] == "sell" and st["qty"] == 10
    assert st["net_proceeds"] == 459011
    assert st["settlement_date"] == "2026-07-21"
    assert st["calculation_id"] == p10["calculation_id"]

    # ── ⑦ 투자 일지(REC) 저장 — 계약 §3.3 ─────────────────────────────
    rr = client.post("/api/record", json={
        "scenario_id": "loss8",
        "intent": "일부 판매 검토",
        "reason_text": "재검토 조건에는 아직 해당하지 않지만, 비중이 목표보다 높아 10주만 줄여 보려는 생각.",
        "calculation_id": st["calculation_id"],
        "review_date": "다음 실적 발표에서 재검토 조건 해당 여부 확인",
    })
    assert rr.status_code == 200
    saved = rr.json()["record"]
    assert re.match(r"^REC-\d{4}-\d{6}-\d+$", saved["record_id"])

    files = list(records_dir.glob("REC-*.json"))
    assert len(files) == 1 and files[0].stem == saved["record_id"]
    on_disk = json.loads(files[0].read_text(encoding="utf-8"))
    assert on_disk == saved


# ---------------------------------------------------------------------------
# I-03 · profit15 (+수익 판매 — 부호·리마인드)
# ---------------------------------------------------------------------------

def test_i03_profit15_load_and_remind(client):
    data = client.get("/api/scenario/profit15").json()
    assert data["ok"] is True
    # 보유 평가(+15%) — hold_summary
    assert data["hold"]["eval_pnl"] == 120000
    assert data["hold"]["eval_pnl_pct"] == 15.0
    assert data["hold"]["weight_pct"] == 18.8
    # 리마인드 데이터(매수 당시 일지)
    assert len(data["past_records"]) == 1
    assert data["past_records"][0]["side"] == "buy"
    assert data["past_records"][0]["qty"] == 20
    # 브리핑 사실 소스(한빛식품 = 2xx)
    assert [f["source_id"] for f in data["briefing"]["facts"]] == \
        ["DEMO-SRC-201", "DEMO-SRC-202"]
    assert data["guard"]["record"]["blocked"] == []


def test_i03_profit15_preview_sign_and_settle(client):
    p = client.post("/api/preview",
                    json={"scenario_id": "profit15", "side": "sell", "qty": 10}).json()["preview"]
    # 계약 §5.2-b 골든값 — 실현손익 +59,011(양수 부호)
    assert p["net_proceeds"] == 459011
    assert p["realized_pnl"] == 59011
    assert p["realized_pnl"] > 0
    assert p["remaining_weight_pct"] == 9.4
    assert p["settlement_date"] == "2026-07-21"

    # loss8 10주와 대금·비용·수령액 동일, 실현손익 부호만 반대(계산의 방향 중립)
    l = client.post("/api/preview",
                    json={"scenario_id": "loss8", "side": "sell", "qty": 10}).json()["preview"]
    assert (l["gross_amount"], l["fee"], l["tax"], l["net_proceeds"]) == \
        (p["gross_amount"], p["fee"], p["tax"], p["net_proceeds"])
    assert l["realized_pnl"] < 0 < p["realized_pnl"]

    st = client.post("/api/settle",
                     json={"preview": p, "confirmed_qty": 10}).json()["settlement"]
    assert st["is_mock"] is True and st["realized_pnl"] == 59011
