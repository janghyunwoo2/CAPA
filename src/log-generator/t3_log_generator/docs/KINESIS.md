# Kinesis 연동 가이드

## 🎯 개요

`t3_log_generator`는 AWS Kinesis Data Stream으로 실시간 로그 전송을 지원합니다.

## 📋 사전 준비

### 1. AWS Kinesis Stream 생성

**AWS 콘솔:**
1. [Kinesis Console](https://console.aws.amazon.com/kinesis) 접속
2. 리전: **ap-northeast-2** (서울) 선택
3. **"데이터 스트림 생성"** 클릭
4. 설정:
   - 스트림 이름: `capa-ad-logs-dev`
   - 용량 모드: **온디맨드**
5. **"생성"** 클릭

### 2. AWS 자격증명 발급

**IAM Console:**
1. [IAM Console](https://console.aws.amazon.com/iam) 접속
2. 좌측 메뉴: **"사용자"** 클릭
3. 본인 사용자 클릭
4. **"보안 자격 증명"** 탭
5. **"액세스 키 만들기"** 클릭
6. 용도: **"로컬 코드"** 선택
7. 생성된 키 복사:
   - Access Key ID: `AKIA...`
   - Secret Access Key: `wJalr...`

## ⚙️ 설정

### `.env` 파일 생성

프로젝트 루트에 `.env` 파일 생성:

```bash
# Kinesis 설정
ENABLE_KINESIS=true
KINESIS_STREAM_NAME=capa-ad-logs-dev
AWS_REGION=ap-northeast-2

# AWS 자격증명
AWS_ACCESS_KEY_ID=AKIA여기에실제키입력
AWS_SECRET_ACCESS_KEY=wJalr여기에실제시크릿키입력

# 로그 생성 설정 (선택)
# USERS_COUNT=200
# SHOPS_COUNT=30
```

## 🚀 실행

### Kinesis 전송 활성화

```bash
uv run main.py
```

**출력:**
```
============================================================
🚀 Ad Log Generator 시작
============================================================
✅ 로그 생성기 초기화 완료 (유저: 200, 가게: 30)
✅ Kinesis 전송 활성화: capa-ad-logs-dev (ap-northeast-2)
============================================================
📊 로그 생성 시작...

{"event_type": "impression", ...}
{"event_type": "click", ...}
```

### Kinesis 비활성화 (로컬 테스트)

`.env` 파일 수정:
```bash
ENABLE_KINESIS=false
```

→ stdout으로만 출력 (Kinesis 전송 안 함)

## 📊 확인 방법

### 1. AWS 콘솔 - 모니터링

1. [Kinesis Console](https://console.aws.amazon.com/kinesis) 접속
2. `capa-ad-logs-dev` 클릭
3. **"모니터링"** 탭
4. **"수신 데이터 합계"** 그래프 확인
   - 그래프가 올라가면 성공! 📈

### 2. 프로그램 종료 시 통계

```bash
# Ctrl + C로 종료
```

**출력:**
```
============================================================
🛑 로그 생성 중지됨

📊 Kinesis 전송 통계:
  - 성공: 1192
  - 실패: 0
  - 전체: 1192
============================================================
```

## 💰 비용

### Kinesis Data Stream (ON_DEMAND)

- **PUT 요청**: $0.014 / 1,000 레코드
- **데이터 저장**: 시간당 $0.023 / GB (24시간 보관)

### 예상 비용

| 실행 시간 | 레코드 수 | 비용 (USD) | 비용 (KRW) |
|----------|----------|-----------|-----------|
| 1시간 | ~10,000 | $0.15 | ~200원 |
| 24시간 | ~240,000 | $3.60 | ~4,800원 |
| 한 달 | ~7,200,000 | $108 | ~144,000원 |

**무료 티어:** 월 100만 건 무료 (12개월)

## 🔧 문제 해결

### "Stream not found" 에러

→ AWS 콘솔에서 `capa-ad-logs-dev` 스트림이 생성되었는지 확인

### "Access Denied" 에러

→ `.env` 파일의 AWS 자격증명 확인
→ IAM 권한 확인 (`kinesis:PutRecord`, `kinesis:DescribeStream`)

### 성공: 0, 실패: 0

→ `.env`에서 `ENABLE_KINESIS=false`로 되어 있을 수 있음

## 🎯 다음 단계

### Firehose 설정 (S3 자동 저장)

> **ℹ️ 자세한 Firehose, S3, Glue 설정 방법은 [INFRASTRUCTURE.md](INFRASTRUCTURE.md) 문서를 참고하세요.**

1. Kinesis Firehose 생성
2. 소스: `capa-ad-logs-dev`
3. 대상: S3 버킷
4. 변환: JSON → Parquet

### Terraform으로 관리

```bash
cd infra/terraform/environments/dev
terraform init
terraform import module.kinesis.aws_kinesis_stream.ad_logs_stream capa-ad-logs-dev
```

## 📝 참고

- **샤드(Shard)**: 데이터를 나눠 담는 통. 같은 `user_id`는 같은 샤드로 전송됨
- **PartitionKey**: `user_id`를 사용하여 샤드 분산
- **데이터 보관**: 24시간 (기본값)
