"""Slice planning primitives for turning render intent into pixel bands."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import numpy.typing as npt

from .models import RGBImage, SliceBand, TimeslicePlan, TimesliceSpec


def _validate_images(images: Sequence[RGBImage]) -> tuple[int, int, int]:
    if not images:
        raise ValueError("No images loaded.")

    first = images[0]
    if first.ndim != 3 or first.shape[2] != 3:
        raise ValueError("Expected RGB images.")

    height, width, channels = first.shape

    for i, img in enumerate(images):
        if img.ndim != 3 or img.shape[2] != 3:
            raise ValueError(f"Image at index {i} is not an RGB image.")
        if img.shape != (height, width, channels):
            raise ValueError(
                "All images must have the same dimensions after preprocessing."
            )

    return height, width, channels


def _build_frame_indices(
    num_images: int,
    num_slices: int,
    reverse_time: bool,
) -> npt.NDArray[np.int_]:
    frame_indices = np.linspace(0, num_images - 1, num_slices).round().astype(np.int_)

    if reverse_time:
        frame_indices = frame_indices[::-1]

    return frame_indices


def build_timeslice_plan(
    images: Sequence[RGBImage],
    spec: TimesliceSpec,
) -> TimeslicePlan:
    """Build a concrete slice plan for a normalized image sequence."""
    height, width, _ = _validate_images(images)

    num_slices = spec.num_slices if spec.num_slices is not None else len(images)

    if num_slices < 1:
        raise ValueError("num_slices must be at least 1.")

    if spec.orientation not in ("vertical", "horizontal"):
        raise ValueError("orientation must be 'vertical' or 'horizontal'.")

    span = width if spec.orientation == "vertical" else height
    if num_slices > span:
        raise ValueError(
            f"num_slices={num_slices} exceeds available pixel span ({span}) "
            f"for orientation={spec.orientation!r}."
        )

    frame_indices = _build_frame_indices(
        num_images=len(images),
        num_slices=num_slices,
        reverse_time=spec.reverse_time,
    )

    edges = np.linspace(0, span, num_slices + 1).round().astype(np.int_)

    bands: list[SliceBand] = []
    for i in range(num_slices):
        start = int(edges[i])
        end = int(edges[i + 1])

        if end <= start:
            continue

        bands.append(
            SliceBand(
                frame_index=int(frame_indices[i]),
                start=start,
                end=end,
            )
        )

    return TimeslicePlan(
        orientation=spec.orientation,
        bands=bands,
    )
