"""Rebuild a Google Play VOC research sample as CSV on stdout.

This script never writes a file. Use --start/--end (1-based, inclusive) to emit
small, reviewable slices before patching a new snapshot into an evidence ledger.

The checked-in CSV is a frozen access-date snapshot. Because this script queries
the latest upstream reviews, later runs can select different rows as new reviews
arrive or Google Play changes result ordering.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from datetime import datetime

from google_play_scraper import Sort, reviews


APPS = [
    ("kakaopay", "com.kakaopay.app", {"neg": 41, "neu": 23, "pos": 16}),
    ("toss", "viva.republica.toss", {"neg": 20, "neu": 10, "pos": 10}),
]
EXCLUDE_REVIEW_IDS = {"7c12f4e6-1e71-4ea0-b13b-828698a63feb"}
CUTOFF = datetime(2025, 7, 16)

CORE_TERMS = [
    "주식", "증권", "투자", "ETF", "종목", "매수", "매도", "평단", "호가",
    "소수점", "시세", "해외주식", "국내주식", "공모주", "배당", "수익률",
    "예수금", "환전", "주가", "ISA", "체결",
]
SECURITIES_CONTEXT = [
    "거래", "매매", "주문", "계좌", "차트", "수수료", "시세", "호가", "종목",
    "앱", "렉", "오류", "튕김", "매수", "매도", "포트폴리오", "버튼", "화면",
    "UI", "기능", "로딩",
]
THEMES = {
    "decision_risk": ["매수", "매도", "손실", "불안", "판단", "평단", "수익률", "익절", "손절"],
    "execution_order": ["주문", "체결", "취소", "거래", "호가", "시세", "버튼", "지연", "판매"],
    "information": ["정보", "설명", "ETF", "뉴스", "공시", "용어", "차트", "알림", "지표", "표시"],
    "settlement_cost": ["출금", "환전", "수수료", "배당", "예수금", "원화", "달러", "세금"],
    "reliability": ["오류", "먹통", "로그인", "접속", "느림", "로딩", "장애", "렉", "튕김", "멈춤", "서버", "트래픽"],
    "portfolio_history": ["보유", "내역", "평단", "수익률", "포트폴리오", "비중", "종목"],
    "support": ["상담", "FAQ", "고객센터", "답변", "안내", "문의"],
    "social": ["토론", "커뮤니티", "댓글", "인기", "순위", "금손", "주주들"],
    "navigation_ux": ["UI", "화면", "메뉴", "찾", "보이", "폰트", "위젯", "버튼", "불편", "탭", "접근성"],
}


def is_relevant(text: str) -> bool:
    upper = text.upper()
    hits = [term for term in CORE_TERMS if term.upper() in upper]
    if not hits:
        return False
    if len(hits) == 1 and hits[0] == "증권":
        return any(term.upper() in upper for term in SECURITIES_CONTEXT)
    return True


def auto_themes(text: str) -> list[str]:
    upper = text.upper()
    tags = [
        name
        for name, terms in THEMES.items()
        if any(term.upper() in upper for term in terms)
    ]
    return tags or ["other_trade"]


def evenly_spaced(rows: list[dict], quota: int) -> list[dict]:
    ordered = sorted(rows, key=lambda row: row["at"], reverse=True)
    if quota == 1:
        return [ordered[0]]
    indexes = [round(i * (len(ordered) - 1) / (quota - 1)) for i in range(quota)]
    return [ordered[index] for index in indexes]


def collect() -> list[dict]:
    selected: list[dict] = []
    for app_name, app_id, quotas in APPS:
        rows, _ = reviews(
            app_id,
            lang="ko",
            country="kr",
            sort=Sort.NEWEST,
            count=5000,
        )
        eligible = [
            row
            for row in rows
            if row["reviewId"] not in EXCLUDE_REVIEW_IDS
            and row["at"] >= CUTOFF
            and len(row.get("content", "").strip()) >= 12
            and is_relevant(row["content"])
        ]
        strata = {
            "neg": [row for row in eligible if row["score"] <= 2],
            "neu": [row for row in eligible if row["score"] == 3],
            "pos": [row for row in eligible if row["score"] >= 4],
        }
        picked: list[dict] = []
        for stratum, quota in quotas.items():
            picked.extend(evenly_spaced(strata[stratum], quota))
        for row in picked:
            row["_app"] = app_name
            row["_app_id"] = app_id
            row["_stratum"] = (
                "neg" if row["score"] <= 2 else "neu" if row["score"] == 3 else "pos"
            )
            row["_themes"] = auto_themes(row["content"])
        selected.extend(picked)
    return selected


def emit(start: int, end: int, include_header: bool) -> None:
    selected = collect()
    audit_ids = {row["reviewId"] for row in selected[::5]}
    # Supplemental cross-app audit: this KakaoPay-app review describes Toss only.
    rejected_ids = {
        "ac1a296d-55e4-48ed-ad25-f55f3cd02ae6",
        # "번호가" accidentally matched the substring "호가".
        "f6af5346-f9a2-4bff-8ceb-9a54b27935b4",
    }
    audit_ids.update(rejected_ids)
    human_overrides = {
        "2cf95377-fbb6-45f1-b85a-9f0a921170f2": "decision_risk|execution_order|reliability",
        "ac1a296d-55e4-48ed-ad25-f55f3cd02ae6": "reject_cross_app_misattribution",
        "f6af5346-f9a2-4bff-8ceb-9a54b27935b4": "reject_substring_false_positive",
    }
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    if include_header:
        writer.writerow(
            [
                "source_id", "app", "app_id", "platform", "country", "review_id",
                "rating", "review_date", "stratum", "auto_themes", "human_audited",
                "human_relevance", "human_themes", "review_excerpt", "url",
                "accessed_at_kst", "limitations",
            ]
        )
    for index, row in enumerate(selected, 1):
        if not start <= index <= end:
            continue
        content = re.sub(r"\s+", " ", row["content"]).strip()
        excerpt = " ".join(content.split()[:20])
        audited = row["reviewId"] in audit_ids
        tags = "|".join(row["_themes"])
        human_tags = human_overrides.get(row["reviewId"], tags) if audited else ""
        url = (
            "https://play.google.com/store/apps/details?"
            f"id={row['_app_id']}&hl=ko&gl=KR&reviewId={row['reviewId']}"
        )
        writer.writerow(
            [
                f"X-SRC-03{index:03d}", row["_app"], row["_app_id"], "Google Play",
                "KR", row["reviewId"], row["score"], row["at"].date().isoformat(),
                row["_stratum"], tags, "Y" if audited else "N",
                "N" if row["reviewId"] in rejected_ids else "Y" if audited else "",
                human_tags, excerpt, url, "2026-07-16",
                "Recent-1y stratified convenience sample from latest-5000; super-app and self-selection bias; do not generalize theme shares.",
            ]
        )
    print(buffer.getvalue(), end="")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=120)
    parser.add_argument("--header", action="store_true")
    args = parser.parse_args()
    emit(args.start, args.end, args.header)


if __name__ == "__main__":
    main()
