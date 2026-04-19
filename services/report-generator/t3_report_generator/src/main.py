from fastapi import FastAPI, BackgroundTasks
from datetime import datetime
import logging
import os
import requests
import json
from athena_utils import AthenaClient

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CAPA Report Generator",
    description="Scheduled report generation service with AI insights",
    version="1.1.0",
)

# 환경 변수 로드
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
ATHENA_DATABASE = os.getenv("GLUE_DATABASE") or os.getenv("ATHENA_DATABASE", "capa_db")
GLUE_TABLE = os.getenv("GLUE_TABLE", "ad_combined_log_summary")

# Athena 결과 저장 경로 (ATHENA_S3_OUTPUT 우선, 없을 경우 REPORT_S3_BUCKET 기반 생성)
ATHENA_S3_OUTPUT = os.getenv("ATHENA_S3_OUTPUT")
REPORT_S3_BUCKET = os.getenv("REPORT_S3_BUCKET")

if ATHENA_S3_OUTPUT:
    S3_STAGING_DIR = ATHENA_S3_OUTPUT
elif REPORT_S3_BUCKET:
    S3_STAGING_DIR = f"s3://{REPORT_S3_BUCKET}/athena-results/"
else:
    S3_STAGING_DIR = None

VANNA_API_URL = os.getenv(
    "VANNA_API_URL", "http://vanna-api.vanna.svc.cluster.local:8000"
)

# Athena 클라이언트 초기화
athena = None
if S3_STAGING_DIR:
    athena = AthenaClient(ATHENA_DATABASE, S3_STAGING_DIR, AWS_REGION)
else:
    logger.warning("Neither ATHENA_S3_OUTPUT nor REPORT_S3_BUCKET is set. Athena queries will fail.")


def generate_report_task(report_type: str, target_date: str = None):
    """실제 리포트 생성 및 분석 로직"""
    try:
        logger.info(
            f"Starting report generation task for type: {report_type}, date: {target_date}"
        )

        # 1. 날짜 설정 (파라미터가 있으면 사용, 없으면 오늘)
        if target_date:
            try:
                date_obj = datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError:
                logger.error(f"Invalid date format: {target_date}. Using today.")
                date_obj = datetime.now()
        else:
            date_obj = datetime.now()

        year, month, day = (
            date_obj.strftime("%Y"),
            date_obj.strftime("%m"),
            date_obj.strftime("%d"),
        )

        query = f"""
        SELECT 
            COUNT(DISTINCT impression_id) as impressions,
            SUM(CASE WHEN is_click = TRUE THEN 1 ELSE 0 END) as clicks,
            SUM(CASE WHEN conversion_type = 'purchase' AND is_click = TRUE THEN conversion_value ELSE 0 END) as total_revenue
        FROM {ATHENA_DATABASE}.{GLUE_TABLE}
        WHERE year = '{year}' AND month = '{month}' AND day = '{day}'
        """

        if not athena:
            raise Exception("Athena client not initialized")

        df = athena.run_query(query)

        if df.empty:
            logger.warning("No data found for today's report")
            stats = {"impressions": 0, "clicks": 0, "revenue": 0}
        else:
            stats = {
                "impressions": int(df.iloc[0]["impressions"])
                if df.iloc[0]["impressions"]
                else 0,
                "clicks": int(df.iloc[0]["clicks"]) if df.iloc[0]["clicks"] else 0,
                "revenue": float(df.iloc[0]["total_revenue"])
                if df.iloc[0]["total_revenue"]
                else 0.0,
            }

        logger.info(f"Retrieved stats: {stats}")

        # 2. Vanna AI를 통한 인사이트 생성
        insight = "AI 분석을 수행하지 못했습니다."
        try:
            vanna_prompt = f"당신은 CAPA 서비스의 데이터 분석 마케터입니다. 아래의 {year}년 {month}월 {day}일자 광고 성과 지표(노출, 클릭, 매출)를 보고, 현재 성과가 어떤지 분석하고 향후 개선 방향을 제안하는 짤막한 리포트를 한국어로 작성해 주세요.\n데이터: {stats}"
            response = requests.post(
                f"{VANNA_API_URL}/summarize", json={"text": vanna_prompt}, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                insight = result.get("answer", insight)
            else:
                logger.error(
                    f"Summarize API error: {response.status_code} - {response.text}"
                )
        except Exception as e:
            logger.error(f"Failed to call Vanna API: {e}")

        # 3. 최종 리포트 구성
        final_report = {
            "title": f"Daily Performance Report ({year}-{month}-{day})",
            "stats": stats,
            "ai_insight": insight,
            "generated_at": datetime.now().isoformat(),
        }

        logger.info(
            f"FINAL REPORT: {json.dumps(final_report, ensure_ascii=False, indent=2)}"
        )

        # 4. Slack으로 전송
        SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
        SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

        if SLACK_BOT_TOKEN and SLACK_CHANNEL_ID:
            slack_message = (
                f"📊 *{final_report['title']}*\n\n"
                f"*핵심 지표:*\n"
                f"- 노출: {stats['impressions']:,}회\n"
                f"- 클릭: {stats['clicks']:,}회\n"
                f"- 매출: {stats['revenue']:,.2f}원\n\n"
                f"*🤖 AI 인사이트:*\n"
                f"{insight}\n\n"
                f"_{final_report['generated_at']}_"
            )

            try:
                response = requests.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    json={"channel": SLACK_CHANNEL_ID, "text": slack_message},
                    timeout=10,
                )
                if response.json().get("ok"):
                    logger.info("Successfully sent report to Slack")
                else:
                    logger.error(f"Failed to send report to Slack: {response.text}")
            except Exception as e:
                logger.error(f"Error sending message to Slack: {e}")
        else:
            logger.warning(
                "SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not set. Skipping Slack delivery."
            )

    except Exception as e:
        logger.error(f"Error in generate_report_task: {e}")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "report-generator",
        "timestamp": datetime.utcnow().isoformat(),
        "athena_config": {"db": ATHENA_DATABASE, "staging": S3_STAGING_DIR},
    }


@app.get("/")
async def root():
    return {"message": "CAPA Report Generator API", "version": "1.1.0"}


@app.post("/generate")
async def generate_report(
    background_tasks: BackgroundTasks, report_type: str = "daily", date: str = None
):
    """리포트 생성 트리거"""
    logger.info(f"Report generation endpoint called: {report_type}, date: {date}")
    background_tasks.add_task(generate_report_task, report_type, date)
    return {
        "status": "accepted",
        "report_type": report_type,
        "date": date,
        "message": "Report generation task started in background",
        "timestamp": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
