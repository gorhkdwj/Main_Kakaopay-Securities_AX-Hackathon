"""통합 테스트 I-02 — scenario_first_buy(백업 K2 · 첫 구매 검토).

확인 항목(검증 계획 §3·지시서):
- plan null → 질문 초안 3문(목표 기간·감수 손실·재검토 조건)
- 진입 맥락(discovery_context) 노출 + 투자 일지 자동완성 초안 문자열
  (행동 사실만 — 감정·판단 어휘 무첨가, guard 사전 통과)
- buy_preview 8주/10주 골든값(계약 §5.2-c) — 10주 집중도 경고 46.0%(차단 아님)
- 22주 예수금 초과 오류(계산·체결 기록 미생성)
"""

from __future__ import annotations

import json

from src.policy.lexicon import find_violations


def test_i02_first_buy_scenario_payload(client):
    data = client.get("/api/scenario/first_buy").json()
    assert data["ok"] is True

    # 계획 없음 + 보유 없음(첫 거래 정합) — hold 없음, past_records 0건
    assert data["meta"]["plan"] is None
    assert data["meta"]["side"] == "buy"
    assert data["meta"]["holding"]["qty"] == 0
    assert data["meta"]["cash"] == 1000000
    assert data["hold"] is None
    assert data["past_records"] == []

    # 질문 초안 3문(목표 기간·감수 손실·재검토 조건)
    qs = data["briefing"]["next_questions"]
    assert len(qs) == 3
    assert any("목표 보유 기간" in q for q in qs)
    assert any("감수할 수 있는 손실" in q for q in qs)
    assert any("다시 검토" in q for q in qs)

    # 진입 맥락(discovery_context)
    dc = data["discovery_context"]
    assert dc["path"] == "탐색하기 > 기업가치로 탐색하기"
    assert dc["theme"] == "꾸준히 매출 좋은 주식"
    assert dc["criteria"] == "최근 3년 매출 20% 이상·4년 연속 성장"
    assert dc["entered_at"] == "2026-07-17 15:10 KST"

    # 사실 카드 소스(다온소재 = 3xx — 실적·IR 일정·시세)
    assert [f["source_id"] for f in data["briefing"]["facts"]] == \
        ["DEMO-SRC-301", "DEMO-SRC-303", "DEMO-SRC-302"]
    assert data["guard"]["record"]["blocked"] == []


def test_i02_diary_draft_facts_only(client):
    data = client.get("/api/scenario/first_buy").json()
    draft = data["diary_draft"]
    assert isinstance(draft, str) and draft

    # 행동 사실(경로·테마·기준·일시)만으로 조립됐다
    assert "탐색하기 > 기업가치로 탐색하기" in draft
    assert "꾸준히 매출 좋은 주식" in draft
    assert "최근 3년 매출 20% 이상·4년 연속 성장" in draft
    assert "2026-07-17 15:10 KST" in draft
    assert "구매를 검토함" in draft

    # 시스템이 감정·판단 어휘를 창작하지 않는다(계약 §9)
    for word in ("기대", "불안", "확신", "유망", "저평가", "안전", "추천",
                 "오를", "상승할", "좋아 보"):
        assert word not in draft, f"초안에 감정·판단 어휘가 섞였습니다: {word}"

    # 초안 문자열도 guard 사전(lexicon)을 통과한다
    assert find_violations(draft) == []


def test_i02_buy_preview_goldens(client):
    # 8주 — 경고 없음(계약 §5.2-c)
    p8 = client.post("/api/preview",
                     json={"scenario_id": "first_buy", "side": "buy", "qty": 8}).json()["preview"]
    assert p8["gross_amount"] == 368000
    assert p8["fee"] == 55
    assert p8["tax"] == 0  # 구매는 거래세·농특세 없음
    assert p8["total_cost"] == 368055
    assert p8["remaining_cash"] == 631945
    assert p8["weight_after_pct"] == 36.8
    assert p8["concentration_warning"] is False
    assert p8["settlement_date"] == "2026-07-21"

    # 10주 — 집중도 경고 46.0%(차단 아님 — 정보 표시)
    p10 = client.post("/api/preview",
                      json={"scenario_id": "first_buy", "side": "buy", "qty": 10}).json()["preview"]
    assert p10["total_cost"] == 460069
    assert p10["remaining_cash"] == 539931
    assert p10["weight_after_pct"] == 46.0
    assert p10["concentration_warning"] is True

    # 경고여도 모의 체결은 가능해야 한다(차단 아님)
    st = client.post("/api/settle",
                     json={"preview": p10, "confirmed_qty": 10}).json()["settlement"]
    assert st["is_mock"] is True and st["side"] == "buy"
    assert st["total_cost"] == 460069


def test_i02_buy_over_cash_is_error_without_calculation(client):
    # 22주 — 총 결제예정액 1,012,151 > 예수금 1,000,000 → 오류(계약 §5.2-c·§5.3)
    r = client.post("/api/preview",
                    json={"scenario_id": "first_buy", "side": "buy", "qty": 22})
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "InsufficientCashError"
    assert "예수금" in body["error"]["message"]
    # 계산 결과·calculation_id가 생성되지 않는다
    dumped = json.dumps(body, ensure_ascii=False)
    assert "preview" not in body
    assert "CALC-" not in dumped
