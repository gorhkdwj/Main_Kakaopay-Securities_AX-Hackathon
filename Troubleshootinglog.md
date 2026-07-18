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

### T-0716-1112-main · pykrx 익명 수집 불가 — KRX 계정 로그인 요구 (R2 리스크 사전 실현)
**발생 상황** — D7 조건("기술적으로 호출이 되는가") 사전 검증을 위해 venv 구성 직후 pykrx 지수 조회 스모크 테스트 실행(7/17 본수집 하루 전).
**증상** — `stock.get_index_ohlcv()`가 「KRX 로그인 실패: KRX_ID 또는 KRX_PW 환경 변수가 설정되지 않았습니다」 + JSON 파싱 오류(`Expecting value: line 1 column 1`) + `KeyError: '지수명'`으로 실패.
**확인된 원인** — 현행 pykrx가 KRX 데이터 API 접근에 계정 자격증명(환경변수 KRX_ID/KRX_PW)을 요구 — 기획서 R2가 예측한 "KRX 로그인 요구" 시나리오의 실현. (불확실점: KRX 정보데이터시스템 웹 수동 다운로드의 로그인 요구 여부는 미확인)
**조치(최종 해결)** — 대안 yfinance를 즉시 설치·검증: 코스피(^KS11)·코스닥(^KQ11) 지수 종가 조회 성공(7/16 당일분 포함). 수집 주 경로를 yfinance로 교체(D-0716-1115-main), requirements.txt·lock 갱신, 계획 2종(S6·R2) 반영.
**재발 방지** — 외부 데이터 의존은 사용 전날이 아니라 **가능한 가장 이른 시점에 스모크 테스트**(이번처럼 D+1 전 검증으로 R2가 무위험 전환됨). pykrx는 KRX 계정 생성 시에만 대체 옵션으로 유지.

### T-0716-1335-main · 실계좌 캡처를 커밋 대상에 포함 시도 — 권한 계층에서 차단(노출 0)
**발생 상황** — S4 스펙 커밋 시 `git add -A`가 사용자 제공 앱 캡처(`docs/references/image/`)를 포함, 원격 push까지 한 명령으로 실행 시도.
**증상** — 실행 전 권한 분류기가 거부: 캡처에 실계좌 정보(보유·잔고·거래 확인)가 포함되며 사용자는 "UI 참고"만 지시했지 저장소 공개(커밋·푸시)를 승인한 적 없음.
**확인된 원인** — 세션의 비밀정보 스캔이 텍스트 패턴(API 키 등) 중심이라 **이미지 속 실계좌 정보를 스캔 대상에서 제외**했고, "사용자가 프로젝트 폴더에 넣은 자료 = 커밋 대상"으로 잘못 일반화함. 헌법 §7의 "실제 고객·계좌정보 금지"는 사용자 본인의 실계좌 데이터에도 적용되어야 함.
**조치(최종 해결)** — 스테이징 미실행 확인(git 이력 오염 0·원격 노출 0) → `.gitignore`에 `docs/references/image/` 등재(로컬 참고 전용) → 스펙 문서에 Git 제외 사실 명기(§2의 텍스트 관찰 기록이 캡처 없이도 구현 근거로 성립).
**재발 방지** — ① 이미지·바이너리는 텍스트 스캔과 무관하게 **내용 확인 전 커밋 금지** ② 사용자 제공 원자료는 기본 로컬 전용으로 취급하고, 커밋은 명시 승인 시에만 ③ push 전 스캔 체크리스트에 "신규 바이너리 포함 여부" 항목 추가(S3 게이트 스크립트 구현 시 반영).

### T-0716-1510-main · ⑥ 바텀시트가 닫히지 않아 전 화면 클릭 차단 (hidden 속성 vs CSS display 우선순위)
**발생 상황** — S4 통합 직후 사용자 브라우저 확인에서 "수량 입력 후 모의 체결하기를 눌러도 진행이 안 되고, 이후 어떤 버튼도 동작하지 않음" 신고.
**증상** — 모의 체결 자체는 성공(뒤 배경에 체결 완료 카드 렌더·CALC ID 발급)했으나, 바텀시트 오버레이가 닫히지 않고 화면 전체를 덮어 모든 클릭을 가로챔 — "먹통"으로 인지됨.
**확인된 원인** — `#sheet-backdrop { display:flex }`(ID 선택자)가 브라우저 기본 `[hidden]{display:none}`(속성 선택자)보다 우선해, JS의 `hidden=true`가 시각적으로 무력화됨. 자동 검증(TestClient)은 서버 응답 계층만 보고 JS·CSS 런타임을 못 보는 갭에서 발생 — subagent도 "실브라우저 육안 리허설 미수행"으로 명시했던 영역.
**조치(최종 해결)** — `[hidden]{display:none !important}` 전역 규칙 추가 후, **playwright 실브라우저로 사용자 재현 경로 전체를 자동 검증**: 홈→⑤(의향 선택·일지 입력)→⑥ 시트 열림(display:flex)→모의 체결→시트 닫힘(display:none)→다음 버튼 정상(⑦ 이동)→기록 저장(REC 발급)→⑧, first_buy 자동완성 초안·안전모드 토글 on/off까지 통과, 콘솔 에러·경고 0.
**재발 방지** — ① UI 표시 토글은 `hidden` 속성 + 전역 `[hidden]` 규칙 병용을 표준으로 ② 화면(JS·CSS) 변경의 통합 게이트에 **실브라우저 완주 검증(playwright)** 을 포함 — TestClient 통과만으로 화면 완료를 선언하지 않는다.

### T-0716-2046-main · DEMO 패널 시나리오 전환 무반응(사용자 환경) — 3중 silent failure
**발생 상황** — 사용자 실사용 검토 중 "데모 시연 장치의 -8% 급락 이외 다른 시나리오 선택이 안 됨" 신고. 같은 코드로 검증 서버(8766)에서는 직전 라운드 playwright 전환 성공 이력 존재.
**증상** — DEMO 패널의 profit15·first_buy 버튼 클릭 시 화면 무변화·오류 표시 없음.
**확인된 원인** — 정적 파일·fixture는 요청마다 재로딩(app.py:329-336)이라 서버 프로세스 구버전 단독으로는 설명 불가. 코드에서 확정된 결함 3건: ① `loadScenario` 실패 시 silent return(app.js:88 — 404·파싱 실패가 무반응으로 인지됨) ② `api()`의 fetch 예외 미방어(app.js:63 — 네트워크 예외 시 unhandled rejection, 무표시) ③ fixture JSON 파손 시 미처리 500(app.py:336). (불확실점: 사용자 환경의 실제 트리거 — 브라우저의 구버전 app.js 캐시 또는 일시 네트워크 예외로 추정, 원격 재현 불가)
**조치(최종 해결)** — 실패 3경로 전부 가시화: api() fetch try/catch, `#app-error` 오류 카드(사유+이전 화면 유지 안내+[다시 시도]), `FixtureInvalidError` → 500 계약 오류. README 실행 방법에 `--reload` 권고·강력 새로고침(Ctrl+F5) 안내 신설. 신선 서버에서 3시나리오 전환+오류 주입 playwright 재검증.
**재발 방지** — ① **어떤 fetch 실패도 화면에 흔적을 남긴다**(silent return 금지 — T-0716-1510의 "무반응=먹통 인지" 교훈 일반화) ② 데모 실행 안내에 서버·브라우저 캐시 재기동 절차 명시.

### T-0717-2031-main · 포트 8765 기동 실패 [WinError 10013] — 재부팅 후 OS 동적 포트 예약 범위 이동
**발생 상황** — 7/17 저녁, 사용자가 표준 실행 명령(`--port 8765 --reload`)으로 앱 기동 시도.
**증상** — `ERROR: [WinError 10013] 액세스 권한에 의해 숨겨진 소켓에 액세스를 시도했습니다` — 서버 기동 자체가 실패(전날 10048=포트 사용 중과 다른 오류).
**확인된 원인** — `netstat`상 8765 리스너 없음(충돌 아님). `netsh interface ipv4 show excludedportrange`로 확인: **8765가 예약 범위 8687–8786에 포함**(8766도 동일 범위). 재부팅 후 Hyper-V/WSL(winnat)의 동적 포트 예약 범위가 이동해 전날 정상이던 포트가 차단된 것 — 예약 범위는 부팅마다 달라질 수 있음.
**조치(최종 해결)** — 범위 밖 후보(9000·8917·8560) bind 검증 → **9000에서 uvicorn 실기동·HTTP 200·/api/scenarios 정상 응답 확인** 후 검증 프로세스 종료. README 실행 방법에 10013 진단·대체 포트·영구 예약 절차(관리자: winnat 정지 → `add excludedportrange` 8765 → 재시작) 추가.
**재발 방지** — ① **본선 당일 기동 절차에 "10013 시 excludedportrange 확인 → 범위 밖 포트" 포함**(포트 번호는 관례일 뿐 데모 동작·테스트와 무관) ② 리허설(S7) 체크리스트에 재부팅 직후 기동 확인 1회 추가 권고.

### T-0717-2340-main · Claude 실호출 3연속 실패 — temperature 거부·JSON 잘림·타임아웃 실측
**발생 상황** — 사용자 키 설정 직후 라이브 브리핑 검증(scenario_loss8, claude-sonnet-5).
**증상** — ① 1차: HTTP 400 `invalid_request_error` — "`temperature` is deprecated for this model"(0.7초 즉시 거부) ② 2차(temperature 제거 후): 8초 ReadTimeout → 캐시 폴백 ③ 3차(타임아웃 90초): 응답은 왔으나 JSON 파싱 실패(Unterminated string, char 1210) — max_tokens=2000 상한에서 한국어 JSON이 중간 절단. 참고 실측: haiku-4-5는 9.9초에 완주.
**확인된 원인** — ① claude-sonnet-5가 temperature 파라미터를 deprecated로 거부(구모델 관례를 그대로 이식한 코드 결함) ② 브리핑 1건 생성 실소요가 10~22초로 앱 내 8초 타임아웃 상한 초과 ③ 출력 상한 2000토큰이 실제 응답 길이(한국어 facts 6건+해석+질문)보다 작음. (불확실점: 소요 시간은 네트워크·부하에 따라 변동 — 22.3초는 1회 실측값)
**조치** — ① temperature 파라미터 제거(출력 안정성은 프롬프트 JSON 계약+guard가 담당) ② MAX_OUTPUT_TOKENS 2000→4000 ③ 타임아웃 이원화: auto=8초(시연 화면 빠른 강등 유지)·live 강제 모드=30초(명시적 의도는 기다림). 최종 해결: live 모드 22.3초 성공, guard 차단 0·경고 0, 288 tests·게이트 통과.
**재발 방지** — 실호출 검증 없이 API 파라미터를 가정하지 않는다(모델 교체 시 1회 실호출 스모크 필수 — llm.py 상수에 실측 근거 주석 명기). auto 모드가 키 존재 시 매 로드 8초를 소모하는 구조이므로 시연 기본은 캐시 경로를 권장(BRIEFING_MODE=cache), 라이브는 의도적 시연에서만.

### T-0718-0500-main · 서브에이전트 대화가 제출 로그(메인 세션 JSONL)에 미포함 — 로그 수집 예행 발견
**발생 상황** — S7 로그 수집 예행에서 제출 로그 완전성 감사(구조 파싱, 내용 비덤프).
**증상** — 메인 세션 로그(`logs/claude-code/79f46e7d…jsonl`, 539줄=user164+assistant375)에 `isSidechain=true` 줄 0. 이 세션은 다수 서브에이전트(Explore/Plan)를 띄웠으나 그 내부 대화가 로그에 없음. codex 포함 12개 파일 모두 JSONL 유효·비밀정보 0.
**확인된 원인** — `save_log.py` 슬림(`_claude_has_text`)은 `isSidechain`을 걸러내지 않으므로, sidechain=0은 **메인 트랜스크립트 자체에 서브에이전트 턴이 기록되지 않음**을 의미(서브에이전트 별도 처리). (불확실점: 이번 턴 서브에이전트가 Stop 훅 후 별도 UUID 로그로 생기는지 미확정 — 다음 세션 재측정 필요)
**조치** — 감사 리포트(`out/submission/log_audit.md`)에 판정 기록. 영향 평가: **실격 위험 낮음** — ① 참가자↔메인 AI 본대화 전량 포함 ② 슬림은 주최 제공 공식 훅의 자동 동작(수동 편집 아님 — "편집·발췌=실격" 조항 비저촉) ③ 메인 응답이 서브에이전트 작업 목적·결과를 서술해 과정이 로그로 읽힘. `save_log.py`는 수정 금지(공식 훅)이므로 임의 개조로 억지 포함시키지 않음.
**재발 방지** — 메인 응답에서 서브에이전트 작업의 목적·핵심 결과를 계속 명시(과정 legibility 유지). 다음 세션 시작 시 `logs/claude-code` 파일 수·sidechain 재측정으로 별도 로그 생성 여부 확정.

### T-0718-0929-main · first_buy 시나리오 전환 크래시 — 지연 브리핑 분리(D-0718-0355) 이후 renderStep1의 브리핑 즉시 참조 잔존
**발생 상황** — 차트 데이터화(D-0718-0931) 브라우저 검증 중 playwright로 loadScenario('first_buy') 호출.
**증상** — `TypeError: Cannot read properties of undefined (reading 'next_questions')` at renderStep1(app.js:460) — first_buy 전환 시 renderAll 단계에서 크래시(loss8·profit15는 정상).
**확인된 원인** — D-0718-0355가 브리핑을 /api/scenario 응답에서 분리(지연 생성)했는데, renderStep1의 plan==null 분기(first_buy 전용 — 질문 초안을 브리핑 next_questions에서 인용)가 `S.data.briefing`을 방어 없이 즉시 참조. 즉 D-0718-0355 이후 first_buy 로드·전환이 UI에서 계속 깨져 있었던 기존 결함(차트 변경과 무관). 당시 검증이 first_buy의 이 경로를 지나치지 않아 미발견.
**조치(최종 해결)** — renderStep1 방어 접근(briefing 부재 시 질문 초안 자리에 "브리핑이 준비되면 질문 초안이 여기에 채워져요." 표시) + requestBriefing 성공 시 renderStep1 재호출(도착한 질문 초안 반영). playwright로 first_buy 전환·차트·질문 초안 자리 표시 재검증, 콘솔 오류 0, 305 tests·게이트 통과.
**재발 방지** — 응답 스키마에서 필드를 분리(지연화)할 때는 해당 필드의 **모든 렌더 참조 지점을 grep으로 전수 확인**(이번 누락 원인 — renderStep2만 수정하고 renderStep1의 plan==null 분기를 놓침). 시나리오 전환 스모크는 3종 전부를 도는 것을 기본으로.
