from __future__ import annotations

import secrets
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Protocol, Sequence

from pytimeslice.domain.compositor import build_timeslice
from pytimeslice.domain.models import (
    CompositeResult,
    RGBImage,
    TimesliceSpec,
    validate_slice_effects,
)
from pytimeslice.shared.types import ResizeMode


class ImageSequenceLoader(Protocol):
    """Application layer contract for loading an ordered image sequence."""

    def get_image_paths(self, folder: Path) -> list[Path]:
        """Return the ordered list of image paths contained in `folder`.

        Args:
            folder: Directory containing the source image sequence.

        Returns:
            A list of image paths in processing order.

        Raises:
            OSError: Implementations may raise an OS-level error if the folder
                cannot be read.
        """
        ...

    def load_images(
        self,
        paths: Sequence[Path],
        resize_mode: ResizeMode = "crop",
    ) -> list[RGBImage]:
        """Load the given image paths into normalized RGB arrays.

        Args:
            paths: Ordered source image paths to load.
            resize_mode: Strategy for handling images whose dimensions do not
                match the base frame size.

        Returns:
            A list of RGB images as numpy arrays.

        Raises:
            ValueError: If the input sequence is invalid.
            OSError: If image files cannot be opened or decoded.
        """
        ...


class ImageWriter(Protocol):
    """Application-layer contract for persisting rendered images.

    Concrete implementations decide how and where the image is written,
    such as saving to local disk with PIL or using another backend.
    """

    def save(self, image: RGBImage, output_file: Path) -> None:
        """Persist an RGB image to the given output path.

        Args:
            image: The rendered RGB image to save.
            output_file: Destination path for the saved file.

        Raises:
            OSError: If the file cannot be written.
        """
        ...

    def save_gif(
        self,
        images: Sequence[RGBImage],
        output_file: Path,
        *,
        duration_ms: int = 250,
    ) -> None:
        """Persist multiple RGB images as an animated GIF.

        Args:
            images: Ordered RGB frames to encode.
            output_file: Destination path for the animated GIF.
            duration_ms: Per-frame duration in milliseconds.

        Raises:
            OSError: If the file cannot be written.
        """
        ...


@dataclass(frozen=True)
class RenderRequest:
    """Input payload for a timeslice render workflow.

    Attributes:
        input_folder: Directory containing the ordered source image sequence.
        spec: Domain-level render specification describing how the timeslice
            should be built.
        resize_mode: Strategy for reconciling dimension mismatches across
            source images before rendering.
    """

    input_folder: Path
    spec: TimesliceSpec
    resize_mode: ResizeMode = "crop"


@dataclass(frozen=True)
class RenderResponse:
    """Output payload for a completed render workflow.

    Attributes:
        result: The final composite result returned by the domain layer.
        input_paths: The ordered source image paths used during rendering.
        output_file: Saved output location when the workflow persisted a file.
    """

    result: CompositeResult
    input_paths: list[Path]
    output_file: Path | None = None


@dataclass(frozen=True)
class ProgressionGifRenderResponse:
    """Output payload for a progression GIF render workflow.

    Attributes:
        peak_result: The highest-slice-count render generated for the GIF.
        last_emitted_result: The final frame emitted into the GIF sequence.
        input_paths: The ordered source image paths used during rendering.
        output_file: Saved GIF location.
        base_slice_counts: The forward slice counts rendered before any
            smooth-loop expansion.
        emitted_slice_counts: The actual slice-count order encoded into the
            GIF, including any smooth-loop walk-back frames.
    """

    peak_result: CompositeResult
    last_emitted_result: CompositeResult
    input_paths: list[Path]
    output_file: Path
    base_slice_counts: list[int]
    emitted_slice_counts: list[int]


def _default_output_file(
    input_folder: Path,
    *,
    suffix: str,
    label: str,
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    token = secrets.token_hex(4)
    filename = f"{stamp}-{token}-{label}{suffix}"
    return input_folder.parent / "out" / filename


def _resolve_output_file(
    input_folder: Path,
    output_file: Path | None,
    *,
    suffix: str,
    label: str,
    require_suffix: bool = False,
) -> Path:
    if output_file is None:
        return _default_output_file(
            input_folder,
            suffix=suffix,
            label=label,
        )

    if output_file.suffix == "":
        return output_file.with_suffix(suffix)

    if require_suffix and output_file.suffix.lower() != suffix:
        raise ValueError(f"Output file must use the {suffix} extension.")

    return output_file


def _progression_slice_counts(
    *,
    num_images: int,
    span: int,
) -> list[int]:
    if num_images < 1:
        raise ValueError("num_images must be at least 1.")

    counts: list[int] = []
    count = 1

    while count <= num_images and count <= span:
        counts.append(count)
        count *= 2

    if count <= span:
        counts.append(count)

    if not counts:
        counts.append(1)

    return counts


def _smooth_loop_slice_counts(slice_counts: Sequence[int]) -> list[int]:
    counts = list(slice_counts)
    if len(counts) < 3:
        return counts
    return counts + counts[-2:0:-1]


class RenderTimesliceService:
    """Application service for rendering a timeslice from an image folder.

    This service coordinates the render workflow:
    1. validate the input folder
    2. discover source image paths
    3. load the images through a sequence loader
    4. invoke the domain compositor with a `TimesliceSpec`
    5. optionally persist the rendered image through an image writer
    """

    def __init__(
        self,
        sequence_loader: ImageSequenceLoader,
        image_writer: ImageWriter | None = None,
    ) -> None:
        """Initialize the render service.

        Args:
            sequence_loader: Adapter responsible for discovering and loading
                source images.
            image_writer: Optional adapter for saving rendered output files.
                Required only when `render_to_file` is used.
        """
        self._sequence_loader = sequence_loader
        self._image_writer = image_writer

    def _validate_request(self, request: RenderRequest) -> None:
        if request.spec.effects is not None:
            validate_slice_effects(request.spec.effects)

    def _load_paths_and_images(
        self,
        request: RenderRequest,
    ) -> tuple[list[Path], list[RGBImage]]:
        if not request.input_folder.exists():
            raise ValueError(f"Input folder does not exist: {request.input_folder}")
        if not request.input_folder.is_dir():
            raise ValueError(f"Input path is not a directory: {request.input_folder}")

        self._validate_request(request)

        paths = self._sequence_loader.get_image_paths(request.input_folder)
        if not paths:
            raise ValueError("No supported image files found.")

        images = self._sequence_loader.load_images(
            paths,
            resize_mode=request.resize_mode,
        )
        return paths, images

    def render(self, request: RenderRequest) -> RenderResponse:
        """Render a timeslice composite from the requested input folder.

        Args:
            request: Structured render input containing the source folder,
                render specification, and resize behavior.

        Returns:
            A `RenderResponse` containing the composite result and the ordered
            source image paths used for rendering.

        Raises:
            ValueError: If the input folder is missing, is not a directory,
                or contains no supported image files.
            OSError: If image loading fails in the configured loader.
        """
        paths, images = self._load_paths_and_images(request)

        result = build_timeslice(
            images=images,
            spec=request.spec,
        )

        return RenderResponse(
            result=result,
            input_paths=paths,
        )

    def render_to_file(
        self,
        request: RenderRequest,
        output_file: Path | None = None,
    ) -> RenderResponse:
        """Render a timeslice composite and save the image to disk.

        Args:
            request: Structured render input containing the source folder,
                render specification, and resize behavior.
            output_file: Destination path for the saved composite image.

        Returns:
            A `RenderResponse` containing the composite result and the ordered
            source image paths used for rendering.

        Raises:
            ValueError: If no image writer was configured for this service.
            OSError: If saving the rendered image fails.
        """
        if self._image_writer is None:
            raise ValueError("No image writer configured.")

        response = self.render(request)
        resolved_output = _resolve_output_file(
            request.input_folder,
            output_file,
            suffix=".png",
            label="timeslice",
        )
        self._image_writer.save(response.result.image, resolved_output)
        return RenderResponse(
            result=response.result,
            input_paths=response.input_paths,
            output_file=resolved_output,
        )

    def render_progression_gif_to_file(
        self,
        request: RenderRequest,
        output_file: Path | None = None,
        *,
        duration_ms: int = 250,
        smooth_loop: bool = False,
    ) -> ProgressionGifRenderResponse:
        """Render a power-of-two slice progression and save it as an animated GIF."""
        if self._image_writer is None:
            raise ValueError("No image writer configured.")
        if duration_ms <= 0:
            raise ValueError("duration_ms must be greater than 0.")

        paths, images = self._load_paths_and_images(request)
        height, width, _ = images[0].shape
        span = width if request.spec.orientation == "vertical" else height
        base_slice_counts = _progression_slice_counts(
            num_images=len(images),
            span=span,
        )
        emitted_slice_counts = (
            _smooth_loop_slice_counts(base_slice_counts)
            if smooth_loop
            else base_slice_counts
        )

        peak_results = [
            build_timeslice(
                images=images,
                spec=replace(request.spec, num_slices=slice_count),
            )
            for slice_count in base_slice_counts
        ]
        results_by_count = {
            slice_count: result
            for slice_count, result in zip(base_slice_counts, peak_results)
        }
        frames = [
            results_by_count[slice_count].image for slice_count in emitted_slice_counts
        ]
        resolved_output = _resolve_output_file(
            request.input_folder,
            output_file,
            suffix=".gif",
            label="progression",
            require_suffix=True,
        )
        self._image_writer.save_gif(
            frames,
            resolved_output,
            duration_ms=duration_ms,
        )
        return ProgressionGifRenderResponse(
            peak_result=peak_results[-1],
            last_emitted_result=results_by_count[emitted_slice_counts[-1]],
            input_paths=paths,
            output_file=resolved_output,
            base_slice_counts=base_slice_counts,
            emitted_slice_counts=emitted_slice_counts,
        )
