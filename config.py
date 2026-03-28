import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5-mini")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-1")
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "10"))
CONTEXT_MESSAGES_LIMIT = int(os.getenv("CONTEXT_MESSAGES_LIMIT", "5"))

if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN в .env")

if not OPENAI_API_KEY:
    raise ValueError("Не найден OPENAI_API_KEY в .env")

PROMPTS_FILE = BASE_DIR / "prompts.json"
GENERATED_DIR = BASE_DIR / "generated_images"
GENERATED_DIR.mkdir(exist_ok=True)


def load_prompts() -> dict:
    if not PROMPTS_FILE.exists():
        raise FileNotFoundError(f"Файл не найден: {PROMPTS_FILE}")

    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "default_prompt" not in data or "prompts" not in data:
        raise ValueError("prompts.json должен содержать ключи 'default_prompt' и 'prompts'")

    default_prompt = data["default_prompt"]
    prompts = data["prompts"]

    if default_prompt not in prompts:
        raise ValueError("default_prompt должен существовать внутри prompts")

    return data