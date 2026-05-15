from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from pytimeslice.domain.models import RGBImage
from pytimeslice.infrastructure.image_loader import normalize_rgb_image
from pytimeslice.shared.types import ResizeMode


@dataclass(frozen=True)
class VideoStreamInfo:
    """Metadata for the first video stream used as timeslice input."""

    width: int
    height: int
    frame_count: int


class FFmpegVideoFrameLoader:
    """ffmpeg-backed adapter for sampling RGB frames from video files."""

    def _require_executable(self, name: str) -> str:
        executable = shutil.which(name)
        if executable is None:
            raise OSError(f"{name} executable not found on PATH.")
        return executable

    def _probe(self, video_file: Path) -> VideoStreamInfo:
        ffprobe_path = self._require_executable("ffprobe")
        command = [
            ffprobe_path,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_read_frames,nb_frames",
            "-of",
            "json",
            str(video_file),
        ]

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise OSError(
                exc.stderr.strip() or "ffprobe video probing failed."
            ) from exc

        payload = json.loads(completed.stdout)
        streams = payload.get("streams", [])
        if not streams:
            raise ValueError(f"No video stream found in: {video_file}")

        stream = streams[0]
        width = int(stream["width"])
        height = int(stream["height"])
        raw_frame_count = stream.get("nb_read_frames") or stream.get("nb_frames")
        if raw_frame_count in (None, "N/A"):
            raise ValueError("Could not determine video frame count.")

        frame_count = int(raw_frame_count)
        if frame_count < 1:
            raise ValueError("Video must contain at least one frame.")

        return VideoStreamInfo(width=width, height=height, frame_count=frame_count)

    def count_frames(self, video_file: Path) -> int:
        """Return the number of decodable frames in the first video stream."""
        return self._probe(video_file).frame_count

    def load_frames(
        self,
        video_file: Path,
        frame_indices: Sequence[int],
        resize_mode: ResizeMode = "crop",
    ) -> list[RGBImage]:
        """Load selected video frames into normalized RGB numpy arrays."""
        if not frame_indices:
            raise ValueError("At least one frame index is required.")

        info = self._probe(video_file)
        unique_indices = sorted(set(frame_indices))
        if unique_indices[0] < 0 or unique_indices[-1] >= info.frame_count:
            raise ValueError(
                f"Frame indices must be between 0 and {info.frame_count - 1}."
            )

        ffmpeg_path = self._require_executable("ffmpeg")
        select_expr = "+".join(f"eq(n\\,{index})" for index in unique_indices)
        command = [
            ffmpeg_path,
            "-v",
            "error",
            "-i",
            str(video_file),
            "-vf",
            f"select={select_expr}",
            "-vsync",
            "0",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ]

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace").strip()
            raise OSError(stderr or "ffmpeg video frame extraction failed.") from exc

        frame_size = info.width * info.height * 3
        expected_size = frame_size * len(unique_indices)
        if len(completed.stdout) != expected_size:
            raise OSError("ffmpeg returned an unexpected number of video frames.")

        decoded_by_index: dict[int, RGBImage] = {}
        for offset, frame_index in enumerate(unique_indices):
            start = offset * frame_size
            end = start + frame_size
            raw_frame = np.frombuffer(completed.stdout[start:end], dtype=np.uint8)
            decoded_by_index[frame_index] = raw_frame.reshape(
                (info.height, info.width, 3)
            ).copy()

        first = decoded_by_index[unique_indices[0]]
        target_h, target_w, _ = first.shape
        return [
            normalize_rgb_image(
                decoded_by_index[frame_index],
                target_w=target_w,
                target_h=target_h,
                resize_mode=resize_mode,
            )
            for frame_index in frame_indices
        ]
