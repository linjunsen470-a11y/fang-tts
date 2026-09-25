"""Generate Fish Audio speech from a YAML configuration file."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import yaml
from fishaudio import FishAudio
from fishaudio.types import Prosody, TTSConfig

from config import ROOT, load_api_key

LOGGER = logging.getLogger("fish-tts")
CONFIG_FIELDS = set(TTSConfig.model_fields) - {"reference_id", "references", "prosody"}


def read_config(path: Path) -> tuple[dict[str, Any], Path]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read YAML file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")

    for field in ("model", "reference_id", "text", "output"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"'{field}' must be a non-empty string")

    options = data.get("tts", {})
    if not isinstance(options, dict):
        raise ValueError("'tts' must be a YAML mapping")
    unknown = set(options) - CONFIG_FIELDS - {"prosody"}
    if unknown:
        raise ValueError(f"unknown 'tts' option(s): {', '.join(sorted(unknown))}")

    prosody = options.get("prosody", {})
    if not isinstance(prosody, dict):
        raise ValueError("'tts.prosody' must be a YAML mapping")
    unknown_prosody = set(prosody) - set(Prosody.model_fields)
    if unknown_prosody:
        raise ValueError(
            f"unknown 'tts.prosody' option(s): {', '.join(sorted(unknown_prosody))}"
        )

    output_path = Path(data["output"])
    if not output_path.is_absolute():
        output_path = path.resolve().parent / output_path
    return data, output_path


def synthesize(config_path: Path) -> Path:
    data, output_path = read_config(config_path)
    api_key = load_api_key()

    options = dict(data.get("tts", {}))
    prosody = options.pop("prosody", {})
    tts_config = TTSConfig(
        reference_id=data["reference_id"].strip(),
        prosody=Prosody(**prosody),
        **options,
    )

    LOGGER.info("model: %s", data["model"])
    LOGGER.info("reference_id: %s", data["reference_id"].strip())
    LOGGER.info("text: %s", data["text"])
    LOGGER.info("output: %s", output_path)
    LOGGER.info("requesting Fish Audio TTS...")

    client = FishAudio(api_key=api_key)
    try:
        audio = client.tts.convert(
            text=data["text"],
            model=data["model"].strip(),
            config=tts_config,
        )
    finally:
        client.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio)
    LOGGER.info("done: %s (%s bytes)", output_path, len(audio))
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Fish Audio TTS (YAML driven)")
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        default=ROOT / "tts.yaml",
        help="configuration YAML (default: tts.yaml)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    try:
        synthesize(args.config)
    except Exception as exc:
        LOGGER.error("TTS failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
