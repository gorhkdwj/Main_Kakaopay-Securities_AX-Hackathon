"""통합 테스트 I-05·I-06 + 안전 지표 카운터 정확성.

I-05: 스냅샷(manifest) 없음 — 응답 어디에도 스냅샷 유래 as_of 배지 형식
      ("… 종가 기준", 계약 §9)이 없고 "교육용 가상 데이터" 배지만 쓴다.
I-06: fixture에서 공시 필드 제거 → 해당 카드 '확인 불가'/생략 —
      대체값을 만들어 채우지 않는다(계약 §8).
카운터: guard 차단·정적 텍스트 검사·렌더 사실 수의 세션 누적 집계(계약 §10).
"""

from __future__ import annotations

import json


# ---------------------------------------------------------------------------
# I-05 · 스냅샷 없음 — 가상 배지만
# ---------------------------------------------------------------------------

def test_i05_no_snapshot_asof_only_synthetic_badge(client):
    for sid in ("loss8", "profit15", "first_buy"):
        res = client.get(f"/api/scenario/{sid}")
        raw = res.text
        # 실동결 스냅샷 배지 형식(계약 §9 "YYYY-MM-DD HH:mm KST 종가 기준")이 없다
        assert "종가 기준" not in raw
        data = res.json()
        assert data["meta"]["is_synthetic"] is True
        assert data["meta"]["badge_text"].startswith("교육용 가상 데이터")
        assert "가상 기준시각" in data["meta"]["badge_text"]

    # 화면 골격도 동일 — 기본 배지에 스냅샷 문구가 없다
    html = client.get("/").text
    assert "교육용 가상 데이터" in html
    assert "종가 기준" not in html


# ---------------------------------------------------------------------------
# I-06 · 공시 필드 없는 변형 fixture — 카드 생략·대체값 생성 금지
# ---------------------------------------------------------------------------

def test_i06_missing_disclosures_card_omitted(make_variant_client):
    c = make_variant_client("loss8", lambda fx: fx.pop("disclosures"))
    data = c.get("/api/scenario/loss8").json()
    assert data["ok"] is True

    # 상태 표기: '확인된 공시 없음'(계약 §8) + unavailable 목록 — scenario 응답(meta)
    assert data["meta"]["disclosures_state"] == "확인된 공시 없음"
    assert "disclosures" in data["meta"]["unavailable"]

    # 브리핑은 별도 엔드포인트(D-0718-0355): 공시 카드 없이 시세 카드만
    bdata = c.get("/api/briefing/loss8").json()
    facts = bdata["briefing"]["facts"]
    assert len(facts) == 1
    assert facts[0]["source_id"] == "DEMO-SRC-102"

    # 대체값 생성 금지 — 원본 공시 문구가 브리핑 어디에도 없다
    dumped = json.dumps(bdata, ensure_ascii=False)
    assert "3분기 잠정 영업이익" not in dumped
    assert "DEMO-SRC-101" not in dumped

    # 생략은 차단이 아니다 — 카운터 0 유지
    assert bdata["safety"]["no_source"] == 0
    assert bdata["safety"]["asof_missing"] == 0

    # 해석의 basis도 비워진다(없는 출처를 지어내지 않음)
    assert all(i["basis"] == [] for i in bdata["briefing"]["interpretations"])


def test_i06_disclosure_without_source_is_blocked_and_counted(make_variant_client):
    """공시가 있으나 출처·기준시각이 없으면 — 조립은 그대로, guard가 차단하고 집계한다."""
    def mutate(fx):
        fx["disclosures"][0].pop("source_id")
        fx["disclosures"][0].pop("published_at")

    c = make_variant_client("loss8", mutate)
    bdata = c.get("/api/briefing/loss8").json()  # 브리핑 별도 엔드포인트(D-0718-0355)

    assert bdata["briefing"]["policy_result"] == "blocked_partial"
    cats = {b["category"] for b in bdata["guard"]["record"]["blocked"]}
    assert cats == {"no_source", "asof_missing"}

    # 렌더 허용 사실은 IR 일정 공시(103)와 시세 카드(102) — 위반 블록만 차단(계약 §6)
    facts = bdata["briefing"]["facts"]
    assert [f["source_id"] for f in facts] == ["DEMO-SRC-103", "DEMO-SRC-102"]
    # 차단된 공시 텍스트는 렌더 대상(briefing)에 없다
    assert "3분기 잠정 영업이익" not in json.dumps(bdata["briefing"], ensure_ascii=False)

    # 세션 카운터 반영(계약 §10)
    assert bdata["safety"]["no_source"] == 1
    assert bdata["safety"]["asof_missing"] == 1
    assert bdata["safety"]["forbidden"] == 0
    assert bdata["safety"]["facts_rendered"] == 2


# ---------------------------------------------------------------------------
# 안전 지표 카운터 — 세션 누적 집계 정확성
# ---------------------------------------------------------------------------

def test_safety_counters_accumulate_per_session(client):
    zero = client.get("/api/safety").json()["safety"]
    for key in ("responses_checked", "facts_rendered", "static_texts_checked",
                "no_source", "forbidden", "asof_missing"):
        assert zero[key] == 0, f"초기 카운터가 0이 아닙니다: {key}"

    # 시나리오 로드는 정적 텍스트(community_buzz)만 검사 — 브리핑 카운터는 아직 0
    # (브리핑은 별도 엔드포인트에서 생성 — D-0718-0355)
    client.get("/api/scenario/loss8")
    s0 = client.get("/api/safety").json()["safety"]
    assert s0["responses_checked"] == 0
    assert s0["facts_rendered"] == 0
    assert s0["static_texts_checked"] == 1  # community_buzz.note

    # 브리핑 생성: 응답 1건 · 사실 3건(공시 2 + 시세 — D-0718-0107 확장)
    client.get("/api/briefing/loss8")
    s1 = client.get("/api/safety").json()["safety"]
    assert s1["responses_checked"] == 1
    assert s1["facts_rendered"] == 3
    assert s1["static_texts_checked"] == 1  # 브리핑은 정적 텍스트 검사 안 함(불변)
    assert s1["no_source"] == 0 and s1["forbidden"] == 0 and s1["asof_missing"] == 0

    # first_buy 로드: +정적 2(buzz + 자동완성 초안) / 브리핑: +응답 1 · +사실 3
    client.get("/api/scenario/first_buy")
    client.get("/api/briefing/first_buy")
    s2 = client.get("/api/safety").json()["safety"]
    assert s2["responses_checked"] == 2
    assert s2["facts_rendered"] == 6
    assert s2["static_texts_checked"] == 3

    # 미리보기도 guard를 거친다(응답 수만 증가 — 사실 렌더 없음)
    client.post("/api/preview", json={"scenario_id": "loss8", "side": "sell", "qty": 10})
    s3 = client.get("/api/safety").json()["safety"]
    assert s3["responses_checked"] == 3
    assert s3["facts_rendered"] == 6
    assert s3["no_source"] == 0 and s3["forbidden"] == 0 and s3["asof_missing"] == 0

    # 오류 미리보기는 guard 응답 자체가 없다 — 카운터 불변(계산 기록 미생성)
    client.post("/api/preview", json={"scenario_id": "loss8", "side": "sell", "qty": 0})
    s4 = client.get("/api/safety").json()["safety"]
    assert s4["responses_checked"] == 3


def test_rendered_briefing_texts_pass_lexicon(client):
    """렌더 대상 텍스트 블록 전수가 금지 사전을 통과한다(정적 문구 자동 검증 — 스펙 §5).

    검사는 guard와 동일하게 '텍스트 블록 단위'다 — 서로 다른 블록의 단어를
    이어 붙여 오탐을 만들지 않는다(계약 §7 복합 규칙의 판정 단위).
    """
    from src.policy.lexicon import find_violations

    for sid in ("loss8", "profit15", "first_buy"):
        data = client.get(f"/api/scenario/{sid}").json()
        b = client.get(f"/api/briefing/{sid}").json()["briefing"]  # 별도 엔드포인트
        blocks = [f["text"] for f in b["facts"]]
        blocks += [i["text"] for i in b["interpretations"]]
        blocks += list(b["unknowns"]) + list(b["next_questions"])
        if data["community_buzz"]:
            blocks.append(data["community_buzz"]["note"])
        if data["diary_draft"]:
            blocks.append(data["diary_draft"])
        if data["meta"]["disclosures_state"]:
            blocks.append(data["meta"]["disclosures_state"])
        blocks.append(data["meta"]["badge_text"])

        for text in blocks:
            assert find_violations(text) == [], f"{sid} 렌더 블록이 금지 사전에 걸립니다: {text}"

        # '원인' 단어 미사용('관련 사실'만 — 헌법 §14)
        dumped = json.dumps(data, ensure_ascii=False)
        assert "원인" not in dumped
