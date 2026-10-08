"""Project allowlist of officially documented Fish Audio S2/S2.1 cues.

S2 accepts free-form cues; this project deliberately checks a curated allowlist.
Sources and usage notes: chatgpt_project/02_fish_tags.md (checked 2026-09-27).
"""

from __future__ import annotations

EMOTIONS = {
    "happy", "sad", "angry", "excited", "calm", "nervous", "confident",
    "surprised", "satisfied", "delighted", "scared", "worried", "upset",
    "frustrated", "depressed", "empathetic", "embarrassed", "disgusted",
    "moved", "proud", "relaxed", "grateful", "curious", "sarcastic",
    "disdainful", "unhappy", "anxious", "hysterical", "indifferent",
    "uncertain", "doubtful", "confused", "disappointed", "regretful",
    "guilty", "ashamed", "jealous", "envious", "hopeful", "optimistic",
    "pessimistic", "nostalgic", "lonely", "bored", "contemptuous",
    "sympathetic", "compassionate", "determined", "resigned",
}

TONE_MARKERS = {
    "in a hurry tone", "shouting", "screaming", "whispering", "soft tone",
    "emphasis",
}

AUDIO_EFFECTS = {
    "laughing", "chuckling", "sobbing", "crying loudly", "sighing",
    "groaning", "panting", "gasping", "yawning", "snoring", "clear throat",
}

SPECIAL_EFFECTS = {
    "audience laughing", "background laughter", "crowd laughing", "break",
    "long-break",
}

# Additional cues explicitly listed in Fish Audio's S2 inline-control guide.
# The English and Chinese editions have different example tables; include both.
# https://fish.audio/blog/fish-audio-s2-fine-grained-ai-voice-control-at-the-word-level/
# https://fish.audio/zh-CN/blog/fish-audio-s2-fine-grained-ai-voice-control-at-the-word-level/
S2_INLINE_MARKERS = {
    # Pitch and delivery (qualitative cues, not numeric API parameters).
    "pitch up", "pitch down", "singing", "mumbling", "monotone",
    "soft voice", "loud voice", "low voice",
    # Local pace and pauses (no guaranteed duration).
    "speaking fast", "speaking slowly", "slight pause", "short pause",
    "pause", "long pause",
    # Breath and vocal sounds; keep documented spellings without alias rewriting.
    "breathing", "sigh", "sniffing", "clears throat", "laughter", "cough",
    "crying", "inhale", "exhale", "gasp", "giggle", "groan",
    "rustling sound",
}

DOCUMENTED_MARKERS = EMOTIONS | TONE_MARKERS | AUDIO_EFFECTS | SPECIAL_EFFECTS | S2_INLINE_MARKERS

# Previously seen in the Playground, but not in the reviewed reference tables.
# This exclusion is a project policy, not a claim that S2 cannot interpret them.
# "pause" and "long pause" are now documented above and must not be excluded.
PLAYGROUND_ONLY_MARKERS = {"breathy", "moaning", "soft"}

LEGACY_S1_MARKERS = {
    f"({marker})" for marker in DOCUMENTED_MARKERS
}  # Reject parenthesized forms of all registered cues, including S2 additions.


def extract_bracket_markers(text: str) -> set[str]:
    """Return bracketed cues in a text field without interpreting prose."""
    import re

    return set(re.findall(r"\[([^\[\]]+)\]", text))


def validate_text(text: str) -> None:
    """Reject unsupported/malformed cues without rewriting the supplied script."""
    import re

    if not isinstance(text, str) or not text.strip():
        raise ValueError("text 必须是非空文本。")
    unknown = extract_bracket_markers(text) - DOCUMENTED_MARKERS
    if unknown:
        raise ValueError(
            f"未登记的标签：{', '.join(sorted(unknown))}；"
            "本项目仅放行已核实清单，见 chatgpt_project/02_fish_tags.md。"
        )
    remaining = re.sub(r"\[[^\[\]]+\]", "", text)
    if "[" in remaining or "]" in remaining:
        raise ValueError("方括号标签不完整或嵌套；请检查 text。")
    legacy = {f"({s})" for s in re.findall(r"\(([^()]+)\)", text)} & LEGACY_S1_MARKERS
    if legacy:
        raise ValueError(f"不支持 S1 圆括号标签：{', '.join(sorted(legacy))}")
    if not remaining.strip():
        raise ValueError("text 必须包含台词，不能只有标签。")
