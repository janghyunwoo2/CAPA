FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
# Manually install dependencies since we are not using a complex build system yet, or we can use pip
# We'll just use pip with the dependencies listed in pyproject.toml for simplicity in this MVP
RUN pip install boto3>=1.34.0 faker>=30.0.0

COPY main.py .

# Environment variables (default values, can be overridden)
ENV PYTHONUNBUFFERED=1
ENV AWS_REGION=ap-northeast-2
ENV STREAM_NAME=capa-stream

CMD ["python", "main.py"]
