# -*- coding: utf-8 -*-
"""실종목 스냅샷 수집기 — W4 실데이터 수집 (계약 §3.1-b·§3.2, D-0718-1110).

yfinance에서 **화이트리스트 필드만** 추출해
`data/snapshots/stock_{티커숫자}_YYYYMMDD_HHMM.json`으로 1회 동결한다.
이 파일이 실종목 fixture(§3.1-b)의 유일 원천이며, 동결 후 원본 수정 금지(헌법 §7
— 파생은 어댑터 `build_real_scenario.py` 산출물로).

권유성 필드 금지(계약 §3.1-b 금지 목록, 리서치 §2(d)):
recommendation*(recommendationMean·recommendationKey 등)·target*(targetMeanPrice
·targetHighPrice 등)·upgrades_downgrades·애널리스트 의견(numberOfAnalystOpinions
·averageAnalystRating 등)은 **수집·저장·표시 전부 금지**. 강제 방식은 이중 게이트:
① 화이트리스트 추출(아래 INFO_WHITELIST 외 info 키는 아예 읽지 않음)
② 저장 직전 FORBIDDEN_KEY_PATTERNS 재귀 스캔(발견 시 저장 중단).

- history는 period='2y', interval='1d', **auto_adjust=False**: 배당·분할 보정 없는
  실제 거래 종가(Close)를 쓴다 — §3.1-b 정합 규칙(closes[-1]==close·closes[-2]==
  prev_close)상 화면 현재가와 시계열 마지막 값이 동일한 실종가여야 하기 때문.
  마지막 250거래일만 동결(목표 250, 실길이 ≥30 허용 — §3.1-b).
- 최근 종가·전일 종가·당일 거래량은 같은 history 꼬리에서 파생(수기 숫자 입력 금지).
- calendar의 실적 예정일은 "회사가 예정일을 공시했다" 서술 전용 문자열(§14 정합
  — 미래 발표를 확정 사실처럼 쓰지 않는다).

사용법: .venv\\Scripts\\python.exe scripts\\data\\collect_stock_snapshot.py [티커]
        (기본 005930.KS)
"""
from __future__ import annotations

import datetime as dt
import json
import re
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
RETRIES = 2  # 최대 시도 횟수(전체 실패 시 가상 fixture 백업 경로 — §3.1-b)
HISTORY_TARGET = 250  # 목표 거래일 수(§3.1-b)
HISTORY_MIN = 30  # 허용 최소 실길이(§3.1-b)

# ── 게이트 ①: info 화이트리스트 — 여기 없는 키는 읽지도 저장하지도 않는다 ──
INFO_WHITELIST = (
    "shortName",
    "longName",
    "sector",
    "industry",
    "marketCap",
    "beta",
    "fiftyTwoWeekHigh",
    "fiftyTwoWeekLow",
    "averageVolume",
    "dividendYield",  # 있으면 — yfinance info 원값 그대로(단위 해석은 어댑터 소관)
)

# ── 게이트 ②: 금지 키 패턴 — 산출 payload 전체를 재귀 스캔, 발견 시 저장 중단 ──
# recommendationMean·recommendationKey·targetHighPrice·targetLowPrice·
# targetMeanPrice·targetMedianPrice·upgrades_downgrades·numberOfAnalystOpinions·
# averageAnalystRating 등 권유성 필드 전부 커버(계약 §3.1-b 금지 목록).
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


def with_retry(label: str, fn):
    last_exc: Exception | None = None
    for _ in range(RETRIES):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise RuntimeError(f"{label}: {last_exc}")


def fetch_info(ticker: yf.Ticker) -> dict:
    """info에서 화이트리스트 키만 추출(없는 키·None은 생략)."""
    info = with_retry("info", lambda: ticker.info)
    out = {}
    for key in INFO_WHITELIST:
        value = info.get(key)
        if value is not None:
            out[key] = value
    return out


def fetch_history(ticker: yf.Ticker) -> tuple[list[str], list[float], int]:
    """(dates, closes, last_volume) — auto_adjust=False 실종가, 마지막 250거래일."""
    hist = with_retry(
        "history",
        lambda: ticker.history(period="2y", interval="1d", auto_adjust=False),
    )
    hist = hist.dropna(subset=["Close"]).tail(HISTORY_TARGET)
    if len(hist) < HISTORY_MIN:
        raise RuntimeError(f"history 실길이 {len(hist)} < 허용 최소 {HISTORY_MIN}")
    dates = [idx.date().isoformat() for idx in hist.index]
    closes = [round(float(v), 4) for v in hist["Close"].tolist()]
    if not all(v > 0 for v in closes):
        raise RuntimeError("closes에 비양수 값 존재(§3.1-b 정합 규칙 위반)")
    last_volume = int(hist["Volume"].iloc[-1])
    return dates, closes, last_volume


def fetch_earnings_dates(ticker: yf.Ticker) -> list[str]:
    """calendar의 공시된 실적 예정일(있으면) — ISO 문자열. 실패는 빈 목록(선택 필드)."""
    try:
        cal = with_retry("calendar", lambda: ticker.calendar)
    except Exception as exc:  # noqa: BLE001
        print(f"경고: calendar 수집 실패(선택 필드) — {exc}", file=sys.stderr)
        return []
    raw = []
    if isinstance(cal, dict):
        raw = cal.get("Earnings Date") or []
    elif cal is not None and hasattr(cal, "to_dict"):  # 구버전 DataFrame 호환
        raw = list(cal.to_dict().get("Earnings Date", {}).values())
    return [d.isoformat() if hasattr(d, "isoformat") else str(d) for d in raw]


def main() -> int:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "005930.KS"
    code = re.sub(r"[^0-9A-Za-z]", "", symbol.split(".")[0])  # 005930.KS → 005930
    now = dt.datetime.now(KST)
    ticker = yf.Ticker(symbol)

    try:
        dates, closes, last_volume = fetch_history(ticker)
    except Exception as exc:  # noqa: BLE001
        print(f"오류: {symbol} history 수집 실패 — 스냅샷 미생성"
              f"(가상 fixture 폴백 경로 사용): {exc}", file=sys.stderr)
        return 1

    try:
        info = fetch_info(ticker)
    except Exception as exc:  # noqa: BLE001
        info = {}
        print(f"경고: {symbol} info 수집 실패 — 시세·시계열만 동결: {exc}",
              file=sys.stderr)

    payload = {
        "ticker": symbol,
        "collected_at": now.strftime("%Y-%m-%d %H:%M KST"),
        "source": SOURCE,
        "delay_note": DELAY_NOTE,
        "info": info,
        "price": {
            # 전부 history 꼬리에서 파생 — §3.1-b 정합 규칙과 원천 단일화
            "close": closes[-1],
            "prev_close": closes[-2],
            "volume": last_volume,
        },
        "history": {
            "period": "2y",
            "interval": "1d",
            "auto_adjust": False,
            "unit": "trading_day",
            "end_date": dates[-1],
            "dates": dates,
            "closes": closes,
        },
    }
    earnings_dates = fetch_earnings_dates(ticker)
    if earnings_dates:
        # 공시된 예정일 서술 전용(§14) — "예정일이 공시되어 있다"까지만
        payload["earnings_dates"] = earnings_dates

    hits = scan_forbidden_keys(payload)
    if hits:
        print(f"오류: 금지 키 검출 — 저장 중단(계약 §3.1-b): {hits}", file=sys.stderr)
        return 1

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"stock_{code}_{now.strftime('%Y%m%d_%H%M')}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"동결 완료: {path.relative_to(ROOT)} · closes {len(closes)}거래일 "
          f"({dates[0]}~{dates[-1]}) · close={closes[-1]} prev={closes[-2]} "
          f"· info {len(info)}키 · earnings_dates {len(earnings_dates)}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
