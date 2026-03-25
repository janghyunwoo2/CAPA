"""
Real-time Ad Impression Anomaly Detector - 실시간 탐지 실행부 (main.py)

동작 흐름:
1. 기존 학습된 모델(.pkl) 로드 (없으면 종료 및 안내)
2. 데이터 소스(Mock 또는 CloudWatch) 연결
3. 실시간 이상 탐지 파이프라인 가동
4. 결과 시각화 및 로그 저장
"""
import json
import logging
import os
import sys
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Union

import matplotlib
matplotlib.use("Agg")  # 헤드리스 환경 대응
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import plotly.graph_objects as go
import pandas as pd

import config
from font_utils import setup_font
from aggregator import FiveMinuteAggregator
from mock_kinesis_source import MockKinesisSource
from cloudwatch_source import CloudWatchSource
from models import IsolationForestDetector, ProphetDetector, ModelError

# 한글 폰트 설정
setup_font()

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(config.OUTPUT_DIR, "anomaly.log"), encoding="utf-8"),
    ],
)

# 세부 로거 로그 레벨 억제
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

OUTPUT_DIR = config.OUTPUT_DIR
MODELS_DIR = "models"
PROPHET_MODEL_PATH = os.path.join(MODELS_DIR, "prophet_model.pkl")
ISO_FOREST_MODEL_PATH = os.path.join(MODELS_DIR, "iso_forest_model.pkl")

@dataclass
class DetectionResult:
    """이상 탐지 결과 보관용 클래스"""
    timestamps: list[datetime] = field(default_factory=list)
    actuals: list[float] = field(default_factory=list)
    predicted: list[float] = field(default_factory=list)
    lowers: list[float] = field(default_factory=list)
    uppers: list[float] = field(default_factory=list)
    anomaly_indices: list[int] = field(default_factory=list)
    anomaly_types: dict[int, str] = field(default_factory=dict)
    anomaly_count: int = 0
    total_windows: int = 0

def save_png(result: DetectionResult) -> None:
    """결과 그래프 PNG 저장"""
    try:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(result.timestamps, result.actuals, label="실제값", color="green", alpha=0.6)
        ax.plot(result.timestamps, result.predicted, label="예측값", color="blue", linestyle="--")
        ax.fill_between(result.timestamps, result.lowers, result.uppers, color="blue", alpha=0.1, label="신뢰구간")

        if result.anomaly_indices:
            anomaly_ts = [result.timestamps[i] for i in result.anomaly_indices]
            anomaly_vals = [result.actuals[i] for i in result.anomaly_indices]
            ax.scatter(anomaly_ts, anomaly_vals, color="red", zorder=5, s=60, label=f"이상치 ({len(result.anomaly_indices)}건)")

        ax.set_title("Ad Impression Anomaly Detection", fontsize=14, fontweight="bold")
        ax.set_xlabel("시각")
        ax.set_ylabel("Impression 수 (5분 단위)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        path = os.path.join(OUTPUT_DIR, "anomaly_result.png")
        plt.savefig(path, dpi=100)
        plt.close(fig)
        logger.info(f"PNG 저장: {path}")
    except Exception as e:
        logger.error(f"PNG 저장 실패: {e}")

def save_html(result: DetectionResult) -> None:
    """Plotly 인터랙티브 HTML 저장"""
    try:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=result.timestamps + result.timestamps[::-1], y=result.uppers + result.lowers[::-1], fill="toself", fillcolor="rgba(0, 0, 255, 0.1)", line=dict(color="rgba(255,255,255,0)"), name="신뢰구간", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=result.timestamps, y=result.predicted, mode="lines", name="예측값", line=dict(color="blue", width=1)))
        fig.add_trace(go.Scatter(x=result.timestamps, y=result.actuals, mode="lines", name="실제값", line=dict(color="green", width=1)))
        if result.anomaly_indices:
            anomaly_vals = [None] * len(result.timestamps)
            anomaly_texts = [None] * len(result.timestamps)
            for i in result.anomaly_indices:
                anomaly_vals[i] = result.actuals[i]
                anomaly_texts[i] = result.anomaly_types[i] if result.anomaly_types else "Anomaly"
            
            # None이 아닌 실제 이상치 포인트에서만 툴팁이 보이도록 설정
            fig.add_trace(go.Scatter(
                x=result.timestamps, 
                y=anomaly_vals, 
                mode="markers", 
                marker=dict(color="red", size=10), 
                name="이상치",
                text=anomaly_texts,
                hovertemplate="<b>[이상치 감지]</b><br>타입: %{text}<br>수치: %{y}<extra></extra>"
            ))
        
        fig.update_layout(
            title="Ad Impression Anomaly Detection (Interactive)", 
            xaxis_title="시각", 
            yaxis_title="Impression 수", 
            hovermode="x", # 통합 모드 대신 개별 X축 고정 모드로 변경 (자석 버그 방지)
            template="plotly_white"
        )
        path = os.path.join(OUTPUT_DIR, "anomaly_interactive.html")
        fig.write_html(path)
        logger.info(f"HTML 저장: {path}")
    except Exception as e:
        logger.error(f"HTML 저장 실패: {e}")

def format_console_line(ts, status, actual, pred, lower, upper, atype):
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
    status_str = f"[{status}{'!' if status == 'ANOMALY' else ' '}]"
    type_info = f"| Type: {atype}" if atype else ""
    return f"[{ts_str}] {status_str:<12} Actual: {actual:6.0f} | Predicted: {pred:6.0f} | Range: ({lower:.0f}, {upper:.0f}) {type_info}"

def load_trained_models():
    """저장된 모델 보관소에서 지능 복구"""
    if not os.path.exists(PROPHET_MODEL_PATH) or not os.path.exists(ISO_FOREST_MODEL_PATH):
        logger.error("=" * 60)
        logger.error("학습된 모델 파일이 없습니다!")
        logger.error("먼저 'python train_model.py'를 실행하여 모델을 훈련시켜주세요.")
        logger.error("=" * 60)
        sys.exit(1)

    prophet = ProphetDetector()
    iso_forest = IsolationForestDetector()
    logger.info("학습된 모델을 로드합니다...")
    prophet.load(PROPHET_MODEL_PATH)
    iso_forest.load(ISO_FOREST_MODEL_PATH)
    logger.info("모델 로드 성공")
    return prophet, iso_forest

def run_detection_pipeline(source: Union[MockKinesisSource, CloudWatchSource], prophet: ProphetDetector, iso_forest: IsolationForestDetector) -> DetectionResult:
    """이상 탐지 파이프라인 실행 루프"""
    result = DetectionResult()
    aggregator = FiveMinuteAggregator(window_size_minutes=config.WINDOW_SIZE_MINUTES)
    jsonl_path = os.path.join(OUTPUT_DIR, "anomaly_log.jsonl")

    logger.info("=" * 60)
    logger.info("실시간 이상 탐지 시작 (콘솔에는 ANOMALY만 출력됩니다)")
    logger.info("=" * 60)

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(jsonl_path, "w", encoding="utf-8") as jsonl_file:
            for record in source:
                window_result = aggregator.add_record(record)
                if window_result is None: continue
                ts, count = window_result
                try:
                    res_dict = prophet.predict(ts, count)
                    status, pred, lower, upper, atype = res_dict["status"], res_dict["predicted"], res_dict["lower"], res_dict["upper"], res_dict["anomaly_type"]
                    
                    if_res = iso_forest.predict(count)
                    if if_res["is_anomaly"] and status == "NORMAL":
                        status, atype = "ANOMALY", "IsoForest Anomaly"

                    result.timestamps.append(ts)
                    result.actuals.append(float(count))
                    result.predicted.append(pred)
                    result.lowers.append(lower)
                    result.uppers.append(upper)

                    if status == "ANOMALY":
                        result.anomaly_indices.append(result.total_windows)
                        result.anomaly_types[result.total_windows] = atype or "Unknown"
                        result.anomaly_count += 1
                        print(format_console_line(ts, status, count, pred, lower, upper, atype))
                    elif result.total_windows % 100 == 0:
                        print(f"[{ts.strftime('%H:%M:%S')}] Processing... ({result.total_windows} windows done)")

                    result.total_windows += 1
                    log_entry = {"timestamp": ts.isoformat(), "actual": count, "predicted": round(pred, 1), "status": status, "anomaly_type": atype}
                    jsonl_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                    jsonl_file.flush()

                    if result.total_windows % config.VISUALIZATION_UPDATE_INTERVAL == 0:
                        save_png(result)
                        save_html(result)

                except ModelError as e:
                    logger.error(f"예측 실패 [{ts}]: {e}")
    except Exception as e:
        logger.error(f"파이프라인 실행 중 오류: {e}")
    
    return result

def main():
    try:
        prophet, iso_forest = load_trained_models()
        if config.DATA_SOURCE == "cloudwatch":
            source = CloudWatchSource()
        else:
            source = MockKinesisSource(history_days=config.HISTORY_DAYS)

        result = run_detection_pipeline(source, prophet, iso_forest)
        
        # 종료 전 최종 저장
        save_png(result)
        save_html(result)
        prophet.save(PROPHET_MODEL_PATH)
        iso_forest.save(ISO_FOREST_MODEL_PATH)
        logger.info("파이프라인 정상 종료")
    except Exception as e:
        logger.error(f"애플리케이션 실패: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
