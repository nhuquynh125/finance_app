import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "app" / "data"
EXPORTS_DIR = DATA_DIR / "exports"
IMPORTS_DIR = DATA_DIR / "imports"
DB_PATH = DATA_DIR / "finance.db"

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

APP_NAME = "Finance AI"
APP_VERSION = "1.0.0"
CURRENCY = "VND"

for d in [DATA_DIR, EXPORTS_DIR, IMPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
