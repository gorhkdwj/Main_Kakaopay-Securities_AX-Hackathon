# Troubleshootinglog · 판단 여권 (Decision Passport)

실제 오류·실패·환경 문제·검증 실패·설계 충돌이 발생하면 기록한다. 같은 문제가 반복되면 새 T-ID를 만들기 전에 기존 T-ID를 먼저 확인한다. (규칙: CLAUDE.md 11·13절 — ID는 `T-MMDD-HHMM-세션`)

## 기록 형식
```
### T-MMDD-HHMM-세션 · 문제 제목
**발생 상황** / **증상** / **확인된 원인**(+불확실점) / **조치**(+최종 해결) / **재발 방지**
```

---

### T-0716-0932-main · 비밀정보 스캔이 git rename 경로를 오파싱해 3개 파일 누락
**발생 상황** — D-0716-0923 커밋 전 push 스캔(임시 PowerShell 명령) 실행 중.
**증상** — `git status --porcelain`의 rename 표기(`R old -> new`)를 단일 경로로 해석해 Test-Path가 "Illegal characters in path" 오류를 내고 이동된 계획 문서 3개가 스캔에서 제외됨.
**확인된 원인** — porcelain 출력 파싱 시 rename 화살표 미처리(임시 명령의 결함).
**조치** — 해당 3개 파일은 본 세션이 직접 작성한 문서로 내용상 비밀정보 없음을 확인 후 push 유지. 이후 스캔은 `git diff --cached --name-only`(rename도 신규 경로만 출력)를 사용.
**재발 방지** — 스캔을 임시 명령이 아니라 `scripts/gate/scan_secrets.py`(S3 게이트 스크립트에 통합)로 구현하고, 병합 게이트 체크리스트(헌법 §10-⑤)의 표준 실행 수단으로 지정.
