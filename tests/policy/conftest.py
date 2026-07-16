"""tests/policy 공통 설정 — 프로젝트 루트를 sys.path에 추가해
`src.policy.*` 임포트를 가능하게 한다(src는 네임스페이스 패키지)."""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SAFETY_SET_PATH = Path(__file__).resolve().parent / "safety_set.json"


def load_safety_set() -> dict:
    """안전 테스트셋(차단 B세트·통과 P세트) 파일을 로드한다."""
    with open(SAFETY_SET_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def safety_set() -> dict:
    return load_safety_set()
