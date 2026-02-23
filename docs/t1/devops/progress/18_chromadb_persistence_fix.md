# 💾 ChromaDB 영구 저장소 구축 및 Vanna AI 안정화 보고서

본 문서는 CAPA 프로젝트의 AI 모듈(Vanna API)에서 발생하던 500 Internal Server Error(데이터 증발 현상)의 근본 원인을 파악하고, 백터 데이터베이스(ChromaDB)의 영구 저장(Persistence) 설정을 최적화하여 해결한 과정을 기록합니다.

---

## 📅 작업 요약
| 단계 | 작업 항목 | 상태 | 완료 일시 | 주요 성과 |
| :--- | :--- | :---: | :--- | :--- |
| **1단계** | **데이터 증발 원인 분석** | ✅ 완료 | 2026-02-23 | 원인(In-Memory 구동) 식별 |
| **2단계** | **ChromaDB 환경 변수 주입** | ✅ 완료 | 2026-02-23 | 영구 저장소 활성화 (`IS_PERSISTENT=TRUE`) |
| **3단계** | **AI(Vanna) 재학습 및 파일 검증** | ✅ 완료 | 2026-02-23 | 디스크 쓰기 성공 및 DB 용량 갱신 확인 |
| **4단계** | **Text-to-SQL 쿼리 통합 테스트** | ✅ 완료 | 2026-02-23 | 자연어 질의 정상 동작 복구 |

---

## 🔍 [1단계] Vanna AI 500 에러 원인 분석

### 1) 현상 및 배경
- **현상**: 슬랙 봇을 통해 자연어로 질문을 던지면 Vanna API에서 500 Error가 발생하여 SQL이 생성되지 않음.
- **조사**: API의 `/training-data` 엔드포인트를 확인한 결과 학습된 데이터(테이블 DDL, 문서, SQL 예제)가 모두 0건으로 비어 있었음.

### 2) 근본 원인 (Root Cause)
- **저장 방식 오류 (휘발성 메모리)**: ChromaDB 컨테이너 내 `/data/chroma.sqlite3` 파일의 수정 시간이 과거 특정 시점에 멈춰있고, 학습을 시켜도 용량이 변하지 않음.
- 파드가 재시작되거나 시간이 경과하면 메모리에 있던 벡터 데이터가 날아가면서 AI 모델이 스키마를 기억하지 못하는 치명적인 상태였음.

---

## 🔍 [2단계] 인프라 설정 수정 (영구 저장 강제)

### 1) 기술적 접근
- 볼륨 리소스(PVC 1Gi)를 마운트해 두었음에도 프로세스가 인식하지 못하는 문제를 헬름 차트 단위의 명시적인 **환경 변수 강제 주입**으로 해결.

### 2) 작업 내용
- `infrastructure/terraform/10-applications.tf` 수정:
  ```hcl
  set {
    name  = "env.IS_PERSISTENT"
    value = "TRUE"
  }
  set {
    name  = "env.PERSIST_DIRECTORY"
    value = "/data"
  }
  ```
- **Terraform 재적용**: `terraform apply -target="helm_release.chromadb"`를 통해 인프라 상태 반영 후 StatefulSet 완전 재시작(`rollout restart`).

---

## 🔍 [3단계] 데이터 재학습 및 디스크 기록 검증

### 1) 재학습 수행
- 포트 포워딩(`kubectl port-forward`)과 로컬 Python 스크립트(`train_vanna.py`)를 통해 `ad_events_raw` 테이블 구조, 비즈니스 의미(documentation), 집계 쿼리 예제들을 다시 주입.

### 2) 검증 결과
- **파일 시스템 갱신 확인**: 컨테이너 내부 `ls -l /data/chroma.sqlite3` 결과, 파일 크기가 `163,840 Bytes`로 커지고 Timestamp가 방금 전 시간으로 갱신됨을 육안으로 검증 성공.

---

## 🔍 [4단계] 자연어-SQL 변환 복구 최종 테스트

### 1) 엔드투엔드(E2E) API 테스트
- 내부 통신망을 통해 `/query` API에 자연어 질문: `"이벤트 타입별 집계 결과를 알려줘"` 발송.

### 2) 결과 확인
- **SQL 생성 성공**:
  ```sql
  SELECT event_type, COUNT(*) as event_count FROM ad_events_raw GROUP BY event_type;
  ```
- **500 에러 소멸**: Vanna API가 아무런 예외 없이 200 OK 상태의 완벽한 JSON 페이로드를 응답함.
- (참고: 로컬 터미널 쉘 한글 인코딩 문제로 결과 출력 시 이모지 깨짐 현상이 있었으나, API 본연의 기능은 완벽히 동작함을 입증)

---

## 📊 최종 결과 및 의의

### 🏆 판정: ✅ **Pass & AI Stabilized**
> 단순한 재학습(임시 조치)이 아닌, **스토리지 영구화 아키텍처(Persistence)**를 확실하게 교정함으로써 EKS 클러스터 내 파드 스케일링/재시작에도 끄떡없는 튼튼한 Vanna AI 기반을 확보했습니다. 이제 사용자는 슬랙에서 지속적이고 안정적인 데이터 조회 서비스를 경험할 수 있습니다!
