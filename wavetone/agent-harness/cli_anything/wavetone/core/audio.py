"""Audio probing utilities for WaveTone projects."""

from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

from .project import normalize_audio_path


def _probe_wav_stdlib(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
    duration = frames / sample_rate if sample_rate else 0.0
    return {
        "path": str(path),
        "format": "wav",
        "codec": "pcm",
        "duration_seconds": round(duration, 6),
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "size_bytes": path.stat().st_size,
        "probe_method": "python-wave",
    }


def _probe_ffprobe(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe not found")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,sample_rate,channels:format=duration,format_name,bit_rate,size",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    audio_stream = next(
        (stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"),
        {},
    )
    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or 0.0)
    return {
        "path": str(path),
        "format": fmt.get("format_name"),
        "codec": audio_stream.get("codec_name"),
        "duration_seconds": round(duration, 6),
        "sample_rate": int(audio_stream["sample_rate"]) if audio_stream.get("sample_rate") else None,
        "channels": audio_stream.get("channels"),
        "bit_rate": int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
        "size_bytes": int(fmt.get("size") or path.stat().st_size),
        "probe_method": "ffprobe",
    }


def probe_audio(audio_path: str | Path) -> dict[str, Any]:
    path = normalize_audio_path(audio_path)
    if path.suffix.lower() in {".wav", ".wave"}:
        try:
            return _probe_wav_stdlib(path)
        except (wave.Error, EOFError):
            pass
    try:
        return _probe_ffprobe(path)
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError):
        return {
            "path": str(path),
            "format": path.suffix.lower().lstrip(".") or None,
            "codec": None,
            "duration_seconds": None,
            "sample_rate": None,
            "channels": None,
            "size_bytes": path.stat().st_size,
            "probe_method": "stat",
            "warning": "Install ffprobe for detailed metadata on this format.",
        }
