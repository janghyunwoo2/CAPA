# CAPA 프로젝트 종합 인프라 및 서비스 명세서

본 문서는 CAPA 프로젝트의 전체 인프라 자원과 서비스 엔드포인트 정보를 포함합니다. 팀원 간 협업 및 서비스 연동 시 아래 정보를 참조하시기 바랍니다.

---

## 1. 🤖 AI 애플리케이션 및 서비스 (EKS)
| 서비스 명 | 내부 접속 URL (Internal DNS) | ECR 리포지토리 URL | 비고 |
| :--- | :--- | :--- | :--- |
| **Vanna AI API** | `http://vanna-api.vanna.svc.cluster.local:8000` | `827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-vanna-api` | Text-to-SQL 서비스 |
| **Report Generator** | `http://report-generator.report.svc.cluster.local:8000` | `827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-report-generator` | 데이터 리포트(PDF/Excel) 생성 |
| **Slack Bot** | `http://slack-bot.slack-bot.svc.cluster.local:3000` | `827913617635.dkr.ecr.ap-northeast-2.amazonaws.com/capa-slack-bot` | 슬랙 인터페이스 대화형 지원 |
| **ChromaDB** | `http://chromadb.chromadb.svc.cluster.local:8000` | - | 지식 베이스 벡터 데이터베이스 |
| **Airflow** | `http://a015fd856c89f45b8a62247f8b61fc74-2092633233.ap-northeast-2.elb.amazonaws.com:8080` | - | 데이터 파이프라인 스케줄러 (admin/admin) |

---

## 2. 📊 데이터 파이프라인 및 스토리지 (AWS)
| 구분 | 리소스 명 | 식별자 / ARN |
| :--- | :--- | :--- |
| **Kinesis Stream** | `capa-stream` | `arn:aws:kinesis:ap-northeast-2:827913617635:stream/capa-stream` |
| **Kinesis Firehose** | `capa-firehose` | Delivery Stream Name: `capa-firehose` |
| **S3 Data Lake** | `capa-data-lake-827913617635` | `arn:aws:s3:::capa-data-lake-827913617635` |
| **Glue Database** | `capa_db` | Athena 쿼리용 데이터베이스 카탈로그 |
| **Glue Table** | `ad_events_raw` | 기초 광고 로그 원천 데이터 테이블 |

---

## 3. 🔔 모니터링 및 알림 설정
| 구분 | 리소스 명 / 알람 목적 | ARN / 상세 정보 |
| :--- | :--- | :--- |
| **SNS Topic** | `capa-alerts-dev` | `arn:aws:sns:ap-northeast-2:827913617635:capa-alerts-dev` |
| **CPU 알람** | `capa-eks-node-cpu-high-dev` | EKS 작업 노드 CPU 고부하 감시 (80% 이상) |
| **Kinesis 알람** | `capa-kinesis-low-traffic-dev` | 데이터 수집 트래픽 비정상 저하 감시 |
| **Firehose 알람** | `capa-firehose-delivery-failure-dev` | S3 데이터 전송 실패 여부 감시 |

---

## 4. 🔑 권한 및 인프라 역할 (IAM)
| 역할(Role) 명 | ARN | 용도 |
| :--- | :--- | :--- |
| **EKS Cluster Role** | `arn:aws:iam::827913617635:role/capa-eks-cluster-role` | EKS 클러스터 제어 평면 권한 |
| **EKS Node Role** | `arn:aws:iam::827913617635:role/capa-eks-node-role` | EKS 작업 노드 및 파드 실행 권한 |
| **Firehose Role** | `arn:aws:iam::827913617635:role/capa-firehose-role` | Kinesis 데이터를 S3에 쓰기 위한 권한 |

---
*최종 업데이트: 2026-02-15*
