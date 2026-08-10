"""GPU-accelerated ML models using PyTorch CUDA.

Each class mirrors the CPU sklearn interface (fit/predict_proba/predict)
and falls back gracefully when CUDA is unavailable.

Note: Uses uppercase X/y naming (standard ML matrix/target convention).
"""
# ruff: noqa: N806

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class TSLogisticRegressionGPU:
    """GPU logistic regression using PyTorch CUDA.

    Same fit/predict_proba/predict interface as TSLogisticRegression (CPU).
    Trains with gradient descent on GPU tensors. Falls back to CPU if
    CUDA is unavailable or config disabled.

    Implements binary cross-entropy with L2 regularization.
    """

    def __init__(self, lr: float = 0.01, epochs: int = 100, l2: float = 0.001, **kwargs):
        self.lr = lr
        self.epochs = epochs
        self.l2 = l2
        self._params = kwargs
        self._weights: Any = None
        self._bias: Any = None
        self._feature_names: list[str] = []
        self._trained = False

    def fit(
        self,
        X: np.ndarray,  # noqa: N803
        y: np.ndarray,
        feature_names: list[str] | None = None,
    ) -> "TSLogisticRegressionGPU":
        """Train on chronologically ordered data using GPU gradient descent."""
        import torch

        if feature_names:
            self._feature_names = feature_names
        elif hasattr(X, "columns"):
            self._feature_names = list(X.columns)

        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32)

        valid = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X_clean = X[valid]
        y_clean = (y[valid] > 0).astype(np.float32)

        if len(X_clean) < 10 or len(np.unique(y_clean)) < 2:
            self._trained = False
            return self

        n_features = X_clean.shape[1]

        # Initialize weights
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._weights = torch.zeros(n_features, 1, device=device, requires_grad=True)
        self._bias = torch.zeros(1, device=device, requires_grad=True)

        X_t = torch.tensor(X_clean, device=device, dtype=torch.float32)
        y_t = torch.tensor(y_clean, device=device, dtype=torch.float32).unsqueeze(1)

        for _epoch in range(self.epochs):
            # Forward
            logits = X_t @ self._weights + self._bias
            probs = torch.sigmoid(logits)
            loss = torch.nn.functional.binary_cross_entropy(probs, y_t)
            if self.l2 > 0:
                loss = loss + self.l2 * (self._weights ** 2).sum()

            # Backward
            loss.backward()

            # Update (simple SGD)
            with torch.no_grad():
                self._weights -= self.lr * self._weights.grad
                self._bias -= self.lr * self._bias.grad
                self._weights.grad.zero_()
                self._bias.grad.zero_()

        self._trained = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:  # noqa: N803
        """Return probability of positive class."""
        import torch

        if not self._trained or self._weights is None:
            return np.full(len(X), 0.5, dtype=np.float64)

        X = np.asarray(X, dtype=np.float32)
        device = self._weights.device
        X_t = torch.tensor(X, device=device, dtype=torch.float32)
        with torch.no_grad():
            logits = X_t @ self._weights + self._bias
            probs = torch.sigmoid(logits)
        return probs.cpu().numpy().flatten().astype(np.float64)

    def predict(self, X: np.ndarray) -> np.ndarray:  # noqa: N803
        """Return binary predictions."""
        return (self.predict_proba(X) > 0.5).astype(int)


def _gpu_ml_available() -> bool:
    """Check if GPU ML (torch CUDA) is available at runtime."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def get_ml_backend() -> str:
    """Return current ML backend: 'gpu' or 'cpu'."""
    from cudaquant.config.settings import settings
    if not settings.CUDA_ENABLED:
        return "cpu"
    if _gpu_ml_available():
        return "gpu"
    return "cpu"


# ── Dispatched model factory ─────────────────────────────────────────────────


def create_logistic_regression(**kwargs) -> Any:
    """Create a logistic regression model using the best available backend.

    Returns TSLogisticRegressionGPU if GPU is available, else TSLogisticRegression.
    Both implement the same fit/predict_proba/predict interface.
    """
    backend = get_ml_backend()
    if backend == "gpu":
        logger.debug("Using GPU logistic regression (torch CUDA)")
        return TSLogisticRegressionGPU(**kwargs)
    else:
        from cudaquant.ml.models import TSLogisticRegression
        logger.debug("Using CPU logistic regression (sklearn)")
        return TSLogisticRegression(**kwargs)
