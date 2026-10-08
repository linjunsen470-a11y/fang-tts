"""Single whole-script Fish TTS. Running synthesis is the user's confirmation."""
from __future__ import annotations

import argparse
import copy
import logging
import tempfile
from pathlib import Path

import httpx

from breaths import apply_breaths
from config import DEFAULT_MODEL, DEFAULT_TTS, ROOT, VOICE_REFERENCE_ID, load_api_key, read_tts_text, read_yaml
from fish_api import request_payload, synthesize as fish_synthesize
from media_utils import audio_duration, binary, publish

LOG = logging.getLogger("fish-tts")


def validate_config(data: dict, path: Path) -> tuple[Path, dict, str, bool]:
    unknown = set(data) - {"model", "reference_id", "text", "text_file", "output", "tts"}
    if unknown:
        raise ValueError(f"未知配置字段：{', '.join(sorted(map(str, unknown)))}；仅支持整段 TTS YAML。")
    if not isinstance(data.get("output"), str) or not data["output"].strip():
        raise ValueError("output 必须是非空文本。")
    text, text_path = read_tts_text(data, path)
    if data.get("model", DEFAULT_MODEL) != DEFAULT_MODEL:
        raise ValueError("模型固定为 s2.1-pro-free；音色可通过 reference_id 调整。")
    reference_id = data.get("reference_id", VOICE_REFERENCE_ID)
    options = data.get("tts", {})
    if not isinstance(options, dict):
        raise ValueError("tts 必须是键值映射。")
    merged = copy.deepcopy(DEFAULT_TTS)
    merged.update(options)
    if isinstance(options.get("prosody"), dict):
        merged["prosody"] = {**DEFAULT_TTS["prosody"], **options["prosody"]}
    breaths = merged.pop("breaths", False)
    if breaths is not True and breaths is not False:
        raise ValueError("tts.breaths 只能是 true 或 false。")
    request_payload(text, reference_id, merged)
    output = Path(data["output"])
    if not output.is_absolute():
        output = path.resolve().parent / output
    if output.suffix.lower() != f".{merged['format']}":
        raise ValueError("output 扩展名必须与 tts.format 一致。")
    for source in (path, text_path):
        if source is not None and (
            output.resolve() == source.resolve()
            or (output.exists() and source.exists() and output.samefile(source))
        ):
            raise ValueError("output 不能指向 YAML 或台词源文件，--overwrite 也不允许覆盖源文件。")
    return output, merged, text, breaths


def single_tts(path: Path, check: bool = False, overwrite: bool = False) -> None:
    data = read_yaml(path)
    output, options, text, breaths = validate_config(data, path)
    reference_id = data.get("reference_id", VOICE_REFERENCE_ID)
    if check:
        LOG.info("校验通过（未联网、未读取密钥）：%s → %s；音色 %s", path, output, reference_id)
        if output.exists():
            LOG.info("输出已存在；实际合成需更改文件名或显式使用 --overwrite。")
        return
    if output.exists() and not overwrite:
        raise ValueError(f"输出已存在：{output}；请换文件名，或使用 --overwrite。")
    if options["format"] != "pcm":
        binary("ffprobe")
    api_key = load_api_key()
    LOG.info("开始整段配音，model=%s，reference_id=%s", DEFAULT_MODEL, reference_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".tts-", suffix=output.suffix, dir=output.parent, delete=False) as handle:
            temp = Path(handle.name)
            handle.write(fish_synthesize(text, api_key, DEFAULT_MODEL, reference_id, options))
        if breaths:
            inserted, skipped = apply_breaths(temp, text, options.get("mp3_bitrate"))
            LOG.info("整段一次合成，句末气口 %d 处，跳过 %d 处。", inserted, skipped)
        duration = audio_duration(temp, options["format"], options.get("sample_rate"))
        size = temp.stat().st_size
        publish(temp, output, overwrite)
        LOG.info("完成：%s；%d 字节；实际时长 %.2f 秒。", output, size, duration)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fish Audio 整段配音；主动运行即确认台词已审核")
    parser.add_argument("config", nargs="?", type=Path, default=ROOT / "tts.yaml")
    parser.add_argument("--check", action="store_true", help="只做离线校验，不读取密钥或调用 API")
    parser.add_argument("--overwrite", action="store_true", help="允许成功合成后替换已有音频")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        single_tts(args.config, args.check, args.overwrite)
        return 0
    except httpx.HTTPStatusError as exc:
        LOG.error("Fish API 请求失败（HTTP %s）。请检查账户、权限或稍后重试。", exc.response.status_code)
    except httpx.RequestError:
        LOG.error("Fish API 网络连接失败或超时；未自动重试，请检查后手动重试。")
    except (OSError, ValueError, RuntimeError) as exc:
        LOG.error("失败：%s", exc)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
