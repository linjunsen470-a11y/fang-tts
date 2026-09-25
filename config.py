"""Load Fish Audio credentials from the local .env file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
def load_api_key() -> str:
    load_dotenv(ROOT / ".env")

    api_key = (
        os.getenv("FISH_AUDIO_API_KEY")
        or os.getenv("FISH_API_KEY")
        or ""
    ).strip()
    if not api_key:
        raise RuntimeError(
            "缺少 API Key。请在 .env 中配置 FISH_AUDIO_API_KEY。"
        )

    # Official SDK reads FISH_API_KEY.
    os.environ["FISH_API_KEY"] = api_key

    return api_key
