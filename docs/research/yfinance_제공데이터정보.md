
## 1. 가격 데이터 (OHLCV)

`history()` 또는 `yf.download()`로 수집하며, 포트폴리오·백테스트·EDA의 기본 입력입니다.

### 1-1. 반환 컬럼

| **컬럼** | **설명** | **비고**                         |
| -------------- | -------------- | -------------------------------------- |
| Open           | 시가           |                                        |
| High           | 고가           |                                        |
| Low            | 저가           |                                        |
| Close          | 종가           | $auto\_adjust=True$ 시 조정종가 기반 |
| Volume         | 거래량         |                                        |
| Dividends      | 배당금         | 해당 날짜에 지급된 경우만 값 존재      |
| Stock Splits   | 주식 분할      | 해당 날짜에 발생한 경우만 값 존재      |

### 1-2. 주요 파라미터

| **파라미터**  | **값 범위**                                                                                                         | **설명**                               |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| $period$          | $1d$ , $5d$ , $1mo$ , $3mo$ , $6mo$ , $1y$ , $2y$ , $5y$ , $10y$ , $ytd$ , $max$                    | 조회 기간 (start/end와 택일)                 |
| $interval$        | $1m$ , $2m$ , $5m$ , $15m$ , $30m$ , $60m$ , $90m$ , $1h$ , $1d$ , $5d$ , $1wk$ , $1mo$ , $3mo$ | 데이터 간격                                  |
| $start$ / $end$ | YYYY-MM-DD                                                                                                                | 조회 시작/종료 날짜                          |
| $auto\_adjust$    | $True$ / $False$                                                                                                      | 배당·분할 반영 조정가격 여부                |
| $group\_by$       | $column$ / $ticker$                                                                                                   | $download()$ 전용 — 다중 티커 그룹핑 기준 |

<aside>
⚠️

**인트라데이 데이터 제한:** $1m$ 간격 → 최근 7일, $interval < 1d$ → 최근 60일만 조회 가능합니다.

</aside>

### 1-3. 코드 예시 — 다중 티커 수집

```python
import yfinance as yf
import pandas as pd

tickers = ["SPY", "QQQ", "TLT", "GLD", "BTC-USD"]
raw = yf.download(
    tickers,
    start="2021-01-01",
    end="2025-12-31",
    auto_adjust=True,
    group_by="ticker",
)

close = {t: raw[t]["Close"].dropna() for t in tickers}
df_prices = pd.DataFrame(close).sort_index()
print(df_prices.shape, df_prices.isna().sum())

# tickers: 수집 대상 티커 리스트 (list[str])
# start/end: 조회 기간 (YYYY-MM-DD)
# auto_adjust: True → 배당·분할 반영 조정가격
# group_by: "ticker" → (티커 → OHLCV) 구조
# 반환값: pandas.DataFrame (MultiIndex columns)
```

### 1-4. 코드 예시 — 단일 티커 history()

```python
import yfinance as yf

t = yf.Ticker("AAPL")
hist = t.history(period="1y", interval="1d", auto_adjust=True)
print(hist.head())

# period: 조회 기간 (str) — "1d"~"max"
# interval: 데이터 간격 (str) — "1m"~"3mo"
# auto_adjust: 조정가격 여부 (bool)
# 반환값: pandas.DataFrame (OHLCV + Dividends + Stock Splits)
```

<aside>
💡

**history_metadata:** `t.history_metadata`로 마지막 `history()` 호출의 메타데이터(통화, 거래소, 타임존, 거래 기간 등)를 확인할 수 있습니다. 루프에서 동일 객체로 반복 호출 시 유용합니다.

</aside>

---

## 2. 메타/일반 정보 (`Ticker.info`)

`dict` 형태로 반환되며, 종목 유형에 따라 포함 키가 달라집니다. 주식(equities)에서 가장 풍부합니다.

### 2-1. 식별 정보

| **키**            | **타입** | **설명**                             |
| ----------------------- | -------------- | ------------------------------------------ |
| $shortName$           | str            | 짧은 종목명                                |
| $longName$            | str            | 정식 종목명                                |
| $symbol$              | str            | 티커 심볼                                  |
| $exchange$            | str            | 거래소 코드                                |
| $currency$            | str            | 거래 통화                                  |
| $quoteType$           | str            | 자산 유형 (EQUITY, ETF, CRYPTOCURRENCY 등) |
| $sector$              | str            | 섹터                                       |
| $industry$            | str            | 산업군                                     |
| $country$ / $city$  | str            | 본사 소재지                                |
| $website$             | str            | 회사 웹사이트                              |
| $longBusinessSummary$ | str            | 사업 개요 설명                             |
| $fullTimeEmployees$   | int            | 정규직 수                                  |

### 2-2. 시장 가격

| **키**                                   | **설명**      |
| ---------------------------------------------- | ------------------- |
| $currentPrice$                               | 현재가              |
| $previousClose$                              | 전일 종가           |
| $open$                                       | 당일 시가           |
| $dayHigh$ / $dayLow$                       | 당일 고/저가        |
| $fiftyTwoWeekHigh$ / $fiftyTwoWeekLow$     | 52주 고/저가        |
| $fiftyDayAverage$ / $twoHundredDayAverage$ | 50일/200일 이동평균 |
| $bid$ / $ask$                              | 매수/매도 호가      |
| $bidSize$ / $askSize$                      | 매수/매도 호가 수량 |

### 2-3. 거래량

| **키**                | **설명**           |
| --------------------------- | ------------------------ |
| $volume$                  | 현재 거래량              |
| $averageVolume$           | 평균 거래량 (최근 3개월) |
| $averageVolume10days$     | 최근 10일 평균 거래량    |
| $averageDailyVolume10Day$ | 10일 일평균 거래량       |

### 2-4. 밸류에이션 지표

| **키**                     | **설명** |
| -------------------------------- | -------------- |
| $marketCap$                    | 시가총액       |
| $enterpriseValue$              | 기업가치 (EV)  |
| $forwardPE$ / $trailingPE$   | 선행/후행 PER  |
| $priceToBook$                  | PBR            |
| $priceToSalesTrailing12Months$ | PSR (TTM)      |
| $enterpriseToRevenue$          | EV/매출        |
| $enterpriseToEbitda$           | EV/EBITDA      |
| $pegRatio$                     | PEG 비율       |
| $trailingPegRatio$             | 후행 PEG 비율  |

### 2-5. 배당 정보

| **키**                                 | **설명**      |
| -------------------------------------------- | ------------------- |
| $dividendRate$                             | 연간 배당금(절대값) |
| $dividendYield$                            | 배당수익률          |
| $exDividendDate$                           | 배당락일            |
| $payoutRatio$                              | 배당성향            |
| $fiveYearAvgDividendYield$                 | 5년 평균 배당수익률 |
| $lastDividendValue$ / $lastDividendDate$ | 최근 배당금/배당일  |

### 2-6. 수익성·성장 지표

| **키**         | **설명** |
| -------------------- | -------------- |
| $profitMargins$    | 순이익률       |
| $operatingMargins$ | 영업이익률     |
| $grossMargins$     | 매출총이익률   |
| $ebitdaMargins$    | EBITDA 마진    |
| $returnOnEquity$   | ROE            |
| $returnOnAssets$   | ROA            |
| $earningsGrowth$   | 이익 성장률    |
| $revenueGrowth$    | 매출 성장률    |

### 2-7. 재무 요약

| **키**                     | **설명**   |
| -------------------------------- | ---------------- |
| $totalRevenue$                 | 총매출           |
| $revenuePerShare$              | 주당 매출        |
| $totalDebt$                    | 총부채           |
| $totalCash$                    | 총현금           |
| $totalCashPerShare$            | 주당 현금        |
| $debtToEquity$                 | 부채비율         |
| $currentRatio$                 | 유동비율         |
| $quickRatio$                   | 당좌비율         |
| $freeCashflow$                 | 잉여현금흐름     |
| $operatingCashflow$            | 영업현금흐름     |
| $bookValue$                    | 주당 장부가치    |
| $earningsQuarterlyGrowth$      | 분기 이익 성장률 |
| $trailingEps$ / $forwardEps$ | 후행/선행 EPS    |

<aside>
⚠️

**주의:** `info`는 `dict`이므로 키 부재 시 `KeyError` 발생. 항상 `.get()` 또는 `in` 검사로 방어 코드를 작성해야 합니다. 특히 암호화폐·외환은 대부분의 재무 키가 $None$ 또는 누락입니다.

</aside>

---

## 3. 재무제표 (Financial Statements)

`pandas.DataFrame` 형태로 반환되며, 연간 및 분기별 버전이 존재합니다.

| **속성**     | **내용**                         | **분기 버전**           |
| ------------------ | -------------------------------------- | ----------------------------- |
| $income\_stmt$   | 손익계산서 (매출, 영업이익, 순이익 등) | $quarterly\_income\_stmt$   |
| $balance\_sheet$ | 대차대조표 (자산, 부채, 자본)          | $quarterly\_balance\_sheet$ |
| $cashflow$       | 현금흐름표 (영업·투자·재무 활동)     | $quarterly\_cashflow$       |
| $financials$     | $income\_stmt$ 의 별칭               | $quarterly\_financials$     |

```python
import yfinance as yf

t = yf.Ticker("AAPL")

# 연간 손익계산서
print(t.income_stmt)

# 분기 대차대조표
print(t.quarterly_balance_sheet)

# 분기 현금흐름표
print(t.quarterly_cashflow)

# 반환값: pandas.DataFrame (행=항목, 열=연도/분기)
# 주식(equities) 전용 — ETF/암호화폐/외환은 미지원
```

<aside>
💡

**구버전 호환:** `get_income_stmt()`, `get_balance_sheet()`, `get_cashflow()` 메서드로도 동일 데이터를 가져올 수 있으며, `proxy` 파라미터를 추가 지원합니다.

</aside>

---

## 4. 배당·분할·기업 행동 (Corporate Actions)

| **속성**     | **반환 타입**  | **설명**                     |
| ------------------ | -------------------- | ---------------------------------- |
| $dividends$      | $pandas.Series$    | 배당 지급 이력 (날짜별 금액)       |
| $splits$         | $pandas.Series$    | 주식 분할 이력 (날짜별 비율)       |
| $actions$        | $pandas.DataFrame$ | 배당 + 분할 통합 테이블            |
| $capital\_gains$ | $pandas.Series$    | 자본이득 분배 이력 (펀드/ETF 전용) |

```python
import yfinance as yf

t = yf.Ticker("AAPL")
print(t.dividends.tail())
print(t.splits.tail())
print(t.actions.tail())

# dividends: 배당 이력 — index=Date, values=배당금(float)
# splits: 분할 이력 — index=Date, values=분할비율(float)
# actions: 배당+분할 통합 — columns=[Dividends, Stock Splits]
```

---

## 5. 옵션 데이터 (Options)

주식·ETF에서 사용 가능하며, 만기일별 콜/풋 체인을 반환합니다.

### 5-1. 만기일 목록

```python
import yfinance as yf

t = yf.Ticker("AAPL")
print(t.options)

# 반환값: tuple — 사용 가능한 만기일 목록 (str, "YYYY-MM-DD")
```

### 5-2. 옵션 체인

```python
opt = t.option_chain(t.options[0])

calls = opt.calls
puts = opt.puts
print(calls.head())

# option_chain(date): 특정 만기일의 옵션 체인 반환
# .calls / .puts: pandas.DataFrame
# 컬럼: contractSymbol, lastTradeDate, strike, lastPrice,
#        bid, ask, change, percentChange, volume,
#        openInterest, impliedVolatility, inTheMoney
```

<aside>
💡

**활용:** 내재변동성( $impliedVolatility$ )으로 시장의 기대 변동성을 측정하거나, 행사가격( $strike$ )별 미결제약정( $openInterest$ ) 분포로 지지/저항 수준을 분석할 수 있습니다.

</aside>

---

## 6. 애널리스트 분석·추정치 (Analysis)

주식 전용 데이터입니다.

| **속성**               | **반환 타입** | **설명**                                |
| ---------------------------- | ------------------- | --------------------------------------------- |
| $analyst\_price\_targets$  | $DataFrame$       | 목표가 (현재·평균·고·저·애널리스트 수)    |
| $recommendations$          | $DataFrame$       | 애널리스트 투자의견 이력 (기관·등급·날짜)   |
| $recommendations\_summary$ | $DataFrame$       | 투자의견 요약 (Strong Buy/Buy/Hold/Sell 집계) |
| $upgrades\_downgrades$     | $DataFrame$       | 등급 변경 이력 (기관·이전→현재 등급)        |
| $earnings\_estimate$       | $DataFrame$       | EPS 추정치 (평균·고·저·애널리스트 수)      |
| $revenue\_estimate$        | $DataFrame$       | 매출 추정치                                   |
| $earnings\_trend$          | $DataFrame$       | EPS 추세 (30d/60d/90d 전 대비 변화)           |
| $eps\_revisions$           | $DataFrame$       | EPS 수정 이력 (상향/하향 건수)                |
| $growth\_estimates$        | $DataFrame$       | 성장률 추정치 (종목·섹터·S&P500 비교)       |

---

## 7. 주주·내부자 정보 (Holders & Insiders)

| **속성**             | **반환 타입** | **설명**                                       |
| -------------------------- | ------------------- | ---------------------------------------------------- |
| $major\_holders$         | $DataFrame$       | 주요 주주 비율 (내부자·기관 비중)                   |
| $institutional\_holders$ | $DataFrame$       | 기관 투자자 보유 현황 (기관명·주수·비중·날짜)     |
| $mutualfund\_holders$    | $DataFrame$       | 뮤추얼펀드 보유 현황                                 |
| $insider\_transactions$  | $DataFrame$       | 내부자 거래 이력 (이름·직위·매수/매도·수량·날짜) |
| $insider\_purchases$     | $DataFrame$       | 내부자 매수 이력 요약                                |
| $shares\_full$           | $DataFrame$       | 발행주식수 이력 (시계열)                             |

---

## 8. 펀드/ETF 전용 데이터 (`Ticker.funds_data`)

ETF·뮤추얼펀드 전용이며, `funds_data` 속성을 통해 접근합니다.

| **속성**         | **설명**                                  |
| ---------------------- | ----------------------------------------------- |
| $description$        | 펀드 설명                                       |
| $fund\_overview$     | 운용 개요 (카테고리, 설정일, 순자산, 법적 유형) |
| $fund\_operations$   | 운용 비용·보수·회전율                         |
| $asset\_classes$     | 자산군 비중 (주식/채권/현금 등)                 |
| $top\_holdings$      | 상위 보유 종목 (종목명·비중)                   |
| $equity\_holdings$   | 주식 보유 통계 (PER·PBR 평균 등)               |
| $bond\_holdings$     | 채권 보유 통계 (만기·듀레이션·쿠폰 등)        |
| $bond\_ratings$      | 채권 신용등급 분포                              |
| $sector\_weightings$ | 섹터별 비중                                     |

```python
import yfinance as yf

spy = yf.Ticker("SPY")
data = spy.funds_data

print(data.fund_overview)
print(data.top_holdings)
print(data.sector_weightings)

# funds_data: FundsData 객체 — ETF/뮤추얼펀드 전용
# fund_overview: dict — 카테고리, 순자산, 설정일 등
# top_holdings: DataFrame — 상위 보유 종목(종목명, 비중)
# sector_weightings: dict — 섹터별 비중
```

---

## 9. 일정·뉴스·기타

| **속성**        | **반환 타입** | **설명**                                       |
| --------------------- | ------------------- | ---------------------------------------------------- |
| $calendar$          | $DataFrame$       | 실적 발표일·배당락일·배당지급일 등 주요 일정       |
| $news$              | $list[dict]$      | 관련 최신 뉴스 (제목·링크·출처·발행일)            |
| $isin$              | $str$             | ISIN 코드                                            |
| $history\_metadata$ | $dict$            | 마지막 history() 호출 메타 (통화, 거래소, 타임존 등) |

---

## 10. 실시간 데이터 (WebSocket)

```python
import yfinance as yf

# 단일 티커
t = yf.Ticker("AAPL")
t.live()

# 다중 티커
tickers = yf.Tickers("AAPL MSFT GOOG")
tickers.live()

# live(): WebSocket 기반 실시간 가격 스트리밍
# 거래소 직결 피드가 아니므로 지연 존재
# 연구/모니터링용 — 운영급 트레이딩에는 부적합
```

<aside>
⚠️

**적합성:** 실시간 스트리밍은 학습·프로토타이핑 용도로 활용하고, SLA가 필요한 트레이딩 시스템에서는 브로커 API(Interactive Brokers 등)나 WebSocket 피드 서비스를 우선 고려해야 합니다.

</aside>

---

## 11. 다중 티커 인터페이스

yfinance는 단일/다중 티커를 각각 다른 방식으로 처리합니다.

| **인터페이스**        | **용도**           | **반환 구조**                             |
| --------------------------- | ------------------------ | ----------------------------------------------- |
| $yf.Ticker("AAPL")$       | 단일 종목 심층 조회      | Ticker 객체 → 속성/메서드 직접 접근            |
| $yf.Tickers("AAPL MSFT")$ | 다중 종목 개별 조회      | $tickers.tickers["AAPL"]$ → 개별 Ticker 객체 |
| $yf.download([...])$      | 다중 종목 가격 일괄 수집 | MultiIndex DataFrame (group_by에 따라)          |

<aside>
💡

**포트폴리오 프로젝트 권장 패턴:** 가격 수집 → `yf.download()` / 종목별 메타·재무 → `yf.Ticker()` 루프. 두 인터페이스를 조합하면 효율적인 파이프라인을 구축할 수 있습니다.

</aside>

---

## 12. 티커 심볼 규칙

| **자산 유형** | **형식**          | **예시**         |
| ------------------- | ----------------------- | ---------------------- |
| 주식                | 표준 심볼               | AAPL, MSFT, 005930.KS  |
| 지수                | $`\hat{}\ `$  • 심볼 | ^GSPC (S&P 500), ^VIX  |
| ETF                 | 표준 심볼               | SPY, QQQ, TLT          |
| 외환                | 통화쌍 + =X             | EURUSD=X, JPYKRW=X     |
| 암호화폐            | 코인-USD                | BTC-USD, ETH-USD       |
| 선물                | 코드 + =F               | GC=F (금), CL=F (원유) |

---

## 13. 자산 유형별 데이터 가용성 종합

| **데이터 카테고리** | **주식** | **ETF/펀드** | **암호화폐** | **외환** | **선물** |
| ------------------------- | -------------- | ------------------ | ------------------ | -------------- | -------------- |
| OHLCV (가격)              | ✅             | ✅                 | ✅                 | ✅             | ✅             |
| info (기본 메타)          | ✅ 풍부        | ✅ 중간            | ⚠️ 제한적        | ⚠️ 제한적    | ⚠️ 제한적    |
| 재무제표                  | ✅             | ❌                 | ❌                 | ❌             | ❌             |
| 배당/분할                 | ✅             | ✅                 | ❌                 | ❌             | ❌             |
| 옵션 체인                 | ✅             | ✅                 | ❌                 | ❌             | ❌             |
| 애널리스트 분석           | ✅             | ❌                 | ❌                 | ❌             | ❌             |
| 주주/내부자               | ✅             | ❌                 | ❌                 | ❌             | ❌             |
| 펀드 보유현황             | ❌             | ✅                 | ❌                 | ❌             | ❌             |
| 뉴스                      | ✅             | ✅                 | ✅                 | ⚠️           | ⚠️           |
| 일정 (calendar)           | ✅             | ⚠️               | ❌                 | ❌             | ❌             |
| 실시간 (WebSocket)        | ✅             | ✅                 | ✅                 | ✅             | ✅             |

---

## 14. 실무 주의사항 체크리스트

- [ ] **가격 정의 통일:** 프로젝트 전체에서 `auto_adjust` 설정(조정/비조정)을 고정하고 문서화
- [ ] **결측치 원인 분류:** 비거래일(주말·공휴일·자산별 캘린더 차이) vs 실제 데이터 누락 구분
- [ ] **info 방어 코드:** `.get(key, default)` 패턴으로 KeyError 방지
- [ ] **인트라데이 제한 인지:** 1m → 7일, <1d → 60일
- [ ] **과다 호출 방지:** 대량 요청 시 IP 차단 가능 → 캐싱·sleep 적용
- [ ] **재무제표 자산 유형 확인:** 주식 외에는 빈 DataFrame 반환됨을 전제로 파이프라인 설계

---

<aside>
🔗

**Reference**

- 공식 문서: https://ranaroussi.github.io/yfinance/
- GitHub: https://github.com/ranaroussi/yfinance
- PyPI: https://pypi.org/project/yfinance/
- 관련 WIKI: yfinance란? — Yahoo Finance 데이터 수집 라이브러리

</aside>
