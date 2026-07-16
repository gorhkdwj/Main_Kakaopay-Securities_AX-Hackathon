"""lexicon v1 단위 테스트 — 계약 §7 금지/허용 경계의 기계 검증.

FORBIDDEN_EXAMPLES(계약 §7·검증계획 §2의 금지 예문)는 전건 해당 카테고리로
매치되어야 하고, ALLOWED_EXAMPLES(허용 경계 예문)는 전건 비매치여야 한다.
"""

import pytest

from src.policy import lexicon
from src.policy.lexicon import (
    ALLOWED_EXAMPLES,
    CATEGORY_LABELS,
    FORBIDDEN_EXAMPLES,
    LEXICON_VERSION,
    RULES,
    find_violations,
)


def _forbidden_params():
    for category, examples in FORBIDDEN_EXAMPLES.items():
        for text in examples:
            yield pytest.param(category, text, id=f"{category}:{text[:20]}")


def _allowed_params():
    for category, examples in ALLOWED_EXAMPLES.items():
        for text in examples:
            yield pytest.param(text, id=f"{category}:{text[:20]}")


class TestVersionAndStructure:
    def test_version_is_v1(self):
        assert LEXICON_VERSION == "v1"

    def test_six_categories_match_contract(self):
        """계약 §7 표의 6개 카테고리가 전부 규칙으로 구현되어 있어야 한다."""
        assert set(CATEGORY_LABELS.keys()) == {
            "direction_conclusion", "assertion_guarantee", "profit_prediction",
            "excessive_reassurance", "topup_inducement", "stigma",
        }
        rule_categories = {rule.category for rule in RULES}
        assert rule_categories == set(CATEGORY_LABELS.keys())

    def test_every_rule_cites_contract_row(self):
        """모든 규칙은 계약 §7 근거 행 표기를 가진다(추적성)."""
        for rule in RULES:
            assert rule.contract_row.startswith("§7"), rule.rule_id

    def test_no_dynamic_execution_paths(self):
        """가드 계층은 텍스트를 데이터로만 취급한다 — 지시를 해석·실행하는
        코드 경로(eval/exec/compile 내장 호출, os.system, subprocess)가
        소스에 없어야 한다.

        보안 참고: 아래 패턴들은 실행되는 코드가 아니라, src/policy 소스에
        동적 실행 경로가 존재하지 않음을 검사하기 위한 검색용 정규식이다
        (프롬프트 인젝션 방어의 구조적 보장 — validation-plan §2 인젝션 행).
        내장 호출만 잡도록 앞에 식별자 문자·점이 없는 경우로 한정한다
        (re.compile / _compile 같은 정규식 컴파일은 코드 실행이 아니므로 허용).
        """
        import inspect
        import re as _re

        from src.policy import guard

        forbidden_call_res = [
            _re.compile(r"(?<![\w.])" + name + r"\s*\(")
            for name in ("eval", "exec", "compile", "__import__")
        ]
        forbidden_literals = ("os.system", "subprocess")
        for module in (lexicon, guard):
            source = inspect.getsource(module)
            for pattern in forbidden_call_res:
                assert not pattern.search(source), (
                    f"{module.__name__}에 동적 실행 호출 존재: {pattern.pattern}")
            for token in forbidden_literals:
                assert token not in source, f"{module.__name__}에 {token} 존재"


class TestForbiddenExamples:
    @pytest.mark.parametrize("category, text", _forbidden_params())
    def test_forbidden_example_is_matched(self, category, text):
        violations = find_violations(text)
        categories = {v["category"] for v in violations}
        assert category in categories, f"차단 예문 미매치: {text!r}"

    def test_violation_payload_shape(self):
        violations = find_violations("매도하세요")
        assert len(violations) == 1
        v = violations[0]
        assert set(v.keys()) == {"category", "label", "rule_id", "pattern", "match", "span"}
        assert v["category"] == "direction_conclusion"
        assert v["label"] == "방향 결론"
        assert v["match"] == "매도하세요"


class TestAllowedExamples:
    @pytest.mark.parametrize("text", _allowed_params())
    def test_allowed_example_not_matched(self, text):
        violations = find_violations(text)
        assert violations == [], f"허용 예문 오차단: {text!r} → {violations}"


class TestBoundaries:
    def test_guarantee_negation_allowed_but_affirmative_blocked(self):
        """'보장' 허용 경계: 부정형 위험 고지는 통과, 긍정형 보장은 차단."""
        assert find_violations("원금이 보장되지 않습니다") == []
        assert find_violations("원금 손실 가능성이 있으며 수익이 보장이 없습니다") == []
        blocked = find_violations("원금이 보장됩니다")
        assert {v["category"] for v in blocked} == {"assertion_guarantee"}

    def test_uncertain_word_not_matched_as_certain(self):
        """'불확실'의 부분 문자열 '확실'을 단정으로 오차단하지 않는다."""
        assert find_violations("단기 방향에는 불확실성이 큽니다") == []

    def test_topup_exemption_only_for_user_request(self):
        """추가매수 문구: 기본은 차단, 사용자 선요청 문맥에서만 면제(계약 §7)."""
        text = "추가 매수를 하면 이 종목 비중이 46.0%로 높아집니다"
        assert {v["category"] for v in find_violations(text)} == {"topup_inducement"}
        assert find_violations(text, user_requested_topup=True) == []

    def test_topup_exemption_does_not_relax_other_categories(self):
        """선요청 면제는 추가매수 카테고리에만 적용된다 — 방향 결론은 여전히 차단."""
        text = "추가 매수를 하면 좋으니 지금 사세요"
        categories = {v["category"] for v in find_violations(text, user_requested_topup=True)}
        assert "direction_conclusion" in categories

    def test_prediction_requires_all_three_elements(self):
        """수익 예측은 미래 시점+수치+등락의 3요소 결합일 때만 위반."""
        assert find_violations("다음 주에 실적 발표가 예정되어 있습니다") == []  # 미래 시점만
        assert find_violations("예상 수령액은 459,011원입니다") == []  # 수치만
        assert find_violations("주가 하락의 배경은 공시에서 확인됩니다") == []  # 등락 어휘만
        blocked = find_violations("다음 주 5만 원까지 오를 전망입니다")
        assert {v["category"] for v in blocked} == {"profit_prediction"}

    def test_one_report_per_category_per_text(self):
        """같은 카테고리 다중 매치는 텍스트당 1건만 보고한다."""
        violations = find_violations("매도하세요 그리고 매수하세요")
        assert len([v for v in violations if v["category"] == "direction_conclusion"]) == 1

    def test_non_string_or_empty_input_returns_no_violation(self):
        assert find_violations("") == []
        assert find_violations(None) == []  # type: ignore[arg-type]

    def test_direction_lookbehind_guards_partial_words(self):
        """'사세요/파세요'는 단어 시작일 때만 — 다른 단어의 일부는 오차단하지 않는다."""
        assert find_violations("상황을 조사세요라는 요청이 있었습니다") == []
        blocked = find_violations("지금 사세요")
        assert {v["category"] for v in blocked} == {"direction_conclusion"}
