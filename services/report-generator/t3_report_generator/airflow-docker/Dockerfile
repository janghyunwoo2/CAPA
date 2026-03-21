FROM apache/airflow:2.9.3

USER root

# 나눔고딕 폰트 설치
RUN apt-get update && apt-get install -y fonts-nanum && apt-get clean

USER airflow

# requirements.txt 복사
COPY requirements.txt /requirements.txt

# PDF 생성 및 차트 라이브러리 설치
RUN pip install --no-cache-dir -r /requirements.txt
