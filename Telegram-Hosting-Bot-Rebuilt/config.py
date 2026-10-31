import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
ROOT = Path(__file__).resolve().parent
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
HOSTING_DIR = Path(os.getenv("HOSTING_DIR", str(ROOT / "hosted_bots"))).resolve()
DATABASE_PATH = str(Path(os.getenv("DATABASE_PATH", str(ROOT / "data/hosting.db"))).resolve())
MAX_FILE_SIZE_MB = max(1, int(os.getenv("MAX_FILE_SIZE_MB", "10")))
MAX_EXTRACTED_MB = max(1, int(os.getenv("MAX_EXTRACTED_MB", "30")))
MAX_BOTS_PER_USER = max(1, int(os.getenv("MAX_BOTS_PER_USER", "3")))
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "python:3.12-slim")
CONTAINER_MEMORY = os.getenv("CONTAINER_MEMORY", "256m")
CONTAINER_CPUS = os.getenv("CONTAINER_CPUS", "0.50")
CONTAINER_PIDS = os.getenv("CONTAINER_PIDS", "64")
CONTAINER_NETWORK = os.getenv("CONTAINER_NETWORK", "bridge")
def validate_config():
    if not BOT_TOKEN or ":" not in BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing or malformed in .env")
    if not ADMIN_IDS:
        raise RuntimeError("ADMIN_IDS must contain at least one numeric Telegram user ID")
    if CONTAINER_NETWORK not in {"bridge", "none"}:
        raise RuntimeError("CONTAINER_NETWORK must be bridge or none")
