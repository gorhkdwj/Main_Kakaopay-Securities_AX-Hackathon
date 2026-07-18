# -*- coding: utf-8 -*-
"""가상 가격 시계열 생성기 — fixture price.history 주입 (계약 §3.1 [데모 고정]).

고정 seed 결정론 생성기: 재실행해도 동일한 출력이 나온다. 시나리오별 서사 앵커
(매수일 평단·전일 종가·당일 종가)를 지나는 구간 선형 보간 + 소폭 노이즈로
250 연속 거래일(주말 제외 — 계약 §13 결제일 규칙과 동일 가정) 종가를 만든다.

시계열은 재현 화면 차트·기간 칩의 장식 렌더 전용이며 판단 재료·금액 계산에
쓰이지 않는다(계산·생성 분리와 무관한 장식 데이터).

사용법: .venv\\Scripts\\python.exe scripts\\data\\gen_price_history.py
"""
from __future__ import annotations

import datetime as dt
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "data" / "fixtures"

END_DATE = dt.date(2026, 7, 17)  # trade_date — 모든 시점이 as_of(07-17 15:30) 이전
N = 250  # 연속 거래일 수 (1년 치)
TICK = 50  # 호가 단위(원) — 표시 자연스러움용 반올림


def trading_days(end: dt.date, n: int) -> list[dt.date]:
    days: list[dt.date] = []
    d = end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= dt.timedelta(days=1)
    return list(reversed(days))


DAYS = trading_days(END_DATE, N)
IDX = {d: i for i, d in enumerate(DAYS)}


def idx_of(iso: str) -> int:
    """해당 날짜(주말이면 다음 평일)의 시계열 인덱스."""
    d = dt.date.fromisoformat(iso)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return IDX[d]


def build_series(anchors: list[tuple[int, int, float]], seed: str) -> list[int]:
    """앵커 (인덱스, 가격, 다음 구간 노이즈 비율) 사이를 선형 보간 + 노이즈.

    앵커 지점 자체는 정확히 그 가격으로 고정된다(노이즈 없음).
    """
    rng = random.Random(seed)
    closes: list[int] = [0] * N
    anchors = sorted(anchors)
    assert anchors[0][0] == 0 and anchors[-1][0] == N - 1, "앵커가 양 끝을 덮어야 함"
    for (i0, p0, noise), (i1, p1, _) in zip(anchors, anchors[1:]):
        for i in range(i0, i1 + 1):
            t = (i - i0) / (i1 - i0)
            base = p0 + (p1 - p0) * t
            if i in (i0, i1):
                v = p0 if i == i0 else p1
            else:
                v = base * (1 + rng.gauss(0, noise))
                v = round(v / TICK) * TICK
            closes[i] = int(v)
    return closes


PURCHASE = {"loss8": "2026-03-02", "profit15": "2026-05-11"}

SCENARIOS: dict[str, dict] = {
    # 급락: 1년 완만 등락(47k~53k) → 매수일(3/2) 50,000 → 최근 한 달 50,000 부근
    # 안정 → 마지막 날 -8% 절벽(46,000)
    "loss8": {
        "anchors": [
            (0, 52000, 0.008),
            (45, 48500, 0.008),
            (95, 52500, 0.008),
            (idx_of("2026-03-02"), 50000, 0.006),
            (N - 55, 49500, 0.005),
            (N - 24, 50000, 0.0025),  # 급락 직전 한 달: 낮은 변동으로 평탄
            (N - 2, 50000, 0.0),      # prev_close
            (N - 1, 46000, 0.0),      # close (-8.0%)
        ],
        "checks": {"window_lo": 48800, "window_hi": 51200},
    },
    # 상승: 1년 전 36,000 저점권 → 매수일(5/11) 40,000 → 꾸준한 우상향 →
    # 전일 44,000 → 마지막 날 +4.5%(46,000). 평단 대비 +15% 도달 서사.
    "profit15": {
        "anchors": [
            (0, 36000, 0.007),
            (60, 37500, 0.007),
            (110, 36500, 0.007),
            (idx_of("2026-05-11"), 40000, 0.004),
            (N - 30, 42000, 0.004),
            (N - 2, 44000, 0.0),      # prev_close
            (N - 1, 46000, 0.0),      # close (+4.5%)
        ],
        "checks": {},
    },
    # 첫 주문: 1년 내내 42k~47k 박스권 횡보(방향성 없음) → 45,500 → 46,000(+1.1%)
    "first_buy": {
        "anchors": [
            (0, 45000, 0.007),
            (35, 42800, 0.007),
            (75, 46500, 0.007),
            (115, 43500, 0.007),
            (155, 46800, 0.007),
            (195, 42500, 0.007),
            (225, 45200, 0.005),
            (N - 2, 45500, 0.0),      # prev_close
            (N - 1, 46000, 0.0),      # close (+1.1%)
        ],
        "checks": {},
    },
}


def self_check(sid: str, closes: list[int], price: dict) -> None:
    assert len(closes) == N, f"{sid}: 길이 {len(closes)}"
    assert closes[-1] == price["close"], f"{sid}: 마지막 != close"
    assert closes[-2] == price["prev_close"], f"{sid}: [-2] != prev_close"
    assert all(isinstance(v, int) and v > 0 for v in closes), f"{sid}: 비양수/비정수"
    day_pct = round((closes[-1] - closes[-2]) / closes[-2] * 100, 1)
    assert day_pct == price["change_pct"], f"{sid}: 1일 수익률 {day_pct} != change_pct"
    if sid in PURCHASE:
        i = idx_of(PURCHASE[sid])
        avg = {"loss8": 50000, "profit15": 40000}[sid]
        assert closes[i] == avg, f"{sid}: 매수일 가격 {closes[i]} != 평단 {avg}"
    ck = SCENARIOS[sid]["checks"]
    if ck:  # loss8: 급락 직전 한 달 평탄 구간 검증
        window = closes[-23:-1]
        assert min(window) >= ck["window_lo"] and max(window) <= ck["window_hi"], (
            f"{sid}: 직전 한 달 창 {min(window)}~{max(window)} 평탄 범위 이탈"
        )


def compact_closes(text: str) -> str:
    """json.dumps(indent=2)가 한 줄에 하나씩 펼친 closes 배열을 10개/줄로 압축."""
    def repl(m: re.Match) -> str:
        nums = re.findall(r"-?\d+", m.group(1))
        lines = [
            "        " + ", ".join(nums[i : i + 10]) for i in range(0, len(nums), 10)
        ]
        return '"closes": [\n' + ",\n".join(lines) + "\n      ]"

    return re.sub(r'"closes": \[([^\]]+)\]', repl, text)


def main() -> int:
    for sid, spec in SCENARIOS.items():
        path = FIXTURE_DIR / f"scenario_{sid}.json"
        fx = json.loads(path.read_text(encoding="utf-8"))
        closes = build_series(spec["anchors"], seed=f"decision-passport/{sid}")
        self_check(sid, closes, fx["price"])
        fx["price"]["history"] = {
            "unit": "trading_day",
            "end_date": END_DATE.isoformat(),
            "closes": closes,
        }
        text = json.dumps(fx, ensure_ascii=False, indent=2) + "\n"
        path.write_text(compact_closes(text), encoding="utf-8")
        # 기간 칩 참고 출력(1일/1주/1달/3달/1년)
        chips = {
            k: round((closes[-1] - closes[-1 - o]) / closes[-1 - o] * 100, 1)
            for k, o in [("1d", 1), ("1w", 5), ("1m", 21), ("3m", 63), ("1y", 249)]
        }
        print(f"{sid}: OK · chips={chips} · min={min(closes)} max={max(closes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
