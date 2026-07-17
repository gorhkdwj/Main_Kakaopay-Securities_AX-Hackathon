# 판단 여권 (Decision Passport)

> 매수·매도·보류의 판단이 흔들리는 순간의 초보 투자자에게, 출처 있는 판단 재료를 구조화해 주고 선택권을 돌려주는 AI 판단 전 브리핑. 대표 시연은 판단 왜곡이 가장 큰 고불안 순간(-8% 급락 보유) — AX 인재전쟁 본선(카카오페이증권 트랙) 프로젝트.

## 개요
- 목적: 초보 투자자가 어떤 판단 순간에든(매수·매도·보류) 스스로 설명 가능한 결정을 내리도록 돕는 데모 시스템 — 우선 공략·대표 시연은 고불안 순간(급락·손실 보유)
- 주요 사용자: 초보 투자자(경험·역량 축 정의) / 시연 청중: 본선 심사위원
- 최종 산출물: 로컬 웹앱 데모 + Codex 플러그인 포장 + 결과물 브리프 + 프롬프트 로그
- 원칙: AI는 결론을 말하지 않는다 — 출처·기준시각 있는 사실, 대칭 시나리오, 비용·세금·D+2 사전 고지, 모의 체결까지만

## 설치 (다른 환경에서 처음 clone했을 때)
`.venv`는 Git에 올리지 않는다(가상환경은 OS 종속 — 재구성 레시피만 커밋). Python **3.10 권장**(락파일 기준), 설치 시에만 인터넷 필요:

```
# 표준(pip)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt

# 또는 uv 사용 시 (pyproject.toml이 없으므로 uv sync가 아니라 uv pip sync)
uv venv --python 3.10
uv pip sync requirements.lock.txt
```

- `requirements.lock.txt` = 전체 버전 고정(재현용), `requirements.txt` = 직접 의존 8개(버전 미고정).
- `.env`(API 키)와 `logs/`(프롬프트 로그)도 Git 제외 — 새 환경에서는 `.env`를 직접 만들고, 그 환경의 `logs/`도 제출 전 수집 대상이다(CLAUDE.md §13-4).

## 실행 방법
데모 웹앱(오프라인 — LLM·외부 네트워크 0회로 완주):

```
.\.venv\Scripts\python.exe -m uvicorn src.webapp.app:app --port 8765 --reload
```

- 브라우저에서 http://127.0.0.1:8765 접속. 반드시 **프로젝트 루트에서** 실행한다(src는 namespace package).
- 테스트 전체 실행: `.\.venv\Scripts\python.exe -m pytest -q`
- **변경 반영 규칙**: 정적 파일(`src/webapp/static/`)과 fixture(`data/fixtures/`)는 서버 재시작 없이 반영된다 — 브라우저에서 강력 새로고침(Ctrl+F5)만 하면 된다. `app.py` 등 파이썬 코드는 서버 재시작이 필요하다 — `--reload` 옵션을 켜 두면 자동 재시작된다.

## 프로젝트 구조
- `src/` 실행 코드(`engine/` 결정론 계산 엔진 · `policy/` 표현 가드 · `webapp/` 웹앱 본체 · `.codex-plugin/` 플러그인 포장 — 예정)
- `tests/` 테스트·안전 테스트셋(엔진·가드·웹앱 — pytest)
- `scripts/` 데이터 수집·검증 스크립트 (research: 리서치 단계 산출)
- `tools/` 보조 스크립트(프롬프트 로그 훅 — 수정 금지)
- `data/snapshots/` 동결 시세 스냅샷 · `data/fixtures/` 오프라인 시나리오
- `docs/` 기획·리서치·검증 문서 · `out/` 임시 산출물(Git 제외) · `logs/` 프롬프트 로그(무편집 제출물, Git 제외)

## 문서
- 작업 규칙(헌법): `CLAUDE.md`(Claude) · `AGENTS.md`(Codex) — 동일한 공통 헌법과 멀티 세션 worktree 협업 규약을 제공한다.
- 헌법 동기화: 공통 규칙 변경 시 두 파일을 같은 작업 단위에서 함께 수정하고, 도구별 차이는 각 문서의 전용 블록에만 둔다.
- 작업 이력: `Worklog.md` · 주요 결정: `Decisionlog.md` · 문제 해결: `Troubleshootinglog.md`
- 계획 3종(`docs/plans/`): 기획 `project-plan.md` · 구현 `implementation-plan.md` · 검증 `validation-plan.md` — 모든 구현·설계 작업의 기준(헌법 §2)
- 기준 계약: `docs/requirements-contract.md` — 지표·수식·스키마·표기의 단일 기준(골든값·안전 지표 분모·금지 표현 사전 포함, 헌법 §5)
- 리서치(교차검증 완료): `docs/report/2026-07-17_리서치_최종보고.html` (출처 402·주장 123) · 목업: `docs/mockup/2026-07-17_판단여권_목업.html`
- 본선 규정: `docs/notice/` — **당일 공지가 본 저장소의 모든 문서보다 우선한다**

## 고지
본 프로젝트는 해커톤 데모이며 투자 권유가 아닙니다. 실주문·개인화 종목 추천·수익 보장을 구현하지 않습니다. 데모 데이터는 가상 종목입니다.
