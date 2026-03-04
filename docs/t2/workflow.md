# 워크플로우 가이드 (통합본)

본 문서는 아래 문서들을 하나로 통합한 버전입니다.

- workflow_init.md
- workflow_p1.md
- workflow_p2.md
- workflow_p3.md
- workflow_p4.md

---

## workflow_init (원문)

<!-- 출처: docs/t2/workflow_init.md -->

# 1. AWS Athena와 Redash란 무엇인가요?
이 두 서비스는 에어플로우가 처리한 데이터를 "사람이 읽을 수 있는 정보"로 만드는 마지막 관문입니다.
- AWS Athena (아테나): "S3 전용 돋보기"
    - 개념: S3라는 창고에 쌓인 수많은 파일(CSV, JSON 등)을 마치 데이터베이스(SQL)처럼 조회할 수 있게 해주는 도구입니다.
    - 특징: 보통 DB는 데이터를 따로 저장해야 하지만, 아테나는 "S3에 있는 파일을 그대로 둔 채" SQL 쿼리문만 던지면 바로 결과를 뽑아줍니다. 서버를 따로 띄울 필요가 없어 입문자가 쓰기에 매우 강력합니다.
- Redash (리대쉬): "데이터 화가"
    - 개념: 아테나가 뽑아준 숫자 데이터를 그래프나 차트로 그려주는 대시보드 도구입니다.
    - 특징: 아테나와 연결해두면 SQL 쿼리 결과를 바탕으로 막대그래프, 파이 차트 등을 만들어 웹 화면에 띄워줍니다.

# 2. 앞으로 진행해야 할 과정 (로드맵)
🛠 AWS Athena & Redash 구축 상세 로드맵
## 1단계: S3 데이터 적재 및 경로 확정
analyzer.py가 생성한 결과물이 S3의 어디에 저장되는지 명확히 해야 합니다. 아테나는 특정 폴더(Prefix) 안에 있는 파일들을 하나의 테이블로 인식합니다.
- 할 일: AWS S3 콘솔에 접속하여 s3://내-버킷-이름/analyzed-data/와 같은 경로에 CSV 또는 Parquet 파일이 있는지 확인합니다.
- 주의사항: 폴더 안에 분석 결과와 상관없는 다른 파일이 섞여 있으면 아테나가 에러를 일으킬 수 있으니, 결과물 전용 폴더를 지정하세요.

## 2단계: AWS Glue를 이용한 메타데이터 등록 (데이터 카탈로그)
설계도 중앙에 있는 AWS Glue Tables 단계입니다. S3에 있는 '파일'을 아테나가 '표(Table)'로 인식하게 설명서를 써주는 과정입니다.
- 방법 A (자동): AWS Glue Crawler를 설정하여 S3 폴더를 스캔하게 합니다. 크롤러가 자동으로 컬럼명(열 이름)과 데이터 타입(숫자, 문자 등)을 찾아내 테이블을 만들어줍니다.
- 방법 B (수동): Athena 화면에서 직접 CREATE EXTERNAL TABLE이라는 SQL 문을 실행하여 테이블 구조를 정의합니다. 입문자에게는 방법 A(크롤러)를 추천합니다.

## 3단계: AWS Athena에서 쿼리 테스트
이제 S3 파일이 DB 테이블처럼 변했습니다. Redash로 가기 전, 데이터가 제대로 나오는지 검증해야 합니다.
- 쿼리 실행: SELECT * FROM 테이블명 LIMIT 10;을 실행하여 데이터가 표 형태로 잘 출력되는지 확인합니다.
- 결과 저장 설정: Athena는 쿼리 결과 자체도 S3에 저장합니다. 설정(Settings) 메뉴에서 쿼리 결과가 저장될 S3 경로를 반드시 지정해 줘야 합니다.

## 4단계: Redash 설치 및 Athena 커넥터 연결
이제 그림을 그릴 도구인 Redash를 준비할 차례입니다.
- 연동 준비: Redash 관리자 페이지의 Data Sources 메뉴에서 Athena를 선택합니다.
- 필요 정보: * AWS Access Key / Secret Key: 권한이 있는 열쇠가 필요합니다.
    - Region: 아테나가 설치된 지역 (예: ap-northeast-2).
    - S3 Staging Path: 3단계에서 설정한 '쿼리 결과 저장 경로'를 적어줍니다.

## 5단계: SQL 작성 및 대시보드 시각화 (최종)
마지막으로 사용자가 볼 화면을 구성합니다.
- New Query: Redash에서 Athena를 소스로 선택하고 SQL을 작성합니다. (예: SELECT date, click_rate FROM analyzed_table)
- Add Visualization: 쿼리 결과 하단의 버튼을 눌러 차트 종류(Line, Bar, Pie 등)를 선택합니다.
- Add to Dashboard: 만든 차트들을 모아서 하나의 대시보드 페이지로 만듭니다.

# 3. 내가 맡은 역할의 전체 흐름 (Flow)
- 작성하신 4개의 파일이 아키텍처 상에서 어떻게 흘러가는지 그 과정을 상세히 짚어드릴게요.

|단계|파일명(Task)|하는 일 (Role)|데이터의위치|
| -- | -- | -- | -- |
|1단계|generate_sample_logs|가짜 광고 로그 데이터를 생성하여 흐름을 시작합니다.|로컬 또는 임시 저장소|
|2단계|processor|생성된 원본 데이터를 정제(Cleaning)합니다.|S3 저장소 (Raw)
|3단계|analyzer|정제된 데이터를 분석하여 통계치(예: 클릭률)를 계산합니다.|S3 저장소 (Processed)|
|4단계|visualize|(에어플로우 상의 역할) 아테나에게 "분석 결과를 조회해줘"라고 명령하거나 리대쉬를 갱신합니다.|Athena / Redash|

💡 입문자를 위한 상세 흐름도
- Airflow가 스케줄에 맞춰 generate_sample_logs부터 visualize까지 순차적으로 실행합니다.
- 이 과정에서 만들어진 최종 데이터는 Amazon S3에 파일 형태로 저장됩니다.
- AWS Athena는 S3에 저장된 파일을 읽어서 SQL 문법으로 변환해 대기합니다.
- Redash가 Athena에게 "최신 클릭률 데이터를 보내줘!"라고 요청하면, Athena가 결과값을 전달합니다.
- 사용자는 웹 브라우저를 통해 Redash가 그려준 예쁜 그래프를 보게 됩니다.

---

## workflow_p1 (원문)

<!-- 출처: docs/t2/workflow_p1.md -->

📍 1단계: S3 데이터 적재 및 경로 확정 (상세 가이드)
1. S3 버킷(Bucket) 구조 설계하기
S3는 윈도우의 폴더와 비슷합니다. 하지만 아테나가 데이터를 효율적으로 읽게 하려면 폴더 구조를 미리 정하는 것이 좋습니다.

권장 경로 구조: s3://capa-logs-dev-ap-northeast-2/data/analyzed_results/year=2025/month=11/day=25/

이유: 나중에 데이터가 많아졌을 때 아테나가 특정 날짜 데이터만 골라 읽을 수 있어 비용과 시간을 아낄 수 있습니다 (이를 '파티셔닝'이라고 합니다).

2. analyzer.py 코드 내 저장 로직 확인
비전공자 입장에서 코드를 볼 때, 다음의 두 가지 핵심 요소가 포함되어 있는지 확인하세요.

저장 포맷: 보통 CSV나 Parquet 형식을 사용합니다.

Boto3 라이브러리: 파이썬으로 AWS S3에 파일을 전송할 때 사용하는 도구입니다.

[코드 예시 설명] 만약 파이드를 통해 데이터를 처리했다면, 대략 이런 흐름의 코드가 들어있어야 합니다.

Python
import boto3 # AWS와 통신하는 도구
변수명은 사용자님의 코드에 맞춰져 있어야 합니다.
.bucket_name = "my-airflow-bucket" file_name = "analysis_result.csv" s3_path = f"data/analyzed_results/{file_name}"

S3로 파일을 보내는 명령어
s3 = boto3.client('s3') s3.upload_file(local_file_path, bucket_name, s3_path)

3. AWS 콘솔에서 직접 눈으로 확인하기
코드가 실행된 후, 실제 파일이 있는지 숨바꼭질을 끝내야 합니다.

AWS 로그인 후 S3 서비스로 이동합니다.

사용자님이 설정한 버킷 이름을 클릭합니다.

analyzer.py에서 지정한 경로(폴더)를 차례대로 클릭하여 들어갑니다.

최종적으로 .csv 또는 .parquet 파일이 생성되어 있는지, 그리고 '수정 시간'이 현재 시간과 일치하는지 확인합니다.

⚠️ 1단계에서 자주 발생하는 실수 (Troubleshooting)
권한 문제 (IAM Error): 에어플로우가 설치된 컴퓨터(또는 EC2)가 S3에 파일을 쓸 수 있는 권한이 없으면 로그에 Access Denied가 뜹니다.

경로 오타: s3://my-bucket인데 코드에는 s3://my_bucket으로 적는 등 작은 오타로 인해 파일이 엉뚱한 곳에 생기거나 에러가 날 수 있습니다.

빈 파일 저장: 분석 결과가 0건인데 파일만 만들어지는 경우입니다. S3에서 파일 용량이 0 Byte가 아닌지 확인하세요.

📝 현재 확인해 보실 사항
S3 버킷 이름을 이미 만드셨나요?

analyzer.py 코드 마지막에 파일을 저장하는 경로가 어떻게 적혀 있나요?

이 두 가지만 확인되면 바로 2단계(AWS Glue 설정)로 넘어가서 아테나가 이 파일을 읽을 수 있게 만들 수 있습니다. 파일 저장 경로 코드를 복사해서 보여주시면 더 정확히 봐드릴 수 있어요! 구체적인 데이터 적재 과정을 시각화한 자료는 아래와 같습니다.

---

## workflow_p2 (원문)

<!-- 출처: docs/t2/workflow_p2.md -->

📍 2단계: AWS Glue 크롤러(Crawler) 설정하기
크롤러는 S3 폴더를 직접 돌아다니며 데이터의 구조(컬럼명, 데이터 타입)를 파악해 데이터 카탈로그(표 명세서)를 자동으로 만들어줍니다.

① Glue 데이터베이스 생성
먼저 테이블들이 담길 '바구니'인 데이터베이스를 만들어야 합니다.

AWS Glue 콘솔 접속 -> 왼쪽 메뉴에서 Databases 클릭.

Add database 버튼 클릭.

이름 입력 (예: my_analysis_db) 후 생성.

② 크롤러(Crawler) 생성 및 실행
왼쪽 메뉴에서 Crawlers 클릭 -> Create crawler 버튼 클릭.

Crawler name 입력 (예: s3_analysis_crawler).

Data source 설정:

Add a data source 클릭.

S3 경로에 아까 1단계에서 확인한 결과물 폴더 경로를 선택합니다. (예: s3://내-버킷-이름/data/analyzed_results/)

IAM Role(권한) 설정:

Create new IAM role을 선택해 이름을 지어줍니다. (이 역할은 크롤러가 S3에 접근할 수 있는 열쇠가 됩니다.)

Output database 설정:

위에서 만든 my_analysis_db를 선택합니다.

완료 및 실행:

설정을 마치고 생성된 크롤러를 선택한 뒤 Run crawler를 누릅니다.

상태가 Running에서 Stopping, 그리고 Ready가 될 때까지 기다립니다 (보통 1~2분 소요).

🔍 결과 확인: "테이블이 생겼나요?"
크롤러 실행이 끝나면 왼쪽 메뉴의 Tables를 확인해 보세요.

사용자가 지정한 S3 폴더 이름과 비슷한 이름의 테이블이 생성되어 있을 것입니다.

해당 테이블을 클릭하면 id, click_count, date 처럼 컬럼명(Schema)이 자동으로 들어와 있는 것을 볼 수 있습니다.

⚠️ 입문자가 주의할 점 (변수 유지 원칙)
사용자님의 원칙인 "변수는 절대 임의로 변경하지 않는다"를 지키기 위해 주의할 점이 있습니다.

컬럼 이름: analyzer.py에서 저장한 CSV 파일의 첫 줄(헤더)이 영어라면, Glue는 그 영어를 그대로 컬럼명으로 가져옵니다. 만약 한글이라면 깨지거나 임의의 이름(col0, col1...)으로 바뀔 수 있으니 영문 헤더를 권장합니다.

데이터 타입: 숫자가 적힌 열을 Glue가 '문자(String)'로 오해할 때가 있습니다. 나중에 Redash에서 계산(합계 등)을 하려면 여기서 '숫자(Bigint/Double)'로 되어 있는지 꼭 눈으로 확인해야 합니다.

---

## workflow_p3 (원문)

<!-- 출처: docs/t2/workflow_p3.md -->

📍 3단계: AWS Athena에서 쿼리 테스트
아테나는 서버가 없는(Serverless) 서비스라, 우리가 SQL 문법으로 "데이터 보여줘!"라고 요청할 때만 동작합니다.

① Athena 서비스 접속 및 설정
AWS 콘솔에서 Athena를 검색해 들어갑니다.

Query Editor 탭을 클릭합니다.

(중요) Settings 설정: 처음 사용하신다면 Settings 탭에서 'Query result location'을 설정해야 합니다. 아테나가 조회한 결과를 임시로 저장할 S3 경로를 지정해 주는 과정입니다 (예: s3://내-버킷-이름/athena-results/).

② 데이터베이스 및 테이블 선택
왼쪽 패널의 Database 항목에서 2단계에서 만든 데이터베이스(예: my_analysis_db)를 선택합니다.

그 아래 Tables 목록에 Glue 크롤러가 만든 테이블 이름이 보이는지 확인합니다.

③ 첫 번째 쿼리 실행 (데이터 확인)
테이블 이름 옆의 점 세 개(⋮) 버튼을 누르고 Preview Table을 클릭하거나, 직접 아래 쿼리를 입력창에 쓰고 Run을 누릅니다.

SQL
-- 테이블 내의 모든 데이터를 10줄만 보여달라는 명령어입니다.
-- 변수명이나 테이블명은 Glue에서 생성된 것을 그대로 사용하세요.
SELECT * FROM "capa_db"."ad_logs" 
LIMIT 10;
④ 결과 확인 및 검증
하단 Results 창에 엑셀 표처럼 데이터가 예쁘게 나오나요? 여기서 다음을 체크해야 합니다.

데이터가 비어있지 않은지: 1단계에서 S3에 올린 내용이 그대로 보이는지 확인합니다.

컬럼명이 정확한지: analyzer.py에서 의도한 변수명들이 열 제목으로 잘 들어가 있는지 확인합니다.

📍 4단계: Redash 설치 및 Athena 연동 (예고)
아테나에서 데이터가 잘 나오는 것을 확인했다면, 이제 이 데이터를 시각화 도구인 Redash로 보낼 차례입니다.

연결에 필요한 정보 (미리 챙겨두세요)
Redash 설정 화면에서 아래 정보들을 입력해야 하므로 메모해 두시는 것이 좋습니다.

AWS Access Key / Secret Key: 아테나에 접근할 권한이 있는 사용자 키.

Region: 아테나를 실행 중인 지역 (예: ap-northeast-2).

Database: 아까 만든 my_analysis_db.

S3 Staging Path: 위 ①번에서 설정한 athena-results 경로.

💡 입문자를 위한 팁
만약 아테나에서 Zero records returned (결과 없음)이 뜬다면, 2단계 크롤러가 S3 경로를 잘못 짚었거나 파일 형식을 오해했을 가능성이 큽니다. 이럴 때는 당황하지 말고 2단계의 크롤러 설정 정보를 다시 한번 살펴보면 됩니다.

이제 아테나에서 데이터가 표 형태로 잘 보이시나요? 성공하셨다면 이제 마지막 관문인 Redash 연동으로 넘어가 보겠습니다! 진행하시면서 막히는 화면이나 에러 메시지가 있다면 말씀해 주세요.

---

## workflow_p4 (원문)

<!-- 출처: docs/t2/workflow_p4.md -->

📍 4단계: Redash 설치 및 Athena 연동
① Redash 설치 (환경 준비)
보통 Redash는 직접 설치하기보다는 도커(Docker)를 이용하거나 AWS 상에 이미 만들어진 이미지를 사용합니다. 만약 개인 컴퓨터에서 연습 중이시라면 Docker Compose를 사용하는 것이 가장 빠릅니다.

② Data Source 연결 (아테나와 리대쉬 잇기)
Redash를 실행한 후 웹 화면에 접속하여 아테나의 데이터를 가져올 수 있도록 통로를 뚫어줘야 합니다.

Settings (우측 상단 아이콘) -> Data Sources 메뉴로 들어갑니다.

+ New Data Source 버튼을 누르고 검색창에 "Amazon Athena"를 입력해 선택합니다.

설정 값 입력 (매우 중요): 여기서 변수명을 정확히 입력해야 합니다.

Name: 이 연결의 이름 (예: My_Athena_Source)

AWS Access Key / Secret Key: AWS에서 발급받은 권한 키를 입력합니다.

AWS Region: 아테나가 있는 지역 (예: ap-northeast-2)

S3 Staging Path: 3단계에서 설정했던 아테나 쿼리 결과 저장 경로를 입력합니다 (예: s3://내-버킷-이름/athena-results/).

Database: Glue에서 만든 데이터베이스 이름 (예: my_analysis_db).

Test Connection: 하단의 버튼을 눌러 Success가 뜨는지 확인합니다.

📍 5단계: 쿼리 작성 및 시각화 (마지막 단계)
연결이 성공했다면 이제 실제 대시보드를 만들 차례입니다.

① 쿼리 작성 (Create Query)
상단 메뉴에서 Create -> Query를 선택합니다.

왼쪽 소스에서 아까 만든 My_Athena_Source를 선택합니다.

중앙 입력창에 아테나에서 테스트했던 SQL을 그대로 적습니다.

SQL
SELECT * FROM "생성된_테이블_이름"
Execute를 눌러 아래에 표 데이터가 잘 불러와지는지 확인합니다.

② 시각화 추가 (Add Visualization)
표 바로 아래에 있는 + Add Visualization 버튼을 누릅니다.

Visualization Type에서 원하는 형태(Bar, Line, Pie 등)를 고릅니다.

X Column: 날짜나 카테고리 변수 선택

Y Column: 숫자 데이터(클릭 수, 매출 등) 선택

우측 하단의 Save를 누르면 그래프가 저장됩니다.

③ 대시보드 구성 (Dashboards)
Create -> Dashboard를 클릭해 이름을 짓습니다.

Add Widget 버튼을 눌러 방금 만든 쿼리 그래프를 추가합니다.

마우스로 크기를 조절하여 설계도에 있던 '데이터 대시보드'를 완성합니다.

🏁 전체 과정 복습
이제 사용자님이 맡으신 모든 흐름이 연결되었습니다!

Airflow: 데이터를 만들어서 S3에 넣고 (analyzer.py)

Glue: 그 데이터가 어떤 구조인지 카탈로그를 만들고

Athena: SQL로 데이터를 조회할 수 있게 준비하고

Redash: 그 데이터를 그래프로 그려서 화면에 띄웁니다.

💡 최종 팁
"데이터가 업데이트되지 않아요!" 라는 문제가 발생한다면, 에어플로우 스케줄에 맞춰 Redash의 쿼리도 자동 갱신(Refresh Schedule)되도록 설정해 보세요. 쿼리 편집 화면 하단에서 Refresh Schedule을 설정할 수 있습니다.
