"""Application configuration — pydantic-settings backed by environment and .env.

Values are read (in priority order) from the process environment and the
``.env`` file in the project root (loaded via python-dotenv through
pydantic-settings). Never hard-code secrets in this file — Alpaca/LLM
credentials come from env/config only.
"""
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from cudaquant.risk.kill_switch import LIVE_ACK_VALUE


class Settings(BaseSettings):
    """Runtime configuration for CUDAQuant-Jetson.

    Live trading is gated: it is only active when ``TRADING_MODE="live"``
    AND ``ENABLE_LIVE_TRADING=true``. See :attr:`live_trading_enabled`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # tolerate env keys for not-yet-declared providers (e.g. FMP/Finnhub)
    )

    # ── Trading mode ──────────────────────────────────────────────────────────
    TRADING_MODE: Literal["paper", "live"] = "paper"
    # Acknowledgement string. Live trading is only eligible when this equals
    # KillSwitch.LIVE_ACK_VALUE ("I_UNDERSTAND_LIVE_TRADING_RISK") AND
    # TRADING_MODE=live. The runtime TradingModeService may still keep the
    # effective mode on paper until all runtime gates pass.
    ENABLE_LIVE_TRADING: str = ""

    # ── Alpaca ────────────────────────────────────────────────────────────────
    ALPACA_API_KEY: str | None = None
    ALPACA_SECRET_KEY: str | None = None
    ALPACA_PAPER: bool = True
    ALPACA_DATA_FEED: str = "iex"

    # ── LLM (optional — system works fully without it) ────────────────────────
    LLM_PROVIDER: str | None = None
    LLM_API_KEY: str | None = None
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"
    LLM_DAILY_BUDGET_USD: float = 1.0
    LLM_MONTHLY_BUDGET_USD: float = 20.0
    LLM_MAX_CALLS_PER_DAY: int = 50
    LLM_MAX_TOKENS_PER_CALL: int = 8000

    # ── LLM research tools (optional — each degrades gracefully if unset) ──────
    BRAVE_SEARCH_API_KEY: str | None = None
    TAVILY_API_KEY: str | None = None
    FIRECRAWL_API_KEY: str | None = None

    # ── Finance data providers (optional) ────────────────────────────────────
    FMP_API_KEY: str | None = None
    FINNHUB_API_KEY: str | None = None

    # ── Alerting (optional) ─────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    # ── Alerts (optional — Telegram alerting skips silently if unset) ──────────
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    # ── Server ────────────────────────────────────────────────────────────────
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    API_AUTH_TOKEN: str = ""  # REQUIRED when HOST != 127.0.0.1

    # ── Storage ───────────────────────────────────────────────────────────────
    DATA_DIR: str = "./data"
    DUCKDB_PATH: str = "./data/cudaquant.duckdb"

    # ── Jetson / GPU ──────────────────────────────────────────────────────────
    CUDA_ENABLED: bool = True
    GPU_BACKTEST_BATCH_SIZE: int = 1024

    # ── Risk limits (paper defaults) ──────────────────────────────────────────
    MAX_POSITION_NOTIONAL: float = 100000
    MAX_TOTAL_EXPOSURE: float = 500000
    MAX_DAILY_TRADES: int = 50
    MAX_DAILY_LOSS: float = 5000
    MAX_DRAWDOWN_PCT: float = 20
    KILL_SWITCH_FILE: str = "./.kill_switch"

    @property
    def live_trading_enabled(self) -> bool:
        """Live trading is active only when explicitly enabled AND mode is live.

        Boot-time semantics (env/.env only) — the runtime TradingModeService
        is the authority for the *effective* mode once the process is running.
        """
        return (
            self.TRADING_MODE == "live"
            and self.ENABLE_LIVE_TRADING == LIVE_ACK_VALUE
        )


settings = Settings()
