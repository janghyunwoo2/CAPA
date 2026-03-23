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
import threading
import importlib
import logging.config
from datetime import datetime, timedelta
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
from slack_notifier import SlackNotifier

# 한글 폰트 설정
setup_font()

# OUTPUT_DIR 미리 생성 (logging 초기화 전)
os.makedirs(config.OUTPUT_DIR, exist_ok=True)

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
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
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
        t_ts = result.timestamps
        t_actuals = result.actuals
        t_predicted = result.predicted
        t_lowers = result.lowers
        t_uppers = result.uppers

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(t_ts, t_actuals, label="실제값", color="green", alpha=0.6)
        ax.plot(t_ts, t_predicted, label="예측값", color="blue", linestyle="--")
        ax.fill_between(t_ts, t_lowers, t_uppers, color="blue", alpha=0.1, label="신뢰구간")

        valid_anomalies = result.anomaly_indices
        if valid_anomalies:
            anomaly_ts = [result.timestamps[i] for i in valid_anomalies]
            anomaly_vals = [result.actuals[i] for i in valid_anomalies]
            ax.scatter(anomaly_ts, anomaly_vals, color="red", zorder=5, s=60, label=f"이상치 ({len(valid_anomalies)}건)")

        ax.set_title("Ad Impression Anomaly Detection", fontsize=14, fontweight="bold")
        ax.set_xlabel("시각")
        ax.set_ylabel("Impression 수 (5분 단위)")

        # X축을 3시간 단위로 표시
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
        
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        
        # [모니터링 차트 스타일 스위치]
        # True : (슬라이딩 모드) 뱀처럼 꼬리를 자르며 최근 24시간 길이만 계속 유지하여 이동함
        # False: (누적 모드) 최초 실행 지점(min)부터 시작해 도화지를 영원히 늘리며 모든 데이터를 다 보여줌
        USE_SLIDING_WINDOW = True 
        
        if USE_SLIDING_WINDOW:
            from datetime import timedelta
            # 현재 가장 최신 시간 기준으로 딱 24시간 전을 계산하되,
            # 아직 전체 데이터가 24시간 치에 못 미치면 실제 가장 오래된 데이터 시작점에 맞추기 (왼쪽 거대 공백 방지)
            latest_time = max(t_ts)
            sliding_start = latest_time - timedelta(hours=24)
            actual_start = max(sliding_start, min(t_ts))
            ax.set_xlim(left=actual_start, right=None)
        else:
            # 기존(누적 모드): 왼쪽 화면 벽을 최초 수집 시간으로 단단히 고정
            ax.set_xlim(left=min(t_ts), right=None)
            
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
        t_ts = result.timestamps
        t_actuals = result.actuals
        t_predicted = result.predicted
        t_lowers = result.lowers
        t_uppers = result.uppers

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t_ts + t_ts[::-1], y=t_uppers + t_lowers[::-1], fill="toself", fillcolor="rgba(0, 0, 255, 0.1)", line=dict(color="rgba(255,255,255,0)"), name="신뢰구간", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=t_ts, y=t_predicted, mode="lines", name="예측값", line=dict(color="blue", width=1)))
        fig.add_trace(go.Scatter(x=t_ts, y=t_actuals, mode="lines", name="실제값", line=dict(color="green", width=1)))
        
        valid_anomalies = result.anomaly_indices
        if valid_anomalies:
            anomaly_ts = [result.timestamps[i] for i in valid_anomalies]
            anomaly_vals = [result.actuals[i] for i in valid_anomalies]
            anomaly_texts = [result.anomaly_types.get(i, "Anomaly") for i in valid_anomalies]
            
            fig.add_trace(go.Scatter(
                x=anomaly_ts, 
                y=anomaly_vals, 
                mode="markers", 
                marker=dict(color="red", size=10), 
                name="이상치",
                text=anomaly_texts,
                hovertemplate="<b>[이상치 감지]</b><br>타입: %{text}<br>수치: %{y}<extra></extra>"
            ))
        
        fig.update_layout(
            title="Ad Impression Anomaly Detection", 
            xaxis_title="시각", 
            yaxis_title="Impression 수", 
            hovermode="x",
            template="plotly_white",
            xaxis=dict(
                tickformat="%m/%d %H:%M",
                dtick=10800000  # 밀리초 기준 3시간
            )
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

def check_retrain():
    """config.py를 다시 로드하고 재훈련 여부 확인"""
    try:
        importlib.reload(config)
        return config.ENABLE_RETRAIN
    except Exception as e:
        logger.error(f"config 재로드 실패: {e}")
        return config.ENABLE_RETRAIN  # 실패 시 기존값 유지

def retrain_in_background(prophet: ProphetDetector, iso_forest: IsolationForestDetector, all_records: list, prophet_path: str, iso_forest_path: str):
    """백그라운드에서 재훈련 + 저장 + 로드"""
    try:
        logger.info("[백그라운드] 재훈련 시작...")
        prophet.retrain_if_needed(all_records)
        iso_forest.retrain_if_needed(all_records)

        logger.info("[백그라운드] 모델 저장 중...")
        prophet.save(prophet_path)
        iso_forest.save(iso_forest_path)

        logger.info("[백그라운드] 새 모델 로드 중...")
        prophet.load(prophet_path)
        iso_forest.load(iso_forest_path)

        logger.info("[백그라운드] 재훈련 완료! 새 모델 적용됨")
    except Exception as e:
        logger.error(f"[백그라운드] 재훈련 실패: {e}")

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
    all_records = []  # 재훈련용 데이터 누적

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

                    # 재훈련용 데이터 누적
                    all_records.append({"timestamp": ts, "impression_count": count})

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

                    # 50윈도우마다 진행 상황만 출력
                    if result.total_windows % 50 == 0:
                        logger.info(f"진행 중... ({result.total_windows} / {len(datapoints) if 'datapoints' in locals() else '?'})")

                    # 24시간마다 재훈련 (백그라운드에서 실행, config.py 변경사항 실시간 반영)
                    if check_retrain() and result.total_windows % config.RETRAIN_INTERVAL == 0:
                        logger.info(f"[재훈련] {result.total_windows}개 윈도우 완료, 백그라운드 재훈련 시작...")
                        # 데이터 복사 (스레드 안전성)
                        records_copy = all_records.copy()
                        # 백그라운드 스레드에서 재훈련 (탐지는 계속)
                        retrain_thread = threading.Thread(
                            target=retrain_in_background,
                            args=(prophet, iso_forest, records_copy, PROPHET_MODEL_PATH, ISO_FOREST_MODEL_PATH),
                            daemon=True
                        )
                        retrain_thread.start()
                        logger.info(f"[재훈련] 백그라운드 스레드 시작됨 (탐지는 계속 진행)")
                        # 메모리 정리
                        all_records.clear()
                        result.timestamps = []
                        result.actuals = []
                        result.predicted = []
                        result.lowers = []
                        result.uppers = []
                        result.anomaly_indices = []
                        result.anomaly_types = {}
                        result.total_windows = 0   # 인덱스 기준점 초기화 (버그 수정)
                        result.anomaly_count = 0   # 이상치 카운터 초기화 (버그 수정)
                        logger.info(f"[메모리] 재훈련 데이터 정리 완료")

                except ModelError as e:
                    logger.error(f"예측 실패 [{ts}]: {e}")
            
            # 파이프라인 종료 시 마지막 미완료 윈도우 처리 (flush)
            last_window = aggregator.flush()
            if last_window is not None:
                ts, count = last_window
                try:
                    res_dict = prophet.predict(ts, count)
                    status, pred, lower, upper, atype = res_dict["status"], res_dict["predicted"], res_dict["lower"], res_dict["upper"], res_dict["anomaly_type"]
                    result.timestamps.append(ts)
                    result.actuals.append(float(count))
                    result.predicted.append(pred)
                    result.lowers.append(lower)
                    result.uppers.append(upper)
                    if status == "ANOMALY":
                        result.anomaly_indices.append(result.total_windows)
                        result.anomaly_types[result.total_windows] = atype or "Unknown"
                        result.anomaly_count += 1
                    result.total_windows += 1
                    logger.info(f"[flush] 마지막 윈도우 처리 완료: {ts} → {count} ({status})")
                except ModelError as e:
                    logger.error(f"마지막 윈도우 예측 실패: {e}")
    except KeyboardInterrupt:
        logger.warning("사용자가 강제로 프로그램(Ctrl+C)을 중단했습니다. (지금까지의 결과를 차트로 저장합니다)")
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
        
        # 슬랙 알림 전송 (신규 추가)
        if config.ENABLE_SLACK_NOTIF:
            notifier = SlackNotifier(config.SLACK_BOT_TOKEN, config.SLACK_CHANNEL_ID)
            has_anomaly = result.anomaly_count > 0
            
            if has_anomaly or config.TEST_MODE_FORCE_SLACK:
                msg = "[🚨 이상 탐지 알림]" if has_anomaly else "[🧪 테스트 알림]"
                msg += f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 기준 탐지 결과입니다.\n"
                msg += f"총 {result.anomaly_count}개의 이상 지점이 발견되었습니다."
                
                png_path = os.path.join(config.OUTPUT_DIR, "anomaly_result.png")
                logger.info(f"슬랙 알림 전송 중... (사유: {'이상 탐지' if has_anomaly else '테스트 모드'})")
                notifier.send_file(
                    file_path=png_path,
                    title="Anomaly Detection Result",
                    initial_comment=msg
                )

        prophet.save(PROPHET_MODEL_PATH)
        iso_forest.save(ISO_FOREST_MODEL_PATH)
        logger.info("파이프라인 정상 종료")
    except KeyboardInterrupt:
        logger.info("프로그램을 종료합니다.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"애플리케이션 실패: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
