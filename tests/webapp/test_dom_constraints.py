"""통합 테스트 I-08 — 화면 제약 DOM 검사(헌법 §14·스펙 §5).

검사 항목:
- ①~⑤(및 홈·⑦·⑧) 영역에 주문 실행 버튼 부재 — 주문은 ⑥ 바텀시트에서만.
  (⑧은 실앱 주문 화면의 '재현'이지만 비기능 — 버튼 disabled·배선 금지, 계약 §9)
- 안전모드는 위저드 밖 오버레이(#safemode-screen) — 주문 UI 없음(계약 §8).
- 검토 의향 4버튼 동일 클래스(동일 크기·색 위계 — 기본 강조 없음).
- '원인' 단어 미사용('관련 사실'만) — 정적 파일·API 응답 전부.
- 손실 화면에 추가 구매(추가매수) 유도 기본 노출 없음.
- 정적 문구도 guard 사전(lexicon)을 통과(방향 추천·단정 문구 금지).
- 외부 CDN·폰트·네트워크 요청 0(오프라인 원칙).
"""

from __future__ import annotations

import re
from pathlib import Path

from src.policy.lexicon import find_violations

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "src" / "webapp" / "static"

STATIC_FILES = ("index.html", "app.js", "app.css")
NON_ORDER_STEPS = (0, 1, 2, 3, 4, 5, 7, 8)


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def section_slice(html: str, section_id: str) -> str:
    m = re.search(
        rf'<section id="{section_id}"[^>]*>(.*?)</section>', html, re.S)
    assert m, f"{section_id} 섹션이 index.html에 없습니다"
    return m.group(1)


# ---------------------------------------------------------------------------
# 주문 실행 버튼은 ⑥에만
# ---------------------------------------------------------------------------

def test_order_execute_button_only_in_step6():
    html = read_static("index.html")
    # 실행 버튼 마커는 전체에서 딱 1개
    assert html.count('data-role="order-execute"') == 1
    # ⑥ 섹션(바텀시트 포함) 안에만 존재
    assert 'data-role="order-execute"' in section_slice(html, "step-6")
    for i in NON_ORDER_STEPS:
        sec = section_slice(html, f"step-{i}")
        assert 'data-role="order-execute"' not in sec, f"step-{i}에 주문 실행 마커"
        assert "체결하기" not in sec, f"step-{i}에 체결 버튼 문구"


def test_step6_has_mock_bar_and_notices_skeleton():
    html = read_static("index.html")
    assert "모의 주문 — 실제 거래 아님" in html  # 상단 고정 바
    sec6 = section_slice(html, "step-6")
    assert "돌아가기" in sec6  # 취소·돌아가기 = 진행과 동일 위계(버튼 존재)
    assert 'id="confirm-qty"' in sec6  # 재확인 수량 입력


# ---------------------------------------------------------------------------
# 검토 의향 4버튼 — 동일 클래스(크기·색 위계 동일)
# ---------------------------------------------------------------------------

def test_intent_buttons_same_class_and_count():
    html = read_static("index.html")
    sec5 = section_slice(html, "step-5")
    classes = re.findall(r'<button class="([^"]+)"[^>]*data-slot="\d"', sec5)
    assert len(classes) == 4, "검토 의향 버튼은 정확히 4개여야 합니다"
    assert set(classes) == {"intent-btn"}, "4버튼의 클래스(크기·색 위계)가 서로 달라졌습니다"
    # ⑤에는 주문성 버튼이 없다(위 test에서 겸증) + 기본 강조(dark) 버튼 없음
    assert 'class="btn dark"' not in sec5


# ---------------------------------------------------------------------------
# '원인' 단어 금지 · 추가 구매 유도 금지
# ---------------------------------------------------------------------------

def test_no_cause_word_in_static_and_responses(client):
    for name in STATIC_FILES:
        assert "원인" not in read_static(name), f"{name}에 '원인' 단어가 있습니다"
    for sid in ("loss8", "profit15", "first_buy"):
        raw = client.get(f"/api/scenario/{sid}").text
        assert "원인" not in raw


def test_no_topup_inducement_by_default():
    # 유도 어형은 계약 §7 사전(TOP-01~04)의 형태를 기준으로 한다
    # ("더 사"만 보면 '렌더 사실' 같은 무관 문구가 오탐되므로 유도 어미까지 본다)
    for name in ("index.html", "app.js"):
        text = read_static(name)
        for phrase in ("추가 매수", "추가 구매", "추가매수", "물타기",
                       "더 사서", "더 사면", "더 사시", "평단을 낮추", "평단가를 낮추"):
            assert phrase not in text, f"{name}에 추가 구매 유도 문구: {phrase}"


# ---------------------------------------------------------------------------
# 정적 문구 guard 통과(방향 추천·단정 금지 자동 검증)
# ---------------------------------------------------------------------------

def test_static_files_pass_lexicon():
    for name in STATIC_FILES:
        text = read_static(name)
        violations = find_violations(text)
        assert violations == [], f"{name} 정적 문구가 금지 사전에 걸립니다: {violations}"


# ---------------------------------------------------------------------------
# 오프라인 — 외부 CDN·폰트·네트워크 0
# ---------------------------------------------------------------------------

def test_no_external_urls_anywhere():
    external = re.compile(r"https?://(?!127\.0\.0\.1|localhost)")
    targets = [read_static(n) for n in STATIC_FILES]
    targets.append(
        (PROJECT_ROOT / "src" / "webapp" / "app.py").read_text(encoding="utf-8"))
    for text in targets:
        assert not external.search(text), "외부 URL 참조가 발견됐습니다(오프라인 원칙 위반)"

    html = read_static("index.html")
    assert '<link rel="stylesheet" href="/static/app.css">' in html
    assert 'src="/static/app.js"' in html
    assert "@import" not in read_static("app.css")
    assert "@font-face" not in read_static("app.css")


def test_server_module_has_no_network_client_imports():
    src = (PROJECT_ROOT / "src" / "webapp" / "app.py").read_text(encoding="utf-8")
    for banned in ("import requests", "import httpx", "import urllib",
                   "import socket", "import openai", "websocket"):
        assert banned not in src, f"서버 모듈에 네트워크 클라이언트 흔적: {banned}"


# ---------------------------------------------------------------------------
# 필수 UI 마커(스펙 §3·§4의 계승·차별 요소)
# ---------------------------------------------------------------------------

def test_required_ui_markers_present(client):
    html = read_static("index.html")
    js = read_static("app.js")

    # 상단 상시: 배지 + 안전 지표 카운터
    assert "교육용 가상 데이터" in html
    assert "안전 지표" in html

    # 차별 레이어 라벨들
    assert "해석 — 사실이 아니에요" in js
    assert "커뮤니티 관심 지표" in js
    assert "알 수 없는 것" in js
    assert "그때 이렇게 적으셨어요" in js          # 지난 투자 일지 리마인드
    assert "자동완성 초안" in html                 # first_buy 초안 버튼
    assert "투자 일지" in html                     # 화면 명칭(계약 §9)
    assert "체결 후에는 취소할 수 없어요" in html + js  # 비가역 고지
    assert "D+2" in html + js                      # 결제일 고지
    assert "(가상)" in js                          # 출처 가상 병기

    # 시세 헤더의 SOR 라벨은 서버 meta로 내려간다
    data = client.get("/api/scenario/loss8").json()
    assert data["meta"]["market_label"] == "SOR 정규장"

    # 접이식 DEMO 패널(시나리오 전환·안전모드·전체 펼침)
    assert 'id="demo-panel"' in html
    assert 'id="demo-safemode"' in html
    assert 'id="demo-expand"' in html
    # 안전모드 CSS: 위저드 전체(#phone)를 조상째 숨기고 안전모드 화면만 표시(오버레이 — 계약 §8)
    assert 'id="safemode-screen"' in html
    css = read_static("app.css")
    assert "body.safemode #phone" in css
    assert "body.safemode #safemode-screen" in css


# ---------------------------------------------------------------------------
# ⑧ 주문 화면(실앱 재현) — 비기능 보장(계약 §9 재현 화면 규칙)
# ---------------------------------------------------------------------------

def test_step8_replica_is_non_functional():
    html = read_static("index.html")
    js = read_static("app.js")
    sec8 = section_slice(html, "step-8")

    # 재현 라벨(시연용 안전 표기 — 계약 §9) + 내 판단 기록 상기 카드(브리핑 재진입 배너 금지)
    assert "실앱 주문 화면 재현(시연용)" in sec8
    assert 'id="s8-judgment"' in sec8
    assert "s8-briefing-entry" not in sec8  # 재수행 유도 배너 제거(사용자 지적 2026-07-17)

    # 주문 버튼 2종(탭 없음 — 버튼과 중복이라 제거): disabled + JS 클릭 배선 부재
    for bid in ("s8-order-buy", "s8-order-sell"):
        m = re.search(rf'<button[^>]*id="{bid}"[^>]*>', sec8)
        assert m, f"{bid} 버튼이 ⑧에 없습니다"
        assert "disabled" in m.group(0), f"{bid}가 disabled가 아닙니다"
        assert f'el("{bid}").addEventListener' not in js, f"{bid}에 클릭 배선(비기능 위반)"


def test_safemode_screen_has_no_order_ui():
    html = read_static("index.html")
    sec = section_slice(html, "safemode-screen")
    assert 'data-role="order-execute"' not in sec
    assert "체결하기" not in sec
    assert "비상 절차" in sec
    assert 'id="btn-safe-exit"' in sec


def test_home_skip_button_replaces_later():
    """홈(S0) 대안 버튼 = "브리핑 없이 바로 주문할게요"(→⑧) — 계약 §9.

    레이어는 투자 행동을 막지 않는다(사용자 결정 2026-07-16) — 소극적
    "나중에 볼게요"는 존재하지 않아야 한다.
    """
    html = read_static("index.html")
    sec0 = section_slice(html, "step-0")
    assert "브리핑 없이 바로 주문할게요" in sec0
    assert "나중에 볼게요" not in html


def test_step0_order_replica_with_intercept():
    """S0 = 실앱 주문 화면 재현(진입) + 인터셉트 팝업(계약 §9 상시 인터셉트 — D-0717-2121).

    S0 주문 버튼은 팝업만 연다(주문 실행 아님 — 실행 마커·"체결하기" 부재는
    test_order_execute_button_only_in_step6이 겸증). 구매/판매는 전 시나리오
    병렬 노출·색 구분만(side 강조·hidden 로직 금지).
    """
    html = read_static("index.html")
    js = read_static("app.js")
    sec0 = section_slice(html, "step-0")

    # 배경 = 주문 화면 재현(시연 라벨) + 인터셉트 팝업 골격·갈림길 2버튼
    assert "실앱 주문 화면 재현(시연용)" in sec0
    assert 'id="intercept-backdrop"' in sec0
    assert "판단 전 브리핑 시작하기" in sec0
    assert "브리핑 없이 바로 주문할게요" in sec0

    # S0 주문 버튼 2종: 존재 + 팝업 배선(openIntercept)만 허용
    for bid in ("s0-order-buy", "s0-order-sell"):
        assert f'id="{bid}"' in sec0, f"{bid} 버튼이 S0에 없습니다"
        assert f'el("{bid}").addEventListener("click", openIntercept)' in js, \
            f"{bid}는 인터셉트 팝업 배선만 가져야 합니다"

    # 방향 중립(전 시나리오 공통): side 강조·hidden 로직 부재 + 탭 중복 제거 유지
    for forbidden in ('el("s8-order-buy").hidden', 'el("s8-order-sell").hidden',
                      'el("s0-order-buy").hidden', 'el("s0-order-sell").hidden'):
        assert forbidden not in js, f"side 강조/hidden 로직 잔존: {forbidden}"
    assert "order-tab" not in html, "구매/판매 탭 잔존 — 버튼과 중복(사용자 지적 2026-07-17)"
