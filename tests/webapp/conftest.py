"""tests/webapp 공용 설정 — import 경로·앱 팩토리·변형 fixture 헬퍼.

어느 위치에서 pytest를 실행해도 ``src.webapp``을 import할 수 있도록
프로젝트 루트를 sys.path에 추가한다(기본 실행: 프로젝트 루트에서
``python -m pytest tests\\webapp -q``).

원칙:
- 서버는 켜지 않는다 — FastAPI TestClient만 사용(외부 네트워크 0회).
- 원본 fixture(data/fixtures)는 절대 수정하지 않는다 — 변형이 필요하면
  임시 디렉터리에 사본을 만들어 create_app(fixtures_dir=...)로 주입한다.
- 판단 기록은 임시 디렉터리에 저장한다(out/records 오염 방지).
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

# 표준 실행 환경은 .venv(fastapi 설치됨 — requirements.txt). fastapi가 없는
# 인터프리터(예: 시스템 파이썬 3.10)에서는 webapp 스위트만 건너뛰어
# 엔진·가드 테스트 수집이 중단되지 않게 한다(수집 하드 오류 방지).
pytest.importorskip("fastapi", reason="webapp 테스트는 .venv 실행 전제(fastapi 필요)")

from fastapi.testclient import TestClient  # noqa: E402

from src.webapp.app import create_app  # noqa: E402

#: 오프라인 시나리오 fixture 디렉터리(읽기 전용 — 수정 금지)
FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"

#: 정적 화면 파일 디렉터리(DOM 검사 대상)
STATIC_DIR = PROJECT_ROOT / "src" / "webapp" / "static"


def load_scenario(scenario_id: str) -> dict:
    """data/fixtures/scenario_<id>.json을 UTF-8로 읽어 dict로 반환한다."""
    path = FIXTURES_DIR / f"scenario_{scenario_id}.json"
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def read_static(name: str) -> str:
    """src/webapp/static/<name>을 UTF-8로 읽는다."""
    return (STATIC_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def records_dir(tmp_path) -> Path:
    """판단 기록 임시 저장 경로(아직 존재하지 않음 — 자동 생성 검증용)."""
    return tmp_path / "records"


@pytest.fixture
def client(records_dir) -> TestClient:
    """기본 fixture(data/fixtures)를 쓰는 새 앱 클라이언트(세션 카운터 0에서 시작)."""
    return TestClient(create_app(records_dir=records_dir))


@pytest.fixture
def make_variant_client(tmp_path, records_dir):
    """원본 fixture를 변형한 사본으로 앱을 만드는 팩토리(원본 무수정).

    사용: client = make_variant_client("loss8", lambda fx: fx.pop("disclosures"))
    """
    def _make(scenario_id: str, mutate) -> TestClient:
        fx = load_scenario(scenario_id)
        mutate(fx)
        vdir = tmp_path / "fixtures"
        vdir.mkdir(parents=True, exist_ok=True)
        with open(vdir / f"scenario_{scenario_id}.json", "w", encoding="utf-8") as fp:
            json.dump(fx, fp, ensure_ascii=False, indent=2)
        return TestClient(create_app(fixtures_dir=vdir, records_dir=records_dir))

    return _make
