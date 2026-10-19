"""Runtime configuration. Everything comes from environment variables with local defaults."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("GTM_DATA_DIR", ROOT / "data"))
SEED_FILE = DATA_DIR / "seed" / "radixark-crm-seed.json"
SOURCES_DIR = DATA_DIR / "sources"

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'gtm.db'}")
# Railway's Postgres plugin provides postgres://; SQLAlchemy 2 wants postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

HF_TOKEN = os.environ.get("HF_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

PRODUCTS = ["SGLang", "Miles", "SGLang-Omni"]
RADIXARK_REPOS = ["sgl-project/sglang", "radixark/miles"]
RELATIONSHIP_STATUSES = ["Unset", "Customer", "Partner", "Open-source user", "Prospect", "None"]
PRIORITIES = ["Unset", "P0", "P1", "P2", "P3"]
RUBRIC_VERSION = "v1"
