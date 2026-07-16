"""판단 여권 · 금지/허용 표현 사전 v1 (S3 정책 가드의 텍스트 규칙 계층).

기준: docs/requirements-contract.md §7 "정책 가드 — 금지·허용 표현 사전 v1"
- 계약 §7 표의 6개 카테고리를 정규식 규칙으로 구현한다:
  방향 결론 / 단정·보장 / 수익 예측 / 과도한 안심 / 추가매수 유도 / 낙인 표현
- 각 규칙 주석에 계약 §7의 근거 행을 표기한다. 계약의 금지 패턴 열은
  "예시 — lexicon.py에 정규식화"로 명시되어 있으므로, 여기서는 예시를
  포괄하는 정규식으로 구체화하되 허용 경계(오차단 방지)를 함께 관리한다.
- 정상 문장 오차단이 발견되면 패턴을 세분화한다. 단, 차단 세트(B)의
  기대 결과를 완화하지 않는다(계약 §7 · 헌법 §6 — 테스트 완화 금지).

설계 원칙:
- 결정론: 같은 텍스트 입력이면 항상 같은 결과. LLM·네트워크·파일 I/O 없음.
- 텍스트는 데이터로만 취급한다. 텍스트 안의 지시문(프롬프트 인젝션)을
  해석·실행하는 코드 경로가 존재하지 않는다 — 정규식 매칭만 수행한다.
- 허용 예외(allow) 규칙: 금지 패턴 매치 구간이 허용 패턴 매치 구간과
  겹치면 해당 매치를 위반으로 세지 않는다(예: "보장" 매치가
  "보장되지 않습니다" 안에 있으면 위험 고지이므로 허용).

공개 인터페이스:
    LEXICON_VERSION: str — 사전 버전("v1"). 게이트 실패로 패턴을 보강하면 증가.
    CATEGORY_LABELS: dict — 카테고리 내부 키 → 계약 §7 한국어 행 이름.
    find_violations(text, *, user_requested_topup=False) -> list[dict]
        반환 항목: {"category", "label", "rule_id", "pattern", "match", "span"}
        - category: 내부 키(예: "direction_conclusion") — guard 차단 기록의 category로 사용
        - label: 계약 §7 행 이름(예: "방향 결론")
        - rule_id: 규칙 식별자(예: "DIR-01") — 감사로그 진단용
        - pattern: 매치된 정규식 원문(복합 규칙은 요소 정규식을 " & "로 결합)
        - match: 실제 매치 문자열(복합 규칙은 요소 매치를 "+"로 결합)
        - span: (시작, 끝) — 텍스트 내 매치 위치(복합 규칙은 첫 요소 기준)
        같은 카테고리는 텍스트당 최대 1건만 보고한다(첫 유효 매치).
        user_requested_topup=True면 '추가매수 유도' 카테고리를 면제한다
        (계약 §7 허용 경계: 사용자 선요청 시 위험 병기 안내 허용).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LEXICON_VERSION = "v1"

# 카테고리 내부 키 → 계약 §7 행 이름(한국어 라벨)
CATEGORY_LABELS = {
    "direction_conclusion": "방향 결론",
    "assertion_guarantee": "단정·보장",
    "profit_prediction": "수익 예측",
    "excessive_reassurance": "과도한 안심",
    "topup_inducement": "추가매수 유도",
    "stigma": "낙인 표현",
}


@dataclass(frozen=True)
class Rule:
    """금지 표현 규칙 1건.

    patterns가 1개면 단일 매치 규칙, 2개 이상이면 복합(all-of) 규칙 —
    모든 요소 패턴이 같은 텍스트에서 각각 유효 매치될 때만 위반이다
    (수익 예측: 미래 시점 + 금액/수익률 수치 + 등락 동사의 결합).
    allow_patterns: 매치 구간과 겹치면 해당 매치를 무효화하는 허용 패턴.
    user_request_exempt: True면 사용자 선요청 시 규칙 전체를 건너뛴다.
    """

    rule_id: str
    category: str
    patterns: tuple[str, ...]
    contract_row: str  # 계약 §7 근거 행 설명
    allow_patterns: tuple[str, ...] = ()
    user_request_exempt: bool = False

    def compiled(self) -> tuple[re.Pattern, ...]:
        return tuple(_compile(p) for p in self.patterns)

    def compiled_allow(self) -> tuple[re.Pattern, ...]:
        return tuple(_compile(p) for p in self.allow_patterns)


_COMPILE_CACHE: dict[str, re.Pattern] = {}


def _compile(pattern: str) -> re.Pattern:
    pat = _COMPILE_CACHE.get(pattern)
    if pat is None:
        pat = re.compile(pattern)
        _COMPILE_CACHE[pattern] = pat
    return pat


# ---------------------------------------------------------------------------
# 규칙 정의 — 계약 §7 표의 행 순서대로
# ---------------------------------------------------------------------------

RULES: tuple[Rule, ...] = (
    # ── 계약 §7 행 1 · 방향 결론 ─────────────────────────────────────────
    # 금지 예시: "(매수|매도|보유|보류)(하세요|를 추천|하시는 게|가 좋겠)"
    # 허용 경계: 조건 서술("매도를 선택하면 …입니다"),
    #            사용자 선택 인용("'매도 검토'를 선택하셨습니다")
    #            → 아래 패턴은 명령형·권유형 어미가 붙는 경우만 매치하므로
    #              "선택하면/선택하셨습니다" 류는 애초에 매치되지 않는다.
    Rule(
        rule_id="DIR-01",
        category="direction_conclusion",
        patterns=(r"(매수|매도|보유|보류)\s*(하세요|하십시오|해\s*보세요|하시죠)",),
        contract_row="§7 방향 결론 — '(매수|매도|보유|보류)하세요' 명령형",
    ),
    Rule(
        rule_id="DIR-02",
        category="direction_conclusion",
        patterns=(r"(매수|매도|보유|보류)[를을]?\s*추천",),
        contract_row="§7 방향 결론 — '(매수|매도|보유|보류)를 추천'",
    ),
    Rule(
        rule_id="DIR-03",
        category="direction_conclusion",
        patterns=(r"(매수|매도|보유|보류)\s*하시는\s*(게|것이|편이)\s*좋",),
        contract_row="§7 방향 결론 — '(매수|매도|보유|보류)하시는 게 좋겠'",
    ),
    Rule(
        rule_id="DIR-04",
        category="direction_conclusion",
        patterns=(r"(매수|매도|보유|보류)[가이]\s*좋겠",),
        contract_row="§7 방향 결론 — '(매수|매도|보유|보류)가 좋겠'",
    ),
    Rule(
        rule_id="DIR-05",
        category="direction_conclusion",
        # 앞이 한글이면(예: '조사세요') 다른 단어의 일부이므로 제외.
        patterns=(r"(?<![가-힣])(사|파)세요",),
        contract_row="§7 방향 결론 — '지금 (사|파)세요'",
    ),
    Rule(
        rule_id="DIR-06",
        category="direction_conclusion",
        # 검증계획 §2 B 예시 "지금 파시는 게 좋겠습니다"의 구어 변형.
        patterns=(r"(?<![가-힣])(사|파)시는\s*(게|것이|편이)\s*좋",),
        contract_row="§7 방향 결론 — '(사|파)시는 게 좋겠'(예시의 구어 변형)",
    ),
    # ── 계약 §7 행 2 · 단정·보장 ─────────────────────────────────────────
    # 금지 예시: "(오릅니다|내립니다|반등할|회복할) 겁니다", "안전한 종목",
    #            "확실(히|합니다)", "보장"
    # 허용 경계: 모름 명시("…는 알 수 없습니다"), 출처 있는 과거 사실
    #            → 미래 단정 어미가 붙는 경우만 매치하므로
    #              "회복 시점은 알 수 없습니다"는 매치되지 않는다.
    Rule(
        rule_id="AST-01",
        category="assertion_guarantee",
        patterns=(
            r"(오를|내릴|떨어질|반등할|회복할|상승할|하락할|급등할|급락할)\s*"
            r"(겁니다|것입니다|거예요|것이에요|게\s*분명)",
        ),
        contract_row="§7 단정·보장 — '(오를|반등할|회복할…) 겁니다' 미래 단정",
    ),
    Rule(
        rule_id="AST-02",
        category="assertion_guarantee",
        # 현재형 단정("오릅니다"). 앞이 한글이면 다른 단어의 일부로 보고 제외.
        patterns=(r"(?<![가-힣])(오릅니다|내립니다|반등합니다|회복합니다)",),
        contract_row="§7 단정·보장 — '(오릅니다|내립니다)' 현재형 단정",
    ),
    Rule(
        rule_id="AST-03",
        category="assertion_guarantee",
        patterns=(r"안전한\s*(종목|주식|투자|자산)",),
        contract_row="§7 단정·보장 — '안전한 종목'",
    ),
    Rule(
        rule_id="AST-04",
        category="assertion_guarantee",
        # '불확실'의 '확실'을 매치하지 않도록 앞 한글 제외.
        patterns=(r"(?<![가-힣])확실(히|합니다|해요)",),
        contract_row="§7 단정·보장 — '확실(히|합니다)'",
    ),
    Rule(
        rule_id="AST-05",
        category="assertion_guarantee",
        patterns=(r"보장",),
        # 부정형 위험 고지("원금이 보장되지 않습니다")는 정확한 고지이므로 허용.
        allow_patterns=(
            r"보장\s*(되지|하지)\s*않",
            r"보장(이|은|도|을|를)?\s*없",
        ),
        contract_row="§7 단정·보장 — '보장' (허용: 부정형 위험 고지)",
    ),
    # ── 계약 §7 행 3 · 수익 예측 ─────────────────────────────────────────
    # 금지: 미래 시점 + 가격/수익률 수치의 조합(계약 원문: "미래 시점+가격/수익률
    #        수치 조합"). 오차단 방지를 위해 등락·도달 동사까지 요구하는
    #        3요소 결합(all-of) 규칙으로 구현 — 세 요소가 한 텍스트 블록에
    #        모두 존재할 때만 위반.
    # 허용 경계: 사용자 계획 인용("목표 기간은 사용자가 적은 3년입니다" — 미래
    #        시점 표현 없음), 계산된 현재 시나리오 수치("예상 수령액은
    #        459,011원입니다" — 미래 시점 표현 없음)는 요소 미충족으로 통과.
    Rule(
        rule_id="PRED-01",
        category="profit_prediction",
        patterns=(
            # 요소 1: 미래 시점 표현(보수적 목록 — '다음 발표', '3년' 등
            #         기간·조건 표현은 포함하지 않는다)
            r"(내일|모레|다음\s*주|다음\s*달|다음\s*분기|내년|올해\s*말|연말|연내|조만간|곧|머지않아)",
            # 요소 2: 가격(원) 또는 수익률(%) 수치
            r"[0-9][0-9,.]*\s*(?:만|억|천)?\s*원|[0-9][0-9,.]*\s*(?:%|퍼센트)",
            # 요소 3: 등락·도달·수익 표현
            r"(오를|오른다|올라갈|상승|급등|반등|도달|돌파|회복|내릴|내린다|하락|급락|떨어질|수익)",
        ),
        contract_row="§7 수익 예측 — 미래 시점+가격/수익률 수치 조합(3요소 결합)",
    ),
    # ── 계약 §7 행 4 · 과도한 안심 ───────────────────────────────────────
    # 금지 예시: "괜찮아질", "걱정(하지 마|없)"
    # 허용 경계: 감정 인정까지 허용 — "불안하실 수 있습니다"는 아래 어떤
    #            패턴에도 매치되지 않는다(불안+'필요 없' 결합만 금지).
    Rule(
        rule_id="REA-01",
        category="excessive_reassurance",
        patterns=(r"괜찮아\s*[지질]",),
        contract_row="§7 과도한 안심 — '괜찮아질'",
    ),
    Rule(
        rule_id="REA-02",
        category="excessive_reassurance",
        patterns=(r"걱정\s*(하지\s*마|마세요|안\s*하셔도|없)",),
        contract_row="§7 과도한 안심 — '걱정(하지 마|없)'",
    ),
    Rule(
        rule_id="REA-03",
        category="excessive_reassurance",
        # 검증계획 §2 '감정 단정' 행: "불안해하실 필요 없습니다" 차단.
        patterns=(r"(불안|걱정|염려)[가-힣]{0,2}\s*하실\s*필요[는가]?\s*없",),
        contract_row="§7 과도한 안심 — 감정 단정 '(불안해)하실 필요 없'(검증계획 §2)",
    ),
    # ── 계약 §7 행 5 · 추가매수 유도 ─────────────────────────────────────
    # 금지: 사용자 요청 없는 "물타기|추가 매수(하면|해서)" 제안
    # 허용 경계: 사용자 선요청 시 집중도·추가손실 위험 병기 안내
    #            → guard가 user_inputs에서 선요청을 감지하면
    #              user_requested_topup=True로 호출해 카테고리 전체 면제.
    Rule(
        rule_id="TOP-01",
        category="topup_inducement",
        patterns=(r"물\s*타기",),
        contract_row="§7 추가매수 유도 — '물타기'",
        user_request_exempt=True,
    ),
    Rule(
        rule_id="TOP-02",
        category="topup_inducement",
        patterns=(r"추가\s*매수[를을]?\s*(하면|해서|하시면|해\s*보)",),
        contract_row="§7 추가매수 유도 — '추가 매수(하면|해서)'",
        user_request_exempt=True,
    ),
    Rule(
        rule_id="TOP-03",
        category="topup_inducement",
        # 검증계획 §2 B 예시 "지금 더 사서 평단을 낮추면…"
        patterns=(r"더\s*사\s*(서|면|시면)",),
        contract_row="§7 추가매수 유도 — '더 사서'(검증계획 §2 예시)",
        user_request_exempt=True,
    ),
    Rule(
        rule_id="TOP-04",
        category="topup_inducement",
        patterns=(r"평단(가)?[를을이]?\s*낮추",),
        contract_row="§7 추가매수 유도 — '평단을 낮추면'(물타기 완곡 표현)",
        user_request_exempt=True,
    ),
    # ── 계약 §7 행 6 · 낙인 표현 ─────────────────────────────────────────
    # 금지 예시: "초보라서", "잘 모르시니까"
    # 허용 경계: 행동 기술("처음 매도하시는 경우") — 아래 패턴에 매치되지 않음.
    Rule(
        rule_id="STG-01",
        category="stigma",
        patterns=(r"초보(라서|이라서|시라서|니까|시니까|이셔서)",),
        contract_row="§7 낙인 표현 — '초보라서'",
    ),
    Rule(
        rule_id="STG-02",
        category="stigma",
        patterns=(r"잘\s*모르(시니까|시잖|셔서|시면서|니까)",),
        contract_row="§7 낙인 표현 — '잘 모르시니까'",
    ),
)


# ---------------------------------------------------------------------------
# 문서·테스트용 예문 대장 — 계약 §7 + 검증계획 §2의 예시 문장을 사전과 함께
# 버전 관리한다(구현계획 S3: "허용 예문을 함께 관리"). test_lexicon.py가
# 아래 예문 전건을 기계 검증한다: FORBIDDEN_EXAMPLES는 전부 매치,
# ALLOWED_EXAMPLES는 전부 비매치여야 한다.
# ---------------------------------------------------------------------------

FORBIDDEN_EXAMPLES: dict[str, tuple[str, ...]] = {
    "direction_conclusion": (
        "매도하세요",                          # 계약 §7 예시
        "매수하세요",
        "보유를 추천드립니다",                  # 검증계획 §2 예시
        "지금 파시는 게 좋겠습니다",            # 검증계획 §2 예시
        "지금 사세요",                          # 계약 §7 예시
        "매도하시는 게 좋겠습니다",
    ),
    "assertion_guarantee": (
        "반등할 겁니다",                        # 검증계획 §2 예시
        "안전한 종목입니다",                    # 검증계획 §2 예시
        "확실히 회복합니다",                    # 검증계획 §2 예시
        "원금이 보장됩니다",                    # 계약 §7 '보장'
        "주가는 다시 오를 겁니다",
    ),
    "profit_prediction": (
        "다음 주 5만 원까지 오를 전망입니다",    # 검증계획 §2 예시
        "내년에는 20% 수익이 기대됩니다",
    ),
    "excessive_reassurance": (
        "불안해하실 필요 없습니다",              # 검증계획 §2 '감정 단정' 예시
        "걱정하지 마세요",                      # 계약 §7 예시
        "걱정 없습니다",
        "곧 괜찮아질 거예요",                    # 계약 §7 '괜찮아질'
    ),
    "topup_inducement": (
        "지금 더 사서 평단을 낮추면 손실 회복이 빨라집니다",  # 검증계획 §2 예시
        "물타기로 평단을 낮추는 방법도 있습니다",
        "추가 매수를 하면 평균 단가가 내려갑니다",
    ),
    "stigma": (
        "초보라서 어려우실 텐데요",              # 계약 §7 예시
        "잘 모르시니까 제가 정해드릴게요",        # 계약 §7 예시
    ),
}

ALLOWED_EXAMPLES: dict[str, tuple[str, ...]] = {
    "direction_conclusion": (
        "매도를 선택하면 예상 수령액은 459,011원입니다",   # 조건 서술(계약 §7)
        "'매도 검토'를 선택하셨습니다",                    # 사용자 선택 인용(계약 §7)
        "'보류'를 선택하시면 재검토 날짜를 함께 정하시겠어요?",
        "처음 매도하시는 경우 주문 순서를 먼저 확인하실 수 있습니다",
    ),
    "assertion_guarantee": (
        "회복 시점은 알 수 없습니다",                      # 모름 명시(계약 §7)
        "과거 20일 평균 대비 거래량이 3.2배로 늘었습니다",  # 출처 있는 과거 사실
        "이 상품은 예금과 달리 원금이 보장되지 않습니다",   # 부정형 위험 고지(allow)
        "단기 방향에는 불확실성이 큽니다",                  # '불확실'은 '확실' 아님
    ),
    "profit_prediction": (
        "목표 기간은 사용자가 적은 3년입니다",              # 계획 인용(계약 §7)
        "매도를 선택하면 예상 수령액은 459,011원입니다",    # 현재 시나리오 계산 수치
        "수수료 69원과 거래세·농특세 920원을 차감한 예상 수령액은 459,011원입니다",
        "3분기 잠정 영업이익 128억 원 — 전년 동기 대비 -32%",  # 과거 실적 사실
    ),
    "excessive_reassurance": (
        "불안하실 수 있습니다",                            # 감정 인정(계약 §7 허용)
        "불안을 느끼는 것은 자연스러운 반응입니다",
    ),
    "topup_inducement": (
        # 사용자 선요청 문맥이 아니어도, 아래 문장 자체는 유도 어형이 아니므로 통과.
        "매수 후 이 종목의 비중은 46.0%입니다",
    ),
    "stigma": (
        "처음 매도하시는 경우 순서를 함께 확인하겠습니다",   # 행동 기술(계약 §7 허용)
    ),
}


# ---------------------------------------------------------------------------
# 매칭 엔진
# ---------------------------------------------------------------------------

def _allowed_spans(rule: Rule, text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for allow in rule.compiled_allow():
        for m in allow.finditer(text):
            spans.append(m.span())
    return spans


def _overlaps(span: tuple[int, int], allowed: list[tuple[int, int]]) -> bool:
    s1, e1 = span
    return any(s1 < e2 and s2 < e1 for s2, e2 in allowed)


def _first_effective_match(pattern: re.Pattern, text: str,
                           allowed: list[tuple[int, int]]) -> re.Match | None:
    for m in pattern.finditer(text):
        if not _overlaps(m.span(), allowed):
            return m
    return None


def find_violations(text: str, *, user_requested_topup: bool = False) -> list[dict]:
    """텍스트 1블록에서 금지 표현 위반을 찾는다(카테고리당 최대 1건).

    입력 텍스트는 데이터로만 취급한다 — 텍스트 안의 지시문을 해석·실행하는
    경로가 없다(프롬프트 인젝션은 여기서 일반 문자열로 검사될 뿐이다).

    Args:
        text: 검사할 텍스트 블록. str이 아니거나 비어 있으면 위반 없음으로 처리.
        user_requested_topup: 사용자가 추가매수를 먼저 요청한 문맥이면 True —
            '추가매수 유도' 카테고리를 면제한다(계약 §7 허용 경계).

    Returns:
        위반 목록. 각 항목:
        {"category": str, "label": str, "rule_id": str,
         "pattern": str, "match": str, "span": (int, int)}
    """
    if not isinstance(text, str) or not text:
        return []

    violations: list[dict] = []
    hit_categories: set[str] = set()

    for rule in RULES:
        if rule.category in hit_categories:
            continue
        if rule.user_request_exempt and user_requested_topup:
            continue

        allowed = _allowed_spans(rule, text)
        compiled = rule.compiled()

        matches: list[re.Match] = []
        for pat in compiled:
            m = _first_effective_match(pat, text, allowed)
            if m is None:
                matches = []
                break
            matches.append(m)

        if not matches:
            continue

        if len(compiled) == 1:
            pattern_str = rule.patterns[0]
            match_str = matches[0].group(0)
        else:  # 복합(all-of) 규칙 — 모든 요소가 존재해야 위반
            pattern_str = " & ".join(rule.patterns)
            match_str = "+".join(m.group(0) for m in matches)

        violations.append({
            "category": rule.category,
            "label": CATEGORY_LABELS[rule.category],
            "rule_id": rule.rule_id,
            "pattern": pattern_str,
            "match": match_str,
            "span": matches[0].span(),
        })
        hit_categories.add(rule.category)

    return violations
