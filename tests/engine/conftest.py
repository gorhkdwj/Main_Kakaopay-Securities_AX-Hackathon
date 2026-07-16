"""tests/engine 공용 설정 — import 경로·fixture 로더.

어느 위치에서 pytest를 실행해도 ``src.engine``을 import할 수 있도록
프로젝트 루트를 sys.path에 추가한다(기본 실행: 프로젝트 루트에서
``python -m pytest tests\\engine -q``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

#: 프로젝트 루트(이 파일 기준 2단계 상위)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

#: 오프라인 시나리오 fixture 디렉터리(읽기 전용 — 수정 금지)
FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"


def load_scenario(scenario_id: str) -> dict:
    """data/fixtures/scenario_<id>.json을 UTF-8로 읽어 dict로 반환한다."""
    path = FIXTURES_DIR / f"scenario_{scenario_id}.json"
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


@pytest.fixture(scope="session")
def loss8() -> dict:
    return load_scenario("loss8")


@pytest.fixture(scope="session")
def profit15() -> dict:
    return load_scenario("profit15")


@pytest.fixture(scope="session")
def first_buy() -> dict:
    return load_scenario("first_buy")
