from __future__ import annotations

import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from pytimeslice.domain.compositor import build_timeslice
from pytimeslice.domain.planner import max_supported_slices
from pytimeslice.domain.models import (
    CompositeResult,
    LayoutDescription,
    RGBImage,
    TimeslicePlan,
    TimesliceSpec,
    VideoFrameSelectionSpec,
    select_video_frame_indices,
    validate_timeslice_spec,
    validate_video_frame_selection_spec,
)
from pytimeslice.shared.types import ResizeMode

AnimationMode = Literal["progression", "random"]
AnimationFormat = Literal["gif", "mp4", "mov"]
AnimationValueKind = Literal["slice_count", "seed"]
AnimationProgressStage = Literal[
    "loading_inputs",
    "rendering_frames",
    "encoding_output",
]


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

    def save_video(
        self,
        images: Sequence[RGBImage],
        output_file: Path,
        *,
        fps: int = 6,
    ) -> None:
        """Persist multiple RGB images as a video file.

        Args:
            images: Ordered RGB frames to encode.
            output_file: Destination path for the encoded video.
            fps: Playback rate in frames per second.

        Raises:
            OSError: If the file cannot be written.
        """
        ...


class VideoFrameLoader(Protocol):
    """Application layer contract for sampling RGB frames from a video."""

    def count_frames(self, video_file: Path) -> int:
        """Return the number of decodable frames in the video."""
        ...

    def load_frames(
        self,
        video_file: Path,
        frame_indices: Sequence[int],
        resize_mode: ResizeMode = "crop",
    ) -> list[RGBImage]:
        """Load selected video frames into normalized RGB arrays."""
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
class VideoRenderRequest:
    """Input payload for a timeslice render workflow from a video file."""

    video_file: Path
    spec: TimesliceSpec
    frame_selection: VideoFrameSelectionSpec = VideoFrameSelectionSpec()
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
class VideoRenderResponse:
    """Output payload for a completed video-input render workflow."""

    result: CompositeResult
    video_file: Path
    sampled_frame_indices: list[int]
    total_video_frames: int
    output_file: Path | None = None


@dataclass(frozen=True)
class AnimationRenderResponse:
    """Output payload for a rendered animation export.

    Attributes:
        mode: Animation strategy used to produce the keyframes.
        output_format: Encoded output format.
        value_kind: Whether the animation advanced slice counts or random seeds.
        first_forward_result: The first keyframe rendered before any loop
            expansion.
        last_forward_result: The last keyframe rendered before any loop
            expansion.
        last_emitted_result: The final keyframe emitted into the encoded output.
        input_paths: The ordered source image paths used during rendering.
        output_file: Saved animation location.
        base_values: The forward animation values rendered before smooth-loop or
            repeat expansion.
        emitted_values: The actual animation values encoded into the output.
    """

    mode: AnimationMode
    output_format: AnimationFormat
    value_kind: AnimationValueKind
    first_forward_result: CompositeResult
    last_forward_result: CompositeResult
    last_emitted_result: CompositeResult
    input_paths: list[Path]
    output_file: Path
    base_values: list[int]
    emitted_values: list[int]


@dataclass(frozen=True)
class AnimationRenderProgress:
    """Progress update emitted while rendering an animation export."""

    mode: AnimationMode
    output_format: AnimationFormat
    value_kind: AnimationValueKind
    stage: AnimationProgressStage
    progress: float
    completed_forward_frames: int
    total_forward_frames: int
    emitted_frame_count: int
    current_value: int | None = None


AnimationProgressCallback = Callable[[AnimationRenderProgress], None]


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


@dataclass(frozen=True)
class RandomGifRenderResponse:
    """Output payload for a random-layout GIF render workflow.

    Attributes:
        initial_result: The first random-layout render generated for the GIF.
        last_emitted_result: The final frame emitted into the GIF sequence.
        input_paths: The ordered source image paths used during rendering.
        output_file: Saved GIF location.
        base_seeds: The forward random-seed sequence rendered before any
            smooth-loop expansion.
        emitted_seeds: The actual seed order encoded into the GIF, including
            any smooth-loop walk-back frames.
    """

    initial_result: CompositeResult
    last_emitted_result: CompositeResult
    input_paths: list[Path]
    output_file: Path
    base_seeds: list[int]
    emitted_seeds: list[int]


@dataclass(frozen=True)
class ProgressionVideoRenderResponse:
    """Output payload for a progression video render workflow."""

    peak_result: CompositeResult
    last_emitted_result: CompositeResult
    input_paths: list[Path]
    output_file: Path
    base_slice_counts: list[int]
    emitted_slice_counts: list[int]


@dataclass(frozen=True)
class RandomVideoRenderResponse:
    """Output payload for a random-layout video render workflow."""

    initial_result: CompositeResult
    last_emitted_result: CompositeResult
    input_paths: list[Path]
    output_file: Path
    base_seeds: list[int]
    emitted_seeds: list[int]


@dataclass(frozen=True)
class ManualTimesliceCanvas:
    """Stateful in-memory canvas for manually assigned slice content.

    Attributes:
        layout_description: Pure slot metadata shared with client flows.
        spec: The layout specification that defines the slice geometry.
        plan: Concrete plan for applying slot images to the output image.
        width: Output width in pixels.
        height: Output height in pixels.
        slot_count: Total number of assignable slice slots.
        slot_images: Per-slot normalized images, or `None` for empty slots.
        image: Current composite preview with empty slots rendered as black.
        filled_slot_indices: Sorted slot indices that have been assigned.
    """

    layout_description: LayoutDescription
    spec: TimesliceSpec
    plan: TimeslicePlan
    width: int
    height: int
    slot_count: int
    slot_images: list[RGBImage | None]
    image: RGBImage
    filled_slot_indices: list[int]

    @property
    def is_complete(self) -> bool:
        """Return whether every slot currently has an assigned image."""
        return len(self.filled_slot_indices) == self.slot_count


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


def _resolve_video_output_file(
    video_file: Path,
    output_file: Path | None,
    *,
    suffix: str,
    label: str,
) -> Path:
    if output_file is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        token = secrets.token_hex(4)
        filename = f"{stamp}-{token}-{label}{suffix}"
        return video_file.parent / "out" / filename

    if output_file.suffix == "":
        return output_file.with_suffix(suffix)

    return output_file


def _resolve_animation_output_file(
    input_folder: Path,
    output_file: Path | None,
    *,
    output_format: AnimationFormat,
    label: str,
) -> Path:
    suffix = f".{output_format}"

    if output_file is None:
        return _default_output_file(
            input_folder,
            suffix=suffix,
            label=label,
        )

    if output_file.suffix == "":
        return output_file.with_suffix(suffix)

    if output_file.suffix.lower() != suffix:
        raise ValueError(f"Animation output file must use the {suffix} extension.")

    return output_file


def _output_format_from_output_file(output_file: Path | None) -> AnimationFormat:
    if output_file is None:
        return "mp4"

    if output_file.suffix.lower() == ".mov":
        return "mov"

    return "mp4"


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


def _smooth_loop_values(values: Sequence[int]) -> list[int]:
    smoothed = list(values)
    if len(smoothed) < 3:
        return smoothed
    return smoothed + smoothed[-2:0:-1]


def _repeat_animation_values(values: Sequence[int], loops: int) -> list[int]:
    if loops <= 0:
        raise ValueError("loops must be greater than 0.")
    return list(values) * loops


def _animation_value_kind(mode: AnimationMode) -> AnimationValueKind:
    return "slice_count" if mode == "progression" else "seed"


def _animation_output_label(mode: AnimationMode) -> str:
    return "progression" if mode == "progression" else "random-shuffle"


def _emit_animation_progress(
    progress_callback: AnimationProgressCallback | None,
    *,
    mode: AnimationMode,
    output_format: AnimationFormat,
    value_kind: AnimationValueKind,
    stage: AnimationProgressStage,
    progress: float,
    completed_forward_frames: int,
    total_forward_frames: int,
    emitted_frame_count: int,
    current_value: int | None = None,
) -> None:
    if progress_callback is None:
        return

    clamped_progress = max(0.0, min(1.0, progress))
    progress_callback(
        AnimationRenderProgress(
            mode=mode,
            output_format=output_format,
            value_kind=value_kind,
            stage=stage,
            progress=clamped_progress,
            completed_forward_frames=completed_forward_frames,
            total_forward_frames=total_forward_frames,
            emitted_frame_count=emitted_frame_count,
            current_value=current_value,
        )
    )


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
        video_frame_loader: VideoFrameLoader | None = None,
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
        self._video_frame_loader = video_frame_loader

    def _validate_request(self, request: RenderRequest) -> None:
        validate_timeslice_spec(request.spec)

    def _validate_video_request(self, request: VideoRenderRequest) -> None:
        validate_timeslice_spec(request.spec)
        validate_video_frame_selection_spec(request.frame_selection)

    def _resolve_video_frame_selection(
        self,
        request: VideoRenderRequest,
        *,
        total_frames: int,
    ) -> VideoFrameSelectionSpec:
        if request.frame_selection.target_frame_count is not None:
            return request.frame_selection

        default_count: int | None
        if request.spec.layout == "random":
            default_count = request.spec.num_blocks if request.spec.num_blocks else 4
        else:
            default_count = request.spec.num_slices

        return VideoFrameSelectionSpec(
            target_frame_count=(
                default_count if default_count is not None else min(total_frames, 24)
            ),
            include_last=request.frame_selection.include_last,
        )

    def _load_video_images(
        self,
        request: VideoRenderRequest,
    ) -> tuple[int, list[int], list[RGBImage]]:
        if self._video_frame_loader is None:
            raise ValueError("No video frame loader was configured for this service.")
        if not request.video_file.exists():
            raise ValueError(f"Video file does not exist: {request.video_file}")
        if not request.video_file.is_file():
            raise ValueError(f"Video path is not a file: {request.video_file}")

        self._validate_video_request(request)

        total_frames = self._video_frame_loader.count_frames(request.video_file)
        selection = self._resolve_video_frame_selection(
            request,
            total_frames=total_frames,
        )
        frame_indices = select_video_frame_indices(
            total_frames=total_frames,
            spec=selection,
        )
        images = self._video_frame_loader.load_frames(
            request.video_file,
            frame_indices,
            resize_mode=request.resize_mode,
        )
        return total_frames, frame_indices, images

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

    def render_video(self, request: VideoRenderRequest) -> VideoRenderResponse:
        """Render a timeslice composite from selected frames in a video file."""
        total_frames, frame_indices, images = self._load_video_images(request)
        result = build_timeslice(
            images=images,
            spec=request.spec,
        )

        return VideoRenderResponse(
            result=result,
            video_file=request.video_file,
            sampled_frame_indices=frame_indices,
            total_video_frames=total_frames,
        )

    def render_video_to_file(
        self,
        request: VideoRenderRequest,
        output_file: Path | None = None,
    ) -> VideoRenderResponse:
        """Render a video-input timeslice composite and save it to disk."""
        if self._image_writer is None:
            raise ValueError("No image writer configured for this service.")

        response = self.render_video(request)
        resolved_output = _resolve_video_output_file(
            request.video_file,
            output_file,
            suffix=".png",
            label="timeslice",
        )
        self._image_writer.save(response.result.image, resolved_output)

        return VideoRenderResponse(
            result=response.result,
            video_file=response.video_file,
            sampled_frame_indices=response.sampled_frame_indices,
            total_video_frames=response.total_video_frames,
            output_file=resolved_output,
        )

    def _forward_animation_values(
        self,
        *,
        mode: AnimationMode,
        request: RenderRequest,
        num_images: int,
        span: int,
        frame_count: int,
    ) -> list[int]:
        if mode == "progression":
            if request.spec.layout == "random":
                raise ValueError(
                    "Progression animation is not currently supported for "
                    "layout='random'."
                )
            return _progression_slice_counts(
                num_images=num_images,
                span=span,
            )

        if frame_count <= 0:
            raise ValueError("frame_count must be greater than 0.")
        if request.spec.layout != "random":
            raise ValueError("Random animation requires layout='random'.")

        base_seed = (
            request.spec.random_seed if request.spec.random_seed is not None else 0
        )
        return [base_seed + frame_index for frame_index in range(frame_count)]

    def _validate_animation_request(
        self,
        *,
        mode: AnimationMode,
        request: RenderRequest,
        frame_count: int,
    ) -> None:
        if mode == "progression":
            if request.spec.layout == "random":
                raise ValueError(
                    "Progression animation is not currently supported for "
                    "layout='random'."
                )
            return

        if frame_count <= 0:
            raise ValueError("frame_count must be greater than 0.")
        if request.spec.layout != "random":
            raise ValueError("Random animation requires layout='random'.")

    def _result_for_animation_value(
        self,
        *,
        mode: AnimationMode,
        images: Sequence[RGBImage],
        spec: TimesliceSpec,
        value: int,
    ) -> CompositeResult:
        if mode == "progression":
            return build_timeslice(
                images=images,
                spec=replace(spec, num_slices=value),
            )

        return build_timeslice(
            images=images,
            spec=replace(spec, random_seed=value),
        )

    def render_animation_to_file(
        self,
        request: RenderRequest,
        output_file: Path | None = None,
        *,
        mode: AnimationMode = "progression",
        output_format: AnimationFormat = "gif",
        frame_duration_ms: int = 250,
        fps: int = 6,
        loops: int = 1,
        smooth_loop: bool = False,
        frame_count: int = 8,
        progress_callback: AnimationProgressCallback | None = None,
    ) -> AnimationRenderResponse:
        """Render an animation export and save it to disk."""
        if self._image_writer is None:
            raise ValueError("No image writer configured.")
        if output_format == "gif" and frame_duration_ms <= 0:
            raise ValueError("frame_duration_ms must be greater than 0.")
        if output_format in {"mp4", "mov"} and fps <= 0:
            raise ValueError("fps must be greater than 0.")
        self._validate_animation_request(
            mode=mode,
            request=request,
            frame_count=frame_count,
        )

        paths, images = self._load_paths_and_images(request)
        height, width, _ = images[0].shape
        span = max_supported_slices(height=height, width=width, spec=request.spec)
        base_values = self._forward_animation_values(
            mode=mode,
            request=request,
            num_images=len(images),
            span=span,
            frame_count=frame_count,
        )
        emitted_once = _smooth_loop_values(base_values) if smooth_loop else base_values
        emitted_values = _repeat_animation_values(emitted_once, loops)
        value_kind = _animation_value_kind(mode)

        _emit_animation_progress(
            progress_callback,
            mode=mode,
            output_format=output_format,
            value_kind=value_kind,
            stage="loading_inputs",
            progress=0.08,
            completed_forward_frames=0,
            total_forward_frames=len(base_values),
            emitted_frame_count=len(emitted_values),
        )

        forward_results: list[CompositeResult] = []
        for index, value in enumerate(base_values, start=1):
            result = self._result_for_animation_value(
                mode=mode,
                images=images,
                spec=request.spec,
                value=value,
            )
            forward_results.append(result)
            render_progress = 0.1 + (0.78 * (index / len(base_values)))
            _emit_animation_progress(
                progress_callback,
                mode=mode,
                output_format=output_format,
                value_kind=value_kind,
                stage="rendering_frames",
                progress=render_progress,
                completed_forward_frames=index,
                total_forward_frames=len(base_values),
                emitted_frame_count=len(emitted_values),
                current_value=value,
            )
        results_by_value = {
            value: result for value, result in zip(base_values, forward_results)
        }
        frames = [results_by_value[value].image for value in emitted_values]
        resolved_output = _resolve_animation_output_file(
            request.input_folder,
            output_file,
            output_format=output_format,
            label=_animation_output_label(mode),
        )

        _emit_animation_progress(
            progress_callback,
            mode=mode,
            output_format=output_format,
            value_kind=value_kind,
            stage="encoding_output",
            progress=0.96,
            completed_forward_frames=len(base_values),
            total_forward_frames=len(base_values),
            emitted_frame_count=len(emitted_values),
            current_value=base_values[-1],
        )

        if output_format == "gif":
            self._image_writer.save_gif(
                frames,
                resolved_output,
                duration_ms=frame_duration_ms,
            )
        else:
            self._image_writer.save_video(
                frames,
                resolved_output,
                fps=fps,
            )

        return AnimationRenderResponse(
            mode=mode,
            output_format=output_format,
            value_kind=value_kind,
            first_forward_result=forward_results[0],
            last_forward_result=forward_results[-1],
            last_emitted_result=results_by_value[emitted_values[-1]],
            input_paths=paths,
            output_file=resolved_output,
            base_values=base_values,
            emitted_values=emitted_values,
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
        try:
            animation_response = self.render_animation_to_file(
                request=request,
                output_file=output_file,
                mode="progression",
                output_format="gif",
                frame_duration_ms=duration_ms,
                smooth_loop=smooth_loop,
            )
        except ValueError as exc:
            if (
                str(exc) == "Progression animation is not currently supported for "
                "layout='random'."
            ):
                raise ValueError(
                    "Progression GIF is not currently supported for layout='random'."
                ) from exc
            raise

        return ProgressionGifRenderResponse(
            peak_result=animation_response.last_forward_result,
            last_emitted_result=animation_response.last_emitted_result,
            input_paths=animation_response.input_paths,
            output_file=animation_response.output_file,
            base_slice_counts=animation_response.base_values,
            emitted_slice_counts=animation_response.emitted_values,
        )

    def render_random_gif_to_file(
        self,
        request: RenderRequest,
        output_file: Path | None = None,
        *,
        duration_ms: int = 250,
        frame_count: int = 8,
        smooth_loop: bool = False,
    ) -> RandomGifRenderResponse:
        """Render a random-layout shuffle GIF and save it to disk."""
        try:
            animation_response = self.render_animation_to_file(
                request=request,
                output_file=output_file,
                mode="random",
                output_format="gif",
                frame_duration_ms=duration_ms,
                frame_count=frame_count,
                smooth_loop=smooth_loop,
            )
        except ValueError as exc:
            if str(exc) == "Random animation requires layout='random'.":
                raise ValueError("Random GIF requires layout='random'.") from exc
            raise

        return RandomGifRenderResponse(
            initial_result=animation_response.first_forward_result,
            last_emitted_result=animation_response.last_emitted_result,
            input_paths=animation_response.input_paths,
            output_file=animation_response.output_file,
            base_seeds=animation_response.base_values,
            emitted_seeds=animation_response.emitted_values,
        )

    def render_progression_video_to_file(
        self,
        request: RenderRequest,
        output_file: Path | None = None,
        *,
        fps: int = 6,
        loops: int = 1,
        smooth_loop: bool = False,
    ) -> ProgressionVideoRenderResponse:
        """Render a power-of-two slice progression and save it as a video."""
        try:
            animation_response = self.render_animation_to_file(
                request=request,
                output_file=output_file,
                mode="progression",
                output_format=_output_format_from_output_file(output_file),
                fps=fps,
                loops=loops,
                smooth_loop=smooth_loop,
            )
        except ValueError as exc:
            if (
                str(exc) == "Progression animation is not currently supported for "
                "layout='random'."
            ):
                raise ValueError(
                    "Progression video is not currently supported for layout='random'."
                ) from exc
            raise

        return ProgressionVideoRenderResponse(
            peak_result=animation_response.last_forward_result,
            last_emitted_result=animation_response.last_emitted_result,
            input_paths=animation_response.input_paths,
            output_file=animation_response.output_file,
            base_slice_counts=animation_response.base_values,
            emitted_slice_counts=animation_response.emitted_values,
        )

    def render_random_video_to_file(
        self,
        request: RenderRequest,
        output_file: Path | None = None,
        *,
        fps: int = 6,
        loops: int = 1,
        frame_count: int = 8,
        smooth_loop: bool = False,
    ) -> RandomVideoRenderResponse:
        """Render a random-layout shuffle animation and save it as a video."""
        try:
            animation_response = self.render_animation_to_file(
                request=request,
                output_file=output_file,
                mode="random",
                output_format=_output_format_from_output_file(output_file),
                fps=fps,
                loops=loops,
                frame_count=frame_count,
                smooth_loop=smooth_loop,
            )
        except ValueError as exc:
            if str(exc) == "Random animation requires layout='random'.":
                raise ValueError("Random video requires layout='random'.") from exc
            raise

        return RandomVideoRenderResponse(
            initial_result=animation_response.first_forward_result,
            last_emitted_result=animation_response.last_emitted_result,
            input_paths=animation_response.input_paths,
            output_file=animation_response.output_file,
            base_seeds=animation_response.base_values,
            emitted_seeds=animation_response.emitted_values,
        )
