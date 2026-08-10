"""Platform tool layer — typed wrappers around the service layer.

READ tools: always available, read-only operations.
WRITE tools: gated behind the same validation as API routes.
EXCLUDED: TRADING_MODE, ENABLE_LIVE_TRADING, SCHEDULER_AUTO_EXECUTE,
kill switch disengage — these are human-UI-only.
"""

from datetime import datetime, timedelta, timezone

from cudaquant.backtest.engine import DeterministicBacktester
from cudaquant.config.settings import settings
from cudaquant.data.schemas import BarFrequency, Order, OrderSide, OrderType
from cudaquant.data.synthetic import SyntheticDataGenerator
from cudaquant.experiments.engine import (
    ExperimentOrigin,
    get_shared_engine,
)
from cudaquant.features.dispatch import get_stats as get_dispatch_stats
from cudaquant.ml.registry import ModelStatus, get_shared_registry
from cudaquant.regimes.detector import RegimeDetector
from cudaquant.scheduler.service import SchedulerService
from cudaquant.strategies.implementations import (
    IntradayMomentum,
    MeanReversion,
    PairsRelativeValue,
)

STRATEGY_REGISTRY = {
    "intraday_momentum": IntradayMomentum,
    "mean_reversion": MeanReversion,
    "pairs_relative_value": PairsRelativeValue,
}


# ══════════════════════════════════════════════════════════════════════════════
# READ tools — always available
# ══════════════════════════════════════════════════════════════════════════════

def list_strategies() -> dict:
    """List available strategies with parameter schemas."""
    import inspect
    result = {}
    for name, cls in STRATEGY_REGISTRY.items():
        sig = inspect.signature(cls.__init__)
        params = {}
        for pname, param in sig.parameters.items():
            if pname == "self":
                continue
            info = {"name": pname}
            if param.default is not inspect.Parameter.empty:
                info["default"] = param.default
            if param.annotation is not inspect.Parameter.empty:
                info["type"] = getattr(param.annotation, "__name__", str(param.annotation))
            params[pname] = info
        result[name] = {"name": name, "parameters": params}
    return result


def list_experiments(status: str | None = None, origin: str | None = None) -> list[dict]:
    engine = get_shared_engine(settings.DUCKDB_PATH)
    exps = engine.list_all()
    if status:
        exps = [e for e in exps if e.status.value == status]
    if origin:
        exps = [e for e in exps if e.origin.value == origin]
    return [{"id": e.experiment_id, "hypothesis": e.hypothesis,
             "status": e.status.value, "origin": e.origin.value,
             "metrics": e.metrics, "created_at": e.created_at} for e in exps]


def get_experiment(experiment_id: str) -> dict | None:
    engine = get_shared_engine(settings.DUCKDB_PATH)
    e = engine.get(experiment_id)
    if not e:
        return None
    return {"id": e.experiment_id, "hypothesis": e.hypothesis,
            "status": e.status.value, "origin": e.origin.value,
            "changed_parameters": e.changed_parameters, "metrics": e.metrics}


def list_models(status: str | None = None) -> list[dict]:
    reg = get_shared_registry(settings.DUCKDB_PATH)
    models = reg.list_by_status(ModelStatus(status)) if status else reg.list_all()
    return [{"model_id": m.model_id, "family": m.family, "status": m.status.value,
             "metrics": m.metrics, "created_at": m.created_at} for m in models]


def get_model(model_id: str) -> dict | None:
    reg = get_shared_registry(settings.DUCKDB_PATH)
    m = reg.get(model_id)
    if not m:
        return None
    return {"model_id": m.model_id, "family": m.family, "status": m.status.value,
            "metrics": m.metrics, "hyperparameters": m.hyperparameters}


def get_model_live_performance(model_id: str) -> dict:
    """Realized performance indicators for a model."""
    from cudaquant.execution.order_service import OrderService
    reg = get_shared_registry(settings.DUCKDB_PATH)
    m = reg.get(model_id)
    if not m:
        return {"error": "model not found"}
    svc = OrderService()
    orders = svc.list_orders(status="closed", limit=100)
    filled = [o for o in orders if o.get("status") == "filled"]
    return {"model_id": model_id, "status": m.status.value,
            "promoted_at": m.promoted_at, "filled_orders": len(filled),
            "backtest_sharpe": m.metrics.get("sharpe")}


def run_backtest_result(strategy: str, params: dict, symbol: str = "AAPL",
                        days: int = 30, frequency: str = "5m") -> dict:
    """Run a backtest and return results (read — doesn't persist)."""
    cls = STRATEGY_REGISTRY.get(strategy)
    if not cls:
        return {"error": f"unknown strategy: {strategy}"}
    strat = cls(**params)
    gen = SyntheticDataGenerator(seed=42)
    end = datetime.now(timezone.utc)
    start = end.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    freq = BarFrequency(frequency)
    df = gen.generate_bars([symbol], start, end, freq)
    bt = DeterministicBacktester(initial_capital=100000, seed=42)
    result = bt.run(data=df, signal_fn=strat.generate_signals)
    return {"strategy": strategy, "params": params, "symbol": symbol,
            "metrics": result.get("metrics", {}),
            "trade_count": len(result.get("trades", []))}


def get_regime_state(symbol: str = "AAPL", days: int = 30) -> dict:
    detector = RegimeDetector()
    gen = SyntheticDataGenerator(seed=42)
    end = datetime.now(timezone.utc)
    start = end.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    df = gen.generate_bars([symbol], start, end, BarFrequency("5m"))
    return {"distribution": detector.regime_distribution(df)}


def get_scheduler_status() -> dict:
    svc = SchedulerService(db_path=settings.DUCKDB_PATH)
    return svc.get_state()


def get_dispatch_stats_tool() -> dict:
    return get_dispatch_stats()


def get_account() -> dict:
    from cudaquant.execution.order_service import OrderService
    svc = OrderService()
    try:
        acct = svc.get_account()
        return {"cash": acct.cash, "portfolio_value": acct.portfolio_value,
                "buying_power": acct.buying_power}
    except Exception as e:
        return {"error": str(e)}


def get_positions() -> list[dict]:
    from cudaquant.execution.order_service import OrderService
    svc = OrderService()
    return [{"symbol": p.symbol, "qty": p.qty, "market_value": p.market_value,
             "unrealized_pnl": p.unrealized_pnl} for p in svc.get_positions()]


def get_order_history(limit: int = 50) -> list[dict]:
    from cudaquant.execution.order_service import OrderService
    svc = OrderService()
    return svc.list_orders(limit=limit)


# ══════════════════════════════════════════════════════════════════════════════
# WRITE tools — must go through same validation as API routes
# ══════════════════════════════════════════════════════════════════════════════

def propose_experiment(hypothesis: str, params: dict | None = None,
                       notes: str = "") -> dict:
    """Propose a new experiment (manual origin)."""
    engine = get_shared_engine(settings.DUCKDB_PATH)
    exp = engine.propose(
        hypothesis=hypothesis,
        origin=ExperimentOrigin.MANUAL,
        changed_parameters=params or {},
        notes=notes,
    )
    return {"experiment_id": exp.experiment_id, "status": exp.status.value}


def promote_model(model_id: str) -> dict:
    reg = get_shared_registry(settings.DUCKDB_PATH)
    m = reg.get(model_id)
    if not m:
        return {"error": "model not found"}
    if m.status == ModelStatus.CANDIDATE:
        ok = reg.promote_to_challenger(model_id)
    elif m.status == ModelStatus.CHALLENGER:
        ok = reg.promote_to_champion(model_id)
    else:
        return {"error": f"cannot promote from status: {m.status.value}"}
    return {"success": ok, "model_id": model_id,
            "new_status": reg.get(model_id).status.value}


def retire_model(model_id: str) -> dict:
    reg = get_shared_registry(settings.DUCKDB_PATH)
    ok = reg.retire(model_id)
    return {"success": ok, "model_id": model_id}


def run_scheduler_job_now(job_name: str) -> dict:
    valid = {"ingest", "retrain", "evaluate", "llm_analyze"}
    if job_name not in valid:
        return {"error": f"unknown job: {job_name}"}
    svc = SchedulerService(db_path=settings.DUCKDB_PATH)
    return svc.run_now(job_name)


def submit_paper_order(symbol: str, side: str, qty: float,
                       order_type: str = "market",
                       limit_price: float | None = None) -> dict:
    """Submit a paper order through the FULL gate chain.

    Goes through OrderService → config gate → RiskGovernor → KillSwitch.
    Returns the same (success, message, order_id) tuple as the API.
    """
    if settings.TRADING_MODE != "paper":
        return {"success": False, "message": "submit_paper_order requires TRADING_MODE=paper"}
    if settings.live_trading_enabled:
        return {"success": False, "message": "paper mode with ENABLE_LIVE_TRADING=True — inconsistent"}

    from cudaquant.execution.order_service import OrderService
    svc = OrderService()

    try:
        order = Order(
            symbol=symbol,
            side=OrderSide(side.lower()),
            order_type=OrderType(order_type.lower()),
            qty=qty,
            limit_price=limit_price,
        )
    except (KeyError, ValueError) as e:
        return {"success": False, "message": f"invalid order: {e}"}

    ok, msg, order_id = svc.submit_order(order)
    return {"success": ok, "message": msg, "order_id": order_id}


# ══════════════════════════════════════════════════════════════════════════════
# Tool registry — only these are exposed to LLM interfaces
# ══════════════════════════════════════════════════════════════════════════════

READ_TOOLS: dict[str, callable] = {
    "list_strategies": list_strategies,
    "list_experiments": list_experiments,
    "get_experiment": get_experiment,
    "list_models": list_models,
    "get_model": get_model,
    "get_model_live_performance": get_model_live_performance,
    "run_backtest_result": run_backtest_result,
    "get_regime_state": get_regime_state,
    "get_scheduler_status": get_scheduler_status,
    "get_dispatch_stats": get_dispatch_stats_tool,
    "get_account": get_account,
    "get_positions": get_positions,
    "get_order_history": get_order_history,
}

WRITE_TOOLS: dict[str, callable] = {
    "propose_experiment": propose_experiment,
    "promote_model": promote_model,
    "retire_model": retire_model,
    "run_scheduler_job_now": run_scheduler_job_now,
    "submit_paper_order": submit_paper_order,
}
