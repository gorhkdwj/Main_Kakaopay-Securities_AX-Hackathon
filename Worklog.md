# Worklog · 판단 여권 (Decision Passport)

주요 사용자 요청이 끝날 때마다 아래 형식으로 누적 기록한다. (규칙: CLAUDE.md 11·13절 — ID는 `W-MMDD-HHMM-세션`, 최신 항목을 위에, append-only, 병합 시 타임스탬프순 보존)

## 기록 형식
```
### W-MMDD-HHMM-세션 · 작업 제목
**요청** / **수행 작업** / **변경 파일** / **검증** / **판단 근거** / **결과**
```

## 파일 소유권 매트릭스 (병렬 작업 시 갱신 — CLAUDE.md 13-5)
| 세션(브랜치) | 담당 경로 | 상태 |
|---|---|---|
| main | 전체 (현재 단일 세션) | 활성 |

---

### W-0716-0952-main · 헌법에 단계 정합 QA 루프 추가
**요청**
- 모든 작업 단계에서 직전·직후·전체 흐름과의 충돌·어긋남을 검토·검증하는 QA 피드백 후 자체 수정 단계를 헌법에 의무화.

**수행 작업**
- CLAUDE.md·AGENTS.md §6에 "단계 정합 QA 루프"(3방향 정합 검토 → 보고 전 자체 수정 → 해소 불가 시 중단·상신, 발견 0건도 명시) 동일 신설, §4 단계 완료 보고 항목에 QA 결과 연결. Decisionlog D-0716-0952-main 기록.

**변경 파일**
- 수정: CLAUDE.md, AGENTS.md, Decisionlog.md, Worklog.md

**검증**
- 정합 QA(본 규칙을 본 작업에 자체 적용): ①직전 — 기존 §6 안전 게이트·§10 병합 게이트와 역할 중복 없음(게이트=말단 방어선, 루프=단계 내 조기 방어선으로 상보) ②직후 — S1부터 적용 가능(implementation-plan의 "다음 단계로 전달" 항목이 대조 기준으로 이미 존재) ③전체 — 계획 3종·계약·§14와 충돌 없음, 두 헌법 공통 본문 동일 적용 확인. 발견·수정 0건 — 정합 QA 통과.

**판단 근거**
- 단계 사이 정합 붕괴는 병렬 분업의 최빈 사고 유형 — 발견 비용이 가장 싼 단계 내부에 방어선 추가.

**결과**
- 완료. 이후 모든 단계 보고에 정합 QA 결과가 포함됨.

---

### W-0716-0945-main · 제품결정로그 스텁 삭제 (기록처 단일화 마무리)
**요청**
- 제품결정로그(이전 완료 후 스텁 상태)를 유지할 필요가 있는지 판단.

**수행 작업**
- 판단: 불필요 — 내용은 D-0716-0210-main으로 전량 이전, 원문은 git 이력(3a0f6a8)에 보존, 스텁 유지 시 결정 기록처가 이원화될 위험만 남음.
- 저장소 전체 참조 검색으로 살아있는 링크 부재 확인(남은 언급은 로그의 이력 서술뿐) 후 `git rm docs/plans/2026-07-17_제품결정로그.md`.

**변경 파일**
- 삭제: docs/plans/2026-07-17_제품결정로그.md / 수정: Worklog.md

**검증**
- grep으로 참조 0건 확인. 과거 Decisionlog 항목(D-0716-0853의 "스텁으로 대체" 서술)은 당시 결정의 기록이므로 수정하지 않음(append-only) — 본 W-항목이 후속 정리를 기록함.

**판단 근거**
- 단일 기록처 원칙(헌법 §11)과 git 이력 보존으로 스텁의 안내 기능이 대체됨.

**결과**
- 완료. 결정 기록처는 루트 Decisionlog.md 하나로 확정.

---

### W-0716-0923-main · 계획 문서 plans/ 통합·상세화 + 기준 계약 전면 상세화 + 헌법 지침 추가
**요청**
- docs/ 바로 하위의 plan 3종을 docs/plans/로 이동·통합하고 리서치 최종 보고 기반으로 세세하게 상세화. 두 헌법에 계획 기반 작업 지침 추가. 기준 계약 문서를 지표 정합성의 핵심 문서로 자세하게 작성.

**수행 작업**
- git mv로 project/implementation/validation-plan.md를 docs/plans/로 이동(이력 보존).
- project-plan: 문제 문장·근거 3계층·타깃 축·8단계 흐름·성공 기준·당일 타임라인·전환 규칙·리스크 8건으로 상세화(근거 ID 연결).
- implementation-plan: 아키텍처 다이어그램(계산·생성 분리×폴백 3계층), S1~S8 전 단계 상세(완료 조건·중단점), 당일 타임박스, 병렬화 계획(worktree 3분담+인터페이스 고정), 기술 스택.
- validation-plan: 엔진 단위 테스트 U-01~12(골든값·경계값), 안전 테스트셋 카테고리별 차단/통과 세트 설계(분모 고정), 통합 I-01~08, 안전 게이트 표, 리허설 체크리스트, 미검증 범위.
- requirements-contract: 용어·ID 체계·데이터 스키마(fixture/manifest/기록)·지표 정의·수식·골든값 4세트·AI 응답 계약 검증 규칙·금지/허용 표현 사전 v1·상태 판정·표기 계약·안전 지표 분모·데모 고정값 대장(§13)으로 전면 재작성.
- CLAUDE.md·AGENTS.md §2·§3·§5에 동일한 계획 기반 작업 지침 추가(동기화 규칙 준수), README 문서 안내 갱신.

**변경 파일**
- 이동+재작성: docs/plans/{project,implementation,validation}-plan.md · 재작성: docs/requirements-contract.md
- 수정: CLAUDE.md, AGENTS.md, README.md, Decisionlog.md(D-0716-0923-main), Worklog.md

**검증**
- 골든값 수기 재검산(10주: 수수료 69·거래세 920·수령 459,011·실현 -40,989 / 30주·1주·유지 포함), 두 헌법 공통 본문 동일 적용 확인. 구현 미착수 — 계약·계획의 코드 검증은 S2~S3 테스트에서 수행 예정.

**판단 근거**
- 병렬 세션 시작 전에 계약·계획을 인터페이스 명세 수준으로 끌어올려야 worktree 분담이 충돌 없이 성립.

**결과**
- 완료: 계획·계약 체계 확정. 남은 작업: S1(fixture 작성·스키마 검증 스크립트)부터 구현 착수.

---

### W-0716-0911-main · Claude·Codex 작업 헌법 동기화
**요청**
- `CLAUDE.md`를 확인해 Codex CLI Agent도 동일하게 작업하도록 `AGENTS.md`로 동기화하고, Codex에만 필요한 차이만 별도 적용. README와 두 헌법에 동기화 지침 명시.

**수행 작업**
- `CLAUDE.md`의 공통 헌법을 기준으로 `AGENTS.md`를 생성하고, 제목과 `[Codex 전용]` 실행·로그 검증 규칙만 다르게 구성.
- 두 헌법에 공통 규칙 동시 수정, 도구 전용 블록 격리, 불일치 정합화 절차를 명시.
- README의 작업 규칙 안내를 `CLAUDE.md`·`AGENTS.md` 한 쌍과 동기화 원칙으로 갱신.

**변경 파일**
- 신규: `AGENTS.md`
- 수정: `CLAUDE.md`, `README.md`, `Worklog.md`, `Decisionlog.md`

**검증**
- 두 헌법의 공통 본문 동일성, Codex 전용 블록 격리, README 상호 참조, Markdown 공백 오류와 Git diff를 확인.

**판단 근거**
- Codex는 `AGENTS.md`를 지속 지침 진입점으로 사용하므로 Claude 전용 파일만으로는 두 에이전트의 동일 규칙 적용을 보장할 수 없음. 다만 도구 차이는 공통 헌법을 분기하지 않고 명시적 전용 블록으로 제한해야 유지보수 드리프트를 줄일 수 있음.

**결과**
- 완료: Claude·Codex 공통 헌법 동기화 구조와 Codex CLI 로그 검증 예외 규칙을 문서화. 이후 공통 규칙 변경 시 두 헌법을 같은 작업 단위에서 함께 수정해야 함.

---

### W-0716-0853-main · 프로젝트 운영 체계 셋업 (/project-setup)
**요청**
- 지금까지의 계획(리서치→PRD→목업→PD-01)을 바탕으로 프로젝트 구조 셋업. 제품결정로그의 Decisionlog 통합 여부 판단, 멀티 세션 worktree·타임라인 기반 로그 병합 규약 설계 포함.

**수행 작업**
- 현재 상태 파악: git 저장소 확인(main, origin 존재, 초기 커밋 1건), `logs/` gitignore 상태·훅 설정(.claude/.codex/tools) 추적 상태 확인.
- 운영 파일 생성: CLAUDE.md(작업 헌법 — 멀티 세션 규약 13절·리서치 확정 제약 14절 포함), Worklog.md, Decisionlog.md(PD-01 이전 + 규약 결정 기록), Troubleshootinglog.md, README.md, docs/project-plan.md, docs/requirements-contract.md, docs/implementation-plan.md, docs/validation-plan.md.
- 폴더 생성: src/, tests/, out/, docs/references/, data/snapshots/, data/fixtures/ (+.gitkeep).
- .gitignore 보강(out/·비밀정보·OS 파일 등), 구 제품결정로그를 스텁으로 대체.

**변경 파일**
- 신규: CLAUDE.md, README.md, Worklog.md, Decisionlog.md, Troubleshootinglog.md, docs/project-plan.md, docs/requirements-contract.md, docs/implementation-plan.md, docs/validation-plan.md, 폴더 6종(.gitkeep)
- 수정: .gitignore(항목 추가), docs/plans/2026-07-17_제품결정로그.md(이전 안내 스텁으로 대체)

**검증**
- 파일 생성·구조 확인만 수행. **구현 미착수**(스킬 4단계 정지). git 커밋은 사용자 확인 대기.

**판단 근거**
- 본선(7/18)까지 다수 세션 병렬 작업이 예정되어, 구현 전에 기록·병합·보안 규칙을 헌법으로 고정하는 것이 우선.

**결과**
- 완료: 운영 체계 셋업. 남은 작업: 1차 보고 승인 → 초기 커밋 → 구현 S1(오프라인 fixture 완주 골격)부터 착수.
