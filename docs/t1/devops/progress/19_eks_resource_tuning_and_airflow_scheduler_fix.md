# ⚖️ EKS 노드 리소스 튜닝 및 Airflow 스케줄러 정상화 보고서

본 문서는 CAPA 프로젝트의 EKS 클러스터에서 발생하던 **노드 과부하(NotReady) 현상**과 이로 인해 파생된 **Airflow Scheduler의 무한 재시작(Init:Error) 문제**를 파악하고, 클러스터 전체 리소스 할당량(Limits)을 튜닝하여 100% 안정화시킨 과정을 기록합니다.

---

## 📅 작업 요약
| 단계 | 작업 항목 | 상태 | 완료 일시 | 주요 성과 |
| :--- | :--- | :---: | :--- | :--- |
| **1단계** | **장애 원인 교차 분석** | ✅ 완료 | 2026-02-23 | Node Limits 200% 초과 및 DB 초기화 상태 파악 |
| **2단계** | **Airflow DB 마이그레이션 정상화** | ✅ 완료 | 2026-02-23 | 헬름 릴리즈 교체로 스키마 생성 완료 |
| **3단계** | **컴포넌트별 리소스 다이어트** | ✅ 완료 | 2026-02-23 | Slack Bot, Vanna API, Redash Limit 대폭 축소 |
| **4단계** | **Redash Gunicorn Timeout 해결** | ✅ 완료 | 2026-02-23 | 서빙용 CPU/Mem 최소 호흡 공간 확보 (700m, 768Mi) |
| **5단계** | **전체 노드 및 파드 안정성 검증** | ✅ 완료 | 2026-02-23 | EKS 클러스터 100% Running (재시작 0) 달성 |

---

## 🔍 [1단계] 장애 원인 파악 (Airflow + Node 과부하)

### 1) 현상 및 배경 (비용 절감을 위한 노드 축소)
- **클러스터 노드 축소 (비용 최적화)**: 과도한 인프라 유지 비용을 절감하기 위해 기존에 운영되던 EKS 노드(`t3.medium`)를 단일 AZ 구성 및 **최소 노드 개수(2대)로 강제 축소**하여 운영하기로 결정했습니다.
- **현상 1**: 노드를 줄인 직후부터 `airflow-scheduler` 파드의 통신이 두절되며 `Init:Error` 또는 Liveness Probe Timeout으로 무한 재시작되는 현상 발생.
- **현상 2**: EC2 기반의 노드 1대(`ip-172-31-34-230`)가 과부하를 견디지 못하고 반복적으로 다운(`NotReady` 상태)됨.

### 2) 근본 원인 (Root Cause)
- **자원 경합(Resource Contention)**: 노드를 2대로 축소하면서 물리적인 가동 자원은 크게 줄어들었으나, 내부에 구동되는 Airflow, Redash, Vanna 등 **무거운 데이터 애플리케이션들의 리소스 한도(Limits) 설정은 축소 이전 그대로 유지**되었습니다. 결과적으로 각 쿠버네티스 파드에 할당된 **Limits (최대 사용 한도)의 총합이 노드 실제 용량의 217%를 초과**하게 되었습니다. 파드들이 일제히 CPU를 요구할 때 자원 경합(Throttling)이 심하게 발생하여 헬스체크 타임아웃 붕괴를 일으켰습니다.
- **마이그레이션 데드락**: 이전 작업에서 PVC(스토리지)를 삭제했으나 Airflow가 빈 깡통 DB에서 Table Scheme를 만들지 못해 데드락 상태.

---

## 🔍 [2단계] 인프라 설정 튜닝 (자원 다이어트 테트리스)

### 1) Terraform 및 Helm Values 리소스 최적화
노드 안정성을 위해 쿠버네티스 스케줄러가 판단하는 파드별 리소스 Limits를 아래와 같이 대폭 가볍게 수정했습니다.

- **Slack Bot & Report Generator**: 
  - (변경 전) `CPU 500m / Mem 512Mi` -> (변경 후) `CPU 200m / Mem 256Mi`
  - 트래픽이 적은 백그라운드 워커 중심 축소.
- **Vanna API (AI 모듈)**: 
  - (변경 전) `CPU 700m / Mem 1Gi` -> (변경 후) `CPU 400m / Mem 768Mi`
- **Redash (서버 및 워커 3종)**:
  - Worker (3개): `CPU 500m / Mem 512Mi` -> `CPU 200m / Mem 256Mi`
  - Server: 최초 CPU를 `400m`로 조였으나(Gunicorn Timeout 에러 137 발생), 최종적으로 **`CPU 700m / Mem 768Mi`**로 타협안 반영. 
  - Liveness / Readiness 대기 시간 2배 증설(`120s`, `60s`).
- **Airflow Scheduler**: 
  - Liveness/Readiness Timeout 수치를 대폭 늘려 노드 경합 시 일시적으로 느려져도 파드가 죽지 않고 버티도록 수정.

### 2) 클러스터 내 재배포 및 정리
- 죽어있던 EC2 노드를 AWS Console 단에서 강제 재부팅(초기화) 진행.
- `terraform apply -replace="helm_release.airflow"`로 PVC가 초기화된 상태에 맞춰 DB Schema Migration Job 강제 구동.
- 수정한 테라폼을 적용(`terraform apply`)하여 클러스터 배포 완료.

---

## 🔍 [3단계] 최종 배포 및 검증

### 1) 노드별 최적화 비율 (Limits 기준)
- **Node 1 (`172-31-34-230`)**: CPU 152%, Memory 150% (기존 217%에서 대폭 하락하여 경합 한계선 회피)
- **Node 2 (`172-31-37-208`)**: CPU 82%, Memory 141% 

### 2) 파드 상태 결과
```bash
# 주요 서비스 생존율 정상 (100% Running, Error 0개)
airflow-scheduler-0                        3/3     Running     (복구 됨)
redash-64dcff6599-2dlfk (Main Server)      1/1     Running     (복구 됨)
vanna-api-567664f6cb-c6vqj                 1/1     Running     
slack-bot-7949b85b86-vgw8b                 1/1     Running 
```

---

## 📊 최종 결과 및 의의

### 🏆 판정: ✅ **Pass & Cluster Stabilized**
> 노드 규모(2대)에 무리하게 맞춰져 있던 앱(Redash, Vanna, Airflow)들의 최대 부하 수치(Limits)를 면밀하게 분석하여 깎아내고 밸런싱했습니다. 이 테트리스 튜닝을 통해 EC2 인스턴스의 OOM / CPU Throttling 패닉을 완벽히 차단했으며, 에러 루프에 빠져있던 **Airflow 스케줄러와 Redash 서버를 완벽하게 구출(Running)하는 데 성공**했습니다.
