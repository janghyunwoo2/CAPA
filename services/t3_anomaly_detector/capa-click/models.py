"""
이상 탐지 모델 모듈

- ProphetDetector: 시계열 트렌드/계절성 기반 이상 탐지
- IsolationForestDetector: 점 이상치 보완 탐지
"""
import logging
import pickle
import os
import threading
from datetime import datetime

import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.ensemble import IsolationForest

import config

logger = logging.getLogger(__name__)

# Prophet/cmdstanpy 로그 억제 (모듈 레벨)
logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


class ModelError(Exception):
    """모델 오류"""
    pass


class ProphetDetector:
    """
    Facebook Prophet 기반 시계열 이상 탐지기

    동작:
    1. 초기 2주치 데이터로 훈련
    2. 각 윈도우마다 신뢰구간 기반 이상치 판별
    3. RETRAIN_INTERVAL마다 누적 데이터로 재훈련
    """

    def __init__(self):
        self._model: Prophet | None = None
        self._training_data: list[dict] = []
        self._window_count: int = 0
        self.is_trained: bool = False
        self._lock = threading.Lock()  # thread safety

    def save(self, file_path: str) -> None:
        """모델을 파일로 저장"""
        if not self.is_trained or self._model is None:
            raise ModelError("훈련되지 않은 모델은 저장할 수 없습니다")
        
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                pickle.dump({
                    "model": self._model,
                    "window_count": self._window_count,
                    "training_data": self._training_data
                }, f)
            logger.info(f"Prophet 모델 저장 완료: {file_path}")
        except Exception as e:
            logger.error(f"Prophet 모델 저장 실패: {e}")
            raise ModelError(f"저장 실패: {e}")

    def load(self, file_path: str) -> None:
        """파일에서 모델 로드"""
        if not os.path.exists(file_path):
            raise ModelError(f"모델 파일을 찾을 수 없습니다: {file_path}")
        
        try:
            with open(file_path, "rb") as f:
                data = pickle.load(f)
                self._model = data["model"]
                self._window_count = data.get("window_count", 0)
                self._training_data = data.get("training_data", [])
                self.is_trained = True
            logger.info(f"Prophet 모델 로드 완료: {file_path} (윈도우: {self._window_count})")
        except Exception as e:
            logger.error(f"Prophet 모델 로드 실패: {e}")
            raise ModelError(f"로드 실패: {e}")

    def train(self, records: list[dict]) -> None:
        """
        Prophet 모델 훈련

        Args:
            records: [{"timestamp": datetime, "click_count": int}, ...]

        Raises:
            ModelError: 훈련 실패
        """
        if not records:
            raise ModelError("훈련 데이터가 비어있습니다")

        try:
            df = pd.DataFrame([
                {"ds": r["timestamp"], "y": r["click_count"]}
                for r in records
            ])

            logger.debug(f"Prophet 훈련 시작: {len(df)}개 데이터포인트")

            model = Prophet(
                interval_width=config.PROPHET_INTERVAL_WIDTH,
                yearly_seasonality=config.PROPHET_YEARLY_SEASONALITY,
                weekly_seasonality=config.PROPHET_WEEKLY_SEASONALITY,
                daily_seasonality=config.PROPHET_DAILY_SEASONALITY,
                changepoint_prior_scale=config.PROPHET_CHANGEPOINT_PRIOR_SCALE,
                seasonality_mode=config.PROPHET_SEASONALITY_MODE,
            )

            model.fit(df)
            self._model = model
            self._training_data = list(records)
            self.is_trained = True
            logger.info(f"Prophet 훈련 완료: {len(df)}개 포인트, 신뢰도 {config.PROPHET_INTERVAL_WIDTH:.0%}")
        except Exception as e:
            logger.error(f"Prophet 훈련 실패: {e}", exc_info=True)
            raise ModelError(f"Prophet 훈련 실패: {e}") from e

    def predict(self, timestamp: datetime, value: float) -> dict:
        """
        단일 포인트 이상치 판별

        Args:
            timestamp: 5분 윈도우 타임스탬프
            value: 실측값 (click_count)

        Returns:
            {
                "status": "NORMAL" | "ANOMALY",
                "predicted": float,
                "lower": float,
                "upper": float,
                "anomaly_type": str | None  # "Sudden Drop" | "Sudden Spike"
            }

        Raises:
            ModelError: 모델이 훈련되지 않음
        """
        with self._lock:  # thread safety
            if not self.is_trained or self._model is None:
                raise ModelError("Prophet 모델이 훈련되지 않았습니다. train()을 먼저 호출하세요.")

            try:
                future = pd.DataFrame({"ds": [timestamp]})
                forecast = self._model.predict(future)

                # 예측 결과 검증
                if forecast.empty or len(forecast) == 0:
                    raise ModelError(f"Prophet 예측 실패: {timestamp}")

                predicted = max(3.0, float(forecast["yhat"].iloc[0]))
                lower = max(config.PROPHET_LOWER_BOUND, float(forecast["yhat_lower"].iloc[0]))
                # 상단 신뢰구간에 가중치를 적용하여 Spike 감지 기준을 완화
                upper = float(forecast["yhat_upper"].iloc[0]) * config.PROPHET_UPPER_WEIGHT
                
                self._window_count += 1

                # 이상치 판별
                if value < lower:
                    status = "ANOMALY"
                    anomaly_type = "Sudden Drop"
                elif value > upper:
                    status = "ANOMALY"
                    anomaly_type = "Sudden Spike"
                else:
                    status = "NORMAL"
                    anomaly_type = None

                return {
                    "status": status,
                    "predicted": predicted,
                    "lower": lower,
                    "upper": upper,
                    "anomaly_type": anomaly_type,
                }
            except Exception as e:
                logger.error(f"Prophet 예측 실패: {e}", exc_info=True)
                raise ModelError(f"Prophet 예측 실패: {e}") from e

    def get_model(self):
        """모델 객체 반환 (None if not trained)"""
        return self._model if self.is_trained else None

    def retrain_if_needed(self, new_records: list[dict]) -> bool:
        """
        RETRAIN_INTERVAL에 도달한 경우 누적 데이터로 재훈련

        Args:
            new_records: 현재까지 누적된 모든 레코드

        Returns:
            True if retrained, False otherwise
        """
        if self._window_count > 0 and self._window_count % config.RETRAIN_INTERVAL == 0:
            logger.debug(f"정기적 재훈련 시작 (윈도우 {self._window_count}/{config.RETRAIN_INTERVAL})")
            try:
                self.train(new_records)
                logger.info(f"재훈련 완료: {len(new_records)}개 포인트")
                return True
            except ModelError as e:
                logger.warning(f"재훈련 실패, 기존 모델 유지: {e}")
                return False
        return False


class IsolationForestDetector:
    """
    Isolation Forest 기반 점 이상치 탐지기

    Prophet이 놓치는 극단값 패턴을 보완합니다.
    """

    def __init__(self):
        self._model: IsolationForest | None = None
        self.is_trained: bool = False
        self._lock = threading.Lock()  # thread safety

    def save(self, file_path: str) -> None:
        """모델을 파일로 저장"""
        if not self.is_trained or self._model is None:
            raise ModelError("훈련되지 않은 모델은 저장할 수 없습니다")
        
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                pickle.dump(self._model, f)
            logger.info(f"IsolationForest 모델 저장 완료: {file_path}")
        except Exception as e:
            logger.error(f"IsolationForest 모델 저장 실패: {e}")
            raise ModelError(f"저장 실패: {e}")

    def load(self, file_path: str) -> None:
        """파일에서 모델 로드"""
        if not os.path.exists(file_path):
            raise ModelError(f"모델 파일을 찾을 수 없습니다: {file_path}")
        
        try:
            with open(file_path, "rb") as f:
                self._model = pickle.load(f)
                self.is_trained = True
            logger.info(f"IsolationForest 모델 로드 완료: {file_path}")
        except Exception as e:
            logger.error(f"IsolationForest 모델 로드 실패: {e}")
            raise ModelError(f"로드 실패: {e}")

    def train(self, records: list[dict]) -> None:
        """
        Isolation Forest 훈련

        Args:
            records: [{"timestamp": datetime, "click_count": int}, ...]

        Raises:
            ModelError: 훈련 실패
        """
        if not records:
            raise ModelError("훈련 데이터가 비어있습니다")

        try:
            values = np.array([r["click_count"] for r in records]).reshape(-1, 1)

            self._model = IsolationForest(
                contamination=config.ISOLATION_FOREST_CONTAMINATION,
                random_state=config.ISOLATION_FOREST_RANDOM_STATE,
            )
            self._model.fit(values)
            self.is_trained = True
            logger.debug(f"IsolationForest 훈련 완료: {len(values)}개 포인트, 오염도 {config.ISOLATION_FOREST_CONTAMINATION:.1%}")
        except Exception as e:
            logger.error(f"IsolationForest 훈련 실패: {e}", exc_info=True)
            raise ModelError(f"IsolationForest 훈련 실패: {e}") from e

    def predict(self, value: float) -> dict:
        """
        단일 포인트 이상치 판별

        Args:
            value: click_count

        Returns:
            {"is_anomaly": bool}

        Raises:
            ModelError: 모델이 훈련되지 않음 또는 예측 실패
        """
        with self._lock:  # thread safety
            if not self.is_trained or self._model is None:
                raise ModelError("IsolationForest 모델이 훈련되지 않았습니다. train()을 먼저 호출하세요.")

            try:
                result = self._model.predict([[value]])
                # 결과 검증
                if result is None or len(result) == 0:
                    raise ModelError(f"IsolationForest 예측 실패: value={value}")

                # IsolationForest: -1 = 이상치, 1 = 정상
                # numpy bool을 Python bool로 변환 (.item() 사용)
                is_anomaly = bool(result[0] == -1)
                return {"is_anomaly": is_anomaly}
            except Exception as e:
                logger.error(f"IsolationForest 예측 실패: {e}", exc_info=True)
                raise ModelError(f"IsolationForest 예측 실패: {e}") from e

    def retrain_if_needed(self, new_records: list[dict]) -> bool:
        """
        RETRAIN_INTERVAL에 도달한 경우 누적 데이터로 재훈련

        Args:
            new_records: 현재까지 누적된 모든 레코드

        Returns:
            True if retrained, False otherwise
        """
        if not new_records:
            return False

        try:
            self.train(new_records)
            logger.info(f"IsolationForest 재훈련 완료: {len(new_records)}개 포인트")
            return True
        except ModelError as e:
            logger.warning(f"IsolationForest 재훈련 실패, 기존 모델 유지: {e}")
            return False
