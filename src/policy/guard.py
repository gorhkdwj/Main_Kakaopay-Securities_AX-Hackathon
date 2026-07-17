"""판단 여권 · 정책 가드 (S3) — AI 응답 계약 JSON의 렌더링 전 결정론 검사.

기준: docs/requirements-contract.md §6(AI 응답 계약·필드별 검증 규칙),
      §7(금지/허용 표현 사전 v1 — src/policy/lexicon.py),
      §2(source_id 체계), §10(안전 지표 분모).

역할: LLM(또는 fixture 조립기)이 만든 응답 JSON이 화면에 그려지기 전에
      ① 출처(source_id)·기준시각(as_of) 없는 사실 ② 금지 표현
      ③ 사용자 입력과 다른 수량을 결정론적으로 걸러낸다.
      차단 단위는 '위반 블록만'이다 — 나머지 정상 블록은 렌더된다
      (계약 §6 "차단의 단위"). 예외적으로 수량 불일치는 응답 전체 차단.

이 모듈은 LLM·네트워크·파일 I/O를 수행하지 않으며, 검사 대상 텍스트를
데이터로만 취급한다 — 텍스트 안의 지시문(프롬프트 인젝션)을 해석하거나
실행하는 코드 경로가 존재하지 않는다(정규식 매칭·구조 비교만 수행).

──────────────────────────────────────────────────────────────────────
check_response(response, calculation=None, *,
               allowed_numbers=None, known_source_ids=None)
    -> (sanitized, record)
──────────────────────────────────────────────────────────────────────

입력:
    response: 계약 §6 형식의 dict —
        {"facts": [{"text", "source_id", "as_of"}],
         "interpretations": [{"text", "basis", "stance"}],
         "unknowns": [str], "user_inputs": {"quantity", "intent", "situation"},
         "calculation_id": str|None, "policy_result": str,
         "next_questions": [str]}
        dict가 아니면 TypeError를 raise한다(콘텐츠 위반이 아닌 호출 오류).
        누락된 필드는 빈 값([], {})으로 취급하고 정화 결과에 채워 넣는다.
    calculation: 엔진(S2) 계산 결과 dict 또는 None.
        입력 수량은 다음 우선순위 키에서 읽는다:
        inputs.quantity → inputs.qty → quantity → qty
        (S2·S5는 이 중 하나로 입력 수량을 노출해야 수량 검사가 작동한다.
         어느 키에도 없으면 검사를 건너뛰고 warnings에 남긴다.)
    allowed_numbers: facts[].text 숫자 대사(계약 §6 — LLM 산수 금지)의
        허용 숫자 집합(collect_allowed_numbers()로 fixture·엔진 결과에서
        추출) 또는 None. None이면 숫자 검사를 건너뛴다(S3 v1 호환).
        검사 시 NUMBER_CONTEXT_WHITELIST(지표 정의 상수)가 항상 합산된다.
    known_source_ids: 실재하는 source_id 집합(fixture 공시·시세 카드 출처
        — 계약 §2 "실재해야 함"의 S5 격상 구현) 또는 None.
        None이면 실재 검사를 건너뛴다(형식 검사만 — S3 v1 호환).

검사 파이프라인(순서 고정 — 결정론 보장):
    ① facts 구조 검사: source_id 또는 as_of 누락/빈 값 → 해당 fact 차단.
       source_id가 계약 §2 형식(`F-/C-/X-SRC-####` 4자리 또는
       `DEMO-SRC-###` 3자리, SOURCE_ID_RE)과 불일치 → 차단.
       known_source_ids가 주어지면 형식 통과 후 **실재 검사**(집합 미포함
       → 차단, rule_id SRC-EXIST — S5 격상: 형식 검사로 갈음하던 v1 한계 해소).
       한 fact가 source_id·as_of를 모두 위반하면 blocked에 2건 기록하고
       카운터를 각각 +1 하되 블록 제거는 1회다.
       (as_of는 존재·비공백 문자열 여부만 검사한다 — 포맷(§11) 검증은
        S1 fixture 검증 스크립트 소관.)
    ①-2 facts 숫자 대사(allowed_numbers 제공 시 — 계약 §6 "숫자 포함 시
       calculation_id 결과 또는 fixture 원천값과 일치"): ①·② 통과 텍스트의
       모든 숫자 토큰(콤마·소수 허용)을 절대값 Decimal로 정규화해 허용
       집합과 대조. 집합 밖 숫자 발견 → 해당 fact 차단(rule_id NUM-01,
       category number_unverified — counters 미집계, §10 3지표 아님).
       부호는 비교하지 않는다(방향 왜곡은 표현 사전 소관 — 책임 분리).
       facts[].text만 검사한다(계약 §6의 숫자 규칙 적용 범위).
    ② 금지 표현 검사(lexicon v1): ①을 통과한 facts[].text와
       interpretations[].text, unknowns[], next_questions[] 전수.
       위반 블록만 제거한다. user_inputs는 검사하지 않는다
       (사용자 입력은 AI 출력이 아니며, 추가매수 선요청 판단의
        문맥으로만 사용 — 계약 §7 허용 경계).
    ③ 수량 일치 검사: calculation이 주어지면 user_inputs.quantity와
       calculation 입력 수량을 비교. 불일치(quantity가 None인 경우 포함)
       → 응답 전체 차단: facts/interpretations/unknowns/next_questions를
       모두 비우고 policy_result="error"(수량 조작 방지 — 계약 §6).
       user_inputs·calculation_id는 유지한다(사용자 자신의 입력 표시는 무해).
       전체 차단 시 ④·⑤ 경고는 생략한다.
    ④ 해석 양면 검사: 원본 interpretations가 1건 이상인데 ①②를 통과한
       해석의 stance 집합이 {"긍정 시각", "부정 시각"} 미달이면
       warnings에 one_sided_interpretation("반대 시각 확인 안 됨") 추가
       — 차단 아님(계약 §6: 한쪽만이면 명시 요구 → 표시는 S4 렌더러 몫).
    ⑤ unknowns 검사: 정화 후 unknowns가 비어 있으면 warnings에
       empty_unknowns 추가 — 차단 아님(계약 §6: 비어 있으면 경고 로그).
    ⑥ policy_result 설정(우선순위): 전체 차단="error" >
       차단 1건 이상="blocked_partial" > 차단 0건="information_only".

구조 이상(malformed) 방어 — 렌더 직전 최후 계층이므로 crash하지 않는다:
    fact/interpretation 항목이 dict가 아니거나 text가 비어 있지 않은 str이
    아닌 경우, interpretations.stance가 "긍정 시각"/"부정 시각" 외의 값인
    경우, unknowns/next_questions 항목이 str이 아닌 경우, 필드가 list여야
    하는데 아닌 경우 → category="malformed"로 blocked에 기록하고 제거한다.
    malformed는 counters 3키에 집계하지 않는다(§10 지표 분모 아님).

──────────────────────────────────────────────────────────────────────
차단 기록(record) 포맷 — S4 화면 카운터와 out/audit 감사로그가 읽는 명세
──────────────────────────────────────────────────────────────────────
{
  "lexicon_version": "v1",            # 사전 버전(감사 추적용)
  "blocked": [                         # 차단 1건당 1항목(전체 차단 포함)
    {
      "category": str,   # 차단 사유 분류 —
                         #  구조: "no_source" | "asof_missing" |
                         #        "quantity_mismatch" | "malformed" |
                         #        "number_unverified"(S5 — 숫자 대사 실패)
                         #  표현: lexicon 카테고리 키
                         #        ("direction_conclusion", "assertion_guarantee",
                         #         "profit_prediction", "excessive_reassurance",
                         #         "topup_inducement", "stigma")
      "field": str,      # 위반 위치 — 원본(입력) 리스트 인덱스 기준 경로.
                         #  예: "facts[2].text", "facts[0].source_id",
                         #      "interpretations[1].text", "unknowns[0]",
                         #      "next_questions[1]", "user_inputs.quantity"
      "excerpt": str,    # 위반 텍스트 발췌(매치 앞뒤 최대 15자, "…" 표시)
      "pattern": str,    # 매치된 규칙 — 표현 위반은 정규식 원문
                         #  (복합 규칙은 " & " 결합), 구조 위반은 상수 식별자
                         #  ("required:source_id", "format:source_id",
                         #   "exists:source_id", "required:as_of",
                         #   "quantity_equality", "numbers:allowed_set", "schema")
      "rule_id": str     # 규칙 ID(진단·감사용): lexicon 규칙("DIR-01" 등)
                         #  또는 구조 검사 ID("SRC-REQ", "SRC-FMT", "SRC-EXIST",
                         #  "ASOF-REQ", "QTY-01", "NUM-01", "SCHEMA")
    }, ...
  ],
  "counters": {                        # 안전 지표 카운터(계약 §10) —
                                       # S4 화면 "무출처 n · 권유 표현 n" 원천
    "no_source": int,    # source_id 누락·비문자열·형식 불일치 fact 수(fact당 최대 1)
    "forbidden": int,    # 금지 표현 차단 건수(텍스트 블록당 카테고리별 최대 1)
    "asof_missing": int  # as_of 누락·비문자열 fact 수(fact당 최대 1)
  },                     # quantity_mismatch·malformed·number_unverified는
                         # blocked에만 기록되고 counters에는 집계하지 않는다
                         # (§10의 3개 분모 지표 아님).
  "warnings": [                        # 차단이 아닌 주의 신호
    {"code": "one_sided_interpretation",  # 반대 시각 확인 안 됨(④)
     "message": str},
    {"code": "empty_unknowns", "message": str},          # ⑤
    {"code": "calc_quantity_unknown", "message": str}    # ③ 검사 불가
  ]
}

반환:
    (sanitized, record) — sanitized는 입력의 깊은 복사본을 정화한 dict.
    입력 response는 절대 수정하지 않는다(원본 보존 — 감사 대조 가능).
"""

from __future__ import annotations

import copy
import re
from decimal import Decimal, InvalidOperation

from src.policy.lexicon import LEXICON_VERSION, find_violations

# 계약 §2 — source_id 체계: 리서치 근거 `F-/C-/X-SRC-####`(4자리) 또는
# 데모 가상 출처 `DEMO-SRC-###`(3자리)만 유효.
SOURCE_ID_RE = re.compile(r"^(?:[FCX]-SRC-\d{4}|DEMO-SRC-\d{3})$")

# 숫자 대사(①-2) — 텍스트에서 숫자 토큰을 뽑는 규칙: 콤마 자릿수 구분·소수 허용.
# 부호는 토큰에 포함하지 않는다(절대값 비교 — 모듈 docstring의 책임 분리).
NUM_TOKEN_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")

# 숫자 대사 상시 허용 집합 — fixture·계산 결과에 없지만 계약이 정의한 지표 상수.
#   2  : 결제일 D+2(계약 §5)·"2개 분기 연속"(재검토 조건 관용구)
#   20 : 거래량 배율의 분모 "20일 평균"(계약 §4)
NUMBER_CONTEXT_WHITELIST = frozenset({Decimal(2), Decimal(20)})

# 계약 §6 — interpretations.stance 허용값(양면 병기 판단 기준).
VALID_STANCES = ("긍정 시각", "부정 시각")

# 계약 §7 허용 경계 — 사용자 선요청 감지: user_inputs의 intent/situation에서
# 추가매수 요청 표현을 찾는다(텍스트는 데이터로만 취급 — 매칭만 수행).
_TOPUP_REQUEST_RE = re.compile(r"추가\s*매수|물\s*타기|더\s*사")

# calculation dict에서 입력 수량을 읽는 키 우선순위(docstring 명세와 동일).
_CALC_QTY_PATHS = (("inputs", "quantity"), ("inputs", "qty"), ("quantity",), ("qty",))

_EXCERPT_CONTEXT = 15  # 표현 위반 발췌 시 매치 앞뒤 문자 수
_EXCERPT_HEAD = 40     # 구조 위반 발췌 시 텍스트 앞부분 문자 수


def _excerpt_around(text: str, span: tuple[int, int]) -> str:
    start, end = span
    s = max(0, start - _EXCERPT_CONTEXT)
    e = min(len(text), end + _EXCERPT_CONTEXT)
    prefix = "…" if s > 0 else ""
    suffix = "…" if e < len(text) else ""
    return f"{prefix}{text[s:e]}{suffix}"


def _excerpt_head(value) -> str:
    text = value if isinstance(value, str) else repr(value)
    return text[:_EXCERPT_HEAD] + ("…" if len(text) > _EXCERPT_HEAD else "")


def _blocked_entry(category: str, field: str, excerpt: str,
                   pattern: str, rule_id: str) -> dict:
    return {"category": category, "field": field, "excerpt": excerpt,
            "pattern": pattern, "rule_id": rule_id}


def _as_list(value) -> tuple[list, bool]:
    """list면 그대로, 아니면(None 포함) 빈 리스트로. (값, 원형이_list였는지)."""
    if isinstance(value, list):
        return value, True
    return [], value is None  # None(필드 부재)은 malformed가 아닌 '빈 값' 취급


def _to_decimal(token: str) -> "Decimal | None":
    """숫자 토큰을 절대값 Decimal로 정규화한다(콤마 제거). 실패 시 None."""
    try:
        return abs(Decimal(token.replace(",", "")))
    except InvalidOperation:
        return None


def collect_allowed_numbers(*sources) -> set:
    """fixture·엔진 결과 등에서 숫자 대사(①-2)의 허용 숫자 집합을 추출한다.

    dict/list는 재귀 순회, int/float 값은 절대값 Decimal로, str 값은
    NUM_TOKEN_RE 토큰을 전부 추출해 넣는다(공시 텍스트 안 숫자 = fixture
    원천값 — 인용 허용). bool은 제외. None 소스는 무시.
    NUMBER_CONTEXT_WHITELIST는 여기서 합치지 않는다 — check_response가
    검사 시점에 항상 합산한다(호출자가 화이트리스트를 빠뜨릴 수 없게).
    """
    allowed: set = set()

    def walk(node) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            value = _to_decimal(str(node))
            if value is not None:
                allowed.add(value)
        elif isinstance(node, str):
            for token in NUM_TOKEN_RE.findall(node):
                value = _to_decimal(token)
                if value is not None:
                    allowed.add(value)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    for source in sources:
        if source is not None:
            walk(source)
    return allowed


def _unverified_numbers(text: str, allowed: set) -> list:
    """text의 숫자 토큰 중 allowed 집합에 없는 것들을 원문 그대로 반환한다."""
    bad: list = []
    for token in NUM_TOKEN_RE.findall(text):
        value = _to_decimal(token)
        if value is not None and value not in allowed:
            bad.append(token)
    return bad


def _user_requested_topup(user_inputs: dict) -> bool:
    """intent/situation 문자열에서 추가매수 선요청 표현을 감지한다."""
    for key in ("intent", "situation"):
        value = user_inputs.get(key)
        if isinstance(value, str) and _TOPUP_REQUEST_RE.search(value):
            return True
    return False


def _extract_calc_quantity(calculation: dict):
    """calculation에서 입력 수량을 읽는다. 못 찾으면 None."""
    for path in _CALC_QTY_PATHS:
        node = calculation
        found = True
        for key in path:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                found = False
                break
        if found and isinstance(node, int) and not isinstance(node, bool):
            return node
    return None


def check_response(response: dict, calculation: dict | None = None, *,
                   allowed_numbers: "set | None" = None,
                   known_source_ids: "set | None" = None) -> tuple[dict, dict]:
    """AI 응답 계약 JSON을 렌더링 전에 검사·정화한다.

    상세 명세(입력·파이프라인·차단 기록 포맷)는 모듈 docstring 참조.

    Args:
        response: 계약 §6 형식의 응답 dict. dict가 아니면 TypeError.
        calculation: 엔진 계산 결과 dict(수량 일치 검사용) 또는 None.
        allowed_numbers: facts 숫자 대사의 허용 집합(collect_allowed_numbers
            결과) 또는 None(검사 생략 — S3 v1 호환).
        known_source_ids: 실재 source_id 집합 또는 None(검사 생략).

    Returns:
        (sanitized, record):
        sanitized — 위반 블록이 제거된 응답 사본(policy_result 갱신됨).
        record — 차단 기록(모듈 docstring의 포맷).
    """
    if not isinstance(response, dict):
        raise TypeError(
            f"response는 계약 §6 형식의 dict여야 합니다: {type(response).__name__}"
        )

    number_check_set = (
        set(allowed_numbers) | set(NUMBER_CONTEXT_WHITELIST)
        if allowed_numbers is not None else None
    )

    sanitized = copy.deepcopy(response)
    record: dict = {
        "lexicon_version": LEXICON_VERSION,
        "blocked": [],
        "counters": {"no_source": 0, "forbidden": 0, "asof_missing": 0},
        "warnings": [],
    }
    blocked: list = record["blocked"]
    counters: dict = record["counters"]
    warnings: list = record["warnings"]

    # ── user_inputs 정규화(검사 문맥·수량 검사에 사용, 텍스트 검사 대상 아님) ──
    user_inputs = sanitized.get("user_inputs")
    if not isinstance(user_inputs, dict):
        if user_inputs is not None:
            blocked.append(_blocked_entry(
                "malformed", "user_inputs", _excerpt_head(user_inputs),
                "schema", "SCHEMA"))
        user_inputs = {"quantity": None, "intent": None, "situation": ""}
        sanitized["user_inputs"] = user_inputs
    topup_requested = _user_requested_topup(user_inputs)

    def scan_text(text: str, field: str) -> bool:
        """금지 표현 검사. 위반이면 blocked 기록 후 True(블록 제거 신호)."""
        violations = find_violations(text, user_requested_topup=topup_requested)
        for v in violations:
            blocked.append(_blocked_entry(
                v["category"], field, _excerpt_around(text, v["span"]),
                v["pattern"], v["rule_id"]))
            counters["forbidden"] += 1
        return bool(violations)

    # ── ① facts 구조 검사 + ② 텍스트 검사 ─────────────────────────────
    facts_raw, facts_ok = _as_list(response.get("facts"))
    if not facts_ok:
        blocked.append(_blocked_entry(
            "malformed", "facts", _excerpt_head(response.get("facts")),
            "schema", "SCHEMA"))
    surviving_facts = []
    for i, fact in enumerate(facts_raw):
        field_base = f"facts[{i}]"
        if not isinstance(fact, dict):
            blocked.append(_blocked_entry(
                "malformed", field_base, _excerpt_head(fact), "schema", "SCHEMA"))
            continue
        text = fact.get("text")
        if not isinstance(text, str) or not text.strip():
            blocked.append(_blocked_entry(
                "malformed", f"{field_base}.text", _excerpt_head(text),
                "schema", "SCHEMA"))
            continue

        structural_violation = False
        source_id = fact.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            blocked.append(_blocked_entry(
                "no_source", f"{field_base}.source_id", _excerpt_head(text),
                "required:source_id", "SRC-REQ"))
            counters["no_source"] += 1
            structural_violation = True
        elif not SOURCE_ID_RE.match(source_id):
            blocked.append(_blocked_entry(
                "no_source", f"{field_base}.source_id",
                f"source_id={source_id!r}: {_excerpt_head(text)}",
                "format:source_id", "SRC-FMT"))
            counters["no_source"] += 1
            structural_violation = True
        elif known_source_ids is not None and source_id not in known_source_ids:
            # S5 격상(계약 §2 "실재해야 함") — 형식은 맞지만 이 시나리오의
            # 실재 출처 집합에 없는 ID(LLM이 지어낸 출처)를 차단한다.
            blocked.append(_blocked_entry(
                "no_source", f"{field_base}.source_id",
                f"source_id={source_id!r} 실재하지 않음: {_excerpt_head(text)}",
                "exists:source_id", "SRC-EXIST"))
            counters["no_source"] += 1
            structural_violation = True

        as_of = fact.get("as_of")
        if not isinstance(as_of, str) or not as_of.strip():
            blocked.append(_blocked_entry(
                "asof_missing", f"{field_base}.as_of", _excerpt_head(text),
                "required:as_of", "ASOF-REQ"))
            counters["asof_missing"] += 1
            structural_violation = True

        if structural_violation:
            continue  # 구조 위반 fact는 텍스트 검사 없이 차단(블록 제거 1회)
        if scan_text(text, f"{field_base}.text"):
            continue
        if number_check_set is not None:
            # ①-2 숫자 대사(계약 §6 — LLM 산수 금지): 허용 집합 밖 숫자 차단
            bad_numbers = _unverified_numbers(text, number_check_set)
            if bad_numbers:
                blocked.append(_blocked_entry(
                    "number_unverified", f"{field_base}.text",
                    f"미확인 숫자 {', '.join(bad_numbers)}: {_excerpt_head(text)}",
                    "numbers:allowed_set", "NUM-01"))
                continue
        surviving_facts.append(copy.deepcopy(fact))
    sanitized["facts"] = surviving_facts

    # ── ② interpretations 구조·텍스트 검사 ────────────────────────────
    interps_raw, interps_ok = _as_list(response.get("interpretations"))
    if not interps_ok:
        blocked.append(_blocked_entry(
            "malformed", "interpretations",
            _excerpt_head(response.get("interpretations")), "schema", "SCHEMA"))
    surviving_interps = []
    for i, interp in enumerate(interps_raw):
        field_base = f"interpretations[{i}]"
        if not isinstance(interp, dict):
            blocked.append(_blocked_entry(
                "malformed", field_base, _excerpt_head(interp), "schema", "SCHEMA"))
            continue
        text = interp.get("text")
        if not isinstance(text, str) or not text.strip():
            blocked.append(_blocked_entry(
                "malformed", f"{field_base}.text", _excerpt_head(text),
                "schema", "SCHEMA"))
            continue
        stance = interp.get("stance")
        if stance not in VALID_STANCES:
            blocked.append(_blocked_entry(
                "malformed", f"{field_base}.stance", _excerpt_head(stance),
                "schema", "SCHEMA"))
            continue
        if scan_text(text, f"{field_base}.text"):
            continue
        surviving_interps.append(copy.deepcopy(interp))
    sanitized["interpretations"] = surviving_interps

    # ── ② unknowns · next_questions 텍스트 검사 ───────────────────────
    def scan_str_list(field_name: str) -> list:
        items_raw, items_ok = _as_list(response.get(field_name))
        if not items_ok:
            blocked.append(_blocked_entry(
                "malformed", field_name, _excerpt_head(response.get(field_name)),
                "schema", "SCHEMA"))
        surviving = []
        for i, item in enumerate(items_raw):
            field = f"{field_name}[{i}]"
            if not isinstance(item, str) or not item.strip():
                blocked.append(_blocked_entry(
                    "malformed", field, _excerpt_head(item), "schema", "SCHEMA"))
                continue
            if scan_text(item, field):
                continue
            surviving.append(item)
        return surviving

    sanitized["unknowns"] = scan_str_list("unknowns")
    sanitized["next_questions"] = scan_str_list("next_questions")

    # ── ③ 수량 일치 검사(불일치 시 응답 전체 차단 — 계약 §6) ──────────
    full_block = False
    if calculation is not None:
        calc_qty = _extract_calc_quantity(calculation) if isinstance(calculation, dict) else None
        if calc_qty is None:
            warnings.append({
                "code": "calc_quantity_unknown",
                "message": ("calculation 입력 수량 확인 불가 — 수량 일치 검사 미수행 "
                            "(기대 키: inputs.quantity/inputs.qty/quantity/qty)"),
            })
        else:
            user_qty = user_inputs.get("quantity")
            if user_qty != calc_qty:
                blocked.append(_blocked_entry(
                    "quantity_mismatch", "user_inputs.quantity",
                    f"user_inputs.quantity={user_qty!r} ≠ calculation 수량={calc_qty!r}",
                    "quantity_equality", "QTY-01"))
                full_block = True

    if full_block:
        # 응답 전체 차단: 렌더 콘텐츠 전부 제거(user_inputs·calculation_id는 유지).
        sanitized["facts"] = []
        sanitized["interpretations"] = []
        sanitized["unknowns"] = []
        sanitized["next_questions"] = []
        sanitized["policy_result"] = "error"
        return sanitized, record

    # ── ④ 해석 양면(stance) 검사 — 경고만, 차단 아님 ──────────────────
    if len(interps_raw) >= 1:
        stances = {interp.get("stance") for interp in surviving_interps}
        if not stances.issuperset(VALID_STANCES):
            present = [s for s in VALID_STANCES if s in stances]
            warnings.append({
                "code": "one_sided_interpretation",
                "message": ("반대 시각 확인 안 됨 — 렌더 가능한 해석의 stance가 "
                            f"{present if present else '없음'}뿐입니다"
                            "(계약 §6: 양면 병기 필요)"),
            })

    # ── ⑤ unknowns 공백 검사 — 경고만, 차단 아님 ─────────────────────
    if not sanitized["unknowns"]:
        warnings.append({
            "code": "empty_unknowns",
            "message": "unknowns 비어 있음 — '알 수 없는 것' 항목이 없습니다(계약 §6 권장 최소 1개)",
        })

    # ── ⑥ policy_result 설정 ──────────────────────────────────────────
    sanitized["policy_result"] = "blocked_partial" if blocked else "information_only"

    return sanitized, record
