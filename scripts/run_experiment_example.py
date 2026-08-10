"""Example: run a full experiment loop end-to-end.

Ties together pieces that exist as separate APIs but have no CLI wrapper yet:
SyntheticDataGenerator -> ExperimentEngine (propose/track) ->
BatchedExperimentRunner (actually execute backtests) -> ModelRegistry
(persist the winner). Prints which backend (GPU/CPU) each feature call used
via features.dispatch.get_stats(), so you can see it engage or not.

Usage:
    python scripts/run_experiment_example.py
    python scripts/run_experiment_example.py --frequency 1m --days 25
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from cudaquant.backtest.engine import DeterministicBacktester
from cudaquant.data.schemas import BarFrequency
from cudaquant.data.synthetic import SyntheticDataGenerator
from cudaquant.experiments.engine import ExperimentEngine, ExperimentStatus
from cudaquant.experiments.runner import BatchedExperimentRunner
from cudaquant.features import dispatch
from cudaquant.ml.registry import ModelRecord, ModelRegistry
from cudaquant.strategies.implementations import MeanReversion

SYMBOL = "AAPL"
FREQ_MAP = {"1m": BarFrequency.MINUTE_1, "5m": BarFrequency.MINUTE_5, "1d": BarFrequency.DAY_1}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frequency", default="1d", choices=FREQ_MAP)
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    # 1. Data — synthetic, deterministic, no API keys needed.
    gen = SyntheticDataGenerator(seed=args.seed)
    start = datetime(2023, 1, 1)
    end = start + timedelta(days=args.days)
    data = gen.generate_bars([SYMBOL], start, end, FREQ_MAP[args.frequency], seed=args.seed)
    print(f"Generated {len(data)} {args.frequency} bars for {SYMBOL}")

    # 2. Propose a grid of experiments (tracked, budgeted, auditable).
    engine = ExperimentEngine()
    param_grid = {
        "window": [10, 20, 30, 50],
        "entry_threshold": [1.5, 2.0, 2.5],
    }
    base_params = {"exit_threshold": 0.5}
    exp_ids = engine.grid_search(
        base_params=base_params,
        param_grid=param_grid,
        hypothesis_template="mean_reversion window={window} entry={entry_threshold}",
    )
    print(f"Proposed {len(exp_ids)} experiments")

    # 3. Actually run them — this is the part that touches GPU dispatch.
    dispatch.reset_stats()
    runner = BatchedExperimentRunner(backtester_factory=lambda: DeterministicBacktester(seed=42))
    results = runner.run_grid(
        data=data,
        strategy_factory=lambda p: MeanReversion(
            window=p["window"],
            entry_threshold=p["entry_threshold"],
            exit_threshold=p["exit_threshold"],
        ),
        param_grid=param_grid,
        base_params=base_params,
    )

    # 4. Record results back onto the tracked experiments.
    for exp_id, result in zip(exp_ids, results, strict=True):
        engine.complete(
            exp_id,
            metrics=result["metrics"],
            result=f"sharpe={result['metrics'].get('sharpe', 0):.3f}",
            status=ExperimentStatus.BACKTEST_PASSED,
        )

    # 5. Rank by Sharpe, show the leaderboard.
    ranked = sorted(results, key=lambda r: r["metrics"].get("sharpe", float("-inf")), reverse=True)
    print("\nTop 3 by Sharpe:")
    for r in ranked[:3]:
        m = r["metrics"]
        print(
            f"  {r['params']}  sharpe={m.get('sharpe', 0):.3f}  "
            f"return={m.get('total_return', 0):.3%}  trades={m.get('trade_count', 0)}"
        )

    # 6. GPU dispatch observability — did any of this actually run on GPU?
    stats = dispatch.get_stats()
    print(f"\nDispatch stats: {stats}")
    if not stats["gpu_calls"]:
        print(
            f"(No GPU calls — {len(data)} bars is below the measured GPU thresholds. "
            "Try --frequency 1m --days 25 for ~36k bars, enough to cross the "
            "rolling_zscore threshold of 20k.)"
        )

    # 7. Register the winning config as a candidate model for tracking.
    best = ranked[0]
    registry = ModelRegistry()
    record = ModelRecord(
        model_id=f"mean_reversion_{best['params']['window']}_{best['params']['entry_threshold']}",
        family="mean_reversion",
        hyperparameters=best["params"],
        metrics=best["metrics"],
        seed=42,
    )
    registry.register(record)
    print(f"\nRegistered candidate: {record.model_id}")


if __name__ == "__main__":
    main()
