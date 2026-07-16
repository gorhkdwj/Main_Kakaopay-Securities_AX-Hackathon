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

### T-0716-1040-main · Windows 셸·인코딩 이슈 3건 (한글 경로 스캔 누락·커밋 메시지 인자 분할·콘솔 cp949 크래시)
**발생 상황** — D-0716-1026 반영 커밋과 S1 검증 스크립트 실행 중 연쇄 발생.
**증상** — ① `git diff --name-only`가 한글 경로(목업 HTML)를 8진수 이스케이프+따옴표로 출력해 Select-String이 "Illegal characters in path"로 해당 파일 스캔 누락(T-0716-0932와 같은 계열 — 이번엔 rename이 아니라 quotepath가 원인) ② 커밋 메시지 here-string 안의 큰따옴표가 PowerShell 5.1 네이티브 인자 처리에서 메시지를 분할해 `git commit` 실패(pathspec 오류) ③ `validate_fixture.py`의 em dash(—) 출력이 cp949 콘솔에서 UnicodeEncodeError 크래시.
**확인된 원인** — ① git 기본 `core.quotepath=true` ② PS 5.1의 네이티브 명령 인자 재인용 규칙(내장 큰따옴표 미이스케이프) ③ Windows 콘솔 기본 코드페이지 cp949.
**조치(최종 해결)** — ① `git -c core.quotepath=false diff --name-only`로 재실행해 9파일 전수 스캔(누락 0·검출 0) ② 메시지의 큰따옴표를 괄호 표기로 대체 후 커밋 성공(cc4f243) ③ 스크립트 서두에 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` 추가 후 전건 통과.
**재발 방지** — 스캔·수집 명령은 항상 `-c core.quotepath=false` 병용(S3의 scan_secrets.py에 내장), 커밋 메시지에 큰따옴표 미사용(따옴표 필요 시 「」·[ ] 사용), 이후 모든 파이썬 스크립트에 stdout 재설정 패턴 포함.
