"""Project defaults, YAML and local credentials."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = "s2.1-pro-free"
VOICE_REFERENCE_ID = "5c353fdb312f4888836a9a5680099ef0"
DEFAULT_TTS = {
    "format": "mp3", "normalize": True, "chunk_length": 200, "latency": "balanced",
    "prosody": {"speed": 1.0, "volume": 0.0, "normalize_loudness": True},
    "temperature": 0.7, "top_p": 0.7,
}


def read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"无法读取 YAML：{path}（{exc}）") from exc
    if not isinstance(data, dict):
        raise ValueError("YAML 根节点必须是键值映射。")
    return data


def read_tts_text(data: dict, path: Path) -> tuple[str, Path | None]:
    """Read exactly one script source, resolving file paths beside the YAML."""
    if ("text" in data) == ("text_file" in data):
        raise ValueError("text 与 text_file 必须且只能填写一个。")
    if "text" in data:
        text = data["text"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text 必须是非空文本。")
        return text, None

    filename = data["text_file"]
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("text_file 必须是非空文件路径。")
    text_path = Path(filename)
    if not text_path.is_absolute():
        text_path = path.resolve().parent / text_path
    try:
        # Decode the optional UTF-8 BOM without normalizing newlines or prose.
        text = text_path.read_bytes().decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError(f"台词文件必须使用 UTF-8 编码，请另存为 UTF-8：{text_path}") from exc
    except (OSError, ValueError) as exc:
        raise ValueError(f"无法读取台词文件：{text_path}（{exc}）") from exc
    if not text.strip():
        raise ValueError(f"台词文件不能为空：{text_path}")
    return text, text_path


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

    return api_key
