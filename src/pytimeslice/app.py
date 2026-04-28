from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path
from typing import cast

import numpy as np
from PIL import Image

from pytimeslice.application.services import (
    AnimationFormat,
    AnimationMode,
    AnimationRenderResponse,
    ManualTimesliceCanvas,
    ProgressionGifRenderResponse,
    ProgressionVideoRenderResponse,
    RandomGifRenderResponse,
    RandomVideoRenderResponse,
    RenderRequest,
    RenderResponse,
    RenderTimesliceService,
)
from pytimeslice.domain.compositor import apply_timeslice_plan
from pytimeslice.domain.models import (
    BorderColorMode,
    BoundaryCurve,
    LayoutBounds,
    LayoutDescription,
    LayoutMode,
    LayoutSlot,
    Orientation,
    RGBImage,
    SliceBand,
    SliceEffects,
    TimeslicePlan,
    TimesliceSpec,
)
from pytimeslice.domain.planner import build_layout_plan, build_slot_map
from pytimeslice.infrastructure.image_loader import (
    PILImageSequenceLoader,
    load_image_to_size,
    normalize_rgb_image,
)
from pytimeslice.infrastructure.image_writer import PILImageWriter
from pytimeslice.shared.types import ResizeMode

DEFAULT_CANVAS_WIDTH = 3840
DEFAULT_CANVAS_HEIGHT = 2160
LAYOUT_JSON_VERSION = 1


def create_render_service() -> RenderTimesliceService:
    """Create the default render service with production infrastructure."""
    return RenderTimesliceService(
        sequence_loader=PILImageSequenceLoader(),
        image_writer=PILImageWriter(),
    )


def _manual_slot_count(spec: TimesliceSpec) -> int:
    if spec.layout == "random":
        raise ValueError(
            "Manual slot assignment is not currently supported for layout='random'."
        )
    if spec.reverse_time:
        raise ValueError(
            "Manual slot assignment does not support reverse_time; provide slot "
            "images in the exact order you want rendered."
        )
    if spec.num_slices is None:
        raise ValueError(
            "Manual slot assignment requires spec.num_slices to be explicitly set."
        )
    return spec.num_slices


def _empty_rgb_image(*, width: int, height: int) -> RGBImage:
    return np.zeros((height, width, 3), dtype=np.uint8)


def _preview_color(slot_index: int) -> tuple[int, int, int]:
    return (
        48 + ((slot_index * 73) % 176),
        48 + ((slot_index * 131) % 176),
        48 + ((slot_index * 47) % 176),
    )


def _solid_color_image(
    color: tuple[int, int, int],
    *,
    width: int,
    height: int,
) -> RGBImage:
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[:, :, 0] = color[0]
    image[:, :, 1] = color[1]
    image[:, :, 2] = color[2]
    return image


def _slot_preview_images(
    *,
    slot_count: int,
    width: int,
    height: int,
) -> list[RGBImage]:
    return [
        _solid_color_image(_preview_color(slot_index), width=width, height=height)
        for slot_index in range(slot_count)
    ]


def _describe_slots(slot_map: np.ndarray, *, slot_count: int) -> list[LayoutSlot]:
    slots: list[LayoutSlot] = []
    for slot_index in range(slot_count):
        row_indices, col_indices = np.nonzero(slot_map == slot_index)
        if row_indices.size == 0 or col_indices.size == 0:
            raise ValueError(f"slot_index={slot_index} does not occupy any pixels.")
        slots.append(
            LayoutSlot(
                index=slot_index,
                bounds=LayoutBounds(
                    left=int(col_indices.min()),
                    top=int(row_indices.min()),
                    right=int(col_indices.max()) + 1,
                    bottom=int(row_indices.max()) + 1,
                ),
                pixel_count=int(row_indices.size),
            )
        )
    return slots


def _render_layout_preview_image(
    *,
    plan: TimeslicePlan,
    slot_count: int,
    width: int,
    height: int,
) -> RGBImage:
    preview_images = _slot_preview_images(
        slot_count=slot_count,
        width=width,
        height=height,
    )
    preview = apply_timeslice_plan(images=preview_images, plan=plan)
    return preview.image


def describe_layout(
    spec: TimesliceSpec,
    *,
    width: int = DEFAULT_CANVAS_WIDTH,
    height: int = DEFAULT_CANVAS_HEIGHT,
) -> LayoutDescription:
    """Describe a layout for client-driven preview and assignment workflows."""
    plan = build_layout_plan(height=height, width=width, spec=spec)
    slot_map = build_slot_map(height=height, width=width, plan=plan)
    slot_count = (
        len(plan.bands)
        if plan.layout == "bands"
        else len(plan.slice_frame_indices or [])
    )
    return LayoutDescription(
        spec=spec,
        plan=plan,
        width=width,
        height=height,
        slot_count=slot_count,
        slot_map=slot_map,
        preview_image=_render_layout_preview_image(
            plan=plan,
            slot_count=slot_count,
            width=width,
            height=height,
        ),
        slots=_describe_slots(slot_map, slot_count=slot_count),
    )


def _as_json_mapping(payload: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"Serialized {field} must be a JSON object.")
    return payload


def _as_json_list(payload: object, *, field: str) -> list[object]:
    if not isinstance(payload, list):
        raise ValueError(f"Serialized {field} must be a JSON array.")
    return payload


def _as_json_int(payload: object, *, field: str) -> int:
    if isinstance(payload, bool) or not isinstance(payload, int):
        raise ValueError(f"Serialized {field} must be an integer.")
    return payload


def _as_json_float(payload: object, *, field: str) -> float:
    if isinstance(payload, bool) or not isinstance(payload, (int, float)):
        raise ValueError(f"Serialized {field} must be numeric.")
    return float(payload)


def _as_json_str(payload: object, *, field: str) -> str:
    if not isinstance(payload, str):
        raise ValueError(f"Serialized {field} must be a string.")
    return payload


def _as_json_bool(payload: object, *, field: str) -> bool:
    if not isinstance(payload, bool):
        raise ValueError(f"Serialized {field} must be a boolean.")
    return payload


def _serialize_slice_effects(
    effects: SliceEffects | None,
) -> dict[str, object] | None:
    if effects is None:
        return None
    return {
        "border_width": effects.border_width,
        "border_color": list(effects.border_color),
        "border_opacity": effects.border_opacity,
        "border_color_mode": effects.border_color_mode,
        "shadow_width": effects.shadow_width,
        "shadow_opacity": effects.shadow_opacity,
        "highlight_width": effects.highlight_width,
        "highlight_opacity": effects.highlight_opacity,
        "highlight_color": list(effects.highlight_color),
        "feather_width": effects.feather_width,
        "curve": effects.curve,
    }


def _deserialize_slice_effects(
    payload: object,
) -> SliceEffects | None:
    if payload is None:
        return None
    data = _as_json_mapping(payload, field="effects")

    border_color = _as_json_list(
        data.get("border_color", [255, 255, 255]),
        field="border_color",
    )
    highlight_color = _as_json_list(
        data.get("highlight_color", [255, 255, 255]),
        field="highlight_color",
    )
    if len(border_color) != 3:
        raise ValueError("Serialized border_color must contain 3 channels.")
    if len(highlight_color) != 3:
        raise ValueError("Serialized highlight_color must contain 3 channels.")

    return SliceEffects(
        border_width=_as_json_int(data.get("border_width", 0), field="border_width"),
        border_color=cast(
            tuple[int, int, int],
            tuple(
                _as_json_int(channel, field="border_color channel")
                for channel in border_color
            ),
        ),
        border_opacity=_as_json_float(
            data.get("border_opacity", 1.0),
            field="border_opacity",
        ),
        border_color_mode=cast(
            BorderColorMode,
            _as_json_str(
                data.get("border_color_mode", "solid"),
                field="border_color_mode",
            ),
        ),
        shadow_width=_as_json_int(data.get("shadow_width", 0), field="shadow_width"),
        shadow_opacity=_as_json_float(
            data.get("shadow_opacity", 0.35),
            field="shadow_opacity",
        ),
        highlight_width=_as_json_int(
            data.get("highlight_width", 0),
            field="highlight_width",
        ),
        highlight_opacity=_as_json_float(
            data.get("highlight_opacity", 0.35),
            field="highlight_opacity",
        ),
        highlight_color=cast(
            tuple[int, int, int],
            tuple(
                _as_json_int(channel, field="highlight_color channel")
                for channel in highlight_color
            ),
        ),
        feather_width=_as_json_int(
            data.get("feather_width", 0),
            field="feather_width",
        ),
        curve=cast(
            BoundaryCurve,
            _as_json_str(data.get("curve", "linear"), field="curve"),
        ),
    )


def _encode_slot_map(slot_map: np.ndarray) -> dict[str, object]:
    flat = slot_map.reshape(-1)
    runs: list[list[int]] = []
    if flat.size > 0:
        current_value = int(flat[0])
        count = 1
        for value in flat[1:]:
            int_value = int(value)
            if int_value == current_value:
                count += 1
            else:
                runs.append([current_value, count])
                current_value = int_value
                count = 1
        runs.append([current_value, count])

    return {
        "encoding": "rle-int-v1",
        "shape": [int(slot_map.shape[0]), int(slot_map.shape[1])],
        "runs": runs,
    }


def _decode_slot_map(payload: object) -> np.ndarray:
    data = _as_json_mapping(payload, field="slot_map")
    if data.get("encoding") != "rle-int-v1":
        raise ValueError("Unsupported slot_map encoding.")

    raw_shape = _as_json_list(data.get("shape"), field="slot_map shape")
    raw_runs = _as_json_list(data.get("runs"), field="slot_map runs")
    if len(raw_shape) != 2:
        raise ValueError("Serialized slot_map shape must contain 2 dimensions.")

    height = _as_json_int(raw_shape[0], field="slot_map height")
    width = _as_json_int(raw_shape[1], field="slot_map width")
    flat = np.empty(height * width, dtype=np.int_)
    offset = 0
    for run in raw_runs:
        decoded_run = _as_json_list(run, field="slot_map run")
        if len(decoded_run) != 2:
            raise ValueError("Each slot_map run must contain a value and count.")
        value = _as_json_int(decoded_run[0], field="slot_map run value")
        count = _as_json_int(decoded_run[1], field="slot_map run count")
        if count < 1:
            raise ValueError("slot_map run counts must be greater than 0.")
        next_offset = offset + count
        if next_offset > flat.size:
            raise ValueError("Serialized slot_map runs exceed the declared shape.")
        flat[offset:next_offset] = value
        offset = next_offset

    if offset != flat.size:
        raise ValueError("Serialized slot_map runs do not fill the declared shape.")

    return flat.reshape((height, width))


def _encode_preview_image(image: RGBImage) -> dict[str, object]:
    buffer = BytesIO()
    Image.fromarray(image, mode="RGB").save(buffer, format="PNG")
    return {
        "encoding": "png-base64-v1",
        "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
    }


def _decode_preview_image(
    payload: object,
    *,
    width: int,
    height: int,
) -> RGBImage:
    data = _as_json_mapping(payload, field="preview_image")
    if data.get("encoding") != "png-base64-v1":
        raise ValueError("Unsupported preview_image encoding.")

    raw_data = _as_json_str(data.get("data"), field="preview_image data")
    decoded = base64.b64decode(raw_data.encode("ascii"))
    with Image.open(BytesIO(decoded)) as opened:
        image = np.array(opened.convert("RGB"), dtype=np.uint8)

    if image.shape != (height, width, 3):
        raise ValueError(
            "Serialized preview_image dimensions do not match the layout size."
        )
    return image


def _serialize_plan(plan: TimeslicePlan) -> dict[str, object]:
    return {
        "layout": plan.layout,
        "orientation": plan.orientation,
        "bands": [
            {
                "frame_index": band.frame_index,
                "start": band.start,
                "end": band.end,
            }
            for band in plan.bands
        ],
        "slice_frame_indices": list(plan.slice_frame_indices)
        if plan.slice_frame_indices is not None
        else None,
    }


def _deserialize_plan(
    payload: object,
    *,
    slot_map: np.ndarray,
) -> TimeslicePlan:
    data = _as_json_mapping(payload, field="plan")

    layout = cast(LayoutMode, _as_json_str(data.get("layout", "bands"), field="layout"))
    orientation = data.get("orientation")
    raw_bands = data.get("bands", [])
    raw_slice_frame_indices = data.get("slice_frame_indices")

    if layout == "bands":
        band_payloads = _as_json_list(raw_bands, field="plan bands")
        return TimeslicePlan(
            layout="bands",
            orientation=cast(
                Orientation | None,
                None
                if orientation is None
                else _as_json_str(orientation, field="orientation"),
            ),
            bands=[
                SliceBand(
                    frame_index=_as_json_int(
                        _as_json_mapping(band, field="band").get("frame_index"),
                        field="band frame_index",
                    ),
                    start=_as_json_int(
                        _as_json_mapping(band, field="band").get("start"),
                        field="band start",
                    ),
                    end=_as_json_int(
                        _as_json_mapping(band, field="band").get("end"),
                        field="band end",
                    ),
                )
                for band in band_payloads
            ],
        )

    if raw_slice_frame_indices is None:
        raise ValueError("Mask-based serialized plans require slice_frame_indices.")
    slice_frame_indices = _as_json_list(
        raw_slice_frame_indices,
        field="slice_frame_indices",
    )

    return TimeslicePlan(
        layout=layout,
        slice_map=slot_map.copy(),
        slice_frame_indices=[
            _as_json_int(index, field="slice_frame_indices item")
            for index in slice_frame_indices
        ],
    )


def _serialize_spec(spec: TimesliceSpec) -> dict[str, object]:
    return {
        "orientation": spec.orientation,
        "layout": spec.layout,
        "num_slices": spec.num_slices,
        "num_blocks": spec.num_blocks,
        "reverse_time": spec.reverse_time,
        "random_seed": spec.random_seed,
        "effects": _serialize_slice_effects(spec.effects),
    }


def _slot_map_to_mask_layout_mask(
    slot_map: np.ndarray,
    *,
    slot_count: int,
) -> np.ndarray:
    flat_slot_map = slot_map.reshape(-1)
    rank_slots = (
        np.arange(flat_slot_map.size, dtype=np.int_) * slot_count
    ) // flat_slot_map.size
    replay_mask = np.empty(flat_slot_map.size, dtype=np.float64)

    for slot_index in range(slot_count):
        pixel_positions = np.flatnonzero(flat_slot_map == slot_index)
        rank_positions = np.flatnonzero(rank_slots == slot_index)
        if pixel_positions.size != rank_positions.size:
            raise ValueError(
                "Serialized slot_map cannot be converted back into a mask layout "
                "because its slot counts are not compatible with layout='mask'."
            )
        replay_mask[pixel_positions] = rank_positions.astype(np.float64)

    return replay_mask.reshape(slot_map.shape)


def _deserialize_spec(
    payload: object,
    *,
    slot_map: np.ndarray,
    slot_count: int,
) -> TimesliceSpec:
    data = _as_json_mapping(payload, field="spec")
    layout = cast(LayoutMode, _as_json_str(data.get("layout", "bands"), field="layout"))
    orientation = cast(
        Orientation,
        _as_json_str(data.get("orientation", "vertical"), field="orientation"),
    )
    reverse_time = _as_json_bool(
        data.get("reverse_time", False),
        field="reverse_time",
    )
    effects = _deserialize_slice_effects(data.get("effects"))
    num_slices_payload = data.get("num_slices")
    num_blocks_payload = data.get("num_blocks")
    random_seed_payload = data.get("random_seed")
    num_slices = (
        _as_json_int(num_slices_payload, field="num_slices")
        if num_slices_payload is not None
        else None
    )
    num_blocks = (
        _as_json_int(num_blocks_payload, field="num_blocks")
        if num_blocks_payload is not None
        else None
    )
    random_seed = (
        _as_json_int(random_seed_payload, field="random_seed")
        if random_seed_payload is not None
        else None
    )

    if layout == "mask":
        return TimesliceSpec(
            orientation=orientation,
            layout=layout,
            num_slices=num_slices if num_slices is not None else slot_count,
            reverse_time=reverse_time,
            random_seed=random_seed,
            effects=effects,
            layout_mask=_slot_map_to_mask_layout_mask(
                slot_map,
                slot_count=slot_count,
            ),
        )
    if layout == "random":
        return TimesliceSpec(
            orientation=orientation,
            layout=layout,
            num_blocks=num_blocks if num_blocks is not None else slot_count,
            reverse_time=reverse_time,
            random_seed=random_seed,
            effects=effects,
        )
    return TimesliceSpec(
        orientation=orientation,
        layout=layout,
        num_slices=num_slices if num_slices is not None else slot_count,
        reverse_time=reverse_time,
        random_seed=random_seed,
        effects=effects,
    )


def serialize_layout(
    layout_description: LayoutDescription,
    *,
    include_preview_image: bool = True,
) -> dict[str, object]:
    """Serialize layout metadata into a JSON-safe payload."""
    return {
        "version": LAYOUT_JSON_VERSION,
        "width": layout_description.width,
        "height": layout_description.height,
        "slot_count": layout_description.slot_count,
        "spec": _serialize_spec(layout_description.spec),
        "plan": _serialize_plan(layout_description.plan),
        "slot_map": _encode_slot_map(layout_description.slot_map),
        "slots": [
            {
                "index": slot.index,
                "bounds": {
                    "left": slot.bounds.left,
                    "top": slot.bounds.top,
                    "right": slot.bounds.right,
                    "bottom": slot.bounds.bottom,
                },
                "pixel_count": slot.pixel_count,
            }
            for slot in layout_description.slots
        ],
        "preview_image": _encode_preview_image(layout_description.preview_image)
        if include_preview_image
        else None,
    }


def deserialize_layout(payload: Mapping[str, object]) -> LayoutDescription:
    """Deserialize a JSON-safe layout payload back into a layout description."""
    version = _as_json_int(payload.get("version", 0), field="version")
    if version != LAYOUT_JSON_VERSION:
        raise ValueError(
            f"Unsupported layout JSON version {version}; expected {LAYOUT_JSON_VERSION}."
        )

    width = _as_json_int(payload.get("width", 0), field="width")
    height = _as_json_int(payload.get("height", 0), field="height")
    slot_count = _as_json_int(payload.get("slot_count", 0), field="slot_count")
    if width < 1 or height < 1:
        raise ValueError("Serialized layout dimensions must be greater than 0.")
    if slot_count < 1:
        raise ValueError("Serialized slot_count must be greater than 0.")

    slot_map = _decode_slot_map(payload.get("slot_map"))
    if slot_map.shape != (height, width):
        raise ValueError("Serialized slot_map shape does not match width and height.")

    spec = _deserialize_spec(
        payload.get("spec"),
        slot_map=slot_map,
        slot_count=slot_count,
    )
    plan = _deserialize_plan(payload.get("plan"), slot_map=slot_map)
    derived_slot_map = build_slot_map(height=height, width=width, plan=plan)
    if not np.array_equal(derived_slot_map, slot_map):
        raise ValueError("Serialized plan does not match the serialized slot_map.")

    derived_slot_count = (
        len(plan.bands)
        if plan.layout == "bands"
        else len(plan.slice_frame_indices or [])
    )
    if derived_slot_count != slot_count:
        raise ValueError("Serialized slot_count does not match the serialized plan.")

    raw_preview_image = payload.get("preview_image")
    preview_image = (
        _render_layout_preview_image(
            plan=plan,
            slot_count=slot_count,
            width=width,
            height=height,
        )
        if raw_preview_image is None
        else _decode_preview_image(raw_preview_image, width=width, height=height)
    )

    return LayoutDescription(
        spec=spec,
        plan=plan,
        width=width,
        height=height,
        slot_count=slot_count,
        slot_map=slot_map,
        preview_image=preview_image,
        slots=_describe_slots(slot_map, slot_count=slot_count),
    )


def export_layout_json(
    layout_description: LayoutDescription,
    output_file: Path | str,
    *,
    include_preview_image: bool = True,
    indent: int = 2,
) -> Path:
    """Write a serialized layout payload to a JSON file."""
    output_path = Path(output_file)
    if output_path.suffix == "":
        output_path = output_path.with_suffix(".json")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = serialize_layout(
        layout_description,
        include_preview_image=include_preview_image,
    )
    output_path.write_text(
        json.dumps(payload, indent=indent, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def import_layout_json(input_file: Path | str) -> LayoutDescription:
    """Load a serialized layout payload from a JSON file."""
    raw_payload = json.loads(Path(input_file).read_text(encoding="utf-8"))
    if not isinstance(raw_payload, dict):
        raise ValueError("Serialized layout files must contain a JSON object.")
    return deserialize_layout(raw_payload)


def _materialize_manual_canvas(
    *,
    layout_description: LayoutDescription,
    slot_images: Sequence[RGBImage | None],
) -> ManualTimesliceCanvas:
    placeholder = _empty_rgb_image(
        width=layout_description.width,
        height=layout_description.height,
    )
    filled_slot_indices = [
        slot_index
        for slot_index, slot_image in enumerate(slot_images)
        if slot_image is not None
    ]
    render_images = [
        slot_image if slot_image is not None else placeholder
        for slot_image in slot_images
    ]
    composite = apply_timeslice_plan(
        images=render_images,
        plan=layout_description.plan,
        effects=layout_description.spec.effects,
    )
    return ManualTimesliceCanvas(
        layout_description=layout_description,
        spec=layout_description.spec,
        plan=layout_description.plan,
        width=layout_description.width,
        height=layout_description.height,
        slot_count=len(slot_images),
        slot_images=list(slot_images),
        image=composite.image,
        filled_slot_indices=filled_slot_indices,
    )


def _slot_images_from_arrays(
    images: Sequence[RGBImage],
    *,
    width: int,
    height: int,
    resize_mode: ResizeMode,
) -> list[RGBImage]:
    return [
        normalize_rgb_image(
            image,
            target_w=width,
            target_h=height,
            resize_mode=resize_mode,
        )
        for image in images
    ]


def _slot_images_from_paths(
    paths: Sequence[Path | str],
    *,
    width: int,
    height: int,
    resize_mode: ResizeMode,
) -> list[RGBImage]:
    return [
        load_image_to_size(
            path,
            target_w=width,
            target_h=height,
            resize_mode=resize_mode,
        )
        for path in paths
    ]


def create_manual_timeslice(
    spec: TimesliceSpec,
    *,
    width: int = DEFAULT_CANVAS_WIDTH,
    height: int = DEFAULT_CANVAS_HEIGHT,
) -> ManualTimesliceCanvas:
    """Create an empty manual timeslice canvas for incremental slot assignment.

    Manual assignment requires `spec.num_slices` because the library needs a
    fixed number of addressable slots up front. Empty slots render as black in
    the preview image until the caller assigns content.
    """
    _manual_slot_count(spec)
    layout_description = describe_layout(spec, width=width, height=height)
    return _materialize_manual_canvas(
        layout_description=layout_description,
        slot_images=[None] * layout_description.slot_count,
    )


def assign_image_to_slot(
    canvas: ManualTimesliceCanvas,
    slot_index: int,
    image: RGBImage,
    *,
    resize_mode: ResizeMode = "crop",
) -> ManualTimesliceCanvas:
    """Assign one in-memory image to a specific slot in a manual canvas."""
    if slot_index < 0 or slot_index >= canvas.slot_count:
        raise IndexError(
            f"slot_index={slot_index} is out of range for {canvas.slot_count} slots."
        )

    normalized = normalize_rgb_image(
        image,
        target_w=canvas.width,
        target_h=canvas.height,
        resize_mode=resize_mode,
    )
    slot_images = list(canvas.slot_images)
    slot_images[slot_index] = normalized
    return _materialize_manual_canvas(
        layout_description=canvas.layout_description,
        slot_images=slot_images,
    )


def assign_path_to_slot(
    canvas: ManualTimesliceCanvas,
    slot_index: int,
    path: Path | str,
    *,
    resize_mode: ResizeMode = "crop",
) -> ManualTimesliceCanvas:
    """Assign one file-backed image to a specific slot in a manual canvas."""
    image = load_image_to_size(
        path,
        target_w=canvas.width,
        target_h=canvas.height,
        resize_mode=resize_mode,
    )
    return assign_image_to_slot(
        canvas,
        slot_index,
        image,
        resize_mode=resize_mode,
    )


def render_assigned_images(
    images: Sequence[RGBImage],
    *,
    spec: TimesliceSpec,
    width: int = DEFAULT_CANVAS_WIDTH,
    height: int = DEFAULT_CANVAS_HEIGHT,
    resize_mode: ResizeMode = "crop",
) -> ManualTimesliceCanvas:
    """Render a manual timeslice from an explicit per-slot image list."""
    canvas = create_manual_timeslice(spec, width=width, height=height)
    if len(images) != canvas.slot_count:
        raise ValueError(
            f"Expected {canvas.slot_count} images for manual assignment, "
            f"received {len(images)}."
        )

    return _materialize_manual_canvas(
        layout_description=canvas.layout_description,
        slot_images=_slot_images_from_arrays(
            images,
            width=canvas.width,
            height=canvas.height,
            resize_mode=resize_mode,
        ),
    )


def render_assigned_paths(
    paths: Sequence[Path | str],
    *,
    spec: TimesliceSpec,
    width: int = DEFAULT_CANVAS_WIDTH,
    height: int = DEFAULT_CANVAS_HEIGHT,
    resize_mode: ResizeMode = "crop",
) -> ManualTimesliceCanvas:
    """Render a manual timeslice from an explicit per-slot file path list."""
    canvas = create_manual_timeslice(spec, width=width, height=height)
    if len(paths) != canvas.slot_count:
        raise ValueError(
            f"Expected {canvas.slot_count} paths for manual assignment, "
            f"received {len(paths)}."
        )

    return _materialize_manual_canvas(
        layout_description=canvas.layout_description,
        slot_images=_slot_images_from_paths(
            paths,
            width=canvas.width,
            height=canvas.height,
            resize_mode=resize_mode,
        ),
    )


def render_images(
    images: list[RGBImage],
    spec: TimesliceSpec | None = None,
):
    """Render a timeslice directly from in-memory images.

    This is the simplest API for callers that already have images loaded.
    """
    from pytimeslice.domain.compositor import build_timeslice

    if spec is None:
        spec = TimesliceSpec()

    return build_timeslice(images=images, spec=spec)


def render_folder(
    input_folder: Path,
    spec: TimesliceSpec | None = None,
    resize_mode: ResizeMode = "crop",
) -> RenderResponse:
    """Render a timeslice from a folder without writing an output file."""
    if spec is None:
        spec = TimesliceSpec()

    service = create_render_service()
    request = RenderRequest(
        input_folder=input_folder,
        spec=spec,
        resize_mode=resize_mode,
    )

    return service.render(request=request)


def render_folder_to_file(
    input_folder: Path,
    output_file: Path | None = None,
    spec: TimesliceSpec | None = None,
    resize_mode: ResizeMode = "crop",
) -> RenderResponse:
    """Render a timeslice from a folder and save it to disk.

    If `output_file` is omitted, a timestamped file is written into a sibling
    `out/` directory next to the input folder.
    """
    if spec is None:
        spec = TimesliceSpec()

    service = create_render_service()
    request = RenderRequest(
        input_folder=input_folder,
        spec=spec,
        resize_mode=resize_mode,
    )

    return service.render_to_file(request=request, output_file=output_file)


def render_progression_gif(
    input_folder: Path,
    output_file: Path | None = None,
    spec: TimesliceSpec | None = None,
    resize_mode: ResizeMode = "crop",
    frame_duration_ms: int = 250,
    smooth_loop: bool = False,
) -> ProgressionGifRenderResponse:
    """Render a power-of-two slice progression GIF from a folder of images.

    The progression starts at 1 slice and doubles until the sequence exceeds
    the number of input images, or until the image span prevents further
    doubling. If `output_file` is omitted, a timestamped GIF is written into a
    sibling `out/` directory next to the input folder.
    """
    if spec is None:
        spec = TimesliceSpec()

    service = create_render_service()
    request = RenderRequest(
        input_folder=input_folder,
        spec=spec,
        resize_mode=resize_mode,
    )
    return service.render_progression_gif_to_file(
        request=request,
        output_file=output_file,
        duration_ms=frame_duration_ms,
        smooth_loop=smooth_loop,
    )


def render_animation(
    input_folder: Path,
    output_file: Path | None = None,
    spec: TimesliceSpec | None = None,
    resize_mode: ResizeMode = "crop",
    *,
    mode: AnimationMode = "progression",
    output_format: AnimationFormat = "gif",
    frame_duration_ms: int = 250,
    fps: int = 6,
    loops: int = 1,
    smooth_loop: bool = False,
    frame_count: int = 8,
) -> AnimationRenderResponse:
    """Render a GIF or video animation from a folder of images.

    `mode="progression"` animates slice-count growth for non-random layouts.
    `mode="random"` animates seed changes for `layout="random"`.
    """
    if spec is None:
        spec = TimesliceSpec(layout="random") if mode == "random" else TimesliceSpec()

    service = create_render_service()
    request = RenderRequest(
        input_folder=input_folder,
        spec=spec,
        resize_mode=resize_mode,
    )
    return service.render_animation_to_file(
        request=request,
        output_file=output_file,
        mode=mode,
        output_format=output_format,
        frame_duration_ms=frame_duration_ms,
        fps=fps,
        loops=loops,
        smooth_loop=smooth_loop,
        frame_count=frame_count,
    )


def render_random_gif(
    input_folder: Path,
    output_file: Path | None = None,
    spec: TimesliceSpec | None = None,
    resize_mode: ResizeMode = "crop",
    frame_duration_ms: int = 250,
    frame_count: int = 8,
    smooth_loop: bool = False,
) -> RandomGifRenderResponse:
    """Render a random-layout shuffle GIF from a folder of images.

    The renderer keeps the same random block layout mode but advances the
    effective random seed once per emitted keyframe. If `output_file` is
    omitted, a timestamped GIF is written into a sibling `out/` directory
    next to the input folder.
    """
    if spec is None:
        spec = TimesliceSpec(layout="random")

    service = create_render_service()
    request = RenderRequest(
        input_folder=input_folder,
        spec=spec,
        resize_mode=resize_mode,
    )
    return service.render_random_gif_to_file(
        request=request,
        output_file=output_file,
        duration_ms=frame_duration_ms,
        frame_count=frame_count,
        smooth_loop=smooth_loop,
    )


def render_progression_video(
    input_folder: Path,
    output_file: Path | None = None,
    spec: TimesliceSpec | None = None,
    resize_mode: ResizeMode = "crop",
    fps: int = 6,
    loops: int = 1,
    smooth_loop: bool = False,
) -> ProgressionVideoRenderResponse:
    """Render a power-of-two slice progression video from a folder of images.

    Video export requires `ffmpeg` on `PATH` and supports `.mp4` or `.mov`
    output paths. `loops` repeats the emitted animation sequence in the encoded
    video.
    """
    if spec is None:
        spec = TimesliceSpec()

    service = create_render_service()
    request = RenderRequest(
        input_folder=input_folder,
        spec=spec,
        resize_mode=resize_mode,
    )
    return service.render_progression_video_to_file(
        request=request,
        output_file=output_file,
        fps=fps,
        loops=loops,
        smooth_loop=smooth_loop,
    )


def render_random_video(
    input_folder: Path,
    output_file: Path | None = None,
    spec: TimesliceSpec | None = None,
    resize_mode: ResizeMode = "crop",
    fps: int = 6,
    loops: int = 1,
    frame_count: int = 8,
    smooth_loop: bool = False,
) -> RandomVideoRenderResponse:
    """Render a random-layout shuffle video from a folder of images.

    Video export requires `ffmpeg` on `PATH` and supports `.mp4` or `.mov`
    output paths. `loops` repeats the emitted animation sequence in the encoded
    video.
    """
    if spec is None:
        spec = TimesliceSpec(layout="random")

    service = create_render_service()
    request = RenderRequest(
        input_folder=input_folder,
        spec=spec,
        resize_mode=resize_mode,
    )
    return service.render_random_video_to_file(
        request=request,
        output_file=output_file,
        fps=fps,
        loops=loops,
        frame_count=frame_count,
        smooth_loop=smooth_loop,
    )
