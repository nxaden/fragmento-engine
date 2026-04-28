from pathlib import Path
import subprocess

import numpy as np
import pytest
from PIL import Image, ImageSequence

from pytimeslice.infrastructure.image_writer import PILImageWriter


def _solid_frame(value: int, *, width: int = 6, height: int = 4) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


def test_pil_image_writer_saves_png_to_disk(tmp_path: Path) -> None:
    output_file = tmp_path / "out" / "timeslice.png"
    image = _solid_frame(123)

    PILImageWriter().save(image, output_file)

    assert output_file.exists()
    with Image.open(output_file) as opened:
        assert opened.size == (6, 4)
        assert opened.mode == "RGB"
        assert np.array_equal(np.array(opened), image)


def test_pil_image_writer_saves_gif_with_expected_frame_order(tmp_path: Path) -> None:
    output_file = tmp_path / "out" / "progression.gif"
    frames = [
        _solid_frame(0),
        _solid_frame(64),
        _solid_frame(128),
        _solid_frame(64),
    ]

    PILImageWriter().save_gif(frames, output_file, duration_ms=90)

    assert output_file.exists()
    with Image.open(output_file) as opened:
        assert opened.n_frames == 4
        assert opened.info["loop"] == 0
        assert opened.info["duration"] == 90

        saved_frames = [
            np.array(frame.convert("RGB")) for frame in ImageSequence.Iterator(opened)
        ]

    assert len(saved_frames) == len(frames)
    for saved_frame, expected_frame in zip(saved_frames, frames):
        assert np.array_equal(saved_frame, expected_frame)


def test_pil_image_writer_invokes_ffmpeg_for_mp4_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_file = tmp_path / "out" / "progression.mp4"
    frames = [
        _solid_frame(0),
        _solid_frame(64),
        _solid_frame(128),
    ]
    captured: dict[str, list[str]] = {}

    monkeypatch.setattr(
        "pytimeslice.infrastructure.image_writer.shutil.which",
        lambda name: "/usr/bin/ffmpeg",
    )

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert capture_output is True
        assert text is True
        captured["command"] = command

        frame_pattern = Path(command[command.index("-i") + 1])
        saved_frames = sorted(frame_pattern.parent.glob("frame_*.png"))
        assert len(saved_frames) == len(frames)

        first_saved = np.array(Image.open(saved_frames[0]).convert("RGB"))
        last_saved = np.array(Image.open(saved_frames[-1]).convert("RGB"))
        assert np.array_equal(first_saved, frames[0])
        assert np.array_equal(last_saved, frames[-1])

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.touch()
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        "pytimeslice.infrastructure.image_writer.subprocess.run",
        fake_run,
    )

    PILImageWriter().save_video(frames, output_file, fps=6)

    assert output_file.exists()
    assert captured["command"][0] == "/usr/bin/ffmpeg"
    assert captured["command"][-1] == str(output_file)


def test_pil_image_writer_rejects_video_export_without_ffmpeg(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "pytimeslice.infrastructure.image_writer.shutil.which",
        lambda name: None,
    )

    with pytest.raises(OSError, match="ffmpeg executable not found"):
        PILImageWriter().save_video(
            [_solid_frame(0)],
            tmp_path / "out" / "progression.mp4",
            fps=6,
        )
