"""Transaction cost models for backtesting.

Costs are expressed as per-share commissions plus basis-point (bp) slippage
and spread. One basis point equals 1/10000 of the reference price.

- Slippage: adverse price impact. A buy fills above the reference price, a
  sell fills below it.
- Spread: total bid/ask spread. Each fill crosses half the spread (buyers pay
  mid + spread/2, sellers receive mid - spread/2).
- Commission: flat USD per share, charged on every fill.

``apply_costs`` is the single entry point the backtest engine uses, so every
fill is charged identically and deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass

# One basis point as a fraction of price.
_BPS = 1e-4

VALID_SIDES = frozenset({"buy", "sell"})


@dataclass
class CostModel:
    """Fixed cost configuration applied to every fill.

    Attributes:
        commission_per_share: USD charged per share on each fill.
        slippage_bps: adverse price impact in basis points. A buy pays more,
            a sell receives less.
        spread_bps: total bid/ask spread in basis points. Half the spread is
            crossed on each fill.
        latency_ms: simulated execution delay in milliseconds. Informational
            metadata for now; the engine models delay as bars and never uses
            wall-clock time.
    """

    commission_per_share: float = 0.005
    slippage_bps: float = 1.0
    spread_bps: float = 1.0
    latency_ms: int = 0


# Predefined cost scenarios for sensitivity analysis.
SCENARIO_BASELINE = CostModel()
SCENARIO_2X_SLIPPAGE = CostModel(slippage_bps=2.0)
SCENARIO_WIDE_SPREAD = CostModel(spread_bps=5.0)
SCENARIO_DELAYED = CostModel(latency_ms=100)


def apply_costs(
    fill_price: float,
    side: str,
    qty: int,
    cost_model: CostModel,
) -> tuple[float, float]:
    """Apply spread, slippage, and commission to a fill.

    Args:
        fill_price: reference price the fill would occur at with no costs.
        side: ``"buy"`` or ``"sell"``.
        qty: number of shares (must be positive).
        cost_model: cost configuration.

    Returns:
        ``(adjusted_price, total_cost)`` where ``adjusted_price`` is the
        execution price after the adverse spread/slippage adjustment and
        ``total_cost`` is the full cost of the fill in currency:
        ``commission + qty * |adjusted_price - fill_price|``.

    Raises:
        ValueError: if ``side`` is invalid, ``qty`` is not positive, or
            ``fill_price`` is not positive.
    """
    if qty <= 0:
        raise ValueError(f"qty must be positive, got {qty}")
    if side not in VALID_SIDES:
        raise ValueError(f"side must be one of {sorted(VALID_SIDES)}, got {side!r}")
    if fill_price <= 0:
        raise ValueError(f"fill_price must be positive, got {fill_price}")

    # Buyers pay up (positive direction), sellers receive down (negative).
    direction = 1.0 if side == "buy" else -1.0
    adverse_bps = cost_model.slippage_bps + cost_model.spread_bps / 2.0
    adjusted_price = fill_price * (1.0 + direction * adverse_bps * _BPS)

    commission = cost_model.commission_per_share * qty
    slippage_cost = qty * abs(adjusted_price - fill_price)
    total_cost = commission + slippage_cost
    return adjusted_price, total_cost
