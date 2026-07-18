"""사실 0건 강등(계약 §8 — T-0718-1220) 검증.

live 응답이 guard 통과 후 facts 0건이 되는 두 경로(모델이 비움 / 전건 차단)에서
'사실 없는 브리핑'을 렌더하지 않고 다음 계층(cache→static)으로 강등하는지 확인한다.
가짜 generate_briefing 주입 — 네트워크 0회.
"""
import json

import src.webapp.app as app_module


def _fake_generate(response):
    """generate_briefing 대체 — 주어진 응답을 live 원천으로 반환."""
    def _fake(fx, *, mode="auto", price_source_id=None, cache_dir=None,
              llm_call=None):
        return response, "live", ["live_ok"]
    return _fake


def _briefing_empty_facts(scenario_id="loss8"):
    """모델이 facts를 아예 비워 보낸 계약 위반 응답."""
    return {
        "facts": [],
        "interpretations": [
            {"text": "부담으로 보는 시각도 있어요.", "basis": [], "stance": "부정 시각"},
            {"text": "여지로 보는 시각도 있어요.", "basis": [], "stance": "긍정 시각"},
        ],
        "unknowns": ["내일 가격은 알 수 없어요."],
        "user_inputs": {"quantity": None, "intent": None, "situation": scenario_id},
        "calculation_id": None,
        "policy_result": "information_only",
        "next_questions": [],
    }


def _briefing_bad_sources(scenario_id="loss8"):
    """facts는 있으나 실재하지 않는 출처 — guard SRC-EXIST가 전건 차단해야 한다."""
    resp = _briefing_empty_facts(scenario_id)
    resp["facts"] = [
        {"text": "가짜 출처 사실입니다.", "source_id": "DEMO-SRC-999",
         "as_of": "2026-07-17 15:30 KST"},
    ]
    return resp


def test_live_empty_facts_degrades_and_renders_facts(client, monkeypatch):
    monkeypatch.setattr(app_module, "generate_briefing",
                        _fake_generate(_briefing_empty_facts()))
    client.get("/api/scenario/loss8")
    r = client.get("/api/briefing/loss8")
    assert r.status_code == 200
    d = r.json()
    # 강등: live가 아니어야 하고(캐시 지문 일치 시 cache, 아니면 static), 사실이 있어야 한다
    assert d["briefing_source"] in ("cache", "static")
    assert len(d["briefing"]["facts"]) >= 1


def test_live_all_blocked_facts_degrades(client, monkeypatch):
    monkeypatch.setattr(app_module, "generate_briefing",
                        _fake_generate(_briefing_bad_sources()))
    client.get("/api/scenario/loss8")
    r = client.get("/api/briefing/loss8")
    assert r.status_code == 200
    d = r.json()
    assert d["briefing_source"] in ("cache", "static")
    assert len(d["briefing"]["facts"]) >= 1
    # 실제 발생한 차단은 세션 안전 지표에 정직 반영된다
    assert d["safety"]["no_source"] >= 1


def test_degrade_recorded_in_audit(client, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "generate_briefing",
                        _fake_generate(_briefing_empty_facts()))
    client.get("/api/scenario/loss8")
    client.get("/api/briefing/loss8")
    audit = client.app.state.audit_dir / "briefing_events.jsonl"
    events = [json.loads(l) for l in open(audit, encoding="utf-8")]
    last = events[-1]
    assert any(a.startswith("facts_empty_degraded(") for a in last["attempts"])
    assert last["facts_rendered"] >= 1
    # 직전 이벤트(강등 전 live 결정)에는 관측 필드가 남는다
    prev = events[-2]
    assert prev["source"] == "live" and prev["facts_rendered"] == 0


def test_static_normal_path_unchanged(client):
    client.get("/api/scenario/loss8")
    r = client.get("/api/briefing/loss8")
    d = r.json()
    assert d["briefing_source"] in ("cache", "static", "live")
    assert len(d["briefing"]["facts"]) >= 1
