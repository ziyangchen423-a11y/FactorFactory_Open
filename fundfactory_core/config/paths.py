"""
FactorFactory Open - Path resolution module.

Provides stable project root detection and absolute path resolution.

Rules:
- PROJECT_ROOT priority:
  1. FACTORFACTORY_PROJECT_ROOT env var
  2. FUNDFACTORY_PROJECT_ROOT env var (legacy)
  3. fundfactory_core/.. (parent of fundfactory_core package)
- .env is loaded from PROJECT_ROOT/.env if it exists (silent failure)
- Relative paths in config vars are resolved from PROJECT_ROOT
"""
import os
from pathlib import Path

# ======================== Project Root ========================
# Determine project root
_env_root = os.environ.get("FACTORFACTORY_PROJECT_ROOT") or os.environ.get("FUNDFACTORY_PROJECT_ROOT", "")
if _env_root:
    PROJECT_ROOT = Path(_env_root).resolve()
else:
    # fundfactory_core/config/paths.py -> fundfactory_core/ -> project root
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ======================== Dotenv Loading ========================
def _load_dotenv():
    """Load .env from project root if it exists. Silent if missing."""
    dotenv_path = PROJECT_ROOT / ".env"
    if not dotenv_path.is_file():
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Parse KEY=VALUE
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Only set if not already in environment
                if key and value and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Silent failure - .env is optional
        pass


_load_dotenv()


# ======================== Path Helpers ========================
def resolve_path(path: str) -> Path:
    """
    Resolve a path string to an absolute Path object.

    - Absolute paths: returned as-is (resolved)
    - Relative paths: resolved from PROJECT_ROOT
    - Empty/None: returns PROJECT_ROOT
    """
    if not path:
        return PROJECT_ROOT
    p = Path(path)
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def resolve_path_str(path: str) -> str:
    """Resolve path and return as string."""
    return str(resolve_path(path))


def ensure_dir(path: str) -> None:
    """Ensure directory exists, creating if necessary."""
    p = resolve_path(path)
    p.mkdir(parents=True, exist_ok=True)
