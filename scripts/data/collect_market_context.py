# -*- coding: utf-8 -*-
"""시장 맥락 스냅샷 수집기 — W4 실데이터 수집 (계약 §3.2, D-0718-1110).

거시 지표 7종(^KS11 코스피 등)의 최근 2거래일 종가를 yfinance로 1회 수집해
`data/snapshots/market_context_YYYYMMDD_HHMM.json`으로 동결한다.

- 부분 실패 허용: 성공 항목만 items에 저장, 실패는 stderr 경고(계약 §3.2 안전 강등
  — 항목 부재 시 해당 카드 미표시).
- 시세는 거래소 지연(최대 20분) — delay_note를 항상 포함(리서치
  `docs/research/2026-07-18_yfinance_활용판단.md` §1).
- 종가·전일·등락률만 수집한다(방향성·권유성 데이터 없음 — 리서치 §2(a) 화이트리스트).
- VKOSPI는 Yahoo 미제공(실증) → ^VIX 사용, 화면에서 "미국 지표 참고" 병기(계약 §3.2).

사용법: .venv\\Scripts\\python.exe scripts\\data\\collect_market_context.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import yfinance as yf

# Windows 콘솔(cp949)에서 한글·특수문자 출력 크래시 방지
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = ROOT / "data" / "snapshots"

KST = dt.timezone(dt.timedelta(hours=9), "KST")
SOURCE = "Yahoo Finance via yfinance"
DELAY_NOTE = "거래소 시세 지연(최대 20분) — 실시간 아님"
RETRIES = 2  # 항목당 최대 시도 횟수(전체 실패 시 가상 fixture 백업 경로가 있음 — §3.1-b)

# 계약 §3.2 market_context items 키 ↔ Yahoo 티커 (리서치 §2(a))
TICKERS: dict[str, str] = {
    "kospi": "^KS11",
    "kosdaq": "^KQ11",
    "kospi200": "^KS200",
    "sp500": "^GSPC",
    "usdkrw": "KRW=X",
    "ust10y": "^TNX",
    "vix": "^VIX",
}


def fetch_item(ticker: str) -> dict:
    """최근 2거래일 종가 → {value, prev, change_pct}. 실패 시 예외.

    auto_adjust=False: 배당·분할 보정 없는 실제 종가(지수·환율은 영향 없으나
    수집 정책을 종목 수집기와 통일).
    """
    last_exc: Exception | None = None
    for _ in range(RETRIES):
        try:
            hist = yf.Ticker(ticker).history(
                period="10d", interval="1d", auto_adjust=False
            )
            closes = [float(v) for v in hist["Close"].dropna().tolist()]
            if len(closes) < 2:
                raise ValueError(f"종가 {len(closes)}건 — 2거래일 미만")
            value, prev = closes[-1], closes[-2]
            return {
                "value": round(value, 4),
                "prev": round(prev, 4),
                "change_pct": round((value - prev) / prev * 100, 2),
            }
        except Exception as exc:  # noqa: BLE001 — 부분 실패 허용 경로
            last_exc = exc
    raise RuntimeError(str(last_exc))


def main() -> int:
    now = dt.datetime.now(KST)
    items: dict[str, dict] = {}
    failed: list[str] = []
    for key, ticker in TICKERS.items():
        try:
            items[key] = fetch_item(ticker)
            print(f"{key} ({ticker}): OK · value={items[key]['value']} "
                  f"change_pct={items[key]['change_pct']}")
        except Exception as exc:  # noqa: BLE001
            failed.append(key)
            print(f"경고: {key} ({ticker}) 수집 실패 — {exc}", file=sys.stderr)

    if not items:
        print("오류: 전 항목 수집 실패 — 스냅샷 미생성(가상 fixture 폴백 경로 사용)",
              file=sys.stderr)
        return 1

    snapshot = {
        "as_of": now.strftime("%Y-%m-%d %H:%M KST"),
        "source": SOURCE,
        "delay_note": DELAY_NOTE,
        "items": items,
    }
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"market_context_{now.strftime('%Y%m%d_%H%M')}.json"
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"동결 완료: {path.relative_to(ROOT)} · 성공 {len(items)}/{len(TICKERS)}"
          + (f" · 실패 {failed}" if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
