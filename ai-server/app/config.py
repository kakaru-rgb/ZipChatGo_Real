import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def get_openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def get_spring_server_base_url() -> str:
    return (
        os.getenv("SPRING_SERVER_BASE_URL", "http://127.0.0.1:8080").strip()
        or "http://127.0.0.1:8080"
    )
