# Task 14: Vanna AI & ChromaDB 배포 완료 보고서 (Complete)

## 📋 최종 작업 요약
- **작업 완료 일자**: 2026-02-15
- **현재 상태**: **완료 (Done)** 🚀
- **주요 결과물**:
  - **AI Layer 서비스**: Vanna AI (`vanna` namespace) + ChromaDB (`chromadb` namespace)
  - **Vector DB 구축**: Helm을 이용한 ChromaDB 단독 인스턴스 구축 (EBS 5Gi)
  - **LLM 연동**: Anthropic Claude 3.5 Sonnet 연동 완료
  - **데이터 연동**: AWS Athena IRSA 연동을 통한 실데이터 조회 환경 구성 완료

## 🛠️ 작업 내용 상세

### 1. 애플리케이션 및 DB 구축
- **Vanna AI API**: FastAPI 기반으로 구축 (`services/vanna-api`)
  - **버전**: v0.7.9 (Chromadb 모듈 호환성 문제로 하이브리드 안정 버전 선택)
- **ChromaDB**: 공식 Helm Chart를 사용하여 별도 네임스페이스에 구축
  - **스토리지**: EBS `gp2` StorageClass를 활용한 5Gi 볼륨 할당
  - **연결**: 내부 DNS `chromadb.chromadb.svc.cluster.local`을 통해 API와 연결

### 2. 보안 및 권한 설정
- **Secret 관리**: Anthropic API Key를 K8s Secret으로 생성하여 Pod 환경 변수로 자동 주입
- **IAM (IRSA)**: `capa-vanna-role`에 Athena 및 S3 ReadOnly 권한을 부여하여 별도 인증키 없이 AWS 데이터에 접근

## 🚧 주요 트러블슈팅 사례

| 이슈 | 원인 | 해결 방법 |
| :--- | :--- | :--- |
| **ModuleNotFoundError** | Vanna 2.0 버전의 라이브러리 파편화 | `vanna==0.7.9`로 버전 고정하여 `vanna.chromadb` 모듈 복구 |
| **Helm Repo URL 오류** | 잘못된 차트 저장소 주소 사용 | `https://amikos-tech.github.io/chromadb-chart/`로 저장소 정정 및 재배포 |
| **ChromaDB 연결 실패** | 서비스 이름 및 호스트명 불일치 | `CHROMA_HOST`를 `chromadb.chromadb`로 수정하여 상호 연결 성공 |
| **DB 빌드 에러** | Docker 빌드 환경 리소스 부족 | 베이스 이미지를 `python:3.11` Full 버전으로 변경하여 컴파일 라이브러리 확보 |

## ✅ 최종 검증 결과
- **ChromaDB 상태**: `Bound` (PVC 5Gi), `Running` (Pod) 확인
- **Vanna API 상태**: `Running` 상태 및 `/health` 호출 시 `{"status":"ok"}` 응답 확인
- **연동 테스트**: Vanna API 로그를 통해 ChromaDB 및 Athena 연결 초기화 확인

## 🔗 관련 자원
- **Namespace**: `vanna`, `chromadb`
- **Internal API**: `http://vanna-api.vanna.svc.cluster.local:8000`
- **Terraform Config**: `10-applications.tf` (Helm), `11-k8s-apps.tf` (Deployment)
