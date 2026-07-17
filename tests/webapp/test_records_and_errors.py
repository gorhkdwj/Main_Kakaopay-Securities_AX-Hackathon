"""판단 기록(REC) 저장 스키마 + 입력 오류 계약(§3.3·§5.3·§8) 검증.

- REC 파일: 계약 §3.3 필드만 저장, 결과(수익률) 필드 없음, 디렉터리 자동 생성.
- 오류 입력: 계산·체결·기록 미생성 + 한국어 오류 메시지(§5.3).
- 모의 체결: 수치 변조·수량 불일치 거부(결정론 재검증).
"""

from __future__ import annotations

import json
import re

#: 계약 §3.3의 전체 필드(이 밖의 키가 파일에 있으면 실패)
ALLOWED_RECORD_KEYS = {
    "record_id", "scenario_id", "intent", "reason_text",
    "calculation_id", "created_at", "review_date",
}
REQUIRED_RECORD_KEYS = {"record_id", "scenario_id", "intent", "reason_text", "created_at"}

#: 결과 중심 지표(저장 금지 — 과정 중심 원칙)의 흔적 키워드
RESULT_FIELD_MARKERS = ("pnl", "profit", "return", "수익률", "손익")


def _save_minimal(client, **overrides):
    payload = {
        "scenario_id": "loss8",
        "intent": "그대로 유지",
        "reason_text": "재검토 조건에 해당하지 않아 계획대로 두려는 생각.",
    }
    payload.update(overrides)
    return client.post("/api/record", json=payload)


def test_record_directory_autocreated_and_schema(client, records_dir):
    assert not records_dir.exists()  # 저장 전에는 디렉터리가 없다

    res = _save_minimal(client)
    assert res.status_code == 200
    rec = res.json()["record"]

    assert records_dir.is_dir()  # 자동 생성
    files = list(records_dir.glob("*.json"))
    assert len(files) == 1
    assert files[0].name == rec["record_id"] + ".json"

    saved = json.loads(files[0].read_text(encoding="utf-8"))
    # 최소 저장: calculation_id·review_date 없이 — 키가 아예 없다(null 저장 아님)
    assert set(saved.keys()) == REQUIRED_RECORD_KEYS
    assert set(saved.keys()) <= ALLOWED_RECORD_KEYS
    assert re.match(r"^REC-\d{4}-\d{6}-\d+$", saved["record_id"])
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} KST$", saved["created_at"])

    # 결과(수익률) 필드가 어떤 이름으로도 없다
    for key in saved:
        for marker in RESULT_FIELD_MARKERS:
            assert marker not in key.lower()


def test_record_full_fields_and_sequence(client, records_dir):
    p = client.post("/api/preview",
                    json={"scenario_id": "loss8", "side": "sell", "qty": 10}).json()["preview"]
    res = _save_minimal(
        client,
        intent="일부 판매 검토",
        calculation_id=p["calculation_id"],
        review_date="다음 실적 발표 후",
    )
    assert res.status_code == 200
    first = res.json()["record"]
    assert set(first.keys()) == ALLOWED_RECORD_KEYS
    assert first["calculation_id"] == p["calculation_id"]
    assert first["review_date"] == "다음 실적 발표 후"

    # 같은 세션에서 seq 증가 — 파일이 누적된다
    res2 = _save_minimal(client, intent="나중에 재검토")
    second = res2.json()["record"]
    assert first["record_id"] != second["record_id"]
    assert len(list(records_dir.glob("REC-*.json"))) == 2

    # 저장 파일에 결과 수익률류 값이 없다(내용 검사)
    for f in records_dir.glob("REC-*.json"):
        saved = json.loads(f.read_text(encoding="utf-8"))
        assert set(saved.keys()) <= ALLOWED_RECORD_KEYS


def test_record_input_errors_do_not_create_files(client, records_dir):
    cases = [
        ({"reason_text": "   "}, "empty_reason"),
        ({"intent": "아무거나"}, "invalid_intent"),
        ({"calculation_id": "CALC-틀린형식"}, "invalid_calculation_id"),
        ({"review_date": "   "}, "invalid_review_date"),
    ]
    for overrides, code in cases:
        res = _save_minimal(client, **overrides)
        assert res.status_code == 400, code
        assert res.json()["error"]["code"] == code
    # 존재하지 않는 시나리오
    res = _save_minimal(client, scenario_id="nope")
    assert res.status_code == 404

    assert not records_dir.exists() or not list(records_dir.glob("*.json"))


# ---------------------------------------------------------------------------
# 미리보기 입력 오류(계약 §5.3 — 계산 기록 미생성·한국어 메시지)
# ---------------------------------------------------------------------------

def test_preview_input_errors(client):
    cases = [
        ({"scenario_id": "loss8", "side": "sell", "qty": 0}, "QuantityError", "1 이상"),
        ({"scenario_id": "loss8", "side": "sell", "qty": -5}, "QuantityError", "1 이상"),
        ({"scenario_id": "loss8", "side": "sell", "qty": 2.5}, "QuantityError", "정수"),
        ({"scenario_id": "loss8", "side": "sell", "qty": "10"}, "QuantityError", "정수"),
        ({"scenario_id": "loss8", "side": "sell", "qty": 31}, "QuantityError", "보유수량"),
        # 양방향(D-0718-0225): loss8도 예수금 1,000,000 — qty=1 매수는 이제 정상.
        # 예수금 초과 경계는 22주(총 결제 1,012,151 > 1,000,000 — 계약 §5.2-c 공유).
        ({"scenario_id": "loss8", "side": "buy", "qty": 22}, "InsufficientCashError", "예수금"),
        ({"scenario_id": "first_buy", "side": "sell", "qty": 1}, "no_holding", "보유 수량"),
    ]
    for payload, code, keyword in cases:
        res = client.post("/api/preview", json=payload)
        assert res.status_code == 400, payload
        body = res.json()
        assert body["error"]["code"] == code
        assert keyword in body["error"]["message"]
        assert "CALC-" not in json.dumps(body, ensure_ascii=False)

    # side 오류·시나리오 없음
    assert client.post("/api/preview",
                       json={"scenario_id": "loss8", "side": "hold", "qty": 1}).status_code == 400
    assert client.post("/api/preview",
                       json={"scenario_id": "nope", "side": "sell", "qty": 1}).status_code == 404


# ---------------------------------------------------------------------------
# 모의 체결 방어 — 변조·수량 불일치 거부
# ---------------------------------------------------------------------------

def test_settle_rejects_tampered_preview(client):
    p = client.post("/api/preview",
                    json={"scenario_id": "loss8", "side": "sell", "qty": 10}).json()["preview"]

    tampered = dict(p)
    tampered["net_proceeds"] = p["net_proceeds"] + 1000  # 수령액 위·변조 시도
    res = client.post("/api/settle", json={"preview": tampered, "confirmed_qty": 10})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "InvalidPreviewError"

    # 재확인 수량 불일치(사용자 재입력 대조)
    res2 = client.post("/api/settle", json={"preview": p, "confirmed_qty": 11})
    assert res2.status_code == 400
    assert "수량" in res2.json()["error"]["message"]

    # preview가 dict가 아니면 형식 오류
    res3 = client.post("/api/settle", json={"preview": "abc", "confirmed_qty": 10})
    assert res3.status_code == 400

    # 정상 재시도는 여전히 성립(오류가 상태를 오염시키지 않음)
    ok = client.post("/api/settle", json={"preview": p, "confirmed_qty": 10})
    assert ok.status_code == 200
    assert ok.json()["settlement"]["is_mock"] is True


def test_broken_fixture_returns_graceful_error(tmp_path, records_dir):
    """fixture JSON 파손 → 미처리 500(스택) 대신 계약 §8 오류 응답(fixture_invalid).

    T-0716-2046: 파손 fixture가 unhandled 예외로 전파되면 화면에서는
    '무반응'으로 인지된다 — 세 라우트 전부 한국어 오류 계약으로 변환돼야 한다.
    """
    from fastapi.testclient import TestClient

    from src.webapp.app import create_app

    vdir = tmp_path / "fixtures"
    vdir.mkdir(parents=True)
    (vdir / "scenario_loss8.json").write_text("{broken", encoding="utf-8")
    client = TestClient(create_app(fixtures_dir=vdir, records_dir=records_dir),
                        raise_server_exceptions=False)

    r1 = client.get("/api/scenario/loss8")
    assert r1.status_code == 500
    assert r1.json()["ok"] is False
    assert r1.json()["error"]["code"] == "fixture_invalid"
    assert "loss8" in r1.json()["error"]["message"]

    r2 = client.post("/api/preview",
                     json={"scenario_id": "loss8", "side": "sell", "qty": 10})
    assert r2.status_code == 500
    assert r2.json()["error"]["code"] == "fixture_invalid"

    r3 = client.post("/api/record", json={
        "scenario_id": "loss8", "intent": "그대로 유지",
        "reason_text": "테스트 사유입니다.",
    })
    assert r3.status_code == 500
    assert r3.json()["error"]["code"] == "fixture_invalid"
    assert not records_dir.exists()  # 오류 시 기록 미생성(§5.3)
