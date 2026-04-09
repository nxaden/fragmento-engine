import argparse
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image


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


def build_timeslice(
    images: List[np.ndarray],
    orientation: str = "vertical",
    num_slices: int | None = None,
    reverse_time: bool = False,
) -> np.ndarray:
    if not images:
        raise ValueError("No images loaded.")

    h, w, c = images[0].shape
    if c != 3:
        raise ValueError("Expected RGB images.")

    for img in images:
        if img.shape != (h, w, c):
            raise ValueError(
                "All images must have the same dimensions after preprocessing."
            )

    if num_slices is None:
        num_slices = len(images)

    if num_slices < 1:
        raise ValueError("num_slices must be at least 1.")

    frame_indices = np.linspace(0, len(images) - 1, num_slices).round().astype(int)
    if reverse_time:
        frame_indices = frame_indices[::-1]

    if orientation == "vertical":
        output = np.zeros((h, w, 3), dtype=np.uint8)
        x_edges = np.linspace(0, w, num_slices + 1).round().astype(int)

        for i in range(num_slices):
            x0, x1 = x_edges[i], x_edges[i + 1]
            if x1 <= x0:
                continue
            output[:, x0:x1, :] = images[frame_indices[i]][:, x0:x1, :]

    elif orientation == "horizontal":
        output = np.zeros((h, w, 3), dtype=np.uint8)
        y_edges = np.linspace(0, h, num_slices + 1).round().astype(int)

        for i in range(num_slices):
            y0, y1 = y_edges[i], y_edges[i + 1]
            if y1 <= y0:
                continue
            output[y0:y1, :, :] = images[frame_indices[i]][y0:y1, :, :]

    else:
        raise ValueError("orientation must be 'vertical' or 'horizontal'.")

    return output


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
