"""Small direct REST client for the documented Fish Audio v1 TTS endpoint."""
from __future__ import annotations

import httpx
import math
import json

from config import DEFAULT_MODEL
from tag_catalog import validate_text

API_URL = "https://api.fish.audio/v1/tts"
BODY_FIELDS = {
    "temperature", "top_p", "chunk_length", "normalize", "format",
    "sample_rate", "mp3_bitrate", "opus_bitrate", "latency",
    "max_new_tokens", "repetition_penalty", "min_chunk_length",
    "condition_on_previous_chunks", "early_stop_threshold", "features",
    "pronunciation_dictionary",
}
PROSODY_FIELDS = {"speed", "volume", "normalize_loudness"}


def request_payload(text: str, reference_id: str, options: dict) -> dict:
    validate_text(text)
    if not isinstance(reference_id, str) or not reference_id.strip() or any(char.isspace() for char in reference_id):
        raise ValueError("reference_id 必须是非空、无空白字符的单说话人音色 ID。")
    if not isinstance(options, dict):
        raise ValueError("tts 必须是键值映射。")
    unknown = set(options) - BODY_FIELDS - {"prosody"}
    if unknown:
        raise ValueError(f"unsupported Fish API option(s): {', '.join(sorted(map(str, unknown)))}")
    prosody = options.get("prosody", {})
    if not isinstance(prosody, dict) or set(prosody) - PROSODY_FIELDS:
        raise ValueError("invalid prosody options")
    for name in ("temperature", "top_p", "repetition_penalty", "early_stop_threshold"):
        if name in options:
            _number(options[name], name)
    for name in ("speed", "volume"):
        if name in prosody:
            _number(prosody[name], f"prosody.{name}")
    for name in ("chunk_length", "min_chunk_length", "max_new_tokens", "mp3_bitrate", "opus_bitrate"):
        if name in options and type(options[name]) is not int:
            raise ValueError(f"{name} 必须是整数。")
    for name in ("normalize", "condition_on_previous_chunks"):
        if name in options and type(options[name]) is not bool:
            raise ValueError(f"{name} 必须是 true/false。")
    if "normalize_loudness" in prosody and type(prosody["normalize_loudness"]) is not bool:
        raise ValueError("prosody.normalize_loudness 必须是 true/false。")
    for name in ("format", "latency"):
        if name in options and not isinstance(options[name], str):
            raise ValueError(f"{name} 必须是字符串。")
    for name in ("temperature", "top_p"):
        if name in options and not 0 <= float(options[name]) <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
    if "speed" in prosody and not 0.5 <= float(prosody["speed"]) <= 2:
        raise ValueError("prosody.speed must be between 0.5 and 2")
    if "volume" in prosody and not -20 <= float(prosody["volume"]) <= 20:
        raise ValueError("prosody.volume must be between -20 and 20 dB")
    if "chunk_length" in options and not 100 <= int(options["chunk_length"]) <= 300:
        raise ValueError("chunk_length must be between 100 and 300")
    if "min_chunk_length" in options and not 0 <= int(options["min_chunk_length"]) <= 100:
        raise ValueError("min_chunk_length must be between 0 and 100")
    if "early_stop_threshold" in options and not 0 <= float(options["early_stop_threshold"]) <= 1:
        raise ValueError("early_stop_threshold must be between 0 and 1")
    if options.get("format", "mp3") not in {"mp3", "wav", "pcm", "opus"}:
        raise ValueError("format must be mp3, wav, pcm, or opus")
    if "mp3_bitrate" in options and options["mp3_bitrate"] not in {64, 128, 192}:
        raise ValueError("mp3_bitrate must be 64, 128, or 192 kbps")
    if "opus_bitrate" in options and options["opus_bitrate"] not in {-1000, 24000, 32000, 48000, 64000}:
        raise ValueError("opus_bitrate must be one of -1000, 24000, 32000, 48000, 64000 bps")
    if options.get("latency", "normal") not in {"low", "balanced", "normal"}:
        raise ValueError("latency must be low, balanced, or normal")
    if "max_new_tokens" in options and options["max_new_tokens"] <= 0:
        raise ValueError("max_new_tokens 必须为正整数。")
    if "repetition_penalty" in options and options["repetition_penalty"] <= 0:
        raise ValueError("repetition_penalty 必须为正数。")
    fmt = options.get("format", "mp3")
    rates = {"mp3": {32000, 44100}, "wav": {8000, 16000, 24000, 32000, 44100},
             "pcm": {8000, 16000, 24000, 32000, 44100}, "opus": {48000}}
    rate = options.get("sample_rate")
    if rate is not None and (type(rate) is not int or rate not in rates[fmt]):
        raise ValueError(f"sample_rate 不适用于 {fmt}；可选 {sorted(rates[fmt])} 或 null。")
    # Irrelevant bitrate fields may appear in old single-TTS files; omit from the request.
    options = dict(options)
    if fmt != "mp3":
        options.pop("mp3_bitrate", None)
    if fmt != "opus":
        options.pop("opus_bitrate", None)
    if "features" in options and (not isinstance(options["features"], list)
                                  or any(item != "quality-guard" for item in options["features"])):
        raise ValueError("features 仅支持官方列出的 quality-guard 字符串列表。")
    if "pronunciation_dictionary" in options:
        dictionary = options["pronunciation_dictionary"]
        if not isinstance(dictionary, dict) or not dictionary:
            raise ValueError("pronunciation_dictionary 必须为非空的官方 schema 对象。")
        try:
            json.dumps(dictionary, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("pronunciation_dictionary 必须可表示为标准 JSON。") from exc
    payload = {"text": text, "reference_id": reference_id, **options}
    return payload


def _number(value: object, name: str) -> None:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} 必须为有限数值，不能是字符串或布尔值。")


def synthesize(text: str, api_key: str, model: str, reference_id: str,
               options: dict, timeout: float = 180) -> bytes:
    if model != DEFAULT_MODEL:
        raise ValueError("model 必须使用项目固定模型。")
    payload = request_payload(text, reference_id, options)
    response = httpx.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "model": model},
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    if not response.content:
        raise RuntimeError("Fish Audio returned an empty audio response")
    return response.content
