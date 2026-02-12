# ✅ 작업 08 완료: Log Generator 및 데이터 파이프라인 검증

**작업 파일**: [`08_log_generator.md`](../work/08_log_generator.md)
**Phase**: 1 (DevOps & Data Pipeline)
**실행 일시**: 2026-02-12 15:30 - 16:10
**결과**: ✅ **성공**

---

## 📋 실행 내용

### 1. Log Generator 구현 (`services/log-generator/`)

**주요 파일**:
- `main.py` (135줄) - 가상 광고 데이터(Impression, Click, Conversion) 생성 및 Kinesis 전송 로직
- `Dockerfile` - Python 3.9 기반 실행 환경 정의
- `pyproject.toml` - 의존성 관리 (`boto3`, `faker`)

**주요 로직**:
- **데이터 생성**: Faker 라이브러리를 이용해 현실적인 유저/광고 데이터 생성
- **확률 모델**: CTR 10%, CVR 20% 확률로 클릭/전환 이벤트 연쇄 생성
- **Kinesis 연동**: `boto3`를 통해 `capa-stream`으로 JSON 데이터 전송

---

### 2. 발생 이슈 및 해결 (Troubleshooting)

| 이슈 | 증상 | 원인 | 해결 |
|------|------|------|------|
| **1. 인코딩 에러** | Windows에서 `UnicodeEncodeError` 발생 | 이모지(🚀 등) 출력 호환성 문제 | 이모지를 텍스트(`[OK]`)로 대체하여 해결 |
| **2. 스키마 불일치** | Firehose 처리 실패 (`DataFormatConversion.MalformedData`) | Timestamp가 String으로 전송됨 (Glue는 BigInt 기대) | `datetime.now().timestamp() * 1000` (밀리초 Int)로 변환 |
| **3. 필드 불일치** | Firehose 처리 실패 | `platform` 필드명 불일치, 불필요 필드 존재 | `platform` -> `device_type` 변경, Glue 스키마에 정의된 필드만 전송 |

---

### 3. 검증 결과

#### ✅ Kinesis -> Firehose -> S3 적재 확인
- **S3 경로**: `s3://capa-data-lake-xxx/raw/year=2026/month=02/day=12/`
- **파일 포맷**: Parquet (Snappy 압축)
- **확인 내용**:
    - `main.py` 수정 후 생성된 데이터가 정상적으로 Parquet 파일로 저장됨.
    - 예: `capa-firehose-1-2026-02-12-07-03-59...parquet`

#### ⚠️ 에러 로그 분석 (잔존 데이터)
- **현상**: `errors/` 폴더에 `format-conversion-failed` 로그 존재.
- **분석**: 에러 로그 내 데이터의 타임스탬프가 **코드 수정 전(16:04 이전)** 데이터임.
- **결론**: Firehose 버퍼에 남아있던 과거 데이터가 뒤늦게 처리되면서 발생한 것으로, 현재 코드는 정상 작동 중임.

---

## ✅ 성공 기준 달성

- [x] Python Log Generator 구현 (`main.py`)
- [x] 의존성 라이브러리 설치 (`boto3`, `faker`)
- [x] Kinesis Stream으로 데이터 전송 성공
- [x] Firehose를 통한 S3 Parquet 변환 및 적재 성공
- [x] Glue Data Catalog 스키마 준수 확인

---

## 🎯 작업 완료

**Log Generator 및 데이터 파이프라인 검증 완료**:
1. ✅ `Log Generator`가 생성한 데이터가 Kinesis로 유입됨.
2. ✅ Kinesis Firehose가 데이터를 Glue 스키마에 맞춰 변환(JSON -> Parquet).
3. ✅ S3 Data Lake (`raw/`)에 시간 파티션(`year/month/day`)별로 적재됨.

**참고 사항**:
- 추후 `CALIIncidentSimulator`(인프라 장애 시뮬레이터) 도입 시, 별도의 Glue 테이블 및 파이프라인 구성이 필요할 수 있음. (현재는 광고 데이터 전용)

---

**작업 완료 시각**: 2026-02-12 16:10
