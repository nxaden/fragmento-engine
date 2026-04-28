from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from pytimeslice.shared.types import ResizeMode
from pytimeslice.domain.models import RGBImage

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def center_crop_to_size(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize an image to fill the target size, then crop the center region."""
    w, h = img.size

    scale = max(target_w / w, target_h / h)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))

    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    right = left + target_w
    bottom = top + target_h

    return resized.crop((left, top, right, bottom))


def normalize_pil_image(
    image: Image.Image,
    *,
    target_w: int,
    target_h: int,
    resize_mode: ResizeMode = "crop",
) -> Image.Image:
    """Normalize an image to the requested size and RGB colorspace."""
    converted = image.convert("RGB")

    if converted.size == (target_w, target_h):
        return converted

    if resize_mode == "resize":
        return converted.resize((target_w, target_h), Image.Resampling.LANCZOS)
    if resize_mode == "crop":
        return center_crop_to_size(converted, target_w, target_h)

    raise ValueError(f"Unsupported resize_mode: {resize_mode}")


def normalize_rgb_image(
    image: RGBImage,
    *,
    target_w: int,
    target_h: int,
    resize_mode: ResizeMode = "crop",
) -> RGBImage:
    """Normalize an RGB numpy array to the requested size."""
    pil_image = Image.fromarray(image).convert("RGB")
    normalized = normalize_pil_image(
        pil_image,
        target_w=target_w,
        target_h=target_h,
        resize_mode=resize_mode,
    )
    return np.array(normalized, dtype=np.uint8)


def load_image_to_size(
    path: Path | str,
    *,
    target_w: int,
    target_h: int,
    resize_mode: ResizeMode = "crop",
) -> RGBImage:
    """Load an image file and normalize it to the requested size."""
    with Image.open(path) as opened:
        normalized = normalize_pil_image(
            opened,
            target_w=target_w,
            target_h=target_h,
            resize_mode=resize_mode,
        )
        return np.array(normalized, dtype=np.uint8)


class PILImageSequenceLoader:
    """PIL-based infrastructure adapter for discovering and loading image sequences."""

    def get_image_paths(self, folder: Path) -> list[Path]:
        """Return supported image paths in sorted order."""
        paths = [
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS
        ]
        paths.sort()
        return paths

    def load_images(
        self,
        paths: Sequence[Path],
        resize_mode: ResizeMode = "crop",
    ) -> list[RGBImage]:
        """Load image files into normalized RGB numpy arrays."""
        if not paths:
            raise ValueError("No images found in the input folder.")

        images: list[RGBImage] = []

        with Image.open(paths[0]) as first_img:
            first = normalize_pil_image(
                first_img,
                target_w=first_img.size[0],
                target_h=first_img.size[1],
                resize_mode=resize_mode,
            )
            base_w, base_h = first.size
            images.append(np.array(first, dtype=np.uint8))

        for path in paths[1:]:
            images.append(
                load_image_to_size(
                    path,
                    target_w=base_w,
                    target_h=base_h,
                    resize_mode=resize_mode,
                )
            )

        return images
