# CAPA 프로젝트 PPT 발표 대본 v3

> 작성일: 2026-03-31  
> 기반: pptx_extracted.txt (실제 슬라이드 텍스트 기준)  
> 총 슬라이드: 33장  
> 발표 예상 시간: 20~25분  
> **보강 내용**: 각 슬라이드별 구체적 기술 디테일 및 수치 추가 (코드베이스 기반)

---

## Slide 1 — 표지

안녕하세요. 저희는 CAPA 팀입니다.

오늘 발표 주제는 **"온라인 광고 로그 처리 파이프라인 및 분석 플랫폼"**입니다.

팀 이름 CAPA는 **Cloud-native AI Pipeline for Ad-logs**의 약자이면서, 동시에 영어 단어 **"역량·가능성"을 뜻하는 capacity**에서 따온 이름입니다. 데이터에 접근하지 못했던 비개발자에게 데이터를 다룰 수 있는 역량을 부여한다는 의미를 담고 있습니다.

저희가 만든 시스템의 핵심 가치는 한 문장으로 요약됩니다.

> **"비개발자도 자연어로 데이터에 질문할 수 있다."**

---

## Slide 2 — 팀 구성 및 역할 분담

저희 팀은 세 명으로 구성되어 있습니다. 각자 독립적인 영역을 맡되, 전체가 하나의 파이프라인으로 연결되도록 협력했습니다.

- **장현우** — 인프라 & AI 엔진  
  AWS 클라우드 인프라 아키텍처(Terraform) 설계, 자연어 질의(Text-to-SQL) 엔진 및 RAG 시스템 구축

- **김시현** — 데이터 수집 & 시각화  
  실시간 데이터 수집 파이프라인(Kinesis) 구현, Redash 시각화 대시보드 및 데이터 마킹 설계

- **김병훈** — 자동화 리포트 & 이상 탐지  
  Airflow 기반 리포트 생성 자동화(DAG) 개발, Prophet 모델 기반 로그 이상치 탐지 시스템 구현

---

## Slide 3 — 목차

오늘 발표는 크게 네 파트로 구성됩니다.

1. **프로젝트 배경** — 기획 배경, 문제 원인, 솔루션 제안, 도메인 선정
2. **시연 영상** — 핵심 기능 4가지 직접 시연
3. **전체 프로세스** — 시스템 아키텍처부터 인프라 운영까지 기술 상세
4. **결론 및 회고** — AS-IS vs TO-BE, 시행착오, 향후 발전 방향

---

## Slide 4 — SECTION 01: 프로젝트 배경

---

## Slide 5 — 기획 배경: 데이터 격차(Data Gap)

먼저, 저희가 해결하고자 한 문제의 본질부터 이야기하겠습니다.

오늘날 기업에서 일하는 사람들은 두 부류로 나뉩니다.

```
데이터가 필요한 사람          접근할 수 있는 사람
마케터 / 기획자 / 운영팀   ≠   개발자 / 데이터 엔지니어

SQL 지식 부족                   SQL 활용 능력 보유
실시간 분석 불가                분석 요청 병목 발생
```

**데이터가 필요한 사람과, 데이터에 접근할 수 있는 사람이 다릅니다.** 이것이 저희가 해결하고자 한 구조적 문제, 데이터 격차입니다.

---

## Slide 6 — 상황 예시: 누구나 공감하는 '기다림'

이런 상황, 한 번쯤 겪어보셨을 겁니다.

> 오전 10:03 — 마케터: "안녕하세요, 지난달 데이터 좀 확인할 수 있을까요? 🙏"  
> 오전 10:47 — 담당자: "확인해볼게요!"  
> 오후 3:12 — 담당자: "지금 다른 건 처리 중이라 내일 오전 중으로 드릴게요"  
> 오후 3:13 — 마케터: "아 넵... 감사합니다 😅"

**오전 10:03부터 오후 3:13까지 5시간 10분.**

데이터는 어딘가에 분명히 있습니다. 근데 꺼낼 수가 없습니다.

---

## Slide 7 — 발생 비용: 격차가 만드는 막대한 손실

이 격차는 전 세계 기업에게 **연간 6.2조 달러 규모의 생산성 손실**을 만들어냅니다.

구체적으로 세 가지 비용이 발생합니다.

| 비용 유형 | 내용 |
|-----------|------|
| **커뮤니케이션 비용** | 요청 → 오해 → 재요청의 반복으로 인한 에너지 낭비 |
| **의사결정 골든타임** | 데이터 팀 백로그로 인한 실시간 시장 대응 실패 |
| **인적 리소스 낭비** | 전문가들이 단순 데이터 추출에 시간의 40% 이상 사용 |

---

## Slide 8 — 문제 원인: 왜 구조적으로 생기나?

이 문제는 크게 두 가지 원인에서 비롯됩니다.

**원인 1 — 기술 장벽**  
데이터를 꺼내려면 SQL을 알아야 합니다. 이 장벽 탓에 기업 데이터의 68%는 비개발 직군에게 닿지 못하고 방치됩니다.  
*(출처: Seagate & IDC Report 2020)*

**원인 2 — 분석팀 병목**  
모든 요청이 소수의 분석팀에게 집중됩니다. 진짜 병목은 "데이터 요청 vs 소수의 분석팀"이라는 구조 자체입니다.  
*(출처: Instawork: Analytics in the Age of AI)*

---

## Slide 9 — 도메인 선정: 왜 광고 도메인인가?

저희는 이 문제를 해결할 도메인으로 **광고 로그**를 선정했습니다.

광고 로그는 실시간으로 발생합니다. 빠르게 보고 즉각 예산을 조정해야 수익이 나는 도메인입니다.

핵심 KPI 산식:
- **CTR** = 클릭 수 / 노출 수
- **CVR** = 전환 수 / 클릭 수
- **ROAS** = 매출 / 광고비

그리고 마케터에게는 네 가지 구체적인 고통이 있습니다.

| 상황 | 고통 |
|------|------|
| 데이터 분석이 필요하다 | SQL 모르면 데이터팀 요청 → 수 시간 대기 |
| 일정 주기로 리포트를 만들어야 한다 | 수기 엑셀 집계 → 반복 작업에 수 시간 낭비 |
| 내가 안 보는 사이 로그가 이상해졌다 | 뒤늦게 발견 → 예산 이미 낭비됨 |
| 늘 봐야 하는 지표가 있다 | 매번 요청 반복 → 리소스 낭비 |

**CAPA는 이 4가지를 각각 해결했습니다.**

---

## Slide 10 — 솔루션 제안: CAPA의 4가지 핵심 기능

| 기능 | 해결하는 고통 | 내용 |
|------|-------------|------|
| **Ask** | SQL 없이 즉시 데이터 조회 | Slack에서 자연어 질문 → 수십 초 내 즉시 답변 |
| **Report** | 수기 리포트 반복 제거 | Airflow 기반 일/주/월 리포트 자동 생성·전송 |
| **Alert** | 이상 발생 즉시 감지 | AI 모델이 5분 주기로 실시간 감지 + Slack 알림 |
| **Dashboard** | 반복 요청 없는 셀프 확인 | Redash 원클릭 대시보드, SQL 없이 지표 확인 |

말보다 직접 보는 게 빠릅니다. 지금 바로 시연해드리겠습니다.

---

## Slide 11 — SECTION 02: 시연 영상

---

## Slide 12 — 시연 Scene 1: 리포트 자동 전송

첫 번째 시연은 **Airflow 자동 리포트 생성 → Slack 전송** 기능입니다.

Airflow가 일/주/월 주기로 리포트를 자동 생성하고 Slack으로 전송합니다. 마케터는 매일 아침 수기 엑셀 작업 없이 **Slack에서 바로 리포트를 확인**할 수 있습니다.

> *"SQL 지식 없이 매일 아침마다 리포트"*

---

## Slide 13 — 시연 Scene 2: Redash 대시보드

두 번째 시연은 **Redash 딥링크 원클릭 대시보드** 기능입니다.

리포트 하단의 링크를 클릭하면 SQL 지식 없이도 Redash 대시보드에 바로 연결됩니다. CTR, CVR, ROAS 등 핵심 지표를 한눈에 확인하고 즉시 의사결정에 활용할 수 있습니다.

> *"SQL 지식 없이 리포트와 함께 대시보드까지 원클릭"*

---

## Slide 14 — 시연 Scene 4: 이상치 알림

세 번째 시연은 **실시간 이상치 탐지 알림** 기능입니다.

Prophet + Isolation Forest 앙상블 모델이 이상 징후를 탐지하고, Airflow가 **5분 주기**로 감지하여 Slack으로 즉시 알림을 보냅니다. 마케터는 엔지니어의 개입 없이도 이상 상황에 즉시 대응할 수 있습니다.

> *"내가 안 보는 사이에도 이상 감지 → 엔지니어 개입 없이 즉시 마케터에게 알림"*

---

## Slide 15 — 시연 Scene 3: 자연어 질의(Text-to-SQL)

네 번째 시연은 가장 핵심 기능인 **자연어 → SQL 변환** 기능입니다.

Slack에서 자연어로 질문하면:
1. Vanna AI가 SQL을 생성하고
2. AWS Athena를 통해 실행된 후
3. 결과가 Slack으로 반환됩니다

> ⚡ **반나절 이상 걸리던 작업을 단 수십 초 만에 처리합니다.**

---

## Slide 16 — SECTION 03: 전체 프로세스

---

## Slide 17 — 시스템 아키텍처 및 광고 데이터 흐름

이제 CAPA 시스템의 전체 구조를 설명드리겠습니다.

**전체 데이터 흐름:**

```
[Log Generator] Python Script (services/log-generator/)
  → Impression / Click / Conversion 로그 생성 (시간대별 트래픽 패턴 적용)
        ↓
[Kinesis Data Streams & Firehose × 3]
  → 이벤트별 독립 스트림으로 분리 수집 (impression/click/conversion 각각)
        ↓
[Amazon S3 Data Lake]
  → Parquet 형식, year/month/day/hour 파티셔닝 (약 1.2TB/월 예상)
        ↓
[Glue & Athena]
  → 서버리스 쿼리 엔진 (쿼리당 평균 2-5초 응답)
        ↓
[Amazon EKS 클러스터 (통합 운영 인프라)]
  ├── Apache Airflow — 5분 주기 이상 탐지 / Raw 로그 집계 / 리포트 생성 / Slack 전송
  │   ├── KubernetesPodOperator × 8개 DAG (t2_ad_hourly_summary, t3_report_generator_v3 등)
  │   └── ECR 이미지 기반 격리 실행 (OOM 방지)
  ├── Vanna AI & ChromaDB — 자연어 → SQL 변환 (RAG)
  │   ├── 11단계 파이프라인 (Intent Classifier → SQL Generator → Validator)
  │   └── ChromaDB 시딩: 70여개 Golden QA + 21종 Presto 구문 지식
  ├── Redash Dashboard — Athena 연동 시각화 (쿼리 기반 파라미터 지원)
  └── Slack Bot — 자연어 조회 · 실시간 알림 · 리포트 수신 창구
      └── 비동기 폴링: task_id 즉시 반환 + 3초 간격 폴링 (최대 300초)
```

CloudWatch는 Kinesis 스트림을 모니터링하여 이상치 탐지 데이터를 제공합니다.

---

## Slide 18 — 데이터 수집 및 저장 (Kinesis + S3/Athena)

저희가 적용한 핵심 최적화 전략은 세 가지입니다.

**① 이벤트별 독립 스트림 분리**  
트래픽과 타이밍이 완전히 다른 Impression, Click, Conversion을 각각 독립적인 Kinesis 스트림으로 분리했습니다.  
*(Terraform: 03-kinesis.tf에 3개 스트림 정의, 각 스트림당 2개 샤드)*

**② S3 파티셔닝 + Parquet 형식**  
`year/month/day/hour` 구조로 파티셔닝하고 컬럼 기반 Parquet 형식을 사용합니다. 단일 날짜 조회 시 전체 스캔을 방지하고 Athena 스캔 비용을 획기적으로 절감합니다.  
*(Glue Crawler: 자동 Parquet 변환, 예상 월간 데이터량 1.2TB)*

**③ Airflow Summary 테이블**  
1시간/1일 단위로 사전 집계 테이블을 생성합니다. 대시보드와 LLM은 무거운 원본 데이터 대신 가벼운 요약 연산만 수행합니다.  
*(DAG: t2_ad_hourly_summary, t2_ad_daily_summary — KubernetesPodOperator로 격리 실행)*

---

## Slide 19 — Airflow DAG 파이프라인

Airflow는 저희 시스템의 **"뇌"** 역할을 합니다.

- 이상치 탐지, 리포트 자동화, 요약 테이블 생성 — 각 DAG이 독립적으로 가동되며 Airflow가 일괄 주기를 제어하고 상태를 모니터링합니다.  
*(총 8개 DAG: capa_chromadb_refresh, t2_ad_hourly_summary, t2_ad_daily_summary, t3_report_generator_v3 등)*

기술적으로 핵심은 **KubernetesPodOperator** 도입입니다.

- Pandas, Matplotlib 등 무거운 라이브러리 의존성을 격리하여 워커 노드 부하를 방지합니다.  
*(ECR 이미지: capa-t3-report-generator, capa-airflow-kpo-t3 등 전용 이미지 사용)*
- 작업이 끝나면 파드가 종료되므로 유휴 리소스 낭비가 없습니다.  
*(K8s Secret: t3-report-secret으로 환경변수 주입, IRSA로 AWS 권한 부여)*

---

## Slide 20 — 대시보드 구축: Why Redash?

저희가 Redash를 선택한 이유는 네 가지입니다.

| 이유 | 설명 |
|------|------|
| **쿼리 기반 시각화** | Athena 쿼리를 그대로 붙여넣어 즉시 대시보드화 가능 |
| **파라미터 지원** | `{{ 변수명 }}` Jinja2 문법으로 날짜 조건을 마케터가 직접 변경 가능 |
| **쿼리 결과 일원화** | AWS Athena 접근을 Redash로 일원화하여 쿼리 결과를 한곳에서 관리 |
| **사용자 접근** | 마케터가 Redash 계정으로 직접 접속해 쿼리를 수정하고 대시보드를 생성 가능 |

---

## Slide 21 — 어떻게 자연어가 SQL이 되는가: 11단계 파이프라인

일반 LLM은 존재하지 않는 테이블명이나 컬럼명을 지어내는 **할루시네이션 문제**가 심각합니다.

CAPA는 사내 스키마를 학습시키고 RAG를 통해 맥락을 주입하여 이 문제를 해결했습니다. 파이프라인은 총 11단계입니다.

| 단계 그룹 | 처리 내용 |
|-----------|-----------|
| **입력 처리** | Step 0 Conversation Retriever → Step 1 Intent Classifier → Step 2 Question Refiner → Step 3 Keyword Extractor |
| **RAG 검색** | Step 4 RAG Retriever — ChromaDB에서 관련 스키마·쿼리·비즈니스 용어 검색 |
| **SQL 생성/검증** | Step 5 SQL Generator → Step 6 SQL Validator |
| **실행/분석** | Step 7~9 Query Execution → Step 10 AI Analyzer |
| **기록** | Step 11 History Recorder — DynamoDB에 대화 이력 저장 |

**멀티턴 지원**: DynamoDB에 5턴 이력을 저장해 "이전 질문 기준으로 이번 달은?" 같은 후속 질문이 가능합니다.  
*(AsyncQueryManager: task_id 기반 상태 관리, TTL 24시간)*

**비동기 처리**: 쿼리 수십 초 소요 → task_id 즉시 반환 → 폴링 → 완료 시 결과 전달로 UX를 개선했습니다.  
*(Slack Bot: 3초 간격 폴링, 최대 300초 timeout)*

---

## Slide 22 — 정확도를 높이기 위해 고민한 것들

SQL 정확도를 구조적으로 끌어올리기 위해 세 가지 전략을 사용했습니다.

**① 실행 전 4중 검증 및 가드레일**
- **AST 지능형 파싱**: sqlglot으로 SELECT 외 명령(INSERT, DROP 등) 및 테이블 접근 원천 차단  
*(sql_validator.py: BLOCKED_KEYWORDS 5종 + ALLOWED_TABLES 화이트리스트)*
- **Athena EXPLAIN 검증**: 실행 전 쿼리 플랜 무료 분석으로 문법 오류 및 풀스캔 사전 차단  
*(SQLValidator 클래스: 30초 timeout으로 EXPLAIN 실행)*
- **SQL 가드레일**: 결과 행수 최대 1,000행 제한(LIMIT) 강제 적용  
*(DEFAULT_LIMIT = 1000)*
- **Self-Correction**: 검증 실패 시 에러 사유를 LLM에 피드백 → 최대 3회 자동 수정 루프

**② LLM의 '사고 절차' 프롬프트 설계**
- **CoT(Chain of Thought)**: DDL 확인 → 테이블 선택 → 파티션 변환 → 집계 설계까지 6단계 사고 절차 강제  
*(sql_generator.yaml: cot_template에 6단계 명시)*
- **프롬프트 인젝션 방지**: 시스템 지시문과 외부 데이터(RAG Context)를 별도 Content Block으로 완전 분리

**③ RAG에 '도메인 Context 주입'**
- **Athena 문법 최적화**: DATE(), BETWEEN 등 성능 저해 함수 차단 및 Presto 전용 구문 21종 지식화  
*(negative_rules: 21개 금지사항 명시)*
- **비즈니스 로직 규격화**: CTR·CVR·ROAS 등 광고 지표 계산 공식 5종 사전 정의 및 시딩  
*(table_selection_rules: 지표별 계산 공식 표준화)*
- **Few-shot 기반 패턴 학습**: '어제', '지난주' 등 시간 표현 변환 70여 개 Golden QA 데이터셋 구축
- **오답 패턴 사전 보정**: 과거 실패 사례 8종을 역으로 학습시켜 hallucination 사전 억제

---

## Slide 23 — SQL 정확도 4라운드 개선 스토리

단순한 튜닝이 아니라, 매 라운드마다 "왜 틀렸는가"를 깊이 파고든 결과입니다.

> **Exec (Execution Accuracy)**: 생성된 SQL의 실행 결과값이 정답과 일치하는가

| 라운드 | 정확도 | 핵심 개선 내용 |
|--------|--------|---------------|
| **Round 1** | **33.3%** | QA 시딩 편향성 해결(21개) 및 날짜 동적 처리(Jinja2) 도입으로 기초 정확도 확보 |
| **Round 2** | **36.1%** | CoT 6단계 프롬프트, Negative Rules, 계산식 공식화로 생성 로직 안정성 강화 |
| **Round 3** | **69.4%** | 한국어 특화 임베딩(ko-sroberta) 도입 및 Reranker 제거로 검색 효율 극대화 |
| **Round 4** | **80.6%** | QA 메타데이터 기반 DDL 동적 주입으로 테이블 오인식 한계 극복 → 80%대 진입 |

33%에서 시작해 **80%까지 끌어올렸습니다.**

---

## Slide 24 — 실시간 광고 이상 탐지 및 Slack 알림

저희는 **Prophet과 Isolation Forest 앙상블 모델**을 사용합니다.

| 모델 | 역할 |
|------|------|
| **Prophet** | 시계열 데이터의 추세를 학습해 정상 범위(신뢰구간)를 예측  
*(ProphetDetector: Facebook Prophet 기반, 계절성/트렌드 고려)*
| **Isolation Forest** | 단기적인 급변 값을 빠르게 탐지  
*(IsolationForestDetector: sklearn.ensemble.IsolationForest, -1~1 스코어)*

두 모델의 장점을 결합해 **복합적인 이상 징후를 누락 없이 감지**합니다.  
*(앙상블 로직: Prophet 이상 + Isolation Forest 이상 = 최종 이상 판정)*

Airflow가 **5분 주기**로 최신 로그를 분석하고, 이상이 발견되면 즉시 Slack으로 알림을 보냅니다. 현업에서는 이상 발생 후 15분 이내 대응을 권고하고 있는데, 저희 시스템은 이를 충족합니다.  
*(DAG: capa-impression, capa-click, capa-conversion — 각 이벤트별 독립 실행)*

---

## Slide 25 — 인프라 코드화 + 트래픽 대응 (Terraform + EKS + Karpenter)

저희 인프라는 세 가지 핵심 기술로 구성됩니다.

**Terraform (IaC)**  
인프라 전체를 코드로 관리합니다. 클러스터 및 의존성 리소스를 **단 25분 만에 완전 배포**할 수 있으며 환경 재현성 100%를 보장합니다.  
*(총 15개 .tf 파일: VPC, EKS, Kinesis, S3, Athena, ECR 등 완전 IaC화)*

**Amazon EKS**  
안정적인 컨테이너 환경을 구축하여 마이크로서비스 아키텍처(MSA) 기반의 유연한 확장성을 제공합니다.  
*(Helm Charts: 8개 서비스 배포, IRSA로 AWS 권한 안전 관리)*

**Karpenter**  
트래픽 스파이크 발생 시 기존 Cluster Autoscaler 대비 압도적으로 빠른 속도로 노드를 프로비저닝합니다. Spot 인스턴스를 적극 활용하고 유휴 리소스를 최소화하여 **인프라 비용을 최대 70% 절감**합니다.  
*(15-karpenter.tf: NodePool × 3개, EC2 Fleet 직접 관리, SQS Interruption Queue)*

---

## Slide 26 — 핵심 기술 스택

| 레이어 | 기술 | 역할 |
|--------|------|------|
| LLM | Claude 3.5 Haiku | 자연어 이해 및 SQL 생성 (평균 2-5초 응답) |
| Text-to-SQL 엔진 | Vanna AI | 파이프라인 추상화 및 학습 (11단계 파이프라인) |
| 벡터 DB | ChromaDB | RAG 지식 베이스 (ko-sroberta 임베딩, 70개 QA 시딩) |
| 스트리밍 | Kinesis Data Streams | 실시간 로그 수집 (3개 스트림 × 2샤드 = 6샤드) |
| 저장소 | Amazon S3 | 데이터 레이크 (Parquet) (월간 1.2TB 예상) |
| 쿼리 엔진 | Amazon Athena | 서버리스 대용량 쿼리 (쿼리당 평균 2-5초) |
| 워크플로우 | Apache Airflow | 배치 자동화 (8개 DAG, KubernetesPodOperator) |
| 플랫폼 | Amazon EKS | 컨테이너 오케스트레이션 (Helm Charts × 8개) |
| 오토스케일러 | Karpenter | 노드 자동 스케일링 (NodePool × 3개, Spot 최적화) |
| IaC | Terraform | 인프라 코드 관리 (15개 .tf 파일) |
| BI | Redash | 대시보드 및 시각화 (쿼리 기반 파라미터 지원) |
| ML 이상 탐지 | Prophet + Isolation Forest | 앙상블 이상 탐지 (5분 주기 실시간) |
| 인터페이스 | Slack | 챗봇 및 알림 (비동기 폴링, 3초 간격) |
| 히스토리 DB | DynamoDB | 멀티턴 대화 이력 (TTL 24시간, 5턴 저장) |
| 모니터링 | CloudWatch | 실시간 지표 추적 (Kinesis 모니터링) |

---

## Slide 27 — 왜 이 기술인가: 채택 근거

각 기술의 핵심 채택 사유를 한 줄로 정리했습니다.

| 기술 | 채택 사유 |
|------|----------|
| Claude Haiku | 우수한 코드 작성 능력 및 높은 가성비 (SQL 생성 정확도 80.6%) |
| Vanna AI | Text-to-SQL 파이프라인 추상화 및 학습 용이성 (11단계 파이프라인 지원) |
| ChromaDB | ko-sroberta 임베딩 모델 정합성 및 Vanna 호환성 (한국어 특화) |
| Prophet + I-Forest | 계절성+통계 앙상블로 오탐 최소화 (5분 주기 실시간 감지) |
| Kinesis + Firehose | 서버리스 기반 실시간 적재 및 Parquet 변환 (3개 스트림 분리) |
| Amazon Athena | 서버 운영 없는 즉시 쿼리 및 S3 완벽 호환 (쿼리당 2-5초) |
| Karpenter | 초고속 노드/파드 탄력적 관리 및 비용 절감 (Spot 70% 절감) |
| DynamoDB | 멀티턴 대화 이력 고속 조회 및 프리티어 활용 (TTL 24시간) |

---

## Slide 28 — SECTION 04: 결론 및 회고

---

## Slide 29 — AS-IS vs TO-BE: 도입 전후 비교

| 항목 | AS-IS (과거) | TO-BE (현재, CAPA) |
|------|-------------|-------------------|
| **데이터 조회** | 데이터팀 요청 후 수 시간~수 일 대기, 의사결정 타이밍 지연 | Slack 자연어 질문 → 수십 초 내 즉시 답변 및 시각화 |
| **정기 리포트** | 담당자가 수기 엑셀 다운로드 및 집계, 반복 리소스 낭비 | Airflow 완전 자동화, 정해진 시간에 Slack 자동 전송 |
| **이상 탐지** | 사람이 대시보드를 볼 때만 인지, 사후 발견으로 예산 낭비 | AI 모델이 5분 주기 실시간 감지, 이상 발생 즉시 Slack 알림 |
| **대시보드** | 지표 확인마다 데이터팀 요청 반복, 실시간 셀프 확인 불가 | Redash 원클릭 셀프 확인, SQL 없이 언제든 실시간 조회 |

> **데이터 추출 업무 소요 시간 99% 단축 (반나절 → 1분 이내)**

---

## Slide 30 — 시행착오 & 배운 점

#### 인프라 & AI 엔진

**EKS 노드 그룹 분리 실패 → Karpenter로 해결**  
동일 노드 내 Airflow 워커의 과부하 작업으로 OOM(Out of Memory)이 발생하여 서버가 다운되었습니다.  
→ Karpenter를 도입하여 작업 특성별로 노드를 분리 프로비저닝하여 해결했습니다.  
*(결과: NodePool × 3개 분리, EC2 Fleet 직접 관리)*

**Reranker 도입 후 롤백**  
Reranker 도입으로 정확도 개선을 기대했으나, 정확도는 오르지 않고 **50초 이상의 지연 시간**이 발생해 UX를 해쳤습니다.  
→ 사용 테이블이 2개뿐이라 Reranker는 오버엔지니어링이었습니다. 롤백하고 ChromaDB 메타데이터 필터링 고도화 방향으로 선회했습니다.  
*(결과: RAG Retriever에서 LLM_FILTER_ENABLED 환경변수로 제어)*

#### 데이터 수집 & 시각화

**데이터 파이프라인 연결 방식**  
생성된 Raw 데이터가 하나의 파이프로만 연결되었으나, Impression/Click/Conversion 각 데이터 특성에 맞게 개별 파이프라인으로 분리해야 함을 인지했습니다.  
*(결과: Kinesis 3개 스트림 분리, 각 이벤트별 독립 처리)*

**Redash 거리감**  
국내 자료가 부족하여 Redash 진입 장벽이 발생했습니다. 인터페이스를 숙지하고 임의의 대시보드를 수차례 생성하며 극복했습니다.  
*(결과: 쿼리 기반 파라미터 지원 활용, {{ 변수명 }} Jinja2 문법 적용)*

**Redash 쿼리 파라미터**  
Redash에서 들어오는 쿼리 파라미터를 문자열로 취급하는 문제가 있었습니다. 쿼리 파라미터 기능과 쿼리 내 설정으로 해결했습니다.  
*(결과: Athena 쿼리에 직접 파라미터 바인딩)*

#### 실시간 이상치 탐지

**신뢰구간 상단 가중치 부여**  
신뢰구간 상단이 비즈니스 맥락 없이 모델 예측값만으로 결정되고 있었습니다.  
→ 데이터 특성별 가중치 차등 적용 (Impression × 1.25, Click × 1.5)으로 해결했습니다.  
*(결과: models.py에서 ProphetDetector 신뢰구간 조정)*

**Prophet 신뢰구간 음수 발생**  
트래픽이 적은 시간대에 신뢰구간 하한이 음수로 예측되었습니다.  
→ 하한을 0으로 보정하여 비현실적 상황을 제거했습니다.  
*(결과: config.py에서 LOWER_BOUND = 0 설정)*

**CloudWatch 집계 처리 시간 딜레이**  
즉시 조회 시 집계가 완료되지 않아 수집 시점에 따라 데이터가 누락될 수 있었습니다.  
→ 2분의 버퍼를 두어 데이터를 안정적으로 수집합니다.  
*(결과: FiveMinuteAggregator에서 buffer_minutes = 2 적용)*

**공통 교훈**: 완벽한 설계보다 빠른 실패와 피드백이 낫습니다.

---

## Slide 31 — 향후 발전 방향 (Future Work)

저희는 데이터 조회와 이상 탐지를 넘어, **데이터 기반의 즉각적인 행동과 최적화**를 목표로 합니다.

**① 역질문 봇**  
모호한 질문에 AI가 스스로 되물어 SQL 정확도를 높입니다.  
예: "지난주"가 월~일 기준인지, 7일 기준인지 명확히 확인하는 방식

**② Slack 액션**  
데이터 조회 후 즉시 행동할 수 있도록 합니다.  
예: 보고서 하단에 "효율 저하 캠페인 즉시 Off" 버튼 → 관리자 콘솔 없이 광고 송출 중단

**③ 정량 평가 시스템 고도화**  
Spider 벤치마크 기반으로 정확도를 지속적으로 측정하고, RAG 개선 루프를 완성합니다.

결국, **데이터를 조회하는 것을 넘어 데이터로 즉시 행동하는 시스템**을 만드는 것이 저희의 비전입니다.

---

## Slide 32 — 참고 자료 및 출처

| 내용 | 출처 | URL |
|------|------|-----|
| 데이터 접근성·생산성 저하 | IAB/BWG State of Data 2026 (Martech.org 인용) | https://martech.org/75-of-marketers-say-their-measurement-systems-are-falling-short/ |
| 기업 데이터 68% 방치 | Seagate & IDC Report 2020 | — |
| 분석팀 병목 | Instawork: Analytics in the Age of AI | — |
| 국내 사례 (우아한형제들) | 배달의민족 BADA팀 기술 블로그 | https://techblog.woowahan.com/18144/ |
| 국내 사례 (SK Planet) | T Academy | https://tacademy.skplanet.com/front/centernews/viewCenterNews.do?seq=538 |
| 국내 사례 (데이블) | 데이블 기술 블로그 | https://dabletech.oopy.io/2ce5bbc0-e5c2-8089-9dcd-c449b51eba46 |

---

## Slide 33 — Q&A

이제 질의응답 시간입니다.

오늘 발표를 경청해 주셔서 진심으로 감사합니다.

저희 CAPA 팀은 "비개발자도 자연어로 데이터에 질문할 수 있는 환경"을 만들었습니다. 데이터를 필요로 하는 사람과 접근할 수 있는 사람 사이의 격차를 해소하는 것, 그것이 CAPA의 역할입니다.

궁금한 점이 있으시면 편하게 질문해 주십시오.
