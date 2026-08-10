"""Deterministic backtesting engine, transaction costs, metrics."""

from cudaquant.backtest.costs import (
    SCENARIO_2X_SLIPPAGE,
    SCENARIO_BASELINE,
    SCENARIO_DELAYED,
    SCENARIO_WIDE_SPREAD,
    CostModel,
    apply_costs,
)
from cudaquant.backtest.engine import DeterministicBacktester
from cudaquant.backtest.metrics import compute_metrics

__all__ = [
    "DeterministicBacktester",
    "compute_metrics",
    "CostModel",
    "apply_costs",
    "SCENARIO_BASELINE",
    "SCENARIO_2X_SLIPPAGE",
    "SCENARIO_WIDE_SPREAD",
    "SCENARIO_DELAYED",
]
