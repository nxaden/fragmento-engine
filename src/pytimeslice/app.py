from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

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
    LayoutBounds,
    LayoutDescription,
    LayoutSlot,
    RGBImage,
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
    preview_images = _slot_preview_images(
        slot_count=slot_count,
        width=width,
        height=height,
    )
    preview = apply_timeslice_plan(images=preview_images, plan=plan)
    return LayoutDescription(
        spec=spec,
        plan=plan,
        width=width,
        height=height,
        slot_count=slot_count,
        slot_map=slot_map,
        preview_image=preview.image,
        slots=_describe_slots(slot_map, slot_count=slot_count),
    )


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
