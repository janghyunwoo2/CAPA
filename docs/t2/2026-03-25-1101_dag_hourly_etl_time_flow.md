# Hourly ETL DAG — "왜 10시 10분에 실행했는데 8시 데이터를 처리해?"

## 1. 한 줄 요약

> **한국시간 10:10에 DAG가 돌면, 8시 데이터를 처리한다. 이건 정상이다.**
> 이유: Airflow가 자동으로 -1시간, 코드가 안전하게 -1시간 = 총 -2시간

---

## 2. 쉬운 비유로 이해하기

택배 분류 센터를 떠올려 보자.

```
📦 광고 로그 = 택배 상자
🏭 ETL      = 택배 분류 작업
⏰ DAG      = "매시간 10분"에 울리는 알람
```

**상황**: 오전 10시 10분에 알람이 울렸다. 어떤 택배를 분류할까?

```
❌ 10시 택배?  → 아직 도착 중이라 상자가 다 안 왔다
❌ 9시 택배?   → Airflow 규칙상 한 칸 전 것을 맡는다 (=9시)
                 하지만 9시 택배도 10시 10분 기준으로 불과 10분 전에 마감되어
                 아직 덜 도착한 게 있을 수 있다
✅ 8시 택배!   → 확실히 다 도착해서 빠짐없이 분류할 수 있다
```

**그래서 -2시간이다.** Airflow의 규칙(-1시간) + 안전장치(-1시간) = 총 -2시간.

---

## 3. 시간이 밀리는 2가지 이유

### 이유 ①: Airflow의 규칙 (-1시간)

Airflow는 "지금 실행" ≠ "지금 데이터"라는 규칙이 있다.

```
10시 10분에 실행 → "내가 담당하는 건 9시 10분부터의 데이터야"
                    (Airflow가 자동으로 1시간 전 구간을 배정)
```

이건 Airflow의 `data_interval_start`라는 개념인데, 쉽게 말하면:
- **"이번 알람이 울리기 직전 구간의 데이터를 네가 처리해라"** 라는 뜻

### 이유 ②: 우리가 코드에서 추가로 -1시간

```
9시 10분 데이터 → 코드에서 1시간 더 빼기 → 8시 10분 → 8시 데이터 처리
```

왜 또 빼느냐?
- 9시 데이터는 10시 10분 시점에 아직 S3에 다 안 올라왔을 수 있다
- **8시 데이터는 확실히 다 올라와 있다** → 빠짐없이 안전하게 처리

---

## 4. 한눈에 보는 시간 흐름

```
한국시간 10:10에 DAG 실행
    │
    │  ① Airflow 규칙: -1시간
    ▼
한국시간 09:10 (Airflow가 배정한 구간)
    │
    │  ② 코드에서 안전하게: -1시간 더
    ▼
한국시간 08:10 → 8시 데이터를 ETL 처리!
```

---

## 5. 매 시간 실행 예시

| DAG 실행 시각 (한국시간) | ① Airflow -1시간 | ② 코드 -1시간 | 최종 처리 대상 |
|:-:|:-:|:-:|:-:|
| 10:10 | 09:10 | **08:10** | **8시** 데이터 |
| 11:10 | 10:10 | **09:10** | **9시** 데이터 |
| 12:10 | 11:10 | **10:10** | **10시** 데이터 |
| 13:10 | 12:10 | **11:10** | **11시** 데이터 |
| ... | ... | ... | ... |

> 규칙: **항상 실행 시각보다 2시간 전 데이터를 처리한다**

---

## 6. 실제 코드에서는 어떻게 구현되어 있나

### AS-IS: 현재 방식 — `01_ad_hourly_summary.py` (PythonOperator)

매시간 자동 실행되는 DAG. Python 코드 안에서 직접 시간을 계산한다.

```python
# ① Airflow가 넘겨주는 시간 (이미 -1시간 된 상태)
dt_utc = context["data_interval_start"]

# UTC를 한국시간으로 변환
dt_kst = pendulum.instance(dt_utc).in_timezone('Asia/Seoul')

# ② 1시간 더 빼기 (안전장치)
target_hour_kst = dt_kst.subtract(hours=1)

etl = HourlyETL(target_hour=target_hour_kst)
etl.run()
```

- **파일**: `dags/01_ad_hourly_summary.py`
- **스케줄**: `"10 * * * *"` (매시간 10분)
- **실행 환경**: Airflow Worker에서 직접 Python 실행

### AS-IS v2: `t2_ad_hourly_summary_v2` (KubernetesPodOperator) - EKS 배포용

ECR 컨테이너를 이용한 EKS Airflow용 버전.
`data_interval_start` 기준으로 `Asia/Seoul` 변환 후 1시간 감산하여, 결국 **실제 처리 대상은 실행 시점 기준 -2시간**이 된다.

```python
arguments=[
    "--mode",
    "hourly",
    "--target-hour",
    "{{ data_interval_start.in_timezone('Asia/Seoul').subtract(hours=1).isoformat() }}",
],
```

- **파일**: `dags/t2_ad_hourly_summary_v2.py` (미존재, 문서 참조용)
- **스케줄**: `"10 * * * *"` (매시간 10분, UTC)
- **실행 환경**: EKS KubernetesPodOperator (`airflow-kpo-t2-etl-runner` 컨테이너)

### AS-IS vs AS-IS v2 시간 차이 정리

| 항목 | Airflow의 `data_interval_start` | 코드 추가 감산 | 최종 처리 대상 (KST) |
|------|----------------------------------|---------------|----------------------|
| 01_ad_hourly_summary | `now-1h` (예: 10:10 실행→09:10) | -1h → 08:10 | 8시 데이터 |
| t2_ad_hourly_summary_v2 | `now-1h` (예: 10:10 실행→09:10) | -1h → 08:10 | 8시 데이터 |

> 둘 다 동작 결과는 동일: `실행시점-2시간` **8시 데이터** 처리.

### TO-BE: 수동 기간 실행 — `05_ad_hourly_summary_period.py` (KubernetesPodOperator)

기간을 지정해 수동으로 트리거하는 DAG. 환경변수로 기간을 넘기고 EKS Pod에서 실행한다.

```python
# KubernetesPodOperator 방식 (EKS 환경에서 자동 활성화)
create_hourly_summary = KubernetesPodOperator(
    task_id="create_hourly_summary_period",
    env_vars={
        "START_DATE": "{{ params.start_date }}",  # 시작일
        "END_DATE": "{{ params.end_date }}",        # 종료일
        "HOURS": "{{ params.hours }}",              # 시간 범위 (0-23)
    },
    ...
)

# PythonOperator 폴백 (로컬 환경에서 자동 활성화)
create_hourly_summary = PythonOperator(
    task_id="create_hourly_summary_period",
    python_callable=_run_hourly_etl_period,  # 동일 로직
)
```

- **파일**: `dags/05_ad_hourly_summary_period.py`
- **스케줄**: `None` (수동 트리거 전용)
- **실행 환경**: EKS Pod (KubernetesPodOperator) 또는 Airflow Worker (PythonOperator 폴백)
- **환경 자동 감지**: `KUBERNETES_SERVICE_HOST` 환경변수 유무로 KPO/Python 자동 전환

### AS-IS vs TO-BE 비교

| 항목 | AS-IS (`01_ad_hourly_summary`) | TO-BE (`05_ad_hourly_summary_period`) |
|------|-------------------------------|---------------------------------------|
| 실행 주기 | 매시간 10분 자동 실행 | 수동 트리거 (기간 지정) |
| 시간 계산 | `data_interval_start` - 1시간 | 파라미터로 기간 직접 지정 |
| 실행 환경 | Airflow Worker | EKS Pod (KPO) / Worker (폴백) |
| 용도 | 실시간 운영 | 백필·재처리 |

---

## 7. 전체 동작 흐름

```
[매시간 10분: Airflow 알람]
    │
    ▼
[시간 계산]  UTC → KST 변환 → 1시간 빼기 → "8시 데이터를 처리해라"
    │
    ▼
[Airflow Worker에서 PythonOperator 실행]  HourlyETL 시작
    │
    ├── 1. Athena에서 8시 impression + click 데이터 조회 (SQL 조인)
    ├── 2. 결과를 Parquet 파일로 변환
    ├── 3. S3에 저장: summary/ad_combined_log/.../hour=08/
    └── 4. Glue 테이블 파티션 갱신
    │
    ▼
[완료]  8시 데이터가 S3 summary 폴더에 적재됨
```

---

## 8. 결론

| 질문 | 답 |
|------|-----|
| 10:10에 실행했는데 8시 데이터를 처리하는 게 맞아? | **맞다. 정상이다.** |
| 왜 2시간이나 차이가 나? | Airflow 규칙(-1시간) + 안전장치(-1시간) = -2시간 |
| 안전장치가 왜 필요해? | 바로 직전 시간 데이터는 S3에 아직 다 안 올라왔을 수 있어서 |
| AS-IS와 TO-BE의 차이는? | AS-IS(`01`)는 매시간 자동 실행, TO-BE(`05`)는 수동 기간 지정 + EKS Pod 실행 |
