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

## 🔍 [5단계] 진짜 원인 발견 및 완벽한 해결 (False Positive 교정)

### 1) 과거 조치의 한계 (False Positive)
- 2월 23일에 진행된 **[2단계]** 인프라 설정 수정 후 용량이 변한 것을 확인했으나, 이는 파드 내부 로컬 임시 폴더에 우연히 저장된 것이었습니다.
- 실제로는 외부의 `chromadb-0` 파드로 데이터가 전송되지 않고, `vanna-api` 파드가 죽을 때마다 데이터가 계속 증발하는 **진짜 문제**가 남아 있었습니다.

### 2) 진짜 원인 (Vanna API 파이썬 코드 결함)
- `services/vanna-api/src/main.py` 파일 분석 결과, Vanna 라이브러리가 외부 ChromaDB 클라이언트 객체를 명시적으로 전달받지 않으면 **호스트 설정(`CHROMA_HOST`)을 무시하고 로컬 임시 폴더(`.`)에 데이터를 저장해 버리는 로직 결함**이 발견되었습니다.

### 3) 코드 수정 및 버전 동기화 조치
- `main.py`의 `get_vanna()` 함수 내에서 `chromadb.HttpClient(host=CHROMA_HOST)`를 명시적으로 생성하여 Vanna 객체에 주입하도록 코드를 완전히 뜯어 고쳤습니다.
- 통신 규격을 맞추기 위해 클라이언트 파이썬 패키지를 서버 버전과 동일하게 `chromadb==1.0.10`으로 업데이트하고, 이와 호환되는 `fastapi==0.115.9`로 핀(Pin)을 박아 도커 이미지를 재빌드 및 배포(`rollout restart`)했습니다.

### 4) 최종 검증 결과
- `vanna-api/src/train_dummy.py`를 파드 내에서 실행하여 더미 데이터를 다시 밀어 넣었습니다.
- `chromadb-0` 파드에 접속하여 `/data/chroma.sqlite3` 파일 사이즈(192512 Bytes)가 명확히 증가했음을 확인했습니다.
- `/query` API로 `전체 광고비를 알려줘`라고 질의한 결과, 정확하게 학습된 DDL에 맞추어 `SELECT SUM(bid_price) as total_ad_spend FROM ad_events_raw` SQL이 생성되고 200 OK 응답을 받았습니다.

---

## 📊 최종 결과 및 의의

### 🏆 판정: ✅ **Pass & AI Permanently Stabilized**
> 환경 변수 주입이라는 인프라적 착시(False Positive)를 넘어, **코드 레벨의 데이터 연결 통로(HttpClient)**를 근본적으로 수리했습니다. 서버와 클라이언트의 버전 호환성까지 완벽하게 동기화함으로써 Vanna AI는 영구적으로 기억을 잃지 않는 진정한 텍스트-SQL AI로 거듭났습니다!
