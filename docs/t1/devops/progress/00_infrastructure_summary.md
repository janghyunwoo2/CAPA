# 🏁 CAPA 프로젝트 종합 인프라 및 서비스 명세서

본 문서는 CAPA 프로젝트의 전체 인프라 자원, 통합 서비스 엔드포인트 및 접속 정보를 포함합니다. **비용 효율적인 단일 ALB(Application Load Balancer) 기반의 통합 아키텍처**로 구성되어 있습니다.

---

## 🚀 1. 통합 서비스 엔드포인트 (Public)
모든 외부 접속 서비스는 하나의 로드밸런서(ALB) 주소를 공유하며, 경로(Path)를 통해 구분됩니다.

| 서비스 명 | 접속 URL | 계정 정보 | 비고 |
| :--- | :--- | :--- | :--- |
| **📊 Redash (BI)** | [바로가기](http://k8s-capaunifiedlb-ab7aaac323-480086301.ap-northeast-2.elb.amazonaws.com/) | `ehrtk2003@gmail.com` / `admin123!` | 통합 ALB 루트 접속 |
| **🌬️ Airflow** | [바로가기](http://k8s-capaunifiedlb-ab7aaac323-480086301.ap-northeast-2.elb.amazonaws.com/airflow/) | `admin` / `admin` | `/airflow/` 경로 필수 (슬래시 포함) |

> **ALB DNS**: `k8s-capaunifiedlb-ab7aaac323-480086301.ap-northeast-2.elb.amazonaws.com`

---

## 🤖 2. 백엔드 및 AI 서비스 (Internal Only)
보안 및 비용 절감을 위해 클러스터 내부 통신(`ClusterIP`)으로만 노출됩니다.

| 서비스 명 | 내부 DNS URL | ECR 리포지토리 주소 | 비고 |
| :--- | :--- | :--- | :--- |
| **Vanna AI API** | `http://vanna-api.vanna.svc.cluster.local:8000` | `.../capa-vanna-api` | 자연어 SQL 질의 엔진 |
| **Report Generator** | `http://report-generator.report.svc.cluster.local:8000` | `.../capa-report-generator` | PDF/Excel 리포트 생성기 |
| **Slack Bot** | `http://slack-bot.slack-bot.svc.cluster.local:3000` | `.../capa-slack-bot` | 슬랙 인터페이스 서버 |
| **ChromaDB** | `http://chromadb.chromadb.svc.cluster.local:8000` | - | 벡터 데이터베이스 |

---

## 📊 3. 데이터 파이프라인 및 스토리지 (AWS)
| 구분 | 리소스 명 | 식별자 / ARN | 상세 정보 |
| :--- | :--- | :--- | :--- |
| **Stream** | `capa-stream` | `arn:aws:kinesis:...:stream/capa-stream` | 실시간 광고 로그 수집 |
| **Firehose** | `capa-firehose` | Delivery Stream: `capa-firehose` | S3 가공 적재 (Parquet) |
| **Data Lake** | `capa-data-lake-xxx` | `s3://capa-data-lake-827913617635` | 원천/분석 데이터 저장소 |
| **Glue/Athena** | `capa_db` | Table: `ad_events_raw` | 무중단 쿼리를 위한 카탈로그 |

---

## 🔔 4. 모니터링 및 알림 (AWS)
| 구분 | 알람 명칭 | 감시 기준 | 알림 타겟 |
| :--- | :--- | :--- | :--- |
| **SNS Topic** | `capa-alerts-dev` | 장애 발생 시 알림 발송 | 팀원 지정 이메일/채널 |
| **EKS CPU** | `capa-eks-node-cpu-high` | Node CPU > 80% | 고부하 발생 시 경고 |
| **트래픽 저하** | `capa-kinesis-low-traffic` | 수집 트래픽 비정상 감소 | 데이터 소스 입력 이상 감지 |

---

## 🔑 5. 주요 IAM 역할 및 보안
| 역할(Role) | ARN | 용도 |
| :--- | :--- | :--- |
| **ALB Controller** | `arn:aws:iam::...:role/capa-aws-load-balancer-controller-role` | 로드밸런서 자동 관리 권한 |
| **Airflow IRSA** | `arn:aws:iam::...:role/capa-airflow-role` | 파드 내 Athena/S3 접근 권한 |
| **Redash IRSA** | `arn:aws:iam::...:role/capa-redash-role-northeast-2` | 대시보드 데이터 조회 권한 |

---
**최종 업데이트**: 2026-02-19 (로드밸런서 통합 및 비용 최적화 완료)
