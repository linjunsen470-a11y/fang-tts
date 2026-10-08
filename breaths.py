"""Fit sentence-end breaths in one continuous take.

Pause tags are not used. Sentence ends are aligned to the single synthesis.
Each quiet run at a finished sentence is brought to about TARGET_SECONDS:
longer runs are shortened from the center, short runs are topped up with this
file's own noise floor. A cut that still sits on speech is skipped.
"""
from __future__ import annotations

import array
import math
import re
import subprocess
import tempfile
import wave
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

from media_utils import binary, run_media

TARGET_SECONDS = 0.50
GAP_SECONDS = TARGET_SECONDS
FADE_SECONDS = 0.02
SNAP_SECONDS = 0.12
LOOK_SECONDS = 1.2
FRAME_SECONDS = 0.02
HOP_SECONDS = 0.01
SPEECH_PERCENTILE = 75
SPEECH_RATIO = 0.22
MIN_SPACING_SECONDS = 0.5

_TAGS = re.compile(r"\[[^\[\]]+\]")
_ENDS = set("。！？!?")
_MODEL = None


def content_tokens(text: str) -> list[tuple[str, bool]]:
    """Tag-free characters, with True on the character that ends a sentence."""
    tokens: list[tuple[str, bool]] = []
    for char in _TAGS.sub("", text):
        if char in _ENDS:
            if tokens:
                tokens[-1] = (tokens[-1][0], True)
            continue
        if "\u4e00" <= char <= "\u9fff" or char.isalnum():
            tokens.append((char, False))
    return tokens


def choose_cut(samples: array.array, rate: int, time: float) -> int | None:
    """Snap to the quietest point within SNAP_SECONDS. Skip if that point is still speech."""
    frame = max(1, int(FRAME_SECONDS * rate))
    hop = max(1, int(HOP_SECONDS * rate))
    if len(samples) <= frame:
        return None
    levels = _levels(samples, frame, hop)
    speech = _percentile(levels, SPEECH_PERCENTILE)
    threshold = speech * SPEECH_RATIO
    target = int(round(time * rate))
    window = int(SNAP_SECONDS * rate)
    start = max(0, target - window)
    stop = min(len(samples) - frame, target + window)
    best_at: int | None = None
    best_level = math.inf
    best_distance = math.inf
    for pos in range(start, stop + 1, hop):
        level = _rms(samples, pos, frame)
        distance = abs((pos + frame // 2) - target)
        if level < best_level - 1e-7 or (abs(level - best_level) <= 1e-7 and distance < best_distance):
            best_level = level
            best_distance = distance
            best_at = pos + frame // 2
    if best_at is None or best_level > threshold:
        return None
    fade = max(1, int(FADE_SECONDS * rate))
    if best_at < fade or best_at > len(samples) - fade:
        return None
    return best_at


def insert_breaths(samples: array.array, rate: int, cuts: list[int], gap: float = GAP_SECONDS) -> array.array:
    """Crossfade a piece of this file's noise floor in at each cut. Cuts are sample indexes."""
    fade = max(1, int(FADE_SECONDS * rate))
    gap_n = int(round(gap * rate))
    noise = _noise(samples, rate, gap_n + 2 * fade)
    for cut in sorted(cuts, reverse=True):
        if cut < fade or cut > len(samples) - fade:
            continue
        samples = _join(samples[:cut], noise, samples[cut:], fade)
    return samples


def adjust_breaths(samples: array.array, rate: int, cuts: list[int], target: float = TARGET_SECONDS) -> array.array:
    """Make each quiet run around a cut about `target` seconds. Longer runs are shortened."""
    target_n = int(round(target * rate))
    edits: list[tuple[int, int, int]] = []
    for cut in cuts:
        span = _quiet_span(samples, rate, cut)
        if span is None:
            continue
        start, end = span
        delta = target_n - (end - start)
        if abs(delta) < int(0.03 * rate):
            continue
        edits.append((start, end, delta))
    if not edits:
        return samples
    for start, end, delta in sorted(edits, reverse=True):
        samples = _apply_breath_delta(samples, rate, start, end, delta)
    return samples


def align_sentence_ends(wav_path: Path, text: str) -> list[float]:
    """Return end times, in seconds, for sentence-ending characters found in the audio."""
    reference = content_tokens(text)
    if not any(is_end for _, is_end in reference):
        return []
    heard, heard_starts, heard_ends = _transcribe(wav_path)
    if not heard:
        return []
    matched_start: dict[int, float] = {}
    matched_end: dict[int, float] = {}
    matcher = SequenceMatcher(a=[char for char, _ in reference], b=heard, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            continue
        for offset, ref_index in enumerate(range(i1, i2)):
            heard_index = j1 + offset
            matched_start[ref_index] = heard_starts[heard_index]
            matched_end[ref_index] = heard_ends[heard_index]
    times: list[float] = []
    for ref_index, (_, is_end) in enumerate(reference):
        if not is_end:
            continue
        if ref_index in matched_end:
            times.append(matched_end[ref_index])
            continue
        # Whisper writes 两千 as 2000, so the character before the period never matches.
        # Use the quiet just before the next matched character when it starts the following sentence.
        following = [index for index in matched_start if index > ref_index]
        if not following:
            continue
        nxt = min(following)
        if nxt - ref_index > 3:
            continue
        cut_at = matched_start[nxt]
        previous = [index for index in matched_end if index < ref_index]
        if previous:
            prev = max(previous)
            if ref_index - prev <= 6:
                cut_at = max(matched_end[prev], matched_start[nxt] - 0.12)
        times.append(cut_at)
    return times


def apply_breaths(path: Path, text: str, bitrate: int | None = None) -> tuple[int, int]:
    """Rewrite one audio file in place. Returns (inserted, skipped)."""
    wav_path, encoded = _as_wav(path)
    try:
        samples, rate = _read_wav(wav_path)
        times = align_sentence_ends(wav_path, text)
        cuts: list[int] = []
        skipped = 0
        for time in times:
            cut = choose_cut(samples, rate, time)
            if cut is None or any(abs(cut - chosen) < int(MIN_SPACING_SECONDS * rate) for chosen in cuts):
                skipped += 1
                continue
            cuts.append(cut)
        if cuts:
            _write_wav(wav_path, adjust_breaths(samples, rate, cuts), rate)
            if encoded:
                _encode(wav_path, path, bitrate)
        return len(cuts), skipped
    finally:
        if encoded:
            wav_path.unlink(missing_ok=True)


def _transcribe(wav_path: Path) -> tuple[list[str], list[float], list[float]]:
    chars: list[str] = []
    starts: list[float] = []
    ends: list[float] = []
    # Pass samples directly. faster-whisper 1.2 decodes files with an av option this environment does not have.
    segments, _info = _whisper().transcribe(
        _pcm16k(wav_path),
        language="zh",
        word_timestamps=True,
        vad_filter=False,
        beam_size=5,
        condition_on_previous_text=False,
    )
    for segment in segments:
        for word in segment.words or []:
            content = [char for char in word.word if "\u4e00" <= char <= "\u9fff" or char.isalnum()]
            if not content:
                continue
            span = max(float(word.end) - float(word.start), 0.01)
            count = len(content)
            for index, char in enumerate(content):
                chars.append(char)
                starts.append(float(word.start) + span * index / count)
                ends.append(float(word.start) + span * (index + 1) / count)
    return chars, starts, ends


def _pcm16k(wav_path: Path) -> np.ndarray:
    result = subprocess.run(
        [binary("ffmpeg"), "-hide_banner", "-v", "error", "-i", str(wav_path),
         "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True, check=False,
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()[-800:]
        raise RuntimeError(f"无法读取音频用于对齐：{message}")
    audio = np.frombuffer(result.stdout, dtype=np.float32)
    if audio.size == 0:
        raise RuntimeError("对齐音频为空。")
    return np.ascontiguousarray(audio)


def _whisper():
    global _MODEL
    if _MODEL is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("缺少 faster-whisper，无法对齐句末。请安装 requirements.txt。") from exc
        _MODEL = WhisperModel("small", device="cpu", compute_type="int8")
    return _MODEL


def _as_wav(path: Path) -> tuple[Path, bool]:
    if path.suffix.lower() == ".wav":
        return path, False
    if path.suffix.lower() != ".mp3":
        raise ValueError("句末气口目前只支持 mp3 和 wav。")
    handle = tempfile.NamedTemporaryFile(prefix=".breath-", suffix=".wav", dir=path.parent, delete=False)
    handle.close()
    wav_path = Path(handle.name)
    run_media([binary("ffmpeg"), "-hide_banner", "-v", "error", "-y", "-i", str(path),
               "-ac", "1", "-c:a", "pcm_s16le", str(wav_path)])
    return wav_path, True


def _encode(wav_path: Path, path: Path, bitrate: int | None) -> None:
    run_media([binary("ffmpeg"), "-hide_banner", "-v", "error", "-y", "-i", str(wav_path),
               "-c:a", "libmp3lame", "-b:a", f"{bitrate or 128}k", str(path)])


def _read_wav(path: Path) -> tuple[array.array, int]:
    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise ValueError("句末气口需要单声道 16-bit 音频。")
        rate = handle.getframerate()
        frames = array.array("h")
        frames.frombytes(handle.readframes(handle.getnframes()))
    return array.array("f", (sample / 32768 for sample in frames)), rate


def _write_wav(path: Path, samples: array.array, rate: int) -> None:
    clipped = array.array("h", (max(-32767, min(32767, int(round(sample * 32767)))) for sample in samples))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(clipped.tobytes())


def _levels(samples: array.array, frame: int, hop: int) -> list[float]:
    return [_rms(samples, pos, frame) for pos in range(0, len(samples) - frame + 1, hop)]


def _rms(samples: array.array, start: int, frame: int) -> float:
    total = 0.0
    for sample in samples[start:start + frame]:
        total += sample * sample
    return math.sqrt(total / frame)


def _percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(percent / 100 * len(ordered)) - 1))
    return ordered[index]


def _quiet_span(samples: array.array, rate: int, cut: int) -> tuple[int, int] | None:
    """Low-energy run containing cut, limited to LOOK_SECONDS on either side."""
    frame = max(1, int(FRAME_SECONDS * rate))
    hop = max(1, int(HOP_SECONDS * rate))
    if len(samples) <= frame:
        return None
    threshold = _percentile(_levels(samples, frame, hop), SPEECH_PERCENTILE) * SPEECH_RATIO
    if not _is_quiet(samples, cut, frame, threshold):
        return None
    reach = int(LOOK_SECONDS * rate)
    left = cut
    pos = cut
    while pos - hop >= max(0, cut - reach):
        if not _is_quiet(samples, pos - hop, frame, threshold):
            break
        pos -= hop
        left = pos
    right = min(len(samples), cut + frame)
    pos = cut
    while pos + hop <= min(len(samples) - frame, cut + reach):
        if not _is_quiet(samples, pos + hop, frame, threshold):
            break
        pos += hop
        right = min(len(samples), pos + frame)
    if right <= left:
        return None
    return left, right


def _is_quiet(samples: array.array, pos: int, frame: int, threshold: float) -> bool:
    pos = min(max(0, pos), len(samples) - frame)
    return _rms(samples, pos, frame) <= threshold


def _apply_breath_delta(samples: array.array, rate: int, start: int, end: int, delta: int) -> array.array:
    """Insert or remove samples inside the quiet span, keeping its edges."""
    fade = max(1, int(FADE_SECONDS * rate))
    if delta > 0:
        at = (start + end) // 2
        if at < fade or at > len(samples) - fade:
            return samples
        noise = _noise(samples, rate, delta + 2 * fade)
        return _join(samples[:at], noise, samples[at:], fade)
    remove = min(-delta, max(0, end - start - 2 * fade))
    if remove <= fade:
        return samples
    keep = (end - start) - remove
    left_end = start + keep // 2
    right_start = end - (keep - keep // 2)
    if left_end < fade or right_start + fade > len(samples) or right_start <= left_end:
        return samples[:left_end] + samples[right_start:]
    kept_left = samples[:left_end]
    kept_right = samples[right_start:]
    mixed = array.array("f", [0.0]) * fade
    _mix(mixed, 0, samples[left_end:left_end + fade], samples[right_start:right_start + fade], fade)
    out = array.array("f")
    out.extend(kept_left)
    out.extend(mixed)
    out.extend(kept_right[fade:])
    return out


def _noise(samples: array.array, rate: int, length: int) -> array.array:
    frame = max(1, int(0.05 * rate))
    hop = max(1, int(HOP_SECONDS * rate))
    if len(samples) <= frame:
        return array.array("f", [0.0]) * length
    best = 0
    best_level = math.inf
    for pos in range(0, len(samples) - frame + 1, hop):
        level = _rms(samples, pos, frame)
        if level < best_level:
            best_level = level
            best = pos
    floor = array.array("f", samples[best:best + frame])
    speech = _percentile(_levels(samples, max(1, int(FRAME_SECONDS * rate)), hop), SPEECH_PERCENTILE)
    if best_level > speech * SPEECH_RATIO:
        floor = array.array("f", (sample * 0.05 for sample in floor))
    tiled = array.array("f")
    while len(tiled) < length:
        tiled.extend(floor)
    return tiled[:length]


def _join(left: array.array, noise: array.array, right: array.array, fade: int) -> array.array:
    total = len(left) + len(noise) + len(right) - 2 * fade
    out = array.array("f", [0.0]) * total
    out[:len(left) - fade] = left[:-fade]
    _mix(out, len(left) - fade, left[-fade:], noise[:fade], fade)
    body_from = len(left)
    body_to = body_from + len(noise) - 2 * fade
    out[body_from:body_to] = noise[fade:len(noise) - fade]
    _mix(out, body_to, noise[-fade:], right[:fade], fade)
    out[body_to + fade:] = right[fade:]
    return out


def _mix(out: array.array, at: int, first: array.array, second: array.array, fade: int) -> None:
    for index in range(fade):
        weight = 1 - (index + 1) / (fade + 1)
        out[at + index] = first[index] * weight + second[index] * (1 - weight)
