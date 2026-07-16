# -*- coding: utf-8 -*-
"""fixture·manifest 스키마 검증 (S1)

단일 기준: docs/requirements-contract.md §3.1(fixture 스키마), §3.2(manifest),
§5.2·5.2-b·5.2-c(골든값 전제). 이 스크립트의 상수가 계약과 다르면 계약이 우선한다.

사용법:
    python scripts/data/validate_fixture.py
동작:
    - data/fixtures/scenario_*.json 전부를 검사 (필수 필드·타입·값 일관성·양면 해석·골든 전제)
    - data/snapshots/manifest.json 상태 보고 (없으면 "fixture 단독 모드" = 정상)
    - 하나라도 실패하면 종료 코드 1
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

# Windows 콘솔(cp949)에서 한글·특수문자 출력 크래시 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "data" / "fixtures"
MANIFEST_PATH = ROOT / "data" / "snapshots" / "manifest.json"

AS_OF_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} KST$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SRC_RE = re.compile(r"^DEMO-SRC-\d{3}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

MARKETS = {"KOSPI", "KOSDAQ"}
STANCES = {"긍정 시각", "부정 시각"}
TOP_KEYS = {
    "scenario_id", "as_of", "is_synthetic", "instrument", "price", "volume",
    "holding", "cash", "portfolio_total_value", "plan", "disclosures",
    "interpretations", "trade_date", "community_buzz",
}
REQUIRED_KEYS = TOP_KEYS - {"community_buzz"}  # community_buzz만 선택(계약 §3.1)
PLAN_KEYS = {"horizon", "max_loss_pct", "review_condition", "recorded_at"}

# 계약 §5.2 / §5.2-b / §5.2-c 의 골든값 전제 — 여기서 어긋나면 골든값 표 전체가 무효
GOLDEN_PREMISES = {
    "loss8": dict(close=46000, prev_close=50000, change_pct=-8.0, qty=30,
                  avg_price=50000, total=4_900_000, cash=0,
                  trade_date="2026-07-17", plan_is_null=False),
    "profit15": dict(close=46000, prev_close=44000, change_pct=4.5, qty=20,
                     avg_price=40000, total=4_900_000, cash=0,
                     trade_date="2026-07-17", plan_is_null=False),
    "first_buy": dict(close=46000, prev_close=45500, change_pct=1.1, qty=0,
                      avg_price=None, total=1_000_000, cash=1_000_000,
                      trade_date="2026-07-17", plan_is_null=True),
}


def is_pos_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def is_nonneg_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def validate_fixture(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"JSON 로드 실패: {exc}"]

    keys = set(data.keys())
    for missing in sorted(REQUIRED_KEYS - keys):
        errors.append(f"필수 필드 누락: {missing}")
    for unknown in sorted(keys - TOP_KEYS):
        errors.append(f"계약에 없는 필드: {unknown} (계약 §3.1이 단일 기준 — 계약을 먼저 갱신할 것)")
    if errors:
        return errors  # 구조가 깨졌으면 이후 검사는 무의미

    sid = data["scenario_id"]
    if f"scenario_{sid}.json" != path.name:
        errors.append(f"scenario_id({sid})와 파일명({path.name}) 불일치")

    if data["is_synthetic"] is not True:
        errors.append("is_synthetic은 데모에서 항상 true여야 함 (화면 '교육용 가상 데이터' 배지 트리거)")

    if not (isinstance(data["as_of"], str) and AS_OF_RE.match(data["as_of"])):
        errors.append(f"as_of 형식 오류: {data['as_of']!r} (규격: 'YYYY-MM-DD HH:mm KST')")

    inst = data["instrument"]
    if not (isinstance(inst, dict) and isinstance(inst.get("code"), str) and inst.get("code")
            and isinstance(inst.get("name"), str) and inst.get("name")):
        errors.append("instrument.code/name 오류")
    if inst.get("market") not in MARKETS:
        errors.append(f"instrument.market 오류: {inst.get('market')!r} (허용: {sorted(MARKETS)} — 세목 산정 근거)")

    price = data["price"]
    if not (is_pos_int(price.get("close")) and is_pos_int(price.get("prev_close"))):
        errors.append("price.close/prev_close는 양의 정수(원)")
    elif isinstance(price.get("change_pct"), (int, float)):
        expected = round((price["close"] - price["prev_close"]) / price["prev_close"] * 100, 1)
        if abs(expected - float(price["change_pct"])) > 1e-9:
            errors.append(f"change_pct 불일치: 기재 {price['change_pct']} vs 계산 {expected}")
    else:
        errors.append("price.change_pct 타입 오류(소수 1자리 수치)")

    vol = data["volume"]
    if not (is_pos_int(vol.get("today")) and is_pos_int(vol.get("avg20"))):
        errors.append("volume.today/avg20는 양의 정수")
    elif isinstance(vol.get("ratio"), (int, float)):
        expected = round(vol["today"] / vol["avg20"], 1)
        if abs(expected - float(vol["ratio"])) > 1e-9:
            errors.append(f"volume.ratio 불일치: 기재 {vol['ratio']} vs 계산 {expected}")
    else:
        errors.append("volume.ratio 타입 오류")

    hold = data["holding"]
    if not is_nonneg_int(hold.get("qty")):
        errors.append("holding.qty는 0 이상 정수 (first_buy만 0)")
    elif hold["qty"] == 0:
        if hold.get("avg_price") is not None:
            errors.append("holding.qty=0이면 avg_price는 null(계약 §3.1)")
    elif not is_pos_int(hold.get("avg_price")):
        errors.append("holding.avg_price는 양의 정수(원)")

    if not is_nonneg_int(data["cash"]):
        errors.append("cash는 0 이상 정수(원)")
    if not is_pos_int(data["portfolio_total_value"]):
        errors.append("portfolio_total_value는 양의 정수(원)")

    plan = data["plan"]
    if plan is not None:
        if not (isinstance(plan, dict) and PLAN_KEYS <= set(plan.keys())):
            errors.append(f"plan 필드 누락(필요: {sorted(PLAN_KEYS)}) — 계획 없음은 null로 표현")
        elif not (isinstance(plan.get("recorded_at"), str) and DATE_RE.match(plan["recorded_at"])):
            errors.append("plan.recorded_at 형식 오류(YYYY-MM-DD)")

    disc = data["disclosures"]
    if not (isinstance(disc, list) and disc):
        errors.append("disclosures는 1건 이상 배열 (공시 없음 시나리오는 계약 §8 '확인된 공시 없음' 규칙으로 별도 설계)")
    else:
        for i, d in enumerate(disc):
            if not (isinstance(d, dict) and isinstance(d.get("text"), str) and d.get("text")):
                errors.append(f"disclosures[{i}].text 오류")
            if not (isinstance(d.get("source_id"), str) and SRC_RE.match(d["source_id"])):
                errors.append(f"disclosures[{i}].source_id 오류: {d.get('source_id')!r} (규격 DEMO-SRC-###)")
            if not (isinstance(d.get("published_at"), str) and AS_OF_RE.match(d["published_at"])):
                errors.append(f"disclosures[{i}].published_at 형식 오류")

    interp = data["interpretations"]
    if not (isinstance(interp, list) and interp):
        errors.append("interpretations 배열 누락")
    else:
        stances = set()
        for i, item in enumerate(interp):
            if not (isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("text")):
                errors.append(f"interpretations[{i}].text 오류")
            if item.get("stance") not in STANCES:
                errors.append(f"interpretations[{i}].stance 오류: {item.get('stance')!r}")
            else:
                stances.add(item["stance"])
        if stances != STANCES:
            errors.append(f"양면 해석 강제 위반: 존재하는 stance={sorted(stances)} (긍정·부정 모두 필요 — 계약 §3.1)")

    td = data["trade_date"]
    if not (isinstance(td, str) and DATE_RE.match(td)):
        errors.append(f"trade_date 형식 오류: {td!r}")
    elif date.fromisoformat(td).weekday() >= 5:
        errors.append(f"trade_date가 주말: {td} (모의 체결 기준일은 영업일)")

    buzz = data.get("community_buzz")
    if buzz is not None and not (isinstance(buzz, dict)
                                 and isinstance(buzz.get("level"), str)
                                 and isinstance(buzz.get("note"), str)):
        errors.append("community_buzz는 {level, note} 형식(선택 필드)")

    premise = GOLDEN_PREMISES.get(sid)
    if premise is None:
        errors.append(f"알 수 없는 scenario_id: {sid} (계약 §5.2에 골든 전제 없음 — 계약을 먼저 확장할 것)")
    else:
        checks = [
            ("price.close", price.get("close"), premise["close"]),
            ("price.prev_close", price.get("prev_close"), premise["prev_close"]),
            ("price.change_pct", price.get("change_pct"), premise["change_pct"]),
            ("holding.qty", hold.get("qty"), premise["qty"]),
            ("holding.avg_price", hold.get("avg_price"), premise["avg_price"]),
            ("portfolio_total_value", data.get("portfolio_total_value"), premise["total"]),
            ("cash", data.get("cash"), premise["cash"]),
            ("trade_date", td, premise["trade_date"]),
            ("plan is null", plan is None, premise["plan_is_null"]),
        ]
        for label, actual, expected in checks:
            if actual != expected:
                errors.append(f"골든 전제 불일치 [{label}]: fixture={actual!r} vs 계약={expected!r}")

    return errors


def report_manifest() -> tuple[str, bool]:
    """manifest 상태 문자열과 유효 여부. 파일 부재는 실패가 아니라 'fixture 단독 모드'(계약 §3.2)."""
    if not MANIFEST_PATH.exists():
        return "manifest 없음 → fixture 단독 모드 (정상 — as_of 미표시 규칙 적용)", True
    try:
        m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"manifest 손상: {exc}", False
    problems = []
    if not (isinstance(m.get("collected_at"), str) and AS_OF_RE.match(m["collected_at"])):
        problems.append("collected_at 형식")
    if not (isinstance(m.get("source"), str) and m.get("source")):
        problems.append("source")
    if not isinstance(m.get("success"), bool):
        problems.append("success(bool)")
    if not (isinstance(m.get("sha256"), str) and SHA256_RE.match(m["sha256"])):
        problems.append("sha256(64 hex)")
    if not isinstance(m.get("items"), list):
        problems.append("items(list)")
    if problems:
        return f"manifest 필드 오류: {', '.join(problems)}", False
    mode = "스냅샷 사용 가능(as_of 표시 허용)" if m["success"] else "success=false → fixture 단독 모드"
    return f"manifest 유효 — {mode}", True


def main() -> int:
    fixtures = sorted(FIXTURE_DIR.glob("scenario_*.json"))
    if not fixtures:
        print(f"FAIL: fixture 없음 ({FIXTURE_DIR})")
        return 1

    all_ok = True
    for path in fixtures:
        errors = validate_fixture(path)
        if errors:
            all_ok = False
            print(f"FAIL {path.name}")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"PASS {path.name}")

    expected = {f"scenario_{sid}.json" for sid in GOLDEN_PREMISES}
    actual = {p.name for p in fixtures}
    if actual != expected:
        all_ok = False
        print(f"FAIL 시나리오 구성 불일치: 기대 {sorted(expected)} vs 실제 {sorted(actual)}")

    manifest_msg, manifest_ok = report_manifest()
    print(("PASS " if manifest_ok else "FAIL ") + manifest_msg)
    all_ok = all_ok and manifest_ok

    print("결과: " + ("전건 통과" if all_ok else "실패 있음 — 계약 §3·§5와 대조해 fixture(또는 계약)를 수정할 것"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
