"""영업일 계산 모듈 — 결제일(D+n) 산출.

기준 계약: docs/requirements-contract.md §4(결제일 D+2)·§11(영업일 총칙).

[데모 고정] 영업일 = 월~금(토·일만 제외)이며 **공휴일은 반영하지 않는다**
(계약 §11·§13 대장 — 데모 기간 2026-07-17~21에 공휴일 없음 확인됨.
실서비스 전 거래소 공휴일 캘린더 연동 재검토 대상).

표준 라이브러리만 사용한다(결정론 원칙 — LLM·네트워크 호출 금지).
"""

from __future__ import annotations

import datetime

__all__ = ["settle_date"]


def _coerce_date(value: "str | datetime.date") -> datetime.date:
    """trade_date 입력을 datetime.date로 정규화한다.

    허용 입력: ``datetime.date`` 또는 ISO 형식 문자열(``YYYY-MM-DD``).
    그 외에는 ValueError를 발생시킨다.
    """
    # datetime.datetime은 date의 서브클래스 — 날짜만 취한다
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        # fromisoformat이 형식 오류 시 ValueError를 발생시킨다
        return datetime.date.fromisoformat(value)
    raise ValueError(
        f"trade_date는 'YYYY-MM-DD' 문자열 또는 date여야 합니다: {value!r}"
    )


def settle_date(trade_date: "str | datetime.date", n: int = 2) -> str:
    """체결일(trade_date)로부터 D+n 영업일의 결제일을 ISO 문자열로 반환한다.

    영업일 규칙(계약 §11): 월~금만 영업일로 세고 **토·일만 제외**한다.
    [데모 고정] 공휴일 미반영 — 모듈 docstring 참조.

    trade_date 자체의 영업일 여부는 검증하지 않는다(계약에 규정 없음).
    다음 날부터 n번째 영업일을 반환한다.

    Args:
        trade_date: 체결 기준일("YYYY-MM-DD" 또는 date).
        n: 더할 영업일 수(0 이상 정수, 기본 2 = D+2).

    Returns:
        결제일 ISO 문자열(``YYYY-MM-DD``). 예: settle_date("2026-07-17", 2)
        → "2026-07-21" (금요일 체결 → 토·일 건너뛰고 월(1)·화(2)).

    Raises:
        ValueError: trade_date 형식이 잘못됐거나 n이 0 이상의 정수가 아닌 경우.
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError(f"n은 0 이상의 정수여야 합니다: {n!r}")
    if n < 0:
        raise ValueError(f"n은 0 이상의 정수여야 합니다: {n!r}")

    day = _coerce_date(trade_date)
    remaining = n
    while remaining > 0:
        day += datetime.timedelta(days=1)
        if day.weekday() < 5:  # 0=월 ~ 4=금 (5=토, 6=일 제외)
            remaining -= 1
    return day.isoformat()
