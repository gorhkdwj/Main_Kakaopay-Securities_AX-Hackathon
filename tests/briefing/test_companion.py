"""src/briefing/companion.py 단위 검증 — 폴백 사슬·guard 관문·캐시 매칭.

기준: 계약 §6 "동반자 대화" 항목. 네트워크 0회 — live 경로는 llm_call 주입으로만
검증한다(가짜 호출자). 원본 fixture·캐시는 수정하지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.briefing.companion import (
    DEGRADED_REPLY_TEXT,
    MARKET_CONTEXT_SOURCE_ID,
    SAFE_REPLY_FALLBACK,
    find_cached_answer,
    find_similar_answer,
    generate_companion_reply,
    load_companion_cache,
    load_market_context,
    normalize_question,
    sanitize_companion_response,
)
from src.briefing.llm import fixture_fingerprint

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"


def load_fx(scenario_id: str) -> dict:
    with open(FIXTURES_DIR / f"scenario_{scenario_id}.json", encoding="utf-8") as fp:
        return json.load(fp)


def contract_response(**over) -> dict:
    base = {
        "reply_text": "정리한 카드를 봐 주세요.",
        "facts": [],
        "interpretations": [],
        "unknowns": ["다음 거래일의 가격 방향은 알 수 없어요."],
        "user_inputs": {"quantity": None, "intent": None, "situation": "loss8"},
        "calculation_id": None,
        "policy_result": "information_only",
        "next_questions": [],
    }
    base.update(over)
    return base


def write_mini_cache(tmp_path: Path, scenario_id: str, fx: dict) -> Path:
    entry = {
        "qa_id": "mini",
        "chip": "테스트 질문",
        "question": "테스트 질문이에요?",
        "match_questions": ["테스트 질문이에요"],
        "keywords": ["테스트", "질문"],
        "calculations": [],
        "derived": {},
        "allowed_extra_numbers": [],
        "response": contract_response(
            reply_text="준비된 답변이에요 — 카드를 봐 주세요.",
            user_inputs={"quantity": None, "intent": None, "situation": scenario_id},
        ),
    }
    data = {
        "scenario_id": scenario_id,
        "fixture_sha256": fixture_fingerprint(fx),
        "qa": [entry],
    }
    path = tmp_path / f"{scenario_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# 캐시 로드·매칭
# ---------------------------------------------------------------------------

def test_normalize_question_strips_punctuation_and_space():
    assert normalize_question("지금 사도 괜찮을까?") == "지금사도괜찮을까"
    assert normalize_question("  나눠 살까, 한 번에 살까? ") == "나눠살까한번에살까"
    assert normalize_question(None) == ""


def test_cache_exact_and_similar_matching(tmp_path):
    fx = load_fx("loss8")
    cache_dir = write_mini_cache(tmp_path, "loss8", fx)
    qa, reason = load_companion_cache("loss8", fx, cache_dir)
    assert reason.startswith("cache_loaded")
    assert find_cached_answer(qa, "테스트 질문이에요?!") is not None   # 문장부호 변형 흡수
    assert find_cached_answer(qa, "전혀 다른 질문") is None
    assert find_similar_answer(qa, "테스트로 드리는 질문이 있어요") is not None  # 키워드 2개
    assert find_similar_answer(qa, "테스트만 포함") is None            # 1개 — 미달


def test_cache_stale_fingerprint_rejected(tmp_path):
    fx = load_fx("loss8")
    cache_dir = write_mini_cache(tmp_path, "loss8", fx)
    fx_mut = dict(fx)
    fx_mut["cash"] = 777_777  # 판단 재료 변경 → 지문 불일치
    qa, reason = load_companion_cache("loss8", fx_mut, cache_dir)
    assert qa is None
    assert reason == "cache_stale_fingerprint"


def test_real_cache_file_matches_current_fixture():
    """동결 캐시가 현재 fixture 지문과 일치한다(스테일이면 데모에서 강등돼 버린다)."""
    fx = load_fx("real_005930")
    qa, reason = load_companion_cache("real_005930", fx)
    assert qa is not None, f"캐시 로드 실패: {reason}"
    assert len(qa) == 4  # 목업 4문답


# ---------------------------------------------------------------------------
# 폴백 사슬(generate_companion_reply)
# ---------------------------------------------------------------------------

def test_fallback_chain_cache_exact_first(tmp_path):
    fx = load_fx("loss8")
    cache_dir = write_mini_cache(tmp_path, "loss8", fx)
    response, source, attempts, entry = generate_companion_reply(
        fx, "loss8", "테스트 질문이에요?", mode="static", cache_dir=cache_dir)
    assert source == "cache"
    assert entry["qa_id"] == "mini"
    assert response["reply_text"].startswith("준비된 답변")


def test_fallback_chain_live_with_fake_llm(tmp_path):
    fx = load_fx("loss8")
    fake = contract_response(reply_text="자료로 정리했어요.")

    def llm_call(messages):
        # 프롬프트 격리 확인 — 자료는 <data> 블록 안에만 있다
        user = messages[-1]["content"]
        assert "<data>" in user and "</data>" in user
        return json.dumps(fake, ensure_ascii=False)

    response, source, attempts, entry = generate_companion_reply(
        fx, "loss8", "자유 질문이에요", mode="auto",
        cache_dir=tmp_path, llm_call=llm_call)
    assert source == "live"
    assert entry is None
    assert "live_ok" in attempts


def test_fallback_chain_live_failure_then_similar_cache(tmp_path):
    fx = load_fx("loss8")
    cache_dir = write_mini_cache(tmp_path, "loss8", fx)

    def broken(messages):
        raise RuntimeError("타임아웃 모사")

    response, source, attempts, entry = generate_companion_reply(
        fx, "loss8", "테스트 관련 질문 있어요", mode="auto",
        cache_dir=cache_dir, llm_call=broken)
    assert source == "cache"
    assert any(a.startswith("live_failed") for a in attempts)
    assert any(a.startswith("cache_similar") for a in attempts)


def test_fallback_chain_degrades_when_nothing_matches(tmp_path):
    fx = load_fx("loss8")
    response, source, attempts, entry = generate_companion_reply(
        fx, "loss8", "팔까요?", mode="static", cache_dir=tmp_path)
    assert response is None
    assert source == "degraded"
    assert "degraded" in attempts


# ---------------------------------------------------------------------------
# guard 관문(sanitize_companion_response)
# ---------------------------------------------------------------------------

def test_sanitize_blocks_direction_reply_and_fake_source():
    """방향 결론 reply_text + 지어낸 출처 fact → 전부 차단·안전 문구 강등."""
    bad = contract_response(
        reply_text="지금 매수하세요",
        facts=[{"text": "이 종목은 반등할 겁니다",
                "source_id": "YF-SRC-999", "as_of": "2026-07-16"}],
        unknowns=[],
    )
    sanitized, record, reply_blocked = sanitize_companion_response(
        bad, allowed_numbers=set(), known_source_ids={"YF-SRC-001"})
    assert reply_blocked is True
    assert sanitized["reply_text"] == DEGRADED_REPLY_TEXT  # 카드도 전멸 → 강등 문구
    assert sanitized["facts"] == []
    assert record["counters"]["forbidden"] >= 1   # 방향 결론(reply_text)
    assert record["counters"]["no_source"] >= 1   # 실재하지 않는 출처(SRC-EXIST)
    assert sanitized["policy_result"] == "blocked_partial"


def test_sanitize_blocks_unverified_numbers_in_reply():
    """허용 숫자 집합 밖 숫자를 담은 reply_text는 차단된다(LLM 산수 금지)."""
    bad = contract_response(reply_text="수수료는 999,999원이에요.")
    sanitized, record, reply_blocked = sanitize_companion_response(
        bad, allowed_numbers={1}, known_source_ids=set())
    assert reply_blocked is True
    assert sanitized["reply_text"] == SAFE_REPLY_FALLBACK  # unknowns 카드는 생존
    assert any(b["rule_id"] == "NUM-01" and b["field"] == "reply_text"
               for b in record["blocked"])


def test_sanitize_passes_clean_response():
    ok = contract_response(reply_text="결제일은 D+2 영업일이에요.")  # 2는 지표 상수 허용
    sanitized, record, reply_blocked = sanitize_companion_response(
        ok, allowed_numbers=set(), known_source_ids=set())
    assert reply_blocked is False
    assert sanitized["reply_text"] == ok["reply_text"]
    assert record["blocked"] == []
    assert sanitized["policy_result"] == "information_only"


# ---------------------------------------------------------------------------
# market_context 로드 — kospi200 제외(W4 주의 ①)
# ---------------------------------------------------------------------------

def test_market_context_excludes_kospi200():
    ctx = load_market_context()
    assert ctx is not None, "market_context 스냅샷이 있어야 한다(동결 완료 상태)"
    assert "kospi200" not in ctx["items"]
    assert ctx["source_id"] == MARKET_CONTEXT_SOURCE_ID
    assert "kospi" in ctx["items"]


def test_market_context_missing_dir_returns_none(tmp_path):
    assert load_market_context(tmp_path) is None
