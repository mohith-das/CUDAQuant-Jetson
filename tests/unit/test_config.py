"""Unit tests for the application configuration system.

Targets ``cudaquant.config.settings.Settings`` (pydantic-settings).
Assumes defaults mirror ``.env.example``: paper trading, live trading OFF,
sane numeric limits, and optional credential fields defaulting to ``None``.
"""

import pytest
from pydantic import ValidationError

from cudaquant.config.settings import Settings

# Every field name the settings class reads from the environment, so default
# tests are hermetic even when the runner's shell exports these.
_SETTINGS_ENV_VARS = [
    "TRADING_MODE",
    "ENABLE_LIVE_TRADING",
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "ALPACA_PAPER",
    "ALPACA_DATA_FEED",
    "LLM_PROVIDER",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_DAILY_BUDGET_USD",
    "LLM_MONTHLY_BUDGET_USD",
    "LLM_MAX_CALLS_PER_DAY",
    "LLM_MAX_TOKENS_PER_CALL",
    "HOST",
    "PORT",
    "LOG_LEVEL",
    "DATA_DIR",
    "DUCKDB_PATH",
    "CUDA_ENABLED",
    "GPU_BACKTEST_BATCH_SIZE",
    "MAX_POSITION_NOTIONAL",
    "MAX_TOTAL_EXPOSURE",
    "MAX_DAILY_TRADES",
    "MAX_DAILY_LOSS",
    "MAX_DRAWDOWN_PCT",
    "KILL_SWITCH_FILE",
]


@pytest.fixture
def clean_env(monkeypatch):
    """Remove every known settings variable so defaults are unambiguous."""
    for name in _SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_loads_with_defaults_without_env_file(clean_env):
    """Settings() must succeed with no .env file and no env vars."""
    settings = Settings()
    assert settings.TRADING_MODE == "paper"


def test_trading_mode_defaults_to_paper(clean_env):
    assert Settings().TRADING_MODE == "paper"


def test_enable_live_trading_defaults_to_false(clean_env):
    settings = Settings()
    assert settings.ENABLE_LIVE_TRADING is False


def test_live_trading_off_by_default(clean_env):
    """The safety gate must be off unless BOTH switches are set."""
    assert Settings().live_trading_enabled is False


@pytest.mark.parametrize(
    ("trading_mode", "enable_live", "expected"),
    [
        ("paper", False, False),
        ("paper", True, False),
        ("live", False, False),
        ("live", True, True),
    ],
)
def test_live_trading_requires_both_gates(clean_env, trading_mode, enable_live, expected):
    """Live trading is active only when mode is live AND explicitly enabled."""
    settings = Settings(TRADING_MODE=trading_mode, ENABLE_LIVE_TRADING=enable_live)
    assert settings.live_trading_enabled is expected


def test_invalid_trading_mode_rejected(clean_env):
    with pytest.raises(ValidationError):
        Settings(TRADING_MODE="ultra-live")


def test_numeric_limits_have_reasonable_defaults(clean_env):
    settings = Settings()
    assert settings.MAX_POSITION_NOTIONAL == 100000
    assert settings.MAX_TOTAL_EXPOSURE == 500000
    assert settings.MAX_DAILY_TRADES == 50
    assert settings.MAX_DAILY_LOSS == 5000
    assert settings.MAX_DRAWDOWN_PCT == 20


def test_other_numeric_defaults(clean_env):
    settings = Settings()
    assert settings.PORT == 8000
    assert settings.GPU_BACKTEST_BATCH_SIZE == 1024
    assert settings.LLM_DAILY_BUDGET_USD == 1.0
    assert settings.LLM_MONTHLY_BUDGET_USD == 20.0
    assert settings.LLM_MAX_CALLS_PER_DAY == 50
    assert settings.LLM_MAX_TOKENS_PER_CALL == 8000


def test_optional_fields_default_to_none(clean_env):
    settings = Settings(_env_file=None)  # prevent reading real .env keys
    assert settings.ALPACA_API_KEY is None
    assert settings.ALPACA_SECRET_KEY is None
    assert settings.LLM_PROVIDER is None
    assert settings.LLM_API_KEY is None


def test_optional_fields_filled_from_environment(clean_env, monkeypatch):
    """Optional credential fields must be sourced from env, never hard-coded."""
    monkeypatch.setenv("ALPACA_API_KEY", "pk_test_123")
    monkeypatch.setenv("LLM_API_KEY", "sk_test_456")
    settings = Settings()
    assert settings.ALPACA_API_KEY == "pk_test_123"
    assert settings.LLM_API_KEY == "sk_test_456"


def test_env_overrides_defaults(clean_env, monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("MAX_POSITION_NOTIONAL", "250000")
    settings = Settings()
    assert settings.TRADING_MODE == "live"
    assert settings.MAX_POSITION_NOTIONAL == 250000


def test_module_level_settings_instance_is_sane(clean_env):
    """The shared module-level singleton must exist and default to paper."""
    from cudaquant.config.settings import settings

    assert settings.TRADING_MODE == "paper"
    assert settings.live_trading_enabled is False
