"""ML models, training, inference, model registry."""

from cudaquant.ml.gpu_models import (
    TSLogisticRegressionGPU,
    create_logistic_regression,
    get_ml_backend,
)
from cudaquant.ml.models import (
    TSLogisticRegression,
    TSRandomForest,
    evaluate_classifier,
    prepare_features,
    prepare_targets,
)
from cudaquant.ml.registry import ModelRecord, ModelRegistry, ModelStatus
from cudaquant.ml.training import TrainingRun, TrainingService, get_shared_training_service

__all__ = [
    "TSLogisticRegression",
    "TSRandomForest",
    "TSLogisticRegressionGPU",
    "create_logistic_regression",
    "get_ml_backend",
    "evaluate_classifier",
    "prepare_features",
    "prepare_targets",
    "ModelRecord",
    "ModelRegistry",
    "ModelStatus",
    "TrainingRun",
    "TrainingService",
    "get_shared_training_service",
]
