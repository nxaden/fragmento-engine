"""Slice planning primitives for turning render intent into bands and masks."""

from __future__ import annotations

from typing import Sequence, cast

import numpy as np
import numpy.typing as npt

from .models import (
    RGBImage,
    SliceBand,
    TimeslicePlan,
    TimesliceSpec,
    validate_timeslice_spec,
)


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


def max_supported_slices(
    *,
    height: int,
    width: int,
    spec: TimesliceSpec,
) -> int:
    """Return the maximum number of non-empty regions supported by a layout."""
    if spec.layout == "bands":
        return width if spec.orientation == "vertical" else height
    if spec.layout == "circular":
        return int(np.unique(_build_circular_layout_mask(height, width)).size)
    if spec.layout == "random":
        max_rows = _largest_power_of_two_at_least_two(height)
        max_cols = _largest_power_of_two_at_least_two(width)
        if max_rows == 0 or max_cols == 0:
            return 0
        return max_rows * max_cols
    return height * width


def _build_band_plan(
    *,
    spec: TimesliceSpec,
    span: int,
    frame_indices: npt.NDArray[np.int_],
    num_slices: int,
) -> TimeslicePlan:
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
        layout="bands",
        orientation=spec.orientation,
        bands=bands,
    )


def _build_diagonal_layout_mask(height: int, width: int) -> npt.NDArray[np.float64]:
    y_coords, x_coords = np.indices((height, width), dtype=np.float64)
    return y_coords + x_coords


def _build_spiral_layout_mask(height: int, width: int) -> npt.NDArray[np.float64]:
    total_pixels = height * width
    order_map = np.full((height, width), -1, dtype=np.int_)

    row = (height - 1) // 2
    col = (width - 1) // 2
    order_map[row, col] = 0
    next_index = 1
    step_length = 1
    directions = ((0, 1), (1, 0), (0, -1), (-1, 0))

    while next_index < total_pixels:
        for direction_index, (delta_row, delta_col) in enumerate(directions):
            for _ in range(step_length):
                row += delta_row
                col += delta_col
                if 0 <= row < height and 0 <= col < width and order_map[row, col] < 0:
                    order_map[row, col] = next_index
                    next_index += 1
                    if next_index >= total_pixels:
                        break
            if next_index >= total_pixels:
                break
            if direction_index % 2 == 1:
                step_length += 1

    return order_map.astype(np.float64)


def _build_circular_layout_mask(height: int, width: int) -> npt.NDArray[np.float64]:
    center_y = (height - 1) / 2.0
    center_x = (width - 1) / 2.0
    y_coords, x_coords = np.indices((height, width), dtype=np.float64)
    return ((y_coords - center_y) ** 2) + ((x_coords - center_x) ** 2)


def _resolve_random_block_count(spec: TimesliceSpec) -> int:
    return spec.num_blocks if spec.num_blocks is not None else 4


def _largest_power_of_two_at_least_two(limit: int) -> int:
    value = 1
    while value * 2 <= limit:
        value *= 2
    return value if value >= 2 else 0


def _resolve_random_grid_shape(
    *,
    height: int,
    width: int,
    num_blocks: int,
) -> tuple[int, int]:
    feasible_pairs: list[tuple[float, int, int]] = []
    image_aspect = width / height

    rows = 2
    while rows <= num_blocks:
        if num_blocks % rows == 0:
            cols = num_blocks // rows
            if rows >= 2 and cols >= 2 and rows <= height and cols <= width:
                block_aspect_ratio = cols / rows
                score = abs(np.log(block_aspect_ratio / image_aspect))
                feasible_pairs.append((float(score), rows, cols))
        rows *= 2

    if not feasible_pairs:
        raise ValueError(
            f"num_blocks={num_blocks} does not fit within the image dimensions "
            f"({height}, {width}) for layout='random'."
        )

    prefers_wider = width >= height
    feasible_pairs.sort(
        key=lambda item: (
            item[0],
            abs(item[2] - item[1]),
            item[1] if prefers_wider else item[2],
        )
    )
    _, rows, cols = feasible_pairs[0]
    return rows, cols


def _build_random_block_map(
    *,
    height: int,
    width: int,
    num_blocks: int,
) -> npt.NDArray[np.int_]:
    rows, cols = _resolve_random_grid_shape(
        height=height,
        width=width,
        num_blocks=num_blocks,
    )
    row_edges = np.linspace(0, height, rows + 1).round().astype(np.int_)
    col_edges = np.linspace(0, width, cols + 1).round().astype(np.int_)
    block_map = np.empty((height, width), dtype=np.int_)

    block_index = 0
    for row_index in range(rows):
        row_start = int(row_edges[row_index])
        row_end = int(row_edges[row_index + 1])
        for col_index in range(cols):
            col_start = int(col_edges[col_index])
            col_end = int(col_edges[col_index + 1])
            block_map[row_start:row_end, col_start:col_end] = block_index
            block_index += 1

    return block_map


def _build_random_block_plan(
    *,
    height: int,
    width: int,
    num_images: int,
    spec: TimesliceSpec,
) -> TimeslicePlan:
    num_blocks = _resolve_random_block_count(spec)
    rng = np.random.default_rng(spec.random_seed)
    candidate_frame_indices = np.arange(num_images, dtype=np.int_)
    if spec.reverse_time:
        candidate_frame_indices = candidate_frame_indices[::-1]

    random_indices = rng.integers(0, num_images, size=num_blocks)
    slice_frame_indices = candidate_frame_indices[random_indices].tolist()

    return TimeslicePlan(
        layout="random",
        slice_map=_build_random_block_map(
            height=height,
            width=width,
            num_blocks=num_blocks,
        ),
        slice_frame_indices=slice_frame_indices,
    )


def _coerce_layout_mask(
    layout_mask: npt.ArrayLike,
    *,
    height: int,
    width: int,
    num_slices: int,
) -> npt.NDArray[np.float64]:
    coerced = np.asarray(layout_mask, dtype=np.float64)

    if coerced.ndim != 2:
        raise ValueError("layout_mask must be a 2D array.")
    if coerced.shape != (height, width):
        raise ValueError(f"layout_mask must match image shape ({height}, {width}).")
    if not np.isfinite(coerced).all():
        raise ValueError("layout_mask must contain only finite values.")
    if num_slices > 1 and np.all(coerced == coerced.flat[0]):
        raise ValueError(
            "layout_mask must contain at least 2 distinct values when rendering "
            "more than 1 slice."
        )

    return coerced


def _resolve_layout_mask(
    *,
    height: int,
    width: int,
    spec: TimesliceSpec,
    num_slices: int,
) -> npt.NDArray[np.float64]:
    if spec.layout == "diagonal":
        return _build_diagonal_layout_mask(height, width)
    if spec.layout == "spiral":
        return _build_spiral_layout_mask(height, width)
    if spec.layout == "circular":
        return _build_circular_layout_mask(height, width)
    if spec.layout == "mask":
        if spec.layout_mask is None:
            raise ValueError("layout_mask is required when layout='mask'.")
        return _coerce_layout_mask(
            cast(npt.ArrayLike, spec.layout_mask),
            height=height,
            width=width,
            num_slices=num_slices,
        )

    raise ValueError(f"Unsupported layout: {spec.layout!r}.")


def _build_slice_map(
    layout_mask: npt.NDArray[np.float64],
    *,
    num_slices: int,
) -> npt.NDArray[np.int_]:
    flat = layout_mask.reshape(-1)
    pixel_order = np.argsort(flat, kind="stable")
    slice_ids_by_rank = (np.arange(flat.size, dtype=np.int_) * num_slices) // flat.size
    slice_map = np.empty(flat.size, dtype=np.int_)
    slice_map[pixel_order] = slice_ids_by_rank
    return slice_map.reshape(layout_mask.shape)


def _build_grouped_slice_map(
    layout_mask: npt.NDArray[np.float64],
    *,
    num_slices: int,
) -> npt.NDArray[np.int_]:
    flat = layout_mask.reshape(-1)
    _, inverse, counts = np.unique(flat, return_inverse=True, return_counts=True)
    starts = np.cumsum(np.concatenate(([0], counts[:-1])))
    midpoints = starts + ((counts - 1) / 2.0)
    slice_ids = np.floor((midpoints * num_slices) / flat.size).astype(np.int_)
    slice_ids = np.clip(slice_ids, 0, num_slices - 1)
    return slice_ids[inverse].reshape(layout_mask.shape)


def build_timeslice_plan(
    images: Sequence[RGBImage],
    spec: TimesliceSpec,
) -> TimeslicePlan:
    """Build a concrete slice plan for a normalized image sequence."""
    validate_timeslice_spec(spec)
    height, width, _ = _validate_images(images)

    if spec.layout == "random":
        num_blocks = _resolve_random_block_count(spec)
        max_blocks = max_supported_slices(height=height, width=width, spec=spec)
        if num_blocks > max_blocks:
            raise ValueError(
                f"num_blocks={num_blocks} exceeds available block capacity "
                f"({max_blocks}) for layout='random'."
            )
        return _build_random_block_plan(
            height=height,
            width=width,
            num_images=len(images),
            spec=spec,
        )

    num_slices = spec.num_slices if spec.num_slices is not None else len(images)

    max_slices = max_supported_slices(height=height, width=width, spec=spec)
    if num_slices > max_slices:
        if spec.layout == "bands":
            raise ValueError(
                f"num_slices={num_slices} exceeds available pixel span ({max_slices}) "
                f"for orientation={spec.orientation!r}."
            )
        raise ValueError(
            f"num_slices={num_slices} exceeds available pixel capacity "
            f"({max_slices}) for layout={spec.layout!r}."
        )

    frame_indices = _build_frame_indices(
        num_images=len(images),
        num_slices=num_slices,
        reverse_time=spec.reverse_time,
    )

    if spec.layout == "bands":
        span = width if spec.orientation == "vertical" else height
        return _build_band_plan(
            spec=spec,
            span=span,
            frame_indices=frame_indices,
            num_slices=num_slices,
        )

    layout_mask = _resolve_layout_mask(
        height=height,
        width=width,
        spec=spec,
        num_slices=num_slices,
    )
    if spec.layout == "circular":
        slice_map = _build_grouped_slice_map(layout_mask, num_slices=num_slices)
    else:
        slice_map = _build_slice_map(layout_mask, num_slices=num_slices)

    return TimeslicePlan(
        layout=spec.layout,
        slice_map=slice_map,
        slice_frame_indices=[int(frame_index) for frame_index in frame_indices],
    )
