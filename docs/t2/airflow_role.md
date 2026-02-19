Airflow의 역할 (CAPA 프로젝트 적용)
- 목적: 배치 ETL 파이프라인의 스케줄링·오케스트레이션 — 주기적으로 분석용 데이터(SQL 기반)를 생성하고 S3에 적재하도록 관리.
- 데이터 흐름 관점: log-generator(또는 Kinesis 등) → 원시로그 저장소(S3 / Kinesis) → Airflow DAG(배치) → Python + SQL 실행(AWS Athena) → 결과 파일 S3 저장 → AWS Glue Tables로 스키마/메타데이터 제공
- DAG 책임: 입력 데이터 유효성 확인 → Athena SQL 쿼리(혹은 CTAS) 실행 → 쿼리 결과를 Parquet/CSV 등으로 S3에 저장 → Glue 메타데이터(테이블/파티션) 업데이트 → 후속 태스크(리포트·시각화) 트리거
- SQL 우선 원칙: 변환은 SQL 기반을 기본으로 구현(성능·표준성). 복잡한 로직이나 예외 처리는 Pandas/Polars를 예외적으로 사용(작은 데이터 또는 SQL로 표현하기 어려운 경우).
실행 방식: Airflow는 PythonOperator 또는 AWSAthenaOperator(또는 boto3/pyathena 사용한 PythonOperator)로 SQL 실행, 쿼리 완료 대기 후 결과 저장 처리 수행.
- 스키마 관리: 데이터 스키마는 AWS Glue Tables 집합으로 정의 — Athena 쿼리는 Glue 메타데이터를 참조하므로 ETL 결과는 Glue 스키마/파티션 규약에 맞춰 적재해야 함(타입·파티션 포맷 일치).
- 파티셔닝 & 증분 처리: 날짜/시간 기준 파티셔닝 전략 적용(예: ds=YYYY-MM-DD). Airflow 태스크에서 파티션 생성/등록(MSCK REPAIR TABLE 또는 Glue API) 수행.
- 내구성 & 운영: 재시도 정책, 실패 알림(메일/Slack), 태스크 타임아웃 설정, 로그 보존(S3/CloudWatch)으로 운영성 확보.
- 인프라·스케일링: Helm으로 EKS에 배포하여 KubernetesExecutor로 동적 워커 확장 — 대규모 Athena/병렬 쿼리 관리 가능.
- 데이터 품질: 스키마 검증(컬럼·타입), 행수/요약 통계 검증, 스모크 테스트 등을 DAG 내에서 자동화.
- Idempotency(안정성): 동일 DAG 반복 실행 시 중복 적재 방지(임시 테이블 → 원자적 교체 또는 파티션 레벨 쓰기) 전략 적용.
- 운영예시(간단한 DAG 순서):
    - check_raw_logs : S3/Kinesis에 데이터 존재 확인 (Sensor)
    - athena_transform : SQL로 변환(CTAS → S3/Parquet)
    - validate_schema : 결과 스키마/레코드 체크 (Python)
    - register_partition : Glue 파티션 등록/업데이트
    - generate_report : 요약/리포트 생성(옵션: Pandas/Polars)
    - notify : 성공/실패 알림
- 요약: 본 프로젝트에서 Airflow는 "로그를 생성하지 않는" 배치 스케줄러이자 오케스트레이터로서, SQL 우선(예외적으로 Pandas/Polars 허용)으로 Athena에 쿼리를 실행해 S3에 분석용 데이터를 적재하고 Glue 테이블(스키마)을 유지·관리하는 중심 엔진입니다. 추가로 예시 DAG나 Operator 구현을 원하면 바로 만들어 드리겠습니다.