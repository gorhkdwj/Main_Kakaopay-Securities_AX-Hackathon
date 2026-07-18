# -*- coding: utf-8 -*-
"""실종목 시나리오 어댑터 — 동결 스냅샷 → fixture 변환 (계약 §3.1-b, D-0718-1110).

`data/snapshots/stock_{티커숫자}_*.json`(최신 1개)을 읽어
`data/fixtures/scenario_real_{티커숫자}.json`을 생성한다.

원칙(계약 §3.1-b · 헌법 §4 계산·생성 분리):
- **수기 숫자 입력 금지** — 가격·거래량·시총·52주 고저·평단·예정일 전부
  스냅샷에서 파생한다. 이 파일의 숫자 상수는 계좌성 모의 값(보유수량·예수금
  ·계획 한도)뿐이며, 전부 `[데모 고정]` 교육용 서사 값이다(실서비스 전 재검토).
- 평단(avg_price)은 지어내지 않고 **스냅샷 시계열 안의 실제 과거 종가**
  (기본: 60거래일 전)를 자동 선택한다. plan.recorded_at·past_records.recorded_at도
  같은 시점의 실제 거래일이다.
- 권유성 필드(recommendation*·target*·upgrades_downgrades·애널리스트 의견)는
  수집기(collect_stock_snapshot.py)의 화이트리스트가 1차 차단하고, 여기서도
  저장 직전 금지 키 재귀 스캔으로 2차 차단한다(발견 시 생성 중단).
- 실공시 원문은 yfinance 미제공 — disclosures는 **측정 사실 카드**(52주 고저·
  거래량 vs 평균·섹터/산업·공시된 실적 예정일)로 대체한다(§3.1-b).
  source_id는 `YF-SRC-001`부터 부여, published_at=collected_at.
- 실적 예정일은 "예정일이 공시되어 있다" 서술까지만(§14 — 미래 발표를 확정
  사실처럼 쓰지 않는다).

사용법: .venv\\Scripts\\python.exe scripts\\data\\build_real_scenario.py [티커숫자]
        (기본 005930)
검증:   .venv\\Scripts\\python.exe scripts\\data\\validate_fixture.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows 콘솔(cp949)에서 한글·특수문자 출력 크래시 방지
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
FIXTURE_DIR = ROOT / "data" / "fixtures"

#: 티커 접미사 → 상장시장(계약 §3.1-b — 세목 산정 근거)
MARKET_BY_SUFFIX = {"KS": "KOSPI", "KQ": "KOSDAQ"}

#: 시계열 최소 실길이(계약 §3.1-b — 목표 250, 부족 시 ≥30 허용)
HISTORY_MIN = 30

# ── 계좌성 모의 값 `[데모 고정]`(계약 §3.1-b — 교육용 시연 서사, 숫자 파생 아님) ──
DEMO_HOLDING_QTY = 20            # 보유수량(모의)
DEMO_CASH = 3_000_000            # 가용 예수금(모의 — 매수 미리보기 10주(약 255만원+수수료)가
                                 # 시연에서 성립하도록 가상 3종(100만원)보다 높게 설정)
AVG_PRICE_OFFSET = 60            # 평단 = 60거래일 전 '실제' 종가를 자동 선택
DEMO_PLAN = {                    # 투자 계획(모의 — recorded_at은 평단 시점 실거래일)
    "horizon": "1년",
    "max_loss_pct": -15,
    "review_condition": "실적 2개 분기 연속 악화",
}
#: 매수 일지(모의) — 사용자 자신의 글 프레임(guard 검사 대상 아님·인용 렌더).
#: 권유 표현·숫자 없이 계획(plan)과 정합하는 한 문장.
DEMO_BUY_REASON = (
    "주력 제품 수요가 회복된다는 기사를 읽고 일 년 정도 보유할 생각으로 매수함. "
    "실적이 두 분기 연속 나빠지면 다시 검토하기로 나와 약속함."
)

# ── 금지 키 2차 게이트(수집기와 동일 패턴 — 계약 §3.1-b 금지 목록) ──
FORBIDDEN_KEY_PATTERNS = ("recommendation", "target", "upgrade", "downgrade", "analyst")


def scan_forbidden_keys(obj, path: str = "$") -> list[str]:
    """payload 내 금지 패턴 키 경로 목록(대소문자 무시). 비어 있어야 저장 가능."""
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(p in kl for p in FORBIDDEN_KEY_PATTERNS):
                hits.append(f"{path}.{k}")
            hits.extend(scan_forbidden_keys(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(scan_forbidden_keys(v, f"{path}[{i}]"))
    return hits


def to_pos_int(value, label: str) -> int:
    """스냅샷 수치를 양의 정수(원·주)로 변환 — 정수가 아니면 중단(반올림 왜곡 방지)."""
    f = float(value)
    iv = int(round(f))
    if abs(f - iv) > 1e-6:
        raise SystemExit(f"오류: {label}={value!r}는 정수가 아님 — 원 단위 정합 확인 필요")
    if iv <= 0:
        raise SystemExit(f"오류: {label}={value!r}는 양수가 아님(§3.1-b 정합 규칙 위반)")
    return iv


def latest_snapshot(code: str) -> Path:
    paths = sorted(SNAPSHOT_DIR.glob(f"stock_{code}_*.json"))
    if not paths:
        raise SystemExit(
            f"오류: data/snapshots/stock_{code}_*.json 없음 — "
            "collect_stock_snapshot.py를 먼저 실행할 것(실패 시 가상 fixture 폴백)")
    return paths[-1]


def main() -> int:
    code = sys.argv[1] if len(sys.argv) > 1 else "005930"
    snap_path = latest_snapshot(code)
    snap = json.loads(snap_path.read_text(encoding="utf-8"))

    ticker = snap["ticker"]                      # 예: "005930.KS"
    suffix = ticker.rsplit(".", 1)[-1]
    market = MARKET_BY_SUFFIX.get(suffix)
    if market is None:
        raise SystemExit(f"오류: 지원하지 않는 티커 접미사 {suffix!r}(.KS/.KQ만 — §3.1-b)")

    info = snap.get("info") or {}
    hist = snap["history"]
    dates: list[str] = hist["dates"]
    closes = [to_pos_int(v, f"history.closes[{i}]") for i, v in enumerate(hist["closes"])]
    if len(closes) < HISTORY_MIN or len(closes) != len(dates):
        raise SystemExit(f"오류: 시계열 길이 이상(closes {len(closes)} · dates {len(dates)})")

    close, prev_close = closes[-1], closes[-2]
    # 스냅샷 price 블록과 교차 검증(원천 단일화 확인)
    if close != to_pos_int(snap["price"]["close"], "price.close") or \
            prev_close != to_pos_int(snap["price"]["prev_close"], "price.prev_close"):
        raise SystemExit("오류: 스냅샷 price와 history 꼬리 불일치 — 스냅샷 재수집 필요")
    change_pct = round((close - prev_close) / prev_close * 100, 1)

    today_vol = to_pos_int(snap["price"]["volume"], "price.volume")
    if "averageVolume" not in info:
        raise SystemExit("오류: info.averageVolume 없음 — volume.avg20 파생 불가(§3.1-b)")
    avg20 = to_pos_int(info["averageVolume"], "info.averageVolume")
    ratio = round(today_vol / avg20, 1)

    if "marketCap" not in info:
        raise SystemExit("오류: info.marketCap 없음 — instrument.market_cap 파생 불가")
    market_cap = to_pos_int(info["marketCap"], "info.marketCap")

    if len(closes) <= AVG_PRICE_OFFSET:
        raise SystemExit(f"오류: 시계열 {len(closes)}개 ≤ 평단 오프셋 {AVG_PRICE_OFFSET}")
    idx = -(AVG_PRICE_OFFSET + 1)
    avg_price, buy_date = closes[idx], dates[idx]   # 실제 과거 종가·실제 거래일

    name = info.get("longName") or info.get("shortName") or ticker
    collected_at = snap["collected_at"]
    end_date = hist["end_date"]

    # ── 측정 사실 카드(disclosures 대체 — §3.1-b, source_id YF-SRC-001부터) ──
    disclosures: list[dict] = []

    def add_card(text: str) -> None:
        disclosures.append({
            "text": text,
            "source_id": f"YF-SRC-{len(disclosures) + 1:03d}",
            "published_at": collected_at,
        })

    hi, lo = info.get("fiftyTwoWeekHigh"), info.get("fiftyTwoWeekLow")
    if hi is not None and lo is not None:
        add_card(f"52주 최고가 {to_pos_int(hi, '52주 최고가'):,}원 · "
                 f"52주 최저가 {to_pos_int(lo, '52주 최저가'):,}원")
    add_card(f"직전 거래일 거래량 {today_vol:,}주 — 최근 평균 거래량 "
             f"{avg20:,}주(평균의 {ratio}배)")
    sector, industry = info.get("sector"), info.get("industry")
    if sector and industry:
        add_card(f"섹터 {sector} · 산업 {industry} — Yahoo Finance 분류(영문 원문)")
    earnings_dates = snap.get("earnings_dates") or []
    if earnings_dates:
        add_card(f"다음 실적 발표 예정일이 {earnings_dates[0]}로 공시되어 있음 — "
                 "회사 IR 일정")
    if not disclosures:
        raise SystemExit("오류: 측정 사실 카드 0건 — disclosures는 1건 이상 필요(§3.1)")

    # ── 해석 양면(§3.1 강제) — 스냅샷 사실(52주 고저 카드) 근거, 숫자·결론 없음 ──
    if not (hi is not None and lo is not None
            and to_pos_int(lo, "lo") < close < to_pos_int(hi, "hi")):
        raise SystemExit("오류: 52주 고저 기반 양면 해석 전제 불충족 — 해석 문안 재설계 필요")
    interpretations = [
        {
            "text": "현재가가 지난 일 년 최저가보다는 상당히 위에 있어, 장기 저점과 "
                    "견주면 여유가 남아 있다고 보는 시각이 있어요 — 사실 확인은 위 "
                    "52주 고저 카드에서 할 수 있어요.",
            "stance": "긍정 시각",
        },
        {
            "text": "현재가가 지난 일 년 최고가에서 크게 내려와 있어, 하락 추세의 "
                    "부담이 남아 있다고 보는 시각이 있어요 — 어느 쪽이 맞는지는 "
                    "앞으로의 실적·수급에서 확인돼요.",
            "stance": "부정 시각",
        },
    ]

    fixture = {
        "scenario_id": f"real_{code}",
        "as_of": collected_at,
        "is_synthetic": False,
        "data_origin": {
            "source": snap["source"],
            "collected_at": collected_at,
            "delay_note": snap["delay_note"],
            "snapshot_ref": snap_path.name,
        },
        "instrument": {
            "code": ticker,
            "name": name,
            "market": market,
            "market_cap": market_cap,
        },
        "price": {
            "close": close,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "history": {
                "unit": "trading_day",
                "end_date": end_date,
                "closes": closes,
            },
        },
        "volume": {"today": today_vol, "avg20": avg20, "ratio": ratio},
        "holding": {"qty": DEMO_HOLDING_QTY, "avg_price": avg_price},
        "cash": DEMO_CASH,
        # 정합 계산(§3.1-b): 총자산 = 보유 평가 + 현금 — 수기 입력 아님
        "portfolio_total_value": DEMO_HOLDING_QTY * close + DEMO_CASH,
        "plan": {**DEMO_PLAN, "recorded_at": buy_date},
        "disclosures": disclosures,
        "interpretations": interpretations,
        "trade_date": end_date,   # 스냅샷 기준 최근 거래일(§3.1-b)
        "past_records": [
            {
                "recorded_at": buy_date,
                "side": "buy",
                "qty": DEMO_HOLDING_QTY,
                "reason_text": DEMO_BUY_REASON,
            }
        ],
    }

    hits = scan_forbidden_keys(fixture)
    if hits:
        print(f"오류: 금지 키 검출 — 생성 중단(계약 §3.1-b): {hits}", file=sys.stderr)
        return 1

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FIXTURE_DIR / f"scenario_real_{code}.json"
    out_path.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"생성 완료: {out_path.relative_to(ROOT)}"
          f" · close={close:,} prev={prev_close:,} change_pct={change_pct}"
          f" · closes {len(closes)}개({dates[0]}~{end_date})"
          f" · avg_price={avg_price:,}({buy_date} 실제 종가)"
          f" · 사실 카드 {len(disclosures)}건 · 원천={snap_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
