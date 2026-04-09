import argparse
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image

from fragmento_core.domain.compositor import build_timeslice


VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def get_image_paths(folder: Path) -> List[Path]:
    paths = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS
    ]
    paths.sort()
    return paths


def load_images(paths: List[Path], resize_mode: str = "crop") -> List[np.ndarray]:
    if not paths:
        raise ValueError("No images found in the input folder.")

    images = []
    first = Image.open(paths[0]).convert("RGB")
    base_w, base_h = first.size
    images.append(np.array(first))

    for path in paths[1:]:
        img = Image.open(path).convert("RGB")
        w, h = img.size

        if (w, h) != (base_w, base_h):
            if resize_mode == "resize":
                img = img.resize((base_w, base_h), Image.Resampling.LANCZOS)
            elif resize_mode == "crop":
                img = center_crop_to_size(img, base_w, base_h)
            else:
                raise ValueError(f"Unsupported resize_mode: {resize_mode}")

        images.append(np.array(img))

    return images


def center_crop_to_size(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
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


def main():
    parser = argparse.ArgumentParser(
        description="Create a time-slice image from a sequence of photos."
    )
    parser.add_argument(
        "input_folder", type=Path, help="Folder containing sequential images."
    )
    parser.add_argument("output_file", type=Path, help="Path for the output image.")
    parser.add_argument(
        "--orientation",
        choices=["vertical", "horizontal"],
        default="vertical",
        help="Use vertical strips (left-to-right time) or horizontal strips (top-to-bottom time).",
    )
    parser.add_argument(
        "--slices",
        type=int,
        default=None,
        help="Number of slices in the final image. Default: number of input images.",
    )
    parser.add_argument(
        "--resize-mode",
        choices=["crop", "resize"],
        default="crop",
        help="How to handle images with different sizes.",
    )
    parser.add_argument(
        "--reverse-time",
        action="store_true",
        help="Reverse the time direction in the final image.",
    )

    args = parser.parse_args()

    paths = get_image_paths(args.input_folder)
    if not paths:
        raise SystemExit("No supported image files found.")

    print(f"Found {len(paths)} images.")
    images = load_images(paths, resize_mode=args.resize_mode)

    result = build_timeslice(
        images=images,
        orientation=args.orientation,
        num_slices=args.slices,
        reverse_time=args.reverse_time,
    )

    Image.fromarray(result).save(args.output_file)
    print(f"Saved: {args.output_file}")


if __name__ == "__main__":
    main()
