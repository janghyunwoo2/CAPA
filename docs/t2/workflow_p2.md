📍 2단계: AWS Glue 크롤러(Crawler) 설정하기
크롤러는 S3 폴더를 직접 돌아다니며 데이터의 구조(컬럼명, 데이터 타입)를 파악해 **데이터 카탈로그(표 명세서)**를 자동으로 만들어줍니다.

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

해당 테이블을 클릭하면 id, click_count, date 처럼 **컬럼명(Schema)**이 자동으로 들어와 있는 것을 볼 수 있습니다.

⚠️ 입문자가 주의할 점 (변수 유지 원칙)
사용자님의 원칙인 **"변수는 절대 임의로 변경하지 않는다"**를 지키기 위해 주의할 점이 있습니다.

컬럼 이름: analyzer.py에서 저장한 CSV 파일의 첫 줄(헤더)이 영어라면, Glue는 그 영어를 그대로 컬럼명으로 가져옵니다. 만약 한글이라면 깨지거나 임의의 이름(col0, col1...)으로 바뀔 수 있으니 영문 헤더를 권장합니다.

데이터 타입: 숫자가 적힌 열을 Glue가 '문자(String)'로 오해할 때가 있습니다. 나중에 Redash에서 계산(합계 등)을 하려면 여기서 '숫자(Bigint/Double)'로 되어 있는지 꼭 눈으로 확인해야 합니다.