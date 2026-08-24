from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
DEFAULT_PREFIX = os.getenv("DEFAULT_PREFIX", ",").strip() or ","
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "bot.db"))
