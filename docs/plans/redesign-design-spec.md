<!-- 판단 여권 리디자인 · 실앱 디자인 스펙 (캡처 26장 병렬 분석 합성 — 2026-07-18)
     지위: 리디자인 작업의 화면 재현 단일 기준(s4-ui-spec §3의 정밀화). 캡처 원본은
     docs/references/image/ (로컬 전용·커밋 금지). 모든 hex·px는 캡처 육안 추정→430px
     환산값이며 [데모 고정] 성격 — 실서비스 전 브랜드 가이드로 재검토.
     개인 데이터(계좌·잔고·보유) 미포함 검수: 저장 시 grep 스캔 수행. -->

# 카카오페이증권 디자인 시스템 스펙 — 판단 여권 데모 재현 기준서 (v1.0)

> 근거: 캡처 6그룹(종목상세 26–29 / 주문확인시트 30–32 / 호가·원탭주문 33–34 / 홈·탐색 1·2·3·22 / 리스트·카드 14–23 / 커뮤니티·달력·주문내역 24·25·35·36) 병렬 분석 종합.
> 적용 대상: 430px 폭 컨테이너, 순수 CSS, 오프라인, 시스템 폰트만. 모든 px는 원본 720px 캡처의 ×0.6 환산 확정값입니다.
> 색상은 전 분석 공통으로 육안 추정 hex이며, 교차 확인된 값을 확정값으로 채택하고 불일치는 병기했습니다.

---

## 1. 디자인 토큰 확정값

### 1.1 색상 (CSS 커스텀 프로퍼티)

```css
:root {
  /* 표면 */
  --bg:           #FFFFFF;            /* 페이지·시트·카드 기본 — 6/6 분석 일치 */
  --canvas-gray:  #F2F3F6;            /* 대시보드형 화면(발견·증권홈) 캔버스 — 분석4·5 (병기: #F4F5F7) */
  --band:         #F4F5F7;            /* 섹션 구분 굵은 밴드 — 분석5·6 (병기: 분석1 #F1F3F5, 분석4 #F4F4F6) */
  --dark-surface: #17191C;            /* 다크 배너·트리맵·툴팁 — 분석4·5 (병기: 분석6 #17181A) */

  /* 텍스트 위계 (4단) */
  --ink-900: #191F28;                 /* 제목·가격·값 — 분석1·3 (병기: #17181C·#1A1C20·#111) */
  --ink-700: #333D4B;                 /* 본문·상세 값 — 분석1·3 (병기: 분석5 #333A42) */
  --ink-500: #8B95A1;                 /* 라벨·메타·비활성 — 분석1·3·5 교차 확인 (병기: 분석6 #8B8F97) */
  --ink-300: #B0B8C1;                 /* 힌트·"실시간/지연"·미래 날짜 — 분석3·5·6 */
  --ink-200: #C4C9CF;                 /* 차트 축 라벨·chevron 최연한 톤 */

  /* 기능색 — 국내 증권 관례: 파랑=하락·판매·손실·링크 / 빨강=상승·구매·이익 */
  --blue:      #3182F6;               /* 분석2·3·6 교차 확인 — 확정 (병기: #1E6EF4~#2D7BF7, #3B7DF7, #1B7DFB) */
  --red:       #F04452;               /* 분석3·5·6 교차 확인 — 확정 (병기: CTA 버튼 관찰값 #F5352C~#F64C4C — 데모는 단일 토큰 통일) */
  --blue-bg:   #E8F3FF;               /* 파랑 연면(배지·판매 셀) */
  --red-bg:    #FFECEF;               /* 빨강 연면(배지·구매 셀) */
  --blue-depth:#DCEBFF;               /* 호가 잔량 깊이 막대 */
  --red-depth: #FFE2E6;
  --blue-cum:  #C9DEFA;               /* 누적 호가 바 */
  --red-cum:   #F9D4D6;
  --warn-bg:   #FDEDEE;               /* 경고 배너 연분홍 (병기: #FDEAEE) */

  /* 회색 유틸 */
  --chip-gray:  #F2F4F6;              /* 칩·pill 비활성 배경 — 분석1·3 (병기: #EFF1F4, #F4F5F8) */
  --seg-track:  #F2F3F5;              /* 세그먼트 토글 트랙 — 분석3·5·6 일치 */
  --hairline:   #EFF0F2;              /* 1px 구분선 — 분석6 (병기: #EEF0F3, #F0F0F0) */
  --dotted:     #E0E1E3;              /* 주문 시트 점선 — 분석2 */
  --handle:     #DADBDD;              /* 시트 핸들바 — 분석2·6 수렴 */
  --btn-gray:   #F0F1F3;              /* 닫기 버튼·X 버튼 배경 */
  --outline:    #26282C;              /* 현재가 아웃라인(진남색-검정) — 분석3 */

  /* 무채색 액션 */
  --charcoal-btn:  #454A54;           /* 빈 상태 CTA — 분석5 */
  --charcoal-chip: #3A3E45;           /* 활성 필터 칩(인기·주요) — 분석6 (병기: 분석1 기간 칩 #4A5058) */

  /* 포인트 */
  --yellow:      #FFE300;             /* 북마크 카카오 옐로 — 분석1·4 (병기: 리본형 아이콘 #FFD338) */
  --ai-badge-bg: #EFEAFB;             /* AI분석 배지 연보라 */
  --ai-badge-tx: #3A66F5;
  --help-badge:  #C6CCD3;             /* ? 도움말 원형 배지 */
  --alert-dot:   #F03E3E;             /* 알림 빨간 점 (병기: #FF3B30) */
  --dim:         rgba(0,0,0,.45);     /* 바텀시트 딤 — 분석1·2 일치 */
}
```

### 1.2 타이포 스케일 (430px 기준, 시스템 폰트)

```css
body { font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo",
  "Malgun Gothic", "Segoe UI", Roboto, sans-serif; color: var(--ink-900); }
.num { font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
```

| 레벨 | px / weight | 용도 | 근거 |
|---|---|---|---|
| Display | 33 / 800 | 종목 상세 대형 현재가 | 분석1 |
| Amount | 31 / 800 | 실현손익 대형 금액(등락색) | 분석6 |
| H1 | 28 / 800 | 대형 화면 타이틀("한국 주식") | 분석4 |
| H2 | 24–25 / 800 | 종목명·섹션 대제목 | 분석1·5 교차 |
| H3 | 22 / 800 | 시트 제목·월 표시·시트 금액 값 | 분석2·6 교차 |
| H4 | 20 / 700 | 섹션 제목·페이지 타이틀·CTA 텍스트 | 분석1·6 교차 |
| Title | 19 / 700 | 리스트 종목명·탭 활성·AI 헤드라인 | 분석1·4·5·6 교차 |
| Body | 18 / 400–500 | 본문(line-height 1.5)·값 18/600–700 | 전 분석 수렴 |
| Sub | 17 / 400 | 상세 라벨·보조 텍스트 | 분석2·5 |
| Caption | 15–16 / 400 | 메타·기준시각·코드·SOR | 전 분석 수렴 |
| Micro | 13 / 400 | "실시간"/"15분 지연" 라벨(배지 아닌 순수 텍스트) | 분석5 |

공통 규칙: 제목 자간 -0.02em(-0.3px 내외), 제목 line-height 1.35–1.4, 본문 1.5, 숫자는 tabular-nums.

### 1.3 간격 스케일

- 기본 단위 4px: `4 / 6 / 8 / 10 / 12 / 16 / 20 / 24 / 32 / 40 / 60`
- 페이지 좌우 패딩: **20px** (분석5·6 수렴 — 병기: 종목 상세 계열은 28px 관찰, 데모는 20px 단일 기준 + 시트·카드 내부만 22–28px)
- 카드 내부 패딩 20–22px / 바텀시트 내부 좌우 28px (분석1·2 일치, 48px@720)
- 리스트 행 높이: 일반 66–72px, 호가 행 45px, KV·상세 행 36–58px
- 시트 대여백 리듬: 헤더 아래 ~60px, 버튼 위 54–66px (버튼은 시트 하단 고정, 콘텐츠 증감은 여백이 흡수 — 분석2)

### 1.4 라운드

| 계층 | 값 | 사용처 |
|---|---|---|
| 완전 pill | `999px` | CTA·확인 버튼·세그먼트 토글·플로팅 내비·총잔량 바 |
| 시트 상단 | `20px` | 바텀시트 좌·우 상단만 (분석1 19px·분석2 20px 수렴) |
| 카드 | `14–17px` | 흰 카드·다크 배너·트리맵 컨테이너(19px) |
| 박스 | `9–12px` | 경고 배너·현재가 아웃라인·세그먼트 활성 칩·필터 칩 |
| 배지 | `4–6px` | 소형 배지(구/판·K중·타일) |

**규칙: 버튼은 완전 pill 아니면 소형 라운드 — 중간값 없음** (분석1·2·3 교차 확인).

### 1.5 그림자 — 원칙적으로 없음(플랫)

허용 4곳만: ① 플로팅 하단 내비 `0 4px 16px rgba(0,0,0,.12)` ② FAB `0 6px 16px rgba(0,0,0,.25)` ③ 세그먼트 활성 칩 `0 1px 4px rgba(0,0,0,.08)` ④ 맨위로 버튼 `0 2px 8px rgba(0,0,0,.08)`. 카드·시트·CTA·배너는 전부 그림자 없이 색면 대비·딤으로 분리합니다.

### 1.6 구분선 4종

| 종류 | 스펙 | 사용처 |
|---|---|---|
| 헤어라인 | `1px solid var(--hairline)` | 탭바 하단·같은 섹션 내 행(뉴스·날짜 그룹) |
| 굵은 밴드 | `height:10px; background:var(--band)` (관찰 8–11px 병기) | 섹션 간 대구분, 음수 마진으로 전폭 확장 |
| 점선 | `2px dotted var(--dotted)` | **주문 확인 시트 전용** 시그니처 |
| 여백 | 구분선 없음 | 순위·관심·스크리너 등 대부분의 리스트 행 |

---

## 2. 컴포넌트별 재현 스펙

### 2.1 상단 네비 행

```css
.nav-row { height:54px; display:flex; align-items:center; justify-content:space-between;
  padding:0 20px; background:var(--bg); }
.nav-icon { width:24px; height:24px; stroke:var(--ink-900); stroke-width:2;
  stroke-linecap:round; fill:none; }
.nav-icons { display:flex; gap:20px; }
.bookmark  { fill:var(--yellow); stroke:none; }     /* 채움형 */
```
- 좌: 뒤로가기 ← / 우: 검색·북마크(노랑 채움)·더보기 ⋯ 최대 3개. 스크롤 컴팩트 상태에서는 북마크 제외 2개.

### 2.2 종목 헤더 (이름·가격·등락·SOR)

```css
.stock-name { font-size:24px; font-weight:700; display:flex; align-items:center; gap:6px; }
.stock-name .caret { width:0; height:0; border-top:6px solid var(--ink-900);
  border-left:5px solid transparent; border-right:5px solid transparent; }
.price-big  { font-size:33px; font-weight:800; letter-spacing:-0.5px; margin-top:10px; }
.change-row { margin-top:10px; font-size:18px; font-weight:700; color:var(--blue); } /* 상승 시 --red */
.sor-label  { font-size:16px; font-weight:400; color:var(--ink-500); margin-left:8px; }
.help-badge { width:18px; height:18px; border-radius:50%; background:var(--help-badge);
  color:#fff; font-size:12px; display:inline-grid; place-items:center; }
/* 스크롤 컴팩트 변형: 중앙 정렬 2줄 승격 */
.compact-header { position:sticky; top:0; background:var(--bg); text-align:center; padding:8px 0; }
.compact-header .name { font-size:18px; font-weight:700; }
.compact-header .price-line { font-size:17px; font-weight:700; }
.compact-header .price-line .chg { color:var(--blue); margin-left:6px; }
```
- 등락 행은 `▼ n.nn% (n,nnn원)` 전체가 동일 등락색 700. 스크롤 시 좌측 정렬 대형 블록 → 중앙 정렬 컴팩트 2줄로 전환(분석1 캡처29).

### 2.3 탭 스트립 (1차·2차)

```css
/* 1차: 텍스트 + 밑줄 */
.tabs { display:flex; gap:30px; padding:0 20px; border-bottom:1px solid var(--hairline); }
.tab  { padding:12px 0; font-size:19px; font-weight:500; color:var(--ink-500); position:relative; }
.tab.active { color:var(--ink-900); font-weight:700; box-shadow:inset 0 -3px 0 var(--ink-900); }
.tab .dot { position:absolute; top:8px; right:-8px; width:6px; height:6px;
  border-radius:50%; background:var(--alert-dot); }
/* 균등 N분할 변형(커뮤니티·주문내역): display:grid; grid-template-columns:repeat(3,1fr); text-align:center; */

/* 2차: pill 배경 */
.subtabs { display:flex; gap:8px; padding:10px 20px; }
.subtab  { padding:6px 12px; font-size:17px; font-weight:500; color:var(--ink-700); border-radius:8px; }
.subtab.active { background:var(--chip-gray); font-weight:700; color:var(--ink-900); }
```
- 활성 표기 2종 고정: 1차=검정 700+밑줄 2.5–3px, 2차=연회색 pill+700. 알림은 빨간 점 6px 우상단.

### 2.4 거래량·시가총액 행

```css
.stat-row { display:flex; align-items:center; gap:16px; padding:12px 20px; font-size:17px; }
.stat-row .label { color:var(--ink-700); font-weight:500; }
.stat-row .value { color:var(--ink-900); font-weight:700; margin-left:4px; }
.stat-fold { margin-left:auto; width:34px; height:29px; border-radius:6px;
  background:#E9EBEE; display:grid; place-items:center; color:var(--ink-700); }
```

### 2.5 차트 영역 (선·축·기간 칩)

```css
.chart { position:relative; height:270px; }
.chart-line { stroke:var(--blue); stroke-width:2.5; fill:none; }
.chart-dot  { r:4; fill:var(--blue); }
.chart-halo { r:17; fill:none; stroke:rgba(49,130,246,.35); stroke-width:1; }
.axis-col { position:absolute; right:0; top:0; bottom:0; width:72px;
  border-left:1px solid var(--hairline); font-size:16px; color:var(--ink-200); }
.chart-note { font-size:16px; font-weight:500; color:var(--ink-700); } /* "최고/최저 n원" + ↑↓, 극값 지점 추적 */
.period-chips { display:flex; align-items:center; gap:17px; padding:8px 20px; }
.period-chip { text-align:center; font-size:18px; font-weight:500; padding:7px 11px; }
.period-chip.active { background:var(--chip-gray); border-radius:9px; font-weight:700; }
.period-chip .pct { display:block; font-size:14px; font-weight:700; margin-top:2px; } /* ▼파랑/▲빨강 */
```

### 2.6 AI 요약 카드

```css
.ai-card { padding:20px; }                                /* 테두리·그림자 없음 — 플랫 리스트형 */
.ai-headline { font-size:19px; font-weight:700; display:flex; justify-content:space-between; }
.ai-headline .em { color:var(--blue); }                   /* "-n.nn% 급락" 스팬만 등락색 */
.ai-headline .chev { color:var(--ink-300); }
.ai-body { margin-top:8px; font-size:17px; color:var(--ink-700); line-height:1.55;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.ai-meta { margin-top:12px; display:flex; align-items:center; gap:8px; }
.ai-badge { background:var(--ai-badge-bg); color:var(--ai-badge-tx);
  border-radius:5px; padding:4px 8px; font-size:15px; font-weight:700; } /* ◆ AI분석 */
.ai-asof  { font-size:15px; color:var(--ink-500); }       /* "{날짜} 정규장 기준" */
```
- `[◆ AI분석] · 기준시각` 메타 행 패턴은 본 프로젝트의 출처·기준시각 배지 요구와 그대로 호환됩니다(분석1 관찰 7).

### 2.7 하단 CTA (판매·구매 좌우 병렬)

```css
.cta-bar { position:absolute; left:0; right:0; bottom:0; display:flex; gap:10px;
  padding:10px 20px 16px; background:var(--bg); }        /* 그림자 없음 — 필요 시 위쪽 흰색 페이드만 */
.cta { flex:1; height:54px; border:0; border-radius:999px;
  font-size:19px; font-weight:700; color:#fff; }
.cta.sell { background:var(--blue); }                     /* 판매 = 파랑, 항상 좌측 */
.cta.buy  { background:var(--red);  }                     /* 구매 = 빨강, 항상 우측 */
```
- 높이는 관찰값 47px(호가 화면)–60px(상세 화면) 사이 → 데모 **54px 단일 확정** (시트 버튼 58px과 근접 정합). 색-행동 매핑(파랑=판매/빨강=구매)은 절대 유지.

### 2.8 주문 확인 시트 (핸들바·총액 행·점선 행·아코디언·버튼 비율)

```css
.backdrop { position:absolute; inset:0; background:var(--dim); }
.sheet { position:absolute; left:0; right:0; bottom:0; background:var(--bg);
  border-radius:20px 20px 0 0; padding:0 28px 22px; }
.sheet-handle { width:48px; height:5px; border-radius:3px; background:var(--handle); margin:11px auto 0; }
.sheet-title { margin-top:31px; font-size:22px; font-weight:800; letter-spacing:-0.3px; }
.sheet-side  { margin-top:8px; font-size:22px; font-weight:800; color:var(--accent); }
/* 액센트 토큰 스왑이 전부: 구매 --accent:var(--red) / 판매·정정 --accent:var(--blue). 그 외 100% 동일 템플릿 */

.total-row { display:flex; justify-content:space-between; align-items:baseline; margin-top:60px; }
.total-row .label { font-size:19px; font-weight:700; }
.total-row .value { font-size:22px; font-weight:800; }

.dotted-hr { border:0; border-top:2px dotted var(--dotted); margin:16px 0 14px; }

.accordion-row { display:flex; justify-content:space-between; align-items:center;
  font-size:16px; color:var(--ink-500); padding:6px 0; }   /* "주문 자세히 보기" + ∧ 캐럿 */
.detail-row { display:flex; justify-content:space-between; align-items:center; height:36px; }
.detail-row .label { font-size:17px; font-weight:400; color:var(--ink-500); }
.detail-row .value { font-size:18px; font-weight:600; color:var(--ink-700); }

.opt-row { display:flex; justify-content:space-between; align-items:center; margin-top:16px;
  font-size:17px; color:#ACAEB1; }
.opt-row .check { width:22px; height:22px; border:1.5px solid #C4C6C9; border-radius:50%; }

.btn-row { display:flex; gap:10px; margin-top:54px; }      /* 옵션 행 없으면 66px — 버튼은 시트 하단 고정 */
.btn { height:58px; border-radius:999px; font-size:18px; font-weight:700; border:0; }
.btn-close   { flex:1;    background:var(--btn-gray); color:var(--ink-700); }
.btn-primary { flex:2.05; background:var(--accent);   color:#fff; }  /* 닫기:주버튼 = 1 : 2.05 확정 */

.tooltip { position:absolute; bottom:calc(100% + 8px); left:0; background:#17181A; color:#fff;
  font-size:14px; font-weight:700; padding:9px 12px; border-radius:8px; white-space:nowrap; }
.tooltip::after { content:""; position:absolute; top:100%; left:22px;
  border:6px solid transparent; border-top-color:#17181A; }
```

### 2.9 호가 세그먼트·토글

```css
/* 원탭 주문 그리드(행별 판매/구매 셀) */
.grid-row { display:grid; grid-template-columns:56px 34px 1fr 34px 56px; height:45px; align-items:stretch; }
.cell-sell { background:var(--blue-bg); color:var(--blue); font-size:14px; font-weight:600; display:grid; place-items:center; }
.cell-buy  { background:var(--red-bg);  color:var(--red);  font-size:14px; font-weight:600; display:grid; place-items:center; }
.hoga-price { font-size:18px; font-weight:700; color:var(--blue); letter-spacing:-0.02em; }
.hoga-pct   { font-size:11px; color:var(--ink-500); }      /* "▾x.xx%" — ▾도 회색 */
.hoga-qty   { font-size:14px; font-weight:600; }           /* 매도=파랑 / 매수=빨강 */
.depth-bar  { position:absolute; height:32px; border-radius:5px; background:var(--blue-depth); } /* 매수측 --red-depth */
.current-outline { border:1.5px solid var(--outline); border-radius:9px; background:#F4F5F7; } /* 색 채움 아닌 아웃라인 강조 */

/* 세그먼티드 컨트롤 — 헤더형(달력|기간)·인라인형(한국|미국)·전폭형(전체|한국|미국) 공통 문법 */
.seg { background:var(--seg-track); border-radius:11px; padding:4px; height:43px; display:flex; }
.seg-item { flex:1; display:grid; place-items:center; padding:0 14px; border-radius:8px;
  font-size:15px; font-weight:500; color:var(--ink-500); }
.seg-item.active { background:#fff; color:var(--ink-900); font-weight:700;
  box-shadow:0 1px 4px rgba(0,0,0,.08); }
/* pill 변형(뉴스 한국|미국): border-radius:999px + 활성에 border:1px solid #E4E6EA */

/* 총잔량 비교 바 / 스테퍼·빠른추가 */
.total-bar { height:31px; border-radius:999px; font-size:14px; font-weight:600; } /* 좌 연파랑/우 연분홍, 폭=잔량 비례 */
.stepper, .quick-add { background:#F4F5F7; border-radius:11px; height:43px;
  display:flex; align-items:center; padding:0 14px; gap:20px; font-weight:600; }
```

### 2.10 카드·리스트 행

```css
/* 카드: 회색 캔버스 위 흰 카드 — 그림자 없이 명도 대비로만 분리 */
.card { margin:14px; background:var(--bg); border-radius:16px; padding:20px; }

/* 리스트 행: 구분선 없음, 균일 높이 반복 */
.list-row { display:flex; align-items:center; height:72px; }
.rank-num   { width:30px; font-size:19px; font-weight:500; }   /* 배지·원 없음 — 순수 텍스트 */
.stock-logo { width:44px; height:44px; border-radius:50%; margin-right:14px; }
.row-name { font-size:19px; font-weight:700; letter-spacing:-0.3px; }
.row-code { font-size:15px; color:var(--ink-500); margin-top:2px; }
.row-right { margin-left:auto; text-align:right; }
.row-pct   { font-size:18px; font-weight:700; }   /* ▼파랑 / ▲빨강 — 색+부호 병행 */
.row-price { font-size:17px; color:var(--ink-500); margin-top:2px; }  /* 가격이 회색 보조, 등락률이 강조 */
.pct-down { color:var(--blue); } .pct-down::before { content:"▼"; font-size:11px; margin-right:2px; }
.pct-up   { color:var(--red);  } .pct-up::before   { content:"▲"; font-size:11px; margin-right:2px; }
```

### 2.11 배지·칩

```css
.badge      { height:21px; padding:0 8px; border-radius:6px; font-size:12px; font-weight:600;
  display:inline-grid; place-items:center; }
.badge.up   { background:#FDEAEE; color:var(--red); }      /* 상승 VI·고가 */
.badge.down { background:var(--blue-bg); color:var(--blue); }
.badge.gray { background:#EFF1F4; color:#6B7684; }         /* 시작가·거래량·K중·N중 */
.chip        { background:var(--chip-gray); border-radius:11px; height:38px; padding:0 14px;
  font-size:16px; color:var(--ink-700); display:inline-flex; align-items:center; gap:6px; }
.chip.charcoal { background:var(--charcoal-chip); color:#fff; font-weight:700; border-radius:12px; } /* 인기·주요 */
.chip.dark     { background:#4A5058; color:#fff; font-weight:700; }  /* 기간 필터 활성(1주 등) */
.mini-badge { font-size:12px; background:#EDEEF0; color:#6B6F76; border-radius:4px; padding:2px 4px; } /* 구/판 */
.alert-dot  { width:6px; height:6px; border-radius:50%; background:var(--alert-dot); }
.flag-badge { position:absolute; right:-3px; bottom:-3px; width:17px; height:17px;
  border-radius:50%; border:2px solid #fff; }              /* 로고 우하단 국기 오버레이 */
```
- 사각 칩은 최소 사용 — 상태 강조는 원칙적으로 **텍스트 색(파랑/빨강)+700 굵기**로만 하고, 배지는 초소형 정보(구/판·VI·지연 표기)에 한정합니다(분석5·6 교차).

### 2.12 달력 손익 표기

```css
.week-grid { display:grid; grid-template-columns:repeat(7,1fr); text-align:center; }
.dow { font-size:16px; color:var(--ink-500); font-weight:500; }
.day { font-size:20px; color:#3E4148; font-weight:500; }
.day.future   { color:#C8CBD1; }
.day.selected { width:41px; height:41px; margin:0 auto; border-radius:50%;
  background:#17181A; color:#fff; font-weight:700; display:grid; place-items:center; }
.day-pnl { font-size:14px; font-weight:500; color:var(--blue); margin-top:3px; } /* 손실=파랑 / 이익=빨강 */
.day-badges { display:flex; gap:4px; justify-content:center; margin-top:3px; }  /* .mini-badge "구" "판" */
.month-title { font-size:22px; font-weight:800; letter-spacing:-0.02em; }       /* "26년 7월 ▼" */
.pnl-amount { font-size:31px; font-weight:800; color:var(--blue); letter-spacing:-0.02em; }
.pnl-rate   { font-size:18px; font-weight:700; color:var(--blue); }             /* "(0.22%)" 형식 */
.kv-row { display:flex; justify-content:space-between; align-items:center; height:58px; font-size:18px; }
.kv-row .label { color:var(--ink-500); font-weight:400; }
.kv-row .value { color:var(--ink-900); font-weight:700; }
```

---

## 3. 전역 패턴 규칙

1. **배경 이원화**: 종목 상세·피드·주문·달력 등 과업형 화면 = 순백 `--bg` + 헤어라인/밴드/여백 분리. 발견·증권홈 등 대시보드형 화면 = 회색 캔버스 `--canvas-gray` + 라운드 16px 흰 카드(그림자 없음, 명도 대비만). 한 화면에서 두 문법을 섞지 않습니다.
2. **텍스트 위계 3단계(+힌트 1단)**: `--ink-900`/700–800 → `--ink-700`/400–600 → `--ink-500`/400–500 (+`--ink-300` 힌트). 굵기 차이와 색 차이를 항상 병행하며, 색만으로 위계를 만들지 않습니다.
3. **좌라벨(회색)-우값(검정 볼드) 리듬**: 모든 KV 행(총 주문 금액·주문 방법·총 구매금액 등)은 좌측 `--ink-500` 400 라벨 / 우측 `--ink-900` 600–700 값, `justify-content:space-between`, 행 높이 36–58px 등간격. 단 대시보드 리스트에서는 역전 — 등락률이 강조색 700, 가격이 회색 400 보조.
4. **점선 vs 실선**: 둥근 점 점선(`2px dotted #E0E1E3`)은 **주문 확인 시트 내부 구분 전용** 시그니처. 그 외 같은 섹션 내 구분은 1px 헤어라인, 섹션 간 대구분은 10px 회색 밴드(전폭), 리스트 행은 여백만. 이 4종 외 구분 장치(카드 테두리·그라데이션)는 쓰지 않습니다.
5. **색 문법 엄수**: 파랑 `#3182F6` = 하락·판매·매도호가·손실·링크·건수 / 빨강 `#F04452` = 상승·구매·매수호가·이익·경고 점. 텍스트→연면(`--blue-bg`/`--red-bg`)→깊이 막대(`--blue-depth`/`--red-depth`) 3단 강도로만 변주하며, 등락 표기에는 항상 ▲▼ 부호를 병행합니다(접근성 — 헌법 §14 색+부호 병행과 일치). 비활성 버튼은 동일 색상의 저채도 밝은 톤 채움 + 흰 텍스트.
6. **아이콘 표현**: 24px 뷰박스 인라인 SVG 권장 — `stroke:currentColor; stroke-width:2; stroke-linecap:round; fill:none` 라인 아이콘 기본, 북마크·활성 내비 아이콘만 채움형. 등락 삼각형은 SVG 대신 CSS border 삼각형 또는 ▲▼▾ 글리프(11px, 본문 대비 축소) 사용. chevron은 `--ink-200`~`#C4C9CF`, 도움말 ?는 `--help-badge` 원형 18px + 흰 글자. 외부 아이콘 폰트·이미지 CDN은 사용 금지(오프라인 제약).
7. **버튼 문법**: 실행 CTA = 완전 pill + 진한 채움 + 흰 700 / 보조(닫기·확인) = 회색 채움 또는 흰 배경+1.5px 테두리 pill / 무채색 CTA(빈 상태) = 차콜 `#454A54` 라운드 10px. 판매·구매 병렬은 1:1, 닫기·주버튼은 1:2.05 고정.

---

## 4. 주의

본 스펙은 UI 형식(레이아웃·색·타이포·간격)만 기록했으며, 원본 캡처에 포함된 개인 데이터(계좌번호·잔고·보유 종목·손익 수치·닉네임 등)는 6개 분석 및 본 문서 어디에도 포함하지 않았음을 확인합니다. 캡처 속 가격·퍼센트·종목명은 형식 예시로만 언급되었고, 데모 구현 시에는 헌법 §7에 따라 가상 종목·가상 수치만 사용해야 합니다. 모든 hex·px 값은 육안 관찰 기반 추정 확정값이며 `[데모 고정]` 성격으로, 실서비스 전 재검토 대상입니다.
