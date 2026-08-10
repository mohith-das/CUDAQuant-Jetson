"""Unit tests for the feature dispatch layer."""
import numpy as np
import pytest

from cudaquant.features.dispatch import (
    get_stats,
    reset_stats,
    returns,
    rolling_max,
    rolling_mean,
    rolling_min,
    rolling_std,
    rolling_sum,
    rolling_zscore,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_stats()
    yield


class TestDispatchRouting:
    """Test that dispatch routes to CPU or GPU based on config/library/size."""

    def test_dispatch_returns_array(self):
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        result = rolling_mean(arr, 3)
        assert isinstance(result, np.ndarray)
        assert len(result) == len(arr)

    def test_returns_computes_correctly(self):
        prices = np.array([100.0, 101.0, 102.0, 103.0], dtype=np.float64)
        r = returns(prices)
        np.testing.assert_allclose(r[1:], [0.01, 0.00990099, 0.00980392], rtol=1e-5)
        assert np.isnan(r[0])

    def test_rolling_mean_correct(self):
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        result = rolling_mean(arr, 3)
        assert np.isnan(result[0])
        assert np.isnan(result[1])
        np.testing.assert_allclose(result[2:], [2.0, 3.0, 4.0])

    def test_rolling_std_correct(self):
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        result = rolling_std(arr, 3)
        assert np.isnan(result[0])
        assert np.isnan(result[1])
        # std of [1,2,3] = 0.816..., [2,3,4] = 0.816..., [3,4,5] = 0.816...
        np.testing.assert_allclose(result[2:], [0.81649658] * 3, rtol=1e-5)

    def test_rolling_min_correct(self):
        arr = np.array([3.0, 1.0, 4.0, 2.0, 5.0], dtype=np.float64)
        result = rolling_min(arr, 3)
        np.testing.assert_allclose(result[2], 1.0)
        np.testing.assert_allclose(result[3], 1.0)

    def test_rolling_zscore_correct(self):
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        result = rolling_zscore(arr, 3)
        np.testing.assert_allclose(result[2:], [1.22474487] * 3, rtol=1e-5)

    def test_stats_tracks_cpu_calls(self):
        arr = np.full(100, 1.0, dtype=np.float64)
        reset_stats()
        rolling_mean(arr, 5)
        stats = get_stats()
        assert "rolling_mean" in stats["cpu_calls"]
        assert stats["cpu_calls"]["rolling_mean"] == 1

    def test_stats_accumulates(self):
        arr = np.full(100, 1.0, dtype=np.float64)
        reset_stats()
        rolling_mean(arr, 5)
        rolling_std(arr, 5)
        stats = get_stats()
        assert stats["cpu_calls"].get("rolling_mean", 0) == 1
        assert stats["cpu_calls"].get("rolling_std", 0) == 1

    def test_config_disabled_bypasses_gpu(self):
        arr = np.full(2000, 1.0, dtype=np.float64)
        reset_stats()
        rolling_min(arr, 5)
        stats = get_stats()
        # On Mac (no GPU lib): should be gpu_bypass_no_lib
        # If CUDA_ENABLED=False: should be gpu_bypass_config
        total_bypass = stats["gpu_bypass_config"] + stats["gpu_bypass_no_lib"]
        assert total_bypass >= 1 or "rolling_min" in stats["cpu_calls"]

    def test_nan_handling(self):
        arr = np.array([1.0, np.nan, 3.0, 4.0, 5.0], dtype=np.float64)
        result = rolling_mean(arr, 2)
        assert np.isnan(result[0])
        assert np.isnan(result[1])
        # NaN propagates through cumsum; position 2 is NaN because it
        # includes the NaN at index 1 in its cumsum window.
        assert np.isnan(result[2])

    def test_window_one(self):
        arr = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        result = rolling_mean(arr, 1)
        np.testing.assert_allclose(result, arr)

    def test_empty_array(self):
        arr = np.array([], dtype=np.float64)
        result = rolling_mean(arr, 5)
        assert len(result) == 0

    def test_large_array_no_crash(self):
        arr = np.random.randn(5000).astype(np.float64)
        result = rolling_sum(arr, 20)
        assert len(result) == 5000
        assert not np.all(np.isnan(result))

    def test_all_dispatch_functions_importable(self):
        """Every dispatch function should be callable without crash."""
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        # Known dispatchable functions
        fns = [
            rolling_mean, rolling_std, rolling_min, rolling_max,
            rolling_sum, rolling_zscore,
        ]
        for fn in fns:
            result = fn(arr, 5)
            assert isinstance(result, np.ndarray)
        r = returns(arr)
        assert isinstance(r, np.ndarray)
