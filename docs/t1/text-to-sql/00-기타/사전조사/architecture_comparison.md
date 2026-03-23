# CAPA 아키텍처 vs 참고 사례 비교

> **작성일**: 2026-03-06  
> **결론**: 현재 CAPA 아키텍처는 참고 문서와 호환되며 그대로 사용 가능

---

## 핵심 결론

> **아키텍처 변경 불필요. 차이는 인프라가 아닌 앱 로직 레벨에 있다.**

---

## 1. 컴포넌트별 비교

| 컴포넌트 | DableTalk | InsightLens | CAPA |
|---------|-----------|------------|------|
| **인터페이스** | Slack Bot + Streamlit | Jira + API | Slack Bot ✅ |
| **Text-to-SQL** | Vanna AI | LangGraph 에이전트 | Vanna AI ✅ |
| **Vector DB** | ChromaDB | Vector Store | ChromaDB ✅ |
| **LLM** | Gemini 2.5 Pro | Claude/OpenAI | Claude ✅ |
| **Query Engine** | Trino | RDB | **Athena** (차이있음→하단 설명) |
| **오케스트레이션** | K8s (ECR) | - | EKS + Helm ✅ |
| **배치** | - | - | Airflow ✅ |

---

## 2. Query Engine 차이: Trino vs Athena

```
DableTalk: Trino      (자체 클러스터 운영 필요)
CAPA:      Athena     (Serverless, 운영 부담 없음)
```

**Athena가 오히려 유리한 이유**:
- Serverless → 클러스터 유지 비용/운영 없음
- S3 + Parquet과 네이티브 궁합
- 파티션 pruning 동일하게 지원
- SQL 문법 사실상 동일 (Presto 기반)

→ **아키텍처 변경 필요 없음**

---

## 3. Vanna AI vs LangGraph 에이전트

InsightLens는 9단계 에이전트를 **직접 구현**했지만,  
CAPA는 Vanna AI가 이 과정을 **내부적으로 추상화**합니다.

```
InsightLens 방식 (직접 구현):
  질문 정제 → 키워드 추출 → RAG 검색 → SQL 생성 → 검증

CAPA(Vanna AI) 방식 (추상화):
  generate_sql() 한 번 호출 → Vanna 내부에서 RAG + LLM 처리
```

**Vanna가 해주지 않아서 직접 추가해야 할 것**:

| 기능 | 참고 사례 | CAPA 대응 |
|------|---------|---------|
| 의도 분류 | InsightLens 핵심 | Phase 3에서 직접 구현 |
| SQL EXPLAIN 검증 | DableTalk 핵심 | Phase 2에서 직접 구현 |
| 질문 정제 | InsightLens 핵심 | Phase 3에서 직접 구현 |

→ **아키텍처 차이가 아닌, 앱 로직 레벨 추가 구현 사항**  
→ **구현 계획서([implementation_plan.md](./implementation_plan.md))의 Phase 2~3 참고**

---

## 4. CAPA 인프라 구성 (현재)

```
[Data Generation]  Log Generator
      ↓
[Streaming]        Kinesis Stream → Kinesis Firehose
      ↓
[Storage]          S3 (Parquet)
      ↓
[Processing]       Glue Catalog → Athena
      ↓
[EKS Cluster]
  ├── Airflow       (배치 스케줄링)
  ├── Vanna API     (Text-to-SQL)
  ├── ChromaDB      (RAG 벡터 저장소)
  ├── Redash        (KPI 대시보드)
  └── Slack Bot     (사용자 인터페이스)
      ↓
[Alert]            CloudWatch Alarms → SNS → Slack
```

이 구조는 참고 사례들의 아키텍처와 동일한 방향이며,  
단일 `terraform apply`로 전체 인프라 + 앱이 배포됩니다.

---

## 관련 문서

- [참고 자료 요약](./reference_summary.md)
- [구현 계획서](./implementation_plan.md)
- [DevOps 구현 가이드](../devops/devops_implementation_guide.md)
