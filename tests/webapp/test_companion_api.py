"""POST /api/companion/chat · GET /api/companion/chips — 동반자 대화 API 검증.

기준: 계약 §6 "동반자 대화(companion chat)" · §9 "동반자 패널" ·
구현제안(docs/plans/2026-07-18_동반자챗봇_구현제안.md) §2~§5.

검증 축:
- 칩 질문 → 캐시 응답(계약 필드·source_id/as_of 전수·guard 무차단)
- 자유 질문 → 키 없는 환경에서 폴백(캐시 유사 질문 / 안전 강등 문구)
- 권유 유도 질문("팔까요?")에 방향 결론 없이 응답
- 수량 없는 질문 처리(오류 아님) · 수량 있는 문답(Q4)의 계산 연결
- 안전 규칙: 응답 어디에도 주문 실행 마커·"체결하기" 문구 없음
- 감사로그(companion_events.jsonl) 기록 · 안전 지표 합산
"""

from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from src.briefing.companion import DEGRADED_REPLY_TEXT
from src.policy.lexicon import find_violations
from src.webapp.app import create_app

CHIP_TIMING = "지금 사도 괜찮을까?"
CHIP_SPLIT = "나눠 살까, 한 번에 살까?"
CHIP_HANDOFF = "오늘은 3주만 먼저 해볼게요"

CALC_ID_RE = re.compile(r"^CALC-\d{8}-\d{6}-\d+$")


def post_chat(client, question, scenario_id="real_005930", **extra):
    payload = {"scenario_id": scenario_id, "question": question,
               "step": 2, "flow_side": "buy", "history": []}
    payload.update(extra)
    return client.post("/api/companion/chat", json=payload)


# ---------------------------------------------------------------------------
# 캐시 경로(빠른 칩) — 계약 필드·출처·guard
# ---------------------------------------------------------------------------

def test_chip_question_served_from_cache(client):
    res = post_chat(client, CHIP_TIMING)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["source"] == "cache"
    assert body["source_label"] == "준비된 문답(캐시)"

    reply = body["reply"]
    # 계약 §6 필드 전부 존재
    for field in ("reply_text", "facts", "interpretations", "unknowns",
                  "user_inputs", "calculation_id", "policy_result",
                  "next_questions"):
        assert field in reply, f"계약 필드 누락: {field}"
    # 모든 사실에 source_id·as_of(계약 §6 — guard 강제)
    assert reply["facts"], "칩 문답에 사실 카드가 있어야 한다"
    for fact in reply["facts"]:
        assert fact["source_id"], fact
        assert fact["as_of"], fact
    # 양면 해석 병기
    stances = {i["stance"] for i in reply["interpretations"]}
    assert {"긍정 시각", "부정 시각"} <= stances
    assert reply["unknowns"], "모름 항목이 있어야 한다"
    assert reply["next_questions"], "되묻는 질문이 있어야 한다"
    # guard 무차단(캐시는 생성 시 검증 통과분만 저장)
    assert body["guard"]["record"]["blocked"] == []
    assert reply["policy_result"] == "information_only"


def test_chip_asof_labels_are_item_specific(client):
    """종목(07-16 종가)과 시장 지표(별도 수집)의 기준시각을 항목별로 분리 표기한다."""
    res = post_chat(client, CHIP_TIMING)
    body = res.json()
    assert body["asof"]["stock"].startswith("2026-07-16 종가")
    assert body["asof"]["market"] is not None
    assert body["asof"]["market"] != body["asof"]["stock"]
    assert body["asof"]["delay_note"]  # 지연 고지 상시(계약 §9 동반자 패널)
    # 시장 지표 사실 카드의 as_of는 종목 as_of와 다르다(같은 날 오독 방지)
    market_facts = [f for f in body["reply"]["facts"]
                    if f["source_id"] == "YF-SRC-006"]
    assert market_facts, "시장 지표 사실 카드가 있어야 한다"
    for fact in market_facts:
        assert fact["as_of"] != body["asof"]["stock"]


def test_split_chip_uses_engine_numbers(client):
    """분할 비교는 엔진 buy_preview 재사용 — 계산 ID 연결 + 과거 사실 병기 문구."""
    res = post_chat(client, CHIP_SPLIT)
    body = res.json()
    assert body["source"] == "cache"
    reply = body["reply"]
    assert CALC_ID_RE.match(reply["calculation_id"] or "")
    assert "총 결제예정액" in reply["reply_text"]
    # 백테스트류 문장은 과거 사실 + "미래에도 그렇다는 뜻 아님" 병기(계약 §6)
    joined = json.dumps(reply, ensure_ascii=False)
    assert "미래에도 그렇다는 뜻이 아니에요" in joined
    assert body["guard"]["record"]["blocked"] == []


def test_handoff_chip_has_quantity_and_notices(client):
    """Q4(결정 핸드오프): 수량·계산 연결 + 구매 4종 고지 + 실행 버튼 부재 선언."""
    res = post_chat(client, CHIP_HANDOFF)
    body = res.json()
    assert body["source"] == "cache"
    reply = body["reply"]
    assert reply["user_inputs"]["quantity"] == 3
    assert CALC_ID_RE.match(reply["calculation_id"] or "")
    text = reply["reply_text"]
    assert "체결 후에는 취소할 수 없어요" in text          # 비가역 고지(§9)
    assert "세금이 없어요" in text                        # 구매는 세금 없음 고지
    assert "실행 버튼을 갖지 않아요" in text              # 핸드오프 선언(목업 프레임)
    assert "모의 주문" in text and "투자 일지" in text     # 서비스 내 핸드오프


# ---------------------------------------------------------------------------
# 폴백 사슬 — live 없음(키 없음/모드 차단) 환경
# ---------------------------------------------------------------------------

def test_solicitation_question_answers_without_direction(client):
    """권유 유도 질문("팔까요?")에도 방향 결론 없이 안전하게 응답한다."""
    res = post_chat(client, "팔까요?")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    # static 모드 + 캐시 미매칭 → 안전 강등(계약 §6 폴백 사슬 최종 단계)
    assert body["source"] == "degraded"
    reply = body["reply"]
    assert reply["reply_text"] == DEGRADED_REPLY_TEXT
    assert reply["facts"] == []
    # 방향 결론·금지 표현 0(모든 렌더 텍스트)
    raw = res.text
    for phrase in ("파세요", "사세요", "매도하세요", "매수하세요"):
        assert phrase not in raw
    assert find_violations(reply["reply_text"]) == []


def test_similar_free_question_falls_back_to_cache(client):
    """live 불가 시 캐시 유사 질문 폴백(키워드 매칭 — 계약 §6)."""
    res = post_chat(client, "요즘 왜 이렇게 떨어진 건가요?")
    body = res.json()
    assert body["source"] == "cache"
    # 하락 재프레임 문답 — "왜"를 확정하지 않는 안전 프레임 재사용(목업)
    assert "확정해 말씀드릴 수는 없어요" in body["reply"]["reply_text"]


def test_question_without_quantity_is_not_an_error(client):
    """수량이 없는 질문도 정상 처리한다(수량 검사는 계산 존재 시에만)."""
    res = post_chat(client, CHIP_TIMING)
    body = res.json()
    reply = body["reply"]
    assert reply["user_inputs"]["quantity"] is None
    assert reply["policy_result"] == "information_only"


def test_synthetic_scenario_works_without_market_context(client):
    """가상 시나리오(loss8)에서도 동작 — 시장 컨텍스트 미주입 + 안전 강등."""
    res = post_chat(client, "지금 사도 괜찮을까?", scenario_id="loss8")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["source"] == "degraded"        # loss8 캐시 없음 + live 차단
    assert body["asof"]["market"] is None      # 실지표 혼용 금지(계약 §1)
    assert find_violations(body["reply"]["reply_text"]) == []


def test_stale_cache_fingerprint_degrades(make_variant_client):
    """fixture 지문 불일치(스테일 캐시) → 캐시 미사용·안전 강등(계약 §8 철학)."""
    client = make_variant_client(
        "real_005930", lambda fx: fx.update(cash=2_000_000))
    res = post_chat(client, CHIP_TIMING)
    body = res.json()
    assert body["source"] == "degraded"
    assert body["reply"]["reply_text"] == DEGRADED_REPLY_TEXT


# ---------------------------------------------------------------------------
# 입력 검증·오류 경로
# ---------------------------------------------------------------------------

def test_unknown_scenario_returns_404(client):
    res = post_chat(client, CHIP_TIMING, scenario_id="ghost")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_empty_question_returns_400(client):
    res = client.post("/api/companion/chat",
                      json={"scenario_id": "real_005930", "question": "  "})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "empty_question"


# ---------------------------------------------------------------------------
# 안전 규칙 — 주문 실행 마커·문구 0(계약 §9 동반자 패널)
# ---------------------------------------------------------------------------

def test_no_order_execution_markers_in_any_companion_response(client):
    questions = [CHIP_TIMING, CHIP_SPLIT, CHIP_HANDOFF,
                 "왜 이렇게 떨어진 거예요?", "팔까요?"]
    for q in questions:
        raw = post_chat(client, q).text
        assert "체결하기" not in raw, q
        assert "order-execute" not in raw, q


def test_companion_cache_file_has_no_execution_markers():
    """정적 캐시 파일 자체에도 실행 마커·금지 표현이 없어야 한다(§9)."""
    from pathlib import Path
    project_root = Path(__file__).resolve().parents[2]
    path = project_root / "data" / "fixtures" / "companion_cache" / "real_005930.json"
    text = path.read_text(encoding="utf-8")
    assert "체결하기" not in text
    assert "order-execute" not in text
    assert "원인" not in text  # '원인' 단어 금지(불확정 인과 단정 방지 규약)
    data = json.loads(text)
    # 모든 렌더 대상 텍스트가 금지 사전을 통과한다
    for entry in data["qa"]:
        resp = entry["response"]
        texts = [resp["reply_text"]]
        texts += [f["text"] for f in resp["facts"]]
        texts += [i["text"] for i in resp["interpretations"]]
        texts += resp["unknowns"] + resp["next_questions"]
        for t in texts:
            assert find_violations(t) == [], f"{entry['qa_id']}: {t}"


# ---------------------------------------------------------------------------
# 칩 목록 · 감사로그 · 안전 지표 합산
# ---------------------------------------------------------------------------

def test_chips_endpoint_lists_prepared_questions(client):
    res = client.get("/api/companion/chips/real_005930")
    body = res.json()
    assert body["ok"] is True
    assert len(body["chips"]) == 4
    for chip in body["chips"]:
        assert chip["label"] and chip["question"]

    empty = client.get("/api/companion/chips/loss8").json()
    assert empty["chips"] == []
    assert empty["cache_state"] == "cache_missing"


def test_companion_audit_log_written(records_dir, tmp_path):
    client = TestClient(create_app(records_dir=records_dir,
                                   briefing_mode="static",
                                   audit_dir=tmp_path / "audit"))
    post_chat(client, CHIP_TIMING)
    post_chat(client, "팔까요?")
    log = tmp_path / "audit" / "companion_events.jsonl"
    assert log.is_file()
    lines = [json.loads(line) for line in
             log.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["source"] == "cache"
    assert lines[1]["source"] == "degraded"
    assert "attempts" in lines[0]  # 폴백 시도 이력 — 실패 은폐 금지


def test_companion_counts_into_session_safety(client):
    before = client.get("/api/safety").json()["safety"]
    body = post_chat(client, CHIP_TIMING).json()
    after = body["safety"]
    assert after["responses_checked"] == before["responses_checked"] + 1
    assert after["facts_rendered"] >= before["facts_rendered"] + 1
    # 캐시 문답은 차단 0 — 금지 표현·무출처 카운터 증가 없음
    assert after["forbidden"] == before["forbidden"]
    assert after["no_source"] == before["no_source"]
