"""Batch video compression for cloud upload. Python standard library + FFmpeg."""
from __future__ import annotations

import argparse
import csv
import logging
import tempfile
from collections import Counter
from pathlib import Path

from media_utils import binary, publish, run_media, video_info

ROOT = Path(__file__).resolve().parent
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
LOG = logging.getLogger("compress")


def dimensions(info: dict) -> tuple[int, int]:
    width, height = info["width"], info["height"]
    bound_w, bound_h = (720, 1280) if height > width else (1280, 720)
    factor = min(1.0, bound_w / width, bound_h / height)
    return max(2, int(width * factor) // 2 * 2), max(2, int(height * factor) // 2 * 2)


def video_filters(info: dict) -> str:
    width, height = dimensions(info)
    filters = [f"scale={width}:{height}", "setsar=1", f"fps={min(12.0, info['fps']):.8f}"]
    if info["hdr"]:
        available = run_media([binary("ffmpeg"), "-hide_banner", "-filters"])
        if not all(name in available for name in ("zscale", "tonemap")):
            raise RuntimeError("HDR 转 SDR 需要 FFmpeg 的 zscale 和 tonemap 滤镜；请安装包含它们的完整版。")
        filters.extend(["zscale=t=linear:npl=100", "format=gbrpf32le", "zscale=p=bt709",
                        "tonemap=tonemap=hable:desat=0", "zscale=t=bt709:m=bt709:r=tv"])
    filters.append("format=yuv420p")
    return ",".join(filters)


def validate_video(path: Path, source: dict) -> dict:
    result = video_info(path)
    stream = result["stream"]
    if len(result["streams"]) != 1 or stream.get("codec_name") != "h264" or stream.get("pix_fmt") != "yuv420p":
        raise ValueError("输出必须只有一条 H.264/yuv420p 视频轨。")
    if (result["width"], result["height"]) != dimensions(source) or result["fps"] > 12.01:
        raise ValueError("输出尺寸、方向或帧率不符合预期。")
    if abs(result["duration"] - source["duration"]) > 0.15:
        raise ValueError("压缩前后时长相差超过 0.15 秒，未发布输出。")
    if source["hdr"] and (result["hdr"] or stream.get("color_transfer") != "bt709"):
        raise ValueError("HDR 转 SDR 结果不符合预期。")
    run_media([binary("ffmpeg"), "-hide_banner", "-v", "error", "-xerror", "-i", str(path),
               "-map", "0:v:0", "-an", "-f", "null", "-"])
    return result


def compress_one(source: Path, output: Path, overwrite: bool = False) -> dict:
    row = {"source": str(source), "output": str(output), "status": "failed",
           "source_bytes": 0, "output_bytes": "", "remaining_percent": "",
           "source_duration_s": "", "output_duration_s": "", "error": ""}
    temp = None
    try:
        row["source_bytes"] = source.stat().st_size
        if output.exists() and not overwrite:
            row.update(status="skipped", output_bytes=output.stat().st_size)
            return row
        info = video_info(source)
        row["source_duration_s"] = round(info["duration"], 3)
        filters = video_filters(info)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".compress-", suffix=".mp4", dir=output.parent, delete=False) as handle:
            temp = Path(handle.name)
        args = [binary("ffmpeg"), "-hide_banner", "-v", "error", "-nostdin", "-y", "-i", str(source),
                "-map", f"0:{info['stream']['index']}", "-an", "-sn", "-dn", "-map_metadata", "-1",
                "-map_chapters", "-1", "-vf", filters, "-c:v", "libx264", "-preset", "fast",
                "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        if info["hdr"]:
            args.extend(["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"])
        args.append(str(temp))
        run_media(args)
        checked = validate_video(temp, info)
        size = temp.stat().st_size
        publish(temp, output, overwrite)
        row.update(status="success", output_bytes=size, remaining_percent=round(size / row["source_bytes"] * 100, 2),
                   output_duration_s=round(checked["duration"], 3))
    except (OSError, ValueError, RuntimeError) as exc:
        row["error"] = str(exc)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return row


def source_files(folder: Path, recursive: bool) -> list[Path]:
    paths = folder.rglob("*") if recursive else folder.glob("*")
    return sorted((p for p in paths if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
                   and "ai_upload" not in {part.lower() for part in p.relative_to(folder).parts[:-1]}),
                  key=lambda p: str(p.relative_to(folder)).casefold())


def compress_folder(folder: Path, recursive: bool = False, overwrite: bool = False) -> int:
    folder = folder.resolve()
    if not folder.is_dir():
        raise ValueError(f"输入必须是文件夹：{folder}")
    if folder.name.casefold() == "ai_upload":
        raise ValueError("请选择原片文件夹，而不是生成的 ai_upload 文件夹。")
    binary("ffmpeg")
    binary("ffprobe")
    sources = source_files(folder, recursive)
    if not sources:
        raise ValueError("文件夹中没有支持的视频。")
    rows = []
    output_root = folder / "ai_upload"
    for index, source in enumerate(sources, 1):
        relative = source.relative_to(folder)
        output = output_root / relative.parent / f"{relative.name}.ai.mp4"
        LOG.info("[%d/%d] %s", index, len(sources), relative)
        row = compress_one(source, output, overwrite)
        rows.append(row)
        if row["status"] == "success":
            LOG.info("成功 %.2f → %.2f MB（剩余 %.1f%%），%.3f 秒 → %.3f 秒",
                     row["source_bytes"] / 1e6, row["output_bytes"] / 1e6, row["remaining_percent"],
                     row["source_duration_s"], row["output_duration_s"])
        elif row["status"] == "skipped":
            LOG.info("跳过已有文件：%s", output)
        else:
            LOG.error("失败：%s", row["error"])
    output_root.mkdir(parents=True, exist_ok=True)
    report = output_root / "compression-report.csv"
    with report.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter(row["status"] for row in rows)
    LOG.info("完成：成功 %d，跳过 %d，失败 %d。汇总：%s", counts["success"], counts["skipped"], counts["failed"], report)
    return 1 if counts["failed"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="压缩视频供云端上传：720p / 最高 12fps / 无音轨")
    parser.add_argument("folder", nargs="?", type=Path, default=ROOT / "input")
    parser.add_argument("--recursive", action="store_true", help="包含子文件夹（排除 ai_upload）")
    parser.add_argument("--overwrite", action="store_true", help="重新生成并替换已有压缩文件")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        return compress_folder(args.folder, args.recursive, args.overwrite)
    except (OSError, ValueError, RuntimeError) as exc:
        LOG.error("失败：%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
