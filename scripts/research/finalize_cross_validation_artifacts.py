"""Apply the Codex re-audit to the Claude WS9 merged ledgers.

The Claude and Codex independent reports/ledgers are immutable inputs.  This
script updates only the two ``*_final.csv`` integration artifacts, records the
explicit adjudications below, and rebuilds the final source-to-claim reverse
links from the final claim ledger.
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "research" / "evidence"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def find_final(first_field: str) -> Path:
    matches: list[Path] = []
    for path in EVIDENCE.glob("*_final.csv"):
        header = path.open("r", encoding="utf-8-sig").readline().lstrip("\ufeff\"")
        if header.startswith(first_field):
            matches.append(path)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one final CSV starting with {first_field}: {matches}")
    return matches[0]


def split_ids(value: str) -> list[str]:
    return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]


def append_unique(value: str, note: str) -> str:
    value = value.strip()
    if note in value:
        return value
    return f"{value}; {note}" if value else note


def normalize_reliability(value: str) -> str:
    value = value.strip()
    if value in {"A", "H", "높음", "높음(원천)"}:
        return "H"
    if value in {"B", "M", "중간", "중간~높음"}:
        return "M"
    if value in {"C", "L", "낮음", "-", ""}:
        return "L"
    return value


def normalize_market(value: str) -> str:
    value = value.strip()
    if value in {"KR", "국내", "한국"}:
        return "KR"
    if value in {"US", "미국", "미국(글로벌ETF)"}:
        return "US"
    if value in {
        "공통",
        "Global",
        "글로벌",
        "국내·미국",
        "국내+미국",
        "KR·US",
    }:
        return "Global"
    return value or "Global"


def normalize_status(value: str) -> str:
    value = value.strip()
    return {
        "included": "채택",
        "확인": "채택",
        "채택": "채택",
        "included_with_limit": "채택(한계)",
        "채택(한계표시)": "채택(한계)",
        "부분확인": "제한",
        "limited": "제한",
        "무관": "기각",
        "rejected": "기각",
        "기각": "기각",
        "접근불가": "접근불가",
        "접근실패": "접근불가",
        "접근제한": "접근불가",
        "inaccessible": "접근불가",
        "미수집": "미수집",
        "not_collected": "미수집",
    }.get(value, value or "채택")


SOURCE_OVERRIDES: dict[str, dict[str, str]] = {
    "X-SRC-0111": {
        "title": "예탁자산 15조 원",
        "evidence_summary": "공식 발표 기준 예탁자산 15조 원",
    },
    "X-SRC-0112": {
        "title": "예탁자산 20조 원",
        "evidence_summary": "2026-05-29 기준 예탁자산 20조 원; 2026-06-02 발표",
    },
    "X-SRC-0114": {
        "title": "국내주식 복귀계좌(RIA) 서비스",
        "evidence_summary": "국내주식 복귀계좌(RIA) 출시 45일 만에 5만 계좌",
        "limitations": "RIA는 이 문맥에서 로보어드바이저가 아니며 상품 채택이 재진입 심리를 직접 입증하지 않음",
    },
    "X-SRC-0210": {
        "status": "기각",
        "rejection_reason": "UCL PDF가 일반 Medical Sciences 페이지로 이동하는 soft 404; C-SRC-0211의 공개 사본과 DOI로 대체",
        "limitations": "WS9 URL 재검사에서 PDF 원문을 반환하지 않음",
    },
    "X-SRC-0515": {
        "title": "디지털취약계층의 정보 접근 및 이용 편의 증진을 위한 고시",
    },
}


CLAIM_OVERRIDES: dict[str, dict[str, str]] = {
    "F-CLM-0008": {
        "claim_statement": "FAQ와 이용안내에는 국내주식 매도대금 출금 D+2영업일, KRX·NXT 구분과 SOR 자동 배분, 배당 기준일, 상품별 출금 가능일 등 시장·상품별 설명이 존재한다.",
        "adjudication_note": "Codex 재검증: D+2를 모든 시장·상품에 일반화하지 않으며 주문 영향 미리보기에는 예상 체결시장·거래시간·거래소별 비용을 포함",
    },
    "F-CLM-0016": {
        "claim_statement": "KIND 1Q26 분기보고서에서 연결 영업수익 약 3,003억 원과 카카오페이증권 영업수익 약 1,001억 원, 당기순이익 약 236억 원을 확인했다. 예탁자산 +208% YoY는 2차 보도 수치여서 별도 원문 확인 전 보조 맥락으로만 사용한다.",
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 236억 원은 영업이익이 아니라 당기순이익으로 정정; 미대조 성장률 때문에 최종 확신도 M",
    },
    "F-CLM-0021": {
        "claim_statement": "이번 공개 웹 표본에서 확인한 카카오페이 기술 글은 내부 챗봇·관측성·인프라 사례가 중심이었다. 이것만으로 고객향 투자 AI가 없거나 아직 구축 단계라고 결론낼 수 없다.",
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 검색 표본에서의 미발견과 실제 부재를 구분",
    },
    "F-CLM-0023": {
        "claim_statement": "처분효과는 국내외 계좌자료에서 관찰된다. Odean의 PGR 0.148/PLR 0.098은 약 1.51배이고, 국내 KCMI의 보유 첫날 매도비율 41%/22%는 약 1.86배이므로 두 수치를 분리해 해석한다.",
        "supporting_source_ids": "C-SRC-0203;C-SRC-0213;X-SRC-0202;X-SRC-0211;X-SRC-0212",
        "adjudication_note": "Codex 재검증: 미국 비율을 '약 2배'로 표현한 오류를 1.51배로 정정; soft 404 X-SRC-0210 제거",
    },
    "F-CLM-0024": {
        "claim_statement": "Odean 표본에서 매도한 이익 종목은 계속 보유한 손실 종목보다 이후 1년 평균 수익률이 3.4%p 높았다. 이는 표본의 사후 연관이며 개별 초보자의 손실 방치가 그만큼 손해를 유발한다는 인과 추정은 아니다.",
        "adjudication_note": "Codex 재검증: 관찰된 사후 성과 차이와 개인 인과효과를 구분",
    },
    "F-CLM-0033": {
        "claim_statement": "초보 투자자는 연령·자산만으로 정하지 않고 진입기간·실전 주문경험·객관지식·자기효능감·행동취약성을 분리한 다차원 제품 가설로 식별한다.",
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 축의 방향은 수렴하지만 구성개념과 절단값은 내부 고객 데이터로 검증되지 않음",
    },
    "F-CLM-0035": {
        "claim_statement": "첫 매수 준비형은 신규 유입·금융이해력·추격매수 위험을 근거로 우선 검증할 수 있는 제품 가설이며, 실제 고객 규모와 발생률은 미확인이다.",
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 검증 완료 세그먼트가 아닌 우선 검증 가설로 하향",
    },
    "F-CLM-0036": {
        "claim_statement": "보유 중 손실·변동성으로 판단이 막힌 저경험·저자기효능 사용자는 우선 검증 세그먼트다. 계좌행동은 손실 상태를 보여주지만 불안의 원인·유병률은 직접 입증하지 않는다.",
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 핵심 타깃을 검증된 고객군이 아닌 강한 제품 가설로 한정",
    },
    "F-CLM-0037": {
        "claim_statement": "매도 판단 막막형은 처분효과와 공개 VOC가 뒷받침하는 우선 검증 가설이다. 행동 자료만으로 막막함의 심리 원인이나 고객 비율을 확정할 수 없다.",
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 행동 관찰과 심리 원인 진단을 분리",
    },
    "F-CLM-0040": {
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: Codex VOC의 human_* 값은 자동 태그를 기본 복사한 값이므로 독립 인적 검수로 사용하지 않음; 표본 내 기계 집계로만 해석",
    },
    "F-CLM-0043": {
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 공개 자발응답의 질적 수렴이며 초보 여부와 유병률은 미확인",
    },
    "F-CLM-0045": {
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 방향성 신호는 유지하되 자동 분류의 독립 인적 검수 주장을 철회",
    },
    "F-CLM-0066": {
        "claim_statement": "토스증권 공개 WTS에서 서로 다른 현재가·체결가 표시를 관찰했으나 기준시각·KRX/NXT·지연 여부를 재현하지 못해 원인과 일반성을 확정할 수 없다.",
        "adjudication_note": "Codex 재검증: 부재·결함 단정 금지; 실기기와 거래소·기준시각을 포함한 재현 필요",
    },
    "F-CLM-0067": {
        "claim_statement": "Robinhood의 게임화·디지털 참여 관행은 매사추세츠 동의명령의 쟁점이었고 약 750만 달러 합의가 있었으나, 콘페티 제거 시점과 전체 제재 사유를 하나의 인과로 동일시하면 안 된다.",
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 기능 제거와 제재 시점·사유를 분리",
    },
    "F-CLM-0068": {
        "claim_statement": "토스증권의 랜덤 주식 1주 지급 이벤트에 약 170만 명이 참여했다는 보도가 있으나, 참여자를 모두 초보 투자자로 분류할 근거는 없다.",
        "adjudication_note": "Codex 재검증: '초보 투자자 170만 명' 라벨 제거",
    },
    "F-CLM-0081": {
        "supporting_source_ids": "C-SRC-0504;C-SRC-0513;X-SRC-0501;X-SRC-0504;X-SRC-0505",
        "adjudication_note": "Codex 재검증: 국내주식 복귀계좌인 X-SRC-0114를 로보어드바이저 근거에서 제거",
    },
    "F-CLM-0087": {
        "claim_statement": "출처 있는 중립 정보와 사용자 입력값의 계산은 상대적으로 위험이 낮지만, 최종 클릭을 사용자가 하더라도 개인화 정도·쌍방향성·표현·옵션 강조·주문 연결의 실질에 따라 투자권유·자문 위험이 남는다.",
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: '어느 쪽에도 해당하지 않는다'는 단정 철회; 기능별 법무·준법 검토 필요",
    },
    "F-CLM-0089": {
        "claim_statement": "해커톤 MVP는 중립 설명·가상 시나리오·사용자 입력 주문 미리보기·모의주문으로 제한한다. 기존 인가 주문서비스 자체가 금지되는 것은 아니지만 AI가 방향·수량·가격·시점을 정하거나 대화 안에서 직접 제출하는 구조는 제외한다.",
        "adjudication_note": "Codex 재검증: 실주문 전체와 AI 주도 주문을 구분",
    },
    "F-CLM-0098": {
        "claim_statement": "KRX 정보데이터시스템의 웹 조회·CSV 경로와 별도로 인증키·승인 기반 KRX OPEN API가 존재한다. 운영 사용에는 호출·이용기간·출처표시·제3자 제공 등 약관과 데이터 계약을 검토해야 한다.",
        "final_confidence": "H",
        "adjudication_note": "Codex 재검증: 'KRX 공개 REST API 없음'으로 읽히는 표현을 공식 OPEN API 존재로 교정",
    },
    "F-CLM-0099": {
        "claim_statement": "본선일이 토요일이므로 실제로 수집에 성공한 금요일 종가 스냅샷과 로컬 fixture를 사전 동결하고, 성공 전의 예정 시각이나 미수집 데이터를 화면에 표시하지 않는다.",
        "claim_type": "D",
        "final_confidence": "H",
        "adjudication_note": "Codex 재검증: 7월 17일 데이터는 7월 16일 현재 수집 완료 사실이 아니라 실행 계획",
    },
    "F-CLM-0103": {
        "claim_statement": "핵심 흐름은 계획 기록, 관련 사실·해석·모름 브리핑, 유지·일부매도·전량매도의 대칭 시나리오, 결정론적 주문 영향 미리보기, 별도 주문 확인, 사후 회고, 장애 안전모드로 구성한다.",
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 원인 확정 표현과 AI 대화 내 주문 CTA를 제거; 추가매수는 사용자가 먼저 의향을 밝힌 경우에만 위험과 함께 검토",
    },
    "F-CLM-0106": {
        "claim_statement": "공통 계획서 가중치로 두 독립본이 핵심안을 각각 92점으로 평가했다. 이는 내부 우선순위 보조값이지 독립 시장검증 점수가 아니며, 최종안은 판단 여권에 고불안 순간 관련 사실 브리핑을 결합한 제품 가설이다.",
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 공유된 채점 기준의 동점과 외부 검증을 구분",
    },
    "F-CLM-0107": {
        "claim_statement": "북극성 지표는 핵심 조건을 이해하고 사전 계획을 따르거나 새로운 근거로 변경 이유를 명시한 뒤, 거래·보류 중 감당 가능한 결정을 완료한 세션 비율이다. 거래량·거래횟수·단기수익률은 성공지표로 사용하지 않는다.",
        "final_confidence": "M",
        "adjudication_note": "Codex 재검증: 합리적인 계획 변경도 성공으로 인정; 0% 안전 게이트는 사전 정의 테스트셋의 건수로만 보고",
    },
    "F-CLM-0109": {
        "claim_statement": "생애 최초 현물주식 체결 후 12개월은 임시 신규 진입 태그일 뿐이며 6·12·24개월 민감도와 실제 과업 성과로 검증해야 한다.",
        "adjudication_note": "Codex 재검증: KCMI 표본 정의를 제품의 검증된 절단값으로 오해하지 않음",
    },
    "F-CLM-0115": {
        "supporting_source_ids": "X-SRC-0202;X-SRC-0208;X-SRC-0209;X-SRC-0211;X-SRC-0212;X-SRC-0425;C-SRC-0203;C-SRC-0213",
        "adjudication_note": "Codex 재검증: soft 404 X-SRC-0210 제거; 행동 관찰과 심리 원인 진단을 분리하는 가드 유지",
    },
    "F-CLM-0119": {
        "status": "기각",
        "adjudication_note": "Codex 재검증: 연구가 선택효과와 인과효과를 구분하지 못하므로 MTS 자체가 손실을 유발한다는 명제는 채택하지 않음",
    },
    "F-CLM-0122": {
        "claim_statement": "금융자산·예탁자산·계좌 수·플랫폼 MAU·월간 거래 고객·커뮤니티 MAU는 정의와 기준일이 다른 지표이므로 합치거나 하나의 성장 시계열로 해석하면 안 된다.",
        "adjudication_note": "Codex 재검증: 공식 제목의 예탁자산 15조·20조와 다른 금융자산 지표를 구분",
    },
}


def main() -> None:
    source_path = find_final("source_id")
    claim_path = find_final("claim_id")
    source_fields, sources = read_csv(source_path)
    claim_fields, claims = read_csv(claim_path)

    for source in sources:
        source["reliability"] = normalize_reliability(source.get("reliability", ""))
        source["market"] = normalize_market(source.get("market", ""))
        source["status"] = normalize_status(source.get("status", ""))
        override = SOURCE_OVERRIDES.get(source["source_id"])
        if override:
            for key, value in override.items():
                if key == "limitations":
                    source[key] = append_unique(source.get(key, ""), value)
                else:
                    source[key] = value
        if source["source_id"].startswith("X-SRC-03") and source.get("source_type") == "user_review":
            source["limitations"] = append_unique(
                source.get("limitations", ""),
                "Codex VOC의 human_audited/human_themes는 생성 스크립트에서 자동 태그를 기본 복사한 값이므로 독립 인적 검수 증거로 사용하지 않음",
            )

    for claim in claims:
        override = CLAIM_OVERRIDES.get(claim["claim_id"])
        if not override:
            continue
        for key, value in override.items():
            if key == "adjudication_note":
                claim[key] = append_unique(claim.get(key, ""), value)
            else:
                claim[key] = value

    source_ids = [source["source_id"] for source in sources]
    claim_ids = [claim["claim_id"] for claim in claims]
    if len(source_ids) != len(set(source_ids)):
        raise RuntimeError("Duplicate final source IDs")
    if len(claim_ids) != len(set(claim_ids)):
        raise RuntimeError("Duplicate final claim IDs")

    source_set = set(source_ids)
    reverse: dict[str, set[str]] = {source_id: set() for source_id in source_ids}
    for claim in claims:
        references = split_ids(claim.get("supporting_source_ids", ""))
        references += split_ids(claim.get("counter_source_ids", ""))
        missing = sorted(set(references) - source_set)
        if missing:
            raise RuntimeError(f"{claim['claim_id']} references missing sources: {missing}")
        for source_id in references:
            reverse[source_id].add(claim["claim_id"])

    for source in sources:
        source["claim_ids"] = ";".join(sorted(reverse[source["source_id"]]))

    write_csv(source_path, source_fields, sources)
    write_csv(claim_path, claim_fields, claims)

    relation_count = sum(len(ids) for ids in reverse.values())
    print(f"sources={len(sources)} claims={len(claims)} relations={relation_count}")
    print(f"claim_overrides={sum(1 for claim in claims if claim['claim_id'] in CLAIM_OVERRIDES)}")
    print(source_path)
    print(claim_path)


if __name__ == "__main__":
    main()
