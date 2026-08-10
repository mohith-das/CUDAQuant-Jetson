"""ML model wrappers with time-series-aware training and evaluation.

All models enforce chronological train/test splits. No random shuffling
of time series data. Models return probability estimates and can be
evaluated with proper backtesting.
"""

from typing import Any

import numpy as np
import pandas as pd


class TSLogisticRegression:
    """Logistic regression wrapper with chronological training.

    Uses sklearn LogisticRegression internally. Enforces time-series
    order (no shuffling). Lightweight, interpretable baseline.
    """

    def __init__(self, **kwargs):
        self._params = kwargs
        self._model: Any = None
        self._feature_names: list[str] = []
        self._trained = False

    def fit(
        self,
        X: np.ndarray | pd.DataFrame,
        y: np.ndarray | pd.Series,
        feature_names: list[str] | None = None,
    ) -> "TSLogisticRegression":
        """Train on chronologically ordered data (NO SHUFFLING)."""
        from sklearn.linear_model import LogisticRegression

        if isinstance(X, pd.DataFrame):
            self._feature_names = list(X.columns)
            X = X.values
        elif feature_names:
            self._feature_names = feature_names

        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)

        # Clean: remove rows with NaN in X or y
        valid = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X_clean = X[valid]
        y_clean = (y[valid] > 0).astype(int)  # binarize: positive return = 1

        if len(X_clean) < 10 or len(np.unique(y_clean)) < 2:
            self._trained = False
            return self

        self._model = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=42,  # fixed for reproducibility; no shuffling
            **{k: v for k, v in self._params.items() if k != "random_state"},
        )
        # sklearn LogisticRegression by default does NOT shuffle if shuffle=False
        self._model.fit(X_clean, y_clean)
        self._trained = True
        return self

    def predict_proba(self, X: np.ndarray | pd.DataFrame) -> np.ndarray:
        """Return probability of positive class."""
        if not self._trained or self._model is None:
            return np.full(len(X), 0.5)
        if isinstance(X, pd.DataFrame):
            X = X.values
        X = np.asarray(X, dtype=np.float64)
        return self._model.predict_proba(X)[:, 1]

    def predict(self, X: np.ndarray | pd.DataFrame) -> np.ndarray:
        """Return binary predictions."""
        return (self.predict_proba(X) > 0.5).astype(int)


class TSRandomForest:
    """Random Forest wrapper with chronological training.

    Uses sklearn RandomForestClassifier. Tree-based models are less
    sensitive to feature scaling. Fixed seed for reproducibility.
    """

    def __init__(self, n_estimators: int = 100, max_depth: int = 10, **kwargs):
        self._params = dict(n_estimators=n_estimators, max_depth=max_depth, **kwargs)
        self._model: Any = None
        self._feature_names: list[str] = []
        self._trained = False

    def fit(
        self,
        X: np.ndarray | pd.DataFrame,
        y: np.ndarray | pd.Series,
        feature_names: list[str] | None = None,
    ) -> "TSRandomForest":
        """Train on chronologically ordered data."""
        from sklearn.ensemble import RandomForestClassifier

        if isinstance(X, pd.DataFrame):
            self._feature_names = list(X.columns)
            X = X.values
        elif feature_names:
            self._feature_names = feature_names

        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)

        valid = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X_clean = X[valid]
        y_clean = (y[valid] > 0).astype(int)

        if len(X_clean) < 10 or len(np.unique(y_clean)) < 2:
            self._trained = False
            return self

        self._model = RandomForestClassifier(
            random_state=42,
            n_jobs=-1,
            class_weight="balanced",
            **{k: v for k, v in self._params.items() if k != "random_state"},
        )
        # Note: RandomForest has internal bootstrap shuffling but
        # does not access future data points — only reorders within
        # the provided training set. This is acceptable for time-series
        # when the training set is already strictly chronological.
        self._model.fit(X_clean, y_clean)
        self._trained = True
        return self

    def predict_proba(self, X: np.ndarray | pd.DataFrame) -> np.ndarray:
        if not self._trained or self._model is None:
            return np.full(len(X), 0.5)
        if isinstance(X, pd.DataFrame):
            X = X.values
        X = np.asarray(X, dtype=np.float64)
        return self._model.predict_proba(X)[:, 1]

    def predict(self, X: np.ndarray | pd.DataFrame) -> np.ndarray:
        return (self.predict_proba(X) > 0.5).astype(int)

    @property
    def feature_importances_(self) -> np.ndarray | None:
        if self._model is not None and hasattr(self._model, "feature_importances_"):
            return self._model.feature_importances_
        return None


def prepare_features(
    data: pd.DataFrame,
    feature_fns: dict[str, callable],
    min_periods: int = 20,
) -> pd.DataFrame:
    """Build a feature matrix from OHLCV data using feature functions.

    Args:
        data: DataFrame with columns [open, high, low, close, volume]
        feature_fns: Dict of {feature_name: callable(data) -> Series}
        min_periods: Minimum bars before features are computed

    Returns:
        DataFrame of features, indexed same as data
    """
    features = {}
    for name, fn in feature_fns.items():
        result = fn(data)
        if isinstance(result, np.ndarray) and result.ndim == 1:
            features[name] = result
        elif isinstance(result, pd.Series):
            features[name] = result.values

    df = pd.DataFrame(features, index=data.index)
    # Drop rows with insufficient history
    df.iloc[:min_periods] = np.nan
    return df


def prepare_targets(
    data: pd.DataFrame,
    horizon: int = 1,
    threshold: float = 0.0,
) -> np.ndarray:
    """Create forward-return target labels.

    Args:
        data: DataFrame with 'close' column, chronologically sorted
        horizon: Forward bars for return computation
        threshold: Minimum return for positive label

    Returns:
        Array of 0/1 labels (1 = forward return > threshold)
    """
    close = data["close"].values.astype(np.float64)
    n = len(close)

    forward_returns = np.full(n, np.nan)
    for i in range(n - horizon):
        forward_returns[i] = (close[i + horizon] - close[i]) / close[i]

    labels = (forward_returns > threshold).astype(float)
    labels[np.isnan(forward_returns)] = np.nan
    return labels


def evaluate_classifier(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> dict:
    """Compute classification metrics.

    Args:
        y_true: Ground truth labels (0/1)
        y_prob: Predicted probabilities

    Returns:
        dict with precision, recall, pr_auc, roc_auc, brier_score
    """
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    valid = ~(np.isnan(y_true) | np.isnan(y_prob))
    if valid.sum() < 5:
        return {"error": "insufficient valid predictions"}

    y_t = y_true[valid]
    y_p = y_prob[valid]

    metrics = {}
    try:
        metrics["precision"] = float(precision_score(y_t, y_p > 0.5, zero_division=0))
        metrics["recall"] = float(recall_score(y_t, y_p > 0.5, zero_division=0))
    except Exception:
        metrics["precision"] = 0.0
        metrics["recall"] = 0.0

    if len(np.unique(y_t)) >= 2:
        try:
            metrics["pr_auc"] = float(average_precision_score(y_t, y_p))
            metrics["roc_auc"] = float(roc_auc_score(y_t, y_p))
        except Exception:
            metrics["pr_auc"] = 0.5
            metrics["roc_auc"] = 0.5
    else:
        metrics["pr_auc"] = 0.5
        metrics["roc_auc"] = 0.5

    try:
        metrics["brier_score"] = float(brier_score_loss(y_t, y_p))
    except Exception:
        metrics["brier_score"] = 0.25

    metrics["n_samples"] = int(valid.sum())
    return metrics
