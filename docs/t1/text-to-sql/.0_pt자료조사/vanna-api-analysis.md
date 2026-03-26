# Vanna AI API - QueryPipeline 아키텍처 및 흐름 분석 보고서

본 문서는 `vanna-api` 서비스의 최신 아키텍처와 11단계 QueryPipeline의 상세 흐름, 각 단계별 입력/출력값 및 주요 기능을 정리한 조사 자료입니다.

## 1. 프로젝트 전체 흐름도 (QueryPipeline)

사용자의 자연어 질문이 입력되면 아래의 11단계 파이프라인을 거쳐 최종 분석 결과와 차트가 생성됩니다. 모든 상태 데이터는 `PipelineContext` 객체를 통해 관리됩니다.

| 단계 | 컴포넌트명 | 주요 기능 및 특징 | 입력값 (Input) | 출력값 (Output) | 사용 파일 / 프롬프트 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Step 0** | **Conversation Retriever** | 멀티턴 대화 맥락을 위해 DynamoDB에서 이전 대화 내용을 호출 | `session_id`, `question` | `conversation_history` | `conversation_history_retriever.py` |
| **Step 1** | **Intent Classifier** | 광고 데이터 분석/일반 질문/범위 외 질문 여부 분류 | `question` | `IntentType` (3종) | `intent_classifier.yaml` |
| **Step 2** | **Question Refiner** | 인사말 제거 및 핵심 데이터 지표 추출(지표 키워드 보존) | `question`, `history` | `refined_question` | `question_refiner.yaml` |
| **Step 3** | **Keyword Extractor** | SQL 생성 및 RAG 검색을 위한 도메인 핵심 키워드 추출 | `refined_question` | `keywords` (List) | `keyword_extractor.py` |
| **Step 4** | **RAG Retriever** | ChromaDB에서 DDL, 문서, Few-shot SQL 예제를 검색 | `refined_q`, `keywords` | `rag_context` | `rag_retriever.py`, `seed_chromadb.py` |
| **Step 5** | **SQL Generator** | Claude LLM과 CoT(Chain-of-Thought)로 Athena SQL 생성 | `refined_q`, `rag_context` | `generated_sql` | `sql_generator.yaml` |
| **Step 6** | **SQL Validator** | AST 분석 및 `EXPLAIN`을 통한 문법/보안/정책 검증 | `generated_sql` | `validation_result` | `sql_validator.py` |
| **Step 6.5**| **Self-Correction** | 검증 실패 시 에러 피드백을 기반으로 SQL 자동 재생성 | `sql`, `error_msg` | `fixed_sql` (Max 3회) | `query_pipeline.py` (Loop) |
| **Step 7~9**| **Query Execution** | Redash API 경유(또는 Athena 직접) 실행 및 결과 수집 | `validated_sql` | `rows`, `columns` | `redash_client.py` |
| **Step 10** | **AI Analyzer** | 결과 데이터 분석, 인사이트 도출 및 차트 유형 결정 | `question`, `results` | `answer`, `chart_type` | `ai_analyzer.yaml` |
| **Step 10.5**| **Chart Renderer** | `matplotlib`을 이용해 차트 이미지 생성 및 Base64 변환 | `results`, `chart_type` | `chart_base64` | `chart_renderer.py` |
| **Step 11** | **History Recorder** | 전체 트랜잭션을 DynamoDB/JSONL에 최종 기록 | `PipelineContext` | `history_id` | `dynamodb_history.py` |

---

## 2. 주요 구성 요소 상세 내역

### 2.1 프롬프트 엔진 (`prompts/`)
각 단계별 LLM의 행동 지침을 YAML 형식으로 엄격하게 관리하여 정밀한 제어를 수행합니다.

- **`sql_generator.yaml`**: 
  - **Athena 전용 규칙**: 풀 스캔 방지를 위한 날짜 파티션(`year`, `month`, `day`) 필수 조건 명시.
  - **Negative Constraints**: 21가지 이상의 금지 사항(BETWEEN 금지, OFFSET 금지 등) 정의.
  - **지표 공식**: CTR, CVR, ROAS, CPA, CPC에 대한 표준 계산식 포함.
- **`question_refiner.yaml`**: 사용자의 비정형 질문을 지표 중심의 간결한 문장으로 변환.
- **`intent_classifier.yaml`**: 도메인 범위(Ad-tech)를 벗어난 질문을 사전에 차단.
- **`ai_analyzer.yaml`**: 데이터 성격(시계열, 비교, 비율 등)에 따른 최적의 시각화 전략 수립.

### 2.2 지식베이스 및 시딩 (`seed_chromadb.py`)
RAG의 성능을 위해 ChromaDB 컬렉션에 전문 지식을 주입하는 핵심 스크립트입니다.

- **데이터 구성**:
    - **DDL**: `ad_combined_log`(시간 단위 로그), `ad_combined_log_summary`(일간 요약) 2종.
    - **Documentation**: 비즈니스 메트릭 정의, 보안 정책, Athena 함수 가이드.
    - **QA Pairs**: 70개 이상의 실제 광고 분석 질문과 검증된 SQL 쌍(Few-shot).
- **최적화**: Vanna 기본 임베딩 방식을 오버라이드하여 `cosine` 유사도 메트릭을 적용, 검색 정확도 향상.

### 2.3 시스템 아키텍처 특징
- **Async Query 모드**: 대용량 쿼리 처리를 위해 BackgroundTasks 기반의 비동기 실행 및 폴링 지원.
- **Table Selection Logic**: `hour` 분석 시 로그 테이블, 전환 분석 시 요약 테이블을 자동 선택하는 하이브리드 전략.
- **Human-in-the-Loop**: Slack 피드백 버튼을 통해 긍정적인 SQL을 즉시 학습 데이터(QA pair)로 반영하는 실시간 개선 프로세스.

---

## 3. 주요 로직 상세 (Table Selection Logic)

시스템이 자연어 질문으로부터 적절한 Athena 테이블(로그 vs 요약)을 선택하는 로직은 **프롬프트 가이드**와 **동적 컨텍스트 주입**의 결합으로 구현되어 있습니다.

### 3.1 프롬프트 기반 추론 규칙 (`sql_generator.yaml`)
LLM(Claude)이 질문의 의도를 분석하여 테이블을 결정하도록 명시적인 규칙을 제공합니다.
- **`ad_combined_log` (로그 테이블) 선택 조건**:
    - '시간대별(hour)', '피크타임', '시간별', 'hourly' 등의 시간 세분화 키워드 포함 시.
- **`ad_combined_log_summary` (요약 테이블) 선택 조건**:
    - '전환(conversion)', 'CVR', 'ROAS', 'CPA', '전환율/수/매출' 등 성과 지표 포함 시.
    - 지표 컬럼(is_conversion, conversion_value 등)은 해당 테이블에만 존재함을 명시.
- **기본값**: 성능 최적화를 위해 위 조건이 없을 경우 기본적으로 일별 집계에 최적화된 요약 테이블을 사용하도록 유도.

### 3.2 Dynamic DDL Injection (`rag_retriever.py`)
RAG 검색 시 질문과 가장 유사한 과거 쿼리 예시(QA Pair)를 기반으로 컨텍스트를 제한하여 LLM의 실수를 방지합니다.
- **구현 방식 (Metadata Backtracking)**:
    1. 질문과 유사한 과거 QA Pair를 ChromaDB에서 먼저 검색.
    2. 각 QA Pair의 메타데이터(`metadata['tables']`)에서 실제로 사용된 테이블 목록을 추출.
    3. 추출된 테이블과 일치하는 DDL 정보만 프롬프트에 주입하여 LLM이 엉뚱한 테이블을 참조할 여지를 차단.
    4. 참조할 데이터가 없는 경우에만 두 테이블의 DDL을 모두 제공하여 하이브리드 선택을 유도.
