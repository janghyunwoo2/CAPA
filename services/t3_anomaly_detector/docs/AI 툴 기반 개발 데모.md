# AI 툴 기반 개발 데모

**역할**: 프로젝트의 요구사항 및 아이디어 문서
**관련 파일**: `implementation_plan.md` (구현 계획)



## 아래와 같이 LLM에 질문해서 데모 준비

```sql
실시간으로 들어오는 ad impression 로그 수를 5분 단위로 모니터링하면서 anomaly detection을 하는 프로그램을 만드려고 해. ad impression 로그는 kinesis에 저장하기 때문에 로그 수 데이터는 kinesis에 있어. kinesis로부터 얻은 데이터는 랜덤으로 2주치를 생성해놓고 거기에서 얻는 거라서 치면 돼.

광고 노출 로그의 데이터 패턴은 **'배달앱 트래픽'**을 기준으로 생성해줘. 
1. 하루 중 점심(11시~13시)과 저녁(18시~21시)에 트래픽이 급증하는 뚜렷한 피크가 있어.
2. 새벽(2시~6시)과 오후(14시~17시)에는 트래픽이 매우 낮아.
3. 평일(월~목)보다 금요일 저녁과 주말(토/일)의 전체적인 트래픽 양이 훨씬 더 많아.
이 규칙을 따르는 2주치 5분 단위 Mock 데이터를 만들고, 중간에 인위적인 이상치(Anomaly - 예: 피크타임에 트래픽 급락, 한가한 시간에 트래픽 폭증)를 2~3개 섞어줘.
```



## 개요

5분 단위 ad impression 로그 수를 모니터링하여 ML 기반으로 이상 징후를 자동 탐지하는 파이프라인 구축

## 배경

- Ad impression 로그는 Kinesis에 저장됨
- 트래픽은 **배달앱의 특징**을 띔: 점심/저녁 강한 피크, 새벽/오후 유휴 시간대, 주말 베이스라인 통신량 증가
- 이상 징후 조기 감지로 광고 시스템 안정성 확보 필요

## 범위

- Kinesis 데이터 수집 레이어 (현재는 Mock 데이터로 대체)
- ML 기반 Anomaly Detection 모델 (Prophet + Isolation Forest)

## 작업 범위

### Task 1: Kinesis 데이터 수집 레이어 구현 (Mock 데이터)

- Mock 데이터 생성기 구현
    - 2주치 히스토리 데이터 생성
    - 배달앱 시계열 패턴 반영: 
        - 점심(11-13시) / 저녁(18-21시) 피크
        - 새벽/오후 유휴 시간대 트래픽 급감
        - 금-일요일 주말 트래픽 증가
    - 인위적인 이상 데이터(Traffic Drop, Sudden Spike) 주입
    - 실시간 스트리밍 시뮬레이션
- Kinesis Consumer 인터페이스 추상화
    - 추후 실제 Kinesis로 교체 시 수정 최소화
    - 5분 단위 집계 인터페이스 정의

### Task 2: Prophet Anomaly Detection 및 콘솔 출력

#### 작업 내용

- ML 기반 Anomaly Detection 모델 (Prophet + Isolation Forest) 적용
- 모니터링 파이프라인 통합 및 5분 단위 실시간 결과 평가
- 모니터링 파이프라인 통합 및 콘솔 출력
    - 그래프 시각화 (Prophet 내장 도구 및 **Plotly** 활용)
        - 전체 시계열 대비 이상치 강조 및 예측 구간 표시 (`m.plot`)
        - **Interactive HTML Report**: 브라우저에서 줌/호버가 가능한 상세 분석용 그래프 (`anomaly_interactive.html`)
        - **Prophet Components Plot**: 배달앱 트래픽의 시간대별/요일별 패턴(학습된 계절성) 시각화 (`m.plot_components`)

---

## 📝 아키텍처 토의 및 결정 기록

**Q: Kinesis에서 데이터를 직접 가져올 것인가, CloudWatch 지표(Metrics)를 폴링 할 것인가?**

*   **현재 인프라 상황**:
    *   `impression`, `click`, `conversion` 이벤트가 섞여 있지 않고 각각의 Kinesis 스트림으로 분리되어 구축된 상태.
*   **실제 프로덕션 권장(Best Practice)**:
    *   분리된 Kinesis 인프라에서는 `ad impression` 스트림으로 들어오는 데이터를 파이썬 서버에서 건건이 파싱할 필요가 없음.
    *   단순히 Kinesis 전체에 들어오는 데이터 갯수(`IncomingRecords`)만 확인하면 되므로, **CloudWatch의 5분 단위 `IncomingRecords` 지표(Metric)를 주기적으로 당겨와서 모델에 넣는 구조**가 정석 (서버 부하 "0", 코드 초간소화).
*   **이번 AI 데모 적용 방안**:
    *   데모의 핵심 목적은 "시계열 트렌드를 이용한 이상 탐지 고도화(Prophet 기반)"를 보여주는 데 있음.
    *   CloudWatch 연동 코드를 당장 짜는 것보다는, **"배달앱의 특징을 가진 가상의 시계열 데이터를 실시간처럼 주입하는 Mock 파이프라인"**을 구축하여 AI 모델이 특정 패턴을 얼마나 잘 인지하는지 증명(PoC)하는 것에 집중하기로 결정함.
    *   (추후 실 운용 전환 시: `mock_generator` 모듈을 탈거하고, `boto3 cloudwatch get_metric_data` 호출 모듈로 쉽게 끼워넣기만 하면 되도록 인터페이스 분리)