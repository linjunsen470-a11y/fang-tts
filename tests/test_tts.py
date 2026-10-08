import copy
import io
import re
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import httpx
import yaml

import cli
import fish_api
from config import DEFAULT_MODEL, ROOT, VOICE_REFERENCE_ID
from tag_catalog import DOCUMENTED_MARKERS, PLAYGROUND_ONLY_MARKERS
from breaths import (
    TARGET_SECONDS,
    adjust_breaths,
    align_sentence_ends,
    choose_cut,
    content_tokens,
    insert_breaths,
)
from scratch import ScratchDirectory


class TTSTests(unittest.TestCase):
    def setUp(self):
        self.temp = ScratchDirectory(prefix="fish-tts-test-")
        self.root = Path(self.temp.name)
        self.path = self.root / "中文 台词.yaml"
        self.data = {"text": "[calm] 欢迎参观。", "output": "output/voice.wav", "tts": {"format": "wav"}}

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        self.path.write_text(yaml.safe_dump(self.data, allow_unicode=True), encoding="utf-8-sig")

    def use_text_file(self, text, filename="台词 文本.txt", encoding="utf-8"):
        self.data.pop("text", None)
        self.data["text_file"] = filename
        source = self.path.parent / filename
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(text.encode(encoding))
        return source

    @staticmethod
    def wav_bytes():
        memory = io.BytesIO()
        with wave.open(memory, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\0\0" * 16000)
        return memory.getvalue()

    def test_check_is_offline_without_credentials_or_ffmpeg(self):
        self.save()
        with patch("cli.load_api_key") as key, patch("cli.fish_synthesize") as api, patch("cli.binary") as binary:
            cli.single_tts(self.path, check=True)
            key.assert_not_called()
            api.assert_not_called()
            binary.assert_not_called()
        self.assertFalse((self.root / "output").exists())

    def test_partial_prosody_preserves_defaults(self):
        self.data["tts"]["prosody"] = {"speed": 1.1}
        output, opts, text, breaths = cli.validate_config(self.data, self.path)
        self.assertFalse(breaths)
        self.assertEqual(opts["prosody"], {"speed": 1.1, "volume": 0.0, "normalize_loudness": True})
        self.assertEqual(output, self.root / "output/voice.wav")
        self.assertEqual(text, self.data["text"])

    def test_text_file_check_is_offline_and_resolves_beside_yaml(self):
        text = "[calm] 欢迎参观。\n这是下一句。"
        self.use_text_file(text, "台词 子目录/旁白.txt")
        self.save()
        with patch("cli.load_api_key") as key, patch("cli.fish_synthesize") as api, patch("cli.binary") as binary:
            self.assertEqual(cli.main([str(self.path), "--check"]), 0)
            key.assert_not_called()
            api.assert_not_called()
            binary.assert_not_called()
        self.assertFalse((self.root / "output").exists())
        self.assertEqual(cli.validate_config(self.data, self.path)[2], text)

    def test_absolute_text_file_path(self):
        source = self.use_text_file("[calm] 欢迎。")
        self.data["text_file"] = str(source.resolve())
        self.assertEqual(cli.validate_config(self.data, self.path)[2], "[calm] 欢迎。")

    def test_file_text_reaches_api_unchanged_and_is_reloaded_on_each_run(self):
        for encoding in ("utf-8", "utf-8-sig"):
            for ending in ("\n", "\r\n"):
                with self.subTest(encoding=encoding, ending=repr(ending)):
                    text = f"  [calm] 欢迎：这里有 # 符号。{ending}{ending}下一句。  {ending}"
                    source = self.use_text_file(text, encoding=encoding)
                    self.save()
                    original = source.read_bytes()
                    response = httpx.Response(200, content=self.wav_bytes(), request=httpx.Request("POST", fish_api.API_URL))
                    with patch("cli.load_api_key", return_value="test-only"), patch("cli.binary"), \
                            patch("fish_api.httpx.post", return_value=response) as post, \
                            patch("cli.audio_duration", return_value=1.0):
                        cli.single_tts(self.path, overwrite=True)
                    post.assert_called_once()
                    self.assertEqual(post.call_args.kwargs["json"]["text"], text)
                    self.assertNotIn("text_file", post.call_args.kwargs["json"])
                    self.assertEqual(source.read_bytes(), original)
                    self.assertEqual((self.root / self.data["output"]).read_bytes(), self.wav_bytes())

    def test_invalid_text_sources_fail_before_credentials_or_network(self):
        (self.root / "empty.txt").write_bytes(b"\xef\xbb\xbf \r\n\t")
        (self.root / "bad-encoding.txt").write_bytes(b"\xff\xfe")
        (self.root / "directory").mkdir()
        cases = [
            ({}, "必须且只能"),
            ({"text": "你好", "text_file": "missing.txt"}, "必须且只能"),
            ({"text": None, "text_file": "missing.txt"}, "必须且只能"),
            ({"text": "你好", "text_file": None}, "必须且只能"),
            ({"text": ""}, "非空文本"),
            ({"text_file": None}, "非空文件路径"),
            ({"text_file": "  "}, "非空文件路径"),
            ({"text_file": 123}, "非空文件路径"),
            ({"text_file": True}, "非空文件路径"),
            ({"text_file": []}, "非空文件路径"),
            ({"text_file": "bad\x00path.txt"}, "无法读取台词文件"),
            ({"text_file": "missing.txt"}, "无法读取台词文件"),
            ({"text_file": "directory"}, "无法读取台词文件"),
            ({"text_file": "empty.txt"}, "台词文件不能为空"),
            ({"text_file": "bad-encoding.txt"}, "UTF-8"),
        ]
        baseline = {key: value for key, value in self.data.items() if key != "text"}
        with patch("cli.load_api_key") as key, patch("cli.fish_synthesize") as api, patch("cli.binary") as binary:
            for fields, message in cases:
                for check in (False, True):
                    with self.subTest(fields=fields, check=check):
                        self.data = {**baseline, **fields}
                        self.save()
                        with self.assertRaisesRegex(ValueError, message):
                            cli.single_tts(self.path, check=check)
            key.assert_not_called()
            api.assert_not_called()
            binary.assert_not_called()

    def test_invalid_file_tags_and_unreadable_file_are_rejected_offline(self):
        with patch("cli.load_api_key") as key, patch("cli.fish_synthesize") as api:
            for text in ("[breathy] 欢迎", "(happy) 欢迎", "[calm 欢迎", "[calm]", "[[calm]] 欢迎",
                         "(pitch up) 测试", "[pitch down]", "[[pitch up]] 测试", "[pitch up 测试",
                         "[pitch high] 测试", "[Pitch up] 测试", "[pitch up +2] 测试"):
                with self.subTest(text=text):
                    self.use_text_file(text)
                    self.save()
                    with self.assertRaises(ValueError):
                        cli.single_tts(self.path)
            with patch("config.Path.read_bytes", side_effect=PermissionError("test permission denied")):
                with self.assertRaisesRegex(ValueError, "无法读取台词文件"):
                    cli.single_tts(self.path)
            key.assert_not_called()
            api.assert_not_called()

    def test_overwrite_cannot_replace_source_text(self):
        source = self.use_text_file("[calm] 欢迎。", "source.wav")
        self.data["output"] = "./source.wav"
        self.save()
        with patch("cli.load_api_key") as key, patch("cli.fish_synthesize") as api:
            with self.assertRaisesRegex(ValueError, "不能指向"):
                cli.single_tts(self.path, overwrite=True)
            key.assert_not_called()
            api.assert_not_called()
        self.assertEqual(source.read_text(encoding="utf-8"), "[calm] 欢迎。")

    def test_invalid_inputs_never_call_api(self):
        invalid = [
            {"text": "[breathy] 欢迎"}, {"text": "(happy) 欢迎"},
            {"text": "[calm 欢迎"}, {"text": "[calm]"}, {"text": "[[calm]] 欢迎"},
            {"approved": True}, {"model": "s2.1-pro"}, {"reference_id": ""},
            {"reference_id": ["voice-a", "voice-b"]}, {"reference_id": "voice\nname"},
            {"reference_id": None},
            {"output": "output/voice.mp3"}, {"tts": {"temperature": "0.7"}},
            {"tts": {"top_p": True}}, {"tts": {"chunk_length": 100.5}},
            {"tts": {"normalize": "true"}}, {"tts": {"sample_rate": 48000}},
            {"tts": {"format": []}}, {"tts": {"prosody": None}},
            {"tts": {"temperature": float("nan")}}, {"tts": {"tag_compatible_mode": True}},
            {"tts": {"prosody": {"speed": 2.1}}}, {"tts": {"max_new_tokens": 0}},
            {"text": "(pitch down) 测试"}, {"text": "[pitch high] 测试"},
            {"pitch": 2}, {"tts": {"pitch": 2}}, {"tts": {"prosody": {"pitch": 2}}},
        ]
        baseline = copy.deepcopy(self.data)
        with patch("cli.fish_synthesize") as api, patch("cli.load_api_key") as key:
            for invalid_item in invalid:
                with self.subTest(invalid=invalid_item):
                    self.data = {**copy.deepcopy(baseline), **invalid_item}
                    self.save()
                    with self.assertRaises(ValueError):
                        cli.single_tts(self.path)
            api.assert_not_called()
            key.assert_not_called()

    def test_existing_output_rejected_before_network(self):
        self.save()
        output = self.root / self.data["output"]
        output.parent.mkdir()
        output.write_bytes(b"old audio")
        with patch("cli.fish_synthesize") as api:
            with self.assertRaisesRegex(ValueError, "已存在"):
                cli.single_tts(self.path)
            api.assert_not_called()
        self.assertEqual(output.read_bytes(), b"old audio")

    def test_api_failure_keeps_existing_output(self):
        self.save()
        output = self.root / self.data["output"]
        output.parent.mkdir()
        output.write_bytes(b"old audio")
        with patch("cli.load_api_key", return_value="test-only"), patch("cli.binary"), \
                patch("cli.fish_synthesize", side_effect=httpx.ConnectError("offline")):
            with self.assertRaises(httpx.ConnectError):
                cli.single_tts(self.path, overwrite=True)
        self.assertEqual(output.read_bytes(), b"old audio")

    def test_validation_failure_keeps_existing_output_and_removes_temp(self):
        self.save()
        output = self.root / self.data["output"]
        output.parent.mkdir()
        output.write_bytes(b"old audio")
        with patch("cli.load_api_key", return_value="test-only"), patch("cli.binary"), \
                patch("cli.fish_synthesize", return_value=b"bad audio"), \
                patch("cli.audio_duration", side_effect=ValueError("invalid audio")):
            with self.assertRaises(ValueError):
                cli.single_tts(self.path, overwrite=True)
        self.assertEqual(output.read_bytes(), b"old audio")
        self.assertEqual(list(output.parent.glob(".tts-*")), [])

    def test_whole_text_sent_unchanged_and_duration_reported(self):
        self.save()
        with patch("cli.load_api_key", return_value="test-only"), patch("cli.binary"), \
                patch("cli.fish_synthesize", return_value=self.wav_bytes()) as api, \
                patch("cli.audio_duration", return_value=1.0), self.assertLogs("fish-tts", "INFO") as logs:
            cli.single_tts(self.path)
        self.assertEqual(api.call_args.args[0], self.data["text"])
        self.assertEqual(api.call_args.args[2:4], (DEFAULT_MODEL, VOICE_REFERENCE_ID))
        self.assertIn("1.00 秒", " ".join(logs.output))
        self.assertEqual((self.root / self.data["output"]).read_bytes(), self.wav_bytes())

    def test_request_headers_and_json_and_no_model_in_body(self):
        response = httpx.Response(200, content=b"audio", request=httpx.Request("POST", fish_api.API_URL))
        with patch("fish_api.httpx.post", return_value=response) as post:
            self.assertEqual(fish_api.synthesize("[calm] 你好", "test-only", DEFAULT_MODEL, VOICE_REFERENCE_ID,
                             {"format": "mp3", "prosody": {"speed": 1.0}}), b"audio")
        args = post.call_args.kwargs
        self.assertEqual(args["headers"]["model"], DEFAULT_MODEL)
        self.assertEqual(args["headers"]["Authorization"], "Bearer test-only")
        self.assertEqual(args["json"]["reference_id"], VOICE_REFERENCE_ID)
        self.assertNotIn("model", args["json"])

    def test_pitch_and_pacing_tags_pass_offline_check_in_both_text_sources(self):
        text = "[pitch up] 测试一。[pitch down] 测试二。[speaking slowly] 测试三。[long pause] 测试四。"
        with patch("cli.load_api_key") as key, patch("fish_api.httpx.post") as post, patch("cli.binary") as binary:
            for source in ("text", "text_file"):
                with self.subTest(source=source):
                    if source == "text":
                        self.data["text"] = text
                    else:
                        self.use_text_file(text)
                    self.save()
                    self.assertEqual(cli.main([str(self.path), "--check"]), 0)
            key.assert_not_called()
            post.assert_not_called()
            binary.assert_not_called()
        self.assertFalse((self.root / "output").exists())

    def test_pitch_and_related_tags_reach_free_model_unchanged(self):
        text = "  [pitch up] 测试一。\r\n[pitch down] 测试二。[speaking fast] 测试三。  \r\n"
        for source in ("text", "text_file"):
            with self.subTest(source=source):
                if source == "text":
                    self.data["text"] = text
                else:
                    self.use_text_file(text, encoding="utf-8-sig")
                self.save()
                response = httpx.Response(200, content=self.wav_bytes(), request=httpx.Request("POST", fish_api.API_URL))
                with patch("cli.load_api_key", return_value="test-only"), patch("cli.binary"), \
                        patch("fish_api.httpx.post", return_value=response) as post, \
                        patch("cli.audio_duration", return_value=1.0):
                    cli.single_tts(self.path, overwrite=True)
                post.assert_called_once()
                self.assertEqual(post.call_args.kwargs["headers"]["model"], "s2.1-pro-free")
                body = post.call_args.kwargs["json"]
                self.assertEqual(body["text"], text)
                self.assertEqual(body["reference_id"], VOICE_REFERENCE_ID)
                self.assertNotIn("pitch", body)
                self.assertNotIn("pitch", body["prosody"])

    def test_pause_tags_stay_in_one_request(self):
        text = "[calm]上一句。[long pause]下一句。"
        self.data["text"] = text
        self.save()
        response = httpx.Response(200, content=self.wav_bytes(), request=httpx.Request("POST", fish_api.API_URL))
        with patch("cli.load_api_key", return_value="test-only"), patch("cli.binary"), \
                patch("fish_api.httpx.post", return_value=response) as post, \
                patch("cli.audio_duration", return_value=1.0):
            cli.single_tts(self.path, overwrite=True)
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["json"]["text"], text)

    def test_breaths_insert_on_one_take_and_are_not_sent_to_api(self):
        import array
        self.assertEqual(
            [char for char, is_end in content_tokens("[excited]甲。乙，丙！") if is_end],
            ["甲", "丙"],
        )
        loud = array.array("f", [0.5] * 16000)
        self.assertIsNone(choose_cut(loud, 16000, 0.5))
        self.data["text"] = "[calm]上一句。下一句。"
        self.data["output"] = "output/breath.wav"
        self.data["tts"] = {"format": "wav", "sample_rate": 16000, "breaths": True}
        self.save()
        with patch("cli.load_api_key", return_value="test-only"), \
                patch("cli.fish_synthesize", return_value=self.wav_bytes()) as api, \
                patch("breaths.align_sentence_ends", return_value=[0.45]):
            cli.single_tts(self.path)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(api.call_args.args[0], self.data["text"])
        self.assertNotIn("breaths", api.call_args.args[4])
        duration = cli.audio_duration(self.root / "output/breath.wav", "wav", 16000)
        self.assertGreater(duration, TARGET_SECONDS - 0.08)
        self.assertLess(duration, TARGET_SECONDS + 0.08)
        self.assertEqual(len(insert_breaths(array.array("f", [0.0] * 1600), 1600, [])), 1600)
        rate = 16000
        loud_n = int(0.3 * rate)
        loud = array.array("f", [0.4] * loud_n)
        long_gap = loud + array.array("f", [0.0] * rate) + loud
        shortened = adjust_breaths(long_gap, rate, [loud_n + rate // 2])
        self.assertLess(len(shortened), len(long_gap) - int(0.2 * rate))
        self.assertGreater(len(shortened), loud_n * 2 + int((TARGET_SECONDS - 0.1) * rate))
        short_gap = loud + array.array("f", [0.0] * int(0.05 * rate)) + loud
        lengthened = adjust_breaths(short_gap, rate, [loud_n + int(0.02 * rate)])
        self.assertGreater(len(lengthened), len(short_gap) + int(0.1 * rate))
        self.assertLess(len(lengthened), len(short_gap) + int((TARGET_SECONDS + 0.05) * rate))
        heard = list("贵2000这站")
        with patch("breaths._transcribe", return_value=(
            heard,
            [0.0, 0.3, 0.4, 0.5, 0.6, 1.1, 1.6],
            [0.2, 0.4, 0.5, 0.6, 0.7, 1.4, 1.8],
        )):
            times = align_sentence_ends(self.path, "贵两千。这站。")
        self.assertEqual(len(times), 2)
        self.assertAlmostEqual(times[0], 0.98)
        self.assertAlmostEqual(times[1], 1.8)

    def test_all_documented_tags_are_valid_and_parenthesized_forms_fail_offline(self):
        with patch("cli.load_api_key") as key, patch("fish_api.httpx.post") as post:
            for marker in sorted(DOCUMENTED_MARKERS):
                with self.subTest(marker=marker):
                    self.data["text"] = f"[{marker}] 测试。"
                    self.assertEqual(cli.validate_config(self.data, self.path)[2], self.data["text"])
                    self.data["text"] = f"({marker}) 测试。"
                    self.save()
                    with self.assertRaisesRegex(ValueError, "圆括号标签"):
                        cli.single_tts(self.path)
            key.assert_not_called()
            post.assert_not_called()

    def test_yaml_voice_override_reaches_request_unchanged(self):
        self.data["reference_id"] = "user-selected-voice"
        self.data["tts"]["prosody"] = {"speed": 0.9, "volume": 2, "normalize_loudness": False}
        self.data["tts"].update(temperature=0.6, top_p=0.8)
        self.save()
        response = httpx.Response(200, content=self.wav_bytes(), request=httpx.Request("POST", fish_api.API_URL))
        with patch("cli.load_api_key", return_value="test-only"), patch("cli.binary"), \
                patch("fish_api.httpx.post", return_value=response) as post, patch("cli.audio_duration", return_value=1.0):
            cli.single_tts(self.path)
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["reference_id"], "user-selected-voice")
        self.assertEqual(body["prosody"], self.data["tts"]["prosody"])
        self.assertEqual(body["temperature"], 0.6)
        self.assertEqual(body["top_p"], 0.8)
        self.assertEqual(post.call_args.kwargs["headers"]["model"], DEFAULT_MODEL)

    def test_empty_response_is_rejected(self):
        response = httpx.Response(200, content=b"", request=httpx.Request("POST", fish_api.API_URL))
        with patch("fish_api.httpx.post", return_value=response):
            with self.assertRaises(RuntimeError):
                fish_api.synthesize("你好", "test-only", DEFAULT_MODEL, VOICE_REFERENCE_ID, {})

    def test_all_document_yaml_examples_are_valid(self):
        count = 0
        documents = [ROOT / "README.md", *sorted((ROOT / "chatgpt_project").glob("*.md"))]
        for path in documents:
            script = None
            for language, block in re.findall(r"```(yaml|text)\s*\n(.*?)```", path.read_text(encoding="utf-8"), re.S):
                if language == "text":
                    script = block
                    continue
                with self.subTest(document=path.name):
                    data = yaml.safe_load(block)
                    example = self.root / f"example-{count}" / "tts.yaml"
                    example.parent.mkdir()
                    if "text_file" in data:
                        self.assertIsNotNone(script, "外部台词示例必须提供对应的 text 代码块")
                        source = example.parent / data["text_file"]
                        self.assertTrue(source.resolve().is_relative_to(self.root))
                        source.parent.mkdir(parents=True, exist_ok=True)
                        source.write_bytes(script.encode("utf-8"))
                    _, _, text, _breaths = cli.validate_config(data, example)
                    self.assertEqual(text, script if "text_file" in data else data["text"])
                    script = None
                    count += 1
        self.assertGreaterEqual(count, 3)
        # Repository tts.yaml / tts.txt contain the user's current script.
        # Validate only documentation examples and temporary test fixtures.

    def test_documented_tag_table_matches_code(self):
        doc = (ROOT / "chatgpt_project/02_fish_tags.md").read_text(encoding="utf-8")
        table_tags = set(re.findall(r"^\| `\[([^\]]+)\]` \|", doc, re.M))
        self.assertEqual(table_tags, DOCUMENTED_MARKERS)
        self.assertEqual(len(table_tags), 98)
        self.assertFalse(DOCUMENTED_MARKERS & PLAYGROUND_ONLY_MARKERS)


if __name__ == "__main__":
    unittest.main()
