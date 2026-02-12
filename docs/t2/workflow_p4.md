📍 4단계: Redash 설치 및 Athena 연동
① Redash 설치 (환경 준비)
보통 Redash는 직접 설치하기보다는 **도커(Docker)**를 이용하거나 AWS 상에 이미 만들어진 이미지를 사용합니다. 만약 개인 컴퓨터에서 연습 중이시라면 Docker Compose를 사용하는 것이 가장 빠릅니다.

② Data Source 연결 (아테나와 리대쉬 잇기)
Redash를 실행한 후 웹 화면에 접속하여 아테나의 데이터를 가져올 수 있도록 통로를 뚫어줘야 합니다.

Settings (우측 상단 아이콘) -> Data Sources 메뉴로 들어갑니다.

+ New Data Source 버튼을 누르고 검색창에 **"Amazon Athena"**를 입력해 선택합니다.

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

마우스로 크기를 조절하여 설계도에 있던 **'데이터 대시보드'**를 완성합니다.

🏁 전체 과정 복습
이제 사용자님이 맡으신 모든 흐름이 연결되었습니다!

Airflow: 데이터를 만들어서 S3에 넣고 (analyzer.py)

Glue: 그 데이터가 어떤 구조인지 카탈로그를 만들고

Athena: SQL로 데이터를 조회할 수 있게 준비하고

Redash: 그 데이터를 그래프로 그려서 화면에 띄웁니다.

💡 최종 팁
"데이터가 업데이트되지 않아요!" 라는 문제가 발생한다면, 에어플로우 스케줄에 맞춰 Redash의 쿼리도 자동 갱신(Refresh Schedule)되도록 설정해 보세요. 쿼리 편집 화면 하단에서 Refresh Schedule을 설정할 수 있습니다.