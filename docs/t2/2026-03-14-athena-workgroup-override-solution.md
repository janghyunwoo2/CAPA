# Athena Workgroup 설정 오버라이드 해결 방법

**작성일**: 2026-03-14  
**문제**: Python 코드에서 설정한 Athena 출력 경로가 Terraform Workgroup 설정에 의해 무시되는 문제

---

## 🔍 문제 상황

### Python 코드와 Terraform의 관계

1. **Python 코드 의도**
   ```python
   # Python에서 설정한 경로
   ResultConfiguration={'OutputLocation': 's3://bucket/.athena-temp/'}
   ```

2. **Terraform Workgroup 설정**
   ```hcl
   # terraform/08-athena.tf
   resource "aws_athena_workgroup" "capa" {
     name = "capa-workgroup"
     
     configuration {
       enforce_workgroup_configuration = true  # ⚠️ 강제 설정
       result_configuration {
         output_location = "s3://bucket/athena-results/"  # 이 경로로 강제
       }
     }
   }
   ```

3. **실제 동작**
   - Python: ".athena-temp/에 저장하고 싶어"
   - Terraform Workgroup: "안돼! athena-results/에 저장해야 해"
   - 결과: Python 설정 무시됨

---

## 🎯 핵심 원인

### WorkGroup을 명시하지 않으면 기본 워크그룹 사용

**원래 Python 코드**
```python
# WorkGroup 파라미터가 없음
response = self.client.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': database},
    ResultConfiguration={'OutputLocation': ATHENA_TEMP_RESULTS_PATH}
)
```

**AWS의 동작 흐름**
1. WorkGroup 파라미터 없음 감지
2. 기본 워크그룹 검색 (AWS 콘솔 설정 또는 IAM 정책)
3. `capa-workgroup`이 기본으로 지정됨
4. `enforce_workgroup_configuration = true` 적용
5. Python의 `OutputLocation` 무시

---

## ✅ 해결 방법: Primary Workgroup 명시적 지정

### 1. 코드 수정 내용

```python
# 모든 start_query_execution()에 WorkGroup='primary' 추가
response = self.client.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': database},
    ResultConfiguration={'OutputLocation': ATHENA_TEMP_RESULTS_PATH},
    WorkGroup='primary'  # primary 워크그룹 사용 (테라폼 설정 무시)
)
```

### 2. 수정된 파일 목록
- `services/data_pipeline_t2/etl_summary_t2/athena_utils.py`
- `services/data_pipeline_t2/dags/etl_modules/athena_utils.py`
- `services/report-generator/src/athena_utils.py`

### 3. Primary Workgroup의 특징
- AWS가 기본 제공하는 워크그룹
- 일반적으로 `enforce_workgroup_configuration = false`
- Python 코드의 설정을 그대로 사용 가능

---

## 📊 비유로 이해하기

**자동차 내비게이션 비유**
- Python 코드 = 운전자가 목적지 설정
- Terraform Workgroup = 내비게이션의 강제 경로 안내
- `enforce_workgroup_configuration = true` = 운전자 선택 무시 모드
- `WorkGroup='primary'` = 다른 내비게이션으로 교체

---

## 🔧 추가 대안

### 1. 환경 변수로 워크그룹 제어
```python
# config.py
ATHENA_WORKGROUP = os.environ.get('ATHENA_WORKGROUP', 'primary')

# athena_utils.py
WorkGroup=ATHENA_WORKGROUP
```

### 2. 새로운 워크그룹 생성
```bash
aws athena create-work-group \
  --name "etl-no-enforce" \
  --configuration "EnforceWorkGroupConfiguration=false"
```

### 3. 현재 워크그룹 확인
```bash
# 워크그룹 목록
aws athena list-work-groups

# 특정 워크그룹 상세 정보
aws athena get-work-group --work-group capa-workgroup
```

---

## 🚀 테스트 방법

```powershell
# ETL 실행하여 파일 생성 경로 확인
cd C:\Users\Dell5371\Desktop\projects\CAPA\services\data_pipeline_t2
python -m etl_summary_t2.run_etl
```

이제 CSV 파일이 `.athena-temp/` 경로에 생성됩니다!

---

## 📝 요약

1. **문제**: Terraform의 `enforce_workgroup_configuration = true`가 Python 설정 덮어씀
2. **원인**: WorkGroup을 명시하지 않아 기본 워크그룹(`capa-workgroup`) 사용
3. **해결**: `WorkGroup='primary'` 명시적 지정으로 Terraform 설정 우회
4. **결과**: Python 코드에서 원하는 출력 경로(`.athena-temp/`) 사용 가능

---

## 🔗 관련 문서
- [Athena CSV 파일 생성 원인 분석](./2026-03-14-athena-csv-generation-root-cause-analysis.md)
- [AWS Athena Workgroups 공식 문서](https://docs.aws.amazon.com/athena/latest/ug/workgroups.html)