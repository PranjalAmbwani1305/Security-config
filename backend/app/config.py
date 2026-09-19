import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("SENTINEL_DB_PATH")
EVIDENCE_ROOT = os.getenv("SENTINEL_EVIDENCE_ROOT")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = os.getenv("HF_MODEL")
