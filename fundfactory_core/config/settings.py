"""
FactorFactory Open - Core configuration module.

This module provides the foundational settings for the open-source version.
All paths are configurable via environment variables with sensible defaults.

Usage:
    from fundfactory_core.config import settings
    from fundfactory_core.config.settings import DB_PATH, OUTPUT_DIR

For production, set environment variables in .env file at PROJECT_ROOT.
"""
from fundfactory_core.config.paths import PROJECT_ROOT, resolve_path_str, ensure_dir


def _get_env(key: str, default: str = "") -> str:
    """Get environment variable, falling back to default."""
    import os
    return os.getenv(key, default)


# ======================== Project Root ========================
# Expose project root
PROJECT_ROOT = PROJECT_ROOT


# ======================== Tushare ========================
TUSHARE_TOKEN = _get_env("TUSHARE_TOKEN", "")

# ======================== Database ========================
_DB_PATH_RAW = _get_env("FUNDFACTORY_DB_PATH", "data/factorfactory_open.db")
DB_PATH = resolve_path_str(_DB_PATH_RAW)

# Ensure DB directory exists
_db_dir_raw = _get_env("FUNDFACTORY_DB_PATH", "data/factorfactory_open.db")
if _db_dir_raw != ":memory:" and "://" not in _db_dir_raw:
    import os
    _db_dirname = os.path.dirname(_db_dir_raw)
    if _db_dirname:
        ensure_dir(_db_dirname)

# ======================== Directories ========================
_OUTPUT_DIR_RAW = _get_env("FUNDFACTORY_OUTPUT_DIR", "output")
OUTPUT_DIR = resolve_path_str(_OUTPUT_DIR_RAW)

# Ensure output directory exists
ensure_dir(_OUTPUT_DIR_RAW)

# ======================== Data Provider ========================
PROVIDER = _get_env("FUNDFACTORY_PROVIDER", "tushare")

# ======================== Sync Settings ========================
DEFAULT_SYNC_START = _get_env("FUNDFACTORY_SYNC_START", "20200101")

# ======================== Backtest Settings ========================
DEFAULT_BENCHMARK = _get_env("FUNDFACTORY_BENCHMARK", "000300.SH")
DEFAULT_FEE_RATE = float(_get_env("FUNDFACTORY_FEE_RATE", "0.0003"))
DEFAULT_SLIPPAGE = float(_get_env("FUNDFACTORY_SLIPPAGE", "0.0005"))
DEFAULT_REBALANCE_FREQ = int(_get_env("FUNDFACTORY_REBALANCE_FREQ", "20"))
DEFAULT_TOP_PCT = float(_get_env("FUNDFACTORY_TOP_PCT", "0.1"))
DEFAULT_INITIAL_CASH = float(_get_env("FUNDFACTORY_INITIAL_CASH", "1000000"))

# ======================== Safety ========================
DRY_RUN = _get_env("DRY_RUN", "true").lower() in {"1", "true", "yes"}
REQUIRE_CONFIRM = _get_env("REQUIRE_CONFIRM", "true").lower() in {"1", "true", "yes"}

# ======================== Logging ========================
LOG_LEVEL = _get_env("LOG_LEVEL", "INFO")


# ======================== Settings Container ========================
class Settings:
    """Convenience container for all settings."""

    def __repr__(self):
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith("_"))
        return f"Settings({attrs})"


settings = Settings()
settings.PROJECT_ROOT = PROJECT_ROOT
settings.TUSHARE_TOKEN = TUSHARE_TOKEN
settings.DB_PATH = DB_PATH
settings.OUTPUT_DIR = OUTPUT_DIR
settings.PROVIDER = PROVIDER
settings.DEFAULT_SYNC_START = DEFAULT_SYNC_START
settings.DEFAULT_BENCHMARK = DEFAULT_BENCHMARK
settings.DEFAULT_FEE_RATE = DEFAULT_FEE_RATE
settings.DEFAULT_SLIPPAGE = DEFAULT_SLIPPAGE
settings.DEFAULT_REBALANCE_FREQ = DEFAULT_REBALANCE_FREQ
settings.DEFAULT_TOP_PCT = DEFAULT_TOP_PCT
settings.DEFAULT_INITIAL_CASH = DEFAULT_INITIAL_CASH
settings.DRY_RUN = DRY_RUN
settings.REQUIRE_CONFIRM = REQUIRE_CONFIRM
settings.LOG_LEVEL = LOG_LEVEL
