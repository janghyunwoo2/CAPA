# [배포 기록] EKS 프로덕션 배포 — vanna-api & slack-bot

| 항목 | 내용 |
|------|------|
| **Feature** | eks-production-deployment |
| **배포일** | 2026-03-27 |
| **배포자** | t1 |
| **참조 설계서** | `02-design/features/eks-production-deployment.design.md` |

---

## 1. 배포 결과

| 체크포인트 | 결과 | 비고 |
|-----------|------|------|
| variables.tf 변수 9개 추가 | ✅ | |
| terraform.tfvars 기존 4개 수정 + 신규 9개 추가 | ✅ | |
| 11-k8s-apps.tf ENV 추가 (vanna-api 7개, slack-bot 2개) | ✅ | |
| vanna-api Docker 이미지 빌드 & ECR 푸시 | ✅ | 1.3GB (CPU torch 전환 후) |
| slack-bot Docker 이미지 빌드 & ECR 푸시 | ✅ | |
| terraform apply | ✅ | 0 added, 4 changed, 0 destroyed |
| vanna-api 파드 상태 | ✅ | Running 1/1 |
| slack-bot 파드 상태 | ✅ | Running 1/1 |
| ChromaDB 시딩 | ✅ | DDL 2개, Documentation 32개, QA 75개 |

---

## 2. 트러블슈팅 기록

### 이슈 1 — Docker 이미지 5GB (ephemeral-storage 초과로 파드 Evicted)

**현상**
- 새 파드가 스케줄링 후 즉시 Evicted
- `Warning Evicted: The node was low on resource: ephemeral-storage. Threshold: 2146223340, available: 1889624Ki`
- Karpenter가 노드를 2개 추가 (불필요한 비용 발생)

**원인**
- `requirements.txt`의 `sentence-transformers`가 PyTorch CUDA 버전을 자동 설치
- torch CUDA: ~2.5GB → 전체 이미지 5GB

**해결**
- `requirements.txt`에 CPU 전용 torch 명시 설치
  ```
  --extra-index-url https://download.pytorch.org/whl/cpu
  torch
  sentence-transformers>=2.6.1
  ```
- 이미지 크기: **5GB → 1.3GB** (74% 감소)
- EKS는 GPU 없는 CPU 환경이므로 CUDA 불필요, 동작 동일

**추가 정리**
- `einops` 제거: jina-reranker 전용이었으나 `RERANKER_ENABLED=false`로 미사용
- `respx` 제거: 테스트 전용 mock 라이브러리 → `tests/requirements-test.txt`로 분리

---

### 이슈 2 — terraform apply Unauthorized (EKS 인증 토큰 만료)

**현상**
- `terraform apply` 9분 경과 후 `Error: Unauthorized` 발생
- `kubernetes_deployment.vanna_api` 수정 실패

**원인**
- 이슈 1의 파드 Evicted로 인해 apply가 장시간 대기
- EKS 인증 토큰 유효시간(15분) 초과

**해결**
- 이미지 크기 문제 해결 후 `terraform plan` 재생성 → `terraform apply` 재실행
- 재실행 시 2분26초 내 완료

---

### 이슈 3 — ChromaDB 임베딩 함수 불일치 오류

**현상**
```
ValueError: Embedding function name mismatch: sentence_transformer != default
```

**원인**
- 기존 ChromaDB 컬렉션이 `default` 임베딩 함수로 생성되어 있었음
- `seed_chromadb.py`의 `reset_collections()`가 잘못된 컬렉션명으로 삭제 시도
  - 삭제 시도: `sql-collection`, `documentation-collection` (404 — 존재 안함)
  - 실제 컬렉션명: `sql`, `documentation`, `ddl` (하이픈 없음)
- 기존 컬렉션(`default` ef)이 남아있는 상태에서 `sentence_transformer` ef로 접근 → 충돌

**해결**
- 기존 컬렉션 전체 수동 삭제 후 재시딩
  ```bash
  kubectl exec -n vanna deployment/vanna-api -- python -c \
    "import chromadb; c = chromadb.HttpClient(host='chromadb.chromadb.svc.cluster.local', port=8000); \
     [c.delete_collection(col.name) for col in c.list_collections()]"
  kubectl exec -n vanna deployment/vanna-api -- python scripts/seed_chromadb.py
  ```

**백로그**
- `seed_chromadb.py`의 `reset_collections()` 함수에서 삭제 대상 컬렉션명 수정 필요
  - 현재: `["sql-collection", "documentation-collection"]`
  - 수정 필요: `["sql", "documentation", "ddl"]`

---

## 3. 최종 시딩 결과

```
✓ ChromaDB 시딩 완료!
  - DDL: 2개 테이블 (ad_combined_log, ad_combined_log_summary)
  - Documentation: 32개 항목 (7개 카테고리)
  - QA 예제: 75개 (CTR/CVR/TOP-N/기간비교/지역기기 패러프레이징 포함)
  - 테스트 쿼리: '어제 클릭률을 구해줘' ✓ / 'CTR을 계산하는 방법은?' ✓ / 'ROAS가 높은 캠페인을 찾아줘' ✓
```

---

## 4. 변경된 파일 목록

| 파일 | 변경 내용 |
|------|---------|
| `infrastructure/terraform/variables.tf` | 신규 변수 9개 추가 |
| `infrastructure/terraform/terraform.tfvars` | 기존 4개 값 수정 + 신규 9개 추가 |
| `infrastructure/terraform/11-k8s-apps.tf` | vanna-api ENV 7개 + slack-bot ENV 2개 추가 |
| `services/vanna-api/Dockerfile` | Reranker 모델 다운로드 주석처리 |
| `services/vanna-api/requirements.txt` | CPU torch 전환, einops/respx 제거 |
| `services/vanna-api/tests/requirements-test.txt` | 신규 생성 (테스트 전용 의존성 분리) |

---

## 5. E2E 검증 결과

| 테스트 | 결과 | 비고 |
|--------|------|------|
| 단일 쿼리 | ✅ | SQL 생성 + Redash 실행 + 결과 반환 정상 |
| 3회 연속 쿼리 | ✅ | 비동기 처리 정상, 전부 성공 |
| DynamoDB 이력 저장 | ✅ | `capa-dev-query-history` 레코드 적재 확인 |
| async-tasks 상태 업데이트 | ✅ | IAM 수정 후 정상 |
| 채널 분리 | ✅ | T2S 봇은 멘션 채널에 응답, 리포트는 Airflow `SLACK_CHANNEL_ID`로 분리 가능 |

**배포 완료일: 2026-03-27**

---

## 6. 추가 트러블슈팅 기록

### 이슈 4 — DynamoDB async-tasks IAM 미적용으로 타임아웃

**현상**
- Slack에서 `AI 서버 응답 시간이 초과되었습니다` 오류
- vanna-api 로그: `AccessDeniedException: dynamodb:UpdateItem on capa-dev-async-tasks`

**원인**
- `async-tasks` 테이블이 Terraform state 외부에 존재 → IAM 정책에 ARN 미포함
- task 상태가 `running`에서 `completed`로 업데이트 불가 → slack-bot 310초 폴링 후 타임아웃

**해결**
- `terraform import aws_dynamodb_table.async_tasks capa-dev-async-tasks`로 기존 테이블 Terraform 관리로 전환
- `13-dynamodb.tf` IAM 정책 Resource에 `async-tasks` ARN 추가
- `terraform apply` → No changes (테이블 구조 그대로, 태그만 추가)

---

### 이슈 5 — ChromaDB 컬렉션 UUID 불일치 (파드 재시작 후)

**현상**
- RAG 검색 실패: `Collection [uuid] does not exists`

**원인**
- `kubectl rollout restart` 후 새 파드가 시딩 전 초기화된 파드의 old UUID 참조

**해결**
- `kubectl rollout restart deployment/vanna-api` → 새 파드가 ChromaDB에서 정확한 UUID 재취득
- 재시딩 불필요 (ChromaDB PVC에 데이터 보존)

---

## 7. 백로그

- [ ] `seed_chromadb.py` `reset_collections()` 컬렉션명 버그 수정 (`sql-collection` → `sql`, `documentation-collection` → `documentation`)
