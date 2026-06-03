from __future__ import annotations

import json
import math
import subprocess
import struct
import wave
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli_anything.wavetone.core import audio as audio_core
from cli_anything.wavetone.core.audio import probe_audio
from cli_anything.wavetone.core.project import (
    DEFAULT_ANALYSIS_SETTINGS,
    add_label,
    create_project,
    load_project,
    save_project,
    set_tempo,
    update_analysis,
)
from cli_anything.wavetone.core.session import append_event, load_events
from cli_anything.wavetone.utils import wavetone_backend
from cli_anything.wavetone.wavetone_cli import cli


def make_wav(path: Path, freq: float = 440.0, duration: float = 0.25, sample_rate: int = 8000) -> Path:
    frames = int(duration * sample_rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        for idx in range(frames):
            sample = int(16000 * math.sin(2 * math.pi * freq * idx / sample_rate))
            handle.writeframes(struct.pack("<h", sample))
    return path


def test_create_project_manifest(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project = create_project(wav, name="Tone Test")

    assert project["schema_version"] == "wavetone-project/v1"
    assert project["project"]["name"] == "Tone Test"
    assert project["audio"]["path"] == str(wav.resolve())
    assert project["analysis"] == DEFAULT_ANALYSIS_SETTINGS


def test_rejects_unsupported_audio(tmp_path: Path) -> None:
    txt = tmp_path / "not-audio.txt"
    txt.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError):
        create_project(txt)


def test_save_load_project_roundtrip(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project = create_project(wav)
    add_label(project, "chorus", 12.5)
    set_tempo(project, 128, first_bar_time_seconds=0.2)
    output = save_project(project, tmp_path / "project.json")

    loaded = load_project(output)
    assert loaded["labels"][0]["name"] == "chorus"
    assert loaded["tempo"]["bpm"] == 128
    assert loaded["tempo"]["first_bar_time_seconds"] == 0.2


def test_labels_are_sorted(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project = create_project(wav)
    add_label(project, "late", 4.0)
    add_label(project, "early", 1.0)

    assert [label["name"] for label in project["labels"]] == ["early", "late"]


def test_update_analysis_settings(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project = create_project(wav)
    update_analysis(project, channel="L+R", blocks_per_second=24, analyze_fundamental_frequency=False)

    assert project["analysis"]["channel"] == "L+R"
    assert project["analysis"]["blocks_per_second"] == 24
    assert project["analysis"]["analyze_fundamental_frequency"] is False


def test_probe_wav_metadata(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav", duration=0.5, sample_rate=16000)
    info = probe_audio(wav)

    assert info["probe_method"] == "python-wave"
    assert info["sample_rate"] == 16000
    assert info["channels"] == 1
    assert info["duration_seconds"] == 0.5
    assert info["size_bytes"] > 0


def test_probe_malformed_wav_falls_back_to_stat(tmp_path: Path) -> None:
    wav = tmp_path / "broken.wav"
    wav.write_bytes(b"")

    info = probe_audio(wav)

    assert info["probe_method"] == "stat"
    assert info["format"] == "wav"
    assert info["duration_seconds"] is None
    assert info["size_bytes"] == 0


def test_ffprobe_uses_single_show_entries_argument(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "tone.mp3"
    audio.write_bytes(b"mp3")
    captured: dict[str, list[str]] = {}

    monkeypatch.setattr(audio_core.shutil, "which", lambda name: "ffprobe")

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        stdout = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "audio",
                        "codec_name": "mp3",
                        "sample_rate": "44100",
                        "channels": 2,
                    }
                ],
                "format": {
                    "duration": "1.25",
                    "format_name": "mp3",
                    "bit_rate": "128000",
                    "size": "3",
                },
            }
        )
        return subprocess.CompletedProcess(args, 0, stdout=stdout)

    monkeypatch.setattr(audio_core.subprocess, "run", fake_run)

    info = audio_core._probe_ffprobe(audio)
    entries = captured["args"][captured["args"].index("-show_entries") + 1]

    assert captured["args"].count("-show_entries") == 1
    assert "stream=codec_type,codec_name,sample_rate,channels" in entries
    assert ":format=duration,format_name,bit_rate,size" in entries
    assert info["probe_method"] == "ffprobe"
    assert info["sample_rate"] == 44100


def test_session_event_log(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    append_event(session_path, "created", {"project": "demo"})
    append_event(session_path, "launched", {"pid": 123})

    events = load_events(session_path)
    assert [event["event"] for event in events] == ["created", "launched"]


def test_session_rejects_invalid_schema(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        append_event(session_path, "created", {})

    session_path.write_text(json.dumps({"events": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="events.*list"):
        load_events(session_path)


def test_find_wavetone_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "wavetone.exe"
    fake.write_bytes(b"MZ")
    monkeypatch.setenv("WAVETONE_EXE", str(fake))

    assert wavetone_backend.find_wavetone() == fake.resolve()


def test_cli_preserves_inherited_project_and_json_context(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "tone.wav")
    project_path = save_project(create_project(wav), tmp_path / "tone.wt.json")

    result = CliRunner().invoke(
        cli,
        ["audio", "probe"],
        obj={"project": str(project_path), "json": True},
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["audio"]["path"] == str(wav.resolve())
