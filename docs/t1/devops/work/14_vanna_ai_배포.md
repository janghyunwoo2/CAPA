# 14. Vanna AI + ChromaDB 배포 (AI Layer)

> **목표**: 자연어 질의(Text-to-SQL) 처리를 위한 Vanna AI 및 Vector DB 구축
> **참조**: [devops_implementation_guide.md](../devops_implementation_guide.md#14-ai-layer-vanna-ai)
> **소요 시간**: 약 25분

## 1. 사전 준비

- [ ] **OpenAI/Claude API Key**: Secret으로 등록 필요
- [ ] **IAM Role (IRSA)**: `capa-vanna-role` (Athena, S3 권한)
- [ ] **Helm Values 준비**: `helm-values/vanna.yaml`, `helm-values/chromadb.yaml`

## 2. 작업 절차

### 2.1 ChromaDB 배포

**Terraform 파일**: `infrastructure/terraform/environments/dev/apps/helm-chromadb.tf`

```bash
cd infrastructure/terraform/environments/dev/apps
terraform apply -target=helm_release.chromadb
```
- Persistent Volume (EBS)이 정상적으로 바인딩되었는지 확인 (`kubectl get pvc -n chromadb`)

### 2.2 Vanna AI 배포

1. **API Key Secret 생성**:
   ```bash
   kubectl create secret generic vanna-secrets \
     --namespace vanna \
     --from-literal=openai-api-key='sk-...' \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

2. **Terraform 배포**:
   **파일**: `infrastructure/terraform/environments/dev/apps/helm-vanna.tf`
   ```bash
   terraform apply -target=helm_release.vanna
   ```

## 3. 검증

### 3.1 Pod 상태 확인

```bash
kubectl get pods -n chromadb
kubectl get pods -n vanna
```

### 3.2 Vanna API Health Check

```bash
kubectl port-forward -n vanna svc/vanna-api 8000:8000
curl http://localhost:8000/health
```

### 3.3 (Optional) SQL 생성 테스트

- 로컬 Python 스크립트로 Vanna API 호출
- "어제 노출수 알려줘" -> SQL 생성되는지 확인

## 4. 문제 해결

- **ChromaDB 연결 실패**: Vanna Config의 `CHROMADB_HOST` 환경변수 확인 (k8s service name 사용)
- **Athena 쿼리 실패**: IRSA Role (`capa-vanna-role`) 권한 및 Trust Policy 확인
- **API Key 오류**: Secret이 올바르게 마운트되었는지 확인

---

- **이전 단계**: [13_report_generator_배포.md](./13_report_generator_배포.md)
- **다음 단계**: [15_slack_bot_echo.md](./15_slack_bot_echo.md)
