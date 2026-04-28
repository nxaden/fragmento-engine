from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Sequence

import numpy as np
import numpy.typing as npt

Orientation = Literal["vertical", "horizontal"]
LayoutMode = Literal["bands", "diagonal", "spiral", "circular", "random", "mask"]
BoundaryCurve = Literal["linear", "smoothstep", "cosine", "hard"]
BorderColorMode = Literal["solid", "auto", "gradient"]
RGBColor = tuple[int, int, int]
RGBImage = npt.NDArray[np.uint8]

_VALID_LAYOUTS = {"bands", "diagonal", "spiral", "circular", "random", "mask"}
_VALID_BORDER_COLOR_MODES = {"solid", "auto", "gradient"}
_VALID_CURVES = {"linear", "smoothstep", "cosine", "hard"}


@dataclass(frozen=True)
class FrameRef:
    """FrameRef is a reference to a singular source frame on disk."""

    index: int
    path: Path


@dataclass(frozen=True)
class SequenceInfo:
    """SequenceInfo describes the loaded sequence at a metadata level."""

    frames: list[FrameRef]
    height: int
    width: int
    channels: int = 3


@dataclass(frozen=True)
class SliceEffects:
    """SliceEffects describes optional treatments applied at slice boundaries."""

    border_width: int = 0
    border_color: RGBColor = (255, 255, 255)
    border_opacity: float = 1.0
    border_color_mode: BorderColorMode = "solid"
    shadow_width: int = 0
    shadow_opacity: float = 0.35
    highlight_width: int = 0
    highlight_opacity: float = 0.35
    highlight_color: RGBColor = (255, 255, 255)
    feather_width: int = 0
    curve: BoundaryCurve = "linear"


def validate_rgb_color(name: str, color: Sequence[int]) -> None:
    if len(color) != 3:
        raise ValueError(f"{name} must contain exactly 3 channels.")
    if any(channel < 0 or channel > 255 for channel in color):
        raise ValueError(f"{name} channels must be between 0 and 255.")


def validate_slice_effects(effects: SliceEffects) -> None:
    if effects.border_width < 0:
        raise ValueError("effects.border_width must be at least 0.")
    if effects.highlight_width < 0:
        raise ValueError("effects.highlight_width must be at least 0.")
    if effects.shadow_width < 0:
        raise ValueError("effects.shadow_width must be at least 0.")
    if effects.feather_width < 0:
        raise ValueError("effects.feather_width must be at least 0.")
    if not 0.0 <= effects.border_opacity <= 1.0:
        raise ValueError("effects.border_opacity must be between 0.0 and 1.0.")
    if not 0.0 <= effects.shadow_opacity <= 1.0:
        raise ValueError("effects.shadow_opacity must be between 0.0 and 1.0.")
    if not 0.0 <= effects.highlight_opacity <= 1.0:
        raise ValueError("effects.highlight_opacity must be between 0.0 and 1.0.")
    if effects.border_color_mode not in _VALID_BORDER_COLOR_MODES:
        raise ValueError(
            "effects.border_color_mode must be one of solid, auto, or gradient."
        )
    if effects.curve not in _VALID_CURVES:
        raise ValueError(
            "effects.curve must be one of linear, smoothstep, cosine, or hard."
        )
    validate_rgb_color("effects.border_color", effects.border_color)
    validate_rgb_color("effects.highlight_color", effects.highlight_color)


def _is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def validate_random_block_count(num_blocks: int) -> None:
    if num_blocks < 4:
        raise ValueError("num_blocks for layout='random' must be at least 4.")

    if not _is_power_of_two(num_blocks):
        raise ValueError(
            "num_blocks for layout='random' must be a power of 2 (for example "
            "4, 8, 16, 32, 64, or 128 total blocks)."
        )


@dataclass(frozen=True)
class TimesliceSpec:
    """TimesliceSpec is the user's render intent.

    `layout="bands"` uses the original straight-band planner controlled by
    `orientation`. `layout="diagonal"`, `layout="spiral"`, and
    `layout="circular"` use built-in mask-based layouts. `layout="random"`
    uses a seeded random block grid. `layout="mask"` expects `layout_mask` to
    be a 2D array matching the input image height and width.
    """

    orientation: Orientation = "vertical"
    layout: LayoutMode = "bands"
    num_slices: int | None = None
    num_blocks: int | None = None
    reverse_time: bool = False
    random_seed: int | None = None
    effects: SliceEffects | None = None
    layout_mask: npt.ArrayLike | None = None


def validate_timeslice_spec(spec: TimesliceSpec) -> None:
    if spec.layout not in _VALID_LAYOUTS:
        raise ValueError(
            "layout must be one of bands, diagonal, spiral, circular, random, or mask."
        )
    if spec.num_slices is not None and spec.num_slices < 1:
        raise ValueError("num_slices must be at least 1.")
    if spec.layout == "bands" and spec.orientation not in ("vertical", "horizontal"):
        raise ValueError("orientation must be 'vertical' or 'horizontal'.")
    if spec.layout == "random" and spec.num_slices is not None:
        raise ValueError(
            "num_slices cannot be used with layout='random'; use num_blocks instead."
        )
    if spec.layout != "random" and spec.num_blocks is not None:
        raise ValueError("num_blocks can only be used when layout='random'.")
    if spec.layout != "random" and spec.random_seed is not None:
        raise ValueError("random_seed can only be used when layout='random'.")
    if spec.layout != "bands" and spec.effects is not None:
        raise ValueError(
            "Slice effects are currently supported only for layout='bands'."
        )
    if spec.layout == "random":
        validate_random_block_count(
            spec.num_blocks if spec.num_blocks is not None else 4
        )
    if spec.layout == "mask" and spec.layout_mask is None:
        raise ValueError("layout_mask is required when layout='mask'.")
    if spec.layout != "mask" and spec.layout_mask is not None:
        raise ValueError("layout_mask can only be used when layout='mask'.")
    if spec.effects is not None:
        validate_slice_effects(spec.effects)


@dataclass(frozen=True)
class SliceBand:
    """SliceBand describes one slice, meaning which frame it comes from and what pixel range it occupies."""

    frame_index: int
    start: int
    end: int


@dataclass(frozen=True)
class TimeslicePlan:
    """TimeslicePlan is the full slice layout."""

    layout: LayoutMode = "bands"
    orientation: Orientation | None = None
    bands: list[SliceBand] = field(default_factory=list)
    slice_map: npt.NDArray[np.int_] | None = None
    slice_frame_indices: list[int] | None = None


@dataclass(frozen=True)
class LayoutBounds:
    """Pixel-space bounding box for one addressable layout slot."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class LayoutSlot:
    """Client-facing metadata for one slot in a layout description."""

    index: int
    bounds: LayoutBounds
    pixel_count: int


@dataclass(frozen=True)
class LayoutDescription:
    """Pure layout metadata for client-driven composition flows."""

    spec: TimesliceSpec
    plan: TimeslicePlan
    width: int
    height: int
    slot_count: int
    slot_map: npt.NDArray[np.int_]
    preview_image: RGBImage
    slots: list[LayoutSlot]

    def mask_for_slot(self, slot_index: int) -> npt.NDArray[np.bool_]:
        """Return a boolean pixel mask for one slot."""
        if slot_index < 0 or slot_index >= self.slot_count:
            raise IndexError(
                f"slot_index={slot_index} is out of range for {self.slot_count} slots."
            )
        return self.slot_map == slot_index

    def render_slot_preview(
        self,
        slot_index: int,
        *,
        inactive_opacity: float = 0.18,
    ) -> RGBImage:
        """Return a preview image with one slot emphasized."""
        if not 0.0 <= inactive_opacity <= 1.0:
            raise ValueError("inactive_opacity must be between 0.0 and 1.0.")

        slot_mask = self.mask_for_slot(slot_index)
        preview = np.rint(self.preview_image.astype(np.float32) * inactive_opacity)
        highlighted = preview.astype(np.uint8)
        highlighted[slot_mask] = self.preview_image[slot_mask]
        return highlighted


@dataclass(frozen=True)
class CompositeResult:
    """CompositeResult is the final output plus traceable metadata."""

    image: RGBImage
    plan: TimeslicePlan
    used_frame_indices: list[int]
