"""guard S5 확장 검증 — facts 숫자 대사(NUM-01)·source_id 실재 검사(SRC-EXIST).

계약 §6의 두 규칙("facts[].text 숫자는 calculation_id 결과 또는 fixture
원천값과 일치" / "source_id는 §2 체계에 실재")의 구현 검증이다.
S3 v1 호환: 두 파라미터를 주지 않으면 기존 동작과 동일해야 한다.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from src.policy.guard import (
    NUMBER_CONTEXT_WHITELIST,
    check_response,
    collect_allowed_numbers,
)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures"


def load_fixture(scenario_id: str) -> dict:
    with open(FIXTURES_DIR / f"scenario_{scenario_id}.json", encoding="utf-8") as fp:
        return json.load(fp)


def make_response(facts: list) -> dict:
    return {
        "facts": facts,
        "interpretations": [],
        "unknowns": ["다음 실적 발표에서 확인됩니다."],
        "user_inputs": {"quantity": None, "intent": None, "situation": "loss8"},
        "calculation_id": None,
        "policy_result": "information_only",
        "next_questions": [],
    }


FACT_OK = {
    "text": "종가 46,000원 · 전일 대비 -8.0% · 거래량 576,000주(20일 평균의 3.2배)",
    "source_id": "DEMO-SRC-102",
    "as_of": "2026-07-17 15:30 KST",
}


# ── collect_allowed_numbers ────────────────────────────────────────────

def test_collect_extracts_values_and_text_tokens():
    fx = load_fixture("loss8")
    allowed = collect_allowed_numbers(fx)
    # 수치 필드(절대값) — close·change_pct·ratio·plan.max_loss_pct
    assert Decimal("46000") in allowed
    assert Decimal("8.0") in allowed
    assert Decimal("3.2") in allowed
    assert Decimal("15") in allowed
    # 문자열 필드 안 숫자(공시 텍스트 "128억"·"-32%" — fixture 원천값 인용 허용)
    assert Decimal("128") in allowed
    assert Decimal("32") in allowed


def test_collect_ignores_bool_and_none_sources():
    allowed = collect_allowed_numbers({"flag": True}, None, {"n": 7})
    assert Decimal(1) not in allowed  # True가 1로 새지 않는다
    assert Decimal(7) in allowed


def test_whitelist_is_not_baked_into_collect():
    # 화이트리스트(2·20)는 check_response 시점 합산 — collect 결과에는 없다
    allowed = collect_allowed_numbers({"x": 5})
    assert NUMBER_CONTEXT_WHITELIST.isdisjoint(allowed)


# ── NUM-01: facts 숫자 대사 ────────────────────────────────────────────

def test_fixture_sourced_numbers_pass():
    fx = load_fixture("loss8")
    sanitized, record = check_response(
        make_response([dict(FACT_OK)]),
        allowed_numbers=collect_allowed_numbers(fx),
    )
    assert record["blocked"] == []
    assert len(sanitized["facts"]) == 1
    assert sanitized["policy_result"] == "information_only"


def test_invented_number_blocks_fact():
    fx = load_fixture("loss8")
    fake = dict(FACT_OK, text="종가 47,500원으로 마감했어요")  # fixture에 없는 숫자
    sanitized, record = check_response(
        make_response([fake]),
        allowed_numbers=collect_allowed_numbers(fx),
    )
    assert sanitized["facts"] == []
    assert sanitized["policy_result"] == "blocked_partial"
    entry = record["blocked"][0]
    assert entry["rule_id"] == "NUM-01"
    assert entry["category"] == "number_unverified"
    assert "47,500" in entry["excerpt"]
    # §10 3지표 카운터에는 미집계(blocked에만 기록)
    assert record["counters"] == {"no_source": 0, "forbidden": 0, "asof_missing": 0}


def test_whitelist_constants_pass_without_fixture_backing():
    # 2(D+2)·20(20일 평균)은 지표 정의 상수 — fixture에 값이 없어도 허용
    fact = dict(FACT_OK, text="결제는 D+2 영업일 뒤예요 · 20일 평균과 비교해요")
    sanitized, record = check_response(
        make_response([fact]), allowed_numbers=set(),
    )
    assert record["blocked"] == []
    assert len(sanitized["facts"]) == 1


def test_calculation_numbers_pass_when_included():
    fx = load_fixture("loss8")
    calc_like = {"receive_amount": 459011, "realized_pnl": -40989}
    fact = dict(FACT_OK, text="예상 수령액은 459,011원이에요")
    _, record = check_response(
        make_response([fact]),
        allowed_numbers=collect_allowed_numbers(fx, calc_like),
    )
    assert record["blocked"] == []


def test_number_check_skipped_without_allowed_numbers():
    # S3 v1 호환 — 파라미터 미전달 시 지어낸 숫자도 숫자 검사로는 차단하지 않는다
    fake = dict(FACT_OK, text="종가 47,500원으로 마감했어요")
    _, record = check_response(make_response([fake]))
    assert all(b["rule_id"] != "NUM-01" for b in record["blocked"])


# ── SRC-EXIST: source_id 실재 검사 ─────────────────────────────────────

def test_unknown_source_id_blocked_when_known_set_given():
    ghost = dict(FACT_OK, source_id="DEMO-SRC-999")  # 형식은 유효하나 실재 없음
    sanitized, record = check_response(
        make_response([ghost]),
        known_source_ids={"DEMO-SRC-101", "DEMO-SRC-102"},
    )
    assert sanitized["facts"] == []
    entry = record["blocked"][0]
    assert entry["rule_id"] == "SRC-EXIST"
    assert entry["category"] == "no_source"
    assert record["counters"]["no_source"] == 1


def test_known_source_id_passes_existence_check():
    _, record = check_response(
        make_response([dict(FACT_OK)]),
        known_source_ids={"DEMO-SRC-102"},
    )
    assert record["blocked"] == []


def test_existence_check_skipped_when_none():
    # S3 v1 호환 — known_source_ids 미전달이면 형식 검사만 수행
    ghost = dict(FACT_OK, source_id="DEMO-SRC-999")
    _, record = check_response(make_response([ghost]))
    assert all(b["rule_id"] != "SRC-EXIST" for b in record["blocked"])
