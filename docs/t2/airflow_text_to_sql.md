# Airflow: Text-to-SQL (TTS) 파이프라인 가이드

## 목적
- 자연어(사용자 질의)를 SQL로 변환하여 분석용 쿼리를 자동 생성하고 실행하는 배치 파이프라인을 Airflow로 운영하기 위한 설계·운영 가이드입니다.
- 핵심 요구사항: SQL 우선(기본 변환은 SQL로), 예외적으로 `pandas`/`polars` 사용 허용, Athena + S3 + Glue 테이블 사용

## 요약 아키텍처
- 사용자 질의 입력 → Text-to-SQL 변환(모듈: LLM/Agent 또는 룰베이스) → 변환된 SQL 검증(문법·화이트리스트) → Athena로 실행 → 결과 S3 저장(Parquet) → Glue 메타데이터 갱신 → (옵션) Redash 새로고침

```mermaid
flowchart LR
  U[사용자 질의] --> TTS[Text-to-SQL 엔진]
  TTS --> V[SQL 검증 & 안전 검사]
  V --> A[Athena 실행]
  A --> S3[S3 결과 (Parquet)]
  S3 --> Glue[AWS Glue 테이블 / 파티션]
  Glue --> Redash[Redash 조회]
  subgraph Airflow
    TTS
    V
    A
    Glue
  end
```

## Airflow의 역할(요점)
- 스케줄링 및 오케스트레이션: Text-to-SQL 변환 → SQL 실행 → 결과 검증 → 메타데이터 갱신의 전 과정 관리
- 변환은 가능하면 SQL로 수행(LLM이 생성한 SQL은 검증 후 실행)
- 변환 단계는 `PythonOperator`(LLM 호출) 또는 외부 Agent SDK 사용
- SQL 실행은 `AWSAthenaOperator` 또는 `PythonOperator`(pyathena/boto3) 사용
- 안전성: SQL 화이트리스트/금지 패턴 검사, 쿼리 비용·스캔량 제한

## DAG 구성요소(권장 태스크)
1. `check_input` — 입력(예: 요청 파일 또는 메시지 큐) 존재 확인
2. `translate_text_to_sql` — LLM/Agent에 질의를 전달해 SQL 생성
3. `validate_sql` — 문법 검사, 허용된 테이블/컬럼만 사용하는지 확인, 위험 쿼리(DDL/DCL/삭제 등) 차단
4. `run_sql_athena` — Athena에 SQL 제출(CTAS/INSERT/SELECT) 및 완료 대기
5. `validate_results` — 결과 스키마·레코드·샘플 확인(비즈니스 규칙 검증)
6. `register_partition` — Glue 파티션/메타데이터 등록
7. `refresh_visuals`(선택) — Redash API 호출로 쿼리/대시보드 갱신
8. `notify` — 성공/실패 알림

## 안전·검증 규칙 (필수)
- SQL 허용 목록: 실행 가능한 테이블/스키마·허용 컬럼 목록을 관리
- 금지 패턴: `DROP`, `DELETE`, `TRUNCATE`, `ALTER`, `GRANT`, `REVOKE`, 외부 연동 호출 등 차단
- 비용 보호: 쿼리 스캔량(예: `SET query_result_cache_enabled = true` 또는 쿼리 전에 `EXPLAIN`) 체크, 쿼리 비용 초과 시 중단
- 파라미터화: 사용자 입력을 직접 SQL에 문자열 결합하지 않도록 설계(LLM이 생성한 리터럴에 주의)
- 쿼리 사이즈/시간 제한: Athena 쿼리 타임아웃 및 최대 실행 시간 설정

## Text-to-SQL(LLM) 운용 주의사항
- 프롬프트 설계: 사용 가능한 테이블/컬럼 목록을 프롬프트로 제공하고 예시 기반으로 제약을 둡니다.
- 샌드박스: LLM이 생성한 SQL은 항상 `validate_sql`을 거쳐야 하며, 가능하면 `EXPLAIN` 또는 제한된 `LIMIT`(예: 100)으로 먼저 실행
- 버전 관리: LLM 프롬프트 템플릿과 변환 규칙을 코드(또는 Git)로 버전 관리

## 예시: 간단한 Airflow DAG (스켈레톤)
아래 예시는 Text-to-SQL 변환(LLM 호출) → 검증 → Athena 실행 → Glue 파티션 등록 플로우의 골격입니다. 실제 환경에 맞게 예외처리/세부설정을 보강하세요.

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.operators.athena import AthenaOperator
from datetime import datetime, timedelta
import os, requests

DEFAULT_ARGS = {
    'owner': 'capa',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def translate_text_to_sql_func(query_text, **context):
    # 예: 내부 LLM 서비스(HTTP) 호출
    LLM_URL = os.environ.get('LOCAL_TTS_URL')
    resp = requests.post(LLM_URL, json={'text': query_text}, timeout=30)
    resp.raise_for_status()
    return resp.json().get('sql')

def validate_sql_func(sql, **context):
    # 간단 예: 금지어 검사
    forbid = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER']
    up = sql.upper()
    for f in forbid:
        if f in up:
            raise ValueError(f'Forbidden SQL token: {f}')
    # 추가: 테이블/컬럼 허용성 검사 등
    return True

with DAG(dag_id='tts_pipeline', default_args=DEFAULT_ARGS, schedule_interval='@hourly', start_date=datetime(2025,1,1), catchup=False) as dag:

    t1 = PythonOperator(
        task_id='translate_text_to_sql',
        python_callable=translate_text_to_sql_func,
        op_kwargs={'query_text': '광고 성과를 날짜별로 집계해줘'},
    )

    t2 = PythonOperator(
        task_id='validate_sql',
        python_callable=validate_sql_func,
        op_kwargs={'sql': '{{ ti.xcom_pull(task_ids="translate_text_to_sql") }}'},
    )

    athena = AthenaOperator(
        task_id='run_sql_athena',
        query='{{ ti.xcom_pull(task_ids="translate_text_to_sql") }}',
        database='analytics',
        output_location='s3://capa-bucket/athena-results/',
    )

    t1 >> t2 >> athena
```

## 운영·테스트 체크리스트
- 개발환경
  - `AIRFLOW_HOME` 설정 및 로컬 DB 초기화(airflow db init)
  - 필요한 패키지: `apache-airflow`, `boto3`, `requests`, LLM 클라이언트(필요시)
- 테스트
  - Unit: `translate_text_to_sql_func`의 다양한 입력(정상/악의적)을 검사
  - Integration: Athena(또는 로컬 mock)를 사용해 전체 DAG 테스트
  - Load: 동시 요청이 많은 경우 LLM API·Athena 쿼리 병목 시험
- 운영
  - 로그 보존: Airflow 로그 + S3 결과 보관 정책
  - 모니터링: DAG 실패/지연 알림(Slack/메일)
  - 비용 관리: Athena 스캔량, LLM 호출 비용 추적

## 배포 권장 사항
- Airflow는 EKS + Helm으로 배포하고 `KubernetesExecutor`로 워커 확장 권장
- LLM 호출은 별도 서비스(내부 마이크로서비스 또는 외부 API)로 분리해 Airflow는 orchestration에 집중
- 민감 데이터: 쿼리나 출력에 개인 식별정보(PII)가 포함될 경우 프라이버시 규칙에 따라 마스킹/비식별화

---
작성: CAPA - Airflow Text-to-SQL 가이드
