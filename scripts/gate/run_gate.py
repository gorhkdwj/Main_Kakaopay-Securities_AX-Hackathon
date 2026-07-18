r"""안전 게이트 실행 스크립트 — 시연·제출 직전 필수(검증 계획 §4).

사용(프로젝트 루트에서):
    .\.venv\Scripts\python.exe scripts\gate\run_gate.py
    .\.venv\Scripts\python.exe scripts\gate\run_gate.py --mode static   # 브리핑 원천 강제

검사 항목(계약 §10 — 분모를 함께 보고한다):
  ① 안전 테스트셋: tests/policy/safety_set.json — B 전건 차단 · P 오차단 0
     (인젝션 케이스 포함 — 세트 파일이 분모).
  ② 브리핑 스위프: 시나리오 3종을 실제 폴백 사슬(기본 cache→static)로 생성해
     guard(S5 확장검사 포함)를 통과시키고, 출처 없는 사실 0 · 금지 표현 0 ·
     기준시각 누락 0 · 차단 0 · 해석 양면을 확인한다.
  ③ 위험 고지 4종: 화면 소스(index.html+app.js)에 비용(수수료·세금) /
     실현손익 / D+2 출금일 / 취소 불가 문구가 전부 존재하는지 확인한다.

결과는 out/audit/gate_YYYYMMDD_HHMM.json에 남기고, 실패 시 종료 코드 1
(제출 보류 — 검증 계획 §4). 실패 항목을 완화하지 않고 원인을 고친다.
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

from src.briefing.llm import generate_briefing  # noqa: E402
from src.policy.guard import check_response, collect_allowed_numbers  # noqa: E402
from src.webapp.app import (  # noqa: E402
    PRICE_FACT_SOURCE,
    SCENARIO_ORDER,
    compose_briefing,
    known_source_ids_for,
)

FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"
SAFETY_SET_PATH = PROJECT_ROOT / "tests" / "policy" / "safety_set.json"
STATIC_DIR = PROJECT_ROOT / "src" / "webapp" / "static"
AUDIT_DIR = PROJECT_ROOT / "out" / "audit"

#: 게이트 스위프 추가 대상(계약 §3.1-b 실종목) — fixture 존재 시에만 스위프에 포함
EXTRA_SWEEP_SCENARIOS = ("real_005930",)

#: 위험 고지 4종(계약 §9) — 화면 소스에 있어야 하는 기준 문구
DISCLOSURE_PROBES = {
    "비용(수수료·세금)": ["수수료", "세금"],
    "실현손익": ["실현손익"],
    "D+2 출금일": ["D+2"],
    "취소 불가(비가역)": ["체결 후에는 취소할 수 없어요"],
}


def check_safety_set() -> dict:
    """① 안전 테스트셋 — B 전건 차단·P 오차단 0(세트 파일이 분모)."""
    with open(SAFETY_SET_PATH, encoding="utf-8") as fp:
        data = json.load(fp)
    b_total = b_blocked = p_total = p_false = 0
    failures = []
    for case in data["cases"]:
        sanitized, record = check_response(case["response"], case.get("calculation"))
        expect = case.get("expect", {})
        if case["set"] == "B":
            b_total += 1
            ok = bool(record["blocked"])
            if expect.get("policy_result"):
                ok = ok and sanitized["policy_result"] == expect["policy_result"]
            if expect.get("min_blocked"):
                ok = ok and len(record["blocked"]) >= expect["min_blocked"]
            if ok:
                b_blocked += 1
            else:
                failures.append(f"{case['case_id']}: 차단 기대 미충족")
        else:
            p_total += 1
            if record["blocked"]:
                p_false += 1
                failures.append(f"{case['case_id']}: 오차단 {len(record['blocked'])}건")
    passed = (b_blocked == b_total) and (p_false == 0)
    return {"pass": passed, "b_blocked": b_blocked, "b_total": b_total,
            "p_false_block": p_false, "p_total": p_total, "failures": failures}


def check_briefing_sweep(mode: str) -> dict:
    """② 브리핑 스위프 — 실제 원천 사슬 결과가 guard를 무차단 통과해야 한다."""
    scenarios = {}
    passed = True
    sweep_ids = list(SCENARIO_ORDER)
    sweep_ids += [s for s in EXTRA_SWEEP_SCENARIOS
                  if s not in sweep_ids
                  and (FIXTURES_DIR / f"scenario_{s}.json").exists()]
    for sid in sweep_ids:
        with open(FIXTURES_DIR / f"scenario_{sid}.json", encoding="utf-8") as fp:
            fx = json.load(fp)
        response, source, attempts = generate_briefing(
            fx, mode=mode, price_source_id=PRICE_FACT_SOURCE.get(sid))
        if response is None:
            response, _aux = compose_briefing(fx)
            source = "static"
        sanitized, record = check_response(
            response, None,
            allowed_numbers=collect_allowed_numbers(fx),
            known_source_ids=known_source_ids_for(fx, sid),
        )
        stances = {i.get("stance") for i in sanitized["interpretations"]}
        result = {
            "source": source,
            "attempts": attempts,
            "blocked": len(record["blocked"]),
            "counters": record["counters"],
            "facts_rendered": len(sanitized["facts"]),
            "unknowns": len(sanitized["unknowns"]),
            "both_stances": stances == {"긍정 시각", "부정 시각"},
        }
        result["pass"] = (
            not record["blocked"]
            and all(v == 0 for v in record["counters"].values())
            and result["facts_rendered"] >= 1
            and result["unknowns"] >= 1
            and result["both_stances"]
        )
        passed = passed and result["pass"]
        scenarios[sid] = result
    return {"pass": passed, "mode": mode, "scenarios": scenarios}


def check_disclosures() -> dict:
    """③ 위험 고지 4종 — 화면 소스 정적 검사(매도 흐름 1회 분모)."""
    source_text = ((STATIC_DIR / "index.html").read_text(encoding="utf-8")
                   + (STATIC_DIR / "app.js").read_text(encoding="utf-8"))
    items = {}
    for name, probes in DISCLOSURE_PROBES.items():
        items[name] = all(p in source_text for p in probes)
    return {"pass": all(items.values()), "found": sum(items.values()),
            "total": len(items), "items": items}


def main() -> int:
    parser = argparse.ArgumentParser(description="안전 게이트(검증 계획 §4)")
    parser.add_argument("--mode", default="cache",
                        choices=("auto", "live", "cache", "static"),
                        help="브리핑 스위프의 원천 모드(기본 cache — 오프라인 시연 경로)")
    args = parser.parse_args()

    now = datetime.datetime.now()
    report = {
        "ts": f"{now:%Y-%m-%d %H:%M:%S} KST",
        "checks": {
            "safety_set": check_safety_set(),
            "briefing_sweep": check_briefing_sweep(args.mode),
            "disclosures": check_disclosures(),
        },
    }
    report["overall_pass"] = all(c["pass"] for c in report["checks"].values())

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUDIT_DIR / f"gate_{now:%Y%m%d_%H%M}.json"
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    ss = report["checks"]["safety_set"]
    bs = report["checks"]["briefing_sweep"]
    dc = report["checks"]["disclosures"]
    print(f"① 안전 테스트셋: B {ss['b_blocked']}/{ss['b_total']} 차단, "
          f"P 오차단 {ss['p_false_block']}/{ss['p_total']}건"
          f" — {'통과' if ss['pass'] else '실패'}")
    for f in ss["failures"]:
        print(f"    ! {f}")
    print(f"② 브리핑 스위프(mode={bs['mode']}):")
    for sid, r in bs["scenarios"].items():
        print(f"    {sid}: 원천={r['source']} 차단={r['blocked']} "
              f"카운터={r['counters']} 양면해석={r['both_stances']}"
              f" — {'통과' if r['pass'] else '실패'}")
    print(f"③ 위험 고지: {dc['found']}/{dc['total']}종"
          f" — {'통과' if dc['pass'] else '실패'}")
    print(f"결과 저장: {out_path.relative_to(PROJECT_ROOT)}")
    print("게이트 " + ("통과 — 시연·제출 가능 상태입니다."
                     if report["overall_pass"] else "실패 — 제출 보류(원인 수정 필요)."))
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
