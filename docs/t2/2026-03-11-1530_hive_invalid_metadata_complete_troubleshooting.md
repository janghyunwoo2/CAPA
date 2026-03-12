# HIVE_INVALID_METADATA: 테이블 중복 컬럼 오류 쉬운 해결 가이드

**작성일**: 2026-03-11 15:30 (KST)  
**문제**: Athena 테이블 조회 시 "중복 컬럼" 오류 발생  
**해결**: 3가지 간단한 단계로 완전히 해결 가능

---

## 🎯 한눈에 보는 요약

| 항목 | 설명 |
|------|------|
| **오류 메시지** | `HIVE_INVALID_METADATA: Table descriptor contains duplicate columns` |
| **의미** | "같은 이름의 컬럼이 2번 정의되었다"는 뜻 |
| **원인** | 파티션 정보를 실수로 중복 저장 |
| **해결 시간** | 약 1-2시간 (간단함) |
| **난이도** | ⭐⭐☆☆☆ (중상) |

---

## � 문제를 쉽게 이해하기

### 📖 비유로 설명 (음식점 주문 시스템)

생각해보세요. 음식점에서:

```
❌ 잘못된 방법:
1. 주문표에 "주문 번호: 123"이라고 적음
2. 음식과 함께 "주문 번호: 123"이라는 종이를 또 포함함
3. 손님 입장: "어? 주문 번호가 왜 2번이야?" → 혼동

✅ 올바른 방법:
1. 주문표에만 "주문 번호: 123"이라고 적음
2. 음식은 순수 음식만 담음
3. 주문 번호는 상자 겉에 라벨로 붙임
4. 손님 입장: "깔끔하네!"
```

**우리 상황도 같습니다:**
- **주문 번호** = 파티션 정보 (year, month, day, hour)
- **음식** = 실제 데이터 (impression_id, user_id, 등등)
- **상자** = Parquet 파일

---

### 🔴 실제 오류 상황

```
❌ 현재 발생하는 상황:

┌─────────────────────────────────────────────────┐
│  CREATE TABLE 정의                               │
│  ├─ 데이터 컬럼: impression_id, user_id, ... (27개)
│  └─ 파티션: year, month, day, hour            │
│     "이 정보는 파일 경로에서만 읽을 거야"      │
└─────────────────────────────────────────────────┘

❌ 그런데 실제 저장된 파일:
┌─────────────────────────────────────────────────┐
│  Parquet 파일 안의 데이터                        │
│  ├─ impression_id, user_id, ... (27개)
│  ├─ year ← 이걸 또 저장했네?                  │
│  ├─ month ← 이것도 또?                        │
│  ├─ day ← 또?                                 │
│  └─ hour ← 또?                                │
│                                                 │
│  "어? 같은 정보가 2번이네!" → 오류!           │
└─────────────────────────────────────────────────┘
```

---

## 🔍 왜 이런 오류가 발생했나?

### 🎬 문제가 발생하는 과정

```
Step 1️⃣: SELECT 쿼리를 실행
┌────────────────────────────────┐
│ SELECT                           │
│   impression_id,                │
│   user_id,                      │
│   ... 27개 데이터 ...            │
│   '2026' AS year,    ← 문제!   │
│   '03' AS month,     ← 문제!   │
│   '11' AS day,       ← 문제!   │
│   '14' AS hour       ← 문제!   │
│ FROM impressions                │
│ LEFT JOIN clicks ...            │
└────────────────────────────────┘
        ↓ 결과: 31개 컬럼

Step 2️⃣: DataFrame으로 변환
┌────────────────────────────────┐
│ 데이터셋:                        │
│ - impression_id, user_id, ...  │
│ - year, month, day, hour       │
│   (총 31개 컬럼)                │
└────────────────────────────────┘
        ↓

Step 3️⃣: Parquet 파일로 저장
┌────────────────────────────────┐
│ 저장된 파일 (year=2026/month=03/...) │
│ 내용:                            │
│ - 27개 데이터 컬럼               │
│ - year, month, day, hour       │
│   (파일 안에도 있음!)           │
└────────────────────────────────┘
        ↓

Step 4️⃣: Athena가 검증할 때
┌────────────────────────────────┐
│ Athena의 검증:                  │
│                                 │
│ 테이블 정의 ↔ 실제 파일          │
│ "year는 파티션에만              │
│  있어야 하는데..."              │
│                                 │
│ → "어? 파일 안에도              │
│    year이 있네??"               │
│                                 │
│ ❌ HIVE_INVALID_METADATA!      │
└────────────────────────────────┘
```

### 💡 핵심 원인 (아주 간단함!)

**문제**: SQL 쿼리에서 year, month, day, hour을 `SELECT`에 포함시킴

```sql
-- ❌ 잘못된 쿼리
SELECT 
    impression_id,
    user_id,
    ... 27개 ...
    '2026' AS year,    ← 이 4줄이 문제!
    '03' AS month,
    '11' AS day,
    '14' AS hour
FROM impressions ...

-- ✅ 올바른 쿼리
SELECT 
    impression_id,
    user_id,
    ... 27개 ...
    -- year, month, day, hour은 SELECT에서 빼기!
FROM impressions ...
```

**파티션 정보는:**
- ✅ 파일 경로에는 있어야 함: `/year=2026/month=03/day=11/hour=14/`
- ❌ 파일 내용에는 없어야 함

---

## 🔧 해결 방법 (3가지 간단한 단계)

### ✋ 잠깐! 먼저 이것부터

```
현재 코드에서 문제점을 찾아 수정하는 것이 가장 중요합니다.
아래 3단계를 차례대로 따라가면 됩니다.
```

---

## 📝 Step 1️⃣: 코드 수정 (가장 중요!)

### hourly_etl.py 수정

**파일**: `services/data_pipeline_t2/etl_summary_t2/hourly_etl.py`

**찾을 부분**: `generate_hourly_etl_query()` 함수

**현재 코드 (❌ 잘못됨)**:
```python
def generate_hourly_etl_query(self) -> str:
    query = f"""
    SELECT 
        imp.impression_id,
        imp.user_id,
        ... (27개 데이터 컬럼) ...
        clk.is_click,
        
        '{self.year}' AS year,      ← ❌ 이 4줄 삭제!
        '{self.month}' AS month,    ← ❌ 이 4줄 삭제!
        '{self.day}' AS day,        ← ❌ 이 4줄 삭제!
        '{self.hour}' AS hour       ← ❌ 이 4줄 삭제!
    FROM {DATABASE}.impressions imp
    ...
    """
    return query
```

**수정 후 코드 (✅ 올바름)**:
```python
def generate_hourly_etl_query(self) -> str:
    query = f"""
    SELECT 
        imp.impression_id,
        imp.user_id,
        ... (27개 데이터 컬럼) ...
        clk.is_click
        
        -- year, month, day, hour 제거됨!
    FROM {DATABASE}.impressions imp
    ...
    """
    return query
```

**이유**: 파티션 정보는 파일 경로에만 있으면 되고, SELECT 결과에는 없어야 함!

---

### daily_etl.py 수정

**파일**: `services/data_pipeline_t2/etl_summary_t2/daily_etl.py`

**같은 방식으로 수정**:

**찾을 부분**: `generate_daily_etl_query()` 함수

**제거할 부분**:
```python
# ❌ 이 3줄 삭제
'{self.year}' AS year,
'{self.month}' AS month,
'{self.day}' AS day,
```

**이유**: daily_etl.py도 hourly_etl.py와 동일한 원칙을 적용해야 함

---

## 🧹 Step 2️⃣: S3 정리 (선택사항이지만 권장)

```
Athena가 생성한 임시 CSV 파일들을 정리합니다.
```

**AWS S3 콘솔에서**:
1. S3 버킷 선택
2. `athena-results/` 폴더 또는 `.athena-temp/` 폴더 열기
3. 모든 파일 선택하고 삭제하기

**또는 AWS CLI로**:
```bash
aws s3 rm s3://your-bucket/athena-results/ --recursive
aws s3 rm s3://your-bucket/.athena-temp/ --recursive
```

---

## 🔄 Step 3️⃣: Athena에서 테이블 재생성 (마무리)

**AWS Athena 콘솔에서** 다음을 한 줄씩 실행:

```sql
-- 1️⃣ 기존 테이블 삭제
DROP TABLE IF EXISTS capa_ad_logs.ad_combined_log;

-- 2️⃣ 기존 테이블 삭제
DROP TABLE IF EXISTS capa_ad_logs.ad_combined_log_summary;
```

**그 다음 코드 실행**:
```bash
cd services/data_pipeline_t2

# 수정한 코드 실행 (테이블 자동 재생성)
python -m etl_summary_t2.run_etl hourly
python -m etl_summary_t2.run_etl daily
```

**완료!** 이제 오류가 사라집니다. ✅

---

## ✅ 수정 후 검증

### 확인 방법 1️⃣: Athena에서 테스트

**AWS Athena 콘솔에서 이 쿼리 실행**:

```sql
SELECT COUNT(*) as row_count
FROM capa_ad_logs.ad_combined_log
LIMIT 5;
```

✅ **성공**: 데이터가 보이고 오류 없음  
❌ **실패**: 오류 메시지 표시

---

### 확인 방법 2️⃣: 로그 확인

**터미널에서 코드 실행 후 로그 확인**:

```
✅ 성공한 경우:
INFO:hourly_etl:Processing hour: 2026-03-11-14
INFO:hourly_etl:✅ Table exists
INFO:hourly_etl:✅ Hourly ETL completed

❌ 실패한 경우:
ERROR:athena_utils:HIVE_INVALID_METADATA: ...
```

---

## 🎯 요약: 무엇을 했나?

| 문제 | 원인 | 해결책 |
|------|------|--------|
| **중복 컬럼 오류** | year, month, day, hour을 SELECT에 포함 | SQL에서 제거 |
| **오류 메시지** | `HIVE_INVALID_METADATA` | 코드 수정하면 자동 해결 |
| **S3 파일 쌓임** | Athena 임시 파일들 | 콘솔에서 삭제 |

---

## � 빠른 참고 (한눈에 보기)

### 핵심 규칙

```
✅ 올바른 방식:

CREATE TABLE (year, month, day, hour 포함 안 함)
PARTITIONED BY (year, month, day, hour)

SELECT impression_id, user_id, ... (27개)  ← 파티션 없음!
→ S3에 저장: /year=2026/month=03/.../data.parquet
→ 파일 경로에만 파티션 정보 존재
→ 파일 내용에는 파티션 컬럼 없음
→ ✅ Athena 정상 작동!
```

---

### 체크리스트 (이것만 확인하면 됨)

#### 1. 코드 수정 확인
- [ ] `hourly_etl.py` - SQL에서 year, month, day, hour 제거함
- [ ] `daily_etl.py` - SQL에서 year, month, day 제거함

#### 2. Athena 준비
- [ ] DROP TABLE로 기존 테이블 삭제 (2개)
- [ ] S3에서 `athena-results/` 폴더 삭제 (선택)

#### 3. 코드 실행
- [ ] `python -m etl_summary_t2.run_etl hourly` 실행
- [ ] `python -m etl_summary_t2.run_etl daily` 실행

#### 4. 결과 확인
- [ ] Athena에서 `SELECT COUNT(*) FROM capa_ad_logs.ad_combined_log LIMIT 5;` 실행
- [ ] 데이터가 보이면 성공! ✅

---

## 💬 자주 묻는 질문

### Q. 왜 파티션 컬럼을 SELECT에서 제거해야 하나?
**A.** 파티션 정보는 **파일 경로**에서 자동으로 읽혀서 추가됩니다. SELECT에 포함시키면 중복이 되어 오류 발생합니다.

### Q. 파일 경로에 year=2026이 있는데, 파일 내용에 year이 없으면 괜찮나?
**A.** 맞습니다! Athena가 파일 경로에서 year=2026을 읽고 자동으로 추가합니다. 파일 내용에는 불필요합니다.

### Q. 수정하면 기존 데이터는 어떻게 되나?
**A.** DROP TABLE로 테이블만 삭제되고, S3의 데이터는 그대로 있습니다. 필요하면 S3에서도 삭제할 수 있습니다.

### Q. 얼마나 걸리나?
**A.** 코드 수정(5분) + Athena 작업(10분) + 실행(20-30분) = 약 1시간

---

## 🎓 핵심 학습

| 개념 | 설명 |
|------|------|
| **파티션** | S3의 폴더 구조를 테이블 메타데이터로 변환 |
| **PARTITIONED BY** | "이 폴더 구조들을 파티션으로 사용할거야" 선언 |
| **SELECT 쿼리** | 실제 데이터만 가져옴 (파티션 컬럼 제외) |
| **MSCK REPAIR** | "파일 경로의 파티션들을 메타데이터에 등록해줘" 명령 |

---

**작성자**: AI Assistant  
**최종 업데이트**: 2026-03-11 (한국어, 친절한 설명 버전)
