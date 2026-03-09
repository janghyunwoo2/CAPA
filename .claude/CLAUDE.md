# CAPA 프로젝트 - Claude Code 설정

## 프로젝트 개요

**CAPA (Cloud-native AI Pipeline for Ad-logs)**
온라인 광고 로그(impression → click → conversion)를 실시간 수집·처리·분석하는 AWS 기반 데이터 파이프라인 플랫폼.

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| 언어 | Python 3.11+ |
| 인프라 (IaC) | Terraform 1.0+ |
| 워크플로우 | Apache Airflow 2.7+ |
| 컨테이너 | Docker / Kubernetes 1.28+ |
| 클라우드 | AWS (Kinesis, S3, Glue, Athena, EKS, ECR) |
| AI 분석 | Vanna, Pydantic AI |
| BI | Redash (Athena 연동) |

## 디렉토리 구조 요약

```
CAPA/
├── services/               # 애플리케이션 서비스
│   ├── log-generator/      # 광고 로그 시뮬레이터
│   ├── airflow-dags/       # Airflow DAG 정의
│   ├── data_pipeline_t2/   # 데이터 처리 파이프라인
│   ├── vanna-api/          # AI Text-to-SQL API
│   ├── report-generator/   # 리포트 생성 서비스
│   └── slack-bot/          # Slack 알림 봇
├── infrastructure/         # 인프라 코드
│   ├── terraform/          # AWS 리소스 IaC
│   └── helm-values/        # Kubernetes Helm 설정
├── docs/                   # 프로젝트 문서
│   ├── t1/                 # t1(본인) 담당 문서
│   ├── t2/                 # t2 팀원 담당 문서
│   └── t3/                 # t3 팀원 담당 문서
└── .github/                # CI/CD, 프로젝트 규칙
```

# [통합 개발 및 에이전트 규칙]
## 2. 코딩 및 작업 원칙
- **언어**: 모든 답변과 설명은 반드시 **한국어**로 작성한다.
- **계획 우선**: 복잡한 작업은 코드를 작성하기 전 **[작업 계획]**을 요약하여 승인받는다.
- **기술 스택**: 항상 **안정성이 보장된 최신 버전(Stable/LTS)**을 기준으로 제안한다. 하위 호환성을 고려하며, 업계 표준(Best Practice)이 되는 최신 기법을 우선 사용한다.
- **최소 수정**: 요청받은 목적에 집중하며, 관련 없는 불필요한 코드 수정은 지양한다.
- **안정성**: 모든 비동기 로직(`async/await`)에는 반드시 `try-catch` 에러 핸들링을 포함한다.
- **타입 엄격**: TypeScript 작성 시 `any` 사용을 금지하며, 명확한 Interface 및 Type을 정의한다.
- **의존성 확인**: 수정 전 반드시 파일 간 의존성을 확인하고 사이드 이펙트를 고려한다.
- **자기 검증**: 코드를 출력하기 전, 스스로 로직 오류나 타입 위반이 없는지 최종 검토한다.
- **객관적 비판**: 사용자의 의견이나 로직이 기술적으로 최선이 아니라고 판단될 경우, 무조건 동의하지 말고 객관적인 근거와 함께 더 나은 대안을 제시한다.

# [팩트 및 데이터 엄격성 준수 규칙 (Hallucination 방지)]

1. **최신 데이터 검색 강제:** AWS 요금, 환율, 제품 스펙 등 변동성이 있는 데이터나 정확한 수치를 요구받을 경우, 내부 학습 데이터에 의존하지 말고 **반드시 웹 검색을 통해 최신 공식 자료를 먼저 확인**하라.
2. **출처 및 기준일 명시:** 수치 데이터를 제공할 때는 반드시 기준이 되는 공식 출처(URL), 기준 리전, 그리고 검색 기준일을 명시하라.
3. **투명한 계산 과정 증명:** 비용이나 수치를 계산할 때는 결론만 던지지 말고, `(시간당 단가) x (대수) x (기준 시간) = (총액)` 처럼 중간 계산식을 빠짐없이 시각적으로 나열하라.
4. **사용자 의도 영합 금지 (Fact-Only):** 사용자가 특정 결과(예: "더 저렴한 것", "더 빠른 것")를 원하더라도, 이를 맞추기 위해 숫자를 조작하거나 억지로 끼워 맞추지 마라. 결과가 사용자의 기대와 다르더라도 오직 팩트 기반의 정확한 수치만을 건조하게 제공하라.
5. **엄격한 무지(Ignorance) 인정:** 웹 검색으로도 정확한 최신 단가를 찾을 수 없거나 계산에 확신이 없다면, 절대 비슷한 숫자로 유추하거나 지어내지 마라. "현재 정확한 단가를 확인할 수 없어 계산이 불가능합니다"라고 단호하게 답변하라.

## 커밋 메시지 규칙

```
<type>(<scope>): <subject>

<body>
```

- `feat`: 새로운 기능
- `fix`: 버그 수정
- `docs`: 문서 수정
- `refactor`: 리팩토링
- `test`: 테스트 코드
- `chore`: 빌드/설정 변경

**예시**: `feat(log-generator): impression 이벤트에 device_type 필드 추가`

## 브랜치 전략

```
main (프로덕션)
  └── develop (통합)
        ├── feat/<담당자>/<기능명>   # 예: feat/t1/Text2SQL
        ├── fix/<담당자>/<버그명>
        └── refactor/<담당자>/<대상>
```

## 자주 발생하는 실수 (팀 경험 기반)

- ❌ AWS boto3 호출 시 `try-except` 누락 사례 있음
  → async 여부와 관계없이 모든 boto3 API 호출은 `ClientError` try-except 필수
- ❌ FastAPI async 엔드포인트 반환 타입 누락 사례 있음
  → `@app.get/post` 함수는 `-> 반환타입` 또는 `response_model` 필수
- ❌ Docker 이미지 `latest` 태그 사용 사례 있음
  → 유틸 이미지(`curlimages/curl` 등)도 반드시 버전 명시 (예: `curlimages/curl:8.5.0`)

## 참고 문서

- [세부 코딩 규칙](.claude/rules/coding-rules.md)
