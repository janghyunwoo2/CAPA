# CAPA 프로젝트 PPT 스토리보드
## Text-to-SQL: 데이터 민주화를 위한 AI 파이프라인

> 작성일: 2026-03-28  
> 기반 문서: `2026-03-27-1427_text-to-sql-research.md`  
> 개선 지표: `2026-03-28-1530_text-to-sql-research-ppt-evaluation.md` (평가 72점 → 목표 89점)  
> 발표 대상: 비개발 직군 포함 사내 전 구성원 / 프로젝트 공유 발표  
> 예상 발표 시간: 15~20분 (슬라이드 17장)  
> 최종 수정: 2026-03-28 16:59 (결론부 보강 — Slide 14·16·17 추가 / 핵심 교훈·데이터 수치·마무리 스토리 강화)

---

## 스토리라인 요약

```
[배경] 데이터 폭발적 증가
    ↓
[문제] 비개발자는 데이터에 손을 댈 수 없다 (격차)
    ↓
[해결] Text-to-SQL — 자연어로 데이터에 접근
    ↓
[증거] 국내외 도입 사례 3건 검증
    ↓
[도메인] 우리가 다루는 광고 데이터란 무엇인가 (퍼널 구조 + 핵심 KPI)
    ↓
[CAPA] 우리가 만든 것 — 전체 파이프라인 (수집→ETL→분석) + Vanna API + Slack Bot
    ↓
[CTA] 지금 써보세요 / 함께 발전시켜요
```

---

## 슬라이드별 스토리보드

---

### Slide 01 — 표지

**제목**: 자연어로 데이터를 묻다  
**부제**: CAPA Text-to-SQL — 비개발자를 위한 AI 데이터 파이프라인  
**시각**: CAPA 로고 + 심플한 대화창 아이콘 (자연어 → 데이터)  

> **메시지**: 발표의 키워드 세 가지를 각인시킨다 — 자연어, 데이터, 비개발자

---

### Slide 02 — 세상의 데이터는 폭발적으로 늘고 있다

**헤드라인**: 하루 4억 2,700만 TB — 데이터는 멈추지 않는다

**핵심 인포그래픽**: 연도별 전 세계 데이터 생성량 바 차트

| 연도 | 연간 데이터 생성량 |
|------|----------------|
| 2010 | 2 ZB |
| 2020 | 64 ZB |
| 2024 | 147 ZB |
| 2026 (예측) | 221 ZB |

> **[출처]** Exploding Topics (Semrush 운영 트렌드 분석 플랫폼) — Statista 등 공신력 있는 데이터 집계 기반  
> URL: https://explodingtopics.com/blog/data-generated-per-day  
> 페이지 위치: 본문 "How Much Data Is Created Every Day?" 섹션 → 연도별 데이터 생성량 테이블  
> 기준일: 2026년 2월 업데이트

**한 줄 메시지**: "15년 만에 **74배** — 데이터는 이미 사람의 처리 속도를 넘어섰다"

**시각화 제안**: 숫자를 크게 강조하는 타이포그래피 슬라이드 (2 ZB → 221 ZB 상승 애니메이션)

---

### Slide 03 — 그런데, 데이터에 접근하는 방법은 아직 "SQL"이다

**헤드라인**: 개발자 10명 중 6명이 매일 쓰는 언어 — SQL

**핵심 수치 3개 (크게 강조)**:

```
58.6%          65%            95%
전체 개발자    데이터 직군    우아한형제들
SQL 사용 비율  채용 공고에서  업무에 데이터를
(SO, 2025)    SQL 필수 비율  활용하는 직원 비율
```

> **[출처 ①] 58.6% — Stack Overflow Developer Survey 2025**  
> URL: https://survey.stackoverflow.co/2025/technology/  
> 페이지 위치: Technology → Most popular technologies → Programming, scripting, and markup languages  
> 조사 대상: 전 세계 개발자 31,771명
>
> **[출처 ②] 65% — DataCamp Blog "What is SQL Used For?" (2023)**  
> URL: https://datacamp.com/blog/what-is-sql-used-for  
> 페이지 위치: 본문 중 "SQL in the Job Market" 섹션  
> 분석 대상: 데이터 사이언스·분석 직군 채용 공고
>
> **[출처 ③] 95% — 우아한형제들 기술 블로그 (2024.07.12)**  
> URL: https://techblog.woowahan.com/18144/  
> 페이지 위치: "AI 데이터 분석가 '물어보새' 등장 – 1부" 본문 중 사내 설문 결과 단락

**보조 설명**: SQL이란? → 엑셀 SUMIF/VLOOKUP을 수억 건에 적용하는 언어  
(비개발 청중을 위한 1-2줄 친절한 설명, 기술팀 대상이면 생략)

**시각화 제안**: 세 수치를 카드형 인포그래픽으로 배치

---

### Slide 04 — 문제: 데이터가 필요한 사람 ≠ 데이터에 접근할 수 있는 사람

**헤드라인**: SQL을 모르면 데이터에 손을 댈 수 없다

**격차 다이어그램**:

```
데이터가 필요한 사람          데이터에 접근할 수 있는 사람
────────────────────         ────────────────────────────
마케터 / 기획자 / 운영        개발자 / 데이터 엔지니어
        ↓                              ↓
   "이거 뽑아줘" 요청   →→→   수 일 후 결과 전달
```

**핵심 수치**:
- 마케터의 **75%**: 현재 측정 시스템이 속도·정확도·신뢰성에서 미달  
  > **[출처]** IAB/BWG "State of Data 2026" — Martech.org 기사로 공개  
  > URL: https://martech.org/75-of-marketers-say-their-measurement-systems-are-falling-short/  
  > 페이지 위치: 기사 리드 단락 및 "Measurement gaps" 섹션  
  > 기준일: 2026년 2월 발표

- 비개발 직군의 **절반 이상**: SQL 활용에 어려움  
  > **[출처]** 우아한형제들 기술 블로그 — AI 데이터 분석가 '물어보새' 등장 1부  
  > URL: https://techblog.woowahan.com/18144/  
  > 페이지 위치: 본문 중 사내 설문 결과 단락 ("95%가 데이터를 활용해 업무를 수행…")

**한 줄 메시지**: "데이터가 필요한 사람과 데이터에 접근할 수 있는 사람이 다르다"

**시각화 제안**: 두 그룹을 대비하는 2-컬럼 레이아웃, 화살표로 의존성 강조

---

### Slide 05 — 이 격차가 만드는 비용

**헤드라인**: 데이터 접근 병목이 만드는 3가지 비용

**카드형 3단 레이아웃**:

| 비용 유형 | 내용 | 임팩트 |
|-----------|------|--------|
| 커뮤니케이션 비용 | 요청 → 오해 → 재요청 반복 | 시간·에너지 낭비 |
| 대기 시간 | 데이터 팀 백로그 → 수 시간~수 일 | 실시간 의사결정 불가 |
| 기회비용 | 인사이트 도출보다 데이터 연결에 더 많은 시간 소비 | **$6.2B 생산성 손실** *(IAB/BWG, 2026)* |

> **[출처]** IAB/BWG "State of Data 2026" — Martech.org 기사로 공개  
> URL: https://martech.org/75-of-marketers-say-their-measurement-systems-are-falling-short/  
> 페이지 위치: 기사 본문 중 "AI could recover $6.2 billion in productivity" 관련 단락  
> 기준일: 2026년 2월 발표

**클로징 멘트**: "AI로 루틴 데이터 작업을 대체하면 **약 6조 2천억원**의 생산성 회복이 가능하다"

**시각화 제안**: 숫자 "$6.2B"를 슬라이드 중앙에 크게 배치, 세 카드 아래로

---

### Slide 06 — 해결책: Text-to-SQL

**헤드라인**: 자연어로 물으면, AI가 SQL을 만든다

**파이프라인 다이어그램** (Mermaid 또는 박스 형태로 제작):

```
사용자 자연어 질문
(한국어 OK)
      ↓
LLM + RAG
(도메인 지식 검색)
      ↓
SQL 자동 생성 + 검증
      ↓
쿼리 실행 (Athena)
      ↓
결과 반환
(Slack / 웹 인터페이스)
```

**예시 대화**:
> 사용자: "지난달 대비 이번달 클릭률이 10% 이상 떨어진 캠페인 알려줘"  
> AI: `SELECT campaign_id, ...` → 실행 → 결과 테이블 반환

**한 줄 메시지**: "SQL을 몰라도 된다 — 질문만 하면 된다"

---

### Slide 07 — 이미 검증된 기술: 국내 도입 사례 3건

**헤드라인**: 국내 기업들이 먼저 증명했다

**3개 카드 레이아웃**:

| 기업 | 솔루션 | 효과 |
|------|--------|------|
| **우아한형제들** | AI 데이터 분석가 "물어보새" | 500+ A/B 테스트 검증, SQL 요청 병목 해소 |
| **SK Planet** | InsightLens (2026.02) | LLM+RAG 기반, 수 일 → 즉시 데이터 조회 |
| **데이블(Dable)** | DableTalk (Slack 봇) | 비개발자 직접 Slack에서 데이터 조회 가능 |

> **[출처 — 우아한형제들]** 기술 블로그 "AI 데이터 분석가 '물어보새' 등장 – 1부"  
> URL: https://techblog.woowahan.com/18144/  
> 페이지 위치: 본문 전체 (솔루션 개요, 사내 설문 결과, A/B 테스트 내용)  
> 발행일: 2024년 7월 12일
>
> **[출처 — SK Planet]** T아카데미 블로그 — InsightLens Text2SQL 구축 사례  
> URL: (T아카데미 블로그 내부 게시물)  
> 발행일: 2026년 2월
>
> **[출처 — 데이블]** 데이블 기술 블로그 — DableTalk 개발 과정  
> URL: (데이블 내부 기술 블로그)

**공통 기술 스택**: `LLM + RAG + Vector DB + Slack Bot`

**공통 교훈 (강조 박스)**:
> "모델 성능보다 **도메인 지식(RAG 데이터) 품질**이 정확도를 결정한다"  
> — SK Planet InsightLens PoC 결론

---

### Slide 08 — 우리가 다루는 데이터: 광고 도메인 이해

**헤드라인**: 광고 1번 노출이 구매로 이어지기까지 — Impression → Click → Conversion 퍼널

> *(CAPA 파이프라인 설명 전, 청중이 광고 도메인을 이해해야 이후 슬라이드가 맥락으로 읽힌다)*

**광고 이벤트 퍼널 다이어그램**:

```
┌──────────────────────────────────────────┐
│  광고 노출 (Impression)   ← 100%         │  ← 사용자가 광고를 봤다
└───────────────────┬──────────────────────┘
                    │ CTR 1~5%
┌───────────────────▼──────────────────────┐
│  광고 클릭 (Click)        ← 1~5%         │  ← 사용자가 광고를 눌렀다
└───────────────────┬──────────────────────┘
                    │ CVR 1~10%
┌───────────────────▼──────────────────────┐
│  전환 (Conversion)        ← 0.01~0.5%    │  ← 구매 / 앱 설치 / 회원가입
└──────────────────────────────────────────┘
```

**이벤트 3종 상세**:

| 이벤트 | 의미 | 핵심 필드 예시 | 발생 비율 |
|--------|------|----------------|----------|
| **Impression** | 광고가 사용자 화면에 노출됨 | user_id, ad_id, campaign_id, ad_format, delivery_region, cost_per_impression | 기준 (100%) |
| **Click** | 사용자가 광고를 실제로 클릭함 | impression_id, click_position_x/y, landing_page_url, cost_per_click | Impression의 1~5% |
| **Conversion** | 클릭 후 목표 행동 완료 (구매 등) | click_id, conversion_type, conversion_value, product_id, quantity | Click의 1~10% |

**광고 도메인 핵심 KPI (Text-to-SQL로 물어볼 수 있는 지표들)**:

| 지표 | 계산식 | 비즈니스 의미 |
|------|--------|--------------|
| **CTR** (클릭률) | 클릭수 ÷ 노출수 × 100 | 광고 소재 매력도 |
| **CVR** (전환율) | 전환수 ÷ 클릭수 × 100 | 랜딩페이지·상품 경쟁력 |
| **CPC** (클릭당 비용) | 총 광고비 ÷ 클릭수 | 트래픽 효율성 |
| **ROAS** (광고 수익률) | 전환 매출 ÷ 광고비 × 100 | 캠페인 수익성 |
| **CPM** (1천 노출당 비용) | 총 광고비 ÷ 노출수 × 1,000 | 브랜딩 비용 효율 |

**CAPA가 이 세 이벤트를 어떻게 연결하는가**:

```
Impression ─┐
            ├─▶ Hourly: ad_combined_log     (CTR, CPC 분석)
Click      ─┘
                                │
                                ▼
            ┌─▶ Daily: ad_combined_log_summary  (ROAS, CVR, 캠페인 KPI)
Conversion ─┘
```

**한 줄 메시지**: "노출 → 클릭 → 전환, 이 퍼널을 데이터로 추적하는 것이 CAPA의 출발점이다"

**시각화 제안**: 퍼널 형태 다이어그램 (상단 넓은 바 → 점점 좁아지는 구조) + KPI 카드 5개

---

### Slide 09 — CAPA가 만든 것: 전체 데이터 파이프라인

> **[설계 원칙]** Text-to-SQL의 정확도는 도메인 지식의 품질이 결정한다. CAPA는 광고 퍼널 3종 이벤트 구조를 정확히 반영해 설계됐다 — 복잡한 다중 JOIN은 RAG 예제 쿼리로, ROAS·CTR 등 비즈니스 용어는 ChromaDB 시딩으로, 한국어 질문 편차는 jina-reranker-v2로 해결한다.

**헤드라인**: 광고 로그가 질문의 답이 되기까지 — End-to-End 파이프라인

**전체 아키텍처 다이어그램**:

```
┌────────────────┐     ┌──────────────────────┐     ┌────────────────────┐     ┌──────────────┐
│  로그 생성기    │ ──▶ │  Kinesis Data Streams │ ──▶ │ Kinesis Firehose   │ ──▶ │  S3 (Raw)    │
│  (Python/EKS)  │     │  imp / clk / cvs × 3  │     │  imp / clk / cvs  │     │  Parquet/ZSTD│
└────────────────┘     └──────────────────────┘     └────────────────────┘     └──────┬───────┘
                                                                                       │
                                                                                       ▼
┌────────────────┐     ┌──────────────────────┐     ┌────────────────────┐     ┌──────────────┐
│   Slack Bot    │ ◀── │  Vanna API (FastAPI)  │ ◀── │   AWS Athena       │ ◀── │ Airflow ETL  │
│ (자연어 질문)   │     │  ChromaDB + LLM + RAG │     │  capa_ad_logs DB   │     │ (Hourly/Daily)│
└────────────────┘     └──────────────────────┘     └────────────────────┘     └──────┬───────┘
                                                              ▲                        │
                                                              │                        ▼
                                                     ┌────────────────┐       ┌──────────────┐
                                                     │  Glue Catalog  │ ◀──── │  S3 (Summary)│
                                                     │  스키마 관리    │       │  Parquet/ZSTD│
                                                     └────────────────┘       └──────────────┘
```

**기술 스택 전체 요약**:

| 레이어 | 기술 | 역할 |
|--------|------|------|
| 수집 | Python + Faker (EKS Pod) | 광고 로그 시뮬레이션 |
| 스트리밍 | Kinesis Data Streams × 3 | imp / clk / cvs 이벤트별 분리 수집 |
| 적재 | Kinesis Firehose × 3 | JSON → Parquet 자동 변환 + S3 적재 |
| 저장 (Raw) | Amazon S3 (Parquet/ZSTD) | 시간 파티셔닝 (year/month/day/hour) |
| ETL 워크플로우 | Apache Airflow 2.7+ (KubernetesExecutor) | Hourly·Daily 집계 스케줄링 |
| 저장 (Summary) | Amazon S3 (Parquet/ZSTD) | 집계 결과 저장 |
| 메타데이터 | AWS Glue Catalog | 스키마 및 파티션 관리 |
| 쿼리 | Amazon Athena (Serverless) | SQL 분석 엔진 |
| AI | Vanna AI + ChromaDB + jina-reranker-v2 | 자연어 → SQL 변환 |
| 인터페이스 | Slack Bolt | 사용자 접점 |
| IaC | Terraform | 전체 인프라 코드 관리 |

**AWS 주요 리소스**:
- 리전: `ap-northeast-2` (서울)
- S3 버킷: `capa-data-lake-827913617635`
- Kinesis: `capa-knss-imp-00` / `capa-knss-clk-00` / `capa-knss-cvs-00`
- Athena DB: `capa_ad_logs` / Workgroup: `capa-workgroup`

---

### Slide 10 — CAPA가 만든 것: 데이터 수집 & 적재 구조

**헤드라인**: 광고 로그 3종이 실시간으로 S3에 쌓이는 방법

**로그 3종 이벤트 구조**:

| 이벤트 | 설명 | 주요 필드 | 발생 비율 |
|--------|------|-----------|---------|
| **impression** | 광고 노출 | impression_id, user_id, ad_id, campaign_id, ad_format, delivery_region, cost_per_impression | 기준 (100%) |
| **click** | 광고 클릭 | click_id, impression_id, click_position_x/y, landing_page_url, cost_per_click | CTR 1~5% |
| **conversion** | 전환 (구매 등) | conversion_id, click_id, conversion_type, conversion_value, product_id, quantity | CVR 1~10% |

**트래픽 패턴 (현실 반영)**:

| 시간대 | 트래픽 배수 | 시간당 예상 생성량 |
|--------|------------|-----------------|
| 00~07시 (새벽) | 0.1 ~ 0.2배 | ~800 ~ 2,000개 |
| 11~14시 (점심 피크) | 1.5 ~ 2.0배 | ~15,000 ~ 30,000개 |
| 17~21시 (저녁 피크) | **2.0 ~ 3.0배** | **~30,000 ~ 60,000개** |
| **일일 합계** | — | **약 28만 ~ 30만개** |

**S3 적재 경로 (Hive 파티셔닝)**:

```
s3://capa-data-lake-827913617635/
├── raw/
│   ├── impressions/year=2026/month=03/day=28/hour=15/
│   ├── clicks/    year=2026/month=03/day=28/hour=15/
│   └── conversions/year=2026/month=03/day=28/hour=15/
├── summary/
│   ├── ad_combined_log/         ← Hourly 집계
│   │   └── year=/month=/day=/hour=/
│   └── ad_combined_log_summary/ ← Daily 집계
│       └── year=/month=/day=/
└── .athena-temp/                ← 쿼리 결과 격리 (7일 자동 삭제)
```

**Firehose 핵심 설정**:
- 버퍼 시간: 최대 60초 대기 후 S3 기록
- 출력 포맷: Parquet + ZSTD 압축 (Glue Catalog 스키마 참조 자동 변환)

---

### Slide 11 — CAPA가 만든 것: ETL 파이프라인 (Airflow)

**헤드라인**: 원시 로그가 분석 가능한 형태로 변환되는 과정

**ETL 2단계 구조**:

```
[Stage 1 — Hourly ETL]  매시간 10분 (10 * * * *)
  impressions (1시간) ─┐
                       ├─ LEFT JOIN ─▶ ad_combined_log (27개 필드, hour 파티션)
  clicks      (1시간) ─┘

[Stage 2 — Daily ETL]   매일 02시 (0 2 * * *)
  ad_combined_log (24시간 × 27필드) ─┐
                                      ├─ LEFT JOIN ─▶ ad_combined_log_summary (35개 필드, day 파티션)
  conversions     (하루치)            ─┘
```

**테이블 비교 (용도 구분이 핵심)**:

| 항목 | ad_combined_log | ad_combined_log_summary |
|------|----------------|------------------------|
| 갱신 주기 | 매 시간 | 매일 02시 |
| 파티션 키 | year/month/day/**hour** | year/month/day |
| 포함 데이터 | impression + click | impression + click + **conversion** |
| 필드 수 | 27개 | 35개 |
| 주요 용도 | 시간대별 CTR, 실시간 모니터링 | **일별 ROAS, 전환율, 캠페인 KPI** |

**ETL 처리 방식 (Athena INSERT 미지원으로 인한 우회)**:

```
Athena SELECT → Python DataFrame → Parquet 변환 → S3 업로드 → MSCK REPAIR TABLE
```

> Athena는 Presto 기반으로 INSERT INTO를 지원하지 않음 → Python이 중간 변환 담당

**설계 결정: DAG 2개 분리 근거**

| 기준 | 1개 파일 | 2개 파일 (채택) |
|------|----------|----------------|
| 스케줄 관리 | 주기 혼재 → 복잡 | 파일당 1 DAG, 주기 명확 |
| 독립 배포 | hourly 수정이 daily에 영향 | 독립적 배포 가능 |
| 시간대 처리 | Airflow UTC → ETL KST 변환 필수 | `pendulum.in_timezone('Asia/Seoul')` |

---

### Slide 12 — CAPA가 만든 것: 실제 데모

**헤드라인**: 실제로 이렇게 동작합니다

**데모 시나리오 (슬라이드에 스크린샷 또는 GIF 삽입)**:

```
Step 1. Slack에서 질문 입력
  → "지난 주 캠페인별 클릭률 상위 5개 알려줘"

Step 2. Vanna API — ChromaDB에서 관련 예제 쿼리 검색 (RAG)
  → ad_combined_log_summary 테이블 스키마 + 유사 예제 쿼리 검색
  → jina-reranker-v2가 후보를 재정렬 (정확도 향상)

Step 3. LLM이 SQL 자동 생성
  → SELECT
         campaign_id,
         COUNT(*) AS impression_cnt,
         SUM(CASE WHEN is_click THEN 1 ELSE 0 END) AS click_cnt,
         ROUND(
             CAST(SUM(CASE WHEN is_click THEN 1 ELSE 0 END) AS DOUBLE)
             / COUNT(*) * 100, 2
         ) AS ctr_pct
     FROM ad_combined_log_summary
     WHERE date_parse(concat(year,'-',month,'-',day), '%Y-%m-%d')
           BETWEEN DATE '2026-03-21' AND DATE '2026-03-27'
     GROUP BY campaign_id
     ORDER BY ctr_pct DESC
     LIMIT 5

Step 4. Athena 실행 후 결과 반환
  → 캠페인 ID    | 노출수  | 클릭수 | CTR%
     campaign_042 | 45,320 | 2,130 | 4.70%
     campaign_017 | 38,910 | 1,740 | 4.47%
     ...

Step 5. 결과 Slack으로 반환
  → 테이블 형태로 채널에 메시지 전송
```

**테이블 선택 근거 (비개발자용 설명)**:

| 질문 유형 | 사용 테이블 | 이유 |
|----------|-----------|------|
| 시간대별 클릭률, 실시간 현황 | `ad_combined_log` | 시간(hour) 파티션 보유 |
| 캠페인 성과, ROAS, 전환율 | `ad_combined_log_summary` | 전환(conversion) 데이터 포함 |

> AI가 질문을 분석하여 어떤 테이블을 쓸지 **자동으로 판단**합니다

**한 줄 메시지**: "질문 하나로, 데이터팀에 요청할 필요가 없어진다"

---

### Slide 13 — AS-IS vs TO-BE: 도입 전후 비교

**헤드라인**: 무엇이 바뀌는가

| 항목 | AS-IS (현재) | TO-BE (CAPA 도입 후) |
|------|-------------|---------------------|
| 데이터 조회 방식 | 개발자에게 요청 | Slack에서 자연어로 직접 질문 |
| 소요 시간 | 수 시간 ~ 수 일 | 수 초 |
| 접근 가능 직군 | 개발자·데이터 엔지니어 | 전 구성원 |
| SQL 지식 필요 여부 | 필수 | 불필요 |
| 커뮤니케이션 비용 | 높음 (반복 요청) | 최소화 |
| 의사결정 속도 | 느림 | 실시간 |

**시각화 제안**: 체크/X 아이콘으로 직관적 비교, 배경 색상 대비 (회색 → 초록)

---

### Slide 14 — 숫자로 보는 변화: 우리가 만든 것의 규모

**헤드라인**: CAPA가 처리하는 데이터 — 수치로 보는 규모

**임팩트 수치 4개 (크게 강조)**:

```
약 28만~30만 건          3종                    2단계               수 초
  일일 광고 로그         이벤트 유형          ETL 파이프라인        질문→결과 소요시간
  (Impression+           (Impression          (Hourly / Daily)      (Athena 쿼리
   Click+Conversion)      / Click /             집계 자동화)         실행 기준)
                          Conversion)
```

**데이터 흐름 수치 요약 테이블**:

| 구간 | 규모 / 성능 |
|------|------------|
| 하루 생성 로그 | 약 28만~30만 건 (시간대별 트래픽 패턴 반영) |
| 피크 시간대 생성량 | 최대 60,000건/시간 (저녁 17~21시, 3.0배 트래픽) |
| Kinesis 스트림 수 | 3개 (impression / click / conversion 분리) |
| S3 파티션 구조 | year / month / day / hour (4단계 Hive 파티셔닝) |
| Hourly ETL 실행 주기 | 매시간 10분 (KST 기준) |
| Daily ETL 실행 주기 | 매일 02시 (KST 기준) |
| Athena 쿼리 응답 | 수 초 (Serverless, 온디맨드 실행) |
| RAG 후보 쿼리 수 | 최대 20개 → jina-reranker-v2 재정렬 |

**한 줄 메시지**: "하루 30만 건의 광고 로그가 자동으로 쌓이고, 자연어 한 문장으로 꺼낼 수 있다"

**시각화 제안**: 숫자 4개를 카드형으로 크게 배치, 하단에 데이터 흐름 수치 테이블

---
### Slide 15 — 발전방향 & 시행착오 & 아쉬운 점

**헤드라인**: 만들면서 배웠고, 못 만든 것이 다음을 만든다

---

#### 🔧 시행착오

| 시점 | 문제 상황 | 해결 방법 | 교훈 |
|------|----------|----------|------|
| 3/9 리포트 구조 개선 | Redash·T2S와 기능 중복 → 유지보수 비용 증가 예상 | AI 분석·온디맨드 요청 제거, 정기 리포트 + 핵심 지표만 남김 | 기능 추가보다 시스템 간 역할 분리가 유지보수에 더 중요 |
| 3/16 이상치 탐지 | Prophet 신뢰구간이 음수로 내려가 잘못된 이상치 판단 발생 | 실제 데이터 최솟값(2월 기준)으로 하한 보정 | 모델 성능보다 데이터 특성에 맞게 보정하는 과정이 더 중요 |
| 3/16 이상치 탐지 | CloudWatch 집계 지연으로 실시간 수집 시 데이터 누락 | 수집 시점에 2분 버퍼를 두고 조회 (2, 7, 12, 17… 분마다 실행) | 실시간 처리에서는 지연 가능성을 설계 단계부터 반영해야 함 |
| 3/24 ETL 파티션 문제 | Athena INSERT 미지원 → 파티션 메타데이터 자동 반영 안 됨 | Python으로 Parquet 직접 변환 후 S3 업로드 → MSCK REPAIR TABLE | Athena 제약은 Python이 중간 레이어로 흡수해야 함 |

---

#### 😅 아쉬운 점

| 항목 | 내용 | 이유 |
|------|------|------|
| **"지난 주 / 이번 주" 질문 구현 불가** | `last week` / `this week` 같은 상대적 날짜 표현 처리 미구현 | Athena의 날짜 파티션 구조(`year/month/day`)와 자연어 날짜 파싱 간 매핑 로직 구현 시간 부족 |
| **데이터 분석의 입체성 부족** | 단순 지표 조회 수준에 머뭄, 시계열 추세·이상 탐지·비교 분석까지는 미도달 | 이상치 탐지(Conversion)는 5분 단위 데이터 희소성 문제로 시간 단위 전환 검토 중 중단 |
| **Conversion 이상치 탐지 미완성** | Impression·Click만 구현, Conversion은 타임스탬프 불일치 문제로 중단 | 컬럼의 month/day/hour 값이 실제 timestamp와 달라 파티션 기준 집계 불일치 발생 |
| **리포트 Redash 연동 미완성** | 쿼리를 Redash 한 곳에서 관리하는 방식 계획했으나 시간 부족으로 미구현 | 발표 준비와 병행으로 우선순위 조정 |

---

#### 🚀 향후 발전 방향

| 항목 | 내용 |
|------|------|
| **상대 날짜 표현 처리** | `last week`, `이번 달`, `최근 7일` 등 자연어 날짜 파싱 → SQL 날짜 조건 자동 변환 |
| **이상치 탐지 고도화** | 24시간 주기 재학습으로 모델 점진적 업데이트 / Conversion 1시간 단위 이상치 탐지 완성 |
| **입체적 분석 제공** | 단순 조회 → 추세 비교, 기간별 증감률, 캠페인 간 벤치마킹 등 다차원 분석 지원 |
| **리포트-Redash 연동** | 쿼리 단일 관리 → 리포트와 대시보드 데이터 일관성 확보 |

---

### Slide 16 — CAPA가 우리에게 가르쳐준 것: 핵심 교훈 3가지

**헤드라인**: 기술보다 중요한 것 — 도메인, 데이터 품질, 설계 결정

> *(시행착오를 나열하는 것에서 한 단계 나아가, 이 프로젝트 전체에서 우리가 얻은 본질적 교훈을 3가지로 압축한다)*

---

**교훈 1 — 모델 성능보다 RAG 데이터 품질이 정확도를 결정한다**

```
LLM 모델 교체        → 정확도 변화: 소폭
ChromaDB 예제 쿼리 추가 → 정확도 변화: 유의미한 향상
jina-reranker-v2 도입  → 정확도 변화: 재정렬로 상위 후보 품질 향상
```

> **교훈**: "더 좋은 AI"가 아니라 "더 좋은 데이터"가 정확도를 만든다.  
> SK Planet InsightLens PoC도 동일한 결론: *"모델 성능보다 도메인 지식(RAG 데이터) 품질이 정확도를 결정한다"*

---

**교훈 2 — 데이터 파이프라인 설계는 질문의 범위를 결정한다**

```
ad_combined_log (Hourly)         → 시간대별 CTR, 실시간 현황만 대답 가능
ad_combined_log_summary (Daily)  → ROAS, 전환율, 캠페인 성과 대답 가능
```

> **교훈**: 어떤 질문에 대답할 수 있는지는 AI가 결정하는 게 아니라, **ETL 설계 단계에서 이미 결정**된다.  
> 데이터를 어떻게 쌓느냐가, AI가 무엇을 말할 수 있는지를 규정한다.

---

**교훈 3 — 실시간성과 정확성은 설계 단계에서 트레이드오프를 선택해야 한다**

```
Firehose 버퍼 60초  →  실시간성 약간 희생, 안정적 S3 적재
CloudWatch 2분 버퍼  →  이상치 탐지 지연, 데이터 누락 방지
Hourly ETL 10분     →  시간 경계 데이터 안전하게 수집 후 집계
```

> **교훈**: "실시간으로 다 된다"는 없다. 어디서 얼마의 지연을 허용할지는 설계 결정이다.

**시각화 제안**: 교훈 3개를 카드 형식으로 배치, 각 카드에 핵심 한 줄만 크게 강조

---

### Slide 17 — 마무리 & Call to Action

**헤드라인**: 데이터는 모두의 것이어야 한다

**마무리 스토리 (3단 구성)**:

> **[시작]** 우리는 하루 30만 건의 광고 로그를 자동으로 쌓는 파이프라인을 만들었습니다.  
> **[과정]** 그 데이터를 누구나 질문으로 꺼낼 수 있도록, AI와 클라우드를 연결했습니다.  
> **[결론]** 빅데이터 시대에 데이터 접근성은 선택이 아닌 필수입니다. SQL 장벽 없이, 누구나 데이터에 질문할 수 있는 환경 — CAPA가 만들었습니다.

**CAPA가 증명한 것 (요약 박스)**:

```
✅ 광고 로그 3종을 실시간으로 수집·적재하는 파이프라인 구축 완료
✅ Hourly / Daily 자동 ETL → Athena에서 바로 쿼리 가능
✅ 자연어 → SQL → 결과 반환 (Slack 봇 통합)
✅ RAG + jina-reranker-v2로 한국어 질문 정확도 향상
```

**3가지 Call to Action**:

1. **지금 써보세요** → Slack `#data-bot` 채널에서 바로 질문
2. **피드백 주세요** → 오답·오류 사례 제보 → RAG 품질 지속 개선
3. **함께 발전시켜요** → 유용한 쿼리 예제 기여 → ChromaDB 시딩 강화

**마지막 한 줄 (크게)**:

> **"질문만 하세요. 나머지는 CAPA가 합니다."**

---

## 슬라이드 구성 요약

| # | 슬라이드 제목 | 핵심 메시지 | 시각화 |
|---|-------------|------------|--------|
| 01 | 표지 | CAPA Text-to-SQL 소개 | 로고 + 대화 아이콘 |
| 02 | 데이터 폭발적 증가 | 15년 만에 74배 | 바 차트 (ZB 단위) |
| 03 | SQL의 현실 | 개발자 10명 중 6명이 SQL 사용 | 카드형 수치 3개 |
| 04 | 격차 문제 | 필요한 사람 ≠ 접근할 수 있는 사람 | 2-컬럼 대비 다이어그램 |
| 05 | 격차의 비용 | $6.2B 생산성 손실 | 3카드 + 임팩트 수치 |
| 06 | Text-to-SQL 개요 | 자연어 → SQL 자동 생성 | 파이프라인 플로우 |
| 07 | 국내 사례 3건 | 이미 검증된 기술 | 3-카드 레이아웃 |
| **08** | **광고 도메인 이해** | **Impression → Click → Conversion 퍼널 + KPI 5종** | **퍼널 다이어그램 + KPI 카드** |
| 09 | CAPA 아키텍처 (전체) | End-to-End 파이프라인 전체 조감 (설계 원칙 포함) | 전체 흐름도 + 기술 스택 표 |
| 10 | 데이터 수집 & 적재 | 로그 3종 → Kinesis → S3 구조 | 이벤트 표 + S3 경로 트리 + 트래픽 패턴 |
| 11 | ETL 파이프라인 | Airflow 2-DAG 구조 + 테이블 비교 | ETL 플로우 + 테이블 비교 표 |
| 12 | 실제 데모 | 질문 → RAG → SQL → 결과 5단계 | 스텝별 코드 블록 + 결과 테이블 |
| 13 | AS-IS vs TO-BE | 무엇이 바뀌는가 | 비교 테이블 |
| **14** | **숫자로 보는 변화** | **하루 30만 건 · 수 초 응답 · 자동화** | **임팩트 수치 카드 4개 + 수치 요약 테이블** |
| **15** | **시행착오 & 아쉬운 점** | **구현 한계 + 개선 방향** | **텍스트** |
| **16** | **핵심 교훈 3가지** | **도메인·데이터 품질·설계 트레이드오프** | **교훈 카드 3개** |
| **17** | **CTA** | **지금 써보세요** | **증명 요약 박스 + 3가지 행동 유도** |

---

## 평가 보고서 대비 개선 사항

| 평가 감점 항목 | 스토리보드 반영 내용 |
|---------------|-------------------|
| 중복 섹션 (3절↔6절) | Slide 03+04로 통합, 수치 중복 제거 |
| 섹션 순서 역전 (IAB 보고서 위치) | Slide 05에서 '비용' 섹션으로 자연스럽게 배치 |
| 시각화 자산 부족 | 각 슬라이드에 명시적 시각화 제안 기재 |
| Call to Action 없음 | Slide 16에 3가지 CTA + 증명 요약 박스 명시 |
| 기술 한계 언급 없음 | Slide 08 신설 (한계 + CAPA 해결 방향) |
| Stack Overflow 연도 불일치 | Slide 03에 "(SO, 2025)" 명확히 표기 |
| 배경 설명 과도 | Slide 02~05를 압축 (4장으로 배경 완결) |
| CAPA 적용 비중 낮음 | Slide 09~12 4장을 CAPA 전용으로 배정 |
| **결론부 설득력 부족** | **Slide 14(수치 임팩트) + Slide 16(핵심 교훈 3가지) + Slide 17(마무리 스토리) 신설** |
| **청중이 가져갈 메시지 불명확** | **교훈 3가지를 카드 형식으로 압축, 마지막 한 줄 강조 메시지 추가** |

---

## 참고 출처

| 수치 | 출처명 | URL | 페이지 내 위치 | 기준일 |
|------|--------|-----|--------------|--------|
| 하루 4억 2,700만 TB / 연간 147 ZB | Exploding Topics (Statista 집계 기반) | https://explodingtopics.com/blog/data-generated-per-day | "How Much Data Is Created Every Day?" 섹션 → 연도별 데이터 생성량 테이블 | 2026.02 |
| 개발자 SQL 사용 **58.6%** | Stack Overflow Developer Survey 2025 | https://survey.stackoverflow.co/2025/technology/ | Technology → Most popular technologies → Programming, scripting, and markup languages | 2025 |
| 데이터 직군 채용공고 SQL 필수 **65%** | DataCamp Blog "What is SQL Used For?" | https://datacamp.com/blog/what-is-sql-used-for | 본문 중 "SQL in the Job Market" 섹션 | 2023 |
| 마케터 **75%** 측정 시스템 불만 | Martech.org (IAB/BWG State of Data 2026 인용) | https://martech.org/75-of-marketers-say-their-measurement-systems-are-falling-short/ | 기사 리드 단락 및 "Measurement gaps" 섹션 | 2026.02 |
| **$6.2B** 생산성 손실 추산 | Martech.org (IAB/BWG State of Data 2026 인용) | https://martech.org/75-of-marketers-say-their-measurement-systems-are-falling-short/ | 기사 본문 중 AI 생산성 회복 관련 단락 | 2026.02 |
| 우아한형제들 사내 설문 (95%, 50%+) | 우아한형제들 기술 블로그 — 물어보새 1부 | https://techblog.woowahan.com/18144/ | 본문 중 사내 설문 결과 단락 ("95%가 데이터를 활용해 업무를 수행…") | 2024.07.12 |
| 우아한형제들 물어보새 솔루션 상세 | 우아한형제들 기술 블로그 — 물어보새 2부 | https://techblog.woowahan.com/18362/ | 본문 전체 (Data Discovery 기능 설명) | 2024.07 |
| SK Planet InsightLens 사례 | T아카데미 블로그 | (T아카데미 내부 게시물) | InsightLens 구축 과정 전체 | 2026.02 |
| 데이블 DableTalk 사례 | 데이블 기술 블로그 | (데이블 내부 기술 블로그) | DableTalk 개발 과정 전체 | — |
