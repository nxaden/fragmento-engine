from __future__ import annotations

from pathlib import Path

from fragmento_engine.application.services import (
    RenderRequest,
    RenderResponse,
    RenderTimesliceService,
)
from fragmento_engine.domain.models import RGBImage, TimesliceSpec
from fragmento_engine.infrastructure.image_loader import PILImageSequenceLoader
from fragmento_engine.infrastructure.image_writer import PILImageWriter
from fragmento_engine.shared.types import ResizeMode


def create_render_service() -> RenderTimesliceService:
    """Create the default render service with production infrastructure."""
    return RenderTimesliceService(
        sequence_loader=PILImageSequenceLoader(),
        image_writer=PILImageWriter(),
    )


def render_images(
    images: list[RGBImage],
    spec: TimesliceSpec | None = None,
):
    """Render a timeslice directly from in-memory images.

    This is the simplest API for callers that already have images loaded.
    """
    from fragmento_engine.domain.compositor import build_timeslice

    if spec is None:
        spec = TimesliceSpec()

    return build_timeslice(images=images, spec=spec)


def render_folder(
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
) -> RenderResponse:
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
