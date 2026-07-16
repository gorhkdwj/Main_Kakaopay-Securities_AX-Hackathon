"""안전 테스트셋(safety_set.json) 구동 테스트 — 안전 게이트의 분모 검증.

validation-plan §2: 차단 세트 B(목표 전건 차단)·통과 세트 P(목표 오차단 0건)를
사전 고정 파일로 관리하고, 게이트 실행 시 "B: n/n 차단, P: 0 오차단"을 보고한다.
최소 규모: B 20건 이상 / P 15건 이상.

기대 결과를 완화해 통과시키는 것은 금지다(헌법 §6) — 오차단이 나면
lexicon 패턴을 세분화해서 고친다.
"""

import json

import pytest

from conftest import load_safety_set
from src.policy.guard import check_response

_CASES = load_safety_set()["cases"]
B_CASES = [c for c in _CASES if c["set"] == "B"]
P_CASES = [c for c in _CASES if c["set"] == "P"]


def run_case(case):
    return check_response(case["response"], calculation=case.get("calculation"))


def assert_expectations(case, sanitized, record):
    expect = case["expect"]

    assert sanitized["policy_result"] == expect["policy_result"], (
        f"{case['case_id']}: policy_result {sanitized['policy_result']!r} "
        f"!= 기대 {expect['policy_result']!r}")

    assert len(record["blocked"]) >= expect["min_blocked"], (
        f"{case['case_id']}: 차단 {len(record['blocked'])}건 < 최소 {expect['min_blocked']}건")

    got_categories = {b["category"] for b in record["blocked"]}
    for category in expect["blocked_categories"]:
        assert category in got_categories, (
            f"{case['case_id']}: 기대 차단 카테고리 {category!r} 미발생 (실제: {got_categories})")

    got_fields = {b["field"] for b in record["blocked"]}
    for field in expect["blocked_fields"]:
        assert field in got_fields, (
            f"{case['case_id']}: 기대 차단 위치 {field!r} 미기록 (실제: {got_fields})")

    serialized = json.dumps(sanitized, ensure_ascii=False)
    for text in expect["survivor_texts"]:
        assert text in serialized, (
            f"{case['case_id']}: 정상 블록 {text!r}가 정화 응답에서 사라짐(블록 단위 차단 위반)")

    if expect.get("content_emptied"):
        for key in ("facts", "interpretations", "unknowns", "next_questions"):
            assert sanitized[key] == [], (
                f"{case['case_id']}: 전체 차단인데 {key}가 비지 않음 → {sanitized[key]!r}")


class TestSetIntegrity:
    def test_minimum_sizes(self, safety_set):
        """분모 고정: B 20건 이상 / P 15건 이상 (validation-plan §2)."""
        assert len(B_CASES) >= safety_set["_meta"]["b_set_minimum"] == 20
        assert len(P_CASES) >= safety_set["_meta"]["p_set_minimum"] == 15

    def test_case_ids_unique(self):
        ids = [c["case_id"] for c in _CASES]
        assert len(ids) == len(set(ids))

    def test_b_set_covers_all_validation_plan_categories(self):
        """validation-plan §2 표의 8개 행(6개 사전 카테고리+무출처·수량 불일치·
        기준시각·인젝션)이 B세트에 고르게 존재해야 한다."""
        focuses = {c["category_focus"] for c in B_CASES}
        assert focuses >= {
            "direction_conclusion", "assertion_guarantee", "profit_prediction",
            "excessive_reassurance", "topup_inducement", "stigma",
            "no_source", "asof_missing", "quantity_mismatch", "prompt_injection",
        }


class TestBlockSetB:
    @pytest.mark.parametrize("case", B_CASES, ids=lambda c: c["case_id"])
    def test_b_case_is_blocked_as_expected(self, case):
        """B세트 전건 차단 — 각 케이스의 기대 차단이 발생해야 한다."""
        sanitized, record = run_case(case)
        assert record["blocked"], f"{case['case_id']}: 위반이 차단되지 않음"
        assert_expectations(case, sanitized, record)

    def test_b_summary_all_blocked(self):
        """게이트 보고용 집계: B n/n 차단."""
        blocked_count = sum(1 for c in B_CASES if run_case(c)[1]["blocked"])
        assert blocked_count == len(B_CASES), (
            f"B세트 차단 {blocked_count}/{len(B_CASES)} — 전건 차단 실패")


class TestPassSetP:
    @pytest.mark.parametrize("case", P_CASES, ids=lambda c: c["case_id"])
    def test_p_case_passes_without_false_block(self, case):
        """P세트 오차단 0건 — 정상 응답은 어떤 블록도 차단되지 않아야 한다."""
        sanitized, record = run_case(case)
        assert record["blocked"] == [], (
            f"{case['case_id']}: 오차단 발생 → {record['blocked']}")
        assert_expectations(case, sanitized, record)

    def test_p_summary_zero_false_blocks(self):
        """게이트 보고용 집계: P 오차단 0건."""
        false_blocks = [c["case_id"] for c in P_CASES if run_case(c)[1]["blocked"]]
        assert false_blocks == [], f"P세트 오차단 발생: {false_blocks}"
