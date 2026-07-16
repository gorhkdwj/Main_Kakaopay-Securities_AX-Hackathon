# WS1. 카카오페이증권 전수 조사 (Claude)

- 작성일: 2026-07-16
- 열람 시각: 2026-07-16 03:50~04:20 KST (모든 페이지 공통, 개별 시각은 출처대장 참조)
- 조사 방법: WebFetch(서버 렌더링 페이지), Chrome DevTools MCP(채용공고·IR 등 JS 렌더링 페이지), curl(회사소식 24페이지 전량 수집)
- 출처대장: `ws1_sources.csv` (C-SRC-0100~), 주장대장: `ws1_claims.csv` (C-CLM-0100~)
- 특이사항: `dynamicPage.do` 계열은 예상과 달리 서버 렌더링으로 WebFetch 접근이 가능했습니다. 카카오페이 IR 목록·채용공고 목록만 JS 렌더링이 필요했습니다. 회사소식 목록의 페이지 이동은 `?searchOption=0&searchText=&pageNumber=N` GET 파라미터로 접근 가능함을 확인했습니다.

## 1. 페이지 인벤토리 (전수)

### 1.1 kakaopaysec.com 본체

| 메뉴 | 페이지 | URL | 상태 | 비고(초보 투자자 관점) |
|---|---|---|---|---|
| 홈 | 메인 | https://www.kakaopaysec.com/ | 확인 | "자산 규모가 적거나 경험이 부족한 사용자" 명시 타깃 [C-SRC-0100] |
| 회사소개 | 회사개요 | /company/about/dynamicPage.do | 확인 | 대표 신호철, 판교 본사·여의도 영업부 [C-SRC-0101] |
| 회사소개 | 회사소식 | /company/news_page/dynamicPage.do | 확인 | 총 24페이지·118건 제목 전수 수집, 핵심 10건 본문 정독 [C-SRC-0104~0115] |
| 비즈니스 | 개인금융 서비스 | /business/retail/dynamicPage.do | 확인 | "카카오 플랫폼을 통해서만 투자서비스 제공", 낮은 진입장벽 강조 [C-SRC-0102] |
| 비즈니스 | 기업금융 서비스 | /business/ib/dynamicPage.do | 확인 | PF·채권·유동화 등. 초보 투자자 주제와는 무관에 가까움 [C-SRC-0103] |
| 경영정보 | 정기보고서 | /management/routine/dynamicPage.do | 확인 | 최신 FY2026 1/4분기 영업보고서(2026.05.15 등록) [C-SRC-0116] |
| 경영정보 | 공시정보 | /management/disclosure/dynamicPage.do | 확인 | 지배구조 공시 위주. 2026.02.13 "손익구조 30%이상 변경" 공시 [C-SRC-0117] |
| 리서치 | 투자전략/퀀트 | /research/quint/dynamicPage.do | 확인 | 2024.10 이후 발간 중단 상태(미국 ETF 주간 리뷰가 마지막) [C-SRC-0118] |
| 리서치 | 산업/기업분석 | /research/industry/dynamicPage.do | 확인 | 2024.04 이후 중단(구글 트렌드 미국주식 시리즈) [C-SRC-0119] |
| 리서치 | 제외종목 | /research/exclusion/dynamicPage.do | 확인 | 커버리지 제외 공지(2018~2022), 현재 주제와 무관 [C-SRC-0120] |
| 고객센터 | 공지사항 | /customer/notice/dynamicPage.do | 확인 | 2026.6~7월 서킷브레이커 3회·앱 접속 지연 장애 공지 [C-SRC-0121] |
| 고객센터 | 주식공지 | /customer/stocknotice/dynamicPage.do | 확인 | 보증금률 변경·거래정지·서비스 지연 공지 [C-SRC-0122] |
| 고객센터 | 상품공지 | /customer/product/dynamicPage.do | 확인 | 판매 펀드 공지(2025.10 최신) [C-SRC-0123] |
| 고객센터 | 약관/서식 | /customer/terms/dynamicPage.do | 확인 | RIA 약관·상품설명서(2026.03.20), 주식 대여중개 약관 [C-SRC-0124] |
| 고객센터 | 소비자보호포털 | /customer/portal/dynamicPage.do | 확인 | 소비자보호 5원칙, 민원접수 채널 [C-SRC-0125] |
| 고객센터 | 고객유의사항 | /customer/caution/dynamicPage.do | 확인 | 보호금융상품등록부 분기 게시 [C-SRC-0126] |
| 고객센터 | FAQ | /customer/faq/dynamicPage.do | 확인 | 계좌/입출금/주식/펀드/기타 5분류, D+2 출금·KRX vs ATS 등 [C-SRC-0127] |
| 이용안내 | 계좌개설안내 | /guide/account/dynamicPage.do | 확인 | 카카오톡 내 비대면 개설 절차 [C-SRC-0128] |
| 이용안내 | 예탁금이용안내 | /guide/bankGuide/dynamicPage.do | 확인 | 30만원 이하 연 2.50% 등 소액 우대 구조 [C-SRC-0129] |
| 이용안내 | 수수료안내 | /guide/feeGuide/dynamicPage.do | 확인 | 국내 온라인 0.015%(KRX)/0.014%(NXT), 해외 0.1%, 환전 스프레드 1% [C-SRC-0130] |
| 이용안내 | 해외주식 시세 유의사항 | /guide/quotation/dynamicPage.do | 확인 | Nasdaq Basic 실시간, 조건부 15분 지연 전환 [C-SRC-0131] |
| 이용안내 | 이해상충·정보교류차단 | /guide/exchange/dynamicPage.do | 확인 | 정보교류차단 체계. 주제 관련성 낮음 [C-SRC-0132] |
| 이용안내 | 신용공여·매매 안내 | /guide/creditntrading/dynamicPage.do | 확인 | 신용이자 최대 연 9.5%, 담보유지 140%, 반대매매 절차 [C-SRC-0133] |
| 이용안내 | 위탁증거금 안내 | /guide/marginnotice/dynamicPage.do | 확인 | 증거금률 A~E등급 20~100%, 해외 100% [C-SRC-0134] |
| 이용안내 | 최선집행기준 | /guide/bestExecutionStandard/dynamicPage.do | 확인 | KRX·NXT SOR 배분 기준(총금액→잔량→KRX) [C-SRC-0135] |
| 이용안내 | 주식판매금 미리받기 | /guide/beforehand/dynamicPage.do | 확인 | 매도대금 담보 융자, 일 0.025%(연 9%) [C-SRC-0136] |
| 이용안내 | 개인채무자보호 안내 | /guide/personal-protection/dynamicPage.do | 확인 | 채무조정 프로그램. 주제 관련성 낮음 [C-SRC-0137] |
| 이용안내 | 상속업무안내 | /guide/inherit/dynamicPage.do | 확인 | 상속 절차. 무관 [C-SRC-0138] |
| 이용안내 | 기타업무안내 | /guide/etcGuide/dynamicPage.do | 확인 | 이체한도, 송금 수수료 무료 [C-SRC-0139] |
| 정책/고지 | 개인정보 처리의 위탁(상세) | /policy-detail/policy-002/dynamicPage.do | 확인 | 커먼컴퓨터에 "AI 상담 어드바이저 구축" 위탁 명시 [C-SRC-0140] |
| 푸터 | 주문 장애시 대처방법/보상기준 | /portal/cstmnotice-obstc/dynamicPage.do | 확인 | 비상주문 미시도 시 보상 제외 가능 [C-SRC-0141] |
| 푸터 | 보호금융상품등록부 | /caution/protection/dynamicBoardPageDetail.do?id=7143 | 무관 | 예금자보호 목록(제목만 확인) |
| 푸터 | 개인정보처리방침 | /caution/privacyCaution/dynamicBoardPageDetail.do?id=7256 | 무관 | 정책 문서(제목만 확인) |
| 푸터 | 고객권리안내문 | /caution/privacyCaution/dynamicBoardPageDetail.do?id=4209 | 무관 | 정책 문서(제목만 확인) |
| 푸터 | 신용정보 활용체제 | /caution/privacyCaution/dynamicBoardPageDetail.do?id=7255 | 무관 | 정책 문서(제목만 확인) |

### 1.2 채용 사이트 (career.kakaopaysec.com)

| 페이지 | URL | 상태 | 비고 |
|---|---|---|---|
| 채용 홈(Company) | https://career.kakaopaysec.com/ | 확인 | JS 렌더링. Chrome DevTools로 확인 [C-SRC-0142] |
| 채용공고(Jobs) | https://career.kakaopaysec.com/job_posting | 확인 | 3페이지·총 52건 전수 수집 [C-SRC-0143] |
| Company 소개 | https://career.kakaopaysec.com/introduction | 확인 | "일상과 투자를 연결" 미션 [C-SRC-0144] |
| Story | https://brunch.co.kr/@kakaopaysec | 무관 | 채용 브런치(외부). 목록만 확인, 정독 생략 |
| Culture & Benefit | https://career.kakaopaysec.com/culture | 무관 | 복지 안내(주제 무관, 미정독) |
| 채용 FAQ | https://career.kakaopaysec.com/faq | 무관 | 채용 절차 FAQ(주제 무관, 미정독) |
| 채용 공지사항 | https://career.kakaopaysec.com/notice | 무관 | 채용 공지(주제 무관, 미정독) |

### 1.3 카카오페이 IR·기술 블로그

| 페이지 | URL | 상태 | 비고 |
|---|---|---|---|
| 카카오페이 IR 루트 | https://www.kakaopay.com/ir | 접근불가 | HTTP 404. 계획서 URL은 무효, 하위 경로만 유효 [C-SRC-0145] |
| 카카오페이 실적발표 | https://www.kakaopay.com/ir/ir_archive/earnings_release | 확인(부분) | JS 렌더링. 브라우저로 "2026년 1분기 실적발표: 실적보고서 PT·Fact Sheet(PDF/EXCEL)·컨퍼런스콜" 존재 확인. PDF 딥링크는 타 에이전트와의 브라우저 경합으로 추출 실패 [C-SRC-0146] |
| 1Q26 실적 보도(보완) | https://v.daum.net/v/20260506170307831 | 확인 | 증권 부문 매출 1,001억·영업이익 236억 등 [C-SRC-0147] |
| 기술 블로그 AI 태그 | https://tech.kakaopay.com/tag/ai/ | 확인 | 15건. 증권 관련은 내부용(핑크와드·춘시리) 2건 [C-SRC-0148] |
| 기술 블로그 카카오페이증권 태그 | https://tech.kakaopay.com/tag/카카오페이증권/ | 확인 | 11건, 전부 인프라·내부 도구 주제 [C-SRC-0149] |
| 금융 용어 AI '금.용.사.' | https://tech.kakaopay.com/post/kakaopay-hackathon-ai-finance-glossary/ | 확인 | 사내 해커톤: 금융 용어 3단계 설명 AI(Simple/Detail/Products) [C-SRC-0150] |

### 1.4 회사소식 118건 제목 전수 목록

원자료: 본 폴더의 `ws1_회사소식_제목전수.txt` (24페이지 curl 수집분에서 추출한 게시물 id·날짜·제목 118건). 핵심 항목은 아래 2장과 출처대장에 반영했으며, 원본은 `dynamicPage.do?searchOption=0&searchText=&pageNumber=N`(N=1~24)으로 재현 가능합니다.

## 2. 핵심 발견 (초보 투자자 매수·매도 지원 관점)

### 2.1 회사 전략: "AI 네이티브 전환"이 공식 경영 의제
- 2026-03-31 신호철 대표 연임. 2기 경영 핵심 = "AI 네이티브 전환 + 사용자 경험 혁신", 3대 과제 = AI 기반 투자 정보 / 커뮤니티 활성화 / 프로모드(고급 주문·자산관리) [C-SRC-0111, F]
- 2025-04-15 대표 발표: 모든 투자 정보를 **"어땠지(시장 요약)·왜지(급등락 이유 1~2줄 요약)·어쩌지(차트 기술 분석 기반 의사결정 지원)"** 3단계로 제공. 내부 AI 모델 운영 중이며 **금융위 혁신금융서비스(샌드박스) 신청 완료**. "손안의 블룸버그" 지향 [C-SRC-0112, F]
- 2026-07-08 **AI 어닝콜 실시간 번역·요약** 정식 출시: PIP로 시청하며 시세 확인·매매 동시 수행, AI 구간 요약마다 어닝콜 시작 대비 주가 등락률 표시. 미국 시총 상위 500종목 → 7월 후반 1,000종목 확대 예정 [C-SRC-0106, F]
- 채용공고 52건 중 **AI Native Engineering팀 AI Agent 기획자·AI 엔지니어, AI Agent 기획자(일반·시니어)** 등 AI Agent 직군 4건 이상 모집 중 → AI 에이전트 조직 실재 [C-SRC-0143, F]
- 개인정보 위탁 현황에 **커먼컴퓨터 "AI 상담 어드바이저 구축"** 명시 → 고객 상담 영역 AI 도입 진행 근거 [C-SRC-0140, F]
- 커뮤니티 게시글 검수를 AI 모니터링으로 전면 자동화 [C-SRC-0115, F]
- 해석(I): 공개된 고객향 AI는 모두 "정보 요약·구조화형"이며 종목 추천·결론 제시형이 아님. "AI가 결론을 대신하지 않고 사용자가 선택하게 돕는다"는 본 리서치 초기 가설과 회사 방향이 정합합니다.

### 2.2 초보 투자자 대상 기능 자산 (매수·매도 여정별)
- 진입: 카카오톡 내 계좌개설, 1,000원 펀드, 해외주식 소수점 거래, 주식 선물하기, 예탁금 30만원 이하 연 2.5% [C-SRC-0100, 0128, 0129]
- 매수: 주식 모으기(2년간 160만 명, "매일 모으기"가 절반 이상), 차트주문(2026-01), 트레이딩뷰 차트(2025-04, "초보 투자자부터 전문가까지" 명시) [C-SRC-0105티틀, 0143 목록 내 뉴스 98·105·70]
- 보유/매도: **스탑로스 주문(2024-09, "금융 서비스 경험이 부족한 사용자들도 손쉽게" 명시)**, 시세감지주문, 수익률 모으기·팔기(2025-10), 주식판매금 미리받기(연 9% 융자) [C-SRC-0114, 0136]
- 커뮤니티: 종목별 토론방(2022-12)→커뮤니티 MAU 130만(1년 만에 5배), 주주 인증 기반 참여, 핀플루언서 확산 [C-SRC-0115, F]
- 절세·재진입: RIA(국내시장 복귀계좌) 45일 만에 5만 계좌(업계 전체의 약 1/4), ISA 두 달 10만 계좌, 연금저축 50만 계좌 [C-SRC-0110, 0104]

### 2.3 규모 지표 (공개 수치)
- 예탁자산 20조 원(2026-05-29, 15조→20조에 29영업일), 종합계좌 700만 개(2025-01), 월간 거래자 100만 명(2025-07), 카톡 채널 친구 100만(증권사 1위) [C-SRC-0109, 0104, 0108]
- 카카오페이 1Q26 연결: 매출 3,003억·영업이익 322억·거래액(TPV) 50.9조. 증권 부문(보도 기준): 분기 매출 1,001억(역대 최대)·영업이익 236억, 예탁자산 전년 대비 +208%, 국내주식 거래액이 해외주식 상회 [C-SRC-0147, F(보도)]
- 카카오페이증권 자체 공시 기준 최신 정기보고서: FY2026 1/4분기 영업보고서(2026-05-15) [C-SRC-0116]
- 2024 투자 리포트: 미국장 투자자 72% 수익 vs 한국장 48%, 20대가 전 연령 최저 수익(한국장 -1.4%) [C-SRC-0113, F] → 젊은 초보층의 성과 부진을 회사 스스로 공개

### 2.4 고객 불편·고불안 순간 관련 신호
- 공지사항 최근 10건 중 다수가 시장 급변동·장애: 코스피 서킷브레이커 1단계 발동 안내 3회(2026-06-26, 07-07, 07-13), 앱 접속·서비스 지연(2026-06-30, 익일 정상화), 선물받기·예약매매 지연(07-10) [C-SRC-0121, F]
- 주문장애 보상: 화면 캡처 등 증거 확보 + 비상주문(ARS·고객센터) 시도가 사실상 전제, "비상주문을 시도하지 않으면 보상 대상에서 제외될 수 있음" [C-SRC-0141, F] → 해석(I): 초보자가 패닉 상황에서 수행하기 어려운 절차
- FAQ 초보자 혼동 포인트: 매도 후 출금 D+2, KRX vs ATS(NXT) 구분, 배당 기준일 2영업일 전 보유, 펀드별 출금 가능일 상이 [C-SRC-0127, F]
- 반대매매: 미수 발생 후 3~4거래일, 담보부족 후 2거래일 내 임의 처분 [C-SRC-0133, F]
- 해외주식 시세: 실시간(Nasdaq Basic)이나 조건 발생 시 예고 없이 15분 지연 전환 가능 [C-SRC-0131, F] → 기준시각 표기의 중요성 근거

### 2.5 수수료 체계 (2026-07-16 확인 기준)
- 국내주식 온라인 0.015%(KRX)/0.014%(NXT), 오프라인 0.5%/0.49%, 최소 1원
- 해외주식 온라인 0.1%(최소 $0.01), SEC Fee 0.00206%·TAF 등 별도
- 환전: 매매기준율 × 스프레드 1%
- 거래세: 코스피·코스닥 매도 0.20%
- 신용융자 연 4.5~9.5%, 주식판매금 미리받기 연 9% [C-SRC-0130, 0133, 0136, F]

### 2.6 접근 실패·한계 기록
- https://www.kakaopay.com/ir : HTTP 404 (계획서 기재 URL 무효. 유효 경로는 /ir/ir_archive/earnings_release 등 하위 경로) [C-SRC-0145]
- 카카오페이 실적발표 자료의 PDF 딥링크: JS 동적 로딩 + 타 워크스트림 에이전트와 Chrome DevTools 브라우저(페이지 선택 상태)를 공유하는 경합으로 링크 추출을 완료하지 못했습니다. 페이지에 2026년 1분기 실적보고서 PT·Fact Sheet(PDF/EXCEL)이 게시되어 있음은 브라우저 렌더링으로 관찰(2026-07-16 04:05 KST경) [C-SRC-0146]. 증권 부문 세부 수치는 보도자료(C-SRC-0147)로 보완했으며, WS8 QA 시 PDF 원문 재확인을 권장합니다.
- 카카오페이증권 회사소식 상세 중 id=117(2026.05.19 연금저축 50만 계좌)은 목록 제목으로만 확인(본문 미정독)했으며, 제목 수집 과정에서 id 결번(65, 66 이전 구간 등)이 있으나 이는 게시판 원본의 결번으로 추정됩니다.
- 리서치 게시판(투자전략/퀀트, 산업/기업분석)은 2024년 이후 갱신이 없음을 확인했습니다(발간 중단 여부는 회사 공식 언급 없음 → 해석에 그침).
