from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from typing import Sequence

from PIL import Image

from pytimeslice.domain.models import RGBImage


class PILImageWriter:
    """PIL-based infrastructure adapter for saving rendered images."""

    def save(self, image: RGBImage, output_file: Path) -> None:
        """Save an RGB numpy array to disk."""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(image).save(output_file)

    def save_gif(
        self,
        images: Sequence[RGBImage],
        output_file: Path,
        *,
        duration_ms: int = 250,
    ) -> None:
        """Save RGB numpy arrays as an animated GIF."""
        if not images:
            raise ValueError("At least one frame is required to save a GIF.")

        output_file.parent.mkdir(parents=True, exist_ok=True)

        pil_frames = [Image.fromarray(image) for image in images]
        first_frame, *remaining_frames = pil_frames
        first_frame.save(
            output_file,
            save_all=True,
            append_images=remaining_frames,
            duration=duration_ms,
            loop=0,
        )

    def save_video(
        self,
        images: Sequence[RGBImage],
        output_file: Path,
        *,
        fps: int = 6,
    ) -> None:
        """Save RGB numpy arrays as an MP4 or MOV using ffmpeg."""
        if not images:
            raise ValueError("At least one frame is required to save a video.")
        if fps <= 0:
            raise ValueError("fps must be greater than 0.")
        if output_file.suffix.lower() not in {".mp4", ".mov"}:
            raise ValueError("Video output file must use the .mp4 or .mov extension.")

        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path is None:
            raise OSError("ffmpeg executable not found on PATH.")

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with TemporaryDirectory(prefix="pytimeslice-video-") as temp_dir:
            temp_path = Path(temp_dir)
            for index, image in enumerate(images):
                frame_file = temp_path / f"frame_{index:06d}.png"
                Image.fromarray(image).save(frame_file)

            frame_pattern = temp_path / "frame_%06d.png"
            command = [
                ffmpeg_path,
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(frame_pattern),
                "-vf",
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(output_file),
            ]

            try:
                subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as exc:
                raise OSError(
                    exc.stderr.strip() or "ffmpeg video encoding failed."
                ) from exc
