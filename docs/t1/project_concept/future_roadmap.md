# CAPA 확장 로드맵

> **문서 목적**: AI 기능 고도화 및 확장 계획  
> **대상**: 기술 리드, ML 팀  
> **참조**: [프로젝트 컨셉 문서](./project_concept_v4.md)

---

## 확장 기술 우선순위

| 순위 | 기술 | 난이도 | 임팩트 | 추천 이유 |
|:----:|------|:------:|:------:|-----------| 
| 1 | **LLM-as-a-Judge** | 낮음 | 높음 | 구현 쉽고 즉시 품질 향상 |
| 2 | **RALF Loop** | 중간 | 높음 | 사용자 피드백으로 지속 개선 |
| 3 | **dbt** | 중간 | 높음 | Text-to-SQL 정확도 + 쿼리 성능 |
| 4 | **DSPy** | 중간 | 중간 | 프롬프트 최적화 자동화 |
| 5 | **ML 이상 탐지** | 중간 | 중간 | Alert 정확도 향상 |
| 6 | **RLAIF** | 높음 | 높음 | 자동 학습 루프 |
| 7 | **A2A** | 높음 | 중간 | 복잡한 질문에만 필요 |

---

## 1. LLM-as-a-Judge (Priority 1)

### 개념

Vanna AI가 생성한 SQL을 **또 다른 LLM이 검증**.

### 플로우

```
User: "어제 캠페인별 CTR"
  ↓
Vanna AI: SQL 생성
  ↓
LLM-as-a-Judge: SQL 검증
  - 문법 오류 체크
  - 로직 검증 (CTR = clicks / impressions)
  - 안전성 체크 (SELECT만 허용)
  ↓
Score ≥ 8/10 → 실행
Score < 8 → 재생성 또는 에러 반환
```

### 구현

```python
def judge_sql(sql: str, question: str) -> dict:
    prompt = f"""
    다음 SQL이 질문에 정확하게 답하는지 평가하세요.
    
    질문: {question}
    SQL: {sql}
    
    평가 기준:
    1. 문법 정확성
    2. 로직 정확성
    3. 효율성
    
    점수: 1-10
    피드백: (문제점 및 개선 제안)
    """
    
    response = llm.complete(prompt)
    return {
        'score': extract_score(response),
        'feedback': extract_feedback(response)
    }
```

---

## 2. RALF Loop (RAG + Feedback)

### 개념

사용자 피드백을 RAG 학습 데이터로 자동 수집.

### 플로우

```
User: "어제 CTR top 5"
  ↓
CAPA: [결과] + [SQL]
  ↓
User: 👍 (좋아요) or 👎 (싫어요)
  ↓
👍 → ChromaDB에 (질문, SQL) 저장 (자동 학습)
👎 → 피드백 수집 → 개선 후 재학습
```

### 구현

```python
@app.event("reaction_added")
def handle_reaction(event):
    if event['reaction'] == 'thumbsup':
        # 좋은 예시로 학습
        vn.train(
            question=event['message']['question'],
            sql=event['message']['sql']
        )
    elif event['reaction'] == 'thumbsdown':
        # 피드백 수집
        collect_feedback(event['message'])
```

---

## 3. DSPy (Prompt Optimization)

### 개념

프롬프트를 수동으로 작성하지 않고, 파이프라인을 정의하면 자동으로 최적화.

### 예시

```python
import dspy

class TextToSQL(dspy.Module):
    def __init__(self):
        self.generate_sql = dspy.ChainOfThought("question, schema -> sql")
        self.validate_sql = dspy.Predict("sql, schema -> is_valid, feedback")
    
    def forward(self, question, schema):
        sql = self.generate_sql(question=question, schema=schema)
        validation = self.validate_sql(sql=sql.sql, schema=schema)
        
        if not validation.is_valid:
            sql = self.generate_sql(
                question=question,
                schema=schema,
                feedback=validation.feedback
            )
        return sql

# 자동 최적화
optimizer = dspy.BootstrapFewShot(metric=sql_correctness)
compiled_model = optimizer.compile(TextToSQL(), trainset=examples)
```

---

## 4. RLAIF (Reinforcement Learning from AI Feedback)

### 개념

사람 피드백 대신 **AI가 AI를 평가**하여 자동 학습.

### 플로우

```
1. Vanna AI가 SQL 생성
  ↓
2. LLM-as-a-Judge가 평가 (0-10점)
  ↓
3. 점수를 reward로 사용
  ↓
4. RL 알고리즘으로 모델 업데이트
```

### 장점

- 사람 피드백 불필요 → 빠른 iteration
- 대규모 학습 가능

---

## 5. A2A (Agent-to-Agent)

### 개념

복잡한 질문을 **여러 에이전트가 협업**하여 해결.

### 예시

```
User: "지난 분기 대비 CTR이 증가한 캠페인의 공통점과 개선 제안"

Agent 1 (Data Analyst):
  → SQL 생성 및 실행 (분기별 CTR 비교)

Agent 2 (Pattern Analyzer):
  → 증가 캠페인의 공통 패턴 분석

Agent 3 (Recommender):
  → 개선 제안 생성

Final Report: 통합 결과 제공
```

---

## 6. ML 기반 이상 탐지 (Alert 고도화)

### 옵션 A: Isolation Forest

SageMaker Endpoint로 배포:

```python
def detect_anomaly_ml(current_metrics):
    sagemaker = boto3.client('sagemaker-runtime')
    
    response = sagemaker.invoke_endpoint(
        EndpointName='capa-anomaly-detector',
        ContentType='application/json',
        Body=json.dumps({
            'impressions': current_metrics['impressions'],
            'clicks': current_metrics['clicks'],
            'conversions': current_metrics['conversions']
        })
    )
    
    result = json.loads(response['Body'].read())
    return result['is_anomaly']
```

### 옵션 B: Amazon Lookout for Metrics

AWS 완전관리형 이상 탐지. 별도 모델 학습 없이 자동 감지.

### 비교

| 방식 | 장점 | 단점 | 추천 상황 |
|------|------|------|-----------|
| CloudWatch | 간단, 저비용 | 단순 패턴만 | MVP |
| SageMaker + ML | 복잡 패턴 | 모델 관리 | 고도화 |
| Lookout for Metrics | 완전관리형 | 비용 높음 | 운영 리소스 부족 시 |

---

## 7. dbt (Data Build Tool)

### Text-to-SQL 관점에서의 이점

| 이유 | 설명 |
|------|------|
| **정확도 향상** | 잘 정리된 Mart 테이블 → LLM이 이해하기 쉬움 |
| **성능 개선** | 미리 집계 → Athena 스캔 비용 감소 |
| **품질 테스트** | not_null, unique 테스트 → 리포트 신뢰성 |
| **로직 표준화** | CTR, CVR 계산을 한 곳에서 관리 |

### 도입 시점

- **1단계 (MVP)**: dbt 없이 원본 테이블 쿼리
- **2단계 (정확도 이슈 발생 시)**: dbt로 Mart 레이어 추가
- **3단계 (테이블 10개+)**: 전체 데이터 모델 dbt 관리

---

## 통합 아키텍처 (Enhanced AI Layer v2)

```
User Question
    ↓
[RALF Loop] - 피드백 수집
    ↓
[DSPy] - 프롬프트 자동 최적화
    ↓
[Vanna AI] - SQL 생성
    ↓
[LLM-as-a-Judge] - SQL 검증
    ↓
Pass → Athena 실행
Fail → 재생성 또는 A2A로 에스컬레이션
    ↓
Result + SQL (투명성)
    ↓
[User Reaction] → RALF Loop 피드백
```

---

## 구현 순서 (권장)

### Phase 1: 기본 품질 향상 (1-2주)
1. LLM-as-a-Judge 구현
2. RALF Loop 기본 (👍/👎 수집)

### Phase 2: 자동화 (2-3주)
3. dbt Mart 레이어 구축
4. DSPy 기본 적용

### Phase 3: 고도화 (4주+)
5. RLAIF 자동 학습
6. ML 기반 이상 탐지
7. A2A (필요시)

---

**문서 끝**
