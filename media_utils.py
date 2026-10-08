"""Local FFmpeg helpers; standard library only, with no audio transcription."""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path


def binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    fallback = Path(r"D:\ffmpeg\bin") / f"{name}.exe"
    if fallback.is_file():
        return str(fallback)
    raise RuntimeError(f"找不到 {name}；请安装 FFmpeg 并加入 PATH（也支持 D:\\ffmpeg\\bin）。")


def run_media(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).stem} 失败：{result.stderr.strip()[-1800:]}")
    return result.stdout


def probe(path: Path) -> dict:
    return json.loads(run_media([binary("ffprobe"), "-v", "error", "-show_streams",
                                 "-show_format", "-of", "json", str(path)]))


def positive_number(value: object) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def video_info(path: Path) -> dict:
    data = probe(path)
    stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"
                   and not s.get("disposition", {}).get("attached_pic")), None)
    if stream is None:
        raise ValueError("没有可处理的视频轨。")
    duration = positive_number(stream.get("duration")) or positive_number(data.get("format", {}).get("duration"))
    width, height = int(stream.get("width", 0)), int(stream.get("height", 0))
    if not duration or width < 2 or height < 2:
        raise ValueError("视频时长或尺寸无效。")
    try:
        sar = float(Fraction(stream.get("sample_aspect_ratio", "1:1").replace(":", "/")))
    except (ValueError, ZeroDivisionError):
        sar = 1.0
    sar = sar if sar > 0 else 1.0
    rotation = float(stream.get("tags", {}).get("rotate", 0))
    for side in stream.get("side_data_list", []):
        if "rotation" in side:
            rotation = float(side["rotation"])
    if not math.isfinite(rotation) or abs(rotation / 90 - round(rotation / 90)) > 0.01:
        raise ValueError("暂不支持非 90 度倍数的视频旋转，请先将视频转正。")
    display_width, display_height = width * sar, float(height)
    if round(rotation / 90) % 2:
        display_width, display_height = display_height, display_width
    fps = 0.0
    for rate in (stream.get("avg_frame_rate"), stream.get("r_frame_rate")):
        try:
            fps = float(Fraction(rate))
        except (ValueError, TypeError, ZeroDivisionError):
            continue
        if fps > 0:
            break
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("无法确定视频帧率。")
    return {"duration": duration, "width": display_width, "height": display_height,
            "fps": fps, "hdr": stream.get("color_transfer") in {"smpte2084", "arib-std-b67"},
            "stream": stream, "streams": data["streams"]}


def publish(temp: Path, output: Path, overwrite: bool) -> None:
    """Publish only a complete file; do not replace existing files without opt-in."""
    if overwrite:
        os.replace(temp, output)
    elif os.name == "nt":
        os.rename(temp, output)
    else:
        os.link(temp, output)
        temp.unlink()


def audio_duration(path: Path, fmt: str, sample_rate: int | None) -> float:
    if fmt == "pcm":  # Fish PCM: signed 16-bit, mono, default 44.1 kHz.
        if path.stat().st_size < 2 or path.stat().st_size % 2:
            raise ValueError("PCM 音频长度无效。")
        return path.stat().st_size / (2 * (sample_rate or 44100))
    data = probe(path)
    if not any(s.get("codec_type") == "audio" for s in data.get("streams", [])):
        raise ValueError("返回文件不包含音频轨。")
    duration = positive_number(data.get("format", {}).get("duration"))
    if not duration:
        raise ValueError("无法读取生成音频的时长。")
    return duration
