from pathlib import Path
from typing import Sequence

from PIL import Image

from fragmento_engine.domain.models import RGBImage


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
