from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import pytimeslice.app as app_module
from pytimeslice import render_images
from pytimeslice.application.services import (
    AnimationRenderProgress,
    AnimationRenderResponse,
    ProgressionGifRenderResponse,
    ProgressionVideoRenderResponse,
    RandomGifRenderResponse,
    RandomVideoRenderResponse,
    RenderRequest,
    RenderResponse,
    RenderTimesliceService,
    VideoRenderRequest,
    VideoRenderResponse,
)
from pytimeslice.domain.models import (
    RGBImage,
    SliceEffects,
    TimesliceSpec,
    VideoFrameSelectionSpec,
    select_video_frame_indices,
)
from pytimeslice.interface.cli import _build_spec, build_parser, main as cli_main


def _solid_frame(value: int, *, width: int = 8, height: int = 2) -> RGBImage:
    return np.full((height, width, 3), value, dtype=np.uint8)


class RecordingLoader:
    def __init__(self, paths: list[Path], images: list[RGBImage]) -> None:
        self.paths = paths
        self.images = images
        self.get_image_paths_calls = 0
        self.load_images_calls = 0

    def get_image_paths(self, folder: Path) -> list[Path]:
        self.get_image_paths_calls += 1
        return self.paths

    def load_images(
        self,
        paths: list[Path],
        resize_mode: str = "crop",
    ) -> list[RGBImage]:
        self.load_images_calls += 1
        return self.images


class RecordingWriter:
    def __init__(self) -> None:
        self.saved_images: list[tuple[RGBImage, Path]] = []
        self.saved_gifs: list[tuple[list[RGBImage], Path, int]] = []
        self.saved_videos: list[tuple[list[RGBImage], Path, int]] = []

    def save(self, image: RGBImage, output_file: Path) -> None:
        self.saved_images.append((image, output_file))

    def save_gif(
        self,
        images: list[RGBImage],
        output_file: Path,
        *,
        duration_ms: int = 250,
    ) -> None:
        self.saved_gifs.append((images, output_file, duration_ms))

    def save_video(
        self,
        images: list[RGBImage],
        output_file: Path,
        *,
        fps: int = 6,
    ) -> None:
        self.saved_videos.append((images, output_file, fps))


class RecordingVideoLoader:
    def __init__(self, total_frames: int, frames: dict[int, RGBImage]) -> None:
        self.total_frames = total_frames
        self.frames = frames
        self.count_frames_calls: list[Path] = []
        self.load_frames_calls: list[tuple[Path, list[int], str]] = []

    def count_frames(self, video_file: Path) -> int:
        self.count_frames_calls.append(video_file)
        return self.total_frames

    def load_frames(
        self,
        video_file: Path,
        frame_indices: list[int],
        resize_mode: str = "crop",
    ) -> list[RGBImage]:
        self.load_frames_calls.append((video_file, list(frame_indices), resize_mode))
        return [self.frames[index] for index in frame_indices]


class RecordingRenderService:
    def __init__(
        self,
        response: RenderResponse,
        animation_response: AnimationRenderResponse | None = None,
        video_response: VideoRenderResponse | None = None,
    ) -> None:
        self.response = response
        self.animation_response = animation_response
        self.video_response = video_response
        self.render_requests: list[RenderRequest] = []
        self.render_to_file_calls: list[tuple[RenderRequest, Path | None]] = []
        self.render_video_calls: list[VideoRenderRequest] = []
        self.render_video_to_file_calls: list[
            tuple[VideoRenderRequest, Path | None]
        ] = []
        self.render_animation_to_file_calls: list[
            tuple[RenderRequest, Path | None, str, str, int, int, int, bool, int]
        ] = []

    def render(self, request: RenderRequest) -> RenderResponse:
        self.render_requests.append(request)
        return self.response

    def render_to_file(
        self,
        request: RenderRequest,
        output_file: Path | None = None,
    ) -> RenderResponse:
        self.render_to_file_calls.append((request, output_file))
        if output_file is None:
            return self.response
        return RenderResponse(
            result=self.response.result,
            input_paths=self.response.input_paths,
            output_file=output_file,
        )

    def render_animation_to_file(
        self,
        request: RenderRequest,
        output_file: Path | None = None,
        *,
        mode: str = "progression",
        output_format: str = "gif",
        frame_duration_ms: int = 250,
        fps: int = 6,
        loops: int = 1,
        smooth_loop: bool = False,
        frame_count: int = 8,
    ) -> AnimationRenderResponse:
        self.render_animation_to_file_calls.append(
            (
                request,
                output_file,
                mode,
                output_format,
                frame_duration_ms,
                fps,
                loops,
                smooth_loop,
                frame_count,
            )
        )
        if self.animation_response is None:
            raise AssertionError("animation_response was not configured for this test.")
        return self.animation_response

    def render_video(self, request: VideoRenderRequest) -> VideoRenderResponse:
        self.render_video_calls.append(request)
        if self.video_response is None:
            raise AssertionError("video_response was not configured for this test.")
        return self.video_response

    def render_video_to_file(
        self,
        request: VideoRenderRequest,
        output_file: Path | None = None,
    ) -> VideoRenderResponse:
        self.render_video_to_file_calls.append((request, output_file))
        if self.video_response is None:
            raise AssertionError("video_response was not configured for this test.")
        if output_file is None:
            return self.video_response
        return VideoRenderResponse(
            result=self.video_response.result,
            video_file=self.video_response.video_file,
            sampled_frame_indices=self.video_response.sampled_frame_indices,
            total_video_frames=self.video_response.total_video_frames,
            output_file=output_file,
        )


def test_render_to_file_defaults_to_out_folder_when_output_is_omitted(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / "001.png", input_folder / "002.png"]
    images = [_solid_frame(0), _solid_frame(255)]
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=RecordingWriter(),
    )

    response = service.render_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(num_slices=2),
        )
    )

    assert response.output_file is not None
    assert response.output_file.parent == tmp_path / "out"
    assert response.output_file.suffix == ".png"
    assert response.output_file.name.endswith("-timeslice.png")


def test_video_frame_indices_are_evenly_sampled() -> None:
    assert select_video_frame_indices(
        total_frames=10,
        spec=VideoFrameSelectionSpec(target_frame_count=4),
    ) == [0, 3, 6, 9]


def test_render_video_samples_frames_and_remains_pure(tmp_path: Path) -> None:
    video_file = tmp_path / "source.mp4"
    video_file.write_bytes(b"not a real video; loader is test double")
    frames = {
        0: _solid_frame(0, width=4, height=2),
        3: _solid_frame(120, width=4, height=2),
        6: _solid_frame(240, width=4, height=2),
    }
    video_loader = RecordingVideoLoader(total_frames=7, frames=frames)
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=[], images=[]),
        image_writer=writer,
        video_frame_loader=video_loader,
    )

    response = service.render_video(
        VideoRenderRequest(
            video_file=video_file,
            spec=TimesliceSpec(num_slices=3),
        )
    )

    assert response.video_file == video_file
    assert response.sampled_frame_indices == [0, 3, 6]
    assert response.total_video_frames == 7
    assert response.output_file is None
    assert video_loader.load_frames_calls == [(video_file, [0, 3, 6], "crop")]
    assert writer.saved_images == []


def test_render_video_to_file_writes_explicit_output(tmp_path: Path) -> None:
    video_file = tmp_path / "source.mp4"
    video_file.write_bytes(b"not a real video; loader is test double")
    output_file = tmp_path / "out" / "video-timeslice.png"
    frames = {
        0: _solid_frame(0, width=4, height=2),
        1: _solid_frame(120, width=4, height=2),
    }
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=[], images=[]),
        image_writer=writer,
        video_frame_loader=RecordingVideoLoader(total_frames=2, frames=frames),
    )

    response = service.render_video_to_file(
        VideoRenderRequest(
            video_file=video_file,
            spec=TimesliceSpec(num_slices=2),
        ),
        output_file=output_file,
    )

    assert response.output_file == output_file
    assert len(writer.saved_images) == 1
    assert writer.saved_images[0][1] == output_file


def test_render_video_to_file_defaults_to_video_sibling_out_folder(
    tmp_path: Path,
) -> None:
    video_file = tmp_path / "media" / "source.mp4"
    video_file.parent.mkdir()
    video_file.write_bytes(b"not a real video; loader is test double")
    frames = {
        0: _solid_frame(0, width=4, height=2),
        1: _solid_frame(120, width=4, height=2),
    }
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=[], images=[]),
        image_writer=RecordingWriter(),
        video_frame_loader=RecordingVideoLoader(total_frames=2, frames=frames),
    )

    response = service.render_video_to_file(
        VideoRenderRequest(
            video_file=video_file,
            spec=TimesliceSpec(num_slices=2),
        )
    )

    assert response.output_file is not None
    assert response.output_file.parent == video_file.parent / "out"
    assert response.output_file.name.endswith("-timeslice.png")


def test_app_render_folder_is_pure_and_does_not_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    expected = RenderResponse(
        result=render_images(
            images=[_solid_frame(0), _solid_frame(255)],
            spec=TimesliceSpec(num_slices=2),
        ),
        input_paths=[input_folder / "001.png", input_folder / "002.png"],
    )
    service = RecordingRenderService(response=expected)
    monkeypatch.setattr(app_module, "create_render_service", lambda: service)

    response = app_module.render_folder(
        input_folder=input_folder,
        spec=TimesliceSpec(num_slices=2),
    )

    assert response == expected
    assert len(service.render_requests) == 1
    assert service.render_requests[0].input_folder == input_folder
    assert service.render_requests[0].spec == TimesliceSpec(num_slices=2)
    assert service.render_to_file_calls == []


def test_app_render_folder_to_file_delegates_to_explicit_save_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    output_file = tmp_path / "out" / "timeslice.png"
    expected = RenderResponse(
        result=render_images(
            images=[_solid_frame(0), _solid_frame(255)],
            spec=TimesliceSpec(num_slices=2),
        ),
        input_paths=[input_folder / "001.png", input_folder / "002.png"],
    )
    service = RecordingRenderService(response=expected)
    monkeypatch.setattr(app_module, "create_render_service", lambda: service)

    response = app_module.render_folder_to_file(
        input_folder=input_folder,
        output_file=output_file,
        spec=TimesliceSpec(num_slices=2),
    )

    assert response.output_file == output_file
    assert service.render_requests == []
    assert len(service.render_to_file_calls) == 1
    request, requested_output = service.render_to_file_calls[0]
    assert request.input_folder == input_folder
    assert request.spec == TimesliceSpec(num_slices=2)
    assert requested_output == output_file


def test_app_render_folder_to_file_defaults_output_path_when_omitted(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    expected = RenderResponse(
        result=render_images(
            images=[_solid_frame(0), _solid_frame(255)],
            spec=TimesliceSpec(num_slices=2),
        ),
        input_paths=[input_folder / "001.png", input_folder / "002.png"],
    )
    service = RecordingRenderService(response=expected)
    monkeypatch.setattr(app_module, "create_render_service", lambda: service)

    response = app_module.render_folder_to_file(
        input_folder=input_folder,
        spec=TimesliceSpec(num_slices=2),
    )

    assert len(service.render_to_file_calls) == 1
    request, requested_output = service.render_to_file_calls[0]
    assert request.input_folder == input_folder
    assert requested_output is None
    assert response.output_file is None


def test_app_render_animation_delegates_to_animation_export(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    output_file = tmp_path / "out" / "animation.mov"
    result = render_images(
        images=[_solid_frame(0), _solid_frame(255)],
        spec=TimesliceSpec(num_slices=2),
    )
    expected = AnimationRenderResponse(
        mode="progression",
        output_format="mov",
        value_kind="slice_count",
        first_forward_result=result,
        last_forward_result=result,
        last_emitted_result=result,
        input_paths=[input_folder / "001.png", input_folder / "002.png"],
        output_file=output_file,
        base_values=[1, 2],
        emitted_values=[1, 2, 1, 2],
    )
    service = RecordingRenderService(
        response=RenderResponse(result=result, input_paths=expected.input_paths),
        animation_response=expected,
    )
    monkeypatch.setattr(app_module, "create_render_service", lambda: service)

    response = app_module.render_animation(
        input_folder=input_folder,
        output_file=output_file,
        spec=TimesliceSpec(num_slices=2),
        mode="progression",
        output_format="mov",
        fps=12,
        loops=2,
        smooth_loop=True,
    )

    assert response == expected
    assert len(service.render_animation_to_file_calls) == 1
    (
        request,
        requested_output,
        mode,
        output_format,
        frame_duration_ms,
        fps,
        loops,
        smooth_loop,
        frame_count,
    ) = service.render_animation_to_file_calls[0]
    assert request.input_folder == input_folder
    assert request.spec == TimesliceSpec(num_slices=2)
    assert requested_output == output_file
    assert mode == "progression"
    assert output_format == "mov"
    assert frame_duration_ms == 250
    assert fps == 12
    assert loops == 2
    assert smooth_loop is True
    assert frame_count == 8


def test_render_animation_to_file_exports_progression_gif(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(5)]
    images = [_solid_frame(index * 10, width=16) for index in range(5)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )

    response = service.render_animation_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(orientation="vertical"),
        ),
        mode="progression",
        output_format="gif",
        frame_duration_ms=120,
        smooth_loop=True,
    )

    assert response.mode == "progression"
    assert response.output_format == "gif"
    assert response.value_kind == "slice_count"
    assert response.base_values == [1, 2, 4, 8]
    assert response.emitted_values == [1, 2, 4, 8, 4, 2]
    assert response.output_file.suffix == ".gif"

    assert len(writer.saved_gifs) == 1
    frames, output_file, duration_ms = writer.saved_gifs[0]
    assert len(frames) == 6
    assert output_file == response.output_file
    assert duration_ms == 120


def test_render_animation_to_file_exports_random_mov(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(4)]
    images = [_solid_frame(index * 60, width=4, height=4) for index in range(4)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )
    output_file = tmp_path / "out" / "random.mov"

    response = service.render_animation_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(layout="random", num_blocks=4, random_seed=7),
        ),
        output_file=output_file,
        mode="random",
        output_format="mov",
        fps=12,
        loops=2,
        frame_count=3,
        smooth_loop=True,
    )

    assert response.mode == "random"
    assert response.output_format == "mov"
    assert response.value_kind == "seed"
    assert response.base_values == [7, 8, 9]
    assert response.emitted_values == [7, 8, 9, 8, 7, 8, 9, 8]
    assert response.output_file == output_file

    assert len(writer.saved_videos) == 1
    frames, saved_output, fps = writer.saved_videos[0]
    assert len(frames) == 8
    assert saved_output == output_file
    assert fps == 12


def test_render_animation_to_file_reports_progress_updates(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(5)]
    images = [_solid_frame(index * 10, width=16) for index in range(5)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )
    updates: list[AnimationRenderProgress] = []

    service.render_animation_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(orientation="vertical"),
        ),
        mode="progression",
        output_format="gif",
        frame_duration_ms=120,
        smooth_loop=True,
        progress_callback=updates.append,
    )

    assert [update.stage for update in updates] == [
        "loading_inputs",
        "rendering_frames",
        "rendering_frames",
        "rendering_frames",
        "rendering_frames",
        "encoding_output",
    ]
    assert updates[0].progress == pytest.approx(0.08)
    assert updates[-1].progress == pytest.approx(0.96)
    assert updates[-1].emitted_frame_count == 6
    assert updates[-2].completed_forward_frames == 4
    assert updates[-2].current_value == 8


def test_render_progression_gif_uses_power_of_two_slice_counts(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(5)]
    images = [_solid_frame(index * 10, width=16) for index in range(5)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )

    response = service.render_progression_gif_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(orientation="vertical"),
        ),
        duration_ms=120,
    )

    assert isinstance(response, ProgressionGifRenderResponse)
    assert response.base_slice_counts == [1, 2, 4, 8]
    assert response.emitted_slice_counts == [1, 2, 4, 8]
    assert response.output_file.parent == tmp_path / "out"
    assert response.output_file.suffix == ".gif"
    assert response.output_file.name.endswith("-progression.gif")
    assert len(response.peak_result.plan.bands) == 8
    assert len(response.last_emitted_result.plan.bands) == 8

    assert len(writer.saved_gifs) == 1
    frames, output_file, duration_ms = writer.saved_gifs[0]
    assert len(frames) == 4
    assert output_file == response.output_file
    assert duration_ms == 120


def test_render_progression_gif_can_use_smooth_loop_slice_counts(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(5)]
    images = [_solid_frame(index * 10, width=16) for index in range(5)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )

    response = service.render_progression_gif_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(orientation="vertical"),
        ),
        duration_ms=120,
        smooth_loop=True,
    )

    assert isinstance(response, ProgressionGifRenderResponse)
    assert response.base_slice_counts == [1, 2, 4, 8]
    assert response.emitted_slice_counts == [1, 2, 4, 8, 4, 2]
    assert len(response.peak_result.plan.bands) == 8
    assert len(response.last_emitted_result.plan.bands) == 2

    assert len(writer.saved_gifs) == 1
    frames, _, duration_ms = writer.saved_gifs[0]
    assert len(frames) == 6
    assert duration_ms == 120


def test_render_progression_gif_supports_mask_based_layouts(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(3)]
    images = [_solid_frame(index * 10, width=2, height=2) for index in range(3)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )

    response = service.render_progression_gif_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(layout="diagonal"),
        ),
        duration_ms=90,
    )

    assert response.base_slice_counts == [1, 2, 4]
    assert response.emitted_slice_counts == [1, 2, 4]
    assert response.peak_result.plan.layout == "diagonal"
    assert response.peak_result.plan.slice_map is not None

    assert len(writer.saved_gifs) == 1
    frames, _, duration_ms = writer.saved_gifs[0]
    assert len(frames) == 3
    assert duration_ms == 90


def test_render_progression_gif_rejects_random_layout_before_loading_images(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    loader = RecordingLoader(
        paths=[input_folder / "001.png"],
        images=[_solid_frame(0, width=4, height=4)],
    )
    service = RenderTimesliceService(
        sequence_loader=loader,
        image_writer=RecordingWriter(),
    )

    with pytest.raises(
        ValueError,
        match="Progression GIF is not currently supported for layout='random'.",
    ):
        service.render_progression_gif_to_file(
            RenderRequest(
                input_folder=input_folder,
                spec=TimesliceSpec(layout="random", num_blocks=4),
            ),
            duration_ms=120,
        )

    assert loader.get_image_paths_calls == 0
    assert loader.load_images_calls == 0


def test_render_progression_video_repeats_emitted_slice_counts_for_loops(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(5)]
    images = [_solid_frame(index * 10, width=16) for index in range(5)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )

    response = service.render_progression_video_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(orientation="vertical"),
        ),
        fps=6,
        loops=2,
        smooth_loop=True,
    )

    assert isinstance(response, ProgressionVideoRenderResponse)
    assert response.base_slice_counts == [1, 2, 4, 8]
    assert response.emitted_slice_counts == [1, 2, 4, 8, 4, 2, 1, 2, 4, 8, 4, 2]
    assert response.output_file.suffix == ".mp4"

    assert len(writer.saved_videos) == 1
    frames, output_file, fps = writer.saved_videos[0]
    assert len(frames) == 12
    assert output_file == response.output_file
    assert fps == 6


def test_render_progression_video_accepts_mov_output_file(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(3)]
    images = [_solid_frame(index * 10, width=8, height=4) for index in range(3)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )
    output_file = tmp_path / "out" / "progression.mov"

    response = service.render_progression_video_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(orientation="vertical"),
        ),
        output_file=output_file,
        fps=8,
    )

    assert response.output_file == output_file
    assert len(writer.saved_videos) == 1


def test_render_random_gif_uses_incrementing_seed_sequence(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(4)]
    images = [_solid_frame(index * 60, width=4, height=4) for index in range(4)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )

    response = service.render_random_gif_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(layout="random", num_blocks=4, random_seed=7),
        ),
        duration_ms=90,
        frame_count=3,
    )

    assert isinstance(response, RandomGifRenderResponse)
    assert response.base_seeds == [7, 8, 9]
    assert response.emitted_seeds == [7, 8, 9]
    assert response.output_file.parent == tmp_path / "out"
    assert response.output_file.suffix == ".gif"
    assert response.output_file.name.endswith("-random-shuffle.gif")

    assert len(writer.saved_gifs) == 1
    frames, output_file, duration_ms = writer.saved_gifs[0]
    assert output_file == response.output_file
    assert duration_ms == 90
    assert len(frames) == 3

    expected_frames = [
        render_images(
            images=images,
            spec=TimesliceSpec(layout="random", num_blocks=4, random_seed=seed),
        ).image
        for seed in (7, 8, 9)
    ]
    assert all(
        np.array_equal(frame, expected)
        for frame, expected in zip(frames, expected_frames)
    )


def test_render_random_gif_supports_smooth_loop(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(4)]
    images = [_solid_frame(index * 60, width=4, height=4) for index in range(4)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )

    response = service.render_random_gif_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(layout="random", num_blocks=4, random_seed=3),
        ),
        duration_ms=90,
        frame_count=3,
        smooth_loop=True,
    )

    assert response.base_seeds == [3, 4, 5]
    assert response.emitted_seeds == [3, 4, 5, 4]
    expected_last = render_images(
        images=images,
        spec=TimesliceSpec(layout="random", num_blocks=4, random_seed=4),
    )
    assert np.array_equal(response.last_emitted_result.image, expected_last.image)
    assert response.last_emitted_result.plan.layout == expected_last.plan.layout
    assert response.last_emitted_result.plan.slice_frame_indices == (
        expected_last.plan.slice_frame_indices
    )
    assert response.last_emitted_result.plan.slice_map is not None
    assert expected_last.plan.slice_map is not None
    assert np.array_equal(
        response.last_emitted_result.plan.slice_map,
        expected_last.plan.slice_map,
    )
    assert (
        response.last_emitted_result.used_frame_indices
        == expected_last.used_frame_indices
    )

    assert len(writer.saved_gifs) == 1
    frames, _, duration_ms = writer.saved_gifs[0]
    assert len(frames) == 4
    assert duration_ms == 90


def test_render_random_gif_rejects_non_random_layout_before_loading_images(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    loader = RecordingLoader(
        paths=[input_folder / "001.png"],
        images=[_solid_frame(0, width=4, height=4)],
    )
    service = RenderTimesliceService(
        sequence_loader=loader,
        image_writer=RecordingWriter(),
    )

    with pytest.raises(ValueError, match="requires layout='random'"):
        service.render_random_gif_to_file(
            RenderRequest(
                input_folder=input_folder,
                spec=TimesliceSpec(layout="circular", num_slices=4),
            ),
            duration_ms=120,
            frame_count=3,
        )

    assert loader.get_image_paths_calls == 0
    assert loader.load_images_calls == 0


def test_render_random_video_repeats_emitted_seeds_for_loops(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(4)]
    images = [_solid_frame(index * 60, width=4, height=4) for index in range(4)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )

    response = service.render_random_video_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(layout="random", num_blocks=4, random_seed=7),
        ),
        fps=12,
        frame_count=3,
        loops=2,
        smooth_loop=True,
    )

    assert isinstance(response, RandomVideoRenderResponse)
    assert response.base_seeds == [7, 8, 9]
    assert response.emitted_seeds == [7, 8, 9, 8, 7, 8, 9, 8]
    assert response.output_file.suffix == ".mp4"

    assert len(writer.saved_videos) == 1
    frames, output_file, fps = writer.saved_videos[0]
    assert len(frames) == 8
    assert output_file == response.output_file
    assert fps == 12


def test_render_random_video_rejects_non_random_layout_before_loading_images(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    loader = RecordingLoader(
        paths=[input_folder / "001.png"],
        images=[_solid_frame(0, width=4, height=4)],
    )
    service = RenderTimesliceService(
        sequence_loader=loader,
        image_writer=RecordingWriter(),
    )

    with pytest.raises(ValueError, match="requires layout='random'"):
        service.render_random_video_to_file(
            RenderRequest(
                input_folder=input_folder,
                spec=TimesliceSpec(layout="circular", num_slices=4),
            ),
            fps=12,
            frame_count=3,
        )

    assert loader.get_image_paths_calls == 0
    assert loader.load_images_calls == 0


def test_service_rejects_invalid_effects_before_loading_images(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    loader = RecordingLoader(
        paths=[input_folder / "001.png"],
        images=[_solid_frame(0)],
    )
    service = RenderTimesliceService(
        sequence_loader=loader,
        image_writer=RecordingWriter(),
    )

    with pytest.raises(ValueError, match="effects.border_width must be at least 0."):
        service.render(
            RenderRequest(
                input_folder=input_folder,
                spec=TimesliceSpec(
                    effects=SliceEffects(border_width=-1),
                ),
            )
        )

    assert loader.get_image_paths_calls == 0
    assert loader.load_images_calls == 0


def test_service_rejects_non_positive_gif_duration_before_loading_images(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    loader = RecordingLoader(
        paths=[input_folder / "001.png"],
        images=[_solid_frame(0)],
    )
    service = RenderTimesliceService(
        sequence_loader=loader,
        image_writer=RecordingWriter(),
    )

    with pytest.raises(ValueError, match="duration_ms must be greater than 0."):
        service.render_progression_gif_to_file(
            RenderRequest(
                input_folder=input_folder,
                spec=TimesliceSpec(),
            ),
            duration_ms=0,
        )

    assert loader.get_image_paths_calls == 0
    assert loader.load_images_calls == 0


def test_cli_output_file_is_optional_for_progression_gif() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--progression-gif",
            "--gif-frame-duration-ms",
            "180",
            "--gif-smooth-loop",
        ]
    )

    assert args.output_file is None
    assert args.progression_gif is True
    assert args.gif_frame_duration_ms == 180
    assert args.gif_smooth_loop is True


def test_cli_random_gif_output_file_is_optional() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "random",
            "--random-gif",
            "--random-gif-frames",
            "6",
        ]
    )

    assert args.output_file is None
    assert args.random_gif is True
    assert args.random_gif_frames == 6


def test_cli_parses_video_input_options() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "source.mp4",
            "out/timeslice.png",
            "--video",
            "--video-frames",
            "12",
        ]
    )

    assert args.input_folder == Path("source.mp4")
    assert args.output_file == Path("out/timeslice.png")
    assert args.video is True
    assert args.video_frames == 12


def test_cli_output_file_is_optional_for_progression_video() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--progression-video",
            "--video-fps",
            "12",
            "--video-loops",
            "2",
        ]
    )

    assert args.output_file is None
    assert args.progression_video is True
    assert args.video_fps == 12
    assert args.video_loops == 2


def test_cli_random_video_output_file_is_optional() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "random",
            "--random-video",
            "--random-video-frames",
            "6",
        ]
    )

    assert args.output_file is None
    assert args.random_video is True
    assert args.random_video_frames == 6


def test_cli_unified_animation_output_file_is_optional() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--animate",
            "--animation-mode",
            "random",
            "--animation-format",
            "mov",
            "--animation-frame-count",
            "6",
            "--animation-fps",
            "12",
            "--animation-loops",
            "2",
            "--animation-smooth-loop",
        ]
    )

    assert args.output_file is None
    assert args.animate is True
    assert args.animation_mode == "random"
    assert args.animation_format == "mov"
    assert args.animation_frame_count == 6
    assert args.animation_fps == 12
    assert args.animation_loops == 2
    assert args.animation_smooth_loop is True


def test_cli_builds_diagonal_layout_spec() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "diagonal",
            "--slices",
            "6",
            "--reverse-time",
        ]
    )

    spec = _build_spec(args, parser)

    assert spec == TimesliceSpec(
        orientation="vertical",
        layout="diagonal",
        num_slices=6,
        reverse_time=True,
    )


def test_cli_builds_circular_layout_spec() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "circular",
            "--slices",
            "6",
        ]
    )

    spec = _build_spec(args, parser)

    assert spec == TimesliceSpec(
        orientation="vertical",
        layout="circular",
        num_slices=6,
    )


def test_cli_builds_random_layout_spec() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "random",
            "--random-blocks",
            "16",
            "--random-seed",
            "7",
        ]
    )

    spec = _build_spec(args, parser)

    assert spec == TimesliceSpec(
        orientation="vertical",
        layout="random",
        num_blocks=16,
        random_seed=7,
    )


def test_cli_accepts_rectangular_power_of_two_random_block_counts() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "random",
            "--random-blocks",
            "128",
        ]
    )

    spec = _build_spec(args, parser)

    assert spec == TimesliceSpec(
        orientation="vertical",
        layout="random",
        num_blocks=128,
    )


def test_cli_loads_user_defined_mask_layout_from_npy(tmp_path: Path) -> None:
    parser = build_parser()
    mask_file = tmp_path / "layout-mask.npy"
    expected_mask = np.array([[0.0, 2.0], [3.0, 1.0]], dtype=np.float64)
    np.save(mask_file, expected_mask)

    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "mask",
            "--layout-mask",
            str(mask_file),
            "--slices",
            "2",
        ]
    )

    spec = _build_spec(args, parser)

    assert spec.layout == "mask"
    assert spec.layout_mask is not None
    assert np.array_equal(spec.layout_mask, expected_mask)


def test_cli_requires_layout_mask_for_mask_layout() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "mask",
            "--slices",
            "2",
        ]
    )

    with pytest.raises(SystemExit):
        _build_spec(args, parser)


def test_cli_rejects_slices_for_random_layout() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "random",
            "--slices",
            "8",
        ]
    )

    with pytest.raises(SystemExit):
        _build_spec(args, parser)


def test_cli_rejects_invalid_random_block_count() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "random",
            "--random-blocks",
            "12",
        ]
    )

    with pytest.raises(SystemExit):
        _build_spec(args, parser)


def test_cli_rejects_random_gif_for_non_random_layout(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            "frames",
            "--layout",
            "circular",
            "--random-gif",
            "--slices",
            "4",
        ],
    )

    with pytest.raises(SystemExit):
        cli_main()


def test_cli_rejects_progression_gif_with_random_gif(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            "frames",
            "--layout",
            "random",
            "--random-blocks",
            "4",
            "--progression-gif",
            "--random-gif",
        ],
    )

    with pytest.raises(SystemExit):
        cli_main()


def test_cli_rejects_progression_video_with_random_video(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            "frames",
            "--layout",
            "random",
            "--random-blocks",
            "4",
            "--progression-video",
            "--random-video",
        ],
    )

    with pytest.raises(SystemExit):
        cli_main()


def test_cli_rejects_unified_animation_with_legacy_animation_flag(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            "frames",
            "--animate",
            "--progression-gif",
        ],
    )

    with pytest.raises(SystemExit):
        cli_main()


def test_cli_rejects_effects_for_non_band_layouts() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "spiral",
            "--border",
            "1",
        ]
    )

    with pytest.raises(SystemExit):
        _build_spec(args, parser)


def test_cli_rejects_layout_mask_without_mask_layout(tmp_path: Path) -> None:
    parser = build_parser()
    mask_file = tmp_path / "layout-mask.npy"
    np.save(mask_file, np.array([[0.0]], dtype=np.float64))
    args = parser.parse_args(
        [
            "frames",
            "--layout-mask",
            str(mask_file),
        ]
    )

    with pytest.raises(SystemExit):
        _build_spec(args, parser)


def test_cli_rejects_negative_effect_widths() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "frames",
                "--border",
                "-1",
            ]
        )


def test_cli_rejects_non_positive_gif_duration() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "frames",
                "--progression-gif",
                "--gif-frame-duration-ms",
                "0",
            ]
        )


def test_cli_random_gif_renders_output(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    for index, value in enumerate((0, 60, 120, 180)):
        Image.fromarray(_solid_frame(value, width=4, height=4)).save(
            input_folder / f"{index:03}.png"
        )

    output_file = tmp_path / "random-shuffle.gif"
    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            str(input_folder),
            str(output_file),
            "--layout",
            "random",
            "--random-blocks",
            "4",
            "--random-seed",
            "7",
            "--random-gif",
            "--random-gif-frames",
            "3",
            "--gif-frame-duration-ms",
            "90",
        ],
    )

    cli_main()

    with Image.open(output_file) as rendered:
        assert rendered.n_frames == 3
        assert rendered.size == (4, 4)


def test_cli_progression_video_delegates_to_unified_animation_export(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    output_file = tmp_path / "progression.mov"
    captured: dict[str, object] = {}
    result = render_images(
        images=[
            _solid_frame(0, width=4, height=4),
            _solid_frame(120, width=4, height=4),
        ],
        spec=TimesliceSpec(num_slices=2),
    )

    def fake_render_animation(
        input_folder: Path,
        output_file: Path | None = None,
        spec: TimesliceSpec | None = None,
        resize_mode: str = "crop",
        *,
        mode: str = "progression",
        output_format: str = "gif",
        frame_duration_ms: int = 250,
        fps: int = 6,
        loops: int = 1,
        smooth_loop: bool = False,
        frame_count: int = 8,
    ) -> AnimationRenderResponse:
        captured["input_folder"] = input_folder
        captured["output_file"] = output_file
        captured["spec"] = spec
        captured["resize_mode"] = resize_mode
        captured["mode"] = mode
        captured["output_format"] = output_format
        captured["frame_duration_ms"] = frame_duration_ms
        captured["fps"] = fps
        captured["loops"] = loops
        captured["smooth_loop"] = smooth_loop
        captured["frame_count"] = frame_count
        return AnimationRenderResponse(
            mode=mode,
            output_format=output_format,
            value_kind="slice_count",
            first_forward_result=result,
            last_forward_result=result,
            last_emitted_result=result,
            input_paths=[input_folder / "001.png"],
            output_file=output_file
            if output_file is not None
            else input_folder / "out.mp4",
            base_values=[1, 2],
            emitted_values=[1, 2, 1, 2],
        )

    monkeypatch.setattr(
        "pytimeslice.interface.cli.render_animation",
        fake_render_animation,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            str(input_folder),
            str(output_file),
            "--progression-video",
            "--slices",
            "2",
            "--video-fps",
            "12",
            "--video-loops",
            "2",
            "--gif-smooth-loop",
        ],
    )

    cli_main()

    assert captured["input_folder"] == input_folder
    assert captured["output_file"] == output_file
    assert captured["spec"] == TimesliceSpec(
        orientation="vertical", layout="bands", num_slices=2
    )
    assert captured["mode"] == "progression"
    assert captured["output_format"] == "mov"
    assert captured["frame_duration_ms"] == 250
    assert captured["fps"] == 12
    assert captured["loops"] == 2
    assert captured["smooth_loop"] is True
    assert captured["frame_count"] == 8


def test_cli_unified_random_animation_delegates_to_render_animation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    output_file = tmp_path / "random.mov"
    captured: dict[str, object] = {}
    result = render_images(
        images=[
            _solid_frame(0, width=4, height=4),
            _solid_frame(120, width=4, height=4),
            _solid_frame(240, width=4, height=4),
            _solid_frame(60, width=4, height=4),
        ],
        spec=TimesliceSpec(layout="random", num_blocks=4, random_seed=7),
    )

    def fake_render_animation(
        input_folder: Path,
        output_file: Path | None = None,
        spec: TimesliceSpec | None = None,
        resize_mode: str = "crop",
        *,
        mode: str = "progression",
        output_format: str = "gif",
        frame_duration_ms: int = 250,
        fps: int = 6,
        loops: int = 1,
        smooth_loop: bool = False,
        frame_count: int = 8,
    ) -> AnimationRenderResponse:
        captured["input_folder"] = input_folder
        captured["output_file"] = output_file
        captured["spec"] = spec
        captured["resize_mode"] = resize_mode
        captured["mode"] = mode
        captured["output_format"] = output_format
        captured["frame_duration_ms"] = frame_duration_ms
        captured["fps"] = fps
        captured["loops"] = loops
        captured["frame_count"] = frame_count
        captured["smooth_loop"] = smooth_loop
        return AnimationRenderResponse(
            mode=mode,
            output_format=output_format,
            value_kind="seed",
            first_forward_result=result,
            last_forward_result=result,
            last_emitted_result=result,
            input_paths=[input_folder / "001.png"],
            output_file=output_file
            if output_file is not None
            else input_folder / "out.mp4",
            base_values=[7, 8, 9],
            emitted_values=[7, 8, 9, 8, 7, 8, 9, 8],
        )

    monkeypatch.setattr(
        "pytimeslice.interface.cli.render_animation",
        fake_render_animation,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            str(input_folder),
            str(output_file),
            "--layout",
            "random",
            "--random-blocks",
            "4",
            "--random-seed",
            "7",
            "--animate",
            "--animation-mode",
            "random",
            "--animation-format",
            "mov",
            "--animation-frame-count",
            "3",
            "--animation-fps",
            "10",
            "--animation-loops",
            "2",
            "--animation-smooth-loop",
        ],
    )

    cli_main()

    assert captured["input_folder"] == input_folder
    assert captured["output_file"] == output_file
    assert captured["spec"] == TimesliceSpec(
        orientation="vertical",
        layout="random",
        num_blocks=4,
        random_seed=7,
    )
    assert captured["mode"] == "random"
    assert captured["output_format"] == "mov"
    assert captured["frame_duration_ms"] == 250
    assert captured["fps"] == 10
    assert captured["loops"] == 2
    assert captured["frame_count"] == 3
    assert captured["smooth_loop"] is True


def test_cli_manual_assigned_paths_renders_output(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "manual-assigned.png"
    paths: list[Path] = []
    for index, value in enumerate((10, 200, 50, 0, 150)):
        path = tmp_path / f"{index}.png"
        Image.fromarray(_solid_frame(value, width=2, height=10)).save(path)
        paths.append(path)

    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            str(output_file),
            "--assigned-path",
            str(paths[0]),
            "--assigned-path",
            str(paths[1]),
            "--assigned-path",
            str(paths[2]),
            "--assigned-path",
            str(paths[3]),
            "--assigned-path",
            str(paths[4]),
            "--orientation",
            "horizontal",
            "--slices",
            "5",
            "--canvas-width",
            "2",
            "--canvas-height",
            "10",
        ],
    )

    cli_main()

    rendered = np.array(Image.open(output_file).convert("RGB"), dtype=np.uint8)
    assert rendered[:, 0, 0].tolist() == [10, 10, 200, 200, 50, 50, 0, 0, 150, 150]


def test_cli_manual_slot_paths_can_render_partial_preview(
    monkeypatch,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.fromarray(_solid_frame(80, width=4, height=2)).save(first)
    Image.fromarray(_solid_frame(180, width=4, height=2)).save(second)
    output_file = tmp_path / "manual-partial.png"

    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            str(output_file),
            "--slot-path",
            "1",
            str(first),
            "--slot-path",
            "3",
            str(second),
            "--orientation",
            "vertical",
            "--slices",
            "4",
            "--canvas-width",
            "8",
            "--canvas-height",
            "2",
        ],
    )

    cli_main()

    rendered = np.array(Image.open(output_file).convert("RGB"), dtype=np.uint8)
    assert rendered[0, :, 0].tolist() == [0, 0, 80, 80, 0, 0, 180, 180]


def test_cli_manual_empty_creates_blank_canvas(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "manual-empty.png"

    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            str(output_file),
            "--manual-empty",
            "--layout",
            "diagonal",
            "--slices",
            "4",
            "--canvas-width",
            "6",
            "--canvas-height",
            "4",
        ],
    )

    cli_main()

    rendered = np.array(Image.open(output_file).convert("RGB"), dtype=np.uint8)
    assert rendered.shape == (4, 6, 3)
    assert np.count_nonzero(rendered) == 0


def test_cli_manual_mode_requires_slices(monkeypatch, tmp_path: Path) -> None:
    output_file = tmp_path / "manual-missing-slices.png"

    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            str(output_file),
            "--manual-empty",
        ],
    )

    with pytest.raises(SystemExit):
        cli_main()


def test_cli_manual_mode_rejects_mixed_assignment_styles(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "manual-invalid.png"

    monkeypatch.setattr(
        "sys.argv",
        [
            "pytimeslice",
            str(output_file),
            "--assigned-path",
            str(tmp_path / "a.png"),
            "--slot-path",
            "0",
            str(tmp_path / "b.png"),
            "--slices",
            "1",
        ],
    )

    with pytest.raises(SystemExit):
        cli_main()
