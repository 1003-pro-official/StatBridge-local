from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PORTABLE = PACKAGE_ROOT.name == 'statbridge_mcp_server'
PROJECT_ROOT = PACKAGE_ROOT.parent if PORTABLE else PACKAGE_ROOT.parents[1]
ENV_FILE = PACKAGE_ROOT / '.env' if PORTABLE else PROJECT_ROOT / '.env'


def _load_env() -> None:
    candidates = [
        ENV_FILE,
        Path.cwd() / '.env',
    ]
    for p in candidates:
        if p.exists():
            load_dotenv(p)
            return
    load_dotenv()


_load_env()

_data_root = PROJECT_ROOT / ('runtime_data' if PORTABLE else 'data')
_default_data = _data_root / 'processed'
_default_tables = _data_root / 'tables'


def _resolve_data_dir() -> Path:
    return Path(os.getenv('STATBRIDGE_DATA_DIR', str(_default_data))).resolve()


def _resolve_tables_dir() -> Path:
    return Path(os.getenv('STATBRIDGE_TABLES_DIR', str(_default_tables))).resolve()


@dataclass(slots=True)
class Settings:
    kosis_api_key: str = os.getenv('KOSIS_API_KEY', '').strip()
    rate_limit_per_minute: int = int(os.getenv('KOSIS_RATE_LIMIT_PER_MINUTE', '50'))
    timeout: int = int(os.getenv('KOSIS_TIMEOUT', '45'))
    data_dir: Path = field(default_factory=_resolve_data_dir)
    tables_dir: Path = field(default_factory=_resolve_tables_dir)


settings = Settings()
