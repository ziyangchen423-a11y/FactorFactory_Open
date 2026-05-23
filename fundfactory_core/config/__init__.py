"""Configuration module."""
from fundfactory_core.config.paths import PROJECT_ROOT, resolve_path, resolve_path_str, ensure_dir
from fundfactory_core.config.settings import (
    settings,
    PROJECT_ROOT,
    DB_PATH,
    OUTPUT_DIR,
    TUSHARE_TOKEN,
    PROVIDER,
    DEFAULT_SYNC_START,
    DRY_RUN,
    REQUIRE_CONFIRM,
)
