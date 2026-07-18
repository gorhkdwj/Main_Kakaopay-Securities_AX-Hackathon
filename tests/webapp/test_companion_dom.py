"""동반자 패널 DOM 검사 — 계약 §9 '동반자 패널'·§6 동반자 대화(D-0718-1120).

검사 항목:
- 구현제안서 §1 DOM 계약 골격(FAB·backdrop·panel·asof·log·quick·form) 존재.
- 패널·동반자 JS 구간 안 주문 실행 마커(`data-role="order-execute"`)·"체결하기" 문구 0
  (계약 §9 — 핸드오프는 ⑥ 모의 주문·투자 일지 내비게이션만).
- 표시 토글은 hidden 속성만(전역 [hidden] 규칙 — T-0716-1510) — display 직접 조작 금지.
- 오버레이 배타: companion z-index(70) < ⑥ 시트·인터셉트(80), 시트·인터셉트·안전모드
  동안 FAB 숨김 CSS 규칙 존재.
- 컨텍스트 주입(구현제안 §2)·안전 강등 문구(계약 §6)·지연 시세 고지(계약 §9) 존재.

정적 문구의 lexicon 통과는 test_dom_constraints.test_static_files_pass_lexicon이
전 파일 대상으로 겸증한다(여기 넣은 문구 전부 자동 검사 대상).
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "src" / "webapp" / "static"


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def companion_html_slice() -> str:
    html = read_static("index.html")
    m = re.search(r"<!-- companion:(.*?)<!-- /companion -->", html, re.S)
    assert m, "index.html에 companion 마커 구간이 없습니다"
    return m.group(1)


def companion_js_slice() -> str:
    js = read_static("app.js")
    m = re.search(
        r"── 동반자 패널\(companion\)(.*?)── /동반자 패널\(companion\)", js, re.S)
    assert m, "app.js에 동반자 패널 마커 구간이 없습니다"
    return m.group(1)


# ---------------------------------------------------------------------------
# DOM 계약(구현제안 §1) — id 골격·역할 속성
# ---------------------------------------------------------------------------

def test_companion_dom_contract_ids():
    sec = companion_html_slice()
    for marker in (
        'id="companion-fab"',
        'id="companion-backdrop" hidden',   # 초기 상태는 닫힘(hidden 속성)
        'id="companion-panel"',
        'id="companion-asof"',
        'id="companion-close"',
        'id="companion-log"',
        'id="companion-quick"',
        'id="companion-form"',
        'id="companion-input"',
    ):
        assert marker in sec, f"companion 구간에 {marker} 가 없습니다"
    assert 'role="dialog"' in sec and 'aria-modal="true"' in sec
    assert 'aria-label="동반자와 대화"' in sec  # FAB 접근성 라벨


def test_companion_lives_inside_phone_frame():
    """FAB·패널은 #phone 안(폰 프레임) — 안전모드의 #phone 숨김이 구조적으로 겸용된다."""
    html = read_static("index.html")
    m = re.search(r'<main id="phone".*?</main>', html, re.S)
    assert m, "#phone 메인 프레임이 없습니다"
    assert 'id="companion-fab"' in m.group(0)
    assert 'id="companion-panel"' in m.group(0)


# ---------------------------------------------------------------------------
# 주문 실행 금지(계약 §9) — 패널·동반자 JS 구간에 실행 마커·문구 0
# ---------------------------------------------------------------------------

def test_companion_has_no_order_execution():
    for name, sec in (("index.html", companion_html_slice()),
                      ("app.js", companion_js_slice())):
        assert 'order-execute' not in sec, f"{name} companion 구간에 주문 실행 마커"
        assert "체결하기" not in sec, f"{name} companion 구간에 체결 버튼 문구"
        assert "btn exec" not in sec, f"{name} companion 구간에 주문 실행 버튼 클래스"


def test_companion_addition_keeps_global_order_execute_count():
    """전체 index.html의 실행 마커는 여전히 ⑥의 1개뿐(기존 테스트와 이중 안전망)."""
    html = read_static("index.html")
    assert html.count('data-role="order-execute"') == 1


# ---------------------------------------------------------------------------
# 표시 토글 — hidden 속성만(T-0716-1510)
# ---------------------------------------------------------------------------

def test_companion_uses_hidden_toggle_only():
    js = companion_js_slice()
    assert '.hidden = false' in js, "패널 열기가 hidden 토글이 아닙니다"
    assert '.hidden = true' in js, "패널 닫기가 hidden 토글이 아닙니다"
    assert "style.display" not in js, "companion 구간에서 display 직접 조작(금지)"


# ---------------------------------------------------------------------------
# 오버레이 배타(계약 §9) — z-계층·FAB 숨김·안전모드 연동
# ---------------------------------------------------------------------------

def test_companion_overlay_stays_below_existing_popups():
    css = read_static("app.css")
    m_cmp = re.search(r"#companion-backdrop\s*\{[^}]*z-index:\s*(\d+)", css)
    assert m_cmp, "companion backdrop z-index 규칙이 없습니다"
    m_sheet = re.search(
        r"#sheet-backdrop,\s*#intercept-backdrop\s*\{[^}]*z-index:\s*(\d+)", css)
    assert m_sheet, "시트·인터셉트 backdrop z-index 규칙이 없습니다"
    assert int(m_cmp.group(1)) < int(m_sheet.group(1)), \
        "companion 패널이 기존 팝업(⑥ 시트·인터셉트)보다 위에 있습니다"


def test_companion_fab_hidden_while_other_overlays_open():
    css = read_static("app.css")
    for selector in (
        "body:has(#sheet-backdrop:not([hidden])) #companion-fab",
        "body:has(#intercept-backdrop:not([hidden])) #companion-fab",
        "body:has(#companion-backdrop:not([hidden])) #companion-fab",
        "body.safemode #companion-fab",
        "body.safemode #companion-backdrop",
    ):
        assert selector in css, f"FAB 배타 규칙 누락: {selector}"


def test_companion_safemode_wiring_in_toggle_handler():
    """안전모드 진입 시 패널을 닫는다(기존 토글 핸들러 연동 — 계약 §9)."""
    js = read_static("app.js")
    m = re.search(r"function toggleSafemode\(.*?\n\}", js, re.S)
    assert m, "toggleSafemode 함수가 없습니다"
    assert "closeCompanion()" in m.group(0), "안전모드 진입 시 동반자 패널 미강등"


def test_companion_reset_on_scenario_change():
    """시나리오 전환 시 대화 상태 초기화 — 다른 시나리오 컨텍스트 혼입 방지."""
    js = read_static("app.js")
    m = re.search(r"async function loadScenario\(.*?\n\}", js, re.S)
    assert m, "loadScenario 함수가 없습니다"
    assert "resetCompanion()" in m.group(0)


# ---------------------------------------------------------------------------
# API 계약·안전 문구(구현제안 §2·§3, 계약 §6·§9)
# ---------------------------------------------------------------------------

def test_companion_chat_api_and_context_fields():
    js = companion_js_slice()
    assert "/api/companion/chat" in js
    for field in ("scenario_id", "step", "flow_side",
                  "active_calculation_id", "question", "history"):
        assert field in js, f"컨텍스트 필드 누락(구현제안 §2): {field}"


def test_companion_safety_copy_present():
    js = companion_js_slice()
    # 폴백 사슬의 끝 — 안전 강등 문구(계약 §6 명문)
    assert "지금은 답변을 준비할 수 없어요 — 화면의 사실 카드를 참고해 주세요." in js
    # 패널 상단 기준시각 바 — 지연·가상 고지(계약 §9)
    assert "지연 시세" in js
    assert "교육용 가상 데이터" in js
    # 카드 문법 라벨 — 사실/해석/모름/계산/가드(계약 §9)
    for label in ("해석 — 사실이 아니에요", "모름", "계산 — 결정론 엔진", "가드 통과"):
        assert label in js, f"카드 라벨 누락: {label}"
