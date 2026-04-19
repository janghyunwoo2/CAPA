# Report Generator Service
# 개발 담당: Backend Developer
# 작업: 13_report_generator_배포.md (Phase 3)

본 디렉토리에는 Report Generator API 소스 코드가 위치합니다.

## 디렉토리 구조 (예정)
```
report-generator/
├── Dockerfile
├── requirements.txt
├── src/
│   ├── main.py (FastAPI)
│   ├── athena_client.py
│   └── report_builder.py 
└── README.md
```

## 작업 순서
1. Health Check API 구현 (MVP)
2. Athena 쿼리 실행 기능
3. 리포트 생성 로직 (PDF/Markdown)
4. LLM 인사이트 생성 연동
