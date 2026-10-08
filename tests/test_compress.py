import csv
import hashlib
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from compress_videos import compress_folder, compress_one, dimensions, source_files, video_filters
from media_utils import audio_duration, binary, run_media, video_info
from scratch import ScratchDirectory


class CompressionUnitTests(unittest.TestCase):
    def test_dimensions_are_orientation_aware_and_never_upscale(self):
        for width, height, expected in [(1920, 1080, (1280, 720)), (1080, 1920, (720, 1280)),
                                        (320, 180, (320, 180)), (1000, 1000, (720, 720)),
                                        (319, 179, (318, 178))]:
            with self.subTest(width=width, height=height):
                self.assertEqual(dimensions({"width": width, "height": height}), expected)

    def test_missing_ffmpeg_is_actionable(self):
        with patch("media_utils.shutil.which", return_value=None), patch("media_utils.Path.is_file", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "PATH"):
                binary("ffmpeg")

    def test_missing_hdr_filters_fails_explicitly(self):
        with patch("compress_videos.binary", return_value="ffmpeg"), patch("compress_videos.run_media", return_value="scale"):
            with self.assertRaisesRegex(RuntimeError, "HDR"):
                video_filters({"width": 1280, "height": 720, "fps": 30, "hdr": True})

    def test_scan_excludes_outputs_and_supports_recursion(self):
        with ScratchDirectory(prefix="fish-scan-test-") as temp:
            root = Path(temp)
            for relative in ["top.MP4", "sub/clip.mov", "ai_upload/generated.mp4", "sub/ai_upload/generated.mp4", "note.txt"]:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            self.assertEqual([p.name for p in source_files(root, False)], ["top.MP4"])
            self.assertEqual({p.name for p in source_files(root, True)}, {"top.MP4", "clip.mov"})


class CompressionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.ffmpeg = binary("ffmpeg")
            binary("ffprobe")
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        cls.temp = ScratchDirectory(prefix="fish-compress-test-")
        cls.root = Path(cls.temp.name)
        cls.base = cls.root / "base.mp4"
        run_media([cls.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24",
                   "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "1.5",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(cls.base)])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_batch_with_chinese_spaces_collisions_skips_and_bad_input(self):
        folder = self.root / "中文 路径 & 空格"
        folder.mkdir()
        for name in ["同名.mp4", "同名.mov"]:
            shutil.copyfile(self.base, folder / name)
        (folder / "bad.mp4").write_bytes(b"not a video")
        before = hashlib.sha256((folder / "同名.mp4").read_bytes()).hexdigest()
        self.assertEqual(compress_folder(folder), 1)
        output_dir = folder / "ai_upload"
        outputs = list(output_dir.glob("*.mp4"))
        self.assertEqual(len(outputs), 2)
        for output in outputs:
            info = video_info(output)
            self.assertEqual((info["width"], info["height"]), (320, 180))
            self.assertEqual(info["fps"], 12)
            self.assertEqual(len(info["streams"]), 1)
            raw = output.read_bytes()
            self.assertLess(raw.index(b"moov"), raw.index(b"mdat"))
        self.assertEqual(before, hashlib.sha256((folder / "同名.mp4").read_bytes()).hexdigest())
        stamps = {p: p.stat().st_mtime_ns for p in outputs}
        self.assertEqual(compress_folder(folder), 1)
        self.assertEqual(stamps, {p: p.stat().st_mtime_ns for p in outputs})
        with (output_dir / "compression-report.csv").open(encoding="utf-8-sig", newline="") as handle:
            self.assertEqual(sorted(r["status"] for r in csv.DictReader(handle)), ["failed", "skipped", "skipped"])
        self.assertEqual(list(output_dir.glob(".compress-*")), [])

    def test_failed_overwrite_does_not_replace_previous_file(self):
        source = self.root / "broken.mp4"
        output = self.root / "previous.mp4"
        source.write_bytes(b"broken")
        output.write_bytes(b"keep this")
        result = compress_one(source, output, overwrite=True)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(output.read_bytes(), b"keep this")

    def test_rotation_is_baked_into_portrait_pixels(self):
        source = self.root / "rotated.mov"
        run_media([self.ffmpeg, "-v", "error", "-y", "-display_rotation", "90", "-i", str(self.base),
                   "-c", "copy", str(source)])
        self.assertEqual((video_info(source)["width"], video_info(source)["height"]), (180, 320))
        output = self.root / "portrait.mp4"
        result = compress_one(source, output)
        self.assertEqual(result["status"], "success", result)
        info = video_info(output)
        self.assertEqual((info["width"], info["height"]), (180, 320))
        self.assertEqual((info["stream"]["width"], info["stream"]["height"]), (180, 320))

    def test_low_fps_is_not_increased(self):
        source = self.root / "slow.mp4"
        run_media([self.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                   "testsrc2=size=160x120:rate=6", "-t", "1.5", "-c:v", "libx264", str(source)])
        output = self.root / "slow-output.mp4"
        result = compress_one(source, output)
        self.assertEqual(result["status"], "success", result)
        self.assertEqual(video_info(output)["fps"], 6)

    def test_hdr_to_sdr(self):
        available = run_media([self.ffmpeg, "-hide_banner", "-filters"])
        if "zscale" not in available or "tonemap" not in available:
            self.skipTest("FFmpeg lacks HDR conversion filters")
        source = self.root / "hdr.mp4"
        run_media([self.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                   "testsrc2=size=320x180:rate=24", "-t", "1", "-vf",
                   "setparams=color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc", "-c:v", "libx264",
                   "-pix_fmt", "yuv420p10le", "-color_primaries", "bt2020",
                   "-color_trc", "smpte2084", "-colorspace", "bt2020nc", str(source)])
        output = self.root / "sdr.mp4"
        self.assertTrue(video_info(source)["hdr"])
        result = compress_one(source, output)
        self.assertEqual(result["status"], "success", result)
        self.assertEqual(video_info(output)["stream"]["color_transfer"], "bt709")

    def test_audio_duration_reads_real_generated_audio(self):
        output = self.root / "tone.wav"
        run_media([self.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                   "sine=frequency=440:sample_rate=16000", "-t", "1", str(output)])
        self.assertAlmostEqual(audio_duration(output, "wav", 16000), 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
