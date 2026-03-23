# Docker에서 CAPA Airflow 실행 트러블슈팅 가이드

개요
- 현재 CAPA 프로젝트에서 Airflow를 Docker로 띄운 상태에서 자주 만나는 문제를 빠르게 해결하는 가이드입니다.
- Kubernetes Pod Operator(KPO) 실행으로 인한 추가 설정이 필요할 수 있지만, Docker 환경에서는 KPO를 피하고 PythonOperator 경로로 동작하는 것을 기본으로 제시합니다.

1) 준비물 및 기본 설정
- Docker 및 Docker Compose가 설치되어 있어야 합니다.
- CAPA 레포의 docker-compose 파일과 .env 및 실행 스크립트에 접근 가능해야 합니다.
- AWS 자격증명은 컨테이너에 주입되거나 런타임에서 접근 가능해야 합니다.
- AWS 리전은 env로 설정하거나 기본값으로 사용 가능해야 함.

2) Docker 환경에서의 실행 경로 선택
- 기본 권장: KPO 비활성화(파이썬 경로 사용) — 왜: Docker 컨테이너 내부에서 쿠버네스 클러스터에 접근 불가가 일반적이므로 KPO 경로의 실패를 피하기 위함
- KPO를 반드시 쓰려면 해당 컨테이너가 쿠버네티스 API 서버에 접근 가능해야 하며, 로컬 개발 환경이 아닌 실제 쿠버네스 클러스터에 연결되어 있어야 함
- KPO 비활성화 예시: USE_KPO=0 환경변수 설정 또는 docker-compose.yml에서 USE_KPO 항목 제거/0으로 설정

3) DAG 트리거 및 로그 확인 절차
- DAG 트리거 방법(로컬 터미널/API):
  - 일반 CLI 경로(컨테이너 내부):
    docker exec -it <airflow-scheduler-container> airflow dags trigger ad_hourly_summary_test -e 2026-03-04T14:10:00+09:00
  - 혹은 uv 런ner 등 로컬 래퍼를 사용 중인 경우 설명에 맞춰 실행
- 로그 확인:
  - docker-compose logs -f airflow-scheduler
  - docker-compose logs -f airflow-webserver
  - 특정 DAG 로그: docker exec -it <airflow-scheduler-container> bash -lc 'tail -n 200 $AIRFLOW_HOME/logs/dags/ad_hourly_summary_test/...' 

4) AWS 자격증명 및 네트워크 점검
- 컨테이너에 AWS 자격증명 전달: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN 필요 시
- AWS_DEFAULT_REGION 설정: ap-northeast-2 등
- 네트워크: S3/Athena 엔드포인트에 접근 가능해야 함(프록시/방화벽 설정 확인)

5) 쿼리 재현 및 디버깅 로드맵
- 임시 테이블 생성 쿼리(ad_hourly_summary_tmp)와 메인 쿼리를 로컬 AWS 콘솔에서 먼저 실행해 보는 것이 좋습니다.
- 임시 테이블 생성/삭제를 통한 아이덴터피 확인
- 파티션/데이터 형식이 쿼리의 필터와 맞는지 확인

6) 자주 발생하는 오류 예시 및 해결
-