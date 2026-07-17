r"""LLM 브리핑 캐시 생성기 — guard 통과분만 동결 저장한다(S5).

사용(프로젝트 루트에서):
    .\.venv\Scripts\python.exe scripts\briefing\gen_llm_cache.py --from-static
    .\.venv\Scripts\python.exe scripts\briefing\gen_llm_cache.py            # 실LLM(키 필요)
    .\.venv\Scripts\python.exe scripts\briefing\gen_llm_cache.py loss8     # 특정 시나리오만

모드:
    --from-static : compose_briefing(S4 정적 조립) 결과를 초안으로 저장.
                    키 불필요 — 키 확보 전 폴백 캐시를 채우는 용도이며
                    generated_by에 출처를 정직하게 남긴다.
    (기본)        : OpenAI 실호출(build_messages → call_openai) 후 저장.

공통 안전 규칙: 저장 전 guard(check_response + 숫자 대사·출처 실재 검사)를
통과해야 하며, 차단이 1건이라도 있으면 저장하지 않고 사유를 출력한다
— "가드 통과시킨 응답만 캐시"(구현 계획 S5).
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.briefing.llm import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    build_messages,
    call_openai,
    fixture_fingerprint,
    parse_llm_json,
)
from src.policy.guard import check_response, collect_allowed_numbers  # noqa: E402
from src.webapp.app import (  # noqa: E402
    PRICE_FACT_SOURCE,
    SCENARIO_ORDER,
    compose_briefing,
    known_source_ids_for,
)

FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"


def load_fixture(scenario_id: str) -> dict:
    path = FIXTURES_DIR / f"scenario_{scenario_id}.json"
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def make_response(fx: dict, scenario_id: str, from_static: bool) -> tuple[dict, str]:
    """(응답, generated_by 라벨)을 만든다."""
    if from_static:
        response, _aux = compose_briefing(fx)
        return response, "static_compose_draft_v1"
    price_src = PRICE_FACT_SOURCE.get(scenario_id)
    raw = call_openai(build_messages(fx, price_src))
    import os
    model = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    return parse_llm_json(raw), f"openai:{model}"


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM 브리핑 캐시 생성(가드 통과분만)")
    parser.add_argument("scenarios", nargs="*", default=None,
                        help="대상 시나리오 ID(기본: 전체 3종)")
    parser.add_argument("--from-static", action="store_true",
                        help="compose_briefing 결과를 초안으로 저장(키 불필요)")
    args = parser.parse_args()

    targets = args.scenarios or list(SCENARIO_ORDER)
    DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0

    for sid in targets:
        fx = load_fixture(sid)
        try:
            response, generated_by = make_response(fx, sid, args.from_static)
        except Exception as exc:
            print(f"[{sid}] 생성 실패: {type(exc).__name__} — 저장하지 않음")
            failures += 1
            continue

        sanitized, record = check_response(
            response, None,
            allowed_numbers=collect_allowed_numbers(fx),
            known_source_ids=known_source_ids_for(fx, sid),
        )
        if record["blocked"]:
            print(f"[{sid}] guard 차단 {len(record['blocked'])}건 — 저장하지 않음:")
            for b in record["blocked"]:
                print(f"    - {b['rule_id']} {b['field']}: {b['excerpt']}")
            failures += 1
            continue

        entry = {
            "scenario_id": sid,
            "generated_by": generated_by,
            "generated_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M} KST",
            "fixture_sha256": fixture_fingerprint(fx),
            "note": ("정적 조립 기반 초안 — OpenAI 키 확보 후 본 스크립트(실LLM 모드)로 재생성 예정"
                     if args.from_static else "실LLM 생성 — guard 통과 확인 후 동결"),
            "response": sanitized,  # 정화본 저장(통과 확인 시 원본과 동일)
        }
        out = DEFAULT_CACHE_DIR / f"scenario_{sid}.json"
        with open(out, "w", encoding="utf-8") as fp:
            json.dump(entry, fp, ensure_ascii=False, indent=2)
        warn = f" · 경고 {len(record['warnings'])}건" if record["warnings"] else ""
        print(f"[{sid}] 저장 완료({generated_by}){warn} → {out.relative_to(PROJECT_ROOT)}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
