# ETL 독립 모듈

이 모듈은 Airflow DAG에서 사용하기 위한 독립적인 ETL 패키지입니다.
원본 `etl_summary_t2`를 수정하지 않고 Airflow 환경에 최적화된 버전입니다.

## 구성

```
etl_modules/
├── __init__.py          # 패키지 초기화
├── athena_utils.py      # Athena 쿼리 실행 유틸리티
├── config.py            # 설정 파일 (S3, Athena 등)
├── hourly_etl.py        # 시간별 ETL 클래스
└── daily_etl.py         # 일별 ETL 클래스
```

## 사용 방법

### DAG에서 import
```python
# 기존 방식 (경로 추가 필요)
# sys.path.append("/opt/airflow/etl_summary_t2")
# from hourly_etl import HourlyETL

# 새로운 방식 (독립 모듈)
from etl_modules.hourly_etl import HourlyETL
from etl_modules.daily_etl import DailyETL
```

### 예제
```python
# Hourly ETL 실행
etl = HourlyETL(target_hour=dt_kst)
etl.run()

# Daily ETL 실행
etl = DailyETL(target_date=dt_kst)
etl.run()
```

## 특징

1. **독립성**: 원본 코드 수정 없이 별도 운영
2. **Airflow 최적화**: DAG와 같은 위치에 배치되어 import 간편
3. **Docker 호환**: 볼륨 마운트 불필요
4. **유지보수**: 원본 변경 시 수동 동기화 필요

## 원본과의 차이점

- import 경로 최적화 (상대 import 유지)
- config.py의 .env 파일 경로 탐색 개선
- Airflow 환경 변수 우선 사용

## 주의사항

- 원본 `etl_summary_t2` 변경 시 수동으로 동기화 필요
- AWS 자격 증명은 환경 변수로 설정 필요
- Python 패키지 의존성은 Airflow 이미지에 포함되어야 함