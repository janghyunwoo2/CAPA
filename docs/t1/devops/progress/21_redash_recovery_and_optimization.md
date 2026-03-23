# 📊 Redash 장애 복구 및 서비스 최적화 보고서

본 문서는 노드 업그레이드 이후 발생했던 **Redash의 무한 재시작(Worker Timeout)** 및 **Redis 인증 오류(NOAUTH)** 현상을 과거 해결 기록([Task #12])을 바탕으로 분석하고, 클리닝 및 리소스 최적화를 통해 서비스를 정상화한 과정을 기록합니다.

---

## 📅 작업 요약
| 단계 | 작업 항목 | 상태 | 완료 일시 | 주요 성과 |
| :--- | :--- | :---: | :--- | :--- |
| **1단계** | **장애 원인 교차 검증** | ✅ 완료 | 2026-02-23 | 30s Gunicorn Timeout 및 Redis Secret 충돌 확인 |
| **2단계** | **레거시 인증 정보 클리닝** | ✅ 완료 | 2026-02-23 | `redash-redis` Secret 수동 삭제 (인증 동기화) |
| **3단계** | **부팅 병목 최적화 (Burst)** | ✅ 완료 | 2026-02-23 | Server CPU Limit 1000m 상향 및 Probe 완화 |
| **4단계** | **클린 재설치 및 DB 초기화** | ✅ 완료 | 2026-02-23 | `terraform replace`를 통한 스키마 재생성 확인 |
| **5단계** | **Athena 연결 장애 해결** | ✅ 완료 | 2026-03-04 | 설정값 특수문자 제거, 타임아웃 및 워커 메모리 최적화 |
| **5단계** | **E2E 서비스 가용성 확인** | ✅ 완료 | 2026-02-23 | Redash 접속 및 `/ping` 헬스체크 200 OK 달성 |

---

## 🔍 [1단계] 핵심 장애 원인 분석

### 1) Gunicorn 워커 타임아웃 (30초의 벽)
- **현상**: 리대시 서버 파드는 `Running` 상태이나, 로그 상에서 **정확히 30초**마다 `WORKER TIMEOUT`이 발생하며 워커가 죽고 재생성됨.
- **원인**: 파드 사양에 관계없이 리대시 내부 Gunicorn의 기본 타임아웃이 30초로 설정되어 있었으며, 초기 DB 테이블 체크 및 연결 과정이 이 시간을 초과함.

### 2) Redis 인증 불일치 (`NOAUTH`)
- **현상**: `Internal Server Error` 발생. Redis 로그 상에 `Authentication required` 출력.
- **원인**: 테라폼 설정은 `auth.enabled=false`였으나, 이전에 생성된 K8s Secret(`redash-redis`)에 기존 암호 정보가 잔존하여 새 파드들이 인증 모순 상태에 빠짐.

---

## 🛠️ [2단계] 기술적 해결 조치 (기록 기반 솔루션)

사용자의 과거 해결 기록(`docs\t1\devops\progress\12_complete.md`)에 명시된 **"성공 방정식"**을 현재의 고스펙 노드(`t3a.large`) 환경에 맞게 재적용했습니다.

### 1) 인증 정보 강제 동기화
- **명령어**: `kubectl delete secret redash-redis -n redash`
- **설명**: 꼬여있던 비밀번호 정보를 물리적으로 제거하여, 리대시와 레디스가 약속된 대로 "비밀번호 없음" 상태로 통신하게 함.

### 2) 인프라 자원 및 프로브(Probe) 튜닝
- **CPU Burst 확보**: 서버 부팅 시의 Python 연산 병목을 해결하기 위해 CPU Limit을 **1000m (1 Core)**으로 설정.
- **Readiness Probe 완화**:
  - `initialDelaySeconds`: **60s** (여유로운 부팅 시간 확보)
  - `timeoutSeconds`: **15s** (일시적인 부하 대응)

---

## 🚀 [3단계] 최종 배포 및 결과 검증

### 1) 클린 재배포 (Replace Deployment)
기존의 오염된 릴리즈를 완전히 걷어내고 새 설정을 반영하기 위해 테라폼 `replace` 명령을 사용했습니다.
```bash
terraform apply -replace="helm_release.redash" -auto-approve
```

### 2) 최종 상태 확인
- **Pod 상태**: `redash-server`를 포함한 모든 컴포넌트(Worker, Scheduler, DB, Redis)가 **1/1 Ready** 달성.
- **서비스 로그**:
  ```text
  [metrics] method=GET path=/ping status=200 duration=0.25ms
  ```
- **접속 확인**: 외부 로드밸런서를 통한 리대시 메인 로그인 화면 정상 호출 확인.

---

## 🛠️ [4단계] Athena 데이터 소스 연결 장애 해결 (2026-03-04)

서버 정상 부팅 이후, Athena 데이터 소스 연결 시 발생하던 `Unknown error occurred` 장애를 해결하기 위해 다각도로 튜닝을 진행했습니다.

### 1) 데이터 소스 설정값 내 숨겨진 특수문자 제거(근본원인 아님)
- **현상**: 모든 설정이 올바름에도 연결 테스트 실패.
- **원인**: AWS Region(`ap-northeast-2`) 및 Work Group(`capa-workgroup`) 필드 끝에 **Zero-Width Space(`\u200b`)**가 포함되어 Athena API 호출 시 잘못된 파라미터로 인식됨.
- **해결**: 데이터 소스 설정을 직접 수정하여 보이지 않는 특수문자를 제거함.

### 2) Gunicorn 및 RQ Job 타임아웃 확장
- **현상**: 연결 테스트가 약 30초 후 응답 없이 종료됨.
- **원인**: Athena 초기 연결 및 메타데이터 조회 시간이 Gunicorn 기본 타임아웃(30s)을 초과함.
- **해결**: `REDASH_GUNICORN_TIMEOUT` 환경변수를 **120**으로 상향하여 원활한 데이터 조회를 보장함.

### 3) Worker 리소스 최적화 및 OOM 해결
- **현상**: 연결 테스트 요청 시 Worker(adhoc) 프로세스가 반복적으로 `SIGKILL` 됨.
- **원인**: 쌓여있는 큐(40+개)를 한꺼번에 처리하는 과정에서 메모리 사용량이 기존 Limit(256Mi)을 초과하여 OOM 발생.
- **해결**:
  - **메모리 상향**: Worker(adhoc, scheduled, generic)의 Limit을 **512Mi**로 상향.
  - **큐 클리닝**: Redis에 적체된 오래된 작업(`queries`, `default`, `schemas` 큐)을 수동으로 삭제하여 워커 부하 경감.

---

## 🏆 성과 및 의의
- **기록의 가치 증명**: 과거에 작성된 트래블슈팅 문서를 활용하여 복잡한 장애를 단시간 내에 근본적으로 해결함.
- **안정적인 데이터 플랫폼**: Airflow와 Redash가 모두 정상화됨에 따라 고사양 노드 기반의 데이터 파이프라인 운영 준비 완료.

---
**다음 단계**: 🏁 전체 인프라 통합 모니터링 및 운영 이관
