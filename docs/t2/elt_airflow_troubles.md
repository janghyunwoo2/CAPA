# Airflow에서 ETL이 실패하는 이유와 조치 체크리스트

본 문서는 “로컬에서 잘 돌던 ETL이 Airflow로 옮기면 왜 실패하는지”를 이해하기 쉽게 설명하고, 바로 적용 가능한 점검/조치 체크리스트를 제공합니다.

## 왜 Airflow에서 실패하나?
- Kubernetes 전제(KPO):
  - DAG가 기본적으로 `KubernetesPodOperator`(KPO)로 태스크를 실행하도록 구성되면, Airflow는 별도 파드를 띄우기 위해 K8s in-cluster 정보 또는 kubeconfig를 필요로 합니다.
  - 로컬(Windows/uv) 개발 환경에는 이 정보가 없어 K8s 클라이언트 초기화 단계에서 즉시 실패합니다. 로그의 `ConfigException: Invalid kube-config file` / `Service host/port is not set`가 이 증거입니다.
- 자격증명/경로 차이:
  - 로컬에서 직접 실행(uv/python)은 현재 셸의 AWS 자격증명·PYTHONPATH·작업 디렉터리를 그대로 사용합니다.
  - Airflow 태스크는 별도 프로세스/컨테이너에서 실행되므로 동일 환경이 보장되지 않습니다.
- 스케줄/시간대 차이:
  - Airflow는 논리시각(`data_interval_*`) 기반으로 템플릿을 채웁니다(예: 10분 버퍼, 전일 날짜). 논리시각/타임존 불일치 시 “존재하지 않는 파티션”을 조회해 빈 결과/오류가 납니다.
- 로깅 차이:
  - `No logs available`은 태스크가 실행 전/즉시 실패하거나(K8s 연결 실패), 로그 경로/서빙 설정이 유효하지 않을 때 흔히 발생합니다.

## 현재 레포에 적용된 해결
- 자동 폴백: K8s 환경이 아니면 자동으로 `PythonOperator` 경로를 사용하도록 DAG 4개 모두에 K8s 감지 로직을 추가했습니다.
  - `USE_KPO` 미설정 시 `KUBERNETES_SERVICE_HOST`/`KUBERNETES_PORT` 존재 여부로 K8s 환경을 감지 → 미존재면 자동 폴백.
  - 수동 제어도 가능: `USE_KPO=1|0|true|false|yes|no`.
- 수동 전용 DAG: ad_hourly_summary_test.py, ad_daily_summary_test.py 는 schedule=None 으로 수동 1회 트리거만 수행하며, 동일 Athena/파티션 로직을 로컬에서도 동작하도록 boto3 기반 실행 경로를 포함합니다.

## 실행 방법(로컬 예시)
```powershell
# (선택) 폴백 강제: K8s가 아니면 기본적으로 자동 감지되지만, 필요 시 명시
$env:USE_KPO=0
uv run --project services/data_pipeline_t2 python -m airflow scheduler
```
```powershell
- 시간별 수동: Asia/Seoul(KST) 기준으로 논리시각을 설정합니다. 예: 14:10 KST에 해당하는 데이터의 10분 버퍼를 포함하여 14:00를 대상으로 트리거합니다.
uv run --project services/data_pipeline_t2 python -m airflow dags trigger ad_hourly_summary_test -l "2026-03-04T14:10:00+09:00"

- 일별 수동: Asia/Seoul(KST) 기준으로 논리시각을 설정합니다. 예: 02:00 KST에 해당하는 데이터를 전일의 00~23시 파티션으로 처리합니다.
uv run --project services/data_pipeline_t2 python -m airflow dags trigger ad_daily_summary_test -l "2026-03-04T02:00:00+09:00"
```
- DAG 런/태스크 로그 확인:
```powershell
# 런 상태
uv run --project services/data_pipeline_t2 python -m airflow dags list-runs -d ad_hourly_summary_test -o table

# 태스크 로그
uv run --project services/data_pipeline_t2 python -m airflow tasks logs ad_hourly_summary_test create_hourly_summary "2026-03-04T14:10:00+09:00"
```

## 내가 확인/조치해야 할 체크리스트
- 환경/실행
  - [ ] (권장) 로컬 개발 시 폴백 활성화: `$env:USE_KPO=0` 또는 환경 자동 감지 확인
  - [ ] 스케줄러/워커를 최신 코드/환경으로 재기동(변경 반영)
  - [ ] 논리시각을 명시해 수동 트리거(`-l "YYYY-MM-DDThh:mm:ss+09:00"`)로 대상 시간/날짜 오동작 방지
- AWS/자격증명
  - [ ] Airflow 런타임에서 `AWS_DEFAULT_REGION` 확인(예: `ap-northeast-2`)
  - [ ] AWS 자격증명(프로파일/역할/Env)이 Airflow 런타임에서도 유효한지 확인
  - [ ] Athena 출력 경로 S3 권한(`s3:GetObject, PutObject, ListBucket`) 포함 여부 확인
- 데이터/쿼리
  - [ ] `external_location`이 가리키는 S3 경로가 비어있거나 덮어쓰기 정책에 맞는지(기존 데이터가 있으면 `HIVE_PATH_ALREADY_EXISTS`)
  - [ ] 파티션 규칙과 템플릿 일치(예: `dt=YYYY-MM-DD-HH` vs `year/month/day`)
  - [ ] 파티션 미인식 시 `MSCK REPAIR TABLE <db>.<table>` 실행
- 로깅/경로
  - [ ] Airflow 홈(`$env:AIRFLOW_HOME`) 하위 logs 폴더에 쓰기 권한/디스크 여유 확인
  - [ ] CLI로 태스크 로그 직접 조회해(`airflow tasks logs ...`) 즉시 실패/대기 상태 구분
- Kubernetes(클러스터에서 실행 시)
  - [ ] in-cluster(Helm 등)로 배포되어 있는지 확인(스케줄러/워커가 Pod로 동작)
  - [ ] ServiceAccount(IRSA) 최소 권한(`athena:*`, `glue:*`, `s3:*` read/write) 검증
  - [ ] (외부 kubeconfig 사용 시) Airflow가 참조할 kubeconfig를 마운트/연결하여 `KubernetesPodOperator`가 클러스터에 접근 가능한지 확인

## 참고
- 시간/타임존: Airflow 2.x에서는 `DAG(..., timezone=...)` 미지원. `start_date`를 KST로 지정했고, 필요 시 `core.default_timezone=Asia/Seoul` 설정을 고려하세요.
- 수동 세트 연결: `ad_daily_summary_test`의 센서를 `external_dag_id="ad_hourly_summary_test"`로 바꿔 수동 세트끼리만 의존시키는 것도 가능합니다.