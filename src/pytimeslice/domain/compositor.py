"""Compositing primitives for building timeslice images from plans."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .models import (
    CompositeResult,
    RGBImage,
    SliceBand,
    SliceEffects,
    TimeslicePlan,
    TimesliceSpec,
    validate_slice_effects,
)
from .planner import build_timeslice_plan


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


def _inner_effect_extent(
    requested_width: int,
    band: SliceBand,
) -> int:
    band_span = band.end - band.start
    return min(requested_width, band_span // 2)


def _apply_curve(values: np.ndarray, curve: str) -> np.ndarray:
    if curve == "linear":
        return values
    if curve == "smoothstep":
        return values * values * (3.0 - (2.0 * values))
    if curve == "cosine":
        return 0.5 - (0.5 * np.cos(np.pi * values))
    return np.where(values >= 0.5, 1.0, 0.0).astype(np.float32)


def _transition_alpha(width: int, curve: str) -> np.ndarray:
    alpha = (np.arange(width, dtype=np.float32) + 0.5) / width
    return _apply_curve(alpha, curve).astype(np.float32)


def _effect_weights(
    width: int,
    opacity: float,
    curve: str,
    *,
    reverse: bool = False,
) -> np.ndarray:
    weights = opacity * _apply_curve(
        (np.arange(width, dtype=np.float32) + 1.0) / width,
        curve,
    )
    if reverse:
        weights = weights[::-1]
    return weights


def _sample_edge_color(
    frame: RGBImage,
    orientation: str,
    index: int,
) -> np.ndarray:
    if orientation == "vertical":
        clamped_index = max(0, min(frame.shape[1] - 1, index))
        return frame[:, clamped_index, :].mean(axis=0, dtype=np.float32)

    clamped_index = max(0, min(frame.shape[0] - 1, index))
    return frame[clamped_index, :, :].mean(axis=0, dtype=np.float32)


def _resolve_border_colors(
    left_frame: RGBImage,
    right_frame: RGBImage,
    orientation: str,
    boundary: int,
    width: int,
    effects: SliceEffects,
) -> np.ndarray:
    if effects.border_color_mode == "solid":
        solid = np.asarray(effects.border_color, dtype=np.float32)
        return np.repeat(solid[np.newaxis, :], width, axis=0)

    left_color = _sample_edge_color(left_frame, orientation, boundary - 1)
    right_color = _sample_edge_color(right_frame, orientation, boundary)

    if effects.border_color_mode == "auto":
        auto_color = (left_color + right_color) / 2.0
        return np.repeat(auto_color[np.newaxis, :], width, axis=0)

    blend = _transition_alpha(width, effects.curve).reshape(-1, 1)
    return (left_color.reshape(1, 3) * (1.0 - blend)) + (
        right_color.reshape(1, 3) * blend
    )


def _blend_boundary(
    output: RGBImage,
    left_frame: RGBImage,
    right_frame: RGBImage,
    orientation: str,
    boundary: int,
    left_extent: int,
    right_extent: int,
    curve: str,
) -> None:
    start = boundary - left_extent
    end = boundary + right_extent
    if start >= end:
        return

    alpha = _transition_alpha(end - start, curve)

    if orientation == "vertical":
        left_region = left_frame[:, start:end, :].astype(np.float32)
        right_region = right_frame[:, start:end, :].astype(np.float32)
        weights = alpha.reshape(1, -1, 1)
        output[:, start:end, :] = np.rint(
            left_region * (1.0 - weights) + right_region * weights
        ).astype(np.uint8)
    else:
        left_region = left_frame[start:end, :, :].astype(np.float32)
        right_region = right_frame[start:end, :, :].astype(np.float32)
        weights = alpha.reshape(-1, 1, 1)
        output[start:end, :, :] = np.rint(
            left_region * (1.0 - weights) + right_region * weights
        ).astype(np.uint8)


def _apply_shadow_region(
    output: RGBImage,
    orientation: str,
    start: int,
    end: int,
    weights: np.ndarray,
) -> None:
    if start >= end:
        return

    if orientation == "vertical":
        region = output[:, start:end, :].astype(np.float32)
        factors = (1.0 - weights).reshape(1, -1, 1)
        output[:, start:end, :] = np.rint(region * factors).astype(np.uint8)
    else:
        region = output[start:end, :, :].astype(np.float32)
        factors = (1.0 - weights).reshape(-1, 1, 1)
        output[start:end, :, :] = np.rint(region * factors).astype(np.uint8)


def _apply_color_region(
    output: RGBImage,
    orientation: str,
    start: int,
    end: int,
    weights: np.ndarray,
    color: Sequence[int],
) -> None:
    if start >= end:
        return

    blend_color = np.asarray(color, dtype=np.float32)

    if orientation == "vertical":
        region = output[:, start:end, :].astype(np.float32)
        factors = weights.reshape(1, -1, 1)
        output[:, start:end, :] = np.rint(
            region * (1.0 - factors) + blend_color.reshape(1, 1, 3) * factors
        ).astype(np.uint8)
    else:
        region = output[start:end, :, :].astype(np.float32)
        factors = weights.reshape(-1, 1, 1)
        output[start:end, :, :] = np.rint(
            region * (1.0 - factors) + blend_color.reshape(1, 1, 3) * factors
        ).astype(np.uint8)


def _apply_boundary_shadow(
    output: RGBImage,
    orientation: str,
    boundary: int,
    left_extent: int,
    right_extent: int,
    opacity: float,
    curve: str,
) -> None:
    if left_extent > 0:
        left_weights = _effect_weights(left_extent, opacity, curve)
        _apply_shadow_region(
            output=output,
            orientation=orientation,
            start=boundary - left_extent,
            end=boundary,
            weights=left_weights,
        )

    if right_extent > 0:
        right_weights = _effect_weights(
            right_extent,
            opacity,
            curve,
            reverse=True,
        )
        _apply_shadow_region(
            output=output,
            orientation=orientation,
            start=boundary,
            end=boundary + right_extent,
            weights=right_weights,
        )


def _apply_boundary_highlight(
    output: RGBImage,
    orientation: str,
    boundary: int,
    left_extent: int,
    right_extent: int,
    opacity: float,
    color: Sequence[int],
    curve: str,
) -> None:
    if left_extent > 0:
        left_weights = _effect_weights(left_extent, opacity, curve)
        _apply_color_region(
            output=output,
            orientation=orientation,
            start=boundary - left_extent,
            end=boundary,
            weights=left_weights,
            color=color,
        )

    if right_extent > 0:
        right_weights = _effect_weights(
            right_extent,
            opacity,
            curve,
            reverse=True,
        )
        _apply_color_region(
            output=output,
            orientation=orientation,
            start=boundary,
            end=boundary + right_extent,
            weights=right_weights,
            color=color,
        )


def _apply_boundary_border(
    output: RGBImage,
    orientation: str,
    boundary: int,
    width: int,
    colors: np.ndarray,
    opacity: float,
) -> None:
    if width <= 0 or opacity <= 0.0:
        return

    span = output.shape[1] if orientation == "vertical" else output.shape[0]
    start = max(0, boundary - (width // 2))
    end = min(span, start + width)
    overlay = colors[: end - start].astype(np.float32)

    if orientation == "vertical":
        region = output[:, start:end, :].astype(np.float32)
        output[:, start:end, :] = np.rint(
            region * (1.0 - opacity) + overlay.reshape(1, -1, 3) * opacity
        ).astype(np.uint8)
    else:
        region = output[start:end, :, :].astype(np.float32)
        output[start:end, :, :] = np.rint(
            region * (1.0 - opacity) + overlay.reshape(-1, 1, 3) * opacity
        ).astype(np.uint8)


def _apply_slice_effects(
    output: RGBImage,
    images: Sequence[RGBImage],
    plan: TimeslicePlan,
    effects: SliceEffects,
) -> None:
    validate_slice_effects(effects)

    if len(plan.bands) < 2:
        return
    if plan.orientation is None:
        raise ValueError("Band layouts require an orientation.")

    orientation = plan.orientation

    for left_band, right_band in zip(plan.bands, plan.bands[1:]):
        boundary = left_band.end
        if boundary != right_band.start:
            continue

        left_frame = images[left_band.frame_index]
        right_frame = images[right_band.frame_index]

        feather_left = _inner_effect_extent(effects.feather_width, left_band)
        feather_right = _inner_effect_extent(effects.feather_width, right_band)
        if feather_left > 0 or feather_right > 0:
            _blend_boundary(
                output=output,
                left_frame=left_frame,
                right_frame=right_frame,
                orientation=orientation,
                boundary=boundary,
                left_extent=feather_left,
                right_extent=feather_right,
                curve=effects.curve,
            )

        shadow_left = _inner_effect_extent(effects.shadow_width, left_band)
        shadow_right = _inner_effect_extent(effects.shadow_width, right_band)
        if (shadow_left > 0 or shadow_right > 0) and effects.shadow_opacity > 0.0:
            _apply_boundary_shadow(
                output=output,
                orientation=orientation,
                boundary=boundary,
                left_extent=shadow_left,
                right_extent=shadow_right,
                opacity=effects.shadow_opacity,
                curve=effects.curve,
            )

        highlight_left = _inner_effect_extent(effects.highlight_width, left_band)
        highlight_right = _inner_effect_extent(effects.highlight_width, right_band)
        if (
            highlight_left > 0 or highlight_right > 0
        ) and effects.highlight_opacity > 0.0:
            _apply_boundary_highlight(
                output=output,
                orientation=orientation,
                boundary=boundary,
                left_extent=highlight_left,
                right_extent=highlight_right,
                opacity=effects.highlight_opacity,
                color=effects.highlight_color,
                curve=effects.curve,
            )

        if effects.border_width > 0:
            border_colors = _resolve_border_colors(
                left_frame=left_frame,
                right_frame=right_frame,
                orientation=orientation,
                boundary=boundary,
                width=effects.border_width,
                effects=effects,
            )
            _apply_boundary_border(
                output=output,
                orientation=orientation,
                boundary=boundary,
                width=effects.border_width,
                colors=border_colors,
                opacity=effects.border_opacity,
            )


def apply_timeslice_plan(
    images: Sequence[RGBImage],
    plan: TimeslicePlan,
    effects: SliceEffects | None = None,
) -> CompositeResult:
    """Apply a slice plan to images and return the rendered composite."""
    height, width, _ = _validate_images(images)
    output = np.zeros((height, width, 3), dtype=np.uint8)

    if plan.layout == "bands":
        for band in plan.bands:
            frame = images[band.frame_index]

            if plan.orientation == "vertical":
                output[:, band.start : band.end, :] = frame[:, band.start : band.end, :]
            else:
                output[band.start : band.end, :, :] = frame[band.start : band.end, :, :]
    else:
        if plan.slice_map is None or plan.slice_frame_indices is None:
            raise ValueError(
                "Mask-based plans must define slice_map and slice_frame_indices."
            )

        for slice_index, frame_index in enumerate(plan.slice_frame_indices):
            pixel_mask = plan.slice_map == slice_index
            if not np.any(pixel_mask):
                continue
            output[pixel_mask] = images[frame_index][pixel_mask]

    if effects is not None:
        if plan.layout != "bands":
            raise ValueError(
                "Slice effects are currently supported only for layout='bands'."
            )
        _apply_slice_effects(
            output=output,
            images=images,
            plan=plan,
            effects=effects,
        )

    if plan.layout == "bands":
        used_frame_indices = sorted({band.frame_index for band in plan.bands})
    else:
        used_frame_indices = (
            sorted(set(plan.slice_frame_indices))
            if plan.slice_frame_indices is not None
            else []
        )

    return CompositeResult(
        image=output,
        plan=plan,
        used_frame_indices=used_frame_indices,
    )


def build_timeslice(
    images: Sequence[RGBImage],
    spec: TimesliceSpec | None = None,
) -> CompositeResult:
    """Build a complete timeslice composite from images and a render spec."""
    if spec is None:
        spec = TimesliceSpec()

    plan = build_timeslice_plan(images=images, spec=spec)
    return apply_timeslice_plan(images=images, plan=plan, effects=spec.effects)
