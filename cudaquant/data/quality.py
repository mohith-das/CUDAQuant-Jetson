"""Data quality checks for market data."""


import pandas as pd


def check_duplicates(df: pd.DataFrame) -> list[dict]:
    """Find duplicate (symbol, timestamp) rows.

    Returns list of {"symbol": str, "timestamp": datetime, "issue": str}.
    """
    issues: list[dict] = []
    dup_mask = df.duplicated(subset=["symbol", "timestamp"], keep=False)
    dup_rows = df[dup_mask]
    for _, row in dup_rows.iterrows():
        issues.append({
            "symbol": row["symbol"],
            "timestamp": row["timestamp"],
            "issue": "Duplicate (symbol, timestamp) row",
        })
    return issues


def check_missing_bars(df: pd.DataFrame, frequency: str) -> list[dict]:
    """Detect gaps in expected bar schedule.

    Args:
        df: DataFrame with symbol, timestamp columns.
        frequency: pandas frequency string (e.g. '1min', '5min', '1h').

    Returns list of issue dicts.
    """
    issues: list[dict] = []
    for symbol in df["symbol"].unique():
        sym_df = df[df["symbol"] == symbol].sort_values("timestamp")
        if len(sym_df) < 2:
            continue
        expected = pd.date_range(
            start=sym_df["timestamp"].min(),
            end=sym_df["timestamp"].max(),
            freq=frequency,
        )
        actual_times = set(sym_df["timestamp"])
        for t in expected:
            if t not in actual_times:
                issues.append({
                    "symbol": symbol,
                    "timestamp": t,
                    "issue": f"Missing bar at expected time (freq={frequency})",
                })
    return issues


def check_ohlc_validity(df: pd.DataFrame) -> list[dict]:
    """Validate OHLC relationships for every row.

    Returns list of {"symbol": str, "timestamp": datetime, "issue": str}.
    """
    issues: list[dict] = []
    for _, row in df.iterrows():
        o, h, low, c = row["open"], row["high"], row["low"], row["close"]
        problems = []
        if h < max(o, c):
            problems.append("high < max(open, close)")
        if low > min(o, c):
            problems.append("low > min(open, close)")
        if problems:
            issues.append({
                "symbol": row["symbol"],
                "timestamp": row["timestamp"],
                "issue": "; ".join(problems),
            })
    return issues


def check_negative_prices(df: pd.DataFrame) -> list[dict]:
    """Find any bar with price <= 0.

    Returns list of {"symbol": str, "timestamp": datetime, "issue": str}.
    """
    issues: list[dict] = []
    price_cols = ["open", "high", "low", "close"]
    for _, row in df.iterrows():
        bad = [c for c in price_cols if row.get(c, 0) <= 0]
        if bad:
            issues.append({
                "symbol": row["symbol"],
                "timestamp": row["timestamp"],
                "issue": f"Non-positive prices: {bad}",
            })
    return issues


def check_unsorted(df: pd.DataFrame) -> list[dict]:
    """Check that timestamps are strictly increasing per symbol.

    Returns list of {"symbol": str, "timestamp": datetime, "issue": str}.
    """
    issues: list[dict] = []
    for symbol in df["symbol"].unique():
        sym_ts = df[df["symbol"] == symbol]["timestamp"].values
        for i in range(1, len(sym_ts)):
            if sym_ts[i] <= sym_ts[i - 1]:
                issues.append({
                    "symbol": symbol,
                    "timestamp": sym_ts[i],
                    "issue": f"Timestamp not strictly increasing (prev: {sym_ts[i-1]})",
                })
    return issues
