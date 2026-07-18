r"""판단 여권 · 웹 UI 서버(FastAPI) — 데모 본체(S4 완주 골격 + S5 LLM 브리핑 결합).

실행 방법(반드시 프로젝트 루트에서 — src는 namespace package라 루트 실행 전제):

    .\.venv\Scripts\python.exe -m uvicorn src.webapp.app:app --port 8765 --reload

이후 브라우저에서 http://127.0.0.1:8765 로 접속한다.
변경 반영: 정적 파일·fixture는 요청마다 다시 읽으므로 브라우저 새로고침(Ctrl+F5)만으로
반영되고, 이 모듈(파이썬 코드)의 변경은 서버 재시작이 필요하다(--reload면 자동).
외부 CDN·폰트·네트워크 요청 0 — 정적 파일은 전부 로컬(src/webapp/static/)이고,
FastAPI 자동 문서(/docs·/redoc)는 CDN 자산을 쓰므로 비활성화했다.

아키텍처 위치(구현 계획 §0 불변 원칙):
  ① 숫자는 전부 src/engine(결정론 계산 엔진)이 만든다 — 이 모듈은 산수를 하지 않는다.
  ② 화면에 그려지는 사실·해석·모름·질문 블록은 전부 src/policy.guard의
     check_response를 통과한 AI 응답 계약(계약 §6) JSON이다. 정적 부가 텍스트
     (community_buzz·투자 일지 자동완성 초안)도 lexicon 검사를 통과해야 반환된다.
  ③ 브리핑 원천은 폴백 사슬(S5 — src/briefing/llm.py): live(키 존재 시)
     → cache(fixture 지문 일치 시) → static(compose_briefing). 모드 기본값
     "auto"는 키가 없으면 네트워크를 시도하지 않는다 — 오프라인 완주 유지.
     어느 원천이든 guard 관문·카운터 집계·화면 렌더는 동일 경로다.

API 명세(입출력 상세는 각 핸들러 docstring):
  GET  /api/scenarios        시나리오 목록
  GET  /api/scenario/{id}    fixture 로드 → 브리핑(폴백 사슬) → guard → 화면 데이터
  POST /api/preview          {scenario_id, side, qty} → 엔진 미리보기(오류는 계약 §5.3)
  POST /api/settle           {preview, confirmed_qty} → settle_order 모의 체결
  POST /api/record           투자 일지·회고 저장 → out/records/REC-*.json(계약 §3.3)
  GET  /api/safety           세션 누적 안전 지표 카운터(계약 §10)
"""

from __future__ import annotations

import datetime
import itertools
import json
import re
from pathlib import Path

from fastapi import Body, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.briefing.llm import append_audit, generate_briefing, resolve_mode
from src.engine import (
    CALC_ID_PATTERN,
    EngineInputError,
    buy_preview,
    hold_summary,
    sell_preview,
    settle_order,
)
from src.policy.guard import check_response, collect_allowed_numbers
from src.policy.lexicon import find_violations

#: 프로젝트 루트(src/webapp/app.py 기준 2단계 상위)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"
DEFAULT_RECORDS_DIR = PROJECT_ROOT / "out" / "records"

#: 체결시장 정보 라벨(계약 §5.1 — 계산은 KRX 기준, 라벨은 실앱 동일 표기)
MARKET_LABEL = "SOR 정규장"

#: 공시 필드 부재 시 카드 상태 문구(계약 §8 — 대체값 생성 금지)
NO_DISCLOSURE_STATE = "확인된 공시 없음"

#: 데모 시나리오 표시 순서·제목(loss8이 기본)
SCENARIO_ORDER = ["loss8", "profit15", "first_buy"]
SCENARIO_TITLES = {
    "loss8": "-8% 급락 · 가온전자 보유",
    "profit15": "+15% 수익 · 한빛식품 보유",
    "first_buy": "첫 구매 검토 · 다온소재",
    # 실종목 시나리오(계약 §3.1-b) — fixture 존재 시에만 목록에 나타난다
    # (/api/scenarios는 디렉터리 스캔). 계좌성 값은 교육용 모의 값.
    "real_005930": "실데이터 스냅샷 · 005930.KS",
}

#: 시세·거래량 사실 카드의 source_id(계약 §2 — 끝자리 02=시세·거래량,
#: 백의 자리 1=가온전자·2=한빛식품·3=다온소재). 값의 원천은 fixture price/volume.
PRICE_FACT_SOURCE = {
    "loss8": "DEMO-SRC-102",
    "profit15": "DEMO-SRC-202",
    "first_buy": "DEMO-SRC-302",
    # 실종목(계약 §3.1-b): 측정 사실 카드가 YF-SRC-001부터 최대 004까지
    # 쓰므로(어댑터 build_real_scenario.py) 시세·거래량 카드는 005를 예약.
    "real_005930": "YF-SRC-005",
}
PRICE_FACT_SOURCE_BY_NAME = {
    "가온전자": "DEMO-SRC-102",
    "한빛식품": "DEMO-SRC-202",
    "다온소재": "DEMO-SRC-302",
}

#: unknowns — 모름·중립 표현 원칙(스펙 §3: 구체적 모름 + 시장 주어).
#: 자명한 일반론("내일 가격은 알 수 없다" 단독)은 정보가치가 없어 금지
#: (사용자 피드백 2026-07-16 — 모름은 '무엇이 언제 어디서 확인되는가'로 쓴다).
SCENARIO_UNKNOWNS = {
    "loss8": [
        "2개 분기 연속 악화 여부는 다음 실적 발표에서 확인됩니다.",
        "공시에 없는 회사 내부 사정(비용·수주 계획)은 공개 자료로 알 수 없습니다.",
    ],
    "profit15": [
        "신제품 매출이 이어질지는 다음 분기 실적 발표에서 확인됩니다.",
        "오늘 상승분에서 실적 요인과 수급 요인은 구분해 확인할 수 없습니다.",
    ],
    "first_buy": [
        "이익 증가가 이어질지는 다음 실적 발표에서 확인됩니다.",
        "경쟁사와 견준 성장 속도는 이 화면의 데이터만으로는 비교할 수 없습니다.",
    ],
    "real_005930": [
        "이번 하락에서 업황 요인과 수급 요인은 이 화면의 데이터만으로 구분할 수 없습니다.",
        "공시된 실적 발표 예정일의 실제 내용은 발표 시점에야 확인됩니다.",
    ],
}

#: plan이 없을 때(first_buy)의 투자 일지 질문 초안 3문(계약 §3.1 — 목표 기간·감수 손실·재검토 조건)
PLAN_QUESTION_DRAFTS = [
    "목표 보유 기간을 얼마로 정하시겠어요? (예: 1년 · 3년)",
    "감수할 수 있는 손실은 몇 %까지로 정하시겠어요?",
    "어떤 조건이 되면 이 구매 판단을 다시 검토하시겠어요?",
]

#: plan이 있는 시나리오의 추가 질문(재검토 조건 대조 질문은 plan에서 동적 생성)
SCENARIO_EXTRA_QUESTIONS = {
    "loss8": [
        "현재 -8.0%는 계획에 적어 두신 감수 범위(-15%) 안에 있나요?",
        "오늘 꼭 결정해야 하는 이유가 있나요?",
    ],
    "profit15": [
        "지금 판매를 검토하는 이유를 한 문장으로 적을 수 있나요?",
        "일부 판매와 전량 판매 후의 비중 차이를 확인하셨나요?",
    ],
}

#: 검토 의향(계약 §3.3·§9 — 방향별 4버튼과 동일 라벨, [데모 고정])
VALID_INTENTS = {
    # 판매 검토 방향
    "그대로 유지",
    "일부 판매 검토",
    "전량 판매 검토",
    "나중에 재검토",
    # 구매 검토 방향
    "구매하지 않기",
    "8주 구매 검토",
    "10주 구매 검토",
}

#: 구매 수량 의향 동적 라벨(계약 §3.3 — ④ 구매 수량 조정, D-0718-0255):
#: "N주 구매 검토"(N=1~999). 수량 유효성(예수금 한도)은 엔진이 계산 시점에
#: 검증하며, 기록은 의향 표현이므로 라벨 형식만 검사한다.
BUY_QTY_INTENT_RE = re.compile(r"^\d{1,3}주 구매 검토$")


def is_valid_intent(intent) -> bool:
    """검토 의향 라벨 검증 — 고정 집합 또는 구매 수량 동적 라벨."""
    return isinstance(intent, str) and (
        intent in VALID_INTENTS or bool(BUY_QTY_INTENT_RE.match(intent))
    )

#: /api/record가 파일에 쓰는 필드 전체(계약 §3.3) — 이 밖의 키는 절대 저장하지
#: 않는다(결과 수익률 저장 금지 — 과정 중심 원칙).
RECORD_FIELDS = (
    "record_id", "scenario_id", "intent", "reason_text",
    "calculation_id", "created_at", "review_date",
)


def known_source_ids_for(fx: dict, scenario_id: str) -> set:
    """이 시나리오에서 '실재'하는 source_id 집합(guard SRC-EXIST의 기준).

    fixture 공시의 source_id + 시세·거래량 카드용 출처(계약 §2)로 구성한다.
    LLM이 이 밖의 ID를 지어내면 guard가 렌더 전에 차단한다.
    """
    known = {
        d["source_id"] for d in (fx.get("disclosures") or [])
        if isinstance(d, dict) and isinstance(d.get("source_id"), str)
    }
    price_src = PRICE_FACT_SOURCE.get(scenario_id) or PRICE_FACT_SOURCE_BY_NAME.get(
        (fx.get("instrument") or {}).get("name", "")
    )
    if price_src:
        known.add(price_src)
    return known


def _now_kst_label() -> str:
    """현재 시각을 계약 §11 포맷(YYYY-MM-DD HH:mm KST)으로 반환(로컬=KST 전제)."""
    return f"{datetime.datetime.now():%Y-%m-%d %H:%M} KST"


def _err(status: int, code: str, message: str, safety: dict | None = None) -> JSONResponse:
    """오류 응답(계약 §5.3·§8 — 오류 메시지 + 재입력, 계산·체결 기록 미생성)."""
    body: dict = {"ok": False, "error": {"code": code, "message": message}}
    if safety is not None:
        body["safety"] = safety
    return JSONResponse(status_code=status, content=body)


class FixtureInvalidError(Exception):
    """fixture JSON 파손 — 라우트가 계약 §8의 500 오류 응답(fixture_invalid)으로 변환한다."""

    def __init__(self, scenario_id: str):
        super().__init__(scenario_id)
        self.scenario_id = scenario_id


# ---------------------------------------------------------------------------
# 정적 브리핑 조립(S5 전 LLM 없음 — fixture 값만 사용, 산수 없음)
# ---------------------------------------------------------------------------

def compose_briefing(fx: dict) -> tuple[dict, dict]:
    """fixture에서 AI 응답 계약(계약 §6) dict와 화면 부가 정보를 조립한다.

    - facts = 공시(disclosures 그대로, as_of=published_at)
              + 시세·거래량 사실 카드(fixture price/volume 값만, source_id x02,
                as_of=fixture.as_of)
    - interpretations = fixture 그대로(양면) + basis=[공시 source_id]
    - unknowns ≥ 1 — 모름·중립 표현 원칙(구체적 모름·시장 주어)
    - next_questions = plan 있으면 재검토 조건 대조 질문, plan null이면 질문 초안 3문
    - user_inputs.situation = scenario_id

    필드가 없으면 지어내지 않고(대체값 생성 금지 — 계약 §8) 카드를 생략하며,
    부가 정보(aux)의 unavailable 목록·disclosures_state로 상태를 알린다.
    반환: (response, aux) — response는 guard(check_response) 입력용.
    """
    scenario_id = fx.get("scenario_id", "")
    as_of = fx.get("as_of")
    facts: list[dict] = []
    unavailable: list[str] = []
    disclosures_state = None

    # ── 공시 사실(그대로 — 필드가 없으면 만들지 않는다) ────────────────
    disclosures = fx.get("disclosures")
    basis: list[str] = []
    if isinstance(disclosures, list) and disclosures:
        for d in disclosures:
            if not isinstance(d, dict):
                continue
            facts.append({
                "text": d.get("text"),
                "source_id": d.get("source_id"),
                "as_of": d.get("published_at"),
            })
            if isinstance(d.get("source_id"), str):
                basis.append(d["source_id"])
    else:
        unavailable.append("disclosures")
        disclosures_state = NO_DISCLOSURE_STATE

    # ── 시세·거래량 사실 카드(fixture price/volume 값만) ────────────────
    price = fx.get("price")
    volume = fx.get("volume")
    if isinstance(price, dict) and "close" in price and "change_pct" in price:
        parts = [
            f"종가 {price['close']:,}원",
            f"전일 대비 {price['change_pct']:+.1f}%",
        ]
        if isinstance(volume, dict) and "today" in volume and "ratio" in volume:
            parts.append(f"거래량 {volume['today']:,}주(20일 평균의 {volume['ratio']}배)")
        else:
            unavailable.append("volume")
        source_id = PRICE_FACT_SOURCE.get(scenario_id) or PRICE_FACT_SOURCE_BY_NAME.get(
            (fx.get("instrument") or {}).get("name", "")
        )
        facts.append({"text": " · ".join(parts), "source_id": source_id, "as_of": as_of})
    else:
        unavailable.append("price")

    # ── 해석(fixture 그대로 — 양면 병기 강제는 S1 검증·guard 경고 소관) ──
    interps = [
        {"text": it.get("text"), "basis": list(basis), "stance": it.get("stance")}
        for it in (fx.get("interpretations") or [])
        if isinstance(it, dict)
    ]
    if not interps:
        unavailable.append("interpretations")

    # ── unknowns · next_questions ───────────────────────────────────────
    unknowns = list(SCENARIO_UNKNOWNS.get(scenario_id, []))

    plan = fx.get("plan")
    if isinstance(plan, dict) and plan.get("review_condition"):
        next_questions = [
            f"오늘 상황이 기록해 두신 재검토 조건({plan['review_condition']})에 해당하나요?"
        ]
        next_questions += SCENARIO_EXTRA_QUESTIONS.get(scenario_id, [])
    else:
        next_questions = list(PLAN_QUESTION_DRAFTS)

    response = {
        "facts": facts,
        "interpretations": interps,
        "unknowns": unknowns,
        "user_inputs": {"quantity": None, "intent": None, "situation": scenario_id},
        "calculation_id": None,
        "policy_result": "information_only",
        "next_questions": next_questions,
    }
    aux = {"unavailable": unavailable, "disclosures_state": disclosures_state}
    return response, aux


def build_diary_draft(dc: dict) -> str | None:
    """discovery_context에서 투자 일지 자동완성 초안을 조립한다(계약 §9).

    사용자의 행동 사실(경로·테마명·기준·일시)만으로 만들고, 시스템이 감정·판단
    어휘를 창작하지 않는다. 저장은 사용자 버튼으로만(자동 저장 금지) — 서버는
    초안 문자열을 돌려줄 뿐 어디에도 저장하지 않는다.
    """
    if not isinstance(dc, dict):
        return None
    path, theme = dc.get("path"), dc.get("theme")
    criteria, entered_at = dc.get("criteria"), dc.get("entered_at")
    if not all(isinstance(v, str) and v for v in (path, theme, criteria, entered_at)):
        return None
    return (
        f"{path} > 「{theme}」 테마({criteria})에서 발견해 구매를 검토함"
        f" ({entered_at})"
    )


# ---------------------------------------------------------------------------
# 앱 팩토리
# ---------------------------------------------------------------------------

def create_app(fixtures_dir: "Path | str | None" = None,
               records_dir: "Path | str | None" = None,
               briefing_mode: "str | None" = None,
               llm_cache_dir: "Path | str | None" = None,
               audit_dir: "Path | str | None" = None) -> FastAPI:
    """웹 UI FastAPI 앱을 만든다.

    Args:
        fixtures_dir: 시나리오 fixture 디렉터리(기본 data/fixtures — 테스트에서
            변형 fixture 검증용으로 교체 가능. 원본 fixture는 수정하지 않는다).
        records_dir: 판단 기록 저장 디렉터리(기본 out/records — Git 제외).
        briefing_mode: 브리핑 원천 모드(auto|live|cache|static — 기본은
            BRIEFING_MODE 환경변수, 그것도 없으면 auto). 테스트는 "cache"를
            명시해 네트워크 시도를 원천 차단한다.
        llm_cache_dir: LLM 응답 캐시 디렉터리(기본 data/fixtures/llm_cache).
        audit_dir: 감사로그 디렉터리(기본 out/audit — Git 제외).
    """
    app = FastAPI(title="판단 여권 · 데모", docs_url=None, redoc_url=None,
                  openapi_url=None)  # 문서 UI는 CDN 자산을 쓰므로 오프라인 원칙상 비활성

    app.state.fixtures_dir = Path(fixtures_dir) if fixtures_dir else DEFAULT_FIXTURES_DIR
    app.state.records_dir = Path(records_dir) if records_dir else DEFAULT_RECORDS_DIR
    app.state.briefing_mode = resolve_mode(briefing_mode)
    app.state.llm_cache_dir = Path(llm_cache_dir) if llm_cache_dir else None
    app.state.audit_dir = Path(audit_dir) if audit_dir else None
    app.state.session_id = f"{datetime.datetime.now():%m%d-%H%M%S}"
    app.state.record_seq = itertools.count(1)
    # 세션 누적 안전 지표(계약 §10 — 화면 상시 카운터의 원천)
    app.state.safety = {
        "responses_checked": 0,      # guard를 통과시킨 응답 수
        "facts_rendered": 0,         # 렌더 허용된 fact 수(전부 출처·기준시각 보유)
        "static_texts_checked": 0,   # lexicon으로 검사한 정적 텍스트 수
        "no_source": 0,              # 출처 없는 사실 차단 수
        "forbidden": 0,              # 금지 표현 차단 수(응답+정적 텍스트)
        "asof_missing": 0,           # 기준시각 없는 사실 차단 수
    }

    # ── 내부 헬퍼 ───────────────────────────────────────────────────────
    def safety_snapshot() -> dict:
        return {"session_id": app.state.session_id, **app.state.safety}

    def accumulate_guard(sanitized: dict, record: dict) -> None:
        """guard 결과를 세션 누적 카운터에 반영한다."""
        s = app.state.safety
        s["responses_checked"] += 1
        s["facts_rendered"] += len(sanitized.get("facts") or [])
        counters = record.get("counters") or {}
        s["no_source"] += counters.get("no_source", 0)
        s["forbidden"] += counters.get("forbidden", 0)
        s["asof_missing"] += counters.get("asof_missing", 0)

    def check_static_text(text: str, field: str, static_blocked: list) -> bool:
        """정적 텍스트(부가 표시용)를 lexicon으로 검사한다. 통과하면 True."""
        app.state.safety["static_texts_checked"] += 1
        violations = find_violations(text)
        for v in violations:
            app.state.safety["forbidden"] += 1
            static_blocked.append({
                "category": v["category"], "field": field,
                "excerpt": v["match"], "pattern": v["pattern"],
                "rule_id": v["rule_id"],
            })
        return not violations

    def load_fixture(scenario_id: str) -> "dict | None":
        if not isinstance(scenario_id, str) or not scenario_id:
            return None
        path = app.state.fixtures_dir / f"scenario_{scenario_id}.json"
        if not path.is_file():
            return None
        with open(path, encoding="utf-8") as fp:
            try:
                return json.load(fp)
            except json.JSONDecodeError as exc:
                raise FixtureInvalidError(scenario_id) from exc

    def _fixture_invalid_response(exc: FixtureInvalidError) -> JSONResponse:
        return _err(500, "fixture_invalid",
                    f"시나리오 '{exc.scenario_id}' 파일을 읽지 못했어요 — JSON 형식을 확인해 주세요.",
                    safety_snapshot())

    # ── 라우트: 정적 화면 ───────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # ── 라우트: API ─────────────────────────────────────────────────────
    @app.get("/api/scenarios")
    def api_scenarios() -> dict:
        """시나리오 목록을 반환한다.

        출력: {ok, scenarios: [{scenario_id, title, is_default}], safety}
        """
        found = sorted(
            p.stem.replace("scenario_", "", 1)
            for p in app.state.fixtures_dir.glob("scenario_*.json")
        )
        ordered = [s for s in SCENARIO_ORDER if s in found]
        ordered += [s for s in found if s not in ordered]
        scenarios = [
            {
                "scenario_id": sid,
                "title": SCENARIO_TITLES.get(sid, sid),
                "is_default": sid == (ordered[0] if ordered else None),
            }
            for sid in ordered
        ]
        return {"ok": True, "scenarios": scenarios, "safety": safety_snapshot()}

    def _build_briefing(fx: dict, scenario_id: str) -> dict:
        """브리핑(폴백 사슬 → guard → 카운터·감사로그)을 생성한다(계약 §6·§8).

        시나리오 로드와 분리된 별도 단계다 — 사용자가 '브리핑 시작'을 택할 때만
        호출되어 live 모드의 불필요한 생성·지연을 없앤다(D-0718-0355).
        반환: {briefing(정화본), briefing_source, guard} — GET /api/briefing 응답용.
        """
        # 정적 조립은 항상 수행 — live·cache 실패 시의 최종 폴백(계약 §8).
        static_response, _aux = compose_briefing(fx)
        llm_response, llm_source, attempts = generate_briefing(
            fx, mode=app.state.briefing_mode,
            price_source_id=PRICE_FACT_SOURCE.get(scenario_id),
            cache_dir=app.state.llm_cache_dir,
        )
        if llm_response is not None:
            response, briefing_source = llm_response, llm_source
        else:
            response, briefing_source = static_response, "static"
        append_audit({
            "scenario_id": scenario_id, "mode": app.state.briefing_mode,
            "source": briefing_source, "attempts": attempts,
        }, app.state.audit_dir)

        # guard 관문(원천 무관 동일) — S5 확장: 숫자 대사·출처 실재 검사
        sanitized, record = check_response(
            response, None,
            allowed_numbers=collect_allowed_numbers(fx),
            known_source_ids=known_source_ids_for(fx, scenario_id),
        )
        accumulate_guard(sanitized, record)
        return {
            "briefing": sanitized,
            "briefing_source": briefing_source,
            "guard": {"policy_result": sanitized.get("policy_result"), "record": record},
        }

    @app.get("/api/briefing/{scenario_id}")
    def api_briefing(scenario_id: str):
        """②의 브리핑을 생성해 반환한다 — '브리핑 시작' 시점에만 호출(D-0718-0355).

        출력: {ok, scenario_id, briefing(정화된 계약 §6 JSON),
               briefing_source("live"|"cache"|"static"),
               guard: {policy_result, record}, safety}
        """
        try:
            fx = load_fixture(scenario_id)
        except FixtureInvalidError as exc:
            return _fixture_invalid_response(exc)
        if fx is None:
            return _err(404, "not_found",
                        f"시나리오 '{scenario_id}'를 찾을 수 없어요 — fixture 파일이 없어요.")
        result = _build_briefing(fx, scenario_id)
        return {"ok": True, "scenario_id": scenario_id, **result,
                "safety": safety_snapshot()}

    @app.get("/api/scenario/{scenario_id}")
    def api_scenario(scenario_id: str):
        """fixture 로드 → 화면 데이터(브리핑 제외 — 별도 GET /api/briefing) 반환.

        브리핑은 '브리핑 시작' 시점에 별도 요청한다(D-0718-0355) — 이 응답에는
        meta·hold·past_records·community_buzz·diary_draft만 담긴다.

        출력: {ok, scenario_id,
               meta: {instrument, price, volume, holding, cash,
                      portfolio_total_value, plan, trade_date, as_of,
                      is_synthetic, side, market_label, badge_text,
                      unavailable, disclosures_state},
               static_blocked(community_buzz·diary_draft 차단 기록),
               hold(hold_summary 결과 | null), past_records, discovery_context,
               community_buzz(정적 검사 통과분 | null),
               diary_draft(first_buy 자동완성 초안 | null), safety}
        """
        try:
            fx = load_fixture(scenario_id)
        except FixtureInvalidError as exc:
            return _fixture_invalid_response(exc)
        if fx is None:
            return _err(404, "not_found",
                        f"시나리오 '{scenario_id}'를 찾을 수 없어요 — fixture 파일이 없어요.")

        # 누락 필드 상태(공시·시세 등) — 브리핑과 무관한 fixture 사실이므로 여기서 계산
        _static_response, aux = compose_briefing(fx)

        static_blocked: list = []

        # community_buzz — 사실 카드와 분리 렌더('관심 지표' 프레임), 정적 텍스트 검사
        buzz = fx.get("community_buzz")
        if isinstance(buzz, dict) and isinstance(buzz.get("note"), str):
            if not check_static_text(buzz["note"], "community_buzz.note", static_blocked):
                buzz = None
        elif not isinstance(buzz, dict):
            buzz = None

        # 투자 일지 자동완성 초안(first_buy) — 행동 사실만 조립, guard(사전) 통과 후 반환
        diary_draft = build_diary_draft(fx.get("discovery_context"))
        if diary_draft is not None:
            if not check_static_text(diary_draft, "diary_draft", static_blocked):
                diary_draft = None

        # '유지' 열 표시값 — 숫자는 엔진만 만든다(hold_summary, calculation_id 없음)
        holding = fx.get("holding") or {}
        hold = None
        try:
            if isinstance(holding, dict) and (holding.get("qty") or 0) >= 1:
                hold = hold_summary(
                    fx["price"]["close"], holding["avg_price"],
                    holding["qty"], fx["portfolio_total_value"],
                )
        except (EngineInputError, KeyError, TypeError):
            hold = None  # 필드 누락 시 '확인 불가'(대체값 생성 금지 — 계약 §8)

        as_of = fx.get("as_of")
        if fx.get("is_synthetic") is False:
            # 실종목 fixture(계약 §3.1-b) — 가상 배지와 구분: 실데이터 스냅샷
            # 기준(지연)이며 보유·계획·예수금 등 계좌성 값은 교육용 모의 값.
            badge_text = (
                f"교육용 모의 환경 — 실데이터 스냅샷 기준(지연, {as_of})" if as_of
                else "교육용 모의 환경 — 실데이터 스냅샷 기준(지연)"
            )
        else:
            badge_text = (
                f"교육용 가상 데이터 (가상 기준시각 {as_of})" if as_of
                else "교육용 가상 데이터"
            )
        side = "buy" if (holding.get("qty") or 0) == 0 else "sell"

        # 등락 금액(원) — 서버 파생 결정론 계산(계약 §3.1: 프런트 산수 금지·계산과 말의 분리)
        price = dict(fx.get("price") or {})
        if isinstance(price.get("close"), int) and isinstance(price.get("prev_close"), int):
            price["change_amount"] = price["close"] - price["prev_close"]

        meta = {
            "instrument": fx.get("instrument"),
            "price": price,
            "volume": fx.get("volume"),
            "holding": fx.get("holding"),
            "cash": fx.get("cash"),
            "portfolio_total_value": fx.get("portfolio_total_value"),
            "plan": fx.get("plan"),
            "trade_date": fx.get("trade_date"),
            "as_of": as_of,
            "is_synthetic": bool(fx.get("is_synthetic")),
            "side": side,
            "market_label": MARKET_LABEL,
            "badge_text": badge_text,
            "unavailable": aux["unavailable"],
            "disclosures_state": aux["disclosures_state"],
        }

        return {
            "ok": True,
            "scenario_id": scenario_id,
            "static_blocked": static_blocked,  # community_buzz·diary_draft 차단 기록
            "meta": meta,
            "hold": hold,
            "past_records": fx.get("past_records") or [],
            "discovery_context": fx.get("discovery_context"),
            "community_buzz": buzz,
            "diary_draft": diary_draft,
            "safety": safety_snapshot(),
        }

    @app.post("/api/preview")
    def api_preview(payload: dict = Body(...)):
        """주문 미리보기 — 숫자는 엔진이 만들고 guard에 calculation을 전달(수량 대조).

        입력: {scenario_id: str, side: "sell"|"buy", qty: int}
        출력: {ok, preview(엔진 결과 — calculation_id 포함),
               guard: {policy_result, record}, safety}
        오류(400): 계약 §5.3 메시지 — 계산 결과·calculation_id·체결 기록 미생성.
        """
        scenario_id = payload.get("scenario_id")
        side = payload.get("side")
        qty = payload.get("qty")

        try:
            fx = load_fixture(scenario_id)
        except FixtureInvalidError as exc:
            return _fixture_invalid_response(exc)
        if fx is None:
            return _err(404, "not_found",
                        f"시나리오 '{scenario_id}'를 찾을 수 없어요 — fixture 파일이 없어요.")
        if side not in ("sell", "buy"):
            return _err(400, "invalid_side",
                        "side는 'sell'(판매) 또는 'buy'(구매)만 가능해요.",
                        safety_snapshot())

        try:
            if side == "sell":
                holding = fx.get("holding") or {}
                if not holding.get("qty"):
                    return _err(400, "no_holding",
                                "보유 수량이 없어 판매 미리보기를 만들 수 없어요.",
                                safety_snapshot())
                preview = sell_preview(
                    qty,
                    fx["price"]["close"],
                    holding["avg_price"],
                    holding["qty"],
                    fx["portfolio_total_value"],
                    fx["trade_date"],
                )
            else:
                holding = fx.get("holding") or {}
                preview = buy_preview(
                    qty, fx["price"]["close"], fx.get("cash", 0), fx["trade_date"],
                    holding_qty=holding.get("qty") or 0,
                    avg_price=holding.get("avg_price"),
                    portfolio_total_value=fx.get("portfolio_total_value"),
                )
        except EngineInputError as exc:
            # 계약 §5.3: 오류 메시지 + 재입력 — 계산 기록 미생성
            return _err(400, type(exc).__name__, str(exc), safety_snapshot())
        except (KeyError, TypeError):
            return _err(400, "fixture_field_missing",
                        "fixture 필드 누락으로 계산할 수 없어요 — 해당 카드는 확인 불가예요.",
                        safety_snapshot())

        # guard 배선(불변 원칙 ②): 미리보기 표시 응답에 calculation을 전달해
        # 수량 대조를 통과시킨다(허용 숫자 = fixture 원천값 + 이 계산 결과).
        stub = {
            "facts": [],
            "interpretations": [],
            "unknowns": [],
            "user_inputs": {"quantity": qty, "intent": side, "situation": scenario_id},
            "calculation_id": preview["calculation_id"],
            "policy_result": "information_only",
            "next_questions": [],
        }
        sanitized, record = check_response(
            stub, calculation=preview,
            allowed_numbers=collect_allowed_numbers(fx, preview),
            known_source_ids=known_source_ids_for(fx, scenario_id),
        )
        accumulate_guard(sanitized, record)
        if sanitized.get("policy_result") == "error":
            # 수량 불일치 전체 차단 — 화면에 계산 결과를 내보내지 않는다
            return _err(400, "quantity_mismatch",
                        "입력 수량과 계산 수량이 일치하지 않아 표시를 차단했어요.",
                        safety_snapshot())

        return {
            "ok": True,
            "preview": preview,
            "guard": {"policy_result": sanitized["policy_result"], "record": record},
            "safety": safety_snapshot(),
        }

    @app.post("/api/settle")
    def api_settle(payload: dict = Body(...)):
        """모의 체결 — settle_order가 preview를 결정론 재계산으로 재검증한다.

        입력: {preview: dict(엔진이 준 미리보기 그대로), confirmed_qty: int}
        출력: {ok, settlement(is_mock=True 상시), safety}
        오류(400): 수량 불일치·수치 변조·형식 오류 — 체결 기록 미생성.
        """
        preview = payload.get("preview")
        confirmed_qty = payload.get("confirmed_qty")
        if not isinstance(preview, dict):
            return _err(400, "invalid_preview",
                        "preview는 엔진이 반환한 미리보기 그대로 보내야 해요.",
                        safety_snapshot())
        try:
            settlement = settle_order(preview, confirmed_qty)
        except EngineInputError as exc:
            return _err(400, type(exc).__name__, str(exc), safety_snapshot())
        return {"ok": True, "settlement": settlement, "safety": safety_snapshot()}

    @app.post("/api/record")
    def api_record(payload: dict = Body(...)):
        """투자 일지·회고를 판단 기록(계약 §3.3)으로 저장한다.

        입력: {scenario_id: str, intent: str(4택), reason_text: str,
               calculation_id?: str(CALC-* 형식), review_date?: str}
        출력: {ok, record(저장된 내용 그대로), safety}
        저장 파일: <records_dir>/REC-<세션>-<seq>.json — 디렉터리 자동 생성.
        결과(수익률)는 어떤 형태로도 저장하지 않는다(과정 중심 원칙).
        저장은 이 엔드포인트를 부르는 사용자 버튼으로만 일어난다(자동 저장 없음).
        """
        scenario_id = payload.get("scenario_id")
        intent = payload.get("intent")
        reason_text = payload.get("reason_text")
        calculation_id = payload.get("calculation_id")
        review_date = payload.get("review_date")

        try:
            fixture_missing = load_fixture(scenario_id) is None
        except FixtureInvalidError as exc:
            return _fixture_invalid_response(exc)
        if fixture_missing:
            return _err(404, "not_found",
                        f"시나리오 '{scenario_id}'를 찾을 수 없어요 — fixture 파일이 없어요.")
        if not is_valid_intent(intent):
            return _err(400, "invalid_intent",
                        "검토 의향은 화면의 4가지 버튼 값 중 하나여야 해요.",
                        safety_snapshot())
        if not isinstance(reason_text, str) or not reason_text.strip():
            return _err(400, "empty_reason",
                        "투자 일지(이유)를 한 문장 이상 적어 주세요.",
                        safety_snapshot())
        if calculation_id is not None and (
            not isinstance(calculation_id, str) or not CALC_ID_PATTERN.match(calculation_id)
        ):
            return _err(400, "invalid_calculation_id",
                        "calculation_id 형식이 올바르지 않아요(CALC-… 형식).",
                        safety_snapshot())
        if review_date is not None and (
            not isinstance(review_date, str) or not review_date.strip()
        ):
            return _err(400, "invalid_review_date",
                        "다음 재검토 메모는 비어 있지 않은 문자열이어야 해요.",
                        safety_snapshot())

        record_id = f"REC-{app.state.session_id}-{next(app.state.record_seq)}"
        record: dict = {
            "record_id": record_id,
            "scenario_id": scenario_id,
            "intent": intent,
            "reason_text": reason_text.strip(),
        }
        if calculation_id is not None:
            record["calculation_id"] = calculation_id
        record["created_at"] = _now_kst_label()
        if review_date is not None:
            record["review_date"] = review_date.strip()

        records_dir: Path = app.state.records_dir
        records_dir.mkdir(parents=True, exist_ok=True)
        path = records_dir / f"{record_id}.json"
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(record, fp, ensure_ascii=False, indent=2)

        return {"ok": True, "record": record, "safety": safety_snapshot()}

    @app.get("/api/safety")
    def api_safety() -> dict:
        """세션 누적 안전 지표 카운터(계약 §10)를 반환한다."""
        return {"ok": True, "safety": safety_snapshot()}

    return app


#: uvicorn 진입점 — `python -m uvicorn src.webapp.app:app --port 8765`
app = create_app()
