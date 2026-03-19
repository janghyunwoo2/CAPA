"""
Real-time Ad Impression Anomaly Detector - 메인 파이프라인

파이프라인 흐름:
1. Mock 데이터 전체 생성 (2주치)
2. 2주치로 Prophet + IsolationForest 초기 훈련
3. 동일 데이터로 "과거 재생" (가속 모드 지원)
4. 각 5분 윈도우마다 이상 탐지
5. 완료 후 시각화 저장
"""
import json
import logging
import os
import sys
import time
from datetime import datetime
from dataclasses import dataclass, field

import matplotlib
matplotlib.use("Agg")  # 헤드리스 환경 대응
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import plotly.graph_objects as go

import config
from font_utils import setup_font
from aggregator import FiveMinuteAggregator
from mock_kinesis_source import MockKinesisSource
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
os.makedirs(OUTPUT_DIR, exist_ok=True)


@dataclass
class DetectionResult:
    """이상 탐지 결과"""
    timestamps: list[datetime] = field(default_factory=list)
    actuals: list[float] = field(default_factory=list)
    predicted: list[float] = field(default_factory=list)
    lowers: list[float] = field(default_factory=list)
    uppers: list[float] = field(default_factory=list)
    anomaly_indices: list[int] = field(default_factory=list)
    anomaly_types: dict[int, str] = field(default_factory=dict)
    total_windows: int = 0
    anomaly_count: int = 0


def save_png(result: DetectionResult) -> None:
    """시계열 + 신뢰구간 + 이상치 정적 PNG 저장"""
    try:
        fig, ax = plt.subplots(figsize=(16, 6))

        ax.fill_between(
            result.timestamps,
            result.lowers,
            result.uppers,
            alpha=0.2,
            color="blue",
            label="예측 신뢰구간 (95%)",
        )
        ax.plot(result.timestamps, result.predicted, color="blue", linewidth=1, alpha=0.7, label="예측값")
        ax.plot(result.timestamps, result.actuals, color="green", linewidth=1, label="실제값")

        # 이상치 빨간 점
        if result.anomaly_indices:
            anomaly_ts = [result.timestamps[i] for i in result.anomaly_indices]
            anomaly_vals = [result.actuals[i] for i in result.anomaly_indices]
            ax.scatter(
                anomaly_ts,
                anomaly_vals,
                color="red",
                zorder=5,
                s=60,
                label=f"이상치 ({len(result.anomaly_indices)}건)",
            )

        ax.set_title("Ad Impression Anomaly Detection", fontsize=14, fontweight="bold")
        ax.set_xlabel("시각")
        ax.set_ylabel("Impression 수 (5분 단위)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        plt.xticks(rotation=45)
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        path = os.path.join(OUTPUT_DIR, "anomaly_result.png")
        plt.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"PNG 저장: {path}")
    except Exception as e:
        logger.error(f"PNG 저장 실패: {e}", exc_info=True)


def save_html(result: DetectionResult) -> None:
    """Plotly 인터랙티브 HTML 저장"""
    try:
        fig = go.Figure()

        # 신뢰구간 음영
        fig.add_trace(
            go.Scatter(
                x=result.timestamps + result.timestamps[::-1],
                y=result.uppers + result.lowers[::-1],
                fill="toself",
                fillcolor="rgba(0, 0, 255, 0.1)",
                line=dict(color="rgba(255,255,255,0)"),
                name="예측 신뢰구간 (95%)",
                hoverinfo="skip",
            )
        )

        # 예측값
        fig.add_trace(
            go.Scatter(
                x=result.timestamps,
                y=result.predicted,
                mode="lines",
                line=dict(color="blue", width=1),
                name="예측값",
                opacity=0.7,
            )
        )

        # 실제값
        fig.add_trace(
            go.Scatter(
                x=result.timestamps,
                y=result.actuals,
                mode="lines",
                line=dict(color="green", width=1),
                name="실제값",
            )
        )

        # 이상치
        if result.anomaly_indices:
            anomaly_ts = [result.timestamps[i] for i in result.anomaly_indices]
            anomaly_vals = [result.actuals[i] for i in result.anomaly_indices]
            hover_texts = [
                f"이상치: {result.anomaly_types.get(i, 'Unknown')}<br>"
                f"실제: {result.actuals[i]:.0f}<br>예측: {result.predicted[i]:.0f}"
                for i in result.anomaly_indices
            ]
            fig.add_trace(
                go.Scatter(
                    x=anomaly_ts,
                    y=anomaly_vals,
                    mode="markers",
                    marker=dict(color="red", size=10, symbol="circle"),
                    name=f"이상치 ({len(result.anomaly_indices)}건)",
                    text=hover_texts,
                    hovertemplate="%{text}<extra></extra>",
                )
            )

        fig.update_layout(
            title="Ad Impression Anomaly Detection (Interactive)",
            xaxis_title="시각",
            yaxis_title="Impression 수 (5분 단위)",
            hovermode="x unified",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        path = os.path.join(OUTPUT_DIR, "anomaly_interactive.html")
        fig.write_html(path)
        logger.info(f"HTML 저장: {path}")
    except Exception as e:
        logger.error(f"HTML 저장 실패: {e}", exc_info=True)


def save_components(prophet_detector: ProphetDetector) -> None:
    """Prophet 계절성 컴포넌트 PNG 저장"""
    try:
        if not prophet_detector.is_trained or prophet_detector.get_model() is None:
            logger.warning("Prophet 모델이 훈련되지 않아 컴포넌트 저장 불가")
            return

        model = prophet_detector.get_model()
        future = model.make_future_dataframe(periods=7 * 24 * 12, freq="5min")
        forecast = model.predict(future)

        fig = model.plot_components(forecast)
        path = os.path.join(OUTPUT_DIR, "anomaly_components.png")
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Prophet 컴포넌트 저장: {path}")
    except Exception as e:
        logger.error(f"컴포넌트 저장 실패: {e}", exc_info=True)


def format_console_line(
    timestamp: datetime,
    status: str,
    actual: float,
    predicted: float,
    lower: float,
    upper: float,
    anomaly_type: str | None,
) -> str:
    """콘솔 출력 포맷"""
    ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    status_str = f"[{status}{'!' if status == 'ANOMALY' else ' '}]"
    type_info = f"| Type: {anomaly_type}" if anomaly_type else ""
    return (
        f"[{ts_str}] {status_str:<12} "
        f"Actual: {actual:6.0f} | Predicted: {predicted:6.0f} | "
        f"Range: ({lower:.0f}, {upper:.0f}) {type_info}"
    )


def train_models(
    records: list[dict],
) -> tuple[ProphetDetector, IsolationForestDetector]:
    """모델 훈련"""
    logger.info("=" * 60)
    logger.info("모델 훈련 시작 (시간이 걸릴 수 있습니다)")
    logger.info("=" * 60)

    try:
        prophet = ProphetDetector()
        prophet.train(records)

        iso_forest = IsolationForestDetector()
        iso_forest.train(records)

        logger.info("모델 훈련 완료")
        return prophet, iso_forest
    except ModelError as e:
        logger.error(f"모델 훈련 실패: {e}", exc_info=True)
        raise


def run_detection_pipeline(
    records: list[dict],
    prophet: ProphetDetector,
    iso_forest: IsolationForestDetector,
) -> DetectionResult:
    """이상 탐지 파이프라인 실행"""
    result = DetectionResult()
    aggregator = FiveMinuteAggregator(window_size_minutes=config.WINDOW_SIZE_MINUTES)

    jsonl_path = os.path.join(OUTPUT_DIR, "anomaly_log.jsonl")
    sleep_seconds = (
        (config.WINDOW_SIZE_MINUTES * 60) / config.ACCELERATION_FACTOR
        if config.ACCELERATION_FACTOR > 1
        else 0
    )

    logger.info("=" * 60)
    logger.info("이상 탐지 시작")
    logger.info("=" * 60)

    try:
        with open(jsonl_path, "w", encoding="utf-8") as jsonl_file:
            for record in records:
                window_result = aggregator.add_record(record)
                if window_result is None:
                    continue

                ts, count = window_result

                try:
                    # Prophet 예측
                    result_dict = prophet.predict(ts, count)
                    status = result_dict["status"]
                    predicted_val = result_dict["predicted"]
                    lower = result_dict["lower"]
                    upper = result_dict["upper"]
                    anomaly_type = result_dict["anomaly_type"]

                    # IsolationForest 보완 탐지
                    if_result = iso_forest.predict(count)
                    if if_result["is_anomaly"] and status == "NORMAL":
                        status = "ANOMALY"
                        anomaly_type = "IsoForest Anomaly"

                    # 결과 수집
                    result.timestamps.append(ts)
                    result.actuals.append(float(count))
                    result.predicted.append(predicted_val)
                    result.lowers.append(lower)
                    result.uppers.append(upper)

                    if status == "ANOMALY":
                        result.anomaly_indices.append(result.total_windows)
                        result.anomaly_types[result.total_windows] = anomaly_type or "Unknown"
                        result.anomaly_count += 1

                    result.total_windows += 1

                    # 콘솔 출력
                    line = format_console_line(
                        ts, status, count, predicted_val, lower, upper, anomaly_type
                    )
                    print(line)

                    # JSONL 기록
                    log_entry = {
                        "timestamp": ts.isoformat(),
                        "actual": count,
                        "predicted": round(predicted_val, 1),
                        "lower": round(lower, 1),
                        "upper": round(upper, 1),
                        "status": status,
                        "anomaly_type": anomaly_type,
                    }
                    jsonl_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                    jsonl_file.flush()

                    # 주기적 재훈련
                    prophet.retrain_if_needed(records[:result.total_windows])

                    # 주기적 시각화 갱신
                    if (
                        result.total_windows % config.VISUALIZATION_UPDATE_INTERVAL == 0
                        and result.total_windows > 0
                    ):
                        logger.debug(f"중간 시각화 갱신 (윈도우 {result.total_windows})")
                        if config.SAVE_PNG:
                            save_png(result)
                        if config.SAVE_HTML:
                            save_html(result)

                    # 가속 sleep
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)

                except ModelError as e:
                    logger.error(f"예측 실패 [{ts}]: {e}")
                    continue

        # 마지막 윈도우 flush
        final_window = aggregator.flush()
        if final_window:
            ts, count = final_window
            try:
                result_dict = prophet.predict(ts, count)
                result.timestamps.append(ts)
                result.actuals.append(float(count))
                result.predicted.append(result_dict["predicted"])
                result.lowers.append(result_dict["lower"])
                result.uppers.append(result_dict["upper"])
                result.total_windows += 1
                logger.debug("마지막 윈도우 처리 완료")
            except ModelError as e:
                logger.warning(f"마지막 윈도우 예측 실패: {e}")

    except IOError as e:
        logger.error(f"파일 쓰기 실패: {e}", exc_info=True)
        raise

    logger.info("=" * 60)
    logger.info(f"파이프라인 완료: {result.total_windows}개 윈도우, {result.anomaly_count}개 이상치")
    logger.info("=" * 60)

    return result


def save_results(result: DetectionResult, prophet: ProphetDetector) -> None:
    """결과 저장"""
    if config.SAVE_PNG and result.timestamps:
        save_png(result)

    if config.SAVE_HTML and result.timestamps:
        save_html(result)

    if config.SAVE_COMPONENTS:
        save_components(prophet)


def print_anomaly_summary(result: DetectionResult) -> None:
    """이상치 요약 출력"""
    if not result.anomaly_indices:
        logger.info("탐지된 이상치 없음")
        return

    print("\n" + "=" * 60)
    print(f"탐지된 이상치 요약 ({result.anomaly_count}건):")
    print("=" * 60)
    for idx in result.anomaly_indices:
        ts = result.timestamps[idx]
        actual = result.actuals[idx]
        pred = result.predicted[idx]
        atype = result.anomaly_types.get(idx, "Unknown")
        print(f"  {ts.strftime('%Y-%m-%d %H:%M')} | {atype} | 실제: {actual:.0f} | 예측: {pred:.0f}")
    print("=" * 60)


def main() -> None:
    """메인 파이프라인"""
    try:
        logger.info("=" * 60)
        logger.info("Ad Impression Anomaly Detector 시작")
        logger.info(f"가속 배율: {config.ACCELERATION_FACTOR}x | 데이터: {config.HISTORY_DAYS}일치")
        logger.info("=" * 60)

        # 1. Mock 데이터 생성
        logger.info("Mock 데이터 로드 중...")
        source = MockKinesisSource(
            history_days=config.HISTORY_DAYS,
            acceleration_factor=1,  # 훈련 시에는 가속 없이
        )
        all_records = source.get_all_records()
        logger.info(f"Mock 데이터 로드 완료: {len(all_records)}개 포인트")

        # 2. 모델 훈련
        prophet, iso_forest = train_models(all_records)

        # 3. 이상 탐지 파이프라인 실행
        result = run_detection_pipeline(all_records, prophet, iso_forest)

        # 4. 결과 저장
        save_results(result, prophet)

        # 5. 요약 출력
        print_anomaly_summary(result)

        logger.info("파이프라인 정상 종료")

    except Exception as e:
        logger.error(f"파이프라인 실패: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
