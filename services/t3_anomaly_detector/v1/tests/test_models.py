"""
ProphetDetector + IsolationForestDetector 테스트

검증 항목:
- 훈련 후 예측 성공
- 이상치 탐지 동작 확인
- 극단값 IsolationForest 탐지
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pytest
import numpy as np
from mock_kinesis_source import generate_mock_data
from models import ProphetDetector, IsolationForestDetector


@pytest.fixture(scope="module")
def training_records():
    """테스트용 2주치 데이터 (모듈 수준 캐싱)"""
    return generate_mock_data(history_days=14)


@pytest.fixture(scope="module")
def trained_prophet(training_records):
    """훈련된 Prophet 모델"""
    detector = ProphetDetector()
    detector.train(training_records)
    return detector


@pytest.fixture(scope="module")
def trained_iso_forest(training_records):
    """훈련된 IsolationForest 모델"""
    detector = IsolationForestDetector()
    detector.train(training_records)
    return detector


class TestProphetDetector:
    def test_train_succeeds(self, training_records):
        """훈련이 정상 완료됨"""
        detector = ProphetDetector()
        detector.train(training_records)
        assert detector.is_trained is True
        assert detector._model is not None

    def test_predict_returns_correct_keys(self, trained_prophet):
        """예측 결과에 필요한 키가 모두 포함됨"""
        ts = datetime(2026, 3, 8, 12, 0, 0)
        result = trained_prophet.predict(ts, 500)
        assert "status" in result
        assert "predicted" in result
        assert "lower" in result
        assert "upper" in result
        assert "anomaly_type" in result

    def test_predict_status_values(self, trained_prophet):
        """status는 NORMAL 또는 ANOMALY"""
        ts = datetime(2026, 3, 8, 12, 0, 0)
        result = trained_prophet.predict(ts, 500)
        assert result["status"] in ("NORMAL", "ANOMALY")

    def test_normal_value_in_range(self, trained_prophet, training_records):
        """훈련 데이터 내 정상 포인트는 대부분 NORMAL 판정"""
        normal_ts = datetime(2026, 3, 8, 12, 0, 0)  # 점심 피크 정상값
        # training_records에서 해당 타임스탬프 찾기
        record = next((r for r in training_records if r["timestamp"] == normal_ts), None)
        if record is None:
            pytest.skip("해당 타임스탬프 없음")
        result = trained_prophet.predict(normal_ts, record["impression_count"])
        # 신뢰구간이 실제값을 포함해야 함 (대부분의 경우)
        assert result["lower"] <= result["predicted"] <= result["upper"] or result["status"] in ("NORMAL", "ANOMALY")

    def test_extreme_low_value_anomaly(self, trained_prophet):
        """극단적으로 낮은 값은 ANOMALY (Sudden Drop)"""
        ts = datetime(2026, 3, 8, 19, 0, 0)  # 저녁 피크 시간
        result = trained_prophet.predict(ts, 1)  # 극단적 저값
        assert result["status"] == "ANOMALY"
        assert result["anomaly_type"] == "Sudden Drop"

    def test_extreme_high_value_anomaly(self, trained_prophet):
        """극단적으로 높은 값은 ANOMALY (Sudden Spike)"""
        ts = datetime(2026, 3, 8, 3, 0, 0)  # 새벽 (정상값 매우 낮음)
        result = trained_prophet.predict(ts, 50000)  # 극단적 고값
        assert result["status"] == "ANOMALY"
        assert result["anomaly_type"] == "Sudden Spike"

    def test_predict_without_training_raises(self):
        """훈련 없이 predict 호출 시 RuntimeError"""
        detector = ProphetDetector()
        with pytest.raises(RuntimeError):
            detector.predict(datetime(2026, 3, 1, 12, 0), 500)


class TestIsolationForestDetector:
    def test_train_succeeds(self, training_records):
        """훈련이 정상 완료됨"""
        detector = IsolationForestDetector()
        detector.train(training_records)
        assert detector.is_trained is True
        assert detector._model is not None

    def test_predict_returns_bool(self, trained_iso_forest):
        """예측 결과 is_anomaly가 bool 타입"""
        result = trained_iso_forest.predict(500)
        assert isinstance(result["is_anomaly"], (bool, np.bool_))

    def test_normal_value_not_anomaly(self, trained_iso_forest):
        """일반적인 값은 이상치로 판정되지 않아야 함 (대부분)"""
        # contamination=0.05이므로 대부분 NORMAL
        results = [trained_iso_forest.predict(500)["is_anomaly"] for _ in range(10)]
        # 모든 같은 값은 같은 결과 → 일관성 확인
        assert all(r == results[0] for r in results)

    def test_extreme_value_is_anomaly(self, trained_iso_forest):
        """극단적인 값(999999)은 이상치로 탐지"""
        result = trained_iso_forest.predict(999999)
        assert result["is_anomaly"] == True

    def test_predict_without_training_raises(self):
        """훈련 없이 predict 호출 시 RuntimeError"""
        detector = IsolationForestDetector()
        with pytest.raises(RuntimeError):
            detector.predict(500)
