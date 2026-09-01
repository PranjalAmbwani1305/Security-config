import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("SENTINEL_DB_PATH")
EVIDENCE_ROOT = os.getenv("SENTINEL_EVIDENCE_ROOT")